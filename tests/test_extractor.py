"""Unit tests for app/services/extractor.py — no DB."""

import re
import pytest

from app.services.extractor import (
    extract_skill, _det_weight, _det_confidence, _det_task_confidence,
    _aggregate_feature_vector, _compute_transferability,
)


SKILL_ID_RE = re.compile(r"^sk_[0-9a-f]{8}$")
ROLLBACK_RE = re.compile(r"^rb_[0-9a-f]{10}$")


class TestExtractSkill:
    def test_returns_valid_structure(self):
        data = extract_skill("Sort packages on a conveyor belt", "robotics_sim", None, 1000, "standard", True, True)
        required = ["skill_id", "name", "version", "source_domain", "extraction",
                    "primitives", "intent_graph", "edge_cases", "feature_vector",
                    "transferability", "confidence_score", "rollback_token"]
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_skill_id_format(self):
        data = extract_skill("Test task description here", "finance", None, 500, "shallow", False, True)
        assert SKILL_ID_RE.match(data["skill_id"]), f"Bad skill_id format: {data['skill_id']}"

    def test_rollback_token_format_when_enabled(self):
        data = extract_skill("Test task description here", "finance", None, 500, "standard", False, True)
        assert data["rollback_token"] is not None
        assert ROLLBACK_RE.match(data["rollback_token"]), f"Bad token format: {data['rollback_token']}"

    def test_rollback_token_none_when_disabled(self):
        data = extract_skill("Test task description here", "finance", None, 500, "standard", False, False)
        assert data["rollback_token"] is None
        assert data["rollback_expires_at"] is None

    def test_shallow_depth_fewer_primitives(self):
        shallow = extract_skill("Navigate to target", "robotics_sim", None, 500, "shallow", False, False)
        standard = extract_skill("Navigate to target", "robotics_sim", None, 500, "standard", False, False)
        assert len(shallow["primitives"]) <= len(standard["primitives"])

    def test_deep_depth_has_edge_cases(self):
        data = extract_skill("Navigate to target", "robotics_sim", None, 1000, "deep", True, False)
        assert len(data["edge_cases"]) > 0

    def test_shallow_no_edge_cases(self):
        data = extract_skill("Navigate to target", "robotics_sim", None, 500, "shallow", True, False)
        # shallow only runs steps 1-4, edge case mining is step 6 — should be empty
        assert data["edge_cases"] == []

    def test_feature_vector_keys(self):
        data = extract_skill("Classify medical images", "medical", None, 1000, "standard", True, False)
        fv = data["feature_vector"]
        for key in ["temporal", "spatial", "cognitive", "action", "social", "physical"]:
            assert key in fv
            assert 0.0 <= fv[key] <= 1.0

    def test_transferability_in_range(self):
        data = extract_skill("Classify medical images", "medical", None, 1000, "standard", False, False)
        assert 0.0 <= data["transferability"] <= 1.0

    def test_confidence_score_deterministic(self):
        task = "Sort and classify inventory items by weight"
        c1 = extract_skill(task, "logistics", None, 1000, "standard", False, False)["confidence_score"]
        c2 = extract_skill(task, "logistics", None, 1000, "standard", False, False)["confidence_score"]
        assert c1 == c2

    def test_two_extractions_have_different_skill_ids(self):
        """CSPRNG — IDs must differ even for identical inputs."""
        d1 = extract_skill("Same task", "finance", None, 500, "shallow", False, True)
        d2 = extract_skill("Same task", "finance", None, 500, "shallow", False, True)
        assert d1["skill_id"] != d2["skill_id"]

    def test_custom_primitives_used(self):
        custom = ["sense_state", "classify_object"]
        data = extract_skill("Custom task here", "education", custom, 200, "shallow", False, False)
        extracted_ids = [p["id"] for p in data["primitives"]]
        for pid in custom:
            assert pid in extracted_ids

    def test_version_is_correct(self):
        data = extract_skill("Test task description here", "game_ai", None, 100, "shallow", False, False)
        assert data["version"] == "2.0.0"

    def test_all_primitive_entries_have_required_fields(self):
        data = extract_skill("Execute trading strategy", "finance", None, 1000, "standard", False, False)
        for p in data["primitives"]:
            assert "id" in p
            assert "weight" in p
            assert "criticality" in p
            assert "criticality_weight" in p
            assert "confidence" in p
            assert p["criticality"] in ("HIGH", "MEDIUM", "LOW")
            assert 0.5 <= p["weight"] <= 1.0
            assert 0.0 <= p["confidence"] <= 1.0

    def test_intent_graph_meta(self):
        data = extract_skill("Plan a surgical procedure", "medical", None, 1000, "standard", False, False)
        ig = data["intent_graph"]
        assert ig["nodes"] > 0
        assert ig["edges"] > 0
        assert ig["cycles"] == 0


class TestDeterministicHelpers:
    def test_det_weight_stable(self):
        w1 = _det_weight("sense_state", 0)
        w2 = _det_weight("sense_state", 0)
        assert w1 == w2

    def test_det_weight_range(self):
        for pid in ["sense_state", "apply_force", "loop_until", "update_belief"]:
            for idx in range(10):
                w = _det_weight(pid, idx)
                assert 0.5 <= w <= 1.0, f"weight out of range for {pid}[{idx}]: {w}"

    def test_det_confidence_stable(self):
        c1 = _det_confidence("detect_pattern", 2)
        c2 = _det_confidence("detect_pattern", 2)
        assert c1 == c2

    def test_det_confidence_range(self):
        for pid in ["detect_pattern", "plan_sequence", "transfer_knowledge"]:
            c = _det_confidence(pid, 0)
            assert 0.76 <= c <= 0.99, f"confidence out of range for {pid}: {c}"

    def test_task_confidence_stable(self):
        task = "Route packages through a warehouse"
        c1 = _det_task_confidence(task)
        c2 = _det_task_confidence(task)
        assert c1 == c2

    def test_task_confidence_range(self):
        for task in ["short", "a much longer task description that goes into detail", ""]:
            c = _det_task_confidence(task)
            assert 0.83 <= c <= 0.999, f"task confidence out of range: {c}"


class TestFeatureVectorHelpers:
    def test_aggregate_returns_six_keys(self):
        fv = _aggregate_feature_vector(["sense_state", "plan_sequence"])
        for k in ["temporal", "spatial", "cognitive", "action", "social", "physical"]:
            assert k in fv

    def test_aggregate_empty_returns_neutral(self):
        fv = _aggregate_feature_vector([])
        for v in fv.values():
            assert v == 0.5

    def test_transferability_uniform_vector_is_high(self):
        # Uniform = no domain specificity = highly transferable
        flat_fv = {"temporal": 0.5, "spatial": 0.5, "cognitive": 0.5,
                   "action": 0.5, "social": 0.5, "physical": 0.5}
        t = _compute_transferability(flat_fv)
        assert t >= 0.90

    def test_transferability_peaked_vector_is_lower(self):
        # Highly physical domain = domain-specific
        peaked = {"temporal": 0.1, "spatial": 0.95, "cognitive": 0.1,
                  "action": 0.95, "social": 0.05, "physical": 0.98}
        t = _compute_transferability(peaked)
        assert t < 0.80
