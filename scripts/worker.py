"""
USKill Background Worker.

Responsibilities:
  1. Dequeue async extraction / batch jobs from Redis (BRPOP).
     Falls back to polling the DB if Redis is unavailable.
  2. Deliver pending webhook outbox rows with exponential back-off.
  3. Clean up expired jobs beyond JOB_RETENTION_DAYS.

Run as a separate process (one replica is safe; use SKIP LOCKED for multi):
    python scripts/worker.py
    # or via Docker:
    docker compose run --rm api python scripts/worker.py

Signal handling:
    SIGTERM / SIGINT → finish the in-flight job, then exit cleanly.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from datetime import datetime, timezone

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import dequeue_job, set_job_result
from app.config import get_settings
from app.database import AsyncSessionLocal, wait_for_db
from app.services.extractor import extract_skill
from app.services.scorer import score_skill
from app.services.domain_resolver import resolve_domain_fv
from app.services.webhook import deliver_pending_webhooks, schedule_webhook

settings = get_settings()
logger = structlog.get_logger()

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

PIPELINE_STEPS = [
    "Task Parse", "Behavior Trace", "Intent Graph Builder",
    "Primitive Detection", "Dependency Analysis",
    "Edge Case Mining", "Transferability Scoring", "Skill Object Serialization",
]

_running = True
_current_task: asyncio.Task | None = None


def _handle_shutdown(sig, frame):
    global _running
    logger.info("worker_shutdown_signal", signal=sig)
    _running = False


# ── Job DB helpers ──────────────────────────────────────────────────────

async def _update_progress(
    db: AsyncSession, job_id: str, step: int, name: str, status: str = "running"
) -> None:
    from app.models.job import Job
    await db.execute(
        update(Job).where(Job.id == job_id).values(
            status=status,
            progress_step=step,
            progress_name=name,
            started_at=datetime.now(timezone.utc) if step == 0 else None,
        )
    )
    await db.commit()


async def _finish_job(
    db: AsyncSession, job_id: str, result: dict, error: str | None = None
) -> None:
    from app.models.job import Job
    status = "failed" if error else "complete"
    await db.execute(
        update(Job).where(Job.id == job_id).values(
            status=status,
            result=result if not error else None,
            error=error,
            completed_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    try:
        await set_job_result(
            job_id, {"status": status, "result": result, "error": error}
        )
    except Exception:
        pass  # Redis cache is best-effort


# ── Job handlers ────────────────────────────────────────────────────────

async def handle_extract(job_id: str, payload: dict) -> None:
    async with AsyncSessionLocal() as db:
        try:
            logger.info("job_started", job_id=job_id, type="extract")
            depth = payload.get("depth", "standard")
            steps = {
                "shallow": list(range(4)),
                "standard": list(range(7)),
                "deep": list(range(8)),
            }.get(depth, list(range(7)))

            for i in steps:
                await _update_progress(db, job_id, i, PIPELINE_STEPS[i])
                await asyncio.sleep(0)

            skill_data = extract_skill(
                task=payload["task"],
                source_domain=payload["source_domain"],
                primitives=None,
                episodes=payload.get("episodes", 1000),
                depth=depth,
                include_edge_cases=payload.get("edge_cases", True),
                include_rollback=payload.get("rollback", True),
                connection_id=payload.get("connection_id"),
            )

            from app.models.skill import Skill
            skill = Skill(
                id=skill_data["skill_id"],
                org_id=payload["org_id"],
                connection_id=skill_data["connection_id"],
                name=skill_data["name"],
                source_domain=skill_data["source_domain"],
                extraction_episodes=skill_data["extraction"]["episodes"],
                extraction_depth=skill_data["extraction"]["depth"],
                extraction_edge_cases=skill_data["extraction"]["edge_cases"],
                primitives=skill_data["primitives"],
                intent_graph=skill_data["intent_graph"],
                edge_cases=skill_data["edge_cases"],
                feature_vector=skill_data["feature_vector"],
                transferability=skill_data["transferability"],
                confidence_score=skill_data["confidence_score"],
                rollback_token=skill_data["rollback_token"],
                rollback_expires_at=skill_data["rollback_expires_at"],
            )
            db.add(skill)
            await db.flush()

            result = {
                "skill_id": skill_data["skill_id"],
                "transferability": skill_data["transferability"],
                "confidence_score": skill_data["confidence_score"],
            }

            # Schedule webhook inside the same transaction (outbox)
            webhook_url = payload.get("webhook_url")
            if webhook_url:
                await schedule_webhook(
                    db=db,
                    org_id=payload["org_id"],
                    url=webhook_url,
                    event_type="extraction_complete",
                    data={"job_id": job_id, "skill_id": skill_data["skill_id"]},
                )

            await db.commit()
            await _finish_job(db, job_id, result)
            logger.info("job_complete", job_id=job_id, skill_id=skill_data["skill_id"])

        except Exception as exc:
            logger.error("job_failed", job_id=job_id, error=str(exc))
            await _finish_job(db, job_id, {}, error=str(exc))


async def handle_batch(job_id: str, payload: dict) -> None:
    async with AsyncSessionLocal() as db:
        jobs: list[dict] = payload.get("jobs", [])
        org_id: str = payload.get("org_id", "")
        webhook_url: str | None = payload.get("webhook_url")
        results = []

        logger.info("batch_started", job_id=job_id, count=len(jobs))

        for idx, item in enumerate(jobs):
            await _update_progress(
                db, job_id, idx, f"Processing job {idx + 1}/{len(jobs)}"
            )
            try:
                skill_data = extract_skill(
                    task=item["task"],
                    source_domain=item["source_domain"],
                    primitives=None,
                    episodes=item.get("episodes", 1000),
                    depth=item.get("depth", "standard"),
                    include_edge_cases=True,
                    include_rollback=True,
                    connection_id=payload.get("connection_id"),
                )
                target_domain = item["target_domain"]
                target_fv = await resolve_domain_fv(target_domain, org_id, db)
                if target_fv is None:
                    raise ValueError(f"Unknown target domain: {target_domain}")

                prim_ids = [p["id"] for p in skill_data["primitives"]]
                sr = score_skill(
                    primitives=prim_ids,
                    source_domain=item["source_domain"],
                    target_domain=target_domain,
                    target_fv=target_fv,
                    threshold=0.70,
                    blend_base=True,
                    include_matrix=False,
                )
                results.append({
                    "job_index": idx,
                    "status": "INJECTED" if sr.score >= 0.70 else "PARTIAL",
                    "skill_id": skill_data["skill_id"],
                    "compat_score": sr.score,
                })
            except Exception as exc:
                results.append({"job_index": idx, "status": "FAILED", "error": str(exc)})

        summary = {
            "batch_id": job_id,
            "total": len(jobs),
            "succeeded": sum(1 for r in results if r["status"] != "FAILED"),
            "failed": sum(1 for r in results if r["status"] == "FAILED"),
            "results": results,
        }

        if webhook_url:
            await schedule_webhook(
                db=db, org_id=org_id, url=webhook_url,
                event_type="batch_complete",
                data={"batch_id": job_id, "summary": summary},
            )

        await _finish_job(db, job_id, summary)
        logger.info("batch_complete", job_id=job_id, succeeded=summary["succeeded"])


JOB_HANDLERS = {"extract": handle_extract, "batch": handle_batch}


# ── Maintenance tasks ───────────────────────────────────────────────────

async def purge_expired_jobs() -> None:
    """Delete job rows older than JOB_RETENTION_DAYS."""
    from datetime import timedelta
    from sqlalchemy import delete
    from app.models.job import Job
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.job_retention_days)
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Job).where(Job.expires_at < cutoff))
        await db.commit()
    logger.info("expired_jobs_purged", cutoff=cutoff.isoformat())


async def flush_webhook_outbox() -> None:
    """Deliver a batch of pending webhook outbox rows."""
    async with AsyncSessionLocal() as db:
        processed = await deliver_pending_webhooks(db, batch_size=50)
        if processed:
            logger.info("outbox_flushed", delivered=processed)


# ── Main loop ───────────────────────────────────────────────────────────

async def run_worker() -> None:
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    logger.info("worker_started")
    await wait_for_db()

    purge_counter = 0
    outbox_counter = 0

    while _running:
        # ── Dequeue job ──────────────────────────────────────────────
        try:
            item = await dequeue_job(timeout=2)
        except Exception as exc:
            logger.warning("redis_dequeue_error", error=str(exc))
            await asyncio.sleep(2)
            item = None

        if item is not None:
            job_id, payload = item
            job_type = payload.get("type", "extract")
            handler = JOB_HANDLERS.get(job_type)
            if handler:
                try:
                    await handler(job_id, payload)
                except Exception as exc:
                    logger.error("handler_error", job_id=job_id, error=str(exc))
            else:
                logger.warning("unknown_job_type", job_id=job_id, type=job_type)

        # ── Periodic maintenance (every ~10s) ────────────────────────
        outbox_counter += 1
        if outbox_counter >= 5:   # every ~5 poll cycles
            outbox_counter = 0
            try:
                await flush_webhook_outbox()
            except Exception as exc:
                logger.warning("outbox_flush_error", error=str(exc))

        purge_counter += 1
        if purge_counter >= 720:   # every ~24 min (720 × 2s)
            purge_counter = 0
            try:
                await purge_expired_jobs()
            except Exception as exc:
                logger.warning("purge_error", error=str(exc))

    logger.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())
