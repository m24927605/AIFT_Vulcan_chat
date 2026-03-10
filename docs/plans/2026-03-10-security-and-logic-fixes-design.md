# Security and Logic Fixes — Design Document

Date: 2026-03-10

## Overview

Fix 4 issue groups identified in the code review: output security parity, search-fail refusal, citation index drift, and broadcast storage lifecycle.

## Issue 1 + 2: Shared Secure Answer Pipeline

**Decision:** Extract a shared helper `secure_execute_and_verify()` that covers the full secured answer path:

1. **Refusal gate:** If `needs_search=True` and `all_results` is empty, return a localized refusal message — do not invoke the executor
2. **Guarded generation:** Run executor and apply `guard_model_output()` to each chunk
3. **Verification:** Run `VerifierAgent.verify()` when search results exist, include results in output

Both `chat_service.py` and `deep_analysis.py` call this shared helper. The refusal message must respect the user's language (not hardcoded English).

## Issue 3: Citation Index Alignment (Option A)

**Decision:** Filter no-URL items **before** they reach any consumer. The same filtered+indexed source set is used by:

- LLM prompt input (executor)
- Verifier input
- Citation payload (build_citations)
- Frontend rendering

Implementation: filter in `chat_service.py` / `deep_analysis.py` right after `normalize_search_results()`, before passing to executor or verifier. `build_citations()` no longer needs its own filter since input is pre-filtered.

## Issue 4: Broadcast Storage Lifecycle

**Decision:**
- Remove `target=all` from schema (no real "all users" concept)
- Use async context manager for `SubscriptionStorage` initialization and cleanup
- Ensure `initialize()` is called before queries, `close()` after

## Non-goals

- CSP tightening
- .env secret rotation
