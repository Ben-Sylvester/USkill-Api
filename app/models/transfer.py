"""SQLAlchemy ORM model for Transfer records.

Every skill transfer (sync, inject, dry-run) produces one Transfer row
that captures the full scoring snapshot, adapter log, and status.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey,
    Integer, JSON, String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # tr_[8hex]
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    connection_id: Mapped[str | None] = mapped_column(
        String(20),
        ForeignKey("connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    skill_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Domain pair at transfer time (denormalised for fast history queries)
    source_domain: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_domain: Mapped[str] = mapped_column(String(64), nullable=False)

    # Scoring snapshot
    compat_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # INJECTED | PARTIAL | REJECTED | DRY_RUN | ROLLED_BACK

    # Detailed scoring data (JSON)
    sub_scores: Mapped[dict] = mapped_column(JSON, nullable=False)
    gaps: Mapped[list] = mapped_column(JSON, nullable=False)
    adapter_log: Mapped[list] = mapped_column(JSON, nullable=False)

    # Rollback envelope (copied from skill at transfer time)
    rollback_token: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rollback_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Telemetry
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # Relationships
    connection: Mapped["Connection | None"] = relationship(  # noqa: F821
        "Connection", back_populates="transfers", lazy="select"
    )
    skill: Mapped["Skill"] = relationship(  # noqa: F821
        "Skill", back_populates="transfers", lazy="select"
    )
