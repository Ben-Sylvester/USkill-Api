from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import FeatureVectorSchema


class DomainImplEntry(BaseModel):
    impl: str
    cost: str = "unknown"


class DomainRegisterRequest(BaseModel):
    id: str = Field(
        min_length=3,
        max_length=32,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Lowercase, underscores only. e.g. drone_delivery",
    )
    name: str = Field(min_length=1, max_length=200)
    icon: str = Field(default="⬡", max_length=10)
    description: str | None = Field(default=None, max_length=500)
    feature_vector: FeatureVectorSchema
    primitive_impls: dict[str, DomainImplEntry] = Field(default_factory=dict)


class DomainResponse(BaseModel):
    id: str
    name: str
    icon: str
    built_in: bool
    description: str | None
    primitive_count: int
    feature_vector: FeatureVectorSchema
    created_at: datetime | None = None
    request_id: str | None = None


class CompatMatrixResponse(BaseModel):
    type: str  # "base" | "skill_adjusted"
    skill_id: str | None = None
    matrix: dict[str, dict[str, float]]
    request_id: str | None = None
