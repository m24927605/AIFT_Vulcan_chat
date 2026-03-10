"""
End-to-end test: HTTP request → FastAPI → ChatService → real SQLite DB → SSE response.

Only external APIs (OpenAI, Tavily) are mocked at the agent/service boundary.
Everything else is real:
- Real FastAPI app with CORS, exception handlers
- Real ConversationStorage with temp-file SQLite
- Real ChatService orchestration (Planner → Search → Executor flow)
- Real SSE event serialization and HTTP streaming
- Real DB persistence of messages with citations
"""

import json
import pytest
from unittest.mock import patch, AsyncMock

from httpx import AsyncClient, ASGITransport

from app.core.storage import ConversationStorage
from app.core.models.schemas import PlannerDecision, SearchResult
from app.web.main import create_app

# Fixed UUIDs for deterministic tests
CONV_ID_1 = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
CONV_ID_2 = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
CONV_ID_3 = "c3d4e5f6-a7b8-9012-cdef-123456789012"
CONV_ID_4 = "d4e5f6a7-b8c9-0123-defa-234567890123"
CONV_ID_5 = "e5f6a7b8-c9d0-1234-efab-345678901234"


@pytest.fixture
async def storage(tmp_path):
    """Real SQLite storage using a temp file."""
    db_path = str(tmp_path / "test_e2e.db")
    s = ConversationStorage(db_path=db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
async def client(storage):
    """Real FastAPI app with real storage."""
    app = create_app()
    app.state.conversation_storage = storage
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-CSRF-Token": "test-csrf"},
        cookies={"csrf_token": "test-csrf"},
    ) as c:
        yield c


def _parse_sse_events(response_text: str) -> list[dict]:
    """Parse SSE text into list of {event, data} dicts."""
    events = []
    current_event = ""
    for line in response_text.split("\n"):
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                events.append({"event": current_event, "data": data})
            except json.JSONDecodeError:
                pass
    return events


