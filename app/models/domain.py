"""SQLAlchemy ORM model for org-registered custom domains."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CustomDomain(Base):
    __tablename__ = "custom_domains"

    # id is org-scoped, e.g. "drone_delivery" — unique per org
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    icon: Mapped[str] = mapped_column(String(10), nullable=False, default="⬡")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 6D feature vector: {temporal, spatial, cognitive, action, social, physical}
    feature_vector: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Primitive → {impl, cost} override map for this domain
    # e.g. {"sense_state": {"impl": "LiDAR sweep", "cost": "low"}}
    primitive_impls: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
