import secrets
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthContext, get_auth, require_write
from app.security import sanitise_text
from app.config import get_settings
from app.database import get_db
from app.models.connection import Connection
from app.models.skill import Skill
from app.models.transfer import Transfer
from app.schemas.common import PaginatedResponse
from app.schemas.connection import (
    ConnectionCreateRequest, ConnectionListItem, ConnectionResponse,
    ConnectionSyncRequest,
)
from app.schemas.skill import TransferResultSchema
from app.services import (
    build_adapter_log, deliver_webhook, domain_exists,
    extract_skill, list_all_domain_fvs, resolve_domain_fv,
    resolve_domain_impls, score_skill,
)

settings = get_settings()
router = APIRouter(prefix="/connections", tags=["Connections"])


def _conn_to_response(conn: Connection, request_id: str | None = None) -> ConnectionResponse:
    return ConnectionResponse(
        connection_id=conn.id,
        name=conn.name,
        source_domain=conn.source_domain,
        destination_domain=conn.destination_domain,
        status=conn.status,
        gap_threshold=conn.gap_threshold,
        allow_partial=conn.allow_partial,
        auto_rollback=conn.auto_rollback,
        webhook_url=conn.webhook_url,
        transfer_count=conn.transfer_count,
        avg_compat_score=conn.avg_compat_score,
        created_at=conn.created_at,
        request_id=request_id,
    )


