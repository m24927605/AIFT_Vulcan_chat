"""Tests for enhanced health check endpoint."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport

from app.web.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    app.state.started_at = 1000000.0

    # Mock storage with working DB
    mock_storage = MagicMock()
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_storage.db = mock_db
    app.state.conversation_storage = mock_storage

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthCheck:
    async def test_healthy_response(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["checks"]["database"] == "ok"
        assert data["uptime_seconds"] is not None

    async def test_degraded_when_db_fails(self):
        app = create_app()
        app.state.started_at = 1000000.0

        mock_storage = MagicMock()
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB connection lost"))
        mock_storage.db = mock_db
        app.state.conversation_storage = mock_storage

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["checks"]["database"] == "error"

    async def test_db_error_does_not_leak_details(self):
        app = create_app()
        app.state.started_at = 1000000.0

        mock_storage = MagicMock()
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(
            side_effect=Exception("FATAL: password auth failed for user 'vulcan'")
        )
        mock_storage.db = mock_db
        app.state.conversation_storage = mock_storage

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/health")

        data = resp.json()
        assert data["checks"]["database"] == "error"
        assert "password" not in str(data)
