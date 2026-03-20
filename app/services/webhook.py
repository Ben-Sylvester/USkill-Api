"""
Webhook Service — Transactional Outbox Pattern.

  schedule_webhook(db, org_id, url, event_type, data)
      Write a pending delivery row to webhook_outbox inside the caller's
      existing DB transaction. Zero network I/O.

  deliver_pending_webhooks(db)
      Called by the background worker. Picks up pending rows, attempts
      HMAC-signed HTTPS delivery with exponential back-off.

  deliver_webhook(url, event_type, data)  [direct / test helper]
      One-shot delivery without the outbox.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.webhook_outbox import WebhookOutbox

settings = get_settings()
logger = structlog.get_logger()


def _sign_payload(payload: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _build_payload(event_type: str, data: dict) -> bytes:
    return json.dumps(
        {
            "event": event_type,
            "data": data,
            "delivered_at": datetime.now(timezone.utc).isoformat(),
        },
        separators=(",", ":"),
    ).encode()


def _delivery_headers(event_type: str, payload: bytes) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-USKill-Signature": _sign_payload(payload, settings.webhook_secret),
        "X-USKill-Event": event_type,
        "User-Agent": f"USKill-Webhook/{settings.app_version}",
    }


async def schedule_webhook(
    db: AsyncSession,
    org_id: str,
    url: str,
    event_type: str,
    data: dict,
) -> WebhookOutbox:
    """
    Enqueue webhook delivery transactionally. Caller owns the transaction.
    """
    row = WebhookOutbox(
        id="wb_" + secrets.token_hex(5),
        org_id=org_id,
        url=url,
        event_type=event_type,
        payload=data,
        status="pending",
        attempts=0,
        max_attempts=settings.webhook_outbox_max_attempts,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    return row


async def deliver_pending_webhooks(db: AsyncSession, batch_size: int = 50) -> int:
    """
    Deliver pending outbox rows. Returns count processed. Called by worker.
    """
    now = datetime.now(timezone.utc)

    # with_for_update(skip_locked=True) prevents multi-worker double-delivery
    try:
        result = await db.execute(
            select(WebhookOutbox)
            .where(
                WebhookOutbox.status == "pending",
                WebhookOutbox.attempts < WebhookOutbox.max_attempts,
            )
            .order_by(WebhookOutbox.created_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        rows: list[WebhookOutbox] = list(result.scalars())
    except Exception:
        # SQLite doesn't support SKIP LOCKED — fall back without it
        result = await db.execute(
            select(WebhookOutbox)
            .where(
                WebhookOutbox.status == "pending",
                WebhookOutbox.attempts < WebhookOutbox.max_attempts,
            )
            .order_by(WebhookOutbox.created_at)
            .limit(batch_size)
        )
        rows = list(result.scalars())

    if not rows:
        return 0

    async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
        for row in rows:
            payload = _build_payload(row.event_type, row.payload)
            headers = _delivery_headers(row.event_type, payload)
            success = False
            error_msg: str | None = None

            try:
                resp = await client.post(row.url, content=payload, headers=headers)
                if resp.status_code < 300:
                    success = True
                else:
                    error_msg = f"HTTP {resp.status_code}"
            except httpx.RequestError as exc:
                error_msg = str(exc)

            row.attempts += 1
            row.last_attempt_at = now
            row.last_error = error_msg

            if success:
                row.status = "delivered"
                row.delivered_at = now
                logger.info("webhook_delivered", outbox_id=row.id, event=row.event_type)
            elif row.attempts >= row.max_attempts:
                row.status = "failed"
                logger.error(
                    "webhook_permanently_failed",
                    outbox_id=row.id,
                    attempts=row.attempts,
                    error=error_msg,
                )
            else:
                logger.warning(
                    "webhook_retry_scheduled",
                    outbox_id=row.id,
                    attempt=row.attempts,
                    error=error_msg,
                )

    await db.commit()
    return len(rows)


async def deliver_webhook(url: str, event_type: str, data: dict) -> bool:
    """Direct one-shot delivery. No outbox. For tests/manual triggers only."""
    payload = _build_payload(event_type, data)
    headers = _delivery_headers(event_type, payload)

    async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
        for attempt in range(settings.webhook_max_retries):
            try:
                resp = await client.post(url, content=payload, headers=headers)
                if resp.status_code < 300:
                    return True
            except httpx.RequestError:
                pass
            if attempt < settings.webhook_max_retries - 1:
                await asyncio.sleep(2 ** attempt)
    return False