# ── POST /connections ────────────────────────────────────────────────
@router.post("", response_model=ConnectionResponse, status_code=201)
async def create_connection(
    body: ConnectionCreateRequest,
    request: Request,
    auth: AuthContext = Depends(require_write),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id

    # Sanitise free-text input
    body.name = sanitise_text(body.name, field_name="name", request=request)

    # Validate domains differ
    if body.source_domain == body.destination_domain:
        raise HTTPException(
            status_code=422,
            detail={"error": "INVALID_REQUEST", "message": "source_domain and destination_domain must differ.", "request_id": rid},
        )

    # Validate both domains exist
    for dom in (body.source_domain, body.destination_domain):
        if not await domain_exists(dom, auth.org_id, db):
            raise HTTPException(
                status_code=422,
                detail={"error": "DOMAIN_UNKNOWN", "message": f'Unknown domain: "{dom}". Register it via POST /domains/register.', "request_id": rid},
            )

    # Enforce plan connection limit
    max_conn = settings.max_connections_for_plan(auth.plan)
    if max_conn > 0:
        count_result = await db.execute(
            select(func.count()).select_from(Connection).where(
                Connection.org_id == auth.org_id,
                Connection.status != "archived",
            )
        )
        current_count = count_result.scalar_one()
        if current_count >= max_conn:
            raise HTTPException(
                status_code=403,
                detail={"error": "PLAN_LIMIT", "message": f"Your {auth.plan} plan allows {max_conn} active connections.", "request_id": rid},
            )

    conn = Connection(
        id="cn_" + secrets.token_hex(4),
        org_id=auth.org_id,
        name=body.name,
        source_domain=body.source_domain,
        destination_domain=body.destination_domain,
        gap_threshold=body.gap_threshold,
        allow_partial=body.allow_partial,
        auto_rollback=body.auto_rollback,
        webhook_url=body.webhook_url,
        metadata_=body.metadata,
    )
    db.add(conn)
    await db.flush()
    return _conn_to_response(conn, rid)


# ── GET /connections ─────────────────────────────────────────────────
@router.get("", response_model=PaginatedResponse[ConnectionListItem])
async def list_connections(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    auth: AuthContext = Depends(get_auth),
    db: AsyncSession = Depends(get_db),
):
    q = select(Connection).where(Connection.org_id == auth.org_id)
    if status_filter:
        q = q.where(Connection.status == status_filter)
    if cursor:
        q = q.where(Connection.id < cursor)
    q = q.order_by(Connection.created_at.desc()).limit(limit + 1)

    result = await db.execute(q)
    rows = result.scalars().all()
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = items[-1].id if has_more else None

    count_q = select(func.count()).select_from(Connection).where(Connection.org_id == auth.org_id)
    total = (await db.execute(count_q)).scalar_one()

    return PaginatedResponse(
        items=[
            ConnectionListItem(
                connection_id=c.id,
                name=c.name,
                source_domain=c.source_domain,
                destination_domain=c.destination_domain,
                status=c.status,
                transfer_count=c.transfer_count,
                avg_compat_score=c.avg_compat_score,
                created_at=c.created_at,
            )
            for c in items
        ],
        total=total,
        next_cursor=next_cursor,
    )


# ── GET /connections/:id ─────────────────────────────────────────────
@router.get("/{conn_id}", response_model=ConnectionResponse)
async def get_connection(
    conn_id: str,
    request: Request,
    auth: AuthContext = Depends(get_auth),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id
    result = await db.execute(
        select(Connection).where(Connection.id == conn_id, Connection.org_id == auth.org_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "CONNECTION_NOT_FOUND", "message": f"No connection with id {conn_id}.", "request_id": rid},
        )
    return _conn_to_response(conn, rid)


# ── POST /connections/:id/sync ───────────────────────────────────────
@router.post("/{conn_id}/sync", response_model=TransferResultSchema)
async def sync_connection(
    conn_id: str,
    body: ConnectionSyncRequest,
    request: Request,
    auth: AuthContext = Depends(require_write),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id
    t_start = time.perf_counter()

    # Load connection
    result = await db.execute(
        select(Connection).where(Connection.id == conn_id, Connection.org_id == auth.org_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(404, {"error": "CONNECTION_NOT_FOUND", "message": f"No connection with id {conn_id}.", "request_id": rid})
    if conn.status != "active":
        raise HTTPException(409, {"error": "CONNECTION_PAUSED", "message": f"Connection is {conn.status}. Resume it before syncing.", "request_id": rid})

    # Episode limit check
    max_eps = settings.max_episodes_for_plan(auth.plan)
    if body.episodes > max_eps:
        raise HTTPException(403, {"error": "PLAN_LIMIT", "message": f"Your {auth.plan} plan allows max {max_eps} episodes.", "request_id": rid})

    threshold = body.override_threshold or conn.gap_threshold

    # Resolve domain FVs
    src_fv = await resolve_domain_fv(conn.source_domain, auth.org_id, db)
    dst_fv = await resolve_domain_fv(conn.destination_domain, auth.org_id, db)
    all_fvs = await list_all_domain_fvs(auth.org_id, db)

    # 1. Extract
    skill_data = extract_skill(
        task=body.task,
        source_domain=conn.source_domain,
        primitives=None,
        episodes=body.episodes,
        depth=body.depth,
        include_edge_cases=body.edge_cases,
        include_rollback=True,
        connection_id=conn_id,
    )
    prim_ids = [p["id"] for p in skill_data["primitives"]]

    # 2. Score
    score_result = score_skill(
        primitives=prim_ids,
        source_domain=conn.source_domain,
        target_domain=conn.destination_domain,
        target_fv=dst_fv,
        threshold=threshold,
        blend_base=True,
        include_matrix=False,
        all_domain_fvs=all_fvs,
    )

    # 3. Determine status
    if score_result.score < threshold and not conn.allow_partial:
        transfer_status = "REJECTED"
    elif score_result.score < threshold:
        transfer_status = "PARTIAL"
    elif body.dry_run:
        transfer_status = "DRY_RUN"
    else:
        transfer_status = "INJECTED"

    # 4. Build adapter log
    custom_impls = await resolve_domain_impls(conn.destination_domain, auth.org_id, db)
    adapter_log = build_adapter_log(
        primitives=prim_ids,
        source_domain=conn.source_domain,
        target_domain=conn.destination_domain,
        target_fv=dst_fv,
        threshold=threshold,
        custom_impls=custom_impls,
    )

    duration_ms = round((time.perf_counter() - t_start) * 1000)
    transfer_id = "tr_" + secrets.token_hex(4)

    # 5. Persist (skip on dry run)
    if transfer_status != "DRY_RUN":
        # Save skill
        from app.models.skill import Skill
        skill_model = Skill(
            id=skill_data["skill_id"],
            org_id=auth.org_id,
            connection_id=conn_id,
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
        db.add(skill_model)

        # Save transfer record
        from app.models.transfer import Transfer
        transfer_model = Transfer(
            id=transfer_id,
            org_id=auth.org_id,
            connection_id=conn_id,
            skill_id=skill_data["skill_id"],
            source_domain=conn.source_domain,
            destination_domain=conn.destination_domain,
            compat_score=score_result.score,
            status=transfer_status,
            sub_scores=score_result.sub_scores.model_dump(),
            gaps=[g.model_dump() for g in score_result.gaps],
            adapter_log=[e.model_dump() for e in adapter_log],
            rollback_token=skill_data["rollback_token"],
            rollback_expires_at=skill_data["rollback_expires_at"],
            duration_ms=duration_ms,
            dry_run=False,
        )
        db.add(transfer_model)

        # Update connection stats
        prev_count = conn.transfer_count
        conn.transfer_count = prev_count + 1
        if conn.avg_compat_score is None:
            conn.avg_compat_score = score_result.score
        else:
            conn.avg_compat_score = round(
                (conn.avg_compat_score * prev_count + score_result.score) / (prev_count + 1), 4
            )
        await db.flush()

        # Schedule webhook via outbox (atomic, durable)
        if conn.webhook_url:
            from app.services.webhook import schedule_webhook
            await schedule_webhook(
                db=db,
                org_id=auth.org_id,
                url=conn.webhook_url,
                event_type="transfer_complete",
                data={"transfer_id": transfer_id, "compat_score": score_result.score, "status": transfer_status},
            )

    return TransferResultSchema(
        transfer_id=transfer_id,
        connection_id=conn_id,
        skill_id=skill_data["skill_id"],
        source_domain=conn.source_domain,
        destination_domain=conn.destination_domain,
        compat_score=score_result.score,
        status=transfer_status,
        sub_scores=score_result.sub_scores,
        gaps=score_result.gaps,
        adapter_log=adapter_log,
        rollback_token=skill_data["rollback_token"],
        duration_ms=duration_ms,
        request_id=rid,
    )


# ── GET /connections/:id/history ─────────────────────────────────────
@router.get("/{conn_id}/history", response_model=PaginatedResponse)
async def connection_history(
    conn_id: str,
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    auth: AuthContext = Depends(get_auth),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rid = request.state.request_id
    # Verify ownership
    conn_result = await db.execute(
        select(Connection.id).where(Connection.id == conn_id, Connection.org_id == auth.org_id)
    )
    if conn_result.scalar_one_or_none() is None:
        raise HTTPException(404, {"error": "CONNECTION_NOT_FOUND", "message": f"No connection with id {conn_id}.", "request_id": rid})

    q = select(Transfer).where(Transfer.connection_id == conn_id, Transfer.org_id == auth.org_id)
    if status_filter:
        q = q.where(Transfer.status == status_filter)
    if cursor:
        q = q.where(Transfer.id < cursor)
    q = q.order_by(Transfer.created_at.desc()).limit(limit + 1)

    rows = (await db.execute(q)).scalars().all()
    has_more = len(rows) > limit
    items = rows[:limit]

    total_result = await db.execute(
        select(func.count()).select_from(Transfer).where(Transfer.connection_id == conn_id)
    )
    total = total_result.scalar_one()

    from app.schemas.connection import TransferHistoryItem
    return PaginatedResponse(
        items=[
            TransferHistoryItem(
                transfer_id=t.id,
                skill_id=t.skill_id,
                compat_score=t.compat_score,
                status=t.status,
                created_at=t.created_at.isoformat(),
            )
            for t in items
        ],
        total=total,
        next_cursor=items[-1].id if has_more else None,
    )


# ── DELETE /connections/:id ──────────────────────────────────────────
@router.delete("/{conn_id}", status_code=204)
async def delete_connection(
    conn_id: str,
    request: Request,
    purge_skills: bool = Query(default=False),
    purge_logs: bool = Query(default=False),
    auth: AuthContext = Depends(require_write),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id
    result = await db.execute(
        select(Connection).where(Connection.id == conn_id, Connection.org_id == auth.org_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(404, {"error": "CONNECTION_NOT_FOUND", "message": f"No connection with id {conn_id}.", "request_id": rid})

    if purge_skills:
        skills_result = await db.execute(
            select(Skill).where(Skill.connection_id == conn_id)
        )
        for skill in skills_result.scalars():
            await db.delete(skill)

    if purge_logs:
        logs_result = await db.execute(
            select(Transfer).where(Transfer.connection_id == conn_id)
        )
        for t in logs_result.scalars():
            await db.delete(t)

    await db.delete(conn)
    await db.flush()


# ── PATCH /connections/:id/status ────────────────────────────────────
from app.schemas.connection import ConnectionStatusUpdate

@router.patch("/{conn_id}/status", response_model=ConnectionResponse)
async def update_connection_status(
    conn_id: str,
    body: ConnectionStatusUpdate,
    request: Request,
    auth: AuthContext = Depends(require_write),
    db: AsyncSession = Depends(get_db),
):
    """
    Transition a connection between active / paused / archived states.

    Rules:
      active   → paused    (pause syncing; connection data preserved)
      paused   → active    (resume syncing)
      *        → archived  (soft-delete; cannot be un-archived via API)
    """
    rid = request.state.request_id
    result = await db.execute(
        select(Connection).where(Connection.id == conn_id, Connection.org_id == auth.org_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(
            404,
            {"error": "CONNECTION_NOT_FOUND", "message": f"No connection with id {conn_id}.", "request_id": rid},
        )

    current = conn.status
    target = body.status

    # Guard invalid transitions
    if current == "archived":
        raise HTTPException(
            409,
            {"error": "INVALID_TRANSITION",
             "message": "Archived connections cannot be reactivated. Create a new connection.",
             "request_id": rid},
        )
    if current == target:
        raise HTTPException(
            409,
            {"error": "INVALID_TRANSITION",
             "message": f"Connection is already {current}.",
             "request_id": rid},
        )

    conn.status = target
    await db.flush()
    return _conn_to_response(conn, rid)
