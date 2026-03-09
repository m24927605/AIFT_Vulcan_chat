"""Tests for request middleware: logging, request ID, rate limiting."""

import time
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient
from fastapi import FastAPI

from app.core.middleware import (
    RequestLoggingMiddleware,
    RateLimitMiddleware,
    SecretRedactionFilter,
    request_id_var,
    RequestIDFilter,
    setup_logging,
)


@pytest.fixture
def app():
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"rid": request_id_var.get("-")}

    @app.post("/api/chat")
    async def chat_endpoint():
        return {"ok": True}

    return app


class TestRequestIDFilter:
    def test_injects_request_id(self):
        import logging

        f = RequestIDFilter()
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        assert f.filter(record)
        assert hasattr(record, "request_id")

    def test_uses_context_value(self):
        import logging

        token = request_id_var.set("test-123")
        f = RequestIDFilter()
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        f.filter(record)
        assert record.request_id == "test-123"
        request_id_var.reset(token)


class TestSecretRedactionFilter:
    def test_redacts_telegram_token_in_message(self):
        import logging

        f = SecretRedactionFilter()
        record = logging.LogRecord(
            "test", logging.ERROR, "", 0,
            "Telegram failed for token 123456789:AAABCDEFGHIJKLMNOPQRSTUV",
            (), None,
        )
        assert f.filter(record)
        assert "123456789:AAABCDEFGHIJKLMNOPQRSTUV" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_redacts_secret_in_args(self):
        import logging

        f = SecretRedactionFilter()
        record = logging.LogRecord(
            "test", logging.ERROR, "", 0,
            "Error: %s", ("authorization: Bearer secret-token-value",), None,
        )
        assert f.filter(record)
        assert "secret-token-value" not in record.args[0]


class TestRequestLoggingMiddleware:
    def test_assigns_request_id(self, app):
        app.add_middleware(RequestLoggingMiddleware)
        client = TestClient(app)
        resp = client.get("/test")
        assert resp.status_code == 200
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) == 12

    def test_preserves_client_request_id(self, app):
        app.add_middleware(RequestLoggingMiddleware)
        client = TestClient(app)
        resp = client.get("/test", headers={"X-Request-ID": "my-custom-id"})
        assert resp.headers["X-Request-ID"] == "my-custom-id"


class TestRateLimitMiddleware:
    def test_allows_requests_under_limit(self, app):
        app.add_middleware(RateLimitMiddleware, max_requests=5, window_seconds=60)
        client = TestClient(app)
        for _ in range(5):
            resp = client.post("/api/chat")
            assert resp.status_code == 200

    def test_blocks_requests_over_limit(self, app):
        app.add_middleware(RateLimitMiddleware, max_requests=2, window_seconds=60)
        client = TestClient(app)
        client.post("/api/chat")
        client.post("/api/chat")
        resp = client.post("/api/chat")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_does_not_limit_non_chat_routes(self, app):
        app.add_middleware(RateLimitMiddleware, max_requests=1, window_seconds=60)
        client = TestClient(app)
        client.post("/api/chat")  # uses the 1 allowed
        resp = client.get("/test")  # non-chat route, no limit
        assert resp.status_code == 200

    def test_ignores_x_forwarded_for_spoofing(self, app):
        """X-Forwarded-For must NOT bypass rate limiting."""
        app.add_middleware(RateLimitMiddleware, max_requests=2, window_seconds=60)
        client = TestClient(app)
        client.post("/api/chat")
        client.post("/api/chat")
        # Attempt to bypass by spoofing a different IP
        resp = client.post("/api/chat", headers={"X-Forwarded-For": "1.2.3.4"})
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_storage_backed_rate_limit(self):
        from unittest.mock import AsyncMock
        from fastapi import FastAPI

        app = FastAPI()

        @app.post("/api/chat")
        async def chat_endpoint():
            return {"ok": True}

        storage = AsyncMock()
        storage.check_rate_limit = AsyncMock(side_effect=[(True, 1), (False, 1)])
        app.state.conversation_storage = storage
        app.add_middleware(RateLimitMiddleware, max_requests=1, window_seconds=60)
        client = TestClient(app)

        ok = client.post("/api/chat")
        blocked = client.post("/api/chat")

        assert ok.status_code == 200
        assert blocked.status_code == 429
        assert storage.check_rate_limit.await_count == 2


class TestSetupLogging:
    def test_configures_root_logger(self):
        setup_logging()
        import logging

        root = logging.getLogger()
        assert root.level == logging.INFO
        assert len(root.handlers) >= 1
