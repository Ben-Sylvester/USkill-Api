from typing import Any, Generic, TypeVar
from datetime import datetime

from pydantic import BaseModel, Field

T = TypeVar("T")

PLAN_VALUES = ["free", "pro", "enterprise"]
STATUS_INJECTED = "INJECTED"
STATUS_PARTIAL = "PARTIAL"
STATUS_REJECTED = "REJECTED"
STATUS_DRY_RUN = "DRY_RUN"
STATUS_ROLLED_BACK = "ROLLED_BACK"
TRANSFER_STATUSES = [STATUS_INJECTED, STATUS_PARTIAL, STATUS_REJECTED, STATUS_DRY_RUN, STATUS_ROLLED_BACK]


class ErrorDetail(BaseModel):
    error: str
    message: str
    field: str | None = None
    request_id: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    next_cursor: str | None = None


class FeatureVectorSchema(BaseModel):
    temporal: float = Field(ge=0.0, le=1.0)
    spatial: float = Field(ge=0.0, le=1.0)
    cognitive: float = Field(ge=0.0, le=1.0)
    action: float = Field(ge=0.0, le=1.0)
    social: float = Field(ge=0.0, le=1.0)
    physical: float = Field(ge=0.0, le=1.0)

    def to_dict(self) -> dict[str, float]:
        return self.model_dump()


class SubScoresSchema(BaseModel):
    PERCEPTION: float = Field(ge=0.0, le=1.0, default=0.0)
    COGNITION: float = Field(ge=0.0, le=1.0, default=0.0)
    ACTION: float = Field(ge=0.0, le=1.0, default=0.0)
    CONTROL: float = Field(ge=0.0, le=1.0, default=0.0)
    COMMUNICATION: float = Field(ge=0.0, le=1.0, default=0.0)
    LEARNING: float = Field(ge=0.0, le=1.0, default=0.0)


class GapReportSchema(BaseModel):
    primitive_id: str
    source_impl: str | None
    target_impl: str | None
    similarity: float
    severity: str  # HIGH | MEDIUM | LOW
    criticality: str  # HIGH | MEDIUM | LOW
    remediation: str  # BRIDGE | SUBSTITUTE | BEST_EFFORT | DROP


class AdapterEntrySchema(BaseModel):
    primitive_id: str
    source_impl: str | None
    target_impl: str | None
    confidence: float
    cost: str | None
    gap_severity: str | None = None
