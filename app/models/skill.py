"""SQLAlchemy ORM model for Skill objects."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # sk_[8hex]
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    connection_id: Mapped[str | None] = mapped_column(
        String(20),
        ForeignKey("connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="2.0.0")
    source_domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Extraction parameters
    extraction_episodes: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    extraction_depth: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")
    extraction_edge_cases: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Skill body (JSON columns)
    primitives: Mapped[list] = mapped_column(JSON, nullable=False)
    intent_graph: Mapped[dict] = mapped_column(JSON, nullable=False)
    edge_cases: Mapped[list] = mapped_column(JSON, nullable=False)
    feature_vector: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Scoring
    transferability: Mapped[float] = mapped_column(Float, nullable=False, default=0.75)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.85)

    # Rollback
    rollback_token: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    rollback_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rollback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Lineage (refine chain)
    previous_skill_id: Mapped[str | None] = mapped_column(
        String(20),
        ForeignKey("skills.id", ondelete="SET NULL"),
        nullable=True,
    )
    refine_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    connection: Mapped["Connection"] = relationship(  # noqa: F821
        "Connection", back_populates="skills", lazy="select", foreign_keys=[connection_id]
    )
    transfers: Mapped[list["Transfer"]] = relationship(  # noqa: F821
        "Transfer", back_populates="skill", lazy="dynamic"
    )
    previous_skill: Mapped["Skill | None"] = relationship(
        "Skill", remote_side="Skill.id", foreign_keys=[previous_skill_id], lazy="select"
    )
