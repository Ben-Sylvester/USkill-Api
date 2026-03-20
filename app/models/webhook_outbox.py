"""
Webhook Outbox — durable delivery table.

Instead of fire-and-forget asyncio.create_task() (which is lost if the
process dies), every outgoing webhook is first written to this table.
The background worker then delivers it with exponential retry, and marks
the row as 'delivered' or 'failed' (after max_attempts exceeded).

This implements the Transactional Outbox Pattern:
  1. Router writes webhook row inside the same DB transaction as the
     business record (atomic — either both persist or neither does).
  2. Worker polls pending rows, delivers, updates status.
  3. No message is ever silently dropped.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WebhookOutbox(Base):
    __tablename__ = "webhook_outbox"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)   # wb_[hex]
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Delivery target
    url: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Delivery state
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )  # pending | delivering | delivered | failed

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # When the outbox row expires and can be cleaned up (GC)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
