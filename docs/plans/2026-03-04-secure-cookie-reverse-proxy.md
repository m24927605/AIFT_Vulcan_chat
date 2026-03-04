# Secure Cookie Reverse Proxy Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix secure cookie detection so it works behind reverse proxies (Railway) that terminate TLS upstream.

**Architecture:** Add `_is_secure(request)` helper that checks `X-Forwarded-Proto` header first, falling back to `request.url.scheme`. Replace the inline scheme check in `_set_cookie`.

**Tech Stack:** Python, FastAPI/Starlette, pytest

---

### Task 1: Write failing tests for `_is_secure`

**Files:**
- Modify: `backend/tests/core/test_web_session.py`

**Step 1: Write the failing tests**

Add to `backend/tests/core/test_web_session.py`:

```python
from app.core.web_session import _cookie_samesite, _is_secure


def _make_request(url: str, origin: str | None = None, extra_headers: list | None = None) -> Request:
    parsed = urlparse(url)
    headers = []
    if origin:
        headers.append((b"origin", origin.encode()))
    if extra_headers:
        headers.extend(extra_headers)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "scheme": parsed.scheme,
        "server": (parsed.hostname or "testserver", parsed.port or (443 if parsed.scheme == "https" else 80)),
        "query_string": b"",
    }
    return Request(scope)


def test_is_secure_with_forwarded_proto_https():
    req = _make_request(
        "http://localhost:8000",
        extra_headers=[(b"x-forwarded-proto", b"https")],
    )
    assert _is_secure(req) is True


def test_is_secure_with_forwarded_proto_http():
    req = _make_request(
        "http://localhost:8000",
        extra_headers=[(b"x-forwarded-proto", b"http")],
    )
    assert _is_secure(req) is False


def test_is_secure_no_header_https_scheme():
    req = _make_request("https://example.com")
    assert _is_secure(req) is True


def test_is_secure_no_header_http_scheme():
    req = _make_request("http://localhost:8000")
    assert _is_secure(req) is False
```

Note: The existing `_make_request` helper needs an `extra_headers` parameter. Update the signature and body as shown above. The two existing tests that call `_make_request` don't pass `extra_headers`, so they continue to work unchanged.

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/core/test_web_session.py -v`
Expected: FAIL — `ImportError: cannot import name '_is_secure'`

---

### Task 2: Implement `_is_secure` and update `_set_cookie`

**Files:**
- Modify: `backend/app/core/web_session.py:28-38`

**Step 3: Write minimal implementation**

Add this function before `_set_cookie` in `web_session.py` (after `_ip_prefix`, before `_set_cookie`):

```python
def _is_secure(request: Request) -> bool:
    proto = request.headers.get("x-forwarded-proto", "").lower().strip()
    if proto:
        return proto == "https"
    return request.url.scheme == "https"
```

Then change line 34 of `_set_cookie` from:
```python
secure=request.url.scheme == "https",
```
to:
```python
secure=_is_secure(request),
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/core/test_web_session.py -v`
Expected: All 6 tests PASS (4 new + 2 existing)

**Step 5: Run full backend test suite**

Run: `cd backend && python -m pytest --tb=short -q`
Expected: All tests PASS, no regressions

---

### Task 3: Commit and push

**Step 6: Commit**

```bash
git add backend/app/core/web_session.py backend/tests/core/test_web_session.py
git commit -m "fix: detect HTTPS via X-Forwarded-Proto for secure cookies behind reverse proxy"
```

**Step 7: Push**

```bash
git push
```
