import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_deep_analysis_runs_multi_step():
    from app.core.tasks.deep_analysis import run_deep_analysis_async

    mock_llm = MagicMock()
    mock_llm.provider_name = "openai"
    mock_llm.chat = AsyncMock(
        side_effect=[
            '{"needs_search": true, "reasoning": "Need data", "search_queries": ["TSMC revenue 2024"], "query_type": "temporal"}',
            '{"needs_search": true, "reasoning": "Need more", "search_queries": ["TSMC Q4 earnings"], "query_type": "temporal"}',
            # verifier response
            '{"is_consistent": true, "issues": [], "confidence": 0.9, "suggestion": ""}',
        ]
    )

    async def mock_stream(*args, **kwargs):
        for chunk in ["TSMC ", "revenue ", "analysis"]:
            yield chunk

    mock_llm.chat_stream = MagicMock(return_value=mock_stream())

    mock_search = MagicMock()
    mock_search.search_multiple = AsyncMock(
        return_value=[
            MagicMock(
                title="TSMC Revenue",
                url="https://example.com",
                content="TSMC Q4 revenue up 30%",
                score=0.9,
            ),
        ]
    )

    result = await run_deep_analysis_async(
        query="Analyze TSMC revenue",
        llm=mock_llm,
        search_service=mock_search,
        max_rounds=2,
    )

    assert result["status"] == "completed"
    assert result["rounds"] == 2
    assert len(result["search_results"]) >= 1
    assert "TSMC " in result["answer"]


@pytest.mark.asyncio
async def test_deep_analysis_stops_when_no_search_needed():
    from app.core.tasks.deep_analysis import run_deep_analysis_async

    mock_llm = MagicMock()
    mock_llm.provider_name = "openai"
    mock_llm.chat = AsyncMock(
        return_value='{"needs_search": false, "reasoning": "Got enough", "search_queries": [], "query_type": "factual"}'
    )

    async def mock_stream(*args, **kwargs):
        yield "answer"

    mock_llm.chat_stream = MagicMock(return_value=mock_stream())

    mock_search = MagicMock()
    mock_search.search_multiple = AsyncMock(return_value=[])

    result = await run_deep_analysis_async(
        query="Simple question",
        llm=mock_llm,
        search_service=mock_search,
        max_rounds=3,
    )

    assert result["status"] == "completed"
    assert result["rounds"] == 1
    mock_search.search_multiple.assert_not_called()


@pytest.mark.asyncio
async def test_deep_analysis_accumulates_search_results():
    from app.core.tasks.deep_analysis import run_deep_analysis_async

    mock_llm = MagicMock()
    mock_llm.provider_name = "openai"

    call_count = 0

    async def mock_search_multiple(queries):
        nonlocal call_count
        call_count += 1
        return [
            MagicMock(
                title=f"Result {call_count}",
                url=f"https://example.com/{call_count}",
                content=f"Content {call_count}",
                score=0.9,
            )
        ]

    mock_llm.chat = AsyncMock(
        side_effect=[
            '{"needs_search": true, "reasoning": "r1", "search_queries": ["q1"], "query_type": "temporal"}',
            '{"needs_search": true, "reasoning": "r2", "search_queries": ["q2"], "query_type": "temporal"}',
            # verifier response
            '{"is_consistent": true, "issues": [], "confidence": 0.9, "suggestion": ""}',
        ]
    )

    async def mock_stream(*args, **kwargs):
        yield "final answer"

    mock_llm.chat_stream = MagicMock(return_value=mock_stream())

    mock_search = MagicMock()
    mock_search.search_multiple = AsyncMock(side_effect=mock_search_multiple)

    result = await run_deep_analysis_async(
        query="Complex", llm=mock_llm, search_service=mock_search, max_rounds=2
    )

    assert result["rounds"] == 2
    assert len(result["search_results"]) == 2


@pytest.mark.asyncio
async def test_deep_analysis_guards_output():
    """Deep analysis must run guard_model_output on executor chunks."""
    from app.core.tasks.deep_analysis import run_deep_analysis_async

    mock_llm = MagicMock()
    mock_llm.provider_name = "openai"
    mock_llm.chat = AsyncMock(
        side_effect=[
            '{"needs_search": true, "reasoning": "Need data", "search_queries": ["test"], "query_type": "temporal"}',
            # verifier response
            '{"is_consistent": true, "issues": [], "confidence": 0.9, "suggestion": ""}',
        ]
    )

    async def mock_stream(*args, **kwargs):
        yield "secret key sk-1234567890abcdefghijklmnop"

    mock_llm.chat_stream = MagicMock(return_value=mock_stream())

    mock_search = MagicMock()
    mock_search.search_multiple = AsyncMock(
        return_value=[
            MagicMock(title="Result", url="https://example.com", content="data about the topic here", score=0.9),
        ]
    )

    result = await run_deep_analysis_async(
        query="test", llm=mock_llm, search_service=mock_search, max_rounds=1
    )

    assert "sk-" not in result["answer"]
    assert "REDACTED" in result["answer"]


@pytest.mark.asyncio
async def test_deep_analysis_runs_verification():
    """Deep analysis must include verification results."""
    from app.core.tasks.deep_analysis import run_deep_analysis_async

    mock_llm = MagicMock()
    mock_llm.provider_name = "openai"
    mock_llm.chat = AsyncMock(
        side_effect=[
            '{"needs_search": true, "reasoning": "Need data", "search_queries": ["test"], "query_type": "temporal"}',
            '{"is_consistent": true, "issues": [], "confidence": 0.95, "suggestion": ""}',
        ]
    )

    async def mock_stream(*args, **kwargs):
        yield "Answer text"

    mock_llm.chat_stream = MagicMock(return_value=mock_stream())

    mock_search = MagicMock()
    mock_search.search_multiple = AsyncMock(
        return_value=[
            MagicMock(title="Result", url="https://example.com", content="data about the topic here", score=0.9),
        ]
    )

    result = await run_deep_analysis_async(
        query="test", llm=mock_llm, search_service=mock_search, max_rounds=1
    )

    assert "verification" in result
    assert result["verification"]["is_consistent"] is True


@pytest.mark.asyncio
async def test_deep_analysis_refuses_when_search_fails():
    """Deep analysis must refuse when search was needed but returned nothing."""
    from app.core.tasks.deep_analysis import run_deep_analysis_async

    mock_llm = MagicMock()
    mock_llm.provider_name = "openai"
    mock_llm.chat = AsyncMock(
        return_value='{"needs_search": true, "reasoning": "Need data", "search_queries": ["latest news"], "query_type": "temporal"}'
    )

    mock_search = MagicMock()
    mock_search.search_multiple = AsyncMock(return_value=[])

    result = await run_deep_analysis_async(
        query="What is the latest news?",
        llm=mock_llm,
        search_service=mock_search,
        max_rounds=1,
    )

    assert result["status"] == "refused"
    assert "unable" in result["answer"].lower() or "unavailable" in result["answer"].lower()
