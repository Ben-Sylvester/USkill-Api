"""
Tests for production hardening additions:
  - Input sanitisation (security.py)
  - API key listing + rotation + revocation
  - Connection status transitions (PATCH)
  - /health deep check
  - Webhook outbox scheduling
"""

import pytest
from httpx import AsyncClient


# ── Security / input sanitisation ──────────────────────────────────────

class TestInputSanitisation:
    async def test_html_in_task_rejected(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/skills/extract", json={
            "task": "<script>alert(1)</script> do something with robotics",
            "source_domain": "robotics_sim",
            "episodes": 100,
        })
        assert resp.status_code == 422
        assert resp.json()["error"] == "INVALID_INPUT"

    async def test_html_in_connection_name_rejected(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/connections", json={
            "name": "<b>Hack</b>",
            "source_domain": "robotics_sim",
            "destination_domain": "finance",
        })
        assert resp.status_code == 422
        assert resp.json()["error"] == "INVALID_INPUT"

    async def test_clean_task_passes(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/skills/extract", json={
            "task": "Analyse logistics routing for warehouse management system",
            "source_domain": "logistics",
            "episodes": 100,
        })
        assert resp.status_code == 200

    async def test_oversized_task_rejected(self, authed_client: AsyncClient):
        # Pydantic enforces max_length=2000 before sanitise_text even runs.
        # This test validates the 422 is returned — the error code will be
        # INVALID_REQUEST (Pydantic) or INPUT_TOO_LARGE (sanitise_text)
        # depending on whether the payload exceeds Pydantic's limit first.
        big = "x" * 2500   # > Pydantic max_length=2000
        resp = await authed_client.post("/v2/skills/extract", json={
            "task": big,
            "source_domain": "logistics",
            "episodes": 100,
        })
        assert resp.status_code == 422
        # Either Pydantic or sanitise_text caught it
        assert resp.json()["error"] in ("INVALID_REQUEST", "INPUT_TOO_LARGE")


# ── API key management ─────────────────────────────────────────────────

class TestApiKeys:
    async def test_list_keys(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/keys")
        assert resp.status_code == 200
        keys = resp.json()
        assert isinstance(keys, list)
        assert len(keys) >= 1
        k = keys[0]
        assert "key_id" in k
        assert "plan" in k
        assert "key_prefix" in k
        # Raw key hash must NOT be present
        assert "key_hash" not in k

    async def test_rotate_key(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/keys/rotate", json={"name": "Rotated"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["raw_key"].startswith("usk_prod_")
        assert data["new_key_id"].startswith("key_")
        assert "revoked_key_id" in data
        # The raw key is returned once and must be a full-length key
        assert len(data["raw_key"]) > 20

    async def test_revoke_self_rejected(self, authed_client: AsyncClient):
        # Get our own key id from the list
        keys = (await authed_client.get("/v2/keys")).json()
        own_id = keys[0]["key_id"]
        resp = await authed_client.delete(f"/v2/keys/{own_id}")
        assert resp.status_code == 409
        assert resp.json()["error"] == "CANNOT_REVOKE_SELF"

    async def test_revoke_nonexistent_key(self, authed_client: AsyncClient):
        resp = await authed_client.delete("/v2/keys/key_nonexistent")
        assert resp.status_code == 404


# ── Connection status transitions ─────────────────────────────────────

class TestConnectionStatus:
    async def _create_conn(self, client: AsyncClient) -> str:
        resp = await client.post("/v2/connections", json={
            "name": "Status Test Connection",
            "source_domain": "software_dev",
            "destination_domain": "education",
        })
        assert resp.status_code == 201
        return resp.json()["connection_id"]

    async def test_pause_active_connection(self, authed_client: AsyncClient):
        conn_id = await self._create_conn(authed_client)
        resp = await authed_client.patch(
            f"/v2/connections/{conn_id}/status",
            json={"status": "paused"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    async def test_resume_paused_connection(self, authed_client: AsyncClient):
        conn_id = await self._create_conn(authed_client)
        await authed_client.patch(f"/v2/connections/{conn_id}/status", json={"status": "paused"})
        resp = await authed_client.patch(
            f"/v2/connections/{conn_id}/status",
            json={"status": "active"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    async def test_archive_connection(self, authed_client: AsyncClient):
        conn_id = await self._create_conn(authed_client)
        resp = await authed_client.patch(
            f"/v2/connections/{conn_id}/status",
            json={"status": "archived"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    async def test_cannot_unarchive(self, authed_client: AsyncClient):
        conn_id = await self._create_conn(authed_client)
        await authed_client.patch(f"/v2/connections/{conn_id}/status", json={"status": "archived"})
        resp = await authed_client.patch(
            f"/v2/connections/{conn_id}/status",
            json={"status": "active"},
        )
        assert resp.status_code == 409
        assert resp.json()["error"] == "INVALID_TRANSITION"

    async def test_same_status_rejected(self, authed_client: AsyncClient):
        conn_id = await self._create_conn(authed_client)
        resp = await authed_client.patch(
            f"/v2/connections/{conn_id}/status",
            json={"status": "active"},   # already active
        )
        assert resp.status_code == 409
        assert resp.json()["error"] == "INVALID_TRANSITION"

    async def test_invalid_status_value(self, authed_client: AsyncClient):
        conn_id = await self._create_conn(authed_client)
        resp = await authed_client.patch(
            f"/v2/connections/{conn_id}/status",
            json={"status": "destroyed"},
        )
        assert resp.status_code == 422

    async def test_sync_paused_connection_blocked(self, authed_client: AsyncClient):
        conn_id = await self._create_conn(authed_client)
        await authed_client.patch(f"/v2/connections/{conn_id}/status", json={"status": "paused"})
        resp = await authed_client.post(f"/v2/connections/{conn_id}/sync", json={
            "task": "This should be blocked by paused status check here",
            "episodes": 100,
        })
        assert resp.status_code == 409
        assert resp.json()["error"] == "CONNECTION_PAUSED"


# ── Health endpoint ────────────────────────────────────────────────────

class TestHealthDeep:
    async def test_health_returns_checks(self, client: AsyncClient):
        resp = await client.get("/health")
        # 200 in test env (APP_ENV=test override) or 503 if postgres not available
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "checks" in data
        assert "version" in data
        assert "environment" in data

    async def test_health_has_database_check(self, client: AsyncClient):
        resp = await client.get("/health")
        data = resp.json()
        assert "database" in data["checks"]
        assert data["checks"]["database"]["status"] in ("ok", "error")

    async def test_health_has_redis_check(self, client: AsyncClient):
        resp = await client.get("/health")
        data = resp.json()
        assert "redis" in data["checks"]
        # Redis will be degraded in test env (no redis running) — that's fine
        assert data["checks"]["redis"]["status"] in ("ok", "degraded")
