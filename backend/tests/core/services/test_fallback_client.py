import pytest
from unittest.mock import AsyncMock, PropertyMock, MagicMock

from openai import APITimeoutError as OpenAITimeout
from openai import APIStatusError as OpenAIStatusError

from app.core.services.fallback_client import FallbackLLMClient


def _make_mock_client(name: str) -> MagicMock:
    client = MagicMock()
    type(client).provider_name = PropertyMock(return_value=name)
    client.chat = AsyncMock(return_value=f"response from {name}")
    return client


def _make_openai_timeout() -> OpenAITimeout:
    return OpenAITimeout(request=MagicMock())


def _make_openai_status_error(status_code: int) -> OpenAIStatusError:
    response = MagicMock()
    response.status_code = status_code
    response.headers = {}
    return OpenAIStatusError(
        message=f"Error {status_code}",
        response=response,
        body=None,
    )


@pytest.mark.asyncio
async def test_chat_primary_success():
    primary = _make_mock_client("openai")
    fallback = _make_mock_client("anthropic")
    client = FallbackLLMClient(primary=primary, fallback=fallback)

    result = await client.chat("system", [{"role": "user", "content": "hi"}])

    assert result == "response from openai"
    primary.chat.assert_called_once()
    fallback.chat.assert_not_called()
    assert client.provider_name == "openai"


@pytest.mark.asyncio
async def test_chat_falls_back_on_timeout():
    primary = _make_mock_client("openai")
    primary.chat = AsyncMock(side_effect=_make_openai_timeout())
    fallback = _make_mock_client("anthropic")
    client = FallbackLLMClient(primary=primary, fallback=fallback)

    result = await client.chat("system", [{"role": "user", "content": "hi"}])

    assert result == "response from anthropic"
    assert client.provider_name == "anthropic"


@pytest.mark.asyncio
async def test_chat_falls_back_on_rate_limit():
    primary = _make_mock_client("openai")
    primary.chat = AsyncMock(side_effect=_make_openai_status_error(429))
    fallback = _make_mock_client("anthropic")
    client = FallbackLLMClient(primary=primary, fallback=fallback)

    result = await client.chat("system", [{"role": "user", "content": "hi"}])

    assert result == "response from anthropic"


@pytest.mark.asyncio
async def test_chat_falls_back_on_server_error():
    primary = _make_mock_client("openai")
    primary.chat = AsyncMock(side_effect=_make_openai_status_error(500))
    fallback = _make_mock_client("anthropic")
    client = FallbackLLMClient(primary=primary, fallback=fallback)

    result = await client.chat("system", [{"role": "user", "content": "hi"}])

    assert result == "response from anthropic"


@pytest.mark.asyncio
async def test_chat_no_fallback_on_client_error():
    primary = _make_mock_client("openai")
    primary.chat = AsyncMock(side_effect=_make_openai_status_error(400))
    fallback = _make_mock_client("anthropic")
    client = FallbackLLMClient(primary=primary, fallback=fallback)

    with pytest.raises(OpenAIStatusError):
        await client.chat("system", [{"role": "user", "content": "hi"}])

    fallback.chat.assert_not_called()


@pytest.mark.asyncio
async def test_stream_falls_back():
    primary = _make_mock_client("openai")

    async def failing_stream(*args, **kwargs):
        raise _make_openai_timeout()
        yield  # noqa: unreachable — makes this an async generator

    primary.chat_stream = MagicMock(side_effect=failing_stream)

    fallback = _make_mock_client("anthropic")

    async def fallback_stream(*args, **kwargs):
        for chunk in ["hello ", "world"]:
            yield chunk

    fallback.chat_stream = MagicMock(side_effect=fallback_stream)

    client = FallbackLLMClient(primary=primary, fallback=fallback)
    chunks = []
    async for chunk in client.chat_stream("system", [{"role": "user", "content": "hi"}]):
        chunks.append(chunk)

    assert chunks == ["hello ", "world"]
    assert client.provider_name == "anthropic"


@pytest.mark.asyncio
async def test_no_fallback_raises():
    """When there's no fallback wrapper, errors propagate directly."""
    primary = _make_mock_client("openai")
    primary.chat = AsyncMock(side_effect=_make_openai_timeout())

    # Using primary directly (no FallbackLLMClient)
    with pytest.raises(OpenAITimeout):
        await primary.chat("system", [{"role": "user", "content": "hi"}])
