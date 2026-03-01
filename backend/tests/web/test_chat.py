import json
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.web.main import app
from app.core.models.events import PlannerEvent, ChunkEvent, DoneEvent


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_chat_rejects_empty_message(client):
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422


def test_chat_returns_sse_stream(client):
    async def mock_process_message(*args, **kwargs):
        yield PlannerEvent(
            needs_search=False,
            reasoning="test",
            search_queries=[],
            query_type="conversational",
        )
        yield ChunkEvent(content="Hello!")
        yield DoneEvent()

    with patch("app.web.routes.chat.get_chat_service") as mock_get_service:
        mock_service = AsyncMock()
        mock_service.process_message = mock_process_message
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/chat",
            json={"message": "Hi there"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        lines = response.text.strip().split("\n")
        events = []
        for line in lines:
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        assert len(events) >= 2
