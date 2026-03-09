import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.agents.verifier import VerifierAgent, VerificationResult
from app.core.models.schemas import (
    NormalizedSearchResult,
    ExtractedFact,
    ExtractedNumber,
)


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.provider_name = "openai"
    llm.chat = AsyncMock()
    return llm


@pytest.fixture
def verifier(mock_llm):
    return VerifierAgent(llm=mock_llm)


@pytest.fixture
def sample_search_results():
    return [
        NormalizedSearchResult(
            source_kind="web",
            title="TSMC Stock Price",
            url="https://example.com",
            excerpt="TSMC closed at $180.50 today with strong volume",
            facts=[
                ExtractedFact(
                    text="TSMC closed at $180.50 today with strong volume"
                )
            ],
            numbers=[ExtractedNumber(label="price", value="$180.50")],
        )
    ]


@pytest.mark.asyncio
async def test_verifier_approves_consistent_answer(
    verifier, mock_llm, sample_search_results
):
    mock_llm.chat.return_value = json.dumps(
        {
            "is_consistent": True,
            "issues": [],
            "confidence": 0.95,
            "suggestion": "",
        }
    )
    result = await verifier.verify(
        query="What is TSMC stock price?",
        answer="TSMC closed at $180.50 today [1]",
        search_results=sample_search_results,
    )
    assert result.is_consistent is True
    assert result.confidence >= 0.9
    assert len(result.issues) == 0


@pytest.mark.asyncio
async def test_verifier_detects_hallucinated_number(
    verifier, mock_llm, sample_search_results
):
    mock_llm.chat.return_value = json.dumps(
        {
            "is_consistent": False,
            "issues": ["Answer says $185.00 but source says $180.50"],
            "confidence": 0.3,
            "suggestion": "Correct the price to $180.50",
        }
    )
    result = await verifier.verify(
        query="What is TSMC stock price?",
        answer="TSMC is trading at $185.00 [1]",
        search_results=sample_search_results,
    )
    assert result.is_consistent is False
    assert len(result.issues) >= 1
    assert result.confidence < 0.5


@pytest.mark.asyncio
async def test_verifier_handles_invalid_json(
    verifier, mock_llm, sample_search_results
):
    mock_llm.chat.return_value = "not json"
    result = await verifier.verify(
        query="test",
        answer="test answer",
        search_results=sample_search_results,
    )
    assert result.is_consistent is False
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_verifier_passes_with_no_search_results(verifier, mock_llm):
    mock_llm.chat.return_value = json.dumps(
        {
            "is_consistent": True,
            "issues": [],
            "confidence": 0.8,
            "suggestion": "",
        }
    )
    result = await verifier.verify(
        query="What is Python?",
        answer="Python is a programming language.",
        search_results=[],
    )
    assert result.is_consistent is True


@pytest.mark.asyncio
async def test_verifier_calls_tracing(verifier, mock_llm, sample_search_results):
    mock_llm.chat.return_value = json.dumps(
        {
            "is_consistent": True,
            "issues": [],
            "confidence": 0.9,
            "suggestion": "",
        }
    )
    with patch("app.core.agents.verifier.get_tracer") as mock_get_tracer:
        mock_tracer = MagicMock()
        mock_get_tracer.return_value = mock_tracer
        await verifier.verify(
            query="test",
            answer="test answer",
            search_results=sample_search_results,
        )
        mock_tracer.trace_llm_call.assert_called_once()
        call_kwargs = mock_tracer.trace_llm_call.call_args.kwargs
        assert call_kwargs["name"] == "verifier"
