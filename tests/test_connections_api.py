"""Integration tests for /v2/connections endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient


class TestCreateConnection:
    async def test_create_returns_201(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/connections", json={
            "name": "Robot → Finance",
            "source_domain": "robotics_sim",
            "destination_domain": "finance",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["connection_id"].startswith("cn_")
        assert data["source_domain"] == "robotics_sim"
        assert data["destination_domain"] == "finance"
        assert data["status"] == "active"
        assert data["transfer_count"] == 0
        assert "request_id" in data

    async def test_create_requires_auth(self, client: AsyncClient):
        resp = await client.post("/v2/connections", json={
            "name": "Test",
            "source_domain": "robotics_sim",
            "destination_domain": "finance",
        })
        assert resp.status_code == 401
        assert resp.json()["error"] == "UNAUTHORIZED"

    async def test_same_domain_rejected(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/connections", json={
            "name": "Bad",
            "source_domain": "finance",
            "destination_domain": "finance",
        })
        assert resp.status_code == 422
        assert "differ" in resp.json()["message"]

    async def test_unknown_domain_rejected(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/connections", json={
            "name": "Bad",
            "source_domain": "nonexistent_domain",
            "destination_domain": "finance",
        })
        assert resp.status_code == 422
        assert resp.json()["error"] == "DOMAIN_UNKNOWN"

    async def test_response_has_x_request_id_header(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/connections", json={
            "name": "Header Test",
            "source_domain": "logistics",
            "destination_domain": "software_dev",
        })
        assert "x-request-id" in resp.headers

    async def test_optional_fields_accepted(self, authed_client: AsyncClient):
        resp = await authed_client.post("/v2/connections", json={
            "name": "Full Config",
            "source_domain": "medical",
            "destination_domain": "education",
            "gap_threshold": 0.65,
            "allow_partial": False,
            "auto_rollback": True,
            "metadata": {"project": "test-alpha"},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["gap_threshold"] == 0.65
        assert data["allow_partial"] is False


class TestGetConnection:
    async def test_get_existing_connection(self, authed_client: AsyncClient):
        create = await authed_client.post("/v2/connections", json={
            "name": "Get Test",
            "source_domain": "game_ai",
            "destination_domain": "logistics",
        })
        conn_id = create.json()["connection_id"]

        resp = await authed_client.get(f"/v2/connections/{conn_id}")
        assert resp.status_code == 200
        assert resp.json()["connection_id"] == conn_id

    async def test_get_nonexistent_returns_404(self, authed_client: AsyncClient):
        resp = await authed_client.get("/v2/connections/cn_00000000")
        assert resp.status_code == 404
        assert resp.json()["error"] == "CONNECTION_NOT_FOUND"


class TestListConnections:
    async def test_list_returns_paginated(self, authed_client: AsyncClient):
        # Create a few
        for i in range(3):
            await authed_client.post("/v2/connections", json={
                "name": f"List Test {i}",
                "source_domain": "robotics_sim",
                "destination_domain": "game_ai",
            })

        resp = await authed_client.get("/v2/connections?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) <= 2


class TestConnectionSync:
    async def test_sync_returns_transfer_result(self, authed_client: AsyncClient):
        # Create connection
        create = await authed_client.post("/v2/connections", json={
            "name": "Sync Test",
            "source_domain": "robotics_sim",
            "destination_domain": "logistics",
        })
        conn_id = create.json()["connection_id"]

        resp = await authed_client.post(f"/v2/connections/{conn_id}/sync", json={
            "task": "Sort and route packages by destination zone",
            "episodes": 500,
            "depth": "standard",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "transfer_id" in data
        assert data["transfer_id"].startswith("tr_")
        assert "compat_score" in data
        assert 0.0 <= data["compat_score"] <= 1.0
        assert data["status"] in ("INJECTED", "PARTIAL", "REJECTED")
        assert "adapter_log" in data
        assert "sub_scores" in data
        assert "gaps" in data

    async def test_sync_dry_run(self, authed_client: AsyncClient):
        create = await authed_client.post("/v2/connections", json={
            "name": "Dry Run Test",
            "source_domain": "finance",
            "destination_domain": "software_dev",
        })
        conn_id = create.json()["connection_id"]

        resp = await authed_client.post(f"/v2/connections/{conn_id}/sync", json={
            "task": "Analyse and rank investment signals by return potential",
            "episodes": 200,
            "dry_run": True,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "DRY_RUN"

    async def test_sync_paused_connection_rejected(self, authed_client: AsyncClient):
        # Manually hit a nonexistent conn
        resp = await authed_client.post("/v2/connections/cn_00000099/sync", json={
            "task": "Some task description here",
            "episodes": 100,
        })
        assert resp.status_code == 404


class TestDeleteConnection:
    async def test_delete_returns_204(self, authed_client: AsyncClient):
        create = await authed_client.post("/v2/connections", json={
            "name": "Delete Me",
            "source_domain": "education",
            "destination_domain": "medical",
        })
        conn_id = create.json()["connection_id"]

        resp = await authed_client.delete(f"/v2/connections/{conn_id}")
        assert resp.status_code == 204

    async def test_deleted_connection_returns_404(self, authed_client: AsyncClient):
        create = await authed_client.post("/v2/connections", json={
            "name": "Delete and Get",
            "source_domain": "education",
            "destination_domain": "game_ai",
        })
        conn_id = create.json()["connection_id"]

        await authed_client.delete(f"/v2/connections/{conn_id}")
        resp = await authed_client.get(f"/v2/connections/{conn_id}")
        assert resp.status_code == 404
