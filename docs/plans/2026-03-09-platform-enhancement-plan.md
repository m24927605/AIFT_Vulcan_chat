# Platform Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance Vulcan with LLMOps observability, adversarial security testing, async task execution, and multi-step agent verification to improve production readiness.

**Architecture:** Four independent features, each as a separate commit: (1) Langfuse tracing for all LLM calls with evaluation dataset, (2) Red-team adversarial test suite for prompt injection defense, (3) Celery + Redis async task queue for long-running analysis, (4) Verifier agent for hallucination detection in multi-step workflows.

**Tech Stack:** Python, FastAPI, Langfuse SDK, Celery, Redis, pytest

---

## Commit 1: Langfuse Integration (LLMOps Observability)

### Task 1.1: Add Langfuse dependency and configuration

**Files:**
- Modify: `backend/pyproject.toml` (add langfuse dependency)
- Modify: `backend/app/core/config.py` (add Langfuse settings)

**Step 1: Add langfuse to dependencies**

In `backend/pyproject.toml`, add to `dependencies`:
```
"langfuse>=2.0.0",
```

**Step 2: Add config fields**

In `backend/app/core/config.py`, add to `Settings`:
```python
langfuse_public_key: str = ""
langfuse_secret_key: str = ""
langfuse_host: str = "https://cloud.langfuse.com"
```

**Step 3: Verify import works**

Run: `cd /Users/sin-chengchen/office-project/AIFT/Vulcan/backend && pip install langfuse>=2.0.0`

---

### Task 1.2: Create Langfuse tracing service

