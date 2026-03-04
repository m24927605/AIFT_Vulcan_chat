import pytest
from app.telegram.formatter import TelegramFormatter
from app.core.models.events import (
    PlannerEvent,
    SearchingEvent,
    CitationsEvent,
)


def test_format_planner_thinking():
    text = TelegramFormatter.format_planner(
        PlannerEvent(
            needs_search=True,
            reasoning="Need latest stock info",
            search_queries=["TSMC stock"],
            query_type="temporal",
        )
    )
    assert "Need latest stock info" in text


def test_format_planner_no_search():
    text = TelegramFormatter.format_planner(
        PlannerEvent(
            needs_search=False,
            reasoning="General knowledge",
            search_queries=[],
            query_type="conversational",
        )
    )
    assert "General knowledge" in text


def test_format_searching():
    text = TelegramFormatter.format_searching(
        SearchingEvent(query="TSMC stock", status="searching")
    )
    assert "TSMC stock" in text


def test_format_searching_done():
    text = TelegramFormatter.format_searching(
        SearchingEvent(query="TSMC stock", status="done", results_count=5)
    )
    assert "5" in text


def test_format_citations():
    text = TelegramFormatter.format_citations(
        CitationsEvent(citations=[
            {"index": 1, "title": "TSMC Stock", "url": "https://example.com/tsmc", "snippet": "TSMC is at $180"},
            {"index": 2, "title": "TSMC News", "url": "https://example.com/news", "snippet": "Q4 earnings"},
        ])
    )
    assert "TSMC Stock" in text
    assert "https://example.com/tsmc" in text
    assert "TSMC News" in text


def test_format_final_message_with_citations():
    answer = "TSMC stock is at $180 [1]."
    citations = CitationsEvent(citations=[
        {"index": 1, "title": "TSMC Stock", "url": "https://example.com/tsmc", "snippet": "..."},
    ])
    text = TelegramFormatter.format_final_message(answer, citations)
    assert "TSMC stock is at $180" in text
    assert "https://example.com/tsmc" in text


def test_format_final_message_without_citations():
    answer = "Hello! How can I help?"
    text = TelegramFormatter.format_final_message(answer, None)
    assert answer in text


def test_format_final_message_with_search_indicator():
    answer = "TSMC stock is at $180."
    text = TelegramFormatter.format_final_message(answer, None, needs_search=True)
    assert text.startswith("🔍 Searched the web")
    assert answer in text


def test_format_final_message_without_search_indicator():
    answer = "Hello! How can I help?"
    text = TelegramFormatter.format_final_message(answer, None, needs_search=False)
    assert text.startswith("💬 Answered directly")
    assert answer in text


def test_format_final_message_no_needs_search():
    answer = "Hello! How can I help?"
    text = TelegramFormatter.format_final_message(answer, None, needs_search=None)
    assert text == answer


def test_format_final_message_search_with_citations():
    answer = "TSMC stock is at $180 [1]."
    citations = CitationsEvent(citations=[
        {"index": 1, "title": "TSMC Stock", "url": "https://example.com/tsmc", "snippet": "..."},
    ])
    text = TelegramFormatter.format_final_message(answer, citations, needs_search=True)
    assert text.startswith("🔍 Searched the web")
    assert answer in text
    assert "https://example.com/tsmc" in text


def test_escape_markdown():
    text = TelegramFormatter.escape_md("Hello *world* _test_ [link](url)")
    assert isinstance(text, str)
