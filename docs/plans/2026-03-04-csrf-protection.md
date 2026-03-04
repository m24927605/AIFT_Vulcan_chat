# CSRF Double-Submit Cookie Protection — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add CSRF protection using the double-submit cookie pattern to all state-mutating endpoints.

**Architecture:** Backend sets a non-HttpOnly `csrf_token` cookie alongside the session cookie. Frontend reads it via `document.cookie` and sends it as `X-CSRF-Token` header. Backend validates header matches cookie on POST/DELETE requests. A FastAPI dependency `verify_csrf` performs the check.

**Tech Stack:** Python/FastAPI (backend), TypeScript/React (frontend), vitest (frontend tests), pytest (backend tests)

---

### Task 1: Backend — Write failing tests for CSRF cookie and verification

**Files:**
- Modify: `backend/tests/core/test_web_session.py`

**Step 1: Write the failing tests**

Add these imports and tests to `backend/tests/core/test_web_session.py`:

```python
from app.core.web_session import _cookie_samesite, _is_secure, CSRF_COOKIE_NAME, verify_csrf
```

Update import line (replace the existing import).

Add these tests:

```python
# --- CSRF tests ---

def test_csrf_cookie_name_constant():
    assert CSRF_COOKIE_NAME == "csrf_token"


@pytest.mark.anyio
async def test_verify_csrf_passes_with_matching_token():
    req = _make_request(
        "http://localhost:8000",
        extra_headers=[
            (b"x-csrf-token", b"abc123"),
            (b"cookie", b"csrf_token=abc123"),
        ],
    )
    # Should not raise
    await verify_csrf(req)


@pytest.mark.anyio
async def test_verify_csrf_rejects_missing_header():
    req = _make_request(
        "http://localhost:8000",
        extra_headers=[
            (b"cookie", b"csrf_token=abc123"),
        ],
    )
    with pytest.raises(HTTPException) as exc_info:
        await verify_csrf(req)
    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_verify_csrf_rejects_missing_cookie():
    req = _make_request(
        "http://localhost:8000",
        extra_headers=[
            (b"x-csrf-token", b"abc123"),
        ],
    )
    with pytest.raises(HTTPException) as exc_info:
        await verify_csrf(req)
    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_verify_csrf_rejects_mismatched_token():
    req = _make_request(
        "http://localhost:8000",
        extra_headers=[
            (b"x-csrf-token", b"abc123"),
            (b"cookie", b"csrf_token=different"),
        ],
    )
    with pytest.raises(HTTPException) as exc_info:
        await verify_csrf(req)
    assert exc_info.value.status_code == 403
```

Add `import pytest` and `from fastapi import HTTPException` to the top of the test file if not already there.

**Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/core/test_web_session.py -v`
Expected: FAIL — `ImportError: cannot import name 'CSRF_COOKIE_NAME'`

---

### Task 2: Backend — Implement CSRF cookie and `verify_csrf`

**Files:**
- Modify: `backend/app/core/web_session.py`

**Step 3: Write minimal implementation**

Add constant after `SESSION_ROTATE_SECONDS` (line 12):

```python
CSRF_COOKIE_NAME = "csrf_token"
```

Add `import hmac` to the top imports.

Add the `verify_csrf` async function after `_cookie_samesite` (after line 58):

```python
async def verify_csrf(request: Request) -> None:
    header_token = request.headers.get("x-csrf-token", "")
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME, "")
    if not header_token or not cookie_token:
        raise HTTPException(status_code=403, detail="CSRF token missing")
    if not hmac.compare_digest(header_token, cookie_token):
        raise HTTPException(status_code=403, detail="CSRF token mismatch")
