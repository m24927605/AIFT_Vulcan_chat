import hmac
import hashlib
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.core.conversation_auth import generate_conversation_token, require_conversation_token


SECRET = "test-secret-key-12345"
CONV_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


class TestGenerateToken:
    def test_returns_hmac_when_key_set(self):
        with patch("app.core.conversation_auth.settings") as mock:
            mock.api_secret_key = SECRET
            token = generate_conversation_token(CONV_ID)
        expected = hmac.new(SECRET.encode(), CONV_ID.encode(), hashlib.sha256).hexdigest()
        assert token == expected

    def test_returns_empty_when_no_key(self):
        with patch("app.core.conversation_auth.settings") as mock:
            mock.api_secret_key = ""
            token = generate_conversation_token(CONV_ID)
        assert token == ""

    def test_different_ids_produce_different_tokens(self):
        with patch("app.core.conversation_auth.settings") as mock:
            mock.api_secret_key = SECRET
            t1 = generate_conversation_token("id-1")
            t2 = generate_conversation_token("id-2")
        assert t1 != t2


class TestRequireToken:
    @pytest.mark.asyncio
    async def test_skips_when_no_key_in_local_dev(self):
        with patch("app.core.conversation_auth.settings") as mock:
            mock.api_secret_key = ""
            mock.frontend_url = "http://localhost:3000"
            # Should not raise
            await require_conversation_token(CONV_ID, None)

    @pytest.mark.asyncio
    async def test_rejects_when_no_key_outside_local_dev(self):
        with patch("app.core.conversation_auth.settings") as mock:
            mock.api_secret_key = ""
            mock.frontend_url = "https://app.example.com"
            with pytest.raises(HTTPException) as exc_info:
                await require_conversation_token(CONV_ID, None)
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_accepts_valid_token(self):
        token = hmac.new(SECRET.encode(), CONV_ID.encode(), hashlib.sha256).hexdigest()
        with patch("app.core.conversation_auth.settings") as mock:
            mock.api_secret_key = SECRET
            await require_conversation_token(CONV_ID, token)

    @pytest.mark.asyncio
    async def test_rejects_missing_token(self):
        with patch("app.core.conversation_auth.settings") as mock:
            mock.api_secret_key = SECRET
            with pytest.raises(HTTPException) as exc_info:
                await require_conversation_token(CONV_ID, None)
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_rejects_wrong_token(self):
        with patch("app.core.conversation_auth.settings") as mock:
            mock.api_secret_key = SECRET
            with pytest.raises(HTTPException) as exc_info:
                await require_conversation_token(CONV_ID, "wrong-token")
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_rejects_token_for_wrong_id(self):
        token = hmac.new(SECRET.encode(), b"other-id", hashlib.sha256).hexdigest()
        with patch("app.core.conversation_auth.settings") as mock:
            mock.api_secret_key = SECRET
            with pytest.raises(HTTPException) as exc_info:
                await require_conversation_token(CONV_ID, token)
            assert exc_info.value.status_code == 403
