from typing import Protocol, runtime_checkable
from collections.abc import AsyncGenerator


@runtime_checkable
class LLMClient(Protocol):
    @property
    def provider_name(self) -> str: ...

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.3,
    ) -> str: ...

    async def chat_stream(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]: ...
