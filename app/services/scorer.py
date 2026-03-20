"""
Compatibility Scorer — the heart of USKill.

No model. No randomness. Pure math:
  1. Retrieve the 6D feature vector for every primitive in the skill
  2. Compute cosine similarity against the target domain's 6D vector
  3. Weight by position (first 3 = HIGH, 4-6 = MEDIUM, 7+ = LOW)
  4. Blend with the Base Compatibility Matrix (60% cosine / 40% BCM)
  5. Compute per-category sub-scores
  6. Build gap report for primitives below threshold
  7. Optionally compute full NxN skill-adjusted matrix
"""

import math
from typing import NamedTuple

from app.data import (
    get_feature_vector, get_category, get_base_compat,
    BUILT_IN_DOMAINS, BUILT_IN_DOMAIN_BY_ID, DOMAIN_KEYS,
)
from app.schemas.common import (
    SubScoresSchema, GapReportSchema, AdapterEntrySchema,
)


_FV = dict[str, float]
_FEATURE_KEYS = ["temporal", "spatial", "cognitive", "action", "social", "physical"]


def _norm(v: _FV) -> float:
    return math.sqrt(sum(v[k] ** 2 for k in _FEATURE_KEYS))


def cosine_sim(a: _FV, b: _FV) -> float:
    """Cosine similarity between two 6D feature vectors. Returns [0, 1]."""
    dot = sum(a[k] * b[k] for k in _FEATURE_KEYS)
    na, nb = _norm(a), _norm(b)
    if na == 0 or nb == 0:
        return 0.0
    raw = dot / (na * nb)
    # Clamp to [0, 1] — negative cosine means orthogonal/opposite, treat as 0
    return max(0.0, min(1.0, raw))


def _criticality_weight(idx: int, use_criticality: bool = True) -> float:
    if not use_criticality:
        return 1.0
    if idx < 3:
        return 1.0
    if idx < 6:
        return 0.8
    return 0.6


def _criticality_label(idx: int) -> str:
    if idx < 3:
        return "HIGH"
    if idx < 6:
        return "MEDIUM"
    return "LOW"


def _severity(sim: float) -> str:
    if sim < 0.50:
        return "HIGH"
    if sim < 0.65:
        return "MEDIUM"
    return "LOW"


def _remediation(severity: str) -> str:
    return {
        "HIGH": "BRIDGE",
        "MEDIUM": "SUBSTITUTE",
        "LOW": "BEST_EFFORT",
    }.get(severity, "BEST_EFFORT")


class ScoreResult(NamedTuple):
    score: float
    sub_scores: SubScoresSchema
    gaps: list[GapReportSchema]
    matrix_row: dict[str, float] | None


def score_skill(
    primitives: list[str],
    source_domain: str,
    target_domain: str,
    target_fv: _FV,
    threshold: float = 0.70,
    blend_base: bool = True,
    include_matrix: bool = True,
    all_domain_fvs: dict[str, _FV] | None = None,
) -> ScoreResult:
    """
    Score a list of primitive IDs against a target domain.

    Args:
        primitives:       Ordered list of primitive IDs (first = highest weight)
        source_domain:    Domain key of the skill's origin
        target_domain:    Domain key we are scoring against
        target_fv:        Feature vector for the target domain
        threshold:        Sims below this are flagged as gaps
        blend_base:       If True, blend 60% cosine + 40% BCM base score
        include_matrix:   Compute full matrix row across all domains
        all_domain_fvs:   Precomputed {domain_id → feature_vector} for matrix

    Returns:
        ScoreResult with score, sub_scores, gaps, matrix_row
    """
    # ── Per-primitive scoring ────────────────────────────────────────
    cat_sims: dict[str, list[float]] = {
        "PERCEPTION": [], "COGNITION": [], "ACTION": [],
        "CONTROL": [], "COMMUNICATION": [], "LEARNING": [],
    }
    weighted_sum = 0.0
    weight_total = 0.0
    gaps: list[GapReportSchema] = []

    for idx, prim_id in enumerate(primitives):
        prim_fv = get_feature_vector(prim_id)
        if prim_fv is None:
            continue  # unknown primitive — skip gracefully

        sim = cosine_sim(prim_fv, target_fv)
        w = _criticality_weight(idx)
        weighted_sum += sim * w
        weight_total += w

        category = get_category(prim_id) or "PERCEPTION"
        cat_sims.setdefault(category, []).append(sim)

        if sim < threshold:
            from app.data import get_impl
            source_impl = get_impl(prim_id, source_domain)
            target_impl = get_impl(prim_id, target_domain)
            sev = _severity(sim)
            gaps.append(GapReportSchema(
                primitive_id=prim_id,
                source_impl=source_impl,
                target_impl=target_impl,
                similarity=round(sim, 4),
                severity=sev,
                criticality=_criticality_label(idx),
                remediation=_remediation(sev),
            ))

    # ── Final score ──────────────────────────────────────────────────
    raw = (weighted_sum / weight_total) if weight_total > 0 else 0.5
    base = get_base_compat(source_domain, target_domain)
    if blend_base:
        final = round(min(0.99, raw * 0.60 + base * 0.40), 4)
    else:
        final = round(min(0.99, raw), 4)

    # ── Sub-scores per category ──────────────────────────────────────
    def _avg(vals: list[float]) -> float:
        return round(sum(vals) / len(vals), 4) if vals else round(final, 4)

    sub = SubScoresSchema(
        PERCEPTION=_avg(cat_sims["PERCEPTION"]),
        COGNITION=_avg(cat_sims["COGNITION"]),
        ACTION=_avg(cat_sims["ACTION"]),
        CONTROL=_avg(cat_sims["CONTROL"]),
        COMMUNICATION=_avg(cat_sims["COMMUNICATION"]),
        LEARNING=_avg(cat_sims["LEARNING"]),
    )

    # ── Full matrix row (optional) ───────────────────────────────────
    matrix_row: dict[str, float] | None = None
    if include_matrix and all_domain_fvs:
        matrix_row = {}
        for dom_id, dom_fv in all_domain_fvs.items():
            dom_raw = 0.0
            dom_w = 0.0
            for idx2, prim_id in enumerate(primitives):
                pv = get_feature_vector(prim_id)
                if pv is None:
                    continue
                s = cosine_sim(pv, dom_fv)
                ww = _criticality_weight(idx2)
                dom_raw += s * ww
                dom_w += ww
            dom_score = (dom_raw / dom_w) if dom_w > 0 else 0.5
            dom_base = get_base_compat(source_domain, dom_id)
            if blend_base:
                cell = min(0.99, dom_score * 0.60 + dom_base * 0.40)
            else:
                cell = min(0.99, dom_score)
            matrix_row[dom_id] = round(cell, 4)

    return ScoreResult(
        score=final,
        sub_scores=sub,
        gaps=gaps,
        matrix_row=matrix_row,
    )
