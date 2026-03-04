import logging
from collections.abc import AsyncGenerator

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

_ANTHROPIC_TIMEOUT = 60.0


class AnthropicClient:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self._client = AsyncAnthropic(api_key=api_key, timeout=_ANTHROPIC_TIMEOUT)
        self._model = model

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.3,
    ) -> str:
        logger.info("Anthropic chat request (model=%s)", self._model)
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            temperature=temperature,
        )
        return resp.content[0].text

    async def chat_stream(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        logger.info("Anthropic stream request (model=%s)", self._model)
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            temperature=temperature,
        ) as stream:
            async for text in stream.text_stream:
                yield text
