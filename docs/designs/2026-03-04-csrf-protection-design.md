# CSRF Double-Submit Cookie Protection

**Date:** 2026-03-04
**Status:** Approved

## Problem

Web session uses cookie-based authentication with `SameSite=None` (required for cross-origin deployment). Without CSRF protection, state-mutating API calls could be forged by a malicious site if a user visits it while authenticated.

## Solution: Double-Submit Cookie

### Backend

1. **Set CSRF cookie:** When `ensure_web_session` sets/rotates the session cookie, also set a `csrf_token` cookie:
   - Value: `secrets.token_urlsafe(32)`
   - HttpOnly: **False** (frontend JS must read it)
   - Secure / SameSite / Path / Max-Age: same as session cookie

2. **Verify CSRF on mutating requests:** Add a `verify_csrf` dependency that:
   - Reads `X-CSRF-Token` from request header
   - Reads `csrf_token` from request cookie
   - Compares with `hmac.compare_digest` (timing-safe)
   - Returns 403 if missing or mismatched

3. **Apply to:** All POST/DELETE endpoints that use cookie session:
   - `POST /api/conversations`
   - `DELETE /api/conversations/{id}`
   - `POST /api/conversations/{id}/telegram-link/request`
   - `POST /api/conversations/{id}/unlink-telegram`
   - `POST /api/chat`

4. **Exempt:** `/api/notify` and `/api/notify/broadcast` (use API key, not cookie session)

### Frontend

1. **Helper function** `getCsrfToken()`: reads `csrf_token` from `document.cookie`
2. **All mutating fetches** add `"X-CSRF-Token": getCsrfToken()` header
3. **Files:** `api.ts`, `useSSE.ts`

### CORS

Add `"X-CSRF-Token"` to `allow_headers` in CORS config (currently `["*"]` so already covered, but explicit is better if tightened later).

## Files Changed

**Backend:**
- `backend/app/core/web_session.py` — add `CSRF_COOKIE_NAME`, set csrf cookie in `_set_cookie`, add `verify_csrf` dependency
- `backend/app/web/routes/conversations.py` — add `Depends(verify_csrf)` to mutating endpoints
- `backend/app/web/routes/chat.py` — add `Depends(verify_csrf)` to chat endpoint
- `backend/tests/` — CSRF verification tests

**Frontend:**
- `frontend/src/lib/api.ts` — add `getCsrfToken()`, add header to all mutating calls
- `frontend/src/hooks/useSSE.ts` — add CSRF header to chat fetch

## Test Plan

- CSRF cookie is set when session is created
- CSRF cookie rotates when session rotates
- Correct X-CSRF-Token header → request passes
- Missing X-CSRF-Token header → 403
- Mismatched token → 403
- GET requests → no CSRF check needed
- API-key endpoints → no CSRF check
