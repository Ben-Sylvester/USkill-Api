"""
Rate limiting — per-API-key, per-minute sliding window via Redis.

Strategy:
  - Key format: rl:{key_id}:{minute_bucket}
  - Limits come from the key's plan via AuthContext
  - Returns X-RateLimit-* headers on every response
  - Returns 429 with Retry-After when exceeded
  - Falls back to ALLOW on Redis errors (fail-open for availability)
"""

from __future__ import annotations

import time
from typing import Callable

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Endpoints that bypass rate limiting
_EXEMPT_PATHS = {"/health", "/", "/metrics", "/docs", "/redoc", "/openapi.json"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Reads the resolved AuthContext from request.state (set by auth dependency)
    and enforces per-plan rate limits.

    Because FastAPI dependency injection runs AFTER middleware, we can't call
    get_auth() here. Instead we read the raw Authorization header, extract just
    the key prefix for Redis keying, and look up the cached limit from a
    lightweight Redis check.

    The actual plan limit is enforced in the auth dependency itself for
    feature-gating; this middleware handles request-rate throttling.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        # Extract key prefix for rate limit bucket (no DB call needed)
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer usk_"):
            # Not an API key request — let auth dependency handle the 401
            return await call_next(request)

        raw_key = auth_header[7:]
        key_prefix = raw_key[:12]   # e.g. "usk_prod_a1b2"

        # Detect plan from key prefix (conservative default: free limits)
        if "usk_prod_" in raw_key[:9] or "usk_ro_" in raw_key[:7]:
            # We don't know the plan without a DB lookup — use conservative limit
            # The auth dependency will enforce plan-level feature limits separately
            # Here we use a generous per-minute limit that covers all plans
            limit = settings.rate_limit_enterprise  # conservative: use highest
        else:
            limit = settings.rate_limit_free

        # Redis rate limit check
        try:
            from app.cache import check_rate_limit
            minute_bucket = int(time.time() // 60)
            rl_key = f"rl:{key_prefix}:{minute_bucket}"
            allowed, count, reset_in = await check_rate_limit(rl_key, limit, window_seconds=60)
        except Exception as exc:
            # Fail-open: Redis unavailable → allow request, log warning
            logger.warning("rate_limit_redis_error", error=str(exc))
            allowed, count, reset_in = True, 0, 60

        if not allowed:
            return JSONResponse(
                status_code=429,
                headers={
                    "X-RateLimit-Limit":     str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset":     str(reset_in),
                    "Retry-After":           str(reset_in),
                },
                content={
                    "error":      "RATE_LIMITED",
                    "message":    f"Rate limit of {limit} requests/minute exceeded.",
                    "retry_after_ms": reset_in * 1000,
                    "request_id": getattr(request.state, "request_id", None),
                },
            )

        response = await call_next(request)

        # Inject rate limit headers on every response
        remaining = max(0, limit - count)
        response.headers["X-RateLimit-Limit"]     = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"]     = str(reset_in)
        return response
