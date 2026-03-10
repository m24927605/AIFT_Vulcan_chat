# Security and Logic Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 4 security/logic issue groups: output security parity for deep analysis, search-fail refusal, citation index drift, and broadcast storage lifecycle.

**Architecture:** Extract a shared `secure_answer_pipeline` module used by both chat and deep-analysis paths. Pre-filter no-URL search results before any consumer. Fix broadcast storage init/cleanup and remove unused `target=all`.

**Tech Stack:** Python/FastAPI (backend), Next.js/React/TypeScript (frontend), pytest, vitest

---

### Task 1: Create shared `secure_answer_pipeline` module

**Files:**
- Create: `backend/app/core/pipelines/__init__.py`
- Create: `backend/app/core/pipelines/secure_answer.py`
- Test: `backend/tests/core/pipelines/test_secure_answer.py`

This module extracts the secured answer path (refusal, guarded generation, verification) into a single reusable function.

**Step 1: Create the `__init__.py` file**

Create empty `backend/app/core/pipelines/__init__.py`.

**Step 2: Write failing tests for `secure_answer_pipeline`**

Create `backend/tests/core/pipelines/__init__.py` (empty) and `backend/tests/core/pipelines/test_secure_answer.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.pipelines.secure_answer import secure_answer_pipeline
from app.core.models.schemas import NormalizedSearchResult, ExtractedFact, ExtractedNumber
from app.core.agents.verifier import VerificationResult


def _make_normalized_result(title="Test", url="https://example.com", excerpt="content"):
    return NormalizedSearchResult(
        source_kind="web",
        title=title,
        url=url,
        publisher="",
        published_at="",
        excerpt=excerpt,
        facts=[ExtractedFact(text="Some fact about the topic")],
        numbers=[ExtractedNumber(label="value_1", value="100")],
    )


def _make_executor():
    executor = MagicMock()
    async def mock_execute(*args, **kwargs):
        for chunk in ["Hello ", "world"]:
            yield chunk
    executor.execute = MagicMock(side_effect=mock_execute)
    return executor


def _make_verifier(is_consistent=True, confidence=0.95):
    verifier = AsyncMock()
    verifier.verify = AsyncMock(return_value=VerificationResult(
        is_consistent=is_consistent, confidence=confidence, issues=[], suggestion=""
    ))
    return verifier


@pytest.mark.asyncio
async def test_refusal_when_search_required_but_empty_english():
    """When needs_search=True and results are empty, return refusal (English query)."""
    executor = _make_executor()
    verifier = _make_verifier()

    result = await secure_answer_pipeline(
        message="What is the latest TSMC stock price?",
        needs_search=True,
        normalized_results=[],
        executor=executor,
        verifier=verifier,
    )

    assert result["refused"] is True
    assert "unable" in result["refusal_message"].lower() or "unavailable" in result["refusal_message"].lower()
    # Executor should NOT have been called
    executor.execute.assert_not_called()
    verifier.verify.assert_not_called()


@pytest.mark.asyncio
async def test_refusal_when_search_required_but_empty_chinese():
    """When needs_search=True and results are empty, return refusal (Chinese query)."""
    executor = _make_executor()
    verifier = _make_verifier()

    result = await secure_answer_pipeline(
        message="台積電今天股價多少？",
        needs_search=True,
        normalized_results=[],
        executor=executor,
        verifier=verifier,
    )

    assert result["refused"] is True
    # Chinese query should get Chinese refusal
    assert any(c >= '\u4e00' and c <= '\u9fff' for c in result["refusal_message"])


@pytest.mark.asyncio
async def test_guarded_output_redacts_secrets():
    """Secret-like patterns in executor output must be redacted."""
    executor = MagicMock()
    async def mock_execute(*args, **kwargs):
        yield "key is sk-1234567890abcdefghijklmnop"
    executor.execute = MagicMock(side_effect=mock_execute)
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


@pytest.mark.asyncio
async def test_verification_runs_when_results_exist():
    """VerifierAgent must run when search results are available."""
    executor = _make_executor()
    verifier = _make_verifier()
    results = [_make_normalized_result()]

    result = await secure_answer_pipeline(
        message="TSMC stock?",
        needs_search=True,
        normalized_results=results,
        executor=executor,
        verifier=verifier,
    )

    assert result["refused"] is False
    verifier.verify.assert_called_once()
    assert result["verification"] is not None
    assert result["verification"].is_consistent is True


@pytest.mark.asyncio
async def test_verification_skipped_when_no_results():
    """VerifierAgent must NOT run when no search results (non-search query)."""
    executor = _make_executor()
    verifier = _make_verifier()

    result = await secure_answer_pipeline(
        message="Explain recursion",
        needs_search=False,
        normalized_results=[],
        executor=executor,
        verifier=verifier,
    )

    assert result["refused"] is False
    verifier.verify.assert_not_called()
    assert result["verification"] is None


@pytest.mark.asyncio
async def test_no_refusal_when_search_not_required():
    """When needs_search=False and results are empty, answer normally."""
    executor = _make_executor()
    verifier = _make_verifier()

    result = await secure_answer_pipeline(
        message="Explain recursion",
        needs_search=False,
        normalized_results=[],
        executor=executor,
        verifier=verifier,
    )

    assert result["refused"] is False
    assert result["answer"] == "Hello world"
```

**Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/pipelines/test_secure_answer.py -v`
Expected: FAIL (module not found)

**Step 4: Implement `secure_answer_pipeline`**

Write `backend/app/core/pipelines/secure_answer.py`:

```python
"""
Shared secured answer pipeline used by both chat and deep-analysis paths.

Guarantees:
1. Refusal when search is required but no results are available
2. guard_model_output() on every executor chunk
3. VerifierAgent verification when search results exist
"""
from __future__ import annotations

import re
from typing import Any

from app.core.agents.executor import ExecutorAgent
from app.core.agents.verifier import VerificationResult, VerifierAgent
from app.core.security import guard_model_output

_CJK_RANGE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

_REFUSAL_EN = (
    "I'm unable to retrieve verified up-to-date information for this query right now. "
    "Please try again later."
)
_REFUSAL_ZH = (
    "目前無法取得經過驗證的最新資訊，請稍後再試。"
)


def _detect_refusal_message(message: str) -> str:
    """Return a refusal message matching the user's language."""
    if _CJK_RANGE.search(message):
        return _REFUSAL_ZH
    return _REFUSAL_EN


async def secure_answer_pipeline(
    *,
    message: str,
    needs_search: bool,
    normalized_results: list,
    executor: ExecutorAgent,
    verifier: VerifierAgent,
    history: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Run the secured answer pipeline.

    Returns a dict with keys:
    - refused: bool
    - refusal_message: str (only if refused)
    - answer: str (only if not refused)
    - guarded_chunks: list[str] (only if not refused)
    - verification: VerificationResult | None
    """
    # Gate 1: refuse if search was required but yielded nothing
    if needs_search and not normalized_results:
        return {
            "refused": True,
            "refusal_message": _detect_refusal_message(message),
            "answer": "",
            "guarded_chunks": [],
            "verification": None,
        }

    # Gate 2: generate answer with output guarding
    guarded_chunks: list[str] = []
    async for chunk in executor.execute(
        message=message,
        search_results=normalized_results,
        history=history,
    ):
        guarded = guard_model_output(chunk)
        guarded_chunks.append(guarded)

    answer = "".join(guarded_chunks)

    # Gate 3: verify against sources when available
    verification: VerificationResult | None = None
    if normalized_results:
        verification = await verifier.verify(
            query=message,
            answer=answer,
            search_results=normalized_results,
        )

    return {
        "refused": False,
        "refusal_message": "",
        "answer": answer,
        "guarded_chunks": guarded_chunks,
        "verification": verification,
    }
```

**Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/pipelines/test_secure_answer.py -v`
Expected: All 6 tests PASS

**Step 6: Commit**

```bash
git add backend/app/core/pipelines/__init__.py backend/app/core/pipelines/secure_answer.py backend/tests/core/pipelines/__init__.py backend/tests/core/pipelines/test_secure_answer.py
git commit -m "feat: add shared secure_answer_pipeline module (Issues 1+2)"
```

---

### Task 2: Pre-filter no-URL search results and add `filter_renderable_results` helper

**Files:**
- Modify: `backend/app/core/security.py` (add filter function)
- Test: `backend/tests/core/test_security.py` (add filter tests)

**Step 1: Write failing tests**

Add to `backend/tests/core/test_security.py` (create if needed, or append):

```python
import pytest
from app.core.models.schemas import SearchResult
from app.core.security import filter_renderable_results


def test_filter_renderable_results_keeps_url_items():
    results = [
        SearchResult(title="Web", url="https://example.com", content="text", score=0.9),
        SearchResult(title="Tavily AI Answer", url="", content="summary", score=0.5),
        SearchResult(title="Also web", url="https://other.com", content="more", score=0.8),
    ]
    filtered = filter_renderable_results(results)
    assert len(filtered) == 2
    assert all(r.url for r in filtered)


def test_filter_renderable_results_empty_input():
    assert filter_renderable_results([]) == []


def test_filter_renderable_results_all_no_url():
    results = [
        SearchResult(title="AI Answer", url="", content="summary", score=0.5),
    ]
    assert filter_renderable_results(results) == []


def test_filter_renderable_results_preserves_order():
    results = [
        SearchResult(title="First", url="https://first.com", content="a", score=0.9),
        SearchResult(title="No URL", url="", content="b", score=0.5),
        SearchResult(title="Second", url="https://second.com", content="c", score=0.8),
    ]
    filtered = filter_renderable_results(results)
    assert filtered[0].title == "First"
    assert filtered[1].title == "Second"
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/test_security.py::test_filter_renderable_results_keeps_url_items -v`
Expected: FAIL (ImportError)

**Step 3: Implement `filter_renderable_results`**

Add to `backend/app/core/security.py` at the end:

```python
def filter_renderable_results(results: list[SearchResult]) -> list[SearchResult]:
    """Keep only search results that have a URL and can be rendered as citations."""
    return [r for r in results if r.url]
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/test_security.py -v -k filter_renderable`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add backend/app/core/security.py backend/tests/core/test_security.py
git commit -m "feat: add filter_renderable_results to pre-filter no-URL items (Issue 3)"
```

---

### Task 3: Integrate shared pipeline into `chat_service.py`

**Files:**
- Modify: `backend/app/core/services/chat_service.py`
- Modify: `backend/tests/core/services/test_chat_service.py`

**Step 1: Write/update failing tests**

Update `test_search_failed_event_when_search_returns_empty` in `backend/tests/core/services/test_chat_service.py` — now it should yield a refusal `ChunkEvent` instead of calling the executor:

```python
@pytest.mark.asyncio
async def test_search_required_but_empty_returns_refusal(chat_service):
    """When needs_search=True but search returns no results, refuse to answer."""
    planner_decision = PlannerDecision(
        needs_search=True,
        reasoning="Stock price query",
        search_queries=["TSMC stock price"],
        query_type="temporal",
    )

    with (
        patch.object(
            chat_service._planner, "plan",
            new_callable=AsyncMock, return_value=planner_decision,
        ),
        patch.object(
            chat_service._search, "search_multiple",
            new_callable=AsyncMock, return_value=[],
        ),
        patch.object(
            chat_service._executor, "execute",
        ) as mock_exec,
    ):
        events = []
        async for event in chat_service.process_message("TSMC stock?"):
            events.append(event)

        # Should have SearchFailedEvent
        failed_events = [e for e in events if isinstance(e, SearchFailedEvent)]
        assert len(failed_events) == 1

        # Should have a refusal ChunkEvent
        chunk_events = [e for e in events if isinstance(e, ChunkEvent)]
        assert len(chunk_events) == 1
        assert "unable" in chunk_events[0].content.lower() or "unavailable" in chunk_events[0].content.lower()

        # Executor should NOT have been called
        mock_exec.assert_not_called()

        assert isinstance(events[-1], DoneEvent)


@pytest.mark.asyncio
async def test_search_required_but_empty_returns_chinese_refusal(chat_service):
    """When needs_search=True, empty results, and Chinese query, refusal is in Chinese."""
    planner_decision = PlannerDecision(
        needs_search=True,
        reasoning="Stock price query",
        search_queries=["台積電股價"],
        query_type="temporal",
    )

    with (
        patch.object(
            chat_service._planner, "plan",
            new_callable=AsyncMock, return_value=planner_decision,
        ),
        patch.object(
            chat_service._search, "search_multiple",
            new_callable=AsyncMock, return_value=[],
        ),
    ):
        events = []
        async for event in chat_service.process_message("台積電今天股價多少"):
            events.append(event)

        chunk_events = [e for e in events if isinstance(e, ChunkEvent)]
        assert len(chunk_events) == 1
        # Chinese refusal
        assert "無法" in chunk_events[0].content or "驗證" in chunk_events[0].content
```

Also add a test for citation index alignment (Issue 3):

```python
@pytest.mark.asyncio
async def test_citation_indices_match_filtered_results(chat_service):
    """No-URL items must be filtered before executor sees them; citations align."""
    planner_decision = PlannerDecision(
        needs_search=True,
        reasoning="Need info",
        search_queries=["test"],
        query_type="factual",
    )
    # Mix of URL and no-URL results
    search_results = [
        SearchResult(title="AI Answer", url="", content="AI summary", score=0.5),
        SearchResult(title="Web Result", url="https://example.com", content="Real content", score=0.9),
    ]

    captured_results = []

    async def mock_execute(message, search_results, history=None):
        captured_results.extend(search_results)
        yield "answer [1]"

    with (
        patch.object(chat_service._planner, "plan", new_callable=AsyncMock, return_value=planner_decision),
        patch.object(chat_service._search, "search_multiple", new_callable=AsyncMock, return_value=search_results),
        patch.object(chat_service._executor, "execute", side_effect=mock_execute),
    ):
        events = []
        async for event in chat_service.process_message("test query"):
            events.append(event)

        # Executor should only see the URL item (pre-filtered)
        assert len(captured_results) == 1
        assert captured_results[0].url == "https://example.com"

        # Citations should also have only 1 item with index=1
        citation_events = [e for e in events if isinstance(e, CitationsEvent)]
        assert len(citation_events) == 1
        assert len(citation_events[0].citations) == 1
        assert citation_events[0].citations[0]["index"] == 1
        assert citation_events[0].citations[0]["url"] == "https://example.com"
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/services/test_chat_service.py::test_search_required_but_empty_returns_refusal -v`
Expected: FAIL

**Step 3: Modify `chat_service.py`**

Key changes:
1. Import `secure_answer_pipeline` and `filter_renderable_results`
2. After `normalize_search_results()`, call `filter_renderable_results()` on raw results before normalize
3. Replace the executor + verifier inline logic with `secure_answer_pipeline()`
4. On refusal, yield `SearchFailedEvent` + refusal `ChunkEvent` + `DoneEvent`

Replace lines 1-10 (imports) with:

```python
import asyncio
import ast
import logging
import re
from collections.abc import AsyncGenerator

from app.core.agents.planner import PlannerAgent
from app.core.agents.executor import ExecutorAgent
from app.core.agents.verifier import VerifierAgent
from app.core.security import (
    filter_renderable_results,
    guard_model_output,
    normalize_search_results,
    sanitize_search_results,
)
from app.core.pipelines.secure_answer import secure_answer_pipeline
from app.core.services.llm_client import LLMClient
from app.core.services.search_service import SearchService
from app.core.services.fugle_service import FugleService
from app.core.services.finnhub_service import FinnhubService
from app.core.models.schemas import SearchResult, FugleSource, FinnhubSource, RterInfoSource
from app.core.models.events import (
    ChatEvent,
    PlannerEvent,
    SearchingEvent,
    ChunkEvent,
    CitationsEvent,
    SearchFailedEvent,
    VerificationEvent,
    DoneEvent,
)
```

Replace lines 153-201 (from `all_results = data_results + search_results` to `yield DoneEvent()`) with:

```python
        all_results = data_results + search_results
        all_results = sanitize_search_results(all_results)
        # Pre-filter: remove no-URL items so LLM, verifier, and citations use the same set
        renderable_results = filter_renderable_results(all_results)
        normalized_results = normalize_search_results(renderable_results)

        # Step 2.5: Warn if search was needed but returned nothing renderable
        search_failed = decision.needs_search and not normalized_results
        if search_failed:
            logger.warning("Search returned 0 renderable results for temporal query: '%s'", message[:80])
            yield SearchFailedEvent(
                message="Web search returned no results. Unable to retrieve verified information."
            )

        # Step 3: Secured answer pipeline (refusal / guarded generation / verification)
        pipeline_result = await secure_answer_pipeline(
            message=message,
            needs_search=decision.needs_search,
            normalized_results=normalized_results,
            executor=self._executor,
            verifier=self._verifier,
            history=history,
        )

        if pipeline_result["refused"]:
            yield ChunkEvent(content=pipeline_result["refusal_message"])
            yield DoneEvent()
            return

        for chunk in pipeline_result["guarded_chunks"]:
            yield ChunkEvent(content=chunk)

        # Step 3.5: Yield verification results
        if pipeline_result["verification"] is not None:
            v = pipeline_result["verification"]
            yield VerificationEvent(
                is_consistent=v.is_consistent,
                confidence=v.confidence,
                issues=v.issues,
                suggestion=v.suggestion,
            )

        # Step 4: Send citations (from pre-filtered renderable results)
        if renderable_results:
            citations = self._executor.build_citations(renderable_results)
            yield CitationsEvent(
                citations=[
                    {"index": c.index, "title": c.title, "url": c.url, "snippet": c.snippet}
                    for c in citations
                ]
            )

        yield DoneEvent()
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/services/test_chat_service.py -v`
Expected: All tests PASS (some existing tests may need minor mock adjustments)

**Step 5: Commit**

```bash
git add backend/app/core/services/chat_service.py backend/tests/core/services/test_chat_service.py
git commit -m "refactor: integrate secure_answer_pipeline into chat_service (Issues 1-3)"
```

---

### Task 4: Integrate shared pipeline into `deep_analysis.py`

**Files:**
- Modify: `backend/app/core/tasks/deep_analysis.py`
- Modify: `backend/tests/core/tasks/test_deep_analysis.py`

**Step 1: Write failing tests**

Add to `backend/tests/core/tasks/test_deep_analysis.py`:

```python
@pytest.mark.asyncio
async def test_deep_analysis_guards_output():
    """Deep analysis must run guard_model_output on executor chunks."""
    from app.core.tasks.deep_analysis import run_deep_analysis_async

    mock_llm = MagicMock()
    mock_llm.provider_name = "openai"
    mock_llm.chat = AsyncMock(
        return_value='{"needs_search": true, "reasoning": "Need data", "search_queries": ["test"], "query_type": "temporal"}'
    )

    async def mock_stream(*args, **kwargs):
        yield "secret key sk-1234567890abcdefghijklmnop"

    mock_llm.chat_stream = MagicMock(return_value=mock_stream())

    mock_search = MagicMock()
    mock_search.search_multiple = AsyncMock(
        return_value=[
            MagicMock(title="Result", url="https://example.com", content="data", score=0.9),
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
            # Second call is the verifier response
            '{"is_consistent": true, "issues": [], "confidence": 0.95, "suggestion": ""}',
        ]
    )

    async def mock_stream(*args, **kwargs):
        yield "Answer text"

    mock_llm.chat_stream = MagicMock(return_value=mock_stream())

    mock_search = MagicMock()
    mock_search.search_multiple = AsyncMock(
        return_value=[
            MagicMock(title="Result", url="https://example.com", content="data", score=0.9),
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
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/tasks/test_deep_analysis.py -v`
Expected: FAIL

**Step 3: Modify `deep_analysis.py`**

Replace the entire file with:

```python
"""
Multi-round deep analysis task.
Runs iterative Planner -> Search -> Refine loops, then synthesizes
a final answer through the shared secured pipeline.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.agents.planner import PlannerAgent
from app.core.agents.executor import ExecutorAgent
from app.core.agents.verifier import VerifierAgent
from app.core.security import (
    filter_renderable_results,
    sanitize_search_results,
    normalize_search_results,
)
from app.core.pipelines.secure_answer import secure_answer_pipeline
from app.core.services.llm_client import LLMClient
from app.core.services.search_service import SearchService

logger = logging.getLogger(__name__)


async def run_deep_analysis_async(
    *,
    query: str,
    llm: LLMClient,
    search_service: SearchService,
    max_rounds: int = 3,
) -> dict[str, Any]:
    planner = PlannerAgent(llm=llm)
    executor = ExecutorAgent(llm=llm)
    verifier = VerifierAgent(llm=llm)
    all_search_results = []
    rounds_executed = 0
    round_logs = []
    any_round_needed_search = False

    for round_num in range(1, max_rounds + 1):
        rounds_executed = round_num
        history = []
        if round_logs:
            context = "\n".join(
                f"Round {r['round']}: searched '{', '.join(r['queries'])}' -> {r['results_count']} results"
                for r in round_logs
            )
            history = [
                {"role": "user", "content": query},
                {
                    "role": "assistant",
                    "content": f"Previous research:\n{context}\nLet me check if more search is needed.",
                },
            ]
        decision = await planner.plan(query, history if history else None)
        if not decision.needs_search:
            break
        any_round_needed_search = True
        results = await search_service.search_multiple(decision.search_queries)
        sanitized = sanitize_search_results(results)
        all_search_results.extend(sanitized)
        round_logs.append(
            {
                "round": round_num,
                "queries": decision.search_queries,
                "results_count": len(results),
                "reasoning": decision.reasoning,
            }
        )

    # Pre-filter: remove no-URL items for consistent indexing
    renderable_results = filter_renderable_results(all_search_results)
    normalized = normalize_search_results(renderable_results)

    # Use shared secured pipeline
    pipeline_result = await secure_answer_pipeline(
        message=query,
        needs_search=any_round_needed_search,
        normalized_results=normalized,
        executor=executor,
        verifier=verifier,
    )

    if pipeline_result["refused"]:
        return {
            "status": "refused",
            "query": query,
            "answer": pipeline_result["refusal_message"],
            "rounds": rounds_executed,
            "round_details": round_logs,
            "search_results": [],
            "verification": None,
        }

    verification_dict = None
    if pipeline_result["verification"] is not None:
        v = pipeline_result["verification"]
        verification_dict = {
            "is_consistent": v.is_consistent,
            "confidence": v.confidence,
            "issues": v.issues,
            "suggestion": v.suggestion,
        }

    return {
        "status": "completed",
        "query": query,
        "answer": pipeline_result["answer"],
        "rounds": rounds_executed,
        "round_details": round_logs,
        "search_results": [
            {"title": r.title, "url": r.url, "content": r.content[:200]}
            for r in renderable_results
        ],
        "verification": verification_dict,
    }


def run_deep_analysis_sync(query: str, max_rounds: int = 3) -> dict[str, Any]:
    from app.core.config import settings
    from app.core.services.llm_factory import create_llm_client

    llm = create_llm_client(settings)
    search = SearchService(api_key=settings.tavily_api_key)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            run_deep_analysis_async(
                query=query, llm=llm, search_service=search, max_rounds=max_rounds
            )
        )
    finally:
        loop.close()
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/tasks/test_deep_analysis.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/app/core/tasks/deep_analysis.py backend/tests/core/tasks/test_deep_analysis.py
git commit -m "refactor: integrate secure_answer_pipeline into deep_analysis (Issues 1+2)"
```

---

### Task 5: Fix `build_citations` to not double-filter

**Files:**
- Modify: `backend/app/core/agents/executor.py`
- Modify: `backend/tests/core/agents/test_executor.py`

Since we now pre-filter no-URL items before they reach the executor, `build_citations` no longer needs its own `if r.url` filter. Removing it ensures the indices match exactly.

**Step 1: Write a test verifying indices are correct on pre-filtered input**

Add to `backend/tests/core/agents/test_executor.py`:

```python
def test_build_citations_all_items_have_urls():
    """After pre-filtering, all items have URLs, indices are 1-based contiguous."""
    from app.core.agents.executor import ExecutorAgent
    from app.core.models.schemas import SearchResult
    from unittest.mock import MagicMock

    executor = ExecutorAgent(llm=MagicMock())
    results = [
        SearchResult(title="First", url="https://first.com", content="A", score=0.9),
        SearchResult(title="Second", url="https://second.com", content="B", score=0.8),
    ]
    citations = executor.build_citations(results)
    assert len(citations) == 2
    assert citations[0].index == 1
    assert citations[1].index == 2
