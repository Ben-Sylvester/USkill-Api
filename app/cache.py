"""
Redis client — single async connection pool shared across the app.

Used for:
  - Rate limiting (via slowapi + Redis backend)
  - Job queue (simple list-based queue for async extractions)
  - Short-lived caches (domain FV lookups, BCM lookups — microsecond wins)
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings

settings = get_settings()

# ── Singleton pool ────────────────────────────────────────────────────
_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Return the shared async Redis client (lazy init)."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


# ── Rate limiting helpers ─────────────────────────────────────────────
async def check_rate_limit(
    key: str,
    limit: int,
    window_seconds: int = 60,
) -> tuple[bool, int, int]:
    """
    Sliding-window rate limiter using Redis INCR + EXPIRE.

    Returns:
        (allowed, current_count, reset_in_seconds)
    """
    r = get_redis()
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.ttl(key)
    results = await pipe.execute()

    count: int = results[0]
    ttl: int   = results[1]

    if count == 1 or ttl == -1:
        # First request in window — set expiry
        await r.expire(key, window_seconds)
        ttl = window_seconds

    allowed = count <= limit
    return allowed, count, ttl


# ── Job queue helpers ─────────────────────────────────────────────────
JOB_QUEUE_KEY   = "uskill:jobs:pending"
JOB_RESULT_TTL  = 60 * 60 * 24 * 7  # 7 days in seconds


async def enqueue_job(job_id: str, payload: dict) -> None:
    """Push a job onto the pending queue."""
    r = get_redis()
    data = json.dumps({"job_id": job_id, "payload": payload})
    await r.lpush(JOB_QUEUE_KEY, data)


async def dequeue_job(timeout: int = 5) -> tuple[str, dict] | None:
    """
    Block-pop a job from the queue. Returns (job_id, payload) or None on timeout.
    Used by the worker process.
    """
    r = get_redis()
    result = await r.brpop(JOB_QUEUE_KEY, timeout=timeout)
    if result is None:
        return None
    _, raw = result
    data = json.loads(raw)
    return data["job_id"], data["payload"]


async def set_job_result(job_id: str, result: dict) -> None:
    r = get_redis()
    await r.setex(f"uskill:jobs:result:{job_id}", JOB_RESULT_TTL, json.dumps(result))


async def get_job_result(job_id: str) -> dict | None:
    r = get_redis()
    raw = await r.get(f"uskill:jobs:result:{job_id}")
    return json.loads(raw) if raw else None


# ── Domain FV cache (optional hot-path optimization) ─────────────────
DOMAIN_FV_TTL = 300  # 5 minutes


async def cache_domain_fv(domain_id: str, org_id: str, fv: dict) -> None:
    r = get_redis()
    key = f"uskill:fv:{org_id}:{domain_id}"
    await r.setex(key, DOMAIN_FV_TTL, json.dumps(fv))


async def get_cached_domain_fv(domain_id: str, org_id: str) -> dict | None:
    r = get_redis()
    raw = await r.get(f"uskill:fv:{org_id}:{domain_id}")
    return json.loads(raw) if raw else None