```

Add `from fastapi import HTTPException, Request, Response` (update existing import on line 6).

Update `_set_cookie` to also set the CSRF cookie. Add after the existing `response.set_cookie(...)` call (after line 47):

```python
    csrf_token = request.cookies.get(CSRF_COOKIE_NAME) or secrets.token_urlsafe(32)
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=_is_secure(request),
        samesite=samesite,
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )
```

Note: we reuse the existing CSRF token if present (from cookie), so it stays stable across requests. A new token is only generated when there's no existing one (new session) or when session rotates.

When session rotates (in `ensure_web_session`, after `_set_cookie` is called for rotation), the CSRF token gets refreshed because `_set_cookie` is called with a new response — but `request.cookies.get(CSRF_COOKIE_NAME)` will still find the old one. To force a fresh CSRF token on rotation, add a parameter to `_set_cookie`:

Actually, let's keep it simple — reuse the CSRF cookie from the request if it exists. It gets a fresh one on new sessions. This is sufficient because the CSRF token's purpose is to prove the request comes from our frontend (which can read the cookie), not to be session-bound.

**Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/core/test_web_session.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/app/core/web_session.py backend/tests/core/test_web_session.py
git commit -m "feat: add CSRF double-submit cookie verification"
```

---

### Task 3: Backend — Wire `verify_csrf` to mutating endpoints

**Files:**
- Modify: `backend/app/web/routes/conversations.py:1-9` (imports)
- Modify: `backend/app/web/routes/conversations.py:68-69` (create_conversation)
- Modify: `backend/app/web/routes/conversations.py:105-106` (delete_conversation)
- Modify: `backend/app/web/routes/conversations.py:133-134` (request_telegram_link_code)
- Modify: `backend/app/web/routes/conversations.py:153-154` (unlink_telegram)
- Modify: `backend/app/web/routes/chat.py:1-15` (imports)
- Modify: `backend/app/web/routes/chat.py:99-104` (chat endpoint)

**Step 6: Write failing integration tests**

Add to `backend/tests/web/test_conversations.py`:

```python
def test_create_conversation_requires_csrf_token(client):
    c, storage = client
    storage.create_conversation.return_value = {
        "id": "conv-1", "title": "Test", "telegram_chat_id": None,
    }
    # Without CSRF token → 403
    r = c.post(
        "/api/conversations",
        json={"title": "Test"},
    )
    assert r.status_code == 403


def test_create_conversation_succeeds_with_csrf_token(client):
    c, storage = client
    storage.create_conversation.return_value = {
        "id": "conv-1", "title": "Test", "telegram_chat_id": None,
    }
    r = c.post(
        "/api/conversations",
        json={"title": "Test"},
        headers={"X-CSRF-Token": "test-csrf"},
        cookies={"csrf_token": "test-csrf"},
    )
    assert r.status_code == 200


def test_delete_conversation_requires_csrf_token(client):
    c, storage = client
    r = c.request("DELETE", "/api/conversations/conv-1")
    assert r.status_code == 403
```

**Step 7: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/web/test_conversations.py::test_create_conversation_requires_csrf_token -v`
Expected: FAIL — returns 200 instead of 403 (no CSRF check yet)

**Step 8: Wire `verify_csrf` to endpoints**

In `backend/app/web/routes/conversations.py`:

Update imports (line 7):
```python
from app.core.web_session import ensure_web_session, verify_csrf
```

Add `Depends(verify_csrf)` to each mutating endpoint:

```python
@router.post("")
async def create_conversation(
    request: Request, response: Response, body: CreateConversationRequest,
    _csrf: None = Depends(verify_csrf),
):
```

```python
@router.delete("/{conversation_id}")
async def delete_conversation(
    request: Request, response: Response, conversation_id: str,
    _csrf: None = Depends(verify_csrf),
):
```

```python
@router.post("/{conversation_id}/telegram-link/request")
async def request_telegram_link_code(
    request: Request, response: Response, conversation_id: str,
    _csrf: None = Depends(verify_csrf),
):
```

```python
@router.post("/{conversation_id}/unlink-telegram")
async def unlink_telegram(
    request: Request, response: Response, conversation_id: str,
    _csrf: None = Depends(verify_csrf),
):
```

Add `Depends` to the fastapi import (line 3):
```python
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Response
```

In `backend/app/web/routes/chat.py`:

Update imports (line 15):
```python
from app.core.web_session import ensure_web_session, verify_csrf
```

Add to the chat endpoint:
```python
@router.post("/api/chat")
async def chat(
    request: ChatRequest,
    raw_request: Request,
    response: Response,
    _csrf: None = Depends(verify_csrf),
):
```

Add `Depends` to the fastapi import (line 6):
```python
from fastapi import APIRouter, Depends, HTTPException, Request, Response
```

**Step 9: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/web/test_conversations.py -v`
Expected: PASS

