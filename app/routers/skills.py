import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthContext, get_auth, require_write
from app.security import sanitise_text
from app.config import get_settings
from app.database import get_db
from app.models.skill import Skill
from app.models.transfer import Transfer
from app.schemas.common import PaginatedResponse, GapReportSchema, AdapterEntrySchema, SubScoresSchema
from app.schemas.skill import (
    BatchJobResponse, BatchRequest, ExtractRequest,
    RefineRequest, RefineResponse,
    RollbackRequest, RollbackResponse,
    ScoreRequest, ScoreResponse,
    SkillListItemSchema, SkillObjectSchema, IntentGraphMetaSchema,
    TransferRequest, TransferResultSchema,
    ValidateRequest, ValidateResponse,
    PrimitiveSchema, EdgeCaseSchema,
)
from app.schemas.common import FeatureVectorSchema
from app.services import (
    build_adapter_log, deliver_webhook, domain_exists,
    extract_skill, list_all_domain_fvs,
    resolve_domain_fv, resolve_domain_impls, score_skill,
)

settings = get_settings()
router = APIRouter(prefix="/skills", tags=["Skills"])

ASYNC_THRESHOLD = settings.async_threshold_episodes


def _skill_to_schema(skill: Skill, request_id: str | None = None) -> SkillObjectSchema:
    return SkillObjectSchema(
        skill_id=skill.id,
        name=skill.name,
        version=skill.version,
        source_domain=skill.source_domain,
        extraction={
            "episodes": skill.extraction_episodes,
            "depth": skill.extraction_depth,
            "edge_cases": skill.extraction_edge_cases,
        },
        primitives=[PrimitiveSchema(**p) for p in skill.primitives],
        intent_graph=IntentGraphMetaSchema(**skill.intent_graph),
        edge_cases=[EdgeCaseSchema(**e) for e in skill.edge_cases],
        feature_vector=FeatureVectorSchema(**skill.feature_vector),
        transferability=skill.transferability,
        confidence_score=skill.confidence_score,
        rollback_token=skill.rollback_token,
        connection_id=skill.connection_id,
        created_at=skill.created_at,
        request_id=request_id,
    )


# ── POST /skills/validate ────────────────────────────────────────────
@router.post("/validate", response_model=ValidateResponse)
async def validate_skill(
    body: ValidateRequest,
    request: Request,
    auth: AuthContext = Depends(get_auth),
):
    rid = request.state.request_id
    errors = []
    warnings = []
    skill = body.skill

    required = ["skill_id", "name", "source_domain", "primitives"]
    for field in required:
        if field not in skill:
            errors.append({"field": field, "code": "MISSING_FIELD", "message": f"'{field}' is required."})

    if "skill_id" in skill and not str(skill["skill_id"]).startswith("sk_"):
        errors.append({"field": "skill_id", "code": "INVALID_FORMAT", "message": "Must match pattern sk_[0-9a-f]{8}"})

    if "confidence_score" in skill:
        try:
            v = float(skill["confidence_score"])
            if not 0.0 <= v <= 1.0:
                errors.append({"field": "confidence_score", "code": "OUT_OF_RANGE", "message": "Must be float in [0.0, 1.0]"})
        except (TypeError, ValueError):
            errors.append({"field": "confidence_score", "code": "INVALID_TYPE", "message": "Must be a float."})

    if skill.get("rollback_token") is None:
        warnings.append("rollback_token is null — rollback not available for this skill.")

    return ValidateResponse(valid=len(errors) == 0, errors=errors, warnings=warnings, request_id=rid)


# ── POST /skills/batch ───────────────────────────────────────────────
@router.post("/batch", response_model=BatchJobResponse, status_code=202)
async def batch_extract(
    body: BatchRequest,
    request: Request,
    auth: AuthContext = Depends(require_write),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id
    max_batch = settings.max_batch_for_plan(auth.plan)
    if len(body.jobs) > max_batch:
        raise HTTPException(
            status_code=403,
            detail={"error": "PLAN_LIMIT", "message": f"Your {auth.plan} plan allows max {max_batch} jobs per batch.", "request_id": rid},
        )

    from app.models.job import Job
    job_id = "bat_" + secrets.token_hex(4)
    job = Job(
        id=job_id,
        org_id=auth.org_id,
        type="batch",
        status="queued",
        progress_total=len(body.jobs),
        input_data={
            "jobs": [j.model_dump() for j in body.jobs],
            "webhook_url": body.webhook_url,
            "connection_id": body.connection_id,
        },
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.job_retention_days),
    )
    db.add(job)
    await db.flush()
    # Enqueue to Redis for the worker process
    try:
        from app.cache import enqueue_job
        await enqueue_job(job_id, {
            **body.model_dump(),
            "org_id": auth.org_id,
            "type": "batch",
        })
    except Exception:
        pass  # Redis unavailable — worker polls DB directly

    return BatchJobResponse(
        batch_id=job_id,
        job_count=len(body.jobs),
        status="queued",
        poll_url=f"/v2/jobs/{job_id}",
        estimated_ms=len(body.jobs) * 1200,
        request_id=rid,
    )


