"""
Domain Resolver — single place to look up domain metadata regardless of
whether the domain is built-in or custom-registered by the org.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data import BUILT_IN_DOMAIN_BY_ID, BUILT_IN_DOMAINS, is_built_in
from app.models.domain import CustomDomain


async def resolve_domain_fv(
    domain_id: str,
    org_id: str,
    db: AsyncSession,
) -> dict[str, float] | None:
    """
    Return feature vector for domain_id. Checks built-ins first, then org custom domains.
    Returns None if domain not found.
    """
    if is_built_in(domain_id):
        return BUILT_IN_DOMAIN_BY_ID[domain_id]["feature_vector"]

    result = await db.execute(
        select(CustomDomain).where(
            CustomDomain.id == domain_id,
            CustomDomain.org_id == org_id,
        )
    )
    custom = result.scalar_one_or_none()
    if custom:
        return custom.feature_vector
    return None


async def resolve_domain_impls(
    domain_id: str,
    org_id: str,
    db: AsyncSession,
) -> dict[str, dict] | None:
    """
    Return primitive_impls map for a custom domain.
    Returns None for built-in domains (they use the hardcoded data).
    """
    if is_built_in(domain_id):
        return None  # built-ins handled by data/primitives.py

    result = await db.execute(
        select(CustomDomain).where(
            CustomDomain.id == domain_id,
            CustomDomain.org_id == org_id,
        )
    )
    custom = result.scalar_one_or_none()
    if custom:
        return custom.primitive_impls
    return None


async def domain_exists(domain_id: str, org_id: str, db: AsyncSession) -> bool:
    if is_built_in(domain_id):
        return True
    result = await db.execute(
        select(CustomDomain.id).where(
            CustomDomain.id == domain_id,
            CustomDomain.org_id == org_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def list_all_domain_fvs(
    org_id: str,
    db: AsyncSession,
) -> dict[str, dict[str, float]]:
    """All domain feature vectors for this org (built-ins + custom)."""
    fvs: dict[str, dict[str, float]] = {
        d["id"]: d["feature_vector"] for d in BUILT_IN_DOMAINS
    }
    result = await db.execute(
        select(CustomDomain).where(CustomDomain.org_id == org_id)
    )
    for custom in result.scalars():
        fvs[custom.id] = custom.feature_vector
    return fvs
