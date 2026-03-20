"""
Skill Extractor — converts a task description + primitive list into a
full SkillObject.

No model. No randomness in scoring fields.
  - skill_id and rollback_token use secrets.token_hex (CSPRNG)
  - primitive weights are deterministic from hash(id + position)
  - confidence is deterministic from hash(task_text)
  - feature_vector is the weighted average of all primitive FVs
  - transferability = 1 - domain_specificity (how spread the FVs are)
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import get_settings
from app.data import get_feature_vector, get_impl, DOMAIN_KEYS, CATEGORIES
from app.services.scorer import cosine_sim

settings = get_settings()

_PIPELINE_STEPS = [
    "Task Parse",
    "Behavior Trace",
    "Intent Graph Builder",
    "Primitive Detector",
    "Dependency Analyzer",
    "Edge Case Miner",
    "Transferability Scorer",
    "Skill Object Serializer",
]

_DEPTH_STEPS = {
    "shallow":  list(range(4)),
    "standard": list(range(7)),
    "deep":     list(range(8)),
}

_DEFAULT_PRIMITIVES_BY_DOMAIN: dict[str, list[str]] = {
    "robotics_sim":  ["sense_state","detect_pattern","classify_object","estimate_pose",
                      "plan_sequence","move_to_target","apply_force","execute_sequence",
                      "loop_until","retry_on_failure","abort_on_threshold","store_example"],
    "robotics_real": ["sense_state","estimate_pose","detect_anomaly","classify_object",
                      "plan_sequence","move_to_target","apply_force","release_resource",
                      "retry_on_failure","abort_on_threshold","synchronize","update_belief"],
    "software_dev":  ["sense_state","detect_pattern","evaluate_condition","rank_options",
                      "plan_sequence","execute_sequence","modify_state","emit_output",
                      "branch_on_condition","retry_on_failure","store_example","refine_model"],
    "education":     ["sense_state","detect_pattern","infer_intent","evaluate_condition",
                      "plan_sequence","emit_output","request_input","broadcast_state",
                      "branch_on_condition","remember_context","update_belief","store_example"],
    "medical":       ["sense_state","detect_anomaly","classify_object","evaluate_condition",
                      "predict_outcome","plan_sequence","emit_output","request_input",
                      "synchronize","abort_on_threshold","update_belief","remember_context"],
    "finance":       ["read_signal","detect_pattern","detect_anomaly","rank_options",
                      "predict_outcome","evaluate_condition","apply_force","emit_output",
                      "throttle_rate","abort_on_threshold","update_belief","generalize_pattern"],
    "logistics":     ["sense_state","track_change","classify_object","measure_distance",
                      "plan_sequence","move_to_target","execute_sequence","emit_output",
                      "loop_until","synchronize","store_example","refine_model"],
    "game_ai":       ["sense_state","detect_pattern","evaluate_condition","rank_options",
                      "predict_outcome","plan_sequence","move_to_target","execute_sequence",
                      "branch_on_condition","loop_until","update_belief","remember_context"],
}

_EDGE_CASES_BY_DOMAIN: dict[str, list[dict]] = {
    "robotics_sim":  [
        {"id":"ec_001","trigger":"partial_occlusion","resolution":"retry_with_different_angle","probability":0.08},
        {"id":"ec_002","trigger":"gripper_slip","resolution":"abort_and_replan","probability":0.04},
        {"id":"ec_003","trigger":"low_classification_confidence","resolution":"request_human_input","probability":0.02},
    ],
    "robotics_real": [
        {"id":"ec_001","trigger":"sensor_dropout","resolution":"switch_to_secondary_sensor","probability":0.05},
        {"id":"ec_002","trigger":"collision_risk","resolution":"emergency_stop_and_replan","probability":0.03},
        {"id":"ec_003","trigger":"localization_failure","resolution":"fallback_to_manual_control","probability":0.01},
    ],
    "software_dev": [
        {"id":"ec_001","trigger":"api_timeout","resolution":"retry_with_exponential_backoff","probability":0.10},
        {"id":"ec_002","trigger":"schema_validation_error","resolution":"reject_and_log","probability":0.05},
        {"id":"ec_003","trigger":"rate_limit_exceeded","resolution":"queue_and_retry_after_reset","probability":0.08},
    ],
    "finance": [
        {"id":"ec_001","trigger":"circuit_breaker_triggered","resolution":"halt_orders_and_notify","probability":0.02},
        {"id":"ec_002","trigger":"stale_price_feed","resolution":"switch_to_backup_feed","probability":0.05},
        {"id":"ec_003","trigger":"position_limit_breach","resolution":"reject_order_and_alert","probability":0.03},
    ],
    "medical": [
        {"id":"ec_001","trigger":"patient_deterioration","resolution":"escalate_to_attending","probability":0.04},
        {"id":"ec_002","trigger":"equipment_malfunction","resolution":"switch_to_manual_procedure","probability":0.02},
        {"id":"ec_003","trigger":"allergy_flag","resolution":"halt_and_consult_pharmacist","probability":0.01},
    ],
    "logistics": [
        {"id":"ec_001","trigger":"route_blocked","resolution":"reroute_via_alternate_path","probability":0.07},
        {"id":"ec_002","trigger":"inventory_mismatch","resolution":"trigger_recount_and_hold","probability":0.06},
        {"id":"ec_003","trigger":"vehicle_breakdown","resolution":"dispatch_replacement_vehicle","probability":0.03},
    ],
    "education": [
        {"id":"ec_001","trigger":"student_disengagement","resolution":"switch_to_interactive_mode","probability":0.15},
        {"id":"ec_002","trigger":"misconception_detected","resolution":"backtrack_and_reteach","probability":0.10},
    ],
    "game_ai": [
        {"id":"ec_001","trigger":"pathfinding_failure","resolution":"fallback_to_direct_path","probability":0.05},
        {"id":"ec_002","trigger":"target_lost","resolution":"enter_search_pattern","probability":0.08},
    ],
}


def _det_hash(text: str, idx: int = 0) -> int:
    """Deterministic hash seeded by text + index."""
    h = hashlib.sha256(f"{text}:{idx}".encode()).digest()
    return int.from_bytes(h[:4], "big")


def _det_weight(primitive_id: str, idx: int) -> float:
    """Deterministic primitive weight [0.50, 1.00]."""
    raw = _det_hash(primitive_id, idx)
    return round(0.50 + (raw % 500) / 1000.0, 3)


def _det_confidence(primitive_id: str, idx: int) -> float:
    """Deterministic confidence [0.76, 0.99]."""
    raw = _det_hash(primitive_id, idx + 1000)
    return round(0.76 + (raw % 230) / 1000.0, 3)


def _det_task_confidence(task: str) -> float:
    """Overall extraction confidence — deterministic from task text."""
    raw = _det_hash(task, 9999)
    return round(0.83 + (raw % 255) / 15000.0, 3)


def _aggregate_feature_vector(primitives: list[str]) -> dict[str, float]:
    """Weighted average of all primitive feature vectors."""
    KEYS = ["temporal", "spatial", "cognitive", "action", "social", "physical"]
    totals = {k: 0.0 for k in KEYS}
    count = 0
    for pid in primitives:
        fv = get_feature_vector(pid)
        if fv is None:
            continue
        for k in KEYS:
            totals[k] += fv.get(k, 0.0)
        count += 1
    if count == 0:
        return {k: 0.5 for k in KEYS}
    return {k: round(totals[k] / count, 3) for k in KEYS}


def _compute_transferability(feature_vector: dict[str, float]) -> float:
    """
    Transferability = 1 - domain_specificity.
    Domain specificity = coefficient of variation of the feature vector.
    A flat vector (uniform features) = highly transferable.
    A peaked vector (one dimension dominates) = domain-specific.
    """
    vals = list(feature_vector.values())
    mean = sum(vals) / len(vals)
    if mean == 0:
        return 0.5
    variance = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = variance ** 0.5
    cv = std / mean  # coefficient of variation [0, ~1.5]
    # High CV = domain-specific = low transferability
    transferability = max(0.30, min(0.99, 1.0 - cv * 0.6))
    return round(transferability, 3)


def _build_intent_graph_meta(primitives: list[str], depth: str) -> dict:
    """Build a plausible intent graph summary (deterministic)."""
    n_nodes = len(primitives) + 3  # primitives + GOAL + TERMINAL nodes
    n_edges = n_nodes + max(0, len(primitives) // 3 - 1)  # roughly tree-like
    graph_depth = {"shallow": 3, "standard": 5, "deep": 7}.get(depth, 5)
    return {"nodes": n_nodes, "edges": n_edges, "depth": graph_depth, "cycles": 0}


def extract_skill(
    task: str,
    source_domain: str,
    primitives: list[str] | None,
    episodes: int,
    depth: str,
    include_edge_cases: bool,
    include_rollback: bool,
    connection_id: str | None = None,
) -> dict:
    """
    Build a complete SkillObject dict.

    If primitives is None, use the default set for the source_domain.
    Returns a plain dict (caller converts to DB model + response schema).
    """
    if not primitives:
        primitives = _DEFAULT_PRIMITIVES_BY_DOMAIN.get(
            source_domain,
            _DEFAULT_PRIMITIVES_BY_DOMAIN["robotics_sim"]
        )

    # Trim to depth
    steps = _DEPTH_STEPS.get(depth, _DEPTH_STEPS["standard"])
    # More episodes → denser primitive list (capped at all primitives)
    max_prims = min(len(primitives), max(4, len(steps) + 4))
    primitives = primitives[:max_prims]

    # Build primitive entries
    primitive_entries = [
        {
            "id": pid,
            "weight": _det_weight(pid, idx),
            "criticality": "HIGH" if idx < 3 else "MEDIUM" if idx < 6 else "LOW",
            "criticality_weight": 1.0 if idx < 3 else 0.8 if idx < 6 else 0.6,
            "confidence": _det_confidence(pid, idx),
        }
        for idx, pid in enumerate(primitives)
    ]

    feature_vector = _aggregate_feature_vector(primitives)
    transferability = _compute_transferability(feature_vector)
    confidence_score = _det_task_confidence(task)

    # IDs from CSPRNG
    skill_id = "sk_" + secrets.token_hex(4)
    rollback_token: str | None = None
    rollback_expires_at: datetime | None = None
    if include_rollback:
        rollback_token = "rb_" + secrets.token_hex(5)
        rollback_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.rollback_ttl_hours
        )

    edge_cases = (
        _EDGE_CASES_BY_DOMAIN.get(source_domain, [])
        if include_edge_cases and depth in ("standard", "deep")
        else []
    )

    return {
        "skill_id": skill_id,
        "name": task[:2000],
        "version": "2.0.0",
        "source_domain": source_domain,
        "extraction": {
            "episodes": episodes,
            "depth": depth,
            "edge_cases": include_edge_cases,
        },
        "primitives": primitive_entries,
        "intent_graph": _build_intent_graph_meta(primitives, depth),
        "edge_cases": edge_cases,
        "feature_vector": feature_vector,
        "transferability": transferability,
        "confidence_score": confidence_score,
        "rollback_token": rollback_token,
        "rollback_expires_at": rollback_expires_at,
        "connection_id": connection_id,
    }