Note: Some existing tests that don't send CSRF tokens will now fail — they need to be updated to include `headers={"X-CSRF-Token": "test-csrf"}` and `cookies={"csrf_token": "test-csrf"}` for any POST/DELETE calls. Fix those tests.

**Step 10: Run full backend test suite**

Run: `cd backend && .venv/bin/python -m pytest --tb=short -q`
Expected: All tests PASS. Fix any tests that fail due to missing CSRF tokens on POST/DELETE requests.

**Step 11: Commit**

```bash
git add backend/app/web/routes/conversations.py backend/app/web/routes/chat.py backend/tests/web/
git commit -m "feat: wire CSRF verification to all mutating endpoints"
```

---

### Task 4: Frontend — Add CSRF token helper and update API calls

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/hooks/useSSE.ts`

**Step 12: Write frontend tests**

Create `frontend/src/__tests__/csrf.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { getCsrfToken } from "@/lib/csrf";

describe("getCsrfToken", () => {
  it("returns empty string when no csrf_token cookie", () => {
    Object.defineProperty(document, "cookie", { value: "", writable: true });
    expect(getCsrfToken()).toBe("");
  });

  it("extracts csrf_token from document.cookie", () => {
    Object.defineProperty(document, "cookie", {
      value: "vulcan_session=abc; csrf_token=xyz123; other=val",
      writable: true,
    });
    expect(getCsrfToken()).toBe("xyz123");
  });
});
```

**Step 13: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/__tests__/csrf.test.ts`
Expected: FAIL — module `@/lib/csrf` not found

**Step 14: Create CSRF helper**

Create `frontend/src/lib/csrf.ts`:

```typescript
export function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
  return match ? match[1] : "";
}
```

**Step 15: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/__tests__/csrf.test.ts`
Expected: PASS

**Step 16: Update `api.ts` — add CSRF header to all mutating calls**

In `frontend/src/lib/api.ts`, add import at top:

```typescript
import { getCsrfToken } from "./csrf";
```

Update `createConversation` headers:
```typescript
headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfToken() },
```

Update `deleteConversationApi` to include headers:
```typescript
export async function deleteConversationApi(conversationId: string): Promise<void> {
  const res = await fetch(`/api/conversations/${conversationId}`, {
    method: "DELETE",
    headers: { "X-CSRF-Token": getCsrfToken() },
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}
```

Update `linkTelegram` to include headers:
```typescript
export async function linkTelegram(conversationId: string): Promise<...> {
  const res = await fetch(`/api/conversations/${conversationId}/telegram-link/request`, {
    method: "POST",
    headers: { "X-CSRF-Token": getCsrfToken() },
    credentials: "include",
  });
  ...
}
```

Update `unlinkTelegram` to include headers:
```typescript
export async function unlinkTelegram(conversationId: string): Promise<void> {
  const res = await fetch(`/api/conversations/${conversationId}/unlink-telegram`, {
    method: "POST",
    headers: { "X-CSRF-Token": getCsrfToken() },
    credentials: "include",
  });
  ...
}
```

**Step 17: Update `useSSE.ts` — add CSRF header to chat fetch**

In `frontend/src/hooks/useSSE.ts`, add import at top:

```typescript
import { getCsrfToken } from "@/lib/csrf";
```

Update the fetch call headers (line 40):
```typescript
headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfToken() },
```

**Step 18: Run frontend tests**

Run: `cd frontend && npx vitest run`
Expected: All tests PASS

**Step 19: Commit**

```bash
git add frontend/src/lib/csrf.ts frontend/src/lib/api.ts frontend/src/hooks/useSSE.ts frontend/src/__tests__/csrf.test.ts
git commit -m "feat: send CSRF token header on all mutating API calls"
```

---

### Task 5: Run full test suites and final verification

**Step 20: Backend full suite**

Run: `cd backend && .venv/bin/python -m pytest --tb=short -q`
Expected: All tests PASS

**Step 21: Frontend full suite**

Run: `cd frontend && npx vitest run`
Expected: All tests PASS

**Step 22: Final commit and push**

```bash
git push
```