class TestChatE2E:
    """Full end-to-end chat flow: create conversation → send message → verify SSE + DB."""

    async def test_full_chat_flow_with_search(self, client, storage):
        """
        Scenario: User asks a temporal question about stock prices.
        Expected: Planner decides to search → Tavily returns results →
                  Executor streams answer with citations → DB persists both messages.
        """
        # Step 1: Create a conversation via API
        conv_response = await client.post(
            "/api/conversations",
            json={"id": CONV_ID_1, "title": "TSMC stock"},
        )
        assert conv_response.status_code == 200

        # Mock Planner → returns search decision
        mock_planner = AsyncMock(return_value=PlannerDecision(
            needs_search=True,
            reasoning="Stock price is a temporal question",
            search_queries=["TSMC stock price today"],
            query_type="temporal",
        ))

        # Mock Search → returns realistic results
        mock_search = AsyncMock(return_value=[
            SearchResult(
                title="TSMC (2330.TW) Stock Price",
                url="https://finance.example.com/tsmc",
                content="TSMC is currently trading at $180.50 USD.",
                score=0.95,
            ),
            SearchResult(
                title="台積電即時股價",
                url="https://tw.example.com/2330",
                content="台積電今日收盤價 935 元新台幣。",
                score=0.90,
            ),
        ])

        # Mock Executor → streams answer chunks
        async def mock_execute(*args, **kwargs):
            for chunk in [
                "Based on the latest data, ",
                "TSMC is trading at ",
                "**$180.50 USD** [1], ",
                "or **935 TWD** [2].",
            ]:
                yield chunk

        # Step 2: Send chat message
        with (
            patch.object(storage, "get_conversation", wraps=storage.get_conversation),
            patch(
                "app.core.agents.planner.PlannerAgent.plan",
                mock_planner,
            ),
            patch(
                "app.core.services.search_service.SearchService.search_multiple",
                mock_search,
            ),
            patch(
                "app.core.agents.executor.ExecutorAgent.execute",
                side_effect=mock_execute,
            ),
        ):
            response = await client.post(
                "/api/chat",
                json={
                    "message": "台積電今天股價多少？",
                    "conversation_id": CONV_ID_1,
                    "history": [],
                },
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # Step 3: Parse and verify SSE events
        events = _parse_sse_events(response.text)
        event_types = [e["event"] for e in events]

        # Planner event first
        assert event_types[0] == "planner"
        assert events[0]["data"]["needs_search"] is True
        assert events[0]["data"]["query_type"] == "temporal"

        # Searching events present
        assert "searching" in event_types

        # Chunks have content with citation markers
        chunks = [e["data"]["content"] for e in events if e["event"] == "chunk"]
        full_content = "".join(chunks)
        assert "[1]" in full_content
        assert "[2]" in full_content

        # Citations event
        citation_events = [e for e in events if e["event"] == "citations"]
        assert len(citation_events) == 1
        citations = citation_events[0]["data"]["citations"]
        assert len(citations) == 2
        assert citations[0]["url"] == "https://finance.example.com/tsmc"

        # Done event last
        assert event_types[-1] == "done"

        # Step 4: Verify DB persistence
        messages = await storage.get_messages(CONV_ID_1)
        assert len(messages) == 2

        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "台積電今天股價多少？"
        assert messages[0]["source"] == "web"

        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == full_content
        assert messages[1]["search_used"]  # SQLite stores as 1
        assert messages[1]["citations"] is not None
        assert len(messages[1]["citations"]) == 2

    async def test_full_chat_flow_with_fugle_and_tavily(self, client, storage):
        """
        Scenario: User asks about a Taiwan stock → Planner outputs data_sources
        → Fugle + Tavily fetched in parallel → Executor streams answer → DB persists.
        Fugle results appear first, have no URL (rendered as data source citations).
        """
        conv_response = await client.post(
            "/api/conversations",
            json={"id": CONV_ID_4, "title": "台積電股價"},
        )
        assert conv_response.status_code == 200

        from app.core.models.schemas import FugleSource

        # Planner returns data_sources for Taiwan stock
        mock_planner = AsyncMock(return_value=PlannerDecision(
            needs_search=True,
            reasoning="Taiwan stock price query — need Fugle + web search",
            search_queries=["台積電 最新消息"],
            query_type="temporal",
            data_sources=[FugleSource(type="fugle_quote", symbol="2330")],
        ))

        # Tavily returns news article
        mock_search = AsyncMock(return_value=[
            SearchResult(
                title="台積電法說會",
                url="https://news.example.com/tsmc",
                content="台積電宣布第四季營收創新高。",
                score=0.90,
            ),
        ])

        # Fugle returns formatted quote
        mock_fugle_quote = AsyncMock(
            return_value="台積電(2330) 2026-03-03 即時報價：\n最新價 1,975 元，漲跌 +15 (+0.76%)"
        )

        # Executor streams answer referencing both sources
        async def mock_execute(message, search_results, history=None):
            # Verify Fugle result is first, Tavily second
            assert len(search_results) == 2
            assert search_results[0].title.startswith("Fugle:")
            assert search_results[0].url == ""
            assert "1,975" in search_results[0].content
            assert search_results[1].url == "https://news.example.com/tsmc"
            for chunk in [
                "台積電(2330)目前股價為 ",
                "**1,975 元** [1]，",
                "近期法說會顯示第四季營收創新高 [2]。",
            ]:
                yield chunk

        with (
            patch(
                "app.core.config.settings.fugle_api_key",
                "test-fugle-key",
            ),
            patch(
                "app.core.agents.planner.PlannerAgent.plan",
                mock_planner,
            ),
            patch(
                "app.core.services.search_service.SearchService.search_multiple",
                mock_search,
            ),
            patch(
                "app.core.agents.executor.ExecutorAgent.execute",
                side_effect=mock_execute,
            ),
            patch(
                "app.core.services.fugle_service.FugleService.get_quote",
                mock_fugle_quote,
            ),
        ):
            response = await client.post(
                "/api/chat",
                json={
                    "message": "台積電今天收盤價多少？",
                    "conversation_id": CONV_ID_4,
                    "history": [],
                },
            )

        assert response.status_code == 200

        events = _parse_sse_events(response.text)
        event_types = [e["event"] for e in events]

        # Planner event shows search needed
        assert events[0]["data"]["needs_search"] is True
        assert events[0]["data"]["query_type"] == "temporal"

        # Searching events present
        assert "searching" in event_types

        # Chunks contain Fugle data
        chunks = [e["data"]["content"] for e in events if e["event"] == "chunk"]
        full_content = "".join(chunks)
        assert "1,975" in full_content
        assert "[1]" in full_content
        assert "[2]" in full_content

        # Citations: Fugle (data source, url="") + Tavily web result
        citation_events = [e for e in events if e["event"] == "citations"]
        assert len(citation_events) == 1
        citations = citation_events[0]["data"]["citations"]
        assert len(citations) == 2
        assert citations[0]["title"].startswith("Fugle:")
        assert citations[1]["url"] == "https://news.example.com/tsmc"

        # Done event
        assert event_types[-1] == "done"

        # DB persistence
        messages = await storage.get_messages(CONV_ID_4)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert "1,975" in messages[1]["content"]
        assert messages[1]["search_used"]

    async def test_full_chat_flow_with_finnhub_and_tavily(self, client, storage):
        """
        Scenario: User asks about US stock → Planner outputs finnhub data_sources
        → Finnhub + Tavily fetched in parallel → Executor streams answer → DB persists.
        Finnhub results have url="" (rendered as data source citations).
        """
        from app.core.models.schemas import FinnhubSource

        conv_response = await client.post(
            "/api/conversations",
            json={"id": CONV_ID_5, "title": "Apple Stock"},
        )
        assert conv_response.status_code == 200

        mock_planner = AsyncMock(return_value=PlannerDecision(
            needs_search=True,
            reasoning="US stock price query — need Finnhub + web search",
            search_queries=["AAPL stock latest"],
            query_type="temporal",
            data_sources=[FinnhubSource(type="finnhub_quote", symbol="AAPL")],
        ))

        mock_search = AsyncMock(return_value=[
            SearchResult(
                title="Apple Stock Analysis",
                url="https://news.example.com/aapl",
                content="Apple stock surges on AI news.",
                score=0.90,
            ),
        ])

        mock_finnhub_quote = AsyncMock(
            return_value="AAPL — Current: $189.50, Change: +2.30 (+1.23%), Day Range: $187.20–$190.15"
        )

        async def mock_execute(message, search_results, history=None):
            assert len(search_results) == 2
            assert search_results[0].title.startswith("Finnhub:")
            assert search_results[0].url == ""
            assert "189.50" in search_results[0].content
            assert search_results[1].url == "https://news.example.com/aapl"
            for chunk in [
                "Apple (AAPL) is currently trading at ",
                "**$189.50** [1], ",
                "up 1.23% today. Recent AI news boosts sentiment [2].",
            ]:
                yield chunk

        with (
            patch(
                "app.core.config.settings.finnhub_api_key",
                "test-finnhub-key",
            ),
            patch(
                "app.core.agents.planner.PlannerAgent.plan",
                mock_planner,
            ),
            patch(
                "app.core.services.search_service.SearchService.search_multiple",
                mock_search,
            ),
            patch(
                "app.core.agents.executor.ExecutorAgent.execute",
                side_effect=mock_execute,
            ),
            patch(
                "app.core.services.finnhub_service.FinnhubService.get_quote",
                mock_finnhub_quote,
            ),
        ):
            response = await client.post(
                "/api/chat",
                json={
                    "message": "What is Apple stock price today?",
                    "conversation_id": CONV_ID_5,
                    "history": [],
                },
            )

        assert response.status_code == 200

        events = _parse_sse_events(response.text)
        event_types = [e["event"] for e in events]

        assert events[0]["data"]["needs_search"] is True
        assert "searching" in event_types

        chunks = [e["data"]["content"] for e in events if e["event"] == "chunk"]
        full_content = "".join(chunks)
        assert "189.50" in full_content
        assert "[1]" in full_content
        assert "[2]" in full_content

        # Citations: Finnhub (data source, url="") + Tavily web result
        citation_events = [e for e in events if e["event"] == "citations"]
        assert len(citation_events) == 1
        citations = citation_events[0]["data"]["citations"]
        assert len(citations) == 2
        assert citations[0]["title"].startswith("Finnhub:")
        assert citations[1]["url"] == "https://news.example.com/aapl"

        assert event_types[-1] == "done"

        messages = await storage.get_messages(CONV_ID_5)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert "189.50" in messages[1]["content"]
        assert messages[1]["search_used"]

    async def test_chat_without_search(self, client, storage):
        """
        Scenario: User sends a greeting (no search needed).
        Expected: Planner decides no search → Executor answers directly →
                  No searching/citations events → DB persists messages.
        """
        await client.post(
            "/api/conversations",
            json={"id": CONV_ID_2, "title": "Greeting"},
        )

        mock_planner = AsyncMock(return_value=PlannerDecision(
            needs_search=False,
            reasoning="This is a greeting",
            search_queries=[],
            query_type="conversational",
        ))

        async def mock_execute(*args, **kwargs):
            yield "Hello! "
            yield "How can I help you today?"

        with (
            patch(
                "app.core.agents.planner.PlannerAgent.plan",
                mock_planner,
            ),
            patch(
                "app.core.agents.executor.ExecutorAgent.execute",
                side_effect=mock_execute,
            ),
        ):
            response = await client.post(
                "/api/chat",
                json={
                    "message": "Hello!",
                    "conversation_id": CONV_ID_2,
                    "history": [],
                },
            )

        assert response.status_code == 200

        events = _parse_sse_events(response.text)
        event_types = [e["event"] for e in events]

        # No searching events
        assert "searching" not in event_types

        # Planner says no search
        assert events[0]["data"]["needs_search"] is False

        # Chunks present
        chunks = [e["data"]["content"] for e in events if e["event"] == "chunk"]
        assert "".join(chunks) == "Hello! How can I help you today?"

        # No citations
        assert "citations" not in event_types

        # DB persistence
        messages = await storage.get_messages(CONV_ID_2)
        assert len(messages) == 2
        assert not messages[1]["search_used"]  # SQLite stores as 0

    async def test_conversation_lifecycle(self, client, storage):
        """
        Scenario: Full CRUD lifecycle — create, list, get, delete.
        Expected: Each API endpoint works with real SQLite storage.
        """
        # Create
        resp = await client.post(
            "/api/conversations",
            json={"id": CONV_ID_3, "title": "Test Conv"},
        )
        assert resp.status_code == 200

        # List without ids → returns this web session's conversations
        resp = await client.get("/api/conversations")
        assert resp.status_code == 200
        convs = resp.json()["conversations"]
        assert any(c["id"] == CONV_ID_3 for c in convs)

        # List with ids → returns matching
        resp = await client.get(f"/api/conversations?ids={CONV_ID_3}")
        assert resp.status_code == 200
        convs = resp.json()["conversations"]
        assert any(c["id"] == CONV_ID_3 for c in convs)

        # Get
        resp = await client.get(f"/api/conversations/{CONV_ID_3}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Conv"

        # Delete
        resp = await client.delete(f"/api/conversations/{CONV_ID_3}")
        assert resp.status_code == 200

        # Verify deleted
        resp = await client.get(f"/api/conversations/{CONV_ID_3}")
        assert resp.status_code == 404
