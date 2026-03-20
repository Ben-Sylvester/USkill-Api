"""
Domains router — browse built-in domains, register custom ones,
and compute compatibility matrices.

Endpoints:
  GET  /v2/domains                   — list all domains (built-in + custom)
  POST /v2/domains/register          — register a custom domain
  GET  /v2/domains/compat-matrix     — full NxN base compatibility matrix
  GET  /v2/domains/{domain_id}       — get a single domain
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthContext, get_auth, require_write
from app.database import get_db
from app.data.domains import BUILT_IN_DOMAINS, get_built_in_domain, is_built_in
from app.data.bcm import BASE_COMPAT_MATRIX
from app.models.domain import CustomDomain
from app.schemas.domain import (
    CompatMatrixResponse,
    DomainRegisterRequest,
    DomainResponse,
)
from app.services.domain_resolver import list_all_domain_fvs

router = APIRouter(prefix="/domains", tags=["Domains"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _builtin_to_response(d: dict, request_id: str | None = None) -> DomainResponse:
    from app.data.primitives import PRIMITIVES_BY_CATEGORY
    # Count primitives that have implementations for this domain
    prim_count = sum(
        1 for p in (PRIMITIVES_BY_CATEGORY.get(cat, []) for cat in ("PERCEPTION", "COGNITION",
            "ACTION", "CONTROL", "COMMUNICATION", "LEARNING"))
        for _ in p
        if True  # all primitives apply to built-in domains
    )
    # Use the actual primitive list length
    from app.data.primitives import PRIMITIVES
    prim_count = len(PRIMITIVES)

    from app.schemas.common import FeatureVectorSchema
    return DomainResponse(
        id=d["id"],
        name=d["name"],
        icon=d["icon"],
        built_in=True,
        description=d.get("description"),
        primitive_count=prim_count,
        feature_vector=FeatureVectorSchema(**d["feature_vector"]),
        created_at=None,
        request_id=request_id,
    )


def _custom_to_response(c: CustomDomain, request_id: str | None = None) -> DomainResponse:
    from app.schemas.common import FeatureVectorSchema
    impl_count = len(c.primitive_impls) if c.primitive_impls else 0
    return DomainResponse(
        id=c.id,
        name=c.name,
        icon=c.icon,
        built_in=False,
        description=c.description,
        primitive_count=impl_count,
        feature_vector=FeatureVectorSchema(**c.feature_vector),
        created_at=c.created_at,
        request_id=request_id,
    )


# ── GET /domains ─────────────────────────────────────────────────────
@router.get("")
async def list_domains(
    request: Request,
    built_in_only: bool = Query(default=False),
    auth: AuthContext = Depends(get_auth),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id
    domains: list[DomainResponse] = [
        _builtin_to_response(d, rid) for d in BUILT_IN_DOMAINS
    ]

    if not built_in_only:
        result = await db.execute(
            select(CustomDomain).where(CustomDomain.org_id == auth.org_id)
        )
        for custom in result.scalars():
            domains.append(_custom_to_response(custom, rid))

    return {"items": [d.model_dump() for d in domains], "total": len(domains)}


# ── GET /domains/compat-matrix ───────────────────────────────────────
@router.get("/compat", response_model=CompatMatrixResponse)
@router.get("/compat-matrix", response_model=CompatMatrixResponse)
async def get_compat_matrix(
    request: Request,
    skill_id: str | None = Query(default=None),
    auth: AuthContext = Depends(get_auth),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id

    if skill_id:
        # Skill-adjusted matrix: recompute each cell using skill primitives
        from sqlalchemy import select as sa_select
        from app.models.skill import Skill
        from app.services.scorer import score_skill
        from app.services.domain_resolver import list_all_domain_fvs

        result = await db.execute(
            sa_select(Skill).where(Skill.id == skill_id, Skill.org_id == auth.org_id)
        )
        skill = result.scalar_one_or_none()
        if not skill:
            raise HTTPException(
                404,
                {"error": "SKILL_NOT_FOUND", "message": f"No skill {skill_id}.", "request_id": rid},
            )

        prim_ids = [p["id"] for p in skill.primitives]
        all_fvs = await list_all_domain_fvs(auth.org_id, db)

        matrix: dict[str, dict[str, float]] = {}
        for src_id, src_fv in all_fvs.items():
            row: dict[str, float] = {}
            for dst_id, dst_fv in all_fvs.items():
                if src_id == dst_id:
                    row[dst_id] = 1.0
                    continue
                sr = score_skill(
                    primitives=prim_ids,
                    source_domain=src_id,
                    target_domain=dst_id,
                    target_fv=dst_fv,
                    threshold=0.70,
                    blend_base=True,
                    include_matrix=False,
                )
                row[dst_id] = sr.score
            matrix[src_id] = row

        return CompatMatrixResponse(
            type="skill_adjusted",
            skill_id=skill_id,
            matrix=matrix,
            request_id=rid,
        )

    # Base compatibility matrix
    return CompatMatrixResponse(
        type="base",
        skill_id=None,
        matrix=BASE_COMPAT_MATRIX,
        request_id=rid,
    )


# ── POST /domains/register ───────────────────────────────────────────
@router.post("/register", response_model=DomainResponse, status_code=201)
async def register_domain(
    body: DomainRegisterRequest,
    request: Request,
    auth: AuthContext = Depends(require_write),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id

    # Reject if clashes with built-in domain id
    if is_built_in(body.id):
        raise HTTPException(
            409,
            {
                "error": "DOMAIN_EXISTS",
                "message": f'"{body.id}" is a built-in domain id and cannot be registered.',
                "request_id": rid,
            },
        )

    # Check for duplicate within org
    existing = await db.execute(
        select(CustomDomain).where(
            CustomDomain.id == body.id,
            CustomDomain.org_id == auth.org_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            409,
            {
                "error": "DOMAIN_EXISTS",
                "message": f'Domain "{body.id}" already registered for your org.',
                "request_id": rid,
            },
        )

    domain = CustomDomain(
        id=body.id,
        org_id=auth.org_id,
        name=body.name,
        icon=body.icon,
        description=body.description,
        feature_vector=body.feature_vector.model_dump(),
        primitive_impls={
            k: v.model_dump() for k, v in body.primitive_impls.items()
        },
        created_at=_utcnow(),
    )
    db.add(domain)
    await db.flush()

    return _custom_to_response(domain, rid)


# ── GET /domains/{domain_id} ─────────────────────────────────────────
@router.get("/{domain_id}", response_model=DomainResponse)
async def get_domain(
    domain_id: str,
    request: Request,
    auth: AuthContext = Depends(get_auth),
    db: AsyncSession = Depends(get_db),
):
    rid = request.state.request_id

    if is_built_in(domain_id):
        d = get_built_in_domain(domain_id)
        return _builtin_to_response(d, rid)

    result = await db.execute(
        select(CustomDomain).where(
            CustomDomain.id == domain_id,
            CustomDomain.org_id == auth.org_id,
        )
    )
    custom = result.scalar_one_or_none()
    if not custom:
        raise HTTPException(
            404,
            {
                "error": "DOMAIN_NOT_FOUND",
                "message": f'Domain "{domain_id}" not found.',
                "request_id": rid,
            },
        )
    return _custom_to_response(custom, rid)
