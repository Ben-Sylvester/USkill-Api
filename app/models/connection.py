import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # cn_[8hex]
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_domain: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_domain: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active | paused | archived
    gap_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.70)
    allow_partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_rollback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True
    )
    transfer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_compat_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # relationships
    skills: Mapped[list["Skill"]] = relationship(  # noqa: F821
        "Skill", back_populates="connection", lazy="dynamic"
    )
    transfers: Mapped[list["Transfer"]] = relationship(  # noqa: F821
        "Transfer", back_populates="connection", lazy="dynamic"
    )
