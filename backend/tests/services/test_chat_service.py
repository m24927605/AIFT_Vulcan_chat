import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.chat_service import ChatService
from app.models.schemas import PlannerDecision, SearchResult


@pytest.fixture
def chat_service():
    return ChatService(
        openai_api_key="test-key",
        openai_model="gpt-4o",
        tavily_api_key="test-tavily",
    )


@pytest.mark.asyncio
async def test_chat_stream_with_search(chat_service):
    planner_decision = PlannerDecision(
        needs_search=True,
        reasoning="Need latest stock info",
        search_queries=["TSMC stock price"],
        query_type="temporal",
    )
    search_results = [
        SearchResult(
            title="TSMC Stock",
            url="https://example.com",
            content="TSMC is at $180",
            score=0.9,
        )
    ]

    async def mock_execute(*args, **kwargs):
        for chunk in ["TSMC ", "is $180 [1]"]:
            yield chunk

    with (
        patch.object(
            chat_service._planner, "plan",
            new_callable=AsyncMock, return_value=planner_decision,
        ),
        patch.object(
            chat_service._search, "search_multiple",
            new_callable=AsyncMock, return_value=search_results,
        ),
        patch.object(
            chat_service._executor, "execute", side_effect=mock_execute,
        ),
        patch.object(
            chat_service._executor, "build_citations",
            return_value=[],
        ),
    ):
        events = []
        async for event_type, data in chat_service.chat_stream("TSMC stock?"):
            events.append((event_type, data))

        event_types = [e[0] for e in events]
        assert "planner" in event_types
        assert "chunk" in event_types
        assert "done" in event_types


@pytest.mark.asyncio
async def test_chat_stream_without_search(chat_service):
    planner_decision = PlannerDecision(
        needs_search=False,
        reasoning="Simple greeting",
        search_queries=[],
        query_type="conversational",
    )

    async def mock_execute(*args, **kwargs):
        for chunk in ["Hello!"]:
            yield chunk

    with (
        patch.object(
            chat_service._planner, "plan",
            new_callable=AsyncMock, return_value=planner_decision,
        ),
        patch.object(
            chat_service._executor, "execute", side_effect=mock_execute,
        ),
        patch.object(
            chat_service._executor, "build_citations",
            return_value=[],
        ),
    ):
        events = []
        async for event_type, data in chat_service.chat_stream("Hello!"):
            events.append((event_type, data))

        event_types = [e[0] for e in events]
        assert "planner" in event_types
        assert "searching" not in event_types
        assert "chunk" in event_types
