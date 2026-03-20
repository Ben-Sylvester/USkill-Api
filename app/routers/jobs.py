from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthContext, get_auth
from app.cache import get_job_result
from app.database import get_db
from app.models.job import Job
from app.schemas.job import JobProgress, JobResponse

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    request: Request,
    auth: AuthContext = Depends(get_auth),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id

    # Fast path: check Redis cache first (worker writes results here)
    try:
        cached = await get_job_result(job_id)
    except Exception:
        cached = None
    if cached and cached.get("status") in ("complete", "failed"):
        return JobResponse(
            job_id=job_id,
            type="unknown",
            status=cached["status"],
            result=cached.get("result"),
            error=cached.get("error"),
            created_at=datetime.now(timezone.utc),
            request_id=rid,
        )

    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.org_id == auth.org_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            404,
            {"error": "JOB_NOT_FOUND", "message": f"No job with id {job_id}. Records expire after 7 days.", "request_id": rid},
        )

    progress = None
    if job.status == "running":
        progress = JobProgress(
            step=job.progress_step,
            total=job.progress_total,
            step_name=job.progress_name,
        )

    return JobResponse(
        job_id=job.id,
        type=job.type,
        status=job.status,
        progress=progress,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        completed_at=job.completed_at,
        request_id=rid,
    )