```

**Step 2: Modify `build_citations`**

Change `executor.py` lines 79-89 from:

```python
    def build_citations(self, search_results: list[SearchResult]) -> list[Citation]:
        return [
            Citation(
                index=i + 1,
                title=r.title,
                url=r.url,
                snippet=r.content[:200],
            )
            for i, r in enumerate(search_results)
            if r.url  # exclude Tavily AI answer (no URL)
        ]
```

to:

```python
    def build_citations(self, search_results: list[SearchResult]) -> list[Citation]:
        """Build citations from pre-filtered search results (all must have URLs)."""
        return [
            Citation(
                index=i + 1,
                title=r.title,
                url=r.url,
                snippet=r.content[:200],
            )
            for i, r in enumerate(search_results)
        ]
```

**Step 3: Run tests**

Run: `cd backend && uv run pytest tests/core/agents/test_executor.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add backend/app/core/agents/executor.py backend/tests/core/agents/test_executor.py
git commit -m "fix: remove double-filter in build_citations, rely on pre-filtering (Issue 3)"
```

---

### Task 6: Fix `/api/notify/broadcast` storage lifecycle and remove `target=all`

**Files:**
- Modify: `backend/app/web/routes/notify.py`
- Modify: `backend/tests/web/test_notify.py`

**Step 1: Write failing tests**

Add to `backend/tests/web/test_notify.py`:

```python
def test_broadcast_rejects_target_all(client):
    """target=all is no longer valid."""
    with patch("app.core.auth.settings") as mock_settings:
        mock_settings.api_secret_key = ""
        mock_settings.frontend_url = "http://localhost:3000"
        response = client.post("/api/notify/broadcast", json={
            "message": "Test",
            "target": "all",
        }, headers={"X-API-Key": "any"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_broadcast_initializes_and_closes_storage():
    """Broadcast must call initialize() and close() on real storage."""
    import tempfile, os
    from app.telegram.storage import SubscriptionStorage

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_subs.db")
        storage = SubscriptionStorage(db_path=db_path)
        await storage.initialize()
        await storage.add(chat_id=111, topic="test", frequency="daily", time="09:00")
        await storage.close()

        # Simulate the broadcast path with real storage
        storage2 = SubscriptionStorage(db_path=db_path)
        await storage2.initialize()
        chat_ids = await storage2.get_subscriber_chat_ids()
        assert chat_ids == [111]
        await storage2.close()
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/web/test_notify.py::test_broadcast_rejects_target_all -v`
Expected: FAIL (422 not returned, currently accepts "all")

**Step 3: Modify `notify.py`**

Replace the entire file:

```python
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from telegram import Bot

from app.core.auth import require_api_key
from app.core.config import settings
from app.telegram.storage import SubscriptionStorage

logger = logging.getLogger(__name__)

router = APIRouter()


class NotifyRequest(BaseModel):
    chat_id: int
    message: str = Field(..., min_length=1)
    parse_mode: str | None = None


class BroadcastRequest(BaseModel):
    message: str = Field(..., min_length=1)
    target: str = Field(..., pattern="^subscribers$")


def get_bot() -> Bot:
    return Bot(token=settings.telegram_bot_token)


@router.post("/api/notify", dependencies=[Depends(require_api_key)])
async def notify(request: NotifyRequest):
    bot = get_bot()
    await bot.send_message(
        chat_id=request.chat_id,
        text=request.message,
        parse_mode=request.parse_mode,
    )
    return {"status": "sent"}


@router.post("/api/notify/broadcast", dependencies=[Depends(require_api_key)])
async def broadcast(request: BroadcastRequest):
    bot = get_bot()
    storage = SubscriptionStorage()
    await storage.initialize()
    try:
        chat_ids = await storage.get_subscriber_chat_ids()

        sent_count = 0
        for chat_id in chat_ids:
            try:
                await bot.send_message(chat_id=chat_id, text=request.message)
                sent_count += 1
            except Exception as e:
                logger.error("Broadcast failed for %s (%s)", chat_id, type(e).__name__)

        return {"sent_count": sent_count}
    finally:
        await storage.close()
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/web/test_notify.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/web/routes/notify.py backend/tests/web/test_notify.py
git commit -m "fix: broadcast storage init/close, remove target=all (Issue 4)"
```

---

### Task 7: Update existing test for broadcast that uses `target=subscribers`

**Files:**
- Modify: `backend/tests/web/test_notify.py`

The existing `test_broadcast_sends_to_subscribers` mocks `get_storage()` which no longer exists (we now create storage inline). Update the test to mock `SubscriptionStorage` directly.

**Step 1: Update the test**

Replace `test_broadcast_sends_to_subscribers`:

```python
def test_broadcast_sends_to_subscribers(client):
    with (
        patch("app.web.routes.notify.get_bot") as mock_get_bot,
        patch("app.web.routes.notify.SubscriptionStorage") as MockStorageCls,
        patch("app.core.auth.settings") as mock_settings,
    ):
        mock_settings.api_secret_key = ""
        mock_settings.frontend_url = "http://localhost:3000"
        mock_bot = AsyncMock()
        mock_get_bot.return_value = mock_bot

        mock_storage = AsyncMock()
        mock_storage.get_subscriber_chat_ids.return_value = [123, 456]
        MockStorageCls.return_value = mock_storage

        response = client.post("/api/notify/broadcast", json={
            "message": "Broadcast test",
            "target": "subscribers",
        }, headers={"X-API-Key": "any"})

        assert response.status_code == 200
        data = response.json()
        assert data["sent_count"] == 2
        mock_storage.initialize.assert_called_once()
        mock_storage.close.assert_called_once()
```

**Step 2: Run tests**

Run: `cd backend && uv run pytest tests/web/test_notify.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add backend/tests/web/test_notify.py
git commit -m "test: update broadcast test to verify storage lifecycle"
```

---

### Task 8: Run full backend test suite

**Step 1: Run all backend tests**

Run: `cd backend && uv run pytest -v`
Expected: All PASS

**Step 2: Fix any failures**

If existing tests fail because of the refactored chat_service (e.g., tests that mock `build_citations` on `all_results` with no-URL items), update them to account for pre-filtering.

**Step 3: Commit fixes if needed**

```bash
git add -A
git commit -m "fix: adjust tests for pre-filtered citation pipeline"
```

---

### Task 9: Run frontend tests

**Step 1: Run frontend tests**

Run: `cd frontend && npm test`
Expected: All PASS (no frontend code changes needed — the `CitationItem` type already requires `url: string`, and the backend now guarantees all citations have URLs)

---

### Task 10: Final verification and report

**Step 1: Run full test suites**

```bash
cd backend && uv run pytest -v
cd frontend && npm test
```

**Step 2: Write summary report**

Report on:
1. Which issues were fixed
2. Why each fix was implemented that way
3. Which API or schema changes were made
4. Test results
5. Remaining risks
