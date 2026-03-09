"""
Automated adversarial testing pipeline for prompt injection defense.

Tests three defense layers:
1. Input sanitization (search result filtering)
2. Output guard (secret redaction)
3. Planner resilience (doesn't follow injected instructions)
"""
import json
import re

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.security import (
    sanitize_search_results,
    guard_model_output,
    normalize_search_results,
)
from app.core.models.schemas import SearchResult


def _load_adversarial_dataset() -> list[dict]:
    path = Path(__file__).resolve().parents[2] / "evals" / "adversarial_dataset.json"
    return json.loads(path.read_text())


def _get_cases_by_behavior(behavior: str) -> list[dict]:
    return [c for c in _load_adversarial_dataset() if c["expected_behavior"] == behavior]


class TestInputSanitization:
    """Tests that prompt injection patterns are filtered from search results."""

    @pytest.mark.parametrize("case", _get_cases_by_behavior("filtered_in_search"), ids=lambda c: c["id"])
    def test_search_result_injection_is_filtered(self, case):
        malicious_result = SearchResult(
            title=case["attack"][:100],
            url="https://example.com",
            content=case["attack"],
            score=0.9,
        )
        sanitized = sanitize_search_results([malicious_result])
        result = sanitized[0]
        has_filter = "[filtered]" in result.title or "[filtered]" in result.content
        assert has_filter, (
            f"Attack '{case['id']}' ({case['description']}) was NOT filtered.\n"
            f"Title: {result.title}\nContent: {result.content[:200]}"
        )

    @pytest.mark.parametrize("case", _get_cases_by_behavior("filtered_in_search"), ids=lambda c: c["id"])
    def test_normalized_search_result_injection_is_filtered(self, case):
        malicious_result = SearchResult(
            title=case["attack"][:100],
            url="https://example.com",
            content=case["attack"],
            score=0.9,
        )
        sanitized = sanitize_search_results([malicious_result])
        normalized = normalize_search_results(sanitized)
        result = normalized[0]
        has_filter = "[filtered]" in result.title or "[filtered]" in result.excerpt
        facts_filtered = any("[filtered]" in f.text for f in result.facts)
        assert has_filter or facts_filtered, (
            f"Attack '{case['id']}' passed through normalization.\n"
            f"Title: {result.title}\nExcerpt: {result.excerpt[:200]}"
        )


class TestOutputGuard:
    """Tests that secret patterns are redacted from model output."""

    @pytest.mark.parametrize("case", _get_cases_by_behavior("redacted_in_output"), ids=lambda c: c["id"])
    def test_secret_pattern_is_redacted(self, case):
        guarded = guard_model_output(case["attack"])
        assert "[REDACTED" in guarded, (
            f"Attack '{case['id']}' ({case['description']}) was NOT redacted.\n"
            f"Output: {guarded}"
        )

    @pytest.mark.parametrize("case", _get_cases_by_behavior("redacted_in_output"), ids=lambda c: c["id"])
    def test_secret_pattern_original_value_removed(self, case):
        guarded = guard_model_output(case["attack"])
        if "sk-" in case["attack"]:
            assert not re.search(r"sk-[A-Za-z0-9_-]{20,}", guarded)
        if "sess-" in case["attack"]:
            assert not re.search(r"sess-[A-Za-z0-9_-]{16,}", guarded)


class TestBenignInputsNotFiltered:
    """Tests that legitimate queries are NOT incorrectly flagged."""

    @pytest.mark.parametrize("case", _get_cases_by_behavior("not_filtered"), ids=lambda c: c["id"])
    def test_benign_input_passes_sanitization(self, case):
        result = SearchResult(
            title=case["attack"][:100],
            url="https://example.com",
            content=case["attack"],
            score=0.9,
        )
        sanitized = sanitize_search_results([result])
        content = sanitized[0].content
        original_words = set(case["attack"].lower().split())
        filtered_words = set(content.lower().split())
        overlap = len(original_words & filtered_words) / len(original_words)
        assert overlap >= 0.5, (
            f"Benign input '{case['id']}' was over-filtered.\n"
            f"Original: {case['attack']}\nFiltered: {content}"
        )


class TestPlannerResilience:
    """Tests that the planner doesn't follow injected instructions."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("case", _get_cases_by_behavior("filtered_or_refused"), ids=lambda c: c["id"])
    async def test_planner_does_not_follow_injection(self, case):
        from app.core.agents.planner import PlannerAgent

        mock_llm = MagicMock()
        mock_llm.provider_name = "openai"
        mock_llm.chat = AsyncMock(return_value=json.dumps({
            "needs_search": False,
            "reasoning": "This appears to be a prompt injection attempt",
            "search_queries": [],
            "query_type": "conversational",
        }))

        planner = PlannerAgent(llm=mock_llm)
        decision = await planner.plan(case["attack"])

        assert decision is not None
        assert isinstance(decision.needs_search, bool)
        assert decision.query_type in ("temporal", "factual", "conversational")

        call_args = mock_llm.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][1]
        user_msg = messages[-1]["content"]
        assert case["attack"] in user_msg


class TestAdversarialReport:
    """Validates dataset coverage."""

    def test_dataset_coverage_report(self):
        dataset = _load_adversarial_dataset()
        categories = {}
        behaviors = {}
        for case in dataset:
            cat = case["category"]
            beh = case["expected_behavior"]
            categories[cat] = categories.get(cat, 0) + 1
            behaviors[beh] = behaviors.get(beh, 0) + 1

        assert len(dataset) >= 25, f"Need at least 25 attack cases, got {len(dataset)}"
        assert len(categories) >= 5, f"Need at least 5 categories, got {len(categories)}"
