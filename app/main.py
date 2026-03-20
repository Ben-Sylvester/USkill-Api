"""USKill Engine API v2 — application factory."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import get_settings
from app.middleware import ExceptionMiddleware, LoggingMiddleware, RequestIDMiddleware
from app.rate_limit import RateLimitMiddleware
from app.cache import get_redis, close_redis
from app.database import wait_for_db, dispose_engine
from app.routers import (
    api_keys_router, connections_router, domains_router,
    jobs_router, primitives_router, skills_router,
)

settings = get_settings()

# ── Structured logging ─────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
logging.basicConfig(level=logging.INFO)
log = structlog.get_logger()


# ── Lifespan (replaces deprecated @app.on_event) ───────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────
    log.info("startup_begin", version=settings.app_version, env=settings.app_env)

    # 1. Wait for Postgres (retry with backoff — safe for k8s init)
    if not settings.is_test:
        await wait_for_db()

    # 2. Warm up Redis (fail-open — rate limiting degrades gracefully)
    try:
        r = get_redis()
        await r.ping()
        log.info("redis_ready")
    except Exception as exc:
        log.warning("redis_unavailable", error=str(exc))

    log.info("startup_complete")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────
    log.info("shutdown_begin")
    await close_redis()
    await dispose_engine()
    log.info("shutdown_complete")


# ── App factory ────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="USKill Engine API",
        description=(
            "Universal Skill Transfer Protocol — extract skills from any agent domain, "
            "score cross-domain compatibility via 6D feature-vector cosine similarity, "
            "and adapt + inject into any destination domain. No model required."
        ),
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    # ── Middleware (outermost first) ───────────────────────────────────
    app.add_middleware(ExceptionMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID", "X-API-Version", "X-Response-Time-Ms",
            "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset",
        ],
    )

    # ── Prometheus metrics ────────────────────────────────────────────
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # ── OpenTelemetry (no-op when OTEL_ENABLED=false) ────────────────
    from app.telemetry import setup_telemetry
    setup_telemetry(app)

    # ── Routers ───────────────────────────────────────────────────────
    prefix = "/v2"
    app.include_router(api_keys_router, prefix=prefix)
    app.include_router(connections_router, prefix=prefix)
    app.include_router(skills_router, prefix=prefix)
    app.include_router(domains_router, prefix=prefix)
    app.include_router(jobs_router, prefix=prefix)
    app.include_router(primitives_router, prefix=prefix)

    # ── Health endpoint ───────────────────────────────────────────────
    @app.get("/health", tags=["System"])
    async def health():
        """
        Deep health check — verifies DB and Redis connectivity.
        Returns 200 if all required dependencies are healthy,
        503 if a required dependency is down.
        """
        checks: dict[str, dict] = {}
        healthy = True

        # Database
        if settings.is_test:
            checks["database"] = {"status": "ok", "note": "skipped in test mode"}
        else:
            try:
                from app.database import engine
                from sqlalchemy import text
                t0 = time.perf_counter()
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                checks["database"] = {
                    "status": "ok",
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                }
            except Exception as exc:
                checks["database"] = {"status": "error", "error": str(exc)}
                healthy = False

        # Redis (optional dependency — degraded, not down)
        try:
            t0 = time.perf_counter()
            r = get_redis()
            await r.ping()
            checks["redis"] = {
                "status": "ok",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            }
        except Exception as exc:
            # Redis unavailable = degraded (rate limiting fails open, no jobs)
            checks["redis"] = {"status": "degraded", "error": str(exc)}

        # In test environment always return 200 (DB is overridden via DI)
        status_code = 200 if (healthy or settings.is_test) else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ok" if healthy else "degraded",
                "version": settings.app_version,
                "environment": settings.app_env,
                "checks": checks,
            },
        )

    @app.get("/", tags=["System"])
    async def root():
        return {
            "name": "USKill Engine API",
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/health",
        }

    # ── Exception handlers ────────────────────────────────────────────
    from fastapi.exceptions import HTTPException as FastAPIHTTPException, RequestValidationError

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        rid = getattr(request.state, "request_id", None)
        errors = exc.errors()
        first = errors[0] if errors else {}
        field = ".".join(str(x) for x in first.get("loc", [])[1:])
        return JSONResponse(
            status_code=422,
            content={
                "error": "INVALID_REQUEST",
                "message": first.get("msg", "Validation error"),
                "field": field or None,
                "request_id": rid,
            },
        )

    @app.exception_handler(FastAPIHTTPException)
    async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
        rid = getattr(request.state, "request_id", None)
        if isinstance(exc.detail, dict):
            body = {**exc.detail}
            body.setdefault("request_id", rid)
            return JSONResponse(status_code=exc.status_code, content=body)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "HTTP_ERROR", "message": str(exc.detail), "request_id": rid},
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        rid = getattr(request.state, "request_id", None)
        if hasattr(exc, "detail") and isinstance(exc.detail, dict):
            body = {**exc.detail}
            body.setdefault("request_id", rid)
            return JSONResponse(status_code=404, content=body)
        return JSONResponse(
            status_code=404,
            content={
                "error": "NOT_FOUND",
                "message": f"Route {request.method} {request.url.path} not found.",
                "request_id": rid,
            },
        )

    @app.exception_handler(422)
    async def validation_error_handler(request: Request, exc):
        rid = getattr(request.state, "request_id", None)
        if hasattr(exc, "detail") and isinstance(exc.detail, dict):
            body = {**exc.detail}
            body.setdefault("request_id", rid)
            return JSONResponse(status_code=422, content=body)
        if hasattr(exc, "errors"):
            errors = exc.errors()
            first = errors[0] if errors else {}
            field = ".".join(str(x) for x in first.get("loc", [])[1:])
            return JSONResponse(
                status_code=422,
                content={
                    "error": "INVALID_REQUEST",
                    "message": first.get("msg", "Validation error"),
                    "field": field or None,
                    "request_id": rid,
                },
            )
        return JSONResponse(
            status_code=422,
            content={"error": "INVALID_REQUEST", "message": str(exc), "request_id": rid},
        )

    return app


app = create_app()
