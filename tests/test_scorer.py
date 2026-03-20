"""Unit tests for app/services/scorer.py — pure math, no DB."""

import math
import pytest

from app.services.scorer import cosine_sim, score_skill, _severity, _remediation
from app.data import BUILT_IN_DOMAIN_BY_ID, BUILT_IN_DOMAINS


class TestCosineSim:
    def test_identical_vectors_return_one(self):
        v = {"temporal": 0.5, "spatial": 0.8, "cognitive": 0.6, "action": 0.9, "social": 0.2, "physical": 0.7}
        assert cosine_sim(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_zero_vector_returns_zero(self):
        zero = {"temporal": 0, "spatial": 0, "cognitive": 0, "action": 0, "social": 0, "physical": 0}
        v    = {"temporal": 0.5, "spatial": 0.8, "cognitive": 0.6, "action": 0.9, "social": 0.2, "physical": 0.7}
        assert cosine_sim(zero, v) == 0.0

    def test_orthogonal_vectors_clamp_to_zero(self):
        # One vector has only temporal, other has only spatial
        a = {"temporal": 1.0, "spatial": 0.0, "cognitive": 0.0, "action": 0.0, "social": 0.0, "physical": 0.0}
        b = {"temporal": 0.0, "spatial": 1.0, "cognitive": 0.0, "action": 0.0, "social": 0.0, "physical": 0.0}
        assert cosine_sim(a, b) == 0.0

    def test_result_always_in_zero_one_range(self):
        import random
        random.seed(42)
        for _ in range(50):
            keys = ["temporal", "spatial", "cognitive", "action", "social", "physical"]
            a = {k: random.random() for k in keys}
            b = {k: random.random() for k in keys}
            result = cosine_sim(a, b)
            assert 0.0 <= result <= 1.0, f"cosine_sim out of range: {result}"

    def test_symmetry(self):
        a = {"temporal": 0.3, "spatial": 0.9, "cognitive": 0.5, "action": 0.9, "social": 0.1, "physical": 0.95}
        b = {"temporal": 0.9, "spatial": 0.1, "cognitive": 0.9, "action": 0.7, "social": 0.3, "physical": 0.0}
        assert cosine_sim(a, b) == pytest.approx(cosine_sim(b, a), abs=1e-9)


class TestScoreSkill:
    """Integration of score_skill with real primitive + domain data."""

    def _robotics_prims(self):
        return ["sense_state", "detect_pattern", "classify_object",
                "plan_sequence", "move_to_target", "apply_force",
                "loop_until", "retry_on_failure"]

    def _get_fv(self, domain_id: str) -> dict:
        return BUILT_IN_DOMAIN_BY_ID[domain_id]["feature_vector"]

    def test_same_domain_scores_high(self):
        prims = self._robotics_prims()
        fv = self._get_fv("robotics_sim")
        result = score_skill(prims, "robotics_sim", "robotics_sim", fv, blend_base=True, include_matrix=False)
        assert result.score >= 0.85, f"Same-domain score should be high, got {result.score}"

    def test_score_is_in_range(self):
        prims = self._robotics_prims()
        fv = self._get_fv("finance")
        result = score_skill(prims, "robotics_sim", "finance", fv, blend_base=True, include_matrix=False)
        assert 0.0 <= result.score <= 1.0

    def test_score_is_deterministic(self):
        prims = self._robotics_prims()
        fv = self._get_fv("finance")
        r1 = score_skill(prims, "robotics_sim", "finance", fv, include_matrix=False)
        r2 = score_skill(prims, "robotics_sim", "finance", fv, include_matrix=False)
        assert r1.score == r2.score

    def test_gaps_below_threshold(self):
        prims = ["apply_force", "sense_state"]
        # finance domain has low physical score — apply_force (high physical) should gap
        fv = self._get_fv("finance")
        result = score_skill(prims, "robotics_sim", "finance", fv, threshold=0.70, include_matrix=False)
        gap_ids = {g.primitive_id for g in result.gaps}
        assert "apply_force" in gap_ids, "apply_force vs finance should be a gap"

    def test_sub_scores_all_populated(self):
        prims = ["sense_state", "rank_options", "apply_force",
                 "loop_until", "send_message", "update_belief"]
        fv = self._get_fv("software_dev")
        result = score_skill(prims, "robotics_sim", "software_dev", fv, include_matrix=False)
        sub = result.sub_scores
        # Each category covered — all should be non-zero
        assert sub.PERCEPTION > 0
        assert sub.COGNITION > 0
        assert sub.ACTION > 0
        assert sub.CONTROL > 0
        assert sub.COMMUNICATION > 0
        assert sub.LEARNING > 0

    def test_matrix_row_has_all_domains(self):
        prims = self._robotics_prims()
        all_fvs = {d["id"]: d["feature_vector"] for d in BUILT_IN_DOMAINS}
        fv = self._get_fv("finance")
        result = score_skill(
            prims, "robotics_sim", "finance", fv,
            include_matrix=True, all_domain_fvs=all_fvs,
        )
        assert result.matrix_row is not None
        assert len(result.matrix_row) == 8

    def test_blend_base_vs_no_blend_differ(self):
        prims = self._robotics_prims()
        fv = self._get_fv("finance")
        with_blend    = score_skill(prims, "robotics_sim", "finance", fv, blend_base=True,  include_matrix=False)
        without_blend = score_skill(prims, "robotics_sim", "finance", fv, blend_base=False, include_matrix=False)
        assert with_blend.score != without_blend.score

    def test_unknown_primitive_skipped_gracefully(self):
        prims = ["sense_state", "nonexistent_prim_xyz", "apply_force"]
        fv = self._get_fv("game_ai")
        result = score_skill(prims, "robotics_sim", "game_ai", fv, include_matrix=False)
        assert 0.0 <= result.score <= 1.0

    def test_empty_primitives_returns_base_score(self):
        fv = self._get_fv("logistics")
        result = score_skill([], "robotics_sim", "logistics", fv, blend_base=True, include_matrix=False)
        # With no primitives, score falls back to BCM base value
        from app.data import get_base_compat
        base = get_base_compat("robotics_sim", "logistics")
        assert result.score == pytest.approx(base * 0.40, abs=0.01) or result.score == pytest.approx(0.5 * 0.60 + base * 0.40, abs=0.05)


class TestSeverityAndRemediation:
    def test_high_severity_below_50(self):
        assert _severity(0.49) == "HIGH"
        assert _severity(0.00) == "HIGH"

    def test_medium_severity_50_to_65(self):
        assert _severity(0.50) == "MEDIUM"
        assert _severity(0.64) == "MEDIUM"

    def test_low_severity_65_plus(self):
        assert _severity(0.65) == "LOW"
        assert _severity(0.80) == "LOW"

    def test_remediation_maps_correctly(self):
        assert _remediation("HIGH")   == "BRIDGE"
        assert _remediation("MEDIUM") == "SUBSTITUTE"
        assert _remediation("LOW")    == "BEST_EFFORT"
