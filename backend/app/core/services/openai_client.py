import logging
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.3,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system_prompt}, *messages],
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    async def chat_stream(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system_prompt}, *messages],
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content
