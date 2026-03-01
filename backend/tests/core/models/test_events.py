import pytest
from app.core.models.events import (
    PlannerEvent,
    SearchingEvent,
    ChunkEvent,
    CitationsEvent,
    DoneEvent,
    ChatEvent,
)


def test_planner_event_creation():
    event = PlannerEvent(
        needs_search=True,
        reasoning="Need latest info",
        search_queries=["TSMC stock"],
        query_type="temporal",
    )
    assert event.needs_search is True
    assert event.reasoning == "Need latest info"
    assert event.search_queries == ["TSMC stock"]
    assert event.query_type == "temporal"


def test_searching_event_creation():
    event = SearchingEvent(query="TSMC stock", status="searching")
    assert event.query == "TSMC stock"
    assert event.status == "searching"
    assert event.results_count is None


def test_searching_event_with_results_count():
    event = SearchingEvent(query="TSMC stock", status="done", results_count=5)
    assert event.results_count == 5


def test_chunk_event_creation():
    event = ChunkEvent(content="Hello ")
    assert event.content == "Hello "


def test_citations_event_creation():
    citations = [{"index": 1, "title": "Test", "url": "https://example.com", "snippet": "..."}]
    event = CitationsEvent(citations=citations)
    assert len(event.citations) == 1


def test_done_event_creation():
    event = DoneEvent()
    assert isinstance(event, DoneEvent)


def test_chat_event_type_union():
    events: list[ChatEvent] = [
        PlannerEvent(needs_search=False, reasoning="test", search_queries=[], query_type="conversational"),
        SearchingEvent(query="q", status="searching"),
        ChunkEvent(content="hi"),
        CitationsEvent(citations=[]),
        DoneEvent(),
    ]
    assert len(events) == 5
