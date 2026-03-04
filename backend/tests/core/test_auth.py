"""Tests for API key authentication."""

import pytest
from unittest.mock import patch

from fastapi import FastAPI, Depends
from starlette.testclient import TestClient

from app.core.auth import require_api_key


@pytest.fixture
def app():
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(require_api_key)])
    async def protected():
        return {"ok": True}

    return app


class TestRequireApiKey:
    def test_rejects_missing_key(self, app):
        with patch("app.core.auth.settings") as mock:
            mock.api_secret_key = "my-secret"
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/protected")
            assert resp.status_code == 403  # missing header → None ≠ secret

    def test_rejects_wrong_key(self, app):
        with patch("app.core.auth.settings") as mock:
            mock.api_secret_key = "my-secret"
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/protected", headers={"X-API-Key": "wrong"})
            assert resp.status_code == 403

    def test_accepts_correct_key(self, app):
        with patch("app.core.auth.settings") as mock:
            mock.api_secret_key = "my-secret"
            client = TestClient(app)
            resp = client.get("/protected", headers={"X-API-Key": "my-secret"})
            assert resp.status_code == 200

    def test_allows_when_no_key_in_local_dev(self, app):
        with patch("app.core.auth.settings") as mock:
            mock.api_secret_key = ""
            mock.frontend_url = "http://localhost:3000"
            client = TestClient(app)
            resp = client.get("/protected", headers={"X-API-Key": "anything"})
            assert resp.status_code == 200

    def test_rejects_when_no_key_outside_local_dev(self, app):
        with patch("app.core.auth.settings") as mock:
            mock.api_secret_key = ""
            mock.frontend_url = "https://app.example.com"
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/protected", headers={"X-API-Key": "anything"})
            assert resp.status_code == 503
