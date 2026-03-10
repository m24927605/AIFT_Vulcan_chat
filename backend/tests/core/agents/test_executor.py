import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.agents.executor import ExecutorAgent
from app.core.models.schemas import NormalizedSearchResult, SearchResult, Citation, ExtractedFact, ExtractedNumber


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.provider_name = "openai"
    llm.chat = AsyncMock()
    return llm


@pytest.fixture
def executor(mock_llm):
    return ExecutorAgent(llm=mock_llm)


@pytest.fixture
def sample_search_results():
    return [
        SearchResult(
            title="TSMC Stock",
            url="https://example.com/tsmc",
            content="TSMC stock is at $180",
            score=0.95,
        ),
        SearchResult(
            title="TSMC News",
            url="https://example.com/tsmc-news",
            content="TSMC Q4 earnings beat expectations",
            score=0.85,
        ),
    ]


@pytest.fixture
def normalized_search_results():
    return [
        NormalizedSearchResult(
            source_kind="web",
            title="TSMC Stock",
            url="https://example.com/tsmc",
            publisher="Reuters",
            published_at="2026-03-08",
            excerpt="TSMC stock is at $180 after earnings.",
            facts=[ExtractedFact(text="TSMC stock is at $180 after earnings.")],
            numbers=[ExtractedNumber(label="value_1", value="$180")],
        )
    ]


@pytest.mark.asyncio
async def test_executor_streams_answer_with_search_results(
    executor, mock_llm, normalized_search_results
):
    async def mock_stream(*args, **kwargs):
        for text in ["TSMC ", "is at ", "$180 [1]"]:
            yield text

    mock_llm.chat_stream = MagicMock(return_value=mock_stream())
    chunks = []
    async for chunk in executor.execute(
        message="What is TSMC stock price?",
        search_results=normalized_search_results,
    ):
        chunks.append(chunk)
    assert len(chunks) == 3
    assert "".join(chunks) == "TSMC is at $180 [1]"


@pytest.mark.asyncio
async def test_executor_streams_answer_without_search(executor, mock_llm):
    async def mock_stream(*args, **kwargs):
        for text in ["Hello! ", "How can ", "I help?"]:
            yield text

    mock_llm.chat_stream = MagicMock(return_value=mock_stream())
    chunks = []
    async for chunk in executor.execute(
        message="Hi there!",
        search_results=[],
    ):
        chunks.append(chunk)
    assert "".join(chunks) == "Hello! How can I help?"


def test_build_citations(executor, sample_search_results):
    citations = executor.build_citations(sample_search_results)
    assert len(citations) == 2
    assert citations[0].index == 1
    assert citations[0].title == "TSMC Stock"
    assert citations[1].index == 2


def test_build_citations_includes_all_pre_filtered_results(executor, sample_search_results):
    """build_citations includes all items (pre-filtered upstream by filter_renderable_results)."""
    results_with_data_source = [
        SearchResult(
            title="Fugle: 2330 fugle_quote",
            url="",
            content="台積電(2330) 最新價 1,975 元",
            score=1.0,
        ),
    ] + sample_search_results

    citations = executor.build_citations(results_with_data_source)
    assert len(citations) == 3
    assert citations[0].title == "Fugle: 2330 fugle_quote"
    assert citations[0].url == ""
    assert citations[1].title == "TSMC Stock"


def test_format_search_results_uses_structured_untrusted_blocks(executor, sample_search_results):
    normalized = [
        NormalizedSearchResult(
            source_kind="web",
            title="TSMC Stock",
            url="https://example.com/tsmc",
            publisher="Reuters",
            published_at="2026-03-08",
            excerpt="TSMC stock is at $180.",
            facts=[ExtractedFact(text="TSMC stock is at $180.")],
            numbers=[ExtractedNumber(label="value_1", value="$180")],
        )
    ]
    formatted = executor._format_search_results(normalized)
    assert "<result index=\"1\">" in formatted
    assert "<excerpt>" in formatted
    assert "<facts>" in formatted
    assert "<numbers>" in formatted
    assert "URL:" not in formatted


@pytest.mark.asyncio
async def test_executor_calls_tracing_after_stream(executor, mock_llm):
    async def mock_stream(*args, **kwargs):
        for text in ["Hello ", "world"]:
            yield text

    mock_llm.chat_stream = MagicMock(return_value=mock_stream())
    with patch("app.core.agents.executor.get_tracer") as mock_get_tracer:
        mock_tracer = MagicMock()
        mock_get_tracer.return_value = mock_tracer
        chunks = []
        async for chunk in executor.execute(message="test", search_results=[]):
            chunks.append(chunk)
        mock_tracer.trace_llm_call.assert_called_once()
        call_kwargs = mock_tracer.trace_llm_call.call_args.kwargs
        assert call_kwargs["name"] == "executor"
        assert call_kwargs["output_text"] == "Hello world"
