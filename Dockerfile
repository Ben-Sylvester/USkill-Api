# ═══════════════════════════════════════════════════════════════════════════
#  USKill Engine API — Production Dockerfile
#
#  Three stages:
#    builder   — installs Python deps into /install (no dev deps, no cache)
#    migrate   — runs `alembic upgrade head` as a one-shot init container
#    runtime   — serves the FastAPI app; never runs migrations
#
#  Why separate migration stage?
#    Running `alembic upgrade head` inside the app container causes a race
#    condition when deploying multiple replicas simultaneously. The correct
#    pattern is a k8s initContainer (or a `docker compose` depends_on hook)
#    that runs migrations exactly once before the API pods start.
# ═══════════════════════════════════════════════════════════════════════════

# ── Stage 1: dependency builder ─────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: migrate (init container) ───────────────────────────────────
FROM python:3.11-slim AS migrate

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 1001 uskill \
    && adduser  --system --uid 1001 --ingroup uskill --no-create-home uskill

COPY --from=builder /install /usr/local

WORKDIR /app
COPY --chown=uskill:uskill app/       ./app/
COPY --chown=uskill:uskill alembic/   ./alembic/
COPY --chown=uskill:uskill alembic.ini .

USER uskill

# Single command: run all pending migrations and exit (code 0 = success)
CMD ["alembic", "upgrade", "head"]


# ── Stage 3: runtime ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="USKill Engine API"
LABEL org.opencontainers.image.version="2.0.0"
LABEL org.opencontainers.image.description="Universal Skill Transfer Protocol API"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 1001 uskill \
    && adduser  --system --uid 1001 --ingroup uskill --no-create-home uskill

COPY --from=builder /install /usr/local

WORKDIR /app

COPY --chown=uskill:uskill app/       ./app/
COPY --chown=uskill:uskill alembic/   ./alembic/
COPY --chown=uskill:uskill alembic.ini .

USER uskill

EXPOSE 8000

# Health check — /health now verifies DB + Redis connectivity
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Runtime does NOT run migrations — handled by the migrate stage / initContainer
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--proxy-headers", \
     "--forwarded-allow-ips=*"]
