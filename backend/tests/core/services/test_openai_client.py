import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.services.openai_client import OpenAIClient


@pytest.fixture
def openai_client():
    return OpenAIClient(api_key="test-key", model="gpt-4o")


@pytest.mark.asyncio
async def test_chat_completion_returns_content(openai_client):
    mock_choice = MagicMock()
    mock_choice.message.content = "Hello, world!"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch.object(
        openai_client._client.chat.completions,
        "create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await openai_client.chat(
            system_prompt="You are helpful.",
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert result == "Hello, world!"


@pytest.mark.asyncio
async def test_chat_stream_yields_chunks(openai_client):
    async def mock_stream():
        for text in ["Hello", ", ", "world!"]:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = text
            yield chunk

    with patch.object(
        openai_client._client.chat.completions,
        "create",
        new_callable=AsyncMock,
        return_value=mock_stream(),
    ):
        chunks = []
        async for chunk in openai_client.chat_stream(
            system_prompt="You are helpful.",
            messages=[{"role": "user", "content": "Hi"}],
        ):
            chunks.append(chunk)
        assert chunks == ["Hello", ", ", "world!"]
