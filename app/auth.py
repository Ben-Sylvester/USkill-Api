"""
Authentication — API key validation and org/plan resolution.

Key format:  usk_prod_<32 hex chars>
             usk_test_<32 hex chars>
             usk_ro_<32 hex chars>

The prefix encodes the key type; the full key is stored as a bcrypt hash.
The first 12 characters (prefix + short segment) are stored in plain text
for fast pre-filtering; the bcrypt check is done against the full key.
"""

import secrets
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.api_key import ApiKey

settings = get_settings()

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
_api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

READ_ONLY_PREFIX = "usk_ro_"
TEST_PREFIX = "usk_test_"
PROD_PREFIX = "usk_prod_"


class AuthContext:
    __slots__ = ("org_id", "plan", "key_id", "scopes", "is_read_only", "is_test")

    def __init__(
        self,
        org_id: str,
        plan: str,
        key_id: str,
        scopes: list[str],
        is_read_only: bool,
        is_test: bool,
    ):
        self.org_id = org_id
        self.plan = plan
        self.key_id = key_id
        self.scopes = scopes
        self.is_read_only = is_read_only
        self.is_test = is_test


def _extract_raw_key(authorization: str | None) -> str | None:
    """Strip 'Bearer ' prefix."""
    if not authorization:
        return None
    if authorization.startswith("Bearer "):
        return authorization[7:].strip()
    return None


def _get_prefix(raw_key: str) -> str | None:
    for prefix in (PROD_PREFIX, TEST_PREFIX, READ_ONLY_PREFIX):
        if raw_key.startswith(prefix):
            return prefix
    return None


async def get_auth(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    raw_key = _extract_raw_key(authorization)

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "UNAUTHORIZED",
                "message": "Missing Authorization header. Format: Bearer usk_prod_<key>",
            },
        )

    prefix = _get_prefix(raw_key)
    if not prefix:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "UNAUTHORIZED",
                "message": "Invalid API key format. Expected usk_prod_, usk_test_, or usk_ro_ prefix.",
            },
        )

    # Use first 12 chars for fast DB pre-filter
    key_prefix_stored = raw_key[:12]

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == key_prefix_stored,
            ApiKey.is_active == True,  # noqa: E712
        )
    )
    candidates = result.scalars().all()

    matched: ApiKey | None = None
    for candidate in candidates:
        if _pwd_ctx.verify(raw_key, candidate.key_hash):
            matched = candidate
            break

    if matched is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHORIZED", "message": "Invalid or revoked API key."},
        )

    # Check expiry
    if matched.expires_at and matched.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHORIZED", "message": "API key has expired."},
        )

    # Update last_used_at asynchronously (fire and forget style — don't fail request)
    try:
        await db.execute(
            update(ApiKey)
            .where(ApiKey.id == matched.id)
            .values(last_used_at=datetime.now(timezone.utc))
        )
    except Exception:
        pass

    scopes = matched.scopes.split() if matched.scopes else ["read"]

    return AuthContext(
        org_id=matched.org_id,
        plan=matched.plan,
        key_id=matched.id,
        scopes=scopes,
        is_read_only=raw_key.startswith(READ_ONLY_PREFIX),
        is_test=raw_key.startswith(TEST_PREFIX),
    )


def require_write(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    if auth.is_read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "FORBIDDEN",
                "message": "Read-only API key cannot perform write operations.",
            },
        )
    return auth


# ── Seed helper (used by migrations / test setup) ───────────────────
def generate_api_key(prefix: str = "usk_prod_") -> tuple[str, str]:
    """
    Returns (raw_key, hash).
    raw_key is shown to the user once; hash is stored in DB.
    """
    raw = prefix + secrets.token_hex(16)
    hashed = _pwd_ctx.hash(raw)
    return raw, hashed