**Files:**
- Create: `backend/app/core/services/tracing.py`
- Test: `backend/tests/core/services/test_tracing.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/services/test_tracing.py
import pytest
from unittest.mock import patch, MagicMock

from app.core.services.tracing import get_tracer, TracingService


def test_tracing_service_disabled_when_no_keys():
    tracer = TracingService(public_key="", secret_key="")
    assert tracer.enabled is False


def test_tracing_service_enabled_when_keys_present():
    with patch("app.core.services.tracing.Langfuse") as MockLangfuse:
        MockLangfuse.return_value = MagicMock()
        tracer = TracingService(public_key="pk-test", secret_key="sk-test")
        assert tracer.enabled is True


def test_get_tracer_returns_singleton():
    t1 = get_tracer()
    t2 = get_tracer()
    assert t1 is t2


def test_trace_llm_call_noop_when_disabled():
    tracer = TracingService(public_key="", secret_key="")
    ctx = tracer.trace_llm_call(
        name="test", model="gpt-4o", input_text="hi",
        output_text="hello", temperature=0.3,
    )
    assert ctx is None


def test_trace_llm_call_creates_generation_when_enabled():
    with patch("app.core.services.tracing.Langfuse") as MockLangfuse:
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_client.trace.return_value = mock_trace
        MockLangfuse.return_value = mock_client

        tracer = TracingService(public_key="pk-test", secret_key="sk-test")
        tracer.trace_llm_call(
            name="planner",
            model="gpt-4o",
            input_text="What is TSMC?",
            output_text='{"needs_search": true}',
            temperature=0.1,
            latency_ms=150.0,
            tokens_input=50,
            tokens_output=20,
            metadata={"agent": "planner"},
        )
        mock_client.trace.assert_called_once()
        mock_trace.generation.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/sin-chengchen/office-project/AIFT/Vulcan/backend && python -m pytest tests/core/services/test_tracing.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

```python
# backend/app/core/services/tracing.py
"""Lightweight Langfuse tracing wrapper for LLM observability."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_singleton: TracingService | None = None


class TracingService:
    """Wraps Langfuse SDK.  No-ops gracefully when keys are missing."""

    def __init__(
        self,
        public_key: str = "",
        secret_key: str = "",
        host: str = "https://cloud.langfuse.com",
    ):
        self._client = None
        if public_key and secret_key:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                )
                logger.info("Langfuse tracing enabled")
            except Exception:
                logger.warning("Langfuse init failed; tracing disabled", exc_info=True)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def trace_llm_call(
        self,
        *,
        name: str,
        model: str,
        input_text: str,
        output_text: str,
        temperature: float = 0.3,
        latency_ms: float | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any | None:
        if not self._client:
            return None
        try:
            trace = self._client.trace(name=name, metadata=metadata or {})
            trace.generation(
                name=name,
                model=model,
                input=input_text,
                output=output_text,
                model_parameters={"temperature": temperature},
                usage={
                    "input": tokens_input,
                    "output": tokens_output,
                },
                metadata={
                    "latency_ms": latency_ms,
                    **(metadata or {}),
                },
            )
            return trace
        except Exception:
            logger.warning("Langfuse trace failed", exc_info=True)
            return None

    def flush(self) -> None:
        if self._client:
            self._client.flush()


def get_tracer() -> TracingService:
    global _singleton
    if _singleton is None:
        from app.core.config import settings

        _singleton = TracingService(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    return _singleton
```

**Step 4: Run tests**

Run: `cd /Users/sin-chengchen/office-project/AIFT/Vulcan/backend && python -m pytest tests/core/services/test_tracing.py -v`
Expected: PASS

---

### Task 1.3: Instrument Planner and Executor with tracing

**Files:**
- Modify: `backend/app/core/agents/planner.py` (add tracing calls)
- Modify: `backend/app/core/agents/executor.py` (add tracing calls)
- Test: `backend/tests/core/agents/test_planner.py` (add tracing test)
- Test: `backend/tests/core/agents/test_executor.py` (add tracing test)

**Step 1: Write the failing tests**

Append to `backend/tests/core/agents/test_planner.py`:
```python
@pytest.mark.asyncio
async def test_planner_calls_tracing_service(planner, mock_llm):
    mock_llm.chat.return_value = _mock_planner_response(True, "temporal")
    with patch("app.core.agents.planner.get_tracer") as mock_get_tracer:
        mock_tracer = MagicMock()
        mock_get_tracer.return_value = mock_tracer
        await planner.plan("TSMC stock?")
        mock_tracer.trace_llm_call.assert_called_once()
        call_kwargs = mock_tracer.trace_llm_call.call_args.kwargs
        assert call_kwargs["name"] == "planner"
        assert "TSMC stock?" in call_kwargs["input_text"]
```

Append to `backend/tests/core/agents/test_executor.py`:
```python
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
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/sin-chengchen/office-project/AIFT/Vulcan/backend && python -m pytest tests/core/agents/test_planner.py::test_planner_calls_tracing_service tests/core/agents/test_executor.py::test_executor_calls_tracing_after_stream -v`
Expected: FAIL

**Step 3: Instrument planner.py**

In `backend/app/core/agents/planner.py`, add import at top:
```python
import time
from app.core.services.tracing import get_tracer
```

Replace the `plan` method body (lines 57-93) with tracing:
```python
    async def plan(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> PlannerDecision:
        messages = list(history or [])
        messages.append({"role": "user", "content": message})

        t0 = time.perf_counter()
        try:
            response = await self._llm.chat(
                system_prompt=PLANNER_SYSTEM_PROMPT,
                messages=messages,
                temperature=0.1,
            )
            latency_ms = (time.perf_counter() - t0) * 1000
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                cleaned = cleaned.rsplit("```", 1)[0]
                cleaned = cleaned.strip()

            data = json.loads(cleaned)
            decision = PlannerDecision(**data)

            get_tracer().trace_llm_call(
                name="planner",
                model=self._llm.provider_name,
                input_text=message,
                output_text=response,
                temperature=0.1,
                latency_ms=latency_ms,
                metadata={"agent": "planner", "decision": data},
            )

            return decision
        except (json.JSONDecodeError, Exception) as e:
            latency_ms = (time.perf_counter() - t0) * 1000
            logger.warning(f"Planner failed to parse response: {e}")

            get_tracer().trace_llm_call(
                name="planner",
                model=self._llm.provider_name,
                input_text=message,
                output_text=str(e),
                temperature=0.1,
                latency_ms=latency_ms,
                metadata={"agent": "planner", "error": str(e)},
            )

            if _is_low_risk_query(message):
                return PlannerDecision(
                    needs_search=False,
                    reasoning="Planner parse failed on low-risk query; falling back to direct answer",
                    search_queries=[],
                    query_type="conversational",
                )
            return PlannerDecision(
                needs_search=True,
                reasoning="Failed to analyze query, defaulting to search",
                search_queries=[message],
                query_type="factual",
            )
```

**Step 4: Instrument executor.py**

In `backend/app/core/agents/executor.py`, add import at top:
```python
import time
from app.core.services.tracing import get_tracer
```

Replace the `execute` method body (lines 37-58) with tracing:
```python
    async def execute(
        self,
        message: str,
        search_results: list[NormalizedSearchResult],
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        if search_results:
            formatted = self._format_search_results(search_results)
            system_prompt = EXECUTOR_SYSTEM_PROMPT_WITH_SEARCH.format(
                search_results=formatted
            )
        else:
            system_prompt = EXECUTOR_SYSTEM_PROMPT_NO_SEARCH

        messages = list(history or [])
        messages.append({"role": "user", "content": message})

        t0 = time.perf_counter()
        full_output = []
        async for chunk in self._llm.chat_stream(
            system_prompt=system_prompt,
            messages=messages,
        ):
            full_output.append(chunk)
            yield chunk

        latency_ms = (time.perf_counter() - t0) * 1000
        get_tracer().trace_llm_call(
            name="executor",
            model=self._llm.provider_name,
            input_text=message,
            output_text="".join(full_output),
            temperature=0.7,
            latency_ms=latency_ms,
            metadata={
                "agent": "executor",
                "has_search_results": bool(search_results),
                "num_results": len(search_results),
            },
        )
```

**Step 5: Run all agent tests**

Run: `cd /Users/sin-chengchen/office-project/AIFT/Vulcan/backend && python -m pytest tests/core/agents/ -v`
Expected: PASS

---

### Task 1.4: Add Planner evaluation dataset and scoring script

**Files:**
- Create: `backend/evals/planner_eval_dataset.json`
- Create: `backend/evals/run_planner_eval.py`
- Test: `backend/tests/evals/test_planner_eval.py`

**Step 1: Write the failing test**

```python
# backend/tests/evals/test_planner_eval.py
import json
import pytest
from pathlib import Path


def test_eval_dataset_is_valid_json():
    dataset_path = Path(__file__).resolve().parents[2] / "evals" / "planner_eval_dataset.json"
    assert dataset_path.exists(), f"Missing eval dataset: {dataset_path}"
    data = json.loads(dataset_path.read_text())
    assert isinstance(data, list)
    assert len(data) >= 15


def test_eval_dataset_has_required_fields():
    dataset_path = Path(__file__).resolve().parents[2] / "evals" / "planner_eval_dataset.json"
    data = json.loads(dataset_path.read_text())
    for i, case in enumerate(data):
        assert "query" in case, f"Case {i} missing 'query'"
        assert "expected_needs_search" in case, f"Case {i} missing 'expected_needs_search'"
        assert "expected_query_type" in case, f"Case {i} missing 'expected_query_type'"
        assert "category" in case, f"Case {i} missing 'category'"
        assert isinstance(case["expected_needs_search"], bool)


def test_eval_dataset_covers_all_categories():
    dataset_path = Path(__file__).resolve().parents[2] / "evals" / "planner_eval_dataset.json"
    data = json.loads(dataset_path.read_text())
    categories = {case["category"] for case in data}
    required = {"temporal", "factual", "conversational", "greeting", "math", "tw_stock", "us_stock", "forex"}
    assert required.issubset(categories), f"Missing categories: {required - categories}"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/sin-chengchen/office-project/AIFT/Vulcan/backend && python -m pytest tests/evals/test_planner_eval.py -v`
Expected: FAIL

**Step 3: Create eval dataset**

Create `backend/evals/planner_eval_dataset.json` with 20 test cases covering categories: tw_stock, us_stock, forex, temporal, factual, conversational, greeting, math.

**Step 4: Create eval runner script**

Create `backend/evals/run_planner_eval.py` with:
- `load_dataset()` to read the JSON
- `score_results()` to compute needs_search accuracy, query_type accuracy, data_source accuracy
- `run_eval()` async function that runs PlannerAgent against each case
- `--dry-run` flag for printing dataset stats only

**Step 5: Run eval tests**

Run: `cd /Users/sin-chengchen/office-project/AIFT/Vulcan/backend && python -m pytest tests/evals/test_planner_eval.py -v`
Expected: PASS

**Step 6: Run all backend tests**

Run: `cd /Users/sin-chengchen/office-project/AIFT/Vulcan/backend && python -m pytest -v`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add backend/pyproject.toml backend/app/core/config.py \
  backend/app/core/services/tracing.py \
  backend/app/core/agents/planner.py backend/app/core/agents/executor.py \
  backend/evals/ backend/tests/core/services/test_tracing.py \
  backend/tests/evals/test_planner_eval.py
git commit -m "feat: add Langfuse LLMOps tracing and planner evaluation pipeline"
```

---

## Commit 2: Adversarial Testing Pipeline

### Task 2.1: Create adversarial attack dataset

**Files:**
- Create: `backend/evals/adversarial_dataset.json`

Create 28 attack cases across 7 categories:
- `jailbreak` (3): DAN, role-play, safety bypass
- `prompt_leaking` (4): system prompt, hidden prompt, CoT, tool instructions
- `instruction_override` (3): ignore instructions, disregard, fake system message
- `data_exfiltration` (4): API key, env var, bearer token, exfiltration command
- `indirect_injection` (4): malicious search result content, fake developer messages
- `encoding_bypass` (3): mixed case, Chinese language, multilingual
- `output_attack` (4): OpenAI key, session token, bearer token, API key assignment in model output
- `benign` (3): legitimate queries that should NOT be filtered

Each case has: `id`, `category`, `attack`, `description`, `expected_behavior` (one of: `filtered_or_refused`, `filtered_in_search`, `redacted_in_output`, `not_filtered`).

---

### Task 2.2: Write adversarial test suite

**Files:**
- Create: `backend/tests/evals/test_adversarial.py`

**Step 1: Write the adversarial tests**

Test classes:
1. `TestInputSanitization` — parametrized over `filtered_in_search` cases, verifies `[filtered]` appears after `sanitize_search_results()`
2. `TestOutputGuard` — parametrized over `redacted_in_output` cases, verifies `[REDACTED` appears after `guard_model_output()`
3. `TestBenignInputsNotFiltered` — parametrized over `not_filtered` cases, verifies at least 50% of original words survive sanitization
4. `TestPlannerResilience` — parametrized over `filtered_or_refused` cases, verifies planner produces valid `PlannerDecision` (doesn't crash or leak)
5. `TestAdversarialReport` — validates dataset has ≥25 cases across ≥5 categories, prints coverage report

**Step 2: Run adversarial tests**

Run: `cd /Users/sin-chengchen/office-project/AIFT/Vulcan/backend && python -m pytest tests/evals/test_adversarial.py -v -s`
Expected: PASS

**Step 3: Run all backend tests**

Run: `cd /Users/sin-chengchen/office-project/AIFT/Vulcan/backend && python -m pytest -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add backend/evals/adversarial_dataset.json \
  backend/tests/evals/test_adversarial.py
git commit -m "feat: add adversarial testing pipeline for prompt injection defense"
```

---

## Commit 3: Celery Task Queue for Async AI Tasks

### Task 3.1: Add Celery + Redis dependencies and configuration

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`
- Create: `backend/app/core/celery_app.py`
- Test: `backend/tests/core/test_celery_app.py`

**Step 1: Write the failing test**

```python
# backend/tests/core/test_celery_app.py
def test_celery_app_configurable():
    from app.core.celery_app import create_celery_app
    app = create_celery_app(broker_url="redis://localhost:6379/0")
    assert app.main == "vulcan"
    assert "redis" in app.conf.broker_url


def test_celery_app_defaults_to_settings():
    with patch("app.core.celery_app.settings") as mock_settings:
        mock_settings.celery_broker_url = "redis://test:6379/0"
        mock_settings.celery_result_backend = "redis://test:6379/1"
        from app.core.celery_app import create_celery_app
        app = create_celery_app()
        assert app.conf.broker_url == "redis://test:6379/0"
```

**Step 2: Add dependencies and config**

In `backend/pyproject.toml` add: `"celery[redis]>=5.3.0"`, `"redis>=5.0.0"`

In `backend/app/core/config.py` add:
```python
celery_broker_url: str = "redis://localhost:6379/0"
celery_result_backend: str = "redis://localhost:6379/1"
```

**Step 3: Create celery app**

```python
# backend/app/core/celery_app.py
from celery import Celery
from app.core.config import settings

def create_celery_app(broker_url=None, result_backend=None) -> Celery:
    app = Celery("vulcan")
    app.conf.broker_url = broker_url or settings.celery_broker_url
    app.conf.result_backend = result_backend or settings.celery_result_backend
    app.conf.task_serializer = "json"
    app.conf.result_serializer = "json"
    app.conf.accept_content = ["json"]
    app.conf.task_track_started = True
    app.conf.task_time_limit = 300
    app.conf.task_soft_time_limit = 240
    return app

celery_app = create_celery_app()
```

**Step 4: Run tests**

Run: `cd /Users/sin-chengchen/office-project/AIFT/Vulcan/backend && python -m pytest tests/core/test_celery_app.py -v`
Expected: PASS

---

### Task 3.2: Create deep analysis task

**Files:**
- Create: `backend/app/core/tasks/__init__.py`
- Create: `backend/app/core/tasks/deep_analysis.py`
- Test: `backend/tests/core/tasks/test_deep_analysis.py`

**Step 1: Write the failing test**

3 test cases:
- `test_deep_analysis_runs_multi_step` — mock planner returns 2 rounds of search, verify rounds=2 and accumulated results
- `test_deep_analysis_stops_when_no_search_needed` — planner says no search on round 1, verify rounds=1 and search not called
- `test_deep_analysis_accumulates_search_results` — verify results from multiple rounds are combined

**Step 2: Write implementation**

`run_deep_analysis_async()`:
1. Loop up to `max_rounds`
2. Each round: call Planner with accumulated context
3. If planner says no search → break
4. Otherwise: search, sanitize, accumulate
5. After loop: call Executor with all accumulated results
6. Return structured result dict

`run_deep_analysis_sync()`: synchronous wrapper for Celery workers (creates event loop).

**Step 3: Run tests**

Run: `cd /Users/sin-chengchen/office-project/AIFT/Vulcan/backend && python -m pytest tests/core/tasks/test_deep_analysis.py -v`
Expected: PASS

---

### Task 3.3: Register Celery task and create API endpoint

**Files:**
- Create: `backend/app/core/tasks/celery_tasks.py`
- Create: `backend/app/web/routes/analysis.py`
- Modify: `backend/app/web/main.py` (register router)
- Test: `backend/tests/web/test_analysis.py`

**Step 1: Write the failing test**

4 test cases:
- `test_submit_analysis_returns_task_id` — POST /api/analysis → 202 with task_id
- `test_get_analysis_status_pending` — GET /api/analysis/{id} → status=PENDING
- `test_get_analysis_status_completed` — GET /api/analysis/{id} → status=SUCCESS with result
- `test_submit_analysis_validates_query_length` — empty query → 422

**Step 2: Create Celery task**

```python
# backend/app/core/tasks/celery_tasks.py
@celery_app.task(name="deep_analysis", bind=True, max_retries=1)
def deep_analysis_task(self, query, max_rounds=3):
    return run_deep_analysis_sync(query=query, max_rounds=max_rounds)
```

**Step 3: Create API routes**

- `POST /api/analysis` → enqueue task, return 202 with task_id
- `GET /api/analysis/{task_id}` → return task status and result

**Step 4: Register router in main.py**

**Step 5: Run all backend tests**

Run: `cd /Users/sin-chengchen/office-project/AIFT/Vulcan/backend && python -m pytest -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/pyproject.toml backend/app/core/config.py \
  backend/app/core/celery_app.py \
  backend/app/core/tasks/ \
  backend/app/web/routes/analysis.py \
  backend/app/web/main.py \
  backend/tests/core/test_celery_app.py \
  backend/tests/core/tasks/ \
  backend/tests/web/test_analysis.py
git commit -m "feat: add Celery task queue with deep analysis async pipeline"
```

---

## Commit 4: Verifier Agent for Hallucination Detection

### Task 4.1: Create Verifier Agent

**Files:**
- Create: `backend/app/core/agents/verifier.py`
- Test: `backend/tests/core/agents/test_verifier.py`

**Step 1: Write the failing test**

5 test cases:
- `test_verifier_approves_consistent_answer` — answer matches sources → is_consistent=True
- `test_verifier_detects_hallucinated_number` — wrong number → is_consistent=False with issues
- `test_verifier_handles_invalid_json` — parse failure → conservative fallback (is_consistent=False, confidence=0.0)
- `test_verifier_passes_with_no_search_results` — general knowledge answer → is_consistent=True
- `test_verifier_calls_tracing` — verify Langfuse trace is called

**Step 2: Write implementation**

System prompt instructs the verifier to:
1. Compare every number/statistic in the answer against search results
2. Flag unsupported claims
3. Check citation markers reference correct sources
4. Return JSON: `{is_consistent, issues, confidence, suggestion}`

Temperature: 0.1 (deterministic verification)

**Step 3: Run tests**

Run: `cd /Users/sin-chengchen/office-project/AIFT/Vulcan/backend && python -m pytest tests/core/agents/test_verifier.py -v`
Expected: PASS

---

### Task 4.2: Integrate Verifier into ChatService

**Files:**
- Modify: `backend/app/core/models/events.py` (add VerificationEvent)
- Modify: `backend/app/core/services/chat_service.py` (add verifier step)
- Modify: `backend/app/web/routes/chat.py` (serialize VerificationEvent)
- Modify: `backend/tests/core/services/test_chat_service.py` (add verifier tests)

**Step 1: Write the failing tests**

2 test cases:
- `test_chat_service_runs_verifier_after_search` — when search was used, VerificationEvent is emitted
- `test_chat_service_skips_verifier_when_no_search` — when no search, no VerificationEvent

**Step 2: Add VerificationEvent**

```python
@dataclass
class VerificationEvent:
    is_consistent: bool
    confidence: float
    issues: list[str]
    suggestion: str
```

Update `ChatEvent` union to include `VerificationEvent`.

**Step 3: Update ChatService**

- Add `self._verifier = VerifierAgent(llm=llm)` in `__init__`
- After executor streaming, collect `answer_chunks`
- If `normalized_results` is non-empty: call `self._verifier.verify()` and yield `VerificationEvent`

**Step 4: Update SSE serialization**

Add `VerificationEvent` handling in chat route SSE generator.

**Step 5: Run ALL backend tests**

Run: `cd /Users/sin-chengchen/office-project/AIFT/Vulcan/backend && python -m pytest -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/app/core/agents/verifier.py \
  backend/app/core/models/events.py \
  backend/app/core/services/chat_service.py \
  backend/app/web/routes/chat.py \
  backend/tests/core/agents/test_verifier.py \
  backend/tests/core/services/test_chat_service.py
git commit -m "feat: add Verifier agent for hallucination detection and multi-step workflow"
```

---

## Summary

| Commit | Feature | Files Created | Files Modified | Tests Added |
|--------|---------|---------------|----------------|-------------|
| 1 | Langfuse LLMOps tracing + eval | 4 | 4 | 3 test files |
| 2 | Adversarial testing pipeline | 2 | 0 | 1 test file |
| 3 | Celery async task queue | 5 | 3 | 3 test files |
| 4 | Verifier agent + multi-step | 1 | 3 | 2 test files |
