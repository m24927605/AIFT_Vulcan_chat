# Claude Code CLI Change Request

## Purpose

This document describes the required code changes for Claude Code CLI based on a full code review of this project.

The main goal is to fix security and business-logic issues, not just to make tests pass. The current system has inconsistent security guarantees across different execution paths, and several behaviors create false confidence for a security-focused interview setting.

Project roots:

- Backend: `backend/`
- Frontend: `frontend/`

## Required Outcomes

Claude Code CLI must fix these four issue groups:

1. The `deep analysis` path does not enforce the same output-security guarantees as the main chat path.
2. When search is required but fails, the system still falls back to free-form model answering.
3. Citation indices can become misaligned with the source cards shown in the UI.
4. The `/api/notify/broadcast` path has an incomplete storage lifecycle and inconsistent API behavior.

## Issue 1: Make `/api/analysis` enforce the same output security as `/api/chat`

### Current problem

The main chat flow applies:

- `guard_model_output()` before returning model output
- `VerifierAgent` when search results exist

The background deep-analysis flow currently returns raw executor output and skips those protections.

This means `/api/analysis` is a lower-security path than `/api/chat`, which is not acceptable.

### Required change

Update `backend/app/core/tasks/deep_analysis.py` so that the deep-analysis path matches the protections in `backend/app/core/services/chat_service.py`.

Requirements:

- Apply `guard_model_output()` to the final generated answer
- Run `VerifierAgent` when search results are available
- Include verification results in the task result payload
- If search fails or returns no results for a query that requires search, expose that state explicitly instead of silently degrading

If needed, extract shared helper logic so chat and analysis do not drift apart again.

### Acceptance criteria

- `/api/analysis` must not provide weaker output protection than `/api/chat`
- Add tests to verify:
  - secret-like output is redacted
  - verification runs when search results exist
  - task results include verification output, or a clear reason why it is absent

## Issue 2: Do not answer “latest/current” questions when required search fails

### Current problem

In `ChatService.process_message()`, if a query is classified as requiring search, but all search/data-source calls fail, the system still lets the executor answer without search results.

For queries like:

- latest news
- live stock price
- exchange rate
- current events

this is a business-logic failure and a trust failure. A warning banner is not enough.

### Required change

Update `backend/app/core/services/chat_service.py`:

- If `needs_search=True` and final `all_results` is empty, do not fall back to “answer from model knowledge”
- Return a clear failure response stating that verified up-to-date information is currently unavailable

Apply the same rule to the deep-analysis flow as well.

Do not change the existing fast-path behavior for:

- greetings
- simple arithmetic
- normal non-search queries

### Acceptance criteria

- For temporal/current/latest queries, if external data retrieval fails, the system must refuse to provide a substantive answer
- It must instead return a clear “unable to retrieve verified up-to-date information” style response
- Add tests for both chat and deep-analysis paths

## Issue 3: Fix citation index drift between backend and frontend

### Current problem

The result set may include entries such as `Tavily AI Answer` with no URL.

Today:

- the LLM sees indices based on the full result list
- `build_citations()` removes no-URL items
- the frontend only renders the remaining items

This means `[1]`, `[2]`, etc. in the answer may not match the source cards shown to the user.

### Required change

Redesign citation/index handling so it is globally consistent.

Implement one of these two approaches:

- Option A: Only index sources that are actually renderable in the UI, and use the exact same indexed set for both LLM prompting and frontend display
- Option B: Keep all indexed items, but render all of them in the frontend as well; if an item has no URL, display it explicitly as an AI summary or non-web source instead of dropping it

Additional requirement:

- If `Tavily AI Answer` or similar generated content is kept, it must be clearly labeled as AI-generated summary, not primary source material

### Acceptance criteria

- It must no longer be possible for answer citations to point to indices that are missing or shifted in the UI
- Add tests to verify:
  - mixed URL / no-URL result sets still keep correct citation alignment
  - backend and frontend interpret citation indices consistently

## Issue 4: Fix `/api/notify/broadcast` storage initialization and target semantics

### Current problem

`backend/app/web/routes/notify.py` currently:

- creates `SubscriptionStorage()` without calling `initialize()`
- accepts `target=all|subscribers`, but does not actually implement different behavior

The current tests mostly mock storage, so they do not catch the real initialization failure path.

### Required change

Update `backend/app/web/routes/notify.py`:

- ensure `SubscriptionStorage` is initialized before use
- close resources properly after use
- define and implement correct behavior for `target`

Rules:

- If the product does not actually support `target=all`, remove that option from the schema and update tests
- If `target=all` is kept, implement it for real

Do not leave a schema option that is accepted but ignored.

### Acceptance criteria

- The broadcast API must work with the real storage path, not only with mocks
- The `target` field must match actual runtime behavior
- Add tests that would fail if storage initialization is missing

## Engineering Requirements

### Testing

After implementation, run at least:

```bash
cd backend && uv run pytest
cd frontend && npm test
```

If citation rendering changes in the UI, add or update frontend component/integration tests as needed.

### Implementation expectations

- Prefer shared logic over duplicated logic
- Do not weaken the existing session, CSRF, or ownership protections
- Do not paper over the issue with comments; fix the behavior
- If response schemas change, update:
  - backend tests
  - frontend types
  - frontend consumers

## Out of Scope

These do not need to be addressed in this change set:

- tightening frontend CSP further
- rotating local `.env` secrets

## Suggested Files To Modify

Start with these files:

- `backend/app/core/services/chat_service.py`
- `backend/app/core/tasks/deep_analysis.py`
- `backend/app/core/agents/executor.py`
- `backend/app/web/routes/analysis.py`
- `backend/app/web/routes/notify.py`
- `backend/tests/core/services/test_chat_service.py`
- `backend/tests/core/tasks/test_deep_analysis.py`
- `backend/tests/web/test_notify.py`
- `frontend/src/lib/types.ts`
- `frontend/src/components/CitationList.tsx`
- `frontend/src/components/CitationCard.tsx`
- `frontend/src/__tests__/CitationCard.test.tsx`

## Final Deliverable Format

After finishing the work, Claude Code CLI should report:

1. Which issues were fixed
2. Why each fix was implemented that way
3. Which API or schema changes were made
4. Which tests were run and their results
5. Any remaining risks or limitations
