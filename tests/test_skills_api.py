"""Integration tests for /v2/skills endpoints."""

import pytest
from httpx import AsyncClient


# ── Helpers ──────────────────────────────────────────────────────────

async def _extract(client: AsyncClient, task: str = "Sort packages on a conveyor belt", domain: str = "robotics_sim") -> dict:
    resp = await client.post("/v2/skills/extract", json={
        "task": task,
        "source_domain": domain,
        "episodes": 500,
        "depth": "standard",
        "edge_cases": True,
        "rollback": True,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestExtractSkill:
    async def test_extract_returns_skill_object(self, authed_client: AsyncClient):
        data = await _extract(authed_client)
        assert data["skill_id"].startswith("sk_")
        assert data["name"] == "Sort packages on a conveyor belt"
        assert data["version"] == "2.0.0"
        assert data["source_domain"] == "robotics_sim"
        assert "primitives" in data and len(data["primitives"]) > 0
        assert "feature_vector" in data
        assert "transferability" in data
        assert 0.0 <= data["transferability"] <= 1.0
        assert data["rollback_token"].startswith("rb_")

    async def test_extract_requires_auth(self, client: AsyncClient):
        resp = await client.post("/v2/skills/extract", json={
            "task": "Test task description",
            "source_domain": "finance",
            "episodes": 100,
        })
        assert resp.status_code == 401

    async def test_extract_task_too_short(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/skills/extract", json={
            "task": "short",
            "source_domain": "finance",
            "episodes": 100,
        })
        assert resp.status_code == 422

    async def test_extract_unknown_domain(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/skills/extract", json={
            "task": "A valid task description here",
            "source_domain": "unknown_domain_xyz",
            "episodes": 100,
        })
        assert resp.status_code == 422
        assert resp.json()["error"] == "DOMAIN_UNKNOWN"

    async def test_extract_invalid_depth(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/skills/extract", json={
            "task": "A valid task description here",
            "source_domain": "finance",
            "depth": "ultra_deep",
            "episodes": 100,
        })
        assert resp.status_code == 422

    async def test_extract_no_rollback(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/skills/extract", json={
            "task": "Detect anomalous trading patterns in real time",
            "source_domain": "finance",
            "episodes": 200,
            "rollback": False,
        })
        assert resp.status_code == 200
        assert resp.json()["rollback_token"] is None

    async def test_large_episodes_returns_202(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/skills/extract", json={
            "task": "Large episode extraction test task description",
            "source_domain": "robotics_sim",
            "episodes": 5000,   # above async threshold
        })
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["job_id"].startswith("job_")
        assert "poll_url" in data


