import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.web.main import app

    return TestClient(app)


def test_submit_analysis_returns_task_id(client):
    mock_task = MagicMock()
    mock_task.id = "test-task-id-123"
    with patch("app.web.routes.analysis.deep_analysis_task") as mock:
        mock.delay.return_value = mock_task
        response = client.post(
            "/api/analysis",
            json={"query": "Analyze TSMC revenue trends", "max_rounds": 2},
        )
    assert response.status_code == 202
    data = response.json()
    assert data["task_id"] == "test-task-id-123"
    assert data["status"] == "pending"


def test_get_analysis_status_pending(client):
    with patch("app.web.routes.analysis.celery_app") as mock_celery:
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.info = None
        mock_celery.AsyncResult.return_value = mock_result
        response = client.get("/api/analysis/test-task-id-123")
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
        response = client.get("/api/analysis/test-task-id-123")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["result"]["answer"] == "TSMC revenue grew 30%"


def test_submit_analysis_validates_query_length(client):
    response = client.post("/api/analysis", json={"query": "", "max_rounds": 2})
    assert response.status_code == 422
