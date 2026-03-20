# ⬡ USKill Engine API v2.0.0

**Universal Skill Transfer Protocol** — extract skills from any agent domain, score cross-domain compatibility via 6D feature-vector cosine similarity, and adapt + inject into any destination domain.

**No model required. No code generation. Pure math + table lookups.**

---

## Table of Contents

- [How it works](#how-it-works)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [API Reference](#api-reference)
  - [Connections (E2E)](#connections)
  - [Skills](#skills)
  - [Domains](#domains)
  - [Primitives](#primitives)
  - [Jobs](#jobs)
- [Authentication](#authentication)
- [Rate Limits](#rate-limits)
- [Primitive Taxonomy](#primitive-taxonomy)
- [Domain Feature Vectors](#domain-feature-vectors)
- [Scoring Algorithm](#scoring-algorithm)
- [Configuration](#configuration)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)

---

## How it works

```
Source Agent (domain A)
        │
        │  Decompose task → which of 48 primitives does it use?
        ▼
   Skill Object  {primitives[], feature_vector, transferability}
        │
        │  cosineSim(prim.features, domainB.features)  ← pure math
        │  blend with BCM[A][B]                        ← table lookup
        ▼
   Compatibility Score + Gap Report
        │
        │  For each primitive → lookup domainB implementation  ← table lookup
        ▼
  Destination Agent (domain B)  receives adapted skill
```

Every step is either **float math** or a **dict lookup**. No LLM, no Docker, no code execution.

---

## Quick Start

### 1. Start infrastructure

```bash
make docker-up
```

### 2. Apply schema

```bash
make migrate
```

### 3. Create an API key

```bash
make seed
# → usk_prod_<32 hex chars>  (save this — shown once)
```

### 4. Start the API

```bash
make dev
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI, dev mode only)
```

### 5. Create your first E2E connection and transfer a skill

```bash
# Create a source→destination connection
curl -X POST http://localhost:8000/v2/connections \
  -H "Authorization: Bearer usk_prod_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Robot → Finance pipeline",
    "source_domain": "robotics_sim",
    "destination_domain": "finance"
  }'

# → {"connection_id": "cn_3f8a1b2c", ...}

# Extract + score + adapt in one call
curl -X POST http://localhost:8000/v2/connections/cn_3f8a1b2c/sync \
  -H "Authorization: Bearer usk_prod_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Detect and classify anomalous signals in real time",
    "episodes": 1000
  }'

# → {"compat_score": 0.712, "status": "INJECTED", "adapter_log": [...], "gaps": [...]}
```

---

## Architecture

```
app/
├── main.py              App factory — middleware stack, router registration
├── config.py            Pydantic-settings — all config from env vars
├── database.py          Async SQLAlchemy engine + session
├── auth.py              API key validation (bcrypt), org/plan resolution
├── middleware.py        RequestID, structured logging, exception handler
├── cache.py             Redis client, rate limit helpers, job queue
├── rate_limit.py        Per-plan sliding-window rate limiting middleware
├── worker.py            Background job processor (async extract + batch)
│
├── data/
│   ├── primitives.py    48 primitives × 6D FVs × 8 domain impls = 384 impls
│   ├── domains.py       8 built-in domain feature vectors
│   └── bcm.py           8×8 base compatibility matrix (64 empirical scores)
│
├── models/              SQLAlchemy async ORM models
│   ├── api_key.py       Hashed keys, plan, scopes, expiry
│   ├── connection.py    E2E source→destination channel
│   ├── skill.py         SkillObject with rollback + lineage
│   ├── transfer.py      Per-transfer audit record
│   ├── domain.py        Custom domain registry
│   └── job.py           Async job tracker
│
├── schemas/             Pydantic v2 request/response validation
├── services/            Pure business logic — no DB in scorer/adapter
│   ├── scorer.py        Cosine sim + BCM blend scoring (no await)
│   ├── adapter.py       Primitive → implementation lookup
│   ├── extractor.py     Deterministic skill extraction (CSPRNG for IDs)
│   ├── domain_resolver.py  Built-in + custom FV resolution
│   └── webhook.py       HMAC-SHA256 signed delivery, exponential retry
│
└── routers/             FastAPI routers (all under /v2/)
    ├── connections.py   POST/GET/LIST/SYNC/HISTORY/DELETE
    ├── skills.py        extract/list/get/graph/score/transfer/rollback/refine/validate/batch/delete
    ├── domains.py       list/register/compat-matrix
    ├── jobs.py          GET /jobs/:id
    └── primitives.py    list/get taxonomy browser
```

### Key design decisions

| Decision | Rationale |
|---|---|
| No LLM in scoring/adapting | Scoring is deterministic cosine similarity. Adapting is a dict lookup. Both are 100× faster and cheaper than any model call. |
| CSPRNG for IDs | `secrets.token_hex` not `random.random()` — cryptographically random, no collision risk. |
| Rollback tokens | Generated at extraction, 72h expiry, single-use — safe injection abort. |
| Fail-open rate limiting | Redis unavailable → allow request. Availability > strict limiting. |
| SQLite in tests | No Postgres needed to run `pytest`. Full integration coverage without a container. |
| Primitive FVs are static | The 6D taxonomy is a domain-expert specification, not trained. Changing it is a schema migration. |

---

## API Reference

All endpoints are under `/v2/`. All responses include:
- `request_id` — for tracing/support
- `X-Request-ID` header
- `X-RateLimit-*` headers
- `X-API-Version: 2` header

### Error envelope

Every error returns:
```json
{
  "error":      "SKILL_NOT_FOUND",
  "message":    "No skill with id sk_3f8a1b2c",
  "field":      null,
  "request_id": "req_9d8e7c6b"
}
```

---

### Connections

A **Connection** is the primary unit — a named, persistent E2E link between a source and destination domain. All skill flows run through it.

```
Source Agent ──→ USKill (extract + score + adapt) ──→ Destination Agent
                          ↑ connection scopes this ↑
```

| Method | Path | Description |
|---|---|---|
| `POST` | `/v2/connections` | Create a source→destination connection |
| `GET` | `/v2/connections` | List all connections (paginated) |
| `GET` | `/v2/connections/:id` | Get connection details |
| `POST` | `/v2/connections/:id/sync` | Extract + transfer a skill through the connection |
| `GET` | `/v2/connections/:id/history` | List all transfers through the connection |
| `DELETE` | `/v2/connections/:id` | Delete connection |

#### POST /v2/connections

```bash
curl -X POST /v2/connections \
  -H "Authorization: Bearer $KEY" \
  -d '{
    "name":               "Robot → Trader",
    "source_domain":      "robotics_sim",
    "destination_domain": "finance",
    "gap_threshold":      0.70,
    "allow_partial":      true,
    "auto_rollback":      false,
    "webhook_url":        "https://your-server.io/events"
  }'
```

#### POST /v2/connections/:id/sync

The primary action — runs the full pipeline:

```bash
curl -X POST /v2/connections/cn_3f8a1b2c/sync \
  -H "Authorization: Bearer $KEY" \
  -d '{
    "task":     "Detect anomalous order flow patterns",
    "episodes": 1000,
    "depth":    "standard",
    "dry_run":  false
  }'
```

Response:
```json
{
  "transfer_id":    "tr_9f8e7d6c",
  "connection_id":  "cn_3f8a1b2c",
  "skill_id":       "sk_a1b2c3d4",
  "compat_score":   0.812,
  "status":         "INJECTED",
  "sub_scores": {
    "PERCEPTION": 0.84, "COGNITION": 0.91, "ACTION": 0.72,
    "CONTROL": 0.79, "COMMUNICATION": 0.68, "LEARNING": 0.85
  },
  "gaps":        [],
  "adapter_log": [
    { "primitive_id": "sense_state", "source_impl": "sim.read_sensor()", "target_impl": "feed.subscribe()", "confidence": 0.91 }
  ],
  "rollback_token": "rb_4d9f01c2e8a3",
  "duration_ms":    23
}
```

---

### Skills

Individual skill lifecycle — extract, score, transfer, rollback, refine.

| Method | Path | Description |
|---|---|---|
| `POST` | `/v2/skills/extract` | Extract a skill (sync ≤2000 eps, async >2000) |
| `GET` | `/v2/skills` | List all skills (paginated, filterable) |
| `GET` | `/v2/skills/:id` | Get full SkillObject |
| `GET` | `/v2/skills/:id/graph` | Get full intent graph DAG |
| `POST` | `/v2/skills/:id/score` | Score against any domain (read-only) |
| `POST` | `/v2/skills/:id/transfer` | Transfer to destination domain |
| `POST` | `/v2/skills/:id/rollback` | Reverse last injection |
| `PUT` | `/v2/skills/:id/refine` | Improve with additional episodes |
| `POST` | `/v2/skills/validate` | Validate SkillObject schema |
| `POST` | `/v2/skills/batch` | Async batch extract + transfer |
| `DELETE` | `/v2/skills/:id` | Delete skill |

#### Skill Object schema

```json
{
  "skill_id":       "sk_3f8a1b2c",
  "name":           "Detect and classify anomalous signals",
  "version":        "2.0.0",
  "source_domain":  "robotics_sim",
  "extraction": {
    "episodes": 1000, "depth": "standard", "edge_cases": true
  },
  "primitives": [
    { "id": "sense_state", "weight": 0.923, "criticality": "HIGH", "criticality_weight": 1.0, "confidence": 0.974 }
  ],
  "intent_graph":   { "nodes": 14, "edges": 16, "depth": 5, "cycles": 0 },
  "edge_cases": [
    { "id": "ec_001", "trigger": "partial_occlusion", "resolution": "retry_with_different_angle", "probability": 0.08 }
  ],
  "feature_vector": { "temporal": 0.41, "spatial": 0.72, "cognitive": 0.68, "action": 0.79, "social": 0.15, "physical": 0.71 },
  "transferability":  0.847,
  "confidence_score": 0.913,
  "rollback_token":   "rb_3f8a1b2c9d0e",
  "created_at":       "2026-03-01T14:23:00Z"
}
```

#### Async extraction

For `episodes > 2000`, extraction returns `202 Accepted`:

```json
{ "job_id": "job_a1b2c3d4", "status": "queued", "poll_url": "/v2/jobs/job_a1b2c3d4", "estimated_ms": 18000 }
```

Poll `GET /v2/jobs/job_a1b2c3d4` until `status` is `complete`.

---

### Domains

| Method | Path | Description |
|---|---|---|
| `GET` | `/v2/domains` | List all domains (built-in + custom) |
| `POST` | `/v2/domains/register` | Register a custom domain |
| `GET` | `/v2/domains/compat` | Base BCM or skill-adjusted compatibility matrix |

#### Register a custom domain

```bash
curl -X POST /v2/domains/register \
  -H "Authorization: Bearer $KEY" \
  -d '{
    "id":   "drone_delivery",
    "name": "Autonomous Drone Delivery",
    "icon": "🚁",
    "feature_vector": {
      "temporal": 0.60, "spatial": 0.95, "cognitive": 0.55,
      "action": 0.88, "social": 0.20, "physical": 0.85
    },
    "primitive_impls": {
      "move_to_target": { "impl": "flight_controller.navigate()", "cost": "varies" },
      "estimate_pose":  { "impl": "gps.localize()", "cost": "50ms" }
    }
  }'
```

---

### Primitives

Read-only taxonomy browser.

| Method | Path | Description |
|---|---|---|
| `GET` | `/v2/primitives` | List all 48 primitives (filterable by category) |
| `GET` | `/v2/primitives/:id` | Get single primitive with all domain implementations |

---

### Jobs

| Method | Path | Description |
|---|---|---|
| `GET` | `/v2/jobs/:id` | Poll async job status and result |

---

## Authentication

All requests require `Authorization: Bearer <key>`.

| Key prefix | Scope | Notes |
|---|---|---|
| `usk_prod_` | Full read + write | Use in production. Store in env vars. |
| `usk_test_` | Sandbox only | Extractions are isolated. Safe for testing. |
| `usk_ro_` | Read-only | GET endpoints only. Cannot create or transfer. |

Generate a key:
```bash
python scripts/seed_api_key.py \
  --org-id "org_acme" \
  --name   "Production Key" \
  --plan   pro
```

---

## Rate Limits

| Plan | Requests/min | Extractions/day | Max Episodes | Connections | Batch Size |
|---|---|---|---|---|---|
| Free | 10 | 20 | 500 | 3 | 5 |
| Pro | 120 | 500 | 10,000 | 25 | 20 |
| Enterprise | 2,000 | Unlimited | 100,000 | Unlimited | 50 |

Rate limit headers on every response:
```
X-RateLimit-Limit:     120
X-RateLimit-Remaining: 118
X-RateLimit-Reset:     47
```

---

## Primitive Taxonomy

48 universal primitives across 6 categories (8 per category):

| Category | Primitives |
|---|---|
| **PERCEPTION** | `sense_state`, `detect_pattern`, `classify_object`, `measure_distance`, `track_change`, `read_signal`, `segment_scene`, `estimate_pose` |
| **COGNITION** | `evaluate_condition`, `rank_options`, `predict_outcome`, `detect_anomaly`, `infer_intent`, `remember_context`, `plan_sequence`, `resolve_conflict` |
| **ACTION** | `move_to_target`, `apply_force`, `execute_sequence`, `modify_state`, `emit_output`, `release_resource`, `sample_environment`, `queue_action` |
| **CONTROL** | `loop_until`, `branch_on_condition`, `retry_on_failure`, `throttle_rate`, `synchronize`, `abort_on_threshold`, `checkpoint`, `escalate` |
| **COMMUNICATION** | `send_message`, `request_input`, `broadcast_state`, `negotiate`, `acknowledge`, `subscribe`, `report_status`, `query_peer` |
| **LEARNING** | `update_belief`, `store_example`, `refine_model`, `generalize_pattern`, `forget_outdated`, `transfer_knowledge`, `evaluate_policy`, `explain_decision` |

Each primitive has a **6D feature vector** `{temporal, spatial, cognitive, action, social, physical}` and a concrete **implementation string** for all 8 built-in domains (= 384 total implementation strings).

---

## Domain Feature Vectors

8 built-in domains, each characterised by a 6D vector:

| Domain | temporal | spatial | cognitive | action | social | physical |
|---|---|---|---|---|---|---|
| robotics_sim | 0.30 | 0.90 | 0.50 | 0.90 | 0.10 | 0.95 |
| robotics_real | 0.40 | 0.88 | 0.52 | 0.88 | 0.12 | 0.92 |
| software_dev | 0.50 | 0.20 | 0.90 | 0.60 | 0.30 | 0.00 |
| education | 0.60 | 0.40 | 0.80 | 0.30 | 0.90 | 0.20 |
| medical | 0.70 | 0.60 | 0.90 | 0.50 | 0.70 | 0.60 |
| finance | 0.90 | 0.10 | 0.90 | 0.70 | 0.30 | 0.00 |
| logistics | 0.65 | 0.85 | 0.55 | 0.75 | 0.40 | 0.70 |
| game_ai | 0.55 | 0.80 | 0.70 | 0.85 | 0.50 | 0.60 |

---

## Scoring Algorithm

```python
# 1. For each primitive in the skill:
sim = cosine_similarity(primitive.feature_vector, target_domain.feature_vector)
weight = 1.0 if idx < 3 else 0.8 if idx < 6 else 0.6  # positional criticality

# 2. Weighted average
raw_score = Σ(sim × weight) / Σ(weight)

# 3. Blend with Base Compatibility Matrix (BCM)
final_score = raw_score × 0.60 + BCM[source][target] × 0.40

# 4. Gap detection
if sim < threshold:  # default 0.70
    severity = "HIGH" if sim < 0.50 else "MEDIUM" if sim < 0.65 else "LOW"
    remediation = {"HIGH": "BRIDGE", "MEDIUM": "SUBSTITUTE", "LOW": "BEST_EFFORT"}
```

**Deterministic**: given the same primitives and domains, the score is always identical. No randomness.

---

## Configuration

All configuration via environment variables. See `.env.example` for the full list.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async Postgres connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `APP_SECRET_KEY` | — | 32+ byte random secret (required in production) |
| `APP_ENV` | `development` | `development` \| `production` |
| `DEFAULT_GAP_THRESHOLD` | `0.70` | Default gap detection threshold |
| `ROLLBACK_TTL_HOURS` | `72` | Rollback token validity window |
| `ASYNC_THRESHOLD_EPISODES` | `2000` | Episode count above which extraction goes async |
| `WEBHOOK_SECRET` | — | HMAC-SHA256 signing secret for webhooks |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins or `*` |

---

## Development

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Make

### Setup

```bash
git clone https://github.com/your-org/uskill-api
cd uskill-api

# Install dependencies
make install

# Start Postgres + Redis
make docker-up

# Apply migrations
make migrate

# Create a dev API key
make seed

# Start the API
make dev

# In a second terminal, start the background worker
make worker
```

### Project layout

```
uskill-api/
├── app/           Application code
├── alembic/       Database migrations
├── tests/         Test suite (121 tests)
├── scripts/       Developer utilities
├── .github/       CI/CD workflows
├── Dockerfile     Multi-stage production image
├── docker-compose.yml
├── Makefile
└── README.md
```

---

## Testing

Tests use **SQLite in-memory** — no Postgres or Redis required.

```bash
# Full suite with coverage
make test

# Fast (no coverage)
make test-fast

# Unit tests only (scorer, adapter, extractor)
make test-unit

# Integration tests only (API endpoints)
make test-integration
```

### Test coverage

| File | Tests | What it covers |
|---|---|---|
| `test_scorer.py` | 20 | Cosine similarity, scoring engine, gap severity |
| `test_adapter.py` | 8 | Primitive→impl lookup, custom domain override |
| `test_extractor.py` | 22 | Extraction, determinism, CSPRNG IDs, feature vectors |
| `test_connections_api.py` | 15 | Full connection CRUD + sync endpoint |
| `test_skills_api.py` | 28 | All 11 skill endpoints |
| `test_domains_api.py` | 12 | Domain list, register, compat matrix |
| `test_health_and_primitives.py` | 13 | Health, primitives, jobs, headers |
| **Total** | **118** | |

---

## Deployment

### Docker Compose (recommended for self-hosting)

```bash
cp .env.example .env
# Edit .env with your DATABASE_URL, REDIS_URL, APP_SECRET_KEY, WEBHOOK_SECRET

docker compose up --build
```

Services started:
- `api` — USKill API on port 8000
- `postgres` — PostgreSQL 16 + pgvector
- `redis` — Redis 7

Optional dev tools (add `--profile dev`):
- `pgadmin` — pgAdmin 4 on port 5050
- `redisinsight` — Redis Insight on port 5540

### Production hardening checklist

- [ ] Set `APP_ENV=production` (disables `/docs`, `/redoc`, `/openapi.json`)
- [ ] Set `APP_SECRET_KEY` to 32+ random bytes
- [ ] Set `WEBHOOK_SECRET` to 32+ random bytes
- [ ] Set `CORS_ORIGINS` to your actual frontend origins (not `*`)
- [ ] Terminate TLS at the load balancer / reverse proxy
- [ ] Run behind Nginx or a cloud load balancer
- [ ] Set up log aggregation (the API emits structured JSON)
- [ ] Configure Prometheus scraping at `/metrics`
- [ ] Create API keys with minimum required scopes
- [ ] Schedule `alembic upgrade head` before every deploy

### Worker process

For async jobs (large extractions, batch transfers) to execute, the worker must be running alongside the API:

```bash
# Production (two processes)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
python -m app.worker
```

Or add a worker service to your `docker-compose.yml`:

```yaml
worker:
  build: .
  command: python -m app.worker
  env_file: .env
  environment:
    DATABASE_URL: postgresql+asyncpg://uskill:uskill@postgres:5432/uskill
    REDIS_URL: redis://redis:6379/0
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
```

---

## Webhook Verification

All webhook deliveries are signed. Verify with HMAC-SHA256:

```python
import hashlib, hmac

def verify(payload: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)

# In your webhook handler:
sig = request.headers["X-USKill-Signature"]
if not verify(request.body, sig, WEBHOOK_SECRET):
    return 401
```

---

## License

MIT — see `LICENSE`.
