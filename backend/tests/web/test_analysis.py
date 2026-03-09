import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web.routes import analysis


_DEFAULT_SESSION = {
    "session_id": "test-session", "ua_hash": "h", "ip_prefix": "127.0",
    "created_at": 0, "last_seen_at": 0, "expires_at": 999999999999,
    "rotated_to": None, "revoked_at": None, "telegram_chat_id": None,
}

_CSRF_HEADERS = {"X-CSRF-Token": "t"}
_CSRF_COOKIES = {"csrf_token": "t"}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(analysis.router)
    storage = AsyncMock()
    storage.get_web_session.return_value = _DEFAULT_SESSION
    app.state.conversation_storage = storage
    with TestClient(app, cookies=_CSRF_COOKIES) as c:
        yield c


def test_submit_analysis_returns_task_id(client):
    mock_task = MagicMock()
    mock_task.id = "test-task-id-123"
    with patch("app.web.routes.analysis.deep_analysis_task") as mock:
        mock.delay.return_value = mock_task
        response = client.post(
            "/api/analysis",
            json={"query": "Analyze TSMC revenue trends", "max_rounds": 2},
            headers=_CSRF_HEADERS,
        )
    assert response.status_code == 202
    data = response.json()
    assert data["task_id"] == "test-task-id-123"
    assert data["status"] == "pending"


def test_submit_analysis_rejected_without_csrf(client):
    """POST without CSRF token should be rejected."""
    response = client.post(
        "/api/analysis",
        json={"query": "Analyze TSMC revenue trends", "max_rounds": 2},
        headers={"Origin": "https://evil.com"},
    )
    assert response.status_code == 403


def test_get_analysis_status_pending(client):
    with patch("app.web.routes.analysis.celery_app") as mock_celery:
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.info = None
        mock_celery.AsyncResult.return_value = mock_result
        response = client.get("/api/analysis/unknown-task-id")
    assert response.status_code == 200
    assert response.json()["status"] == "PENDING"


def test_get_analysis_status_completed(client):
    with patch("app.web.routes.analysis.celery_app") as mock_celery:
        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.result = {
            "status": "completed",
            "answer": "TSMC revenue grew 30%",
            "rounds": 2,
        }
        mock_celery.AsyncResult.return_value = mock_result
        response = client.get("/api/analysis/unknown-task-id")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["result"]["answer"] == "TSMC revenue grew 30%"


def test_submit_analysis_validates_query_length(client):
    response = client.post(
        "/api/analysis",
        json={"query": "", "max_rounds": 2},
        headers=_CSRF_HEADERS,
    )
    assert response.status_code == 422


def test_get_analysis_task_forbidden_for_other_session(client):
    """A different session should not be able to read another session's task."""
    analysis._task_owners["owned-task-id"] = "other-session-id"
    try:
        with patch("app.web.routes.analysis.celery_app") as mock_celery:
            mock_result = MagicMock()
            mock_result.state = "SUCCESS"
            mock_result.result = {"answer": "secret"}
            mock_celery.AsyncResult.return_value = mock_result
            response = client.get("/api/analysis/owned-task-id")
        assert response.status_code == 403
    finally:
        analysis._task_owners.pop("owned-task-id", None)
