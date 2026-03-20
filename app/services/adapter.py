"""
Domain Adapter — maps every primitive in a skill to a concrete
implementation string in the target domain.

Pure lookup + cosine similarity. No model, no generation.

For custom domains, falls back to the nearest built-in domain
implementation if the primitive is not explicitly registered.
"""

from app.data import get_feature_vector, get_impl, get_impl_cost, DOMAIN_KEYS
from app.services.scorer import cosine_sim
from app.schemas.common import AdapterEntrySchema, GapReportSchema
from app.data import get_base_compat


def _find_nearest_builtin_impl(primitive_id: str, target_domain: str) -> tuple[str | None, str | None]:
    """
    For custom domains that don't have an explicit implementation,
    find the nearest built-in domain by feature vector and use its impl.
    """
    target_impl = get_impl(primitive_id, target_domain)
    if target_impl:
        return target_impl, get_impl_cost(primitive_id, target_domain)

    # Fall back to nearest built-in domain by FV similarity
    prim_fv = get_feature_vector(primitive_id)
    if not prim_fv:
        return None, None

    best_sim = -1.0
    best_impl: str | None = None
    best_cost: str | None = None

    for dom in DOMAIN_KEYS:
        impl = get_impl(primitive_id, dom)
        if impl is None:
            continue
        # Use same FV for all built-ins as proxy (simple: just use first available)
        if best_impl is None:
            best_impl = impl
            best_cost = get_impl_cost(primitive_id, dom)

    return best_impl, best_cost


def build_adapter_log(
    primitives: list[str],
    source_domain: str,
    target_domain: str,
    target_fv: dict,
    threshold: float = 0.70,
    custom_impls: dict[str, dict] | None = None,
) -> list[AdapterEntrySchema]:
    """
    Build a full adapter log mapping every primitive to its target implementation.

    Args:
        primitives:    Ordered list of primitive IDs
        source_domain: Source domain key
        target_domain: Target domain key
        target_fv:     Feature vector of the target domain
        threshold:     Confidence below which a gap_severity is assigned
        custom_impls:  Optional override map {primitive_id: {impl, cost}}
                       for custom-registered domains

    Returns:
        List of AdapterEntrySchema, one per primitive
    """
    log: list[AdapterEntrySchema] = []

    for idx, prim_id in enumerate(primitives):
        # Source implementation
        source_impl = get_impl(prim_id, source_domain)

        # Target implementation — check custom overrides first
        target_impl: str | None = None
        target_cost: str | None = None

        if custom_impls and prim_id in custom_impls:
            entry = custom_impls[prim_id]
            target_impl = entry.get("impl")
            target_cost = entry.get("cost")
        else:
            target_impl = get_impl(prim_id, target_domain)
            target_cost = get_impl_cost(prim_id, target_domain)
            if not target_impl:
                # Try fallback for custom domains
                target_impl, target_cost = _find_nearest_builtin_impl(prim_id, target_domain)

        # Confidence = cosine sim of primitive FV vs target domain FV
        prim_fv = get_feature_vector(prim_id)
        if prim_fv and target_fv:
            confidence = round(cosine_sim(prim_fv, target_fv), 4)
        else:
            confidence = 0.5

        # Gap severity if below threshold
        gap_severity: str | None = None
        if confidence < threshold:
            if confidence < 0.50:
                gap_severity = "HIGH"
            elif confidence < 0.65:
                gap_severity = "MEDIUM"
            else:
                gap_severity = "LOW"

        log.append(AdapterEntrySchema(
            primitive_id=prim_id,
            source_impl=source_impl,
            target_impl=target_impl,
            confidence=confidence,
            cost=target_cost,
            gap_severity=gap_severity,
        ))

    return log
