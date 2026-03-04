# Secure Cookie Reverse Proxy Fix

**Date:** 2026-03-04
**Status:** Approved
**Scope:** Issue #3 only (of 3 identified security items)

## Problem

`web_session.py:34` uses `request.url.scheme == "https"` to set the `Secure` flag on session cookies. Behind Railway's reverse proxy (TLS terminated at load balancer), the backend always sees `http`, so `Secure` is always `False`.

This also breaks `SameSite=None` cookies (required for cross-origin), since browsers reject `SameSite=None` without `Secure=True`.

## Solution

Add `_is_secure(request)` helper that checks `X-Forwarded-Proto` header first, falling back to `request.url.scheme`:

```python
def _is_secure(request: Request) -> bool:
    proto = request.headers.get("x-forwarded-proto", "").lower().strip()
    if proto:
        return proto == "https"
    return request.url.scheme == "https"
```

Replace `secure=request.url.scheme == "https"` with `secure=_is_secure(request)` in `_set_cookie`.

## Files Changed

- `backend/app/core/web_session.py` — add `_is_secure`, update `_set_cookie`
- `backend/tests/` — add unit tests for `_is_secure`

## Test Plan

- `_is_secure` with `X-Forwarded-Proto: https` → True
- `_is_secure` with `X-Forwarded-Proto: http` → False
- `_is_secure` without header, scheme=https → True
- `_is_secure` without header, scheme=http → False
- Existing session tests still pass
