from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import (
    AdapterEntrySchema, FeatureVectorSchema, GapReportSchema, SubScoresSchema
)


# ── Primitive ────────────────────────────────────────────────────────
class PrimitiveSchema(BaseModel):
    id: str
    weight: float = Field(ge=0.0, le=1.0)
    criticality: str
    criticality_weight: float
    confidence: float = Field(ge=0.0, le=1.0)


# ── EdgeCase ─────────────────────────────────────────────────────────
class EdgeCaseSchema(BaseModel):
    id: str
    trigger: str
    resolution: str
    probability: float = Field(ge=0.001, le=0.50)


# ── Intent Graph ─────────────────────────────────────────────────────
class IntentGraphMetaSchema(BaseModel):
    nodes: int
    edges: int
    depth: int
    cycles: int = 0


# ── SkillObject ──────────────────────────────────────────────────────
class SkillObjectSchema(BaseModel):
    skill_id: str
    name: str
    version: str
    source_domain: str
    extraction: dict
    primitives: list[PrimitiveSchema]
    intent_graph: IntentGraphMetaSchema
    edge_cases: list[EdgeCaseSchema]
    feature_vector: FeatureVectorSchema
    transferability: float
    confidence_score: float
    rollback_token: str | None
    connection_id: str | None
    created_at: datetime
    request_id: str | None = None


class SkillListItemSchema(BaseModel):
    skill_id: str
    name: str
    source_domain: str
    transferability: float
    confidence_score: float
    connection_id: str | None
    created_at: datetime


# ── Extract ──────────────────────────────────────────────────────────
class ExtractRequest(BaseModel):
    task: str = Field(min_length=10, max_length=2000)
    source_domain: str = Field(min_length=1, max_length=64)
    connection_id: str | None = None
    episodes: int = Field(default=1000, ge=100)
    depth: str = Field(default="standard", pattern="^(shallow|standard|deep)$")
    edge_cases: bool = True
    rollback: bool = True
    webhook_url: str | None = None


# ── Score ────────────────────────────────────────────────────────────
class ScoreRequest(BaseModel):
    target_domain: str
    threshold: float = Field(default=0.70, ge=0.10, le=0.95)
    blend_base: bool = True
    include_matrix: bool = True


class ScoreResponse(BaseModel):
    skill_id: str
    target_domain: str
    score: float
    sub_scores: SubScoresSchema
    gaps: list[GapReportSchema]
    matrix_row: dict[str, float] | None = None
    request_id: str | None = None


# ── Transfer ─────────────────────────────────────────────────────────
class TransferRequest(BaseModel):
    destination_domain: str | None = None
    connection_id: str | None = None
    gap_threshold: float = Field(default=0.70, ge=0.10, le=0.95)
    allow_partial: bool = True
    dry_run: bool = False


class TransferResultSchema(BaseModel):
    transfer_id: str
    connection_id: str | None
    skill_id: str
    source_domain: str
    destination_domain: str
    compat_score: float
    status: str
    sub_scores: SubScoresSchema
    gaps: list[GapReportSchema]
    adapter_log: list[AdapterEntrySchema]
    rollback_token: str | None
    duration_ms: int | None
    request_id: str | None = None


# ── Rollback ─────────────────────────────────────────────────────────
class RollbackRequest(BaseModel):
    rollback_token: str
    connection_id: str | None = None


class RollbackResponse(BaseModel):
    skill_id: str
    status: str
    message: str
    request_id: str | None = None


# ── Refine ───────────────────────────────────────────────────────────
class RefineRequest(BaseModel):
    additional_episodes: int = Field(ge=100)
    merge_strategy: str = Field(
        default="weighted_avg",
        pattern="^(weighted_avg|replace|additive)$"
    )
    bump_version: bool = True
    connection_id: str | None = None


class RefineResponse(BaseModel):
    new_skill_id: str
    previous_skill_id: str
    version: str
    delta: dict
    request_id: str | None = None


# ── Validate ─────────────────────────────────────────────────────────
class ValidateRequest(BaseModel):
    skill: dict


class ValidateResponse(BaseModel):
    valid: bool
    schema_version: str = "uskill-object/v2"
    errors: list[dict] = []
    warnings: list[str] = []
    request_id: str | None = None


# ── Batch ────────────────────────────────────────────────────────────
class BatchJobItem(BaseModel):
    task: str = Field(min_length=10, max_length=2000)
    source_domain: str
    target_domain: str
    episodes: int = Field(default=1000, ge=100)
    depth: str = Field(default="standard", pattern="^(shallow|standard|deep)$")


class BatchRequest(BaseModel):
    jobs: list[BatchJobItem] = Field(min_length=1)
    connection_id: str | None = None
    webhook_url: str | None = None
    priority: str = Field(default="normal", pattern="^(normal|high)$")


class BatchJobResponse(BaseModel):
    batch_id: str
    job_count: int
    status: str
    poll_url: str
    estimated_ms: int
    request_id: str | None = None