# ── POST /skills/extract ─────────────────────────────────────────────
@router.post("/extract", status_code=200)
async def extract(
    body: ExtractRequest,
    request: Request,
    auth: AuthContext = Depends(require_write),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id

    # Sanitise free-text input
    body.task = sanitise_text(body.task, field_name="task", request=request)

    max_eps = settings.max_episodes_for_plan(auth.plan)
    if body.episodes > max_eps:
        raise HTTPException(403, {"error": "PLAN_LIMIT", "message": f"Your {auth.plan} plan allows max {max_eps} episodes.", "request_id": rid})

    if not await domain_exists(body.source_domain, auth.org_id, db):
        raise HTTPException(422, {"error": "DOMAIN_UNKNOWN", "message": f'Unknown domain: "{body.source_domain}".', "request_id": rid})

    # Async path for large episode counts
    if body.episodes > ASYNC_THRESHOLD:
        from app.models.job import Job
        from app.cache import enqueue_job
        job_id = "job_" + secrets.token_hex(4)
        job = Job(
            id=job_id,
            org_id=auth.org_id,
            type="extract",
            status="queued",
            progress_total=8,
            input_data=body.model_dump(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.job_retention_days),
        )
        db.add(job)
        await db.flush()
        # Enqueue to Redis for the worker process (fail-open: worker polls DB)
        try:
            await enqueue_job(job_id, {
                **body.model_dump(),
                "org_id": auth.org_id,
                "type": "extract",
            })
        except Exception:
            pass
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=202,
            content={
                "job_id": job_id,
                "status": "queued",
                "poll_url": f"/v2/jobs/{job_id}",
                "estimated_ms": body.episodes * 6,
                "request_id": rid,
            },
        )

    # Sync extraction
    skill_data = extract_skill(
        task=body.task,
        source_domain=body.source_domain,
        primitives=None,
        episodes=body.episodes,
        depth=body.depth,
        include_edge_cases=body.edge_cases,
        include_rollback=body.rollback,
        connection_id=body.connection_id,
    )

    skill = Skill(
        id=skill_data["skill_id"],
        org_id=auth.org_id,
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

    return _skill_to_schema(skill, rid)


# ── GET /skills ──────────────────────────────────────────────────────
@router.get("", response_model=PaginatedResponse[SkillListItemSchema])
async def list_skills(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    domain: str | None = None,
    connection_id: str | None = None,
    after: datetime | None = None,
    fields: str | None = None,
    auth: AuthContext = Depends(get_auth),
    db: AsyncSession = Depends(get_db),
):
    q = select(Skill).where(Skill.org_id == auth.org_id)
    if domain:
        q = q.where(Skill.source_domain == domain)
    if connection_id:
        q = q.where(Skill.connection_id == connection_id)
    if after:
        q = q.where(Skill.created_at > after)
    if cursor:
        q = q.where(Skill.id < cursor)
    q = q.order_by(Skill.created_at.desc()).limit(limit + 1)

    rows = (await db.execute(q)).scalars().all()
    has_more = len(rows) > limit
    items = rows[:limit]

    total = (await db.execute(
        select(func.count()).select_from(Skill).where(Skill.org_id == auth.org_id)
    )).scalar_one()

    return PaginatedResponse(
        items=[
            SkillListItemSchema(
                skill_id=s.id,
                name=s.name,
                source_domain=s.source_domain,
                transferability=s.transferability,
                confidence_score=s.confidence_score,
                connection_id=s.connection_id,
                created_at=s.created_at,
            )
            for s in items
        ],
        total=total,
        next_cursor=items[-1].id if has_more else None,
    )


# ── GET /skills/:id ──────────────────────────────────────────────────
@router.get("/{skill_id}", response_model=SkillObjectSchema)
async def get_skill(
    skill_id: str,
    request: Request,
    auth: AuthContext = Depends(get_auth),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.org_id == auth.org_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(404, {"error": "SKILL_NOT_FOUND", "message": f"No skill with id {skill_id}.", "request_id": rid})
    return _skill_to_schema(skill, rid)


# ── GET /skills/:id/graph ────────────────────────────────────────────
@router.get("/{skill_id}/graph")
async def get_skill_graph(
    skill_id: str,
    request: Request,
    auth: AuthContext = Depends(get_auth),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.org_id == auth.org_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(404, {"error": "SKILL_NOT_FOUND", "message": f"No skill with id {skill_id}.", "request_id": rid})

    # Build a full graph from primitive list
    prims = [p["id"] for p in skill.primitives]
    from app.data import get_category
    nodes = [{"id": "g0", "label": f"GOAL: {skill.name[:40]}", "type": "GOAL", "primitive": "plan_sequence", "x": 400, "y": 30}]
    edges = []
    prev = "g0"
    for idx, pid in enumerate(prims):
        nid = f"n{idx+1}"
        cat = get_category(pid) or "ACTION"
        nodes.append({"id": nid, "label": pid, "type": cat, "primitive": pid, "x": 100 + (idx % 3) * 220, "y": 110 + (idx // 3) * 100})
        edges.append({"f": prev, "t": nid})
        if idx % 3 == 2:
            prev = nid
    # Terminal
    nodes.append({"id": "t0", "label": "SUCCESS", "type": "TERMINAL", "primitive": None, "x": 400, "y": 110 + (len(prims) // 3 + 1) * 100})
    edges.append({"f": f"n{len(prims)}", "t": "t0"})

    return {
        "skill_id": skill_id,
        "schema_version": "uskill-graph/v2",
        "nodes": nodes,
        "edges": edges,
        "depth": skill.intent_graph.get("depth", 5),
        "cycles": 0,
        "request_id": rid,
    }


# ── POST /skills/:id/score ───────────────────────────────────────────
@router.post("/{skill_id}/score", response_model=ScoreResponse)
async def score_skill_endpoint(
    skill_id: str,
    body: ScoreRequest,
    request: Request,
    auth: AuthContext = Depends(get_auth),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.org_id == auth.org_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(404, {"error": "SKILL_NOT_FOUND", "message": f"No skill with id {skill_id}.", "request_id": rid})

    if not await domain_exists(body.target_domain, auth.org_id, db):
        raise HTTPException(422, {"error": "DOMAIN_UNKNOWN", "message": f'Unknown domain: "{body.target_domain}".', "request_id": rid})

    target_fv = await resolve_domain_fv(body.target_domain, auth.org_id, db)
    all_fvs = await list_all_domain_fvs(auth.org_id, db) if body.include_matrix else None
    prim_ids = [p["id"] for p in skill.primitives]

    result = score_skill(
        primitives=prim_ids,
        source_domain=skill.source_domain,
        target_domain=body.target_domain,
        target_fv=target_fv,
        threshold=body.threshold,
        blend_base=body.blend_base,
        include_matrix=body.include_matrix,
        all_domain_fvs=all_fvs,
    )

    return ScoreResponse(
        skill_id=skill_id,
        target_domain=body.target_domain,
        score=result.score,
        sub_scores=result.sub_scores,
        gaps=result.gaps,
        matrix_row=result.matrix_row,
        request_id=rid,
    )


# ── POST /skills/:id/transfer ────────────────────────────────────────
@router.post("/{skill_id}/transfer", response_model=TransferResultSchema)
async def transfer_skill(
    skill_id: str,
    body: TransferRequest,
    request: Request,
    auth: AuthContext = Depends(require_write),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id
    t_start = time.perf_counter()

    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.org_id == auth.org_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(404, {"error": "SKILL_NOT_FOUND", "message": f"No skill with id {skill_id}.", "request_id": rid})

    # Resolve destination domain
    dest_domain = body.destination_domain
    if not dest_domain and body.connection_id:
        from app.models.connection import Connection as Conn
        cr = await db.execute(select(Conn).where(Conn.id == body.connection_id, Conn.org_id == auth.org_id))
        conn = cr.scalar_one_or_none()
        if conn:
            dest_domain = conn.destination_domain

    if not dest_domain:
        raise HTTPException(422, {"error": "INVALID_REQUEST", "message": "destination_domain is required when not using a connection.", "request_id": rid})

    if not await domain_exists(dest_domain, auth.org_id, db):
        raise HTTPException(422, {"error": "DOMAIN_UNKNOWN", "message": f'Unknown domain: "{dest_domain}".', "request_id": rid})

    target_fv = await resolve_domain_fv(dest_domain, auth.org_id, db)
    prim_ids = [p["id"] for p in skill.primitives]

    score_result = score_skill(
        primitives=prim_ids,
        source_domain=skill.source_domain,
        target_domain=dest_domain,
        target_fv=target_fv,
        threshold=body.gap_threshold,
        blend_base=True,
        include_matrix=False,
    )

    if score_result.score < body.gap_threshold and not body.allow_partial:
        raise HTTPException(422, {"error": "SCORE_TOO_LOW", "message": f"Compat score {score_result.score:.2%} is below threshold {body.gap_threshold:.2%} and allow_partial is false.", "request_id": rid})

    if score_result.score < body.gap_threshold:
        xfer_status = "PARTIAL"
    elif body.dry_run:
        xfer_status = "DRY_RUN"
    else:
        xfer_status = "INJECTED"

    custom_impls = await resolve_domain_impls(dest_domain, auth.org_id, db)
    adapter_log = build_adapter_log(
        primitives=prim_ids,
        source_domain=skill.source_domain,
        target_domain=dest_domain,
        target_fv=target_fv,
        threshold=body.gap_threshold,
        custom_impls=custom_impls,
    )

    duration_ms = round((time.perf_counter() - t_start) * 1000)
    transfer_id = "tr_" + secrets.token_hex(4)

    if xfer_status != "DRY_RUN":
        xfer = Transfer(
            id=transfer_id,
            org_id=auth.org_id,
            connection_id=body.connection_id,
            skill_id=skill_id,
            source_domain=skill.source_domain,
            destination_domain=dest_domain,
            compat_score=score_result.score,
            status=xfer_status,
            sub_scores=score_result.sub_scores.model_dump(),
            gaps=[g.model_dump() for g in score_result.gaps],
            adapter_log=[e.model_dump() for e in adapter_log],
            rollback_token=skill.rollback_token,
            rollback_expires_at=skill.rollback_expires_at,
            duration_ms=duration_ms,
            dry_run=False,
        )
        db.add(xfer)
        await db.flush()

    return TransferResultSchema(
        transfer_id=transfer_id,
        connection_id=body.connection_id,
        skill_id=skill_id,
        source_domain=skill.source_domain,
        destination_domain=dest_domain,
        compat_score=score_result.score,
        status=xfer_status,
        sub_scores=score_result.sub_scores,
        gaps=score_result.gaps,
        adapter_log=adapter_log,
        rollback_token=skill.rollback_token,
        duration_ms=duration_ms,
        request_id=rid,
    )


# ── POST /skills/:id/rollback ────────────────────────────────────────
@router.post("/{skill_id}/rollback", response_model=RollbackResponse)
async def rollback_skill(
    skill_id: str,
    body: RollbackRequest,
    request: Request,
    auth: AuthContext = Depends(require_write),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.org_id == auth.org_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(404, {"error": "SKILL_NOT_FOUND", "message": f"No skill with id {skill_id}.", "request_id": rid})

    if skill.rollback_token != body.rollback_token:
        raise HTTPException(401, {"error": "UNAUTHORIZED", "message": "Invalid rollback_token.", "request_id": rid})

    if skill.rollback_used:
        raise HTTPException(409, {"error": "TOKEN_USED", "message": "This rollback_token was already redeemed.", "request_id": rid})

    now = datetime.now(timezone.utc)
    exp = skill.rollback_expires_at
    # SQLite returns naive datetimes; normalise before comparing
    if exp is not None:
        if exp.tzinfo is None:
            from datetime import timezone as _tz
            exp = exp.replace(tzinfo=_tz.utc)
    if exp is not None and exp < now:
        raise HTTPException(410, {"error": "TOKEN_EXPIRED", "message": "Rollback window has expired (72h). Use manual snapshot restoration.", "request_id": rid})

    skill.rollback_used = True

    # Mark most recent transfer as ROLLED_BACK
    xfer_result = await db.execute(
        select(Transfer)
        .where(Transfer.skill_id == skill_id, Transfer.org_id == auth.org_id)
        .order_by(Transfer.created_at.desc())
        .limit(1)
    )
    latest_xfer = xfer_result.scalar_one_or_none()
    if latest_xfer:
        latest_xfer.status = "ROLLED_BACK"

    await db.flush()
    return RollbackResponse(
        skill_id=skill_id,
        status="ROLLED_BACK",
        message="Destination agent restored to pre-injection state.",
        request_id=rid,
    )


# ── PUT /skills/:id/refine ───────────────────────────────────────────
@router.put("/{skill_id}/refine", response_model=RefineResponse)
async def refine_skill(
    skill_id: str,
    body: RefineRequest,
    request: Request,
    auth: AuthContext = Depends(require_write),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.org_id == auth.org_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(404, {"error": "SKILL_NOT_FOUND", "message": f"No skill with id {skill_id}.", "request_id": rid})

    old_prim_ids = [p["id"] for p in skill.primitives]

    # Re-extract with additional episodes
    new_data = extract_skill(
        task=skill.name,
        source_domain=skill.source_domain,
        primitives=None,
        episodes=body.additional_episodes,
        depth=skill.extraction_depth,
        include_edge_cases=skill.extraction_edge_cases,
        include_rollback=True,
        connection_id=skill.connection_id,
    )
    new_prim_ids = [p["id"] for p in new_data["primitives"]]

    # Merge strategies
    if body.merge_strategy == "replace":
        merged_prims = new_data["primitives"]
    elif body.merge_strategy == "additive":
        seen = {p["id"] for p in skill.primitives}
        merged_prims = skill.primitives + [p for p in new_data["primitives"] if p["id"] not in seen]
    else:  # weighted_avg
        old_map = {p["id"]: p for p in skill.primitives}
        new_map = {p["id"]: p for p in new_data["primitives"]}
        merged_prims = []
        for pid in dict.fromkeys(list(old_map) + list(new_map)):
            if pid in old_map and pid in new_map:
                merged_prims.append({
                    **old_map[pid],
                    "weight": round((old_map[pid]["weight"] + new_map[pid]["weight"]) / 2, 3),
                    "confidence": round((old_map[pid]["confidence"] + new_map[pid]["confidence"]) / 2, 3),
                })
            elif pid in new_map:
                merged_prims.append(new_map[pid])
            else:
                merged_prims.append(old_map[pid])

    # Bump version
    if body.bump_version:
        parts = skill.version.split(".")
        new_version = f"{parts[0]}.{int(parts[1])+1}.0"
    else:
        new_version = skill.version

    new_skill = Skill(
        id=new_data["skill_id"],
        org_id=auth.org_id,
        connection_id=skill.connection_id,
        name=skill.name,
        version=new_version,
        source_domain=skill.source_domain,
        extraction_episodes=skill.extraction_episodes + body.additional_episodes,
        extraction_depth=skill.extraction_depth,
        extraction_edge_cases=skill.extraction_edge_cases,
        primitives=merged_prims,
        intent_graph=new_data["intent_graph"],
        edge_cases=new_data["edge_cases"],
        feature_vector=new_data["feature_vector"],
        transferability=new_data["transferability"],
        confidence_score=new_data["confidence_score"],
        rollback_token=new_data["rollback_token"],
        rollback_expires_at=new_data["rollback_expires_at"],
        previous_skill_id=skill_id,
        refine_version=skill.refine_version + 1,
    )
    db.add(new_skill)
    await db.flush()

    prims_added = len([p for p in merged_prims if p["id"] not in {x["id"] for x in skill.primitives}])
    prims_removed = len([p for p in skill.primitives if p["id"] not in {x["id"] for x in merged_prims}])

    return RefineResponse(
        new_skill_id=new_skill.id,
        previous_skill_id=skill_id,
        version=new_version,
        delta={
            "primitives_added": prims_added,
            "primitives_removed": prims_removed,
            "confidence_delta": round(new_skill.confidence_score - skill.confidence_score, 4),
            "transferability_delta": round(new_skill.transferability - skill.transferability, 4),
        },
        request_id=rid,
    )


# ── DELETE /skills/:id ───────────────────────────────────────────────
@router.delete("/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: str,
    request: Request,
    force: bool = Query(default=False),
    purge_logs: bool = Query(default=False),
    auth: AuthContext = Depends(require_write),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.org_id == auth.org_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(404, {"error": "SKILL_NOT_FOUND", "message": f"No skill with id {skill_id}.", "request_id": rid})

    if not force:
        active_xfer = await db.execute(
            select(Transfer.id).where(
                Transfer.skill_id == skill_id,
                Transfer.status == "INJECTED",
            ).limit(1)
        )
        if active_xfer.scalar_one_or_none():
            raise HTTPException(409, {"error": "ACTIVE_INJECTION", "message": "This skill has an active injection. Rollback first or pass ?force=true.", "request_id": rid})

    if purge_logs:
        logs = (await db.execute(select(Transfer).where(Transfer.skill_id == skill_id))).scalars()
        for t in logs:
            await db.delete(t)

    await db.delete(skill)
    await db.flush()
