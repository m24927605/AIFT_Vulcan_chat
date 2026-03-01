import pytest
from unittest.mock import AsyncMock, patch

from app.core.services.chat_service import ChatService
from app.core.models.schemas import PlannerDecision, SearchResult
from app.core.models.events import (
    PlannerEvent,
    SearchingEvent,
    ChunkEvent,
    CitationsEvent,
    DoneEvent,
)


@pytest.fixture
def chat_service():
    return ChatService(
        openai_api_key="test-key",
        openai_model="gpt-4o",
        tavily_api_key="test-tavily",
    )


@pytest.mark.asyncio
async def test_chat_stream_yields_chat_events_with_search(chat_service):
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
        async for event in chat_service.process_message("TSMC stock?"):
            events.append(event)

        assert isinstance(events[0], PlannerEvent)
        assert events[0].needs_search is True

        searching_events = [e for e in events if isinstance(e, SearchingEvent)]
        assert len(searching_events) >= 2

        chunk_events = [e for e in events if isinstance(e, ChunkEvent)]
        assert len(chunk_events) == 2
        assert chunk_events[0].content == "TSMC "

        assert isinstance(events[-1], DoneEvent)


@pytest.mark.asyncio
async def test_chat_stream_yields_chat_events_without_search(chat_service):
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
        async for event in chat_service.process_message("Hello!"):
            events.append(event)

        assert isinstance(events[0], PlannerEvent)
        assert events[0].needs_search is False

        searching_events = [e for e in events if isinstance(e, SearchingEvent)]
        assert len(searching_events) == 0

        chunk_events = [e for e in events if isinstance(e, ChunkEvent)]
        assert len(chunk_events) == 1
        assert chunk_events[0].content == "Hello!"

        assert isinstance(events[-1], DoneEvent)
