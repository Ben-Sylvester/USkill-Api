from datetime import datetime

from pydantic import BaseModel, Field


class ConnectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_domain: str = Field(min_length=1, max_length=64)
    destination_domain: str = Field(min_length=1, max_length=64)
    gap_threshold: float = Field(default=0.70, ge=0.10, le=0.95)
    allow_partial: bool = True
    auto_rollback: bool = False
    webhook_url: str | None = None
    metadata: dict | None = None

    @classmethod
    def validate_domains_differ(cls, v, values):
        if "source_domain" in values and v == values["source_domain"]:
            raise ValueError("destination_domain must differ from source_domain")
        return v


class ConnectionResponse(BaseModel):
    connection_id: str
    name: str
    source_domain: str
    destination_domain: str
    status: str
    gap_threshold: float
    allow_partial: bool
    auto_rollback: bool
    webhook_url: str | None
    transfer_count: int
    avg_compat_score: float | None
    created_at: datetime
    request_id: str | None = None


class ConnectionListItem(BaseModel):
    connection_id: str
    name: str
    source_domain: str
    destination_domain: str
    status: str
    transfer_count: int
    avg_compat_score: float | None
    created_at: datetime


class ConnectionSyncRequest(BaseModel):
    task: str = Field(min_length=10, max_length=2000)
    episodes: int = Field(default=1000, ge=100)
    depth: str = Field(default="standard", pattern="^(shallow|standard|deep)$")
    edge_cases: bool = True
    dry_run: bool = False
    override_threshold: float | None = Field(default=None, ge=0.10, le=0.95)


# ── Status transition ───────────────────────────────────────────────
class ConnectionStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|paused|archived)$")
    reason: str | None = Field(default=None, max_length=500)


# ── Transfer history item (typed) ──────────────────────────────────
class TransferHistoryItem(BaseModel):
    transfer_id: str
    skill_id: str
    compat_score: float
    status: str
    created_at: str   # ISO 8601 — serialised from datetime
