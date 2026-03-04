import pytest
from fastapi import HTTPException
from starlette.requests import Request
from urllib.parse import urlparse

from app.core.web_session import CSRF_COOKIE_NAME, _cookie_samesite, _is_secure, verify_csrf


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


def test_cookie_samesite_is_none_for_cross_site_origin():
    req = _make_request(
        "https://vulcan-backend-production.up.railway.app",
        "https://vulcanchat.xyz",
    )
    assert _cookie_samesite(req) == "none"


def test_cookie_samesite_is_lax_for_same_host_origin():
    req = _make_request(
        "https://api.example.com",
        "https://api.example.com",
    )
    assert _cookie_samesite(req) == "lax"


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
