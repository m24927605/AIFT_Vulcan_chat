"""Tests for the secure_answer_pipeline module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.verifier import VerificationResult
from app.core.pipelines.secure_answer import secure_answer_pipeline


def _make_executor(chunks: list[str]) -> MagicMock:
    """Create a mock ExecutorAgent whose execute() yields the given chunks."""
    executor = MagicMock()

    async def fake_execute(message, search_results, history=None):
        for chunk in chunks:
            yield chunk

    executor.execute = MagicMock(side_effect=fake_execute)
    return executor


def _make_verifier(result: VerificationResult | None = None) -> MagicMock:
    """Create a mock VerifierAgent."""
    verifier = MagicMock()
    if result is None:
        result = VerificationResult(
            is_consistent=True, issues=[], confidence=0.95, suggestion=""
        )
    verifier.verify = AsyncMock(return_value=result)
    return verifier


def _make_normalized_result() -> MagicMock:
    """Create a minimal mock NormalizedSearchResult."""
    r = MagicMock()
    r.title = "Test Result"
    r.url = "https://example.com"
    r.excerpt = "Some excerpt"
    r.facts = []
    r.numbers = []
    return r


@pytest.mark.asyncio
async def test_refusal_when_search_required_but_empty_english():
    """English query, needs_search=True, empty results -> refused with English message."""
    executor = _make_executor(["should not appear"])
    verifier = _make_verifier()

    result = await secure_answer_pipeline(
        message="What is the latest stock price?",
        needs_search=True,
        normalized_results=[],
        executor=executor,
        verifier=verifier,
    )

    assert result["refused"] is True
    assert "unable to retrieve" in result["refusal_message"].lower()
    assert result["answer"] == ""
    assert result["guarded_chunks"] == []
    assert result["verification"] is None
    executor.execute.assert_not_called()
    verifier.verify.assert_not_called()


@pytest.mark.asyncio
async def test_refusal_when_search_required_but_empty_chinese():
    """Chinese query -> Chinese refusal with CJK chars."""
    executor = _make_executor(["should not appear"])
    verifier = _make_verifier()

    result = await secure_answer_pipeline(
        message="最新的股票價格是多少？",
        needs_search=True,
        normalized_results=[],
        executor=executor,
        verifier=verifier,
    )

    assert result["refused"] is True
    assert "無法取得" in result["refusal_message"]
    assert result["answer"] == ""
    assert result["guarded_chunks"] == []
    assert result["verification"] is None
    executor.execute.assert_not_called()
    verifier.verify.assert_not_called()


@pytest.mark.asyncio
async def test_guarded_output_redacts_secrets():
    """Executor yields a chunk containing a secret key -> REDACTED in answer."""
    executor = _make_executor(["Here is the key: sk-abc1234567890abcdefghij"])
    verifier = _make_verifier()

    result = await secure_answer_pipeline(
        message="Tell me something",
        needs_search=False,
        normalized_results=[],
        executor=executor,
        verifier=verifier,
    )

    assert result["refused"] is False
    assert "sk-" not in result["answer"]
    assert "REDACTED" in result["answer"]
    assert len(result["guarded_chunks"]) == 1
    assert "REDACTED" in result["guarded_chunks"][0]


@pytest.mark.asyncio
async def test_verification_runs_when_results_exist():
    """Results present -> verifier.verify called, verification returned."""
    search_result = _make_normalized_result()
    verification_result = VerificationResult(
        is_consistent=True, issues=[], confidence=0.9, suggestion=""
    )
    executor = _make_executor(["The answer is 42."])
    verifier = _make_verifier(verification_result)

    result = await secure_answer_pipeline(
        message="What is the answer?",
        needs_search=True,
        normalized_results=[search_result],
        executor=executor,
        verifier=verifier,
    )

    assert result["refused"] is False
    assert result["verification"] is not None
    assert result["verification"].is_consistent is True
    verifier.verify.assert_called_once()


@pytest.mark.asyncio
async def test_verification_skipped_when_no_results():
    """No results, needs_search=False -> verifier not called, verification=None."""
    executor = _make_executor(["General knowledge answer."])
    verifier = _make_verifier()

    result = await secure_answer_pipeline(
        message="What is Python?",
        needs_search=False,
        normalized_results=[],
        executor=executor,
        verifier=verifier,
    )

    assert result["refused"] is False
    assert result["verification"] is None
    verifier.verify.assert_not_called()


@pytest.mark.asyncio
async def test_no_refusal_when_search_not_required():
    """needs_search=False, empty results -> refused=False, answer normal."""
    executor = _make_executor(["Hello world!"])
    verifier = _make_verifier()

    result = await secure_answer_pipeline(
        message="Say hello",
        needs_search=False,
        normalized_results=[],
        executor=executor,
        verifier=verifier,
    )

    assert result["refused"] is False
    assert result["answer"] == "Hello world!"
    assert result["guarded_chunks"] == ["Hello world!"]
    assert result["refusal_message"] == ""