class TestGetSkill:
    async def test_get_existing_skill(self, authed_client: AsyncClient):
        extracted = await _extract(authed_client, "Analyse and execute medical diagnostic")
        skill_id = extracted["skill_id"]

        resp = await authed_client.get(f"/v2/skills/{skill_id}")
        assert resp.status_code == 200
        assert resp.json()["skill_id"] == skill_id

    async def test_get_nonexistent_returns_404(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/skills/sk_00000000")
        assert resp.status_code == 404
        assert resp.json()["error"] == "SKILL_NOT_FOUND"


class TestListSkills:
    async def test_list_returns_paginated(self, authed_client: AsyncClient):
        # Ensure at least one skill exists
        await _extract(authed_client, "List test task alpha beta gamma")

        resp = await authed_client.get("/v2/skills?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    async def test_list_filter_by_domain(self, authed_client: AsyncClient):
        await _extract(authed_client, "Finance skill listing test", domain="finance")
        resp = await authed_client.get("/v2/skills?domain=finance&limit=20")
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["source_domain"] == "finance"


class TestSkillGraph:
    async def test_get_graph_returns_nodes_and_edges(self, authed_client: AsyncClient):
        extracted = await _extract(authed_client, "Route vehicles through a logistics hub")
        skill_id = extracted["skill_id"]

        resp = await authed_client.get(f"/v2/skills/{skill_id}/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert data["schema_version"] == "uskill-graph/v2"
        assert data["cycles"] == 0
        assert len(data["nodes"]) > 0


class TestScoreSkill:
    async def test_score_returns_compat_score(self, authed_client: AsyncClient):
        extracted = await _extract(authed_client, "Detect and classify incoming signals")
        skill_id = extracted["skill_id"]

        resp = await authed_client.post(f"/v2/skills/{skill_id}/score", json={
            "target_domain": "finance",
            "threshold": 0.65,
            "blend_base": True,
            "include_matrix": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "score" in data
        assert 0.0 <= data["score"] <= 1.0
        assert "sub_scores" in data
        assert "gaps" in data
        assert "matrix_row" in data
        assert len(data["matrix_row"]) == 8

    async def test_score_without_matrix(self, authed_client: AsyncClient):
        extracted = await _extract(authed_client, "Plan and execute delivery route optimisation")
        skill_id = extracted["skill_id"]

        resp = await authed_client.post(f"/v2/skills/{skill_id}/score", json={
            "target_domain": "game_ai",
            "include_matrix": False,
        })
        assert resp.status_code == 200
        assert resp.json()["matrix_row"] is None

    async def test_score_unknown_domain_rejected(self, authed_client: AsyncClient):
        extracted = await _extract(authed_client, "Score test with bad domain description")
        skill_id = extracted["skill_id"]

        resp = await authed_client.post(f"/v2/skills/{skill_id}/score", json={
            "target_domain": "bad_domain_xyz",
        })
        assert resp.status_code == 422


class TestTransferSkill:
    async def test_transfer_returns_result(self, authed_client: AsyncClient):
        extracted = await _extract(authed_client, "Detect and rank anomalous sensor readings")
        skill_id = extracted["skill_id"]

        resp = await authed_client.post(f"/v2/skills/{skill_id}/transfer", json={
            "destination_domain": "medical",
            "allow_partial": True,
            "dry_run": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["transfer_id"].startswith("tr_")
        assert data["skill_id"] == skill_id
        assert data["destination_domain"] == "medical"
        assert data["status"] in ("INJECTED", "PARTIAL", "REJECTED")

    async def test_transfer_dry_run_not_persisted(self, authed_client: AsyncClient):
        extracted = await _extract(authed_client, "Execute sequence of warehouse pick operations")
        skill_id = extracted["skill_id"]

        resp = await authed_client.post(f"/v2/skills/{skill_id}/transfer", json={
            "destination_domain": "logistics",
            "dry_run": True,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "DRY_RUN"

    async def test_transfer_missing_destination_rejected(self, authed_client: AsyncClient):
        extracted = await _extract(authed_client, "Transfer test missing destination domain")
        skill_id = extracted["skill_id"]

        resp = await authed_client.post(f"/v2/skills/{skill_id}/transfer", json={})
        assert resp.status_code == 422


class TestRollbackSkill:
    async def test_rollback_succeeds(self, authed_client: AsyncClient):
        extracted = await _extract(authed_client, "Rollback test — transfer and reverse")
        skill_id = extracted["skill_id"]
        rollback_token = extracted["rollback_token"]

        # Transfer first
        await authed_client.post(f"/v2/skills/{skill_id}/transfer", json={
            "destination_domain": "game_ai",
        })

        resp = await authed_client.post(f"/v2/skills/{skill_id}/rollback", json={
            "rollback_token": rollback_token,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ROLLED_BACK"

    async def test_rollback_wrong_token_rejected(self, authed_client: AsyncClient):
        extracted = await _extract(authed_client, "Wrong token rollback test task here")
        skill_id = extracted["skill_id"]

        resp = await authed_client.post(f"/v2/skills/{skill_id}/rollback", json={
            "rollback_token": "rb_badtoken00",
        })
        assert resp.status_code == 401

    async def test_rollback_used_twice_rejected(self, authed_client: AsyncClient):
        extracted = await _extract(authed_client, "Double rollback test task description here")
        skill_id = extracted["skill_id"]
        token = extracted["rollback_token"]

        await authed_client.post(f"/v2/skills/{skill_id}/rollback", json={"rollback_token": token})
        resp2 = await authed_client.post(f"/v2/skills/{skill_id}/rollback", json={"rollback_token": token})
        assert resp2.status_code == 409
        assert resp2.json()["error"] == "TOKEN_USED"


class TestRefineSkill:
    async def test_refine_returns_new_skill(self, authed_client: AsyncClient):
        extracted = await _extract(authed_client, "Refine test — improve skill with more episodes")
        skill_id = extracted["skill_id"]

        resp = await authed_client.put(f"/v2/skills/{skill_id}/refine", json={
            "additional_episodes": 200,
            "merge_strategy": "weighted_avg",
            "bump_version": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_skill_id"] != skill_id
        assert data["previous_skill_id"] == skill_id
        assert data["version"] == "2.1.0"
        assert "delta" in data


class TestValidateSkill:
    async def test_valid_skill_object(self, authed_client: AsyncClient):
        extracted = await _extract(authed_client, "Validate this skill object structure test")
        resp = await authed_client.post("/v2/skills/validate", json={"skill": extracted})
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    async def test_missing_required_field(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/skills/validate", json={"skill": {"name": "incomplete"}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        fields = [e["field"] for e in data["errors"]]
        assert "skill_id" in fields

    async def test_bad_skill_id_format(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/skills/validate", json={"skill": {
            "skill_id": "bad_format",
            "name": "test",
            "source_domain": "finance",
            "primitives": [],
        }})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False


class TestBatchExtract:
    async def test_batch_returns_job_id(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/skills/batch", json={
            "jobs": [
                {"task": "Sort packages on conveyor belt alpha", "source_domain": "robotics_sim", "target_domain": "logistics"},
                {"task": "Analyse signal patterns in financial data", "source_domain": "finance", "target_domain": "software_dev"},
            ]
        })
        assert resp.status_code == 202
        data = resp.json()
        assert data["batch_id"].startswith("bat_")
        assert data["job_count"] == 2
        assert "/v2/jobs/" in data["poll_url"]

    async def test_batch_empty_rejected(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/skills/batch", json={"jobs": []})
        assert resp.status_code == 422


class TestDeleteSkill:
    async def test_delete_returns_204(self, authed_client: AsyncClient):
        extracted = await _extract(authed_client, "Delete test skill task description here")
        skill_id = extracted["skill_id"]

        resp = await authed_client.delete(f"/v2/skills/{skill_id}?force=true")
        assert resp.status_code == 204

    async def test_deleted_skill_not_found(self, authed_client: AsyncClient):
        extracted = await _extract(authed_client, "Delete and get test skill task")
        skill_id = extracted["skill_id"]

        await authed_client.delete(f"/v2/skills/{skill_id}?force=true")
        resp = await authed_client.get(f"/v2/skills/{skill_id}")
        assert resp.status_code == 404
