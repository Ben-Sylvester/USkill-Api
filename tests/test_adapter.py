"""Unit tests for app/services/adapter.py — pure lookup, no DB."""

import pytest

from app.services.adapter import build_adapter_log
from app.data import BUILT_IN_DOMAIN_BY_ID


class TestBuildAdapterLog:
    def _fv(self, domain_id: str) -> dict:
        return BUILT_IN_DOMAIN_BY_ID[domain_id]["feature_vector"]

    def test_returns_one_entry_per_primitive(self):
        prims = ["sense_state", "apply_force", "plan_sequence"]
        fv = self._fv("finance")
        log = build_adapter_log(prims, "robotics_sim", "finance", fv)
        assert len(log) == 3

    def test_entry_has_all_fields(self):
        log = build_adapter_log(["sense_state"], "robotics_sim", "finance", self._fv("finance"))
        entry = log[0]
        assert entry.primitive_id == "sense_state"
        assert entry.source_impl is not None     # robotics_sim has impl
        assert entry.target_impl is not None     # finance has impl
        assert 0.0 <= entry.confidence <= 1.0
        assert entry.cost is not None

    def test_high_gap_primitive_flagged(self):
        # apply_force vs finance: physical dimension very high in robotics, zero in finance
        fv = self._fv("finance")
        log = build_adapter_log(["apply_force"], "robotics_sim", "finance", fv, threshold=0.70)
        entry = log[0]
        assert entry.gap_severity is not None
        assert entry.gap_severity == "HIGH"

    def test_same_domain_no_gaps(self):
        prims = ["sense_state", "detect_pattern", "plan_sequence"]
        fv = self._fv("robotics_sim")
        log = build_adapter_log(prims, "robotics_sim", "robotics_sim", fv, threshold=0.70)
        gaps = [e for e in log if e.gap_severity is not None]
        assert len(gaps) == 0

    def test_custom_impl_override_used(self):
        custom_impls = {"sense_state": {"impl": "my_sensor.read()", "cost": "1ms"}}
        fv = self._fv("finance")
        log = build_adapter_log(["sense_state"], "robotics_sim", "custom_domain", fv,
                                custom_impls=custom_impls)
        assert log[0].target_impl == "my_sensor.read()"

    def test_confidence_is_deterministic(self):
        fv = self._fv("game_ai")
        log1 = build_adapter_log(["move_to_target"], "robotics_sim", "game_ai", fv)
        log2 = build_adapter_log(["move_to_target"], "robotics_sim", "game_ai", fv)
        assert log1[0].confidence == log2[0].confidence

    def test_unknown_primitive_returns_null_impls(self):
        fv = self._fv("finance")
        log = build_adapter_log(["totally_unknown_prim_xyz"], "robotics_sim", "finance", fv)
        assert log[0].source_impl is None
        assert log[0].target_impl is None
        assert log[0].confidence == 0.5  # fallback

    def test_confidence_range(self):
        prims = ["sense_state", "classify_object", "plan_sequence",
                 "apply_force", "send_message", "update_belief"]
        fv = self._fv("medical")
        log = build_adapter_log(prims, "robotics_sim", "medical", fv)
        for entry in log:
            assert 0.0 <= entry.confidence <= 1.0, f"{entry.primitive_id} confidence out of range"
