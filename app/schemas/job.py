from datetime import datetime

from pydantic import BaseModel


class JobProgress(BaseModel):
    step: int
    total: int
    step_name: str | None = None


class JobResponse(BaseModel):
    job_id: str
    type: str
    status: str
    progress: JobProgress | None = None
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    request_id: str | None = None
