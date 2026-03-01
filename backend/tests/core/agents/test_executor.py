import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.agents.executor import ExecutorAgent
from app.core.models.schemas import SearchResult, Citation


@pytest.fixture
def executor():
    return ExecutorAgent(api_key="test-key", model="gpt-4o")


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


@pytest.mark.asyncio
async def test_executor_streams_answer_with_search_results(
    executor, sample_search_results
):
    async def mock_stream(*args, **kwargs):
        for text in ["TSMC ", "is at ", "$180 [1]"]:
            yield text

    with patch.object(
        executor._openai, "chat_stream", return_value=mock_stream()
    ):
        chunks = []
        async for chunk in executor.execute(
            message="What is TSMC stock price?",
            search_results=sample_search_results,
        ):
            chunks.append(chunk)
        assert len(chunks) == 3
        assert "".join(chunks) == "TSMC is at $180 [1]"


@pytest.mark.asyncio
async def test_executor_streams_answer_without_search(executor):
    async def mock_stream(*args, **kwargs):
        for text in ["Hello! ", "How can ", "I help?"]:
            yield text

    with patch.object(
        executor._openai, "chat_stream", return_value=mock_stream()
    ):
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
