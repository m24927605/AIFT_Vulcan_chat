# Claude Code CLI Follow-Up Change Request

## Purpose

The previous fix set addressed the main security and logic issues. This follow-up request covers the remaining gaps found during verification.

These are not broad redesign items. They are targeted corrections to improve product consistency and test confidence.

## Remaining Issues To Fix

### 1. Localize the `search_failed` warning message

### Current problem

The refusal message is now localized for English and Chinese, but the earlier `SearchFailedEvent` warning emitted in the chat flow is still hardcoded in English.

Current behavior is inconsistent:

- refusal message: localized
- `search_failed` warning: English only

This is not a security bug, but it is a product and UX inconsistency, especially since the system explicitly tries to preserve the user's language/script.

### Required change

Update the chat flow so that the `SearchFailedEvent.message` is localized using the same language-detection rule already used by the secured refusal path.

Requirements:

- Chinese queries should receive a Chinese warning
- English queries should receive an English warning
- Do not duplicate language-detection logic in multiple places if it can be shared cleanly

Preferred approach:

- Extract or reuse a shared helper from the secure answer pipeline for language-aware fallback/refusal text

### Acceptance criteria

- A Chinese temporal query with empty search results emits a Chinese `search_failed` warning
- An English temporal query with empty search results emits an English `search_failed` warning
- Add backend tests for both cases

## 2. Add a real route-level integration test for `/api/notify/broadcast`

### Current problem

The storage lifecycle bug in `/api/notify/broadcast` has been fixed, but the current test coverage is still not strong enough at the route integration level.

Right now:

- one test mocks `SubscriptionStorage` at the route boundary
- another test validates the storage class directly

What is still missing:

- a test that exercises the actual `/api/notify/broadcast` route using a real temporary SQLite database path and verifies the route works end-to-end without mocking storage internals away

### Required change

Add an integration-style test for the broadcast route that:

- uses a temporary data directory / temporary DB file
- lets the route instantiate real `SubscriptionStorage`
- pre-populates subscriber data in that temporary DB
- calls `/api/notify/broadcast`
- verifies the route returns success and sends to the expected subscriber IDs

Requirements:

- It is acceptable to mock the Telegram bot send behavior
- Do not mock away the storage lifecycle that the route itself is responsible for
- The test should fail if `initialize()` is removed or if the route cannot access subscriber data from the real DB

### Acceptance criteria

- The broadcast route is covered by an end-to-end style test using real storage
- The test proves that route-level initialization and cleanup are functioning

## Implementation Constraints

- Keep this follow-up narrowly scoped to the two issues above
- Do not rework the already-fixed secure answer pipeline unless needed to share localization helpers cleanly
- Do not weaken existing auth/session/CSRF protections

## Suggested Files To Modify

- `backend/app/core/pipelines/secure_answer.py`
- `backend/app/core/services/chat_service.py`
- `backend/tests/core/services/test_chat_service.py`
- `backend/tests/web/test_notify.py`

## Test Requirements

Run at least:

```bash
cd backend && uv run pytest
```

If any frontend code is touched unexpectedly, also run:

```bash
cd frontend && npm test
```

## Final Deliverable Format

After finishing, report:

1. What was changed
2. Why it was changed that way
3. Which tests were added or updated
4. Which test suites were run and the results
5. Any remaining limitations
