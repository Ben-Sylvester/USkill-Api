"""Tests for system endpoints — health, primitives, jobs."""

import pytest
from httpx import AsyncClient


class TestHealth:
    async def test_health_no_auth(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    async def test_root_no_auth(self, client: AsyncClient):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "USKill" in resp.json()["name"]

    async def test_unknown_route_404(self, client: AsyncClient):
        resp = await client.get("/v2/nonexistent_endpoint")
        assert resp.status_code == 404
        assert resp.json()["error"] == "NOT_FOUND"


class TestPrimitives:
    async def test_list_all_primitives(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/primitives")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 48
        assert len(data["primitives"]) == 48
        assert len(data["categories"]) == 6

    async def test_filter_by_category(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/primitives?category=PERCEPTION")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8
        for p in data["primitives"]:
            assert p["category"] == "PERCEPTION"

    async def test_filter_invalid_category(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/primitives?category=INVALID")
        assert resp.status_code == 422

    async def test_get_single_primitive(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/primitives/sense_state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "sense_state"
        assert data["category"] == "PERCEPTION"
        assert "features" in data
        assert "domains" in data

    async def test_unknown_primitive_404(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/primitives/nonexistent_prim")
        assert resp.status_code == 404

    async def test_primitives_require_auth(self, client: AsyncClient):
        resp = await client.get("/v2/primitives")
        assert resp.status_code == 401

    async def test_all_primitives_have_6d_feature_vector(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/primitives")
        for p in resp.json()["primitives"]:
            fv = p["features"]
            for k in ("temporal", "spatial", "cognitive", "action", "social", "physical"):
                assert k in fv, f"Primitive {p['id']} missing feature {k}"
                assert 0.0 <= fv[k] <= 1.0


class TestJobs:
    async def test_get_nonexistent_job(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/jobs/job_00000000")
        assert resp.status_code == 404
        assert resp.json()["error"] == "JOB_NOT_FOUND"

    async def test_get_batch_job(self, authed_client: AsyncClient):
        batch_resp = await authed_client.post("/v2/skills/batch", json={
            "jobs": [
                {"task": "Sort logistics packages by weight class", "source_domain": "logistics", "target_domain": "robotics_sim"},
            ]
        })
        job_id = batch_resp.json()["batch_id"]

        resp = await authed_client.get(f"/v2/jobs/{job_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == job_id
        assert data["status"] in ("queued", "running", "complete", "failed")


class TestRequestIDHeader:
    async def test_x_request_id_in_response(self, authed_client: AsyncClient):
        resp = await authed_client.get("/health")
        assert "x-request-id" in resp.headers

    async def test_custom_request_id_echoed(self, authed_client: AsyncClient):
        resp = await authed_client.get("/health", headers={"X-Request-ID": "my-custom-id-123"})
        assert resp.headers["x-request-id"] == "my-custom-id-123"

    async def test_x_api_version_header(self, authed_client: AsyncClient):
        resp = await authed_client.get("/health")
        assert resp.headers.get("x-api-version") == "2"
