"""Integration tests for /v2/domains endpoints."""

import pytest
from httpx import AsyncClient


class TestListDomains:
    async def test_list_includes_built_ins(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/domains")
        assert resp.status_code == 200
        data = resp.json()
        ids = {d["id"] for d in data["items"]}
        for expected in ("robotics_sim", "finance", "medical", "logistics"):
            assert expected in ids

    async def test_list_has_feature_vectors(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/domains")
        data = resp.json()
        for d in data["items"]:
            fv = d["feature_vector"]
            for k in ("temporal", "spatial", "cognitive", "action", "social", "physical"):
                assert k in fv

    async def test_built_in_only_flag(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/domains?built_in_only=true")
        assert resp.status_code == 200
        for d in resp.json()["items"]:
            assert d["built_in"] is True


class TestRegisterDomain:
    async def test_register_custom_domain(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/domains/register", json={
            "id": "test_drone_fleet",
            "name": "Test Drone Fleet",
            "icon": "🚁",
            "feature_vector": {
                "temporal": 0.6, "spatial": 0.95, "cognitive": 0.5,
                "action": 0.88, "social": 0.2, "physical": 0.85,
            },
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "test_drone_fleet"
        assert data["built_in"] is False

    async def test_register_duplicate_rejected(self, authed_client: AsyncClient):
        body = {
            "id": "duplicate_domain_x",
            "name": "Duplicate",
            "feature_vector": {
                "temporal": 0.5, "spatial": 0.5, "cognitive": 0.5,
                "action": 0.5, "social": 0.5, "physical": 0.5,
            },
        }
        await authed_client.post("/v2/domains/register", json=body)
        resp2 = await authed_client.post("/v2/domains/register", json=body)
        assert resp2.status_code == 409
        assert resp2.json()["error"] == "DOMAIN_EXISTS"

    async def test_register_builtin_id_rejected(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/domains/register", json={
            "id": "finance",
            "name": "Finance Copy",
            "feature_vector": {
                "temporal": 0.5, "spatial": 0.5, "cognitive": 0.5,
                "action": 0.5, "social": 0.5, "physical": 0.5,
            },
        })
        assert resp.status_code == 409

    async def test_register_invalid_id_format(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/domains/register", json={
            "id": "Bad-ID-With-Caps",
            "name": "Bad",
            "feature_vector": {
                "temporal": 0.5, "spatial": 0.5, "cognitive": 0.5,
                "action": 0.5, "social": 0.5, "physical": 0.5,
            },
        })
        assert resp.status_code == 422

    async def test_register_fv_out_of_range_rejected(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/domains/register", json={
            "id": "bad_fv_domain",
            "name": "Bad FV",
            "feature_vector": {
                "temporal": 1.5,  # > 1.0 — invalid
                "spatial": 0.5, "cognitive": 0.5,
                "action": 0.5, "social": 0.5, "physical": 0.5,
            },
        })
        assert resp.status_code == 422


class TestCompatMatrix:
    async def test_base_matrix_has_all_domains(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/domains/compat")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "base"
        for src in ("robotics_sim", "finance", "game_ai"):
            assert src in data["matrix"]

    async def test_base_matrix_diagonal_is_one(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/domains/compat")
        matrix = resp.json()["matrix"]
        for domain in ("robotics_sim", "finance", "medical"):
            assert matrix[domain][domain] == pytest.approx(1.0, abs=0.01)

    async def test_skill_adjusted_matrix(self, authed_client: AsyncClient):
        # Extract a skill first
        extract_resp = await authed_client.post("/v2/skills/extract", json={
            "task": "Compat matrix test task description",
            "source_domain": "robotics_sim",
            "episodes": 200,
        })
        skill_id = extract_resp.json()["skill_id"]

        resp = await authed_client.get(f"/v2/domains/compat?skill_id={skill_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "skill_adjusted"
        assert data["skill_id"] == skill_id
        assert len(data["matrix"]) >= 8

    async def test_matrix_values_in_range(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/domains/compat")
        for src, row in resp.json()["matrix"].items():
            for tgt, val in row.items():
                assert 0.0 <= val <= 1.0, f"BCM[{src}][{tgt}] = {val} out of range"
