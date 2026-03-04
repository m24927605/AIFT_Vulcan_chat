import logging
from collections.abc import AsyncGenerator

from anthropic import APITimeoutError as AnthropicTimeout
from anthropic import APIConnectionError as AnthropicConnectionError
from anthropic import APIStatusError as AnthropicStatusError
from openai import APITimeoutError as OpenAITimeout
from openai import APIConnectionError as OpenAIConnectionError
from openai import APIStatusError as OpenAIStatusError

from app.core.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

# Status codes that trigger fallback (rate-limit + server errors)
_FALLBACK_STATUS_CODES = {429, 500, 502, 503, 504}


def _should_fallback(exc: Exception) -> bool:
    if isinstance(exc, (OpenAITimeout, AnthropicTimeout)):
        return True
    if isinstance(exc, (OpenAIConnectionError, AnthropicConnectionError)):
        return True
    if isinstance(exc, (OpenAIStatusError, AnthropicStatusError)):
        return exc.status_code in _FALLBACK_STATUS_CODES
    return False


class FallbackLLMClient:
    def __init__(self, primary: LLMClient, fallback: LLMClient):
        self._primary = primary
        self._fallback = fallback
        self._active = primary

    @property
    def provider_name(self) -> str:
        return self._active.provider_name

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.3,
    ) -> str:
        try:
            result = await self._primary.chat(system_prompt, messages, temperature)
            self._active = self._primary
            logger.info("LLM chat served by %s", self._primary.provider_name)
            return result
        except Exception as exc:
            if not _should_fallback(exc):
                raise
            logger.warning(
                "Primary LLM (%s) failed: %s — falling back to %s",
                self._primary.provider_name, exc, self._fallback.provider_name,
            )
            self._active = self._fallback
            result = await self._fallback.chat(system_prompt, messages, temperature)
            logger.info("LLM chat served by %s (fallback)", self._fallback.provider_name)
            return result

    async def chat_stream(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        try:
            async for chunk in self._primary.chat_stream(system_prompt, messages, temperature):
                self._active = self._primary
                yield chunk
            logger.info("LLM stream served by %s", self._primary.provider_name)
            return
        except Exception as exc:
            if not _should_fallback(exc):
                raise
            logger.warning(
                "Primary LLM stream (%s) failed: %s — falling back to %s",
                self._primary.provider_name, exc, self._fallback.provider_name,
            )

        self._active = self._fallback
        async for chunk in self._fallback.chat_stream(system_prompt, messages, temperature):
            yield chunk
        logger.info("LLM stream served by %s (fallback)", self._fallback.provider_name)
