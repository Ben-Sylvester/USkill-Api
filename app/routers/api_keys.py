"""
API Key management router.

Endpoints (all require a valid non-read-only key):

  POST /v2/keys/rotate     — atomically create a replacement key and revoke the current one
  GET  /v2/keys            — list all active keys for the org (metadata only, no hashes)
  DELETE /v2/keys/:key_id  — revoke a specific key
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthContext, generate_api_key, require_write
from app.database import get_db
from app.models.api_key import ApiKey

router = APIRouter(prefix="/keys", tags=["API Keys"])


class KeyListItem(BaseModel):
    key_id: str
    name: str
    plan: str
    scopes: str
    key_prefix: str   # first 12 chars — enough to identify without exposing the full key
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None


class RotateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200, default="Rotated key")
    prefix: str = Field(
        default="usk_prod_",
        pattern="^(usk_prod_|usk_test_|usk_ro_)$",
    )


class RotateResponse(BaseModel):
    new_key_id: str
    raw_key: str       # shown ONCE — caller must store immediately
    revoked_key_id: str
    plan: str
    created_at: datetime
    request_id: str | None = None


# ── GET /v2/keys ───────────────────────────────────────────────────────
@router.get("", response_model=list[KeyListItem])
async def list_keys(
    request: Request,
    auth: AuthContext = Depends(require_write),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.org_id == auth.org_id, ApiKey.is_active == True)  # noqa: E712
        .order_by(ApiKey.created_at.desc())
    )
    return [
        KeyListItem(
            key_id=k.id,
            name=k.name,
            plan=k.plan,
            scopes=k.scopes,
            key_prefix=k.key_prefix,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            expires_at=k.expires_at,
        )
        for k in result.scalars()
    ]


# ── POST /v2/keys/rotate ───────────────────────────────────────────────
@router.post("/rotate", response_model=RotateResponse, status_code=201)
async def rotate_key(
    body: RotateRequest,
    request: Request,
    auth: AuthContext = Depends(require_write),
    db: AsyncSession = Depends(get_db),
):
    """
    Atomically create a new API key and revoke the calling key.
    The new raw key is returned ONCE — it cannot be recovered later.
    The revoked key stops working immediately.
    """
    rid = request.state.request_id
    import secrets as _secrets
    from passlib.context import CryptContext
    _pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

    raw_key, key_hash = generate_api_key(body.prefix)
    new_id = "key_" + _secrets.token_hex(5)
    now = datetime.now(timezone.utc)

    # Fetch the current key to copy its plan
    current = await db.execute(
        select(ApiKey).where(ApiKey.id == auth.key_id)
    )
    current_key = current.scalar_one_or_none()
    if current_key is None:
        raise HTTPException(
            404,
            {"error": "KEY_NOT_FOUND", "message": "Calling key not found.", "request_id": rid},
        )

    # Create the new key (same plan + org)
    new_key = ApiKey(
        id=new_id,
        org_id=auth.org_id,
        name=body.name,
        key_hash=key_hash,
        key_prefix=raw_key[:12],
        plan=current_key.plan,
        is_active=True,
        scopes=current_key.scopes,
        created_at=now,
    )
    db.add(new_key)

    # Revoke the calling key atomically in the same transaction
    current_key.is_active = False

    await db.flush()

    return RotateResponse(
        new_key_id=new_id,
        raw_key=raw_key,
        revoked_key_id=auth.key_id,
        plan=current_key.plan,
        created_at=now,
        request_id=rid,
    )


# ── DELETE /v2/keys/:key_id ────────────────────────────────────────────
@router.delete("/{key_id}", status_code=204)
async def revoke_key(
    key_id: str,
    request: Request,
    auth: AuthContext = Depends(require_write),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a specific key by id. Cannot revoke the calling key itself."""
    rid = request.state.request_id

    if key_id == auth.key_id:
        raise HTTPException(
            409,
            {
                "error": "CANNOT_REVOKE_SELF",
                "message": "Cannot revoke the key you are currently using. Use /rotate instead.",
                "request_id": rid,
            },
        )

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.org_id == auth.org_id,
            ApiKey.is_active == True,  # noqa: E712
        )
    )
    key = result.scalar_one_or_none()
    if key is None:
        raise HTTPException(
            404,
            {"error": "KEY_NOT_FOUND", "message": f"No active key with id {key_id}.", "request_id": rid},
        )

    key.is_active = False
    await db.flush()
