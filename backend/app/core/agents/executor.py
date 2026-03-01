import logging
from collections.abc import AsyncGenerator

from app.core.models.schemas import Citation, SearchResult
from app.core.services.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

EXECUTOR_SYSTEM_PROMPT_WITH_SEARCH = """You are a helpful assistant that answers questions based on web search results.

RULES:
1. Answer based on the provided search results
2. Cite sources using [1], [2], etc. markers that correspond to the search result indices
3. Be accurate and concise
4. If search results don't contain relevant information, say so honestly
5. Match your response language to the user's query language (Chinese → Chinese, English → English)
6. Use markdown formatting for readability

SEARCH RESULTS:
{search_results}"""

EXECUTOR_SYSTEM_PROMPT_NO_SEARCH = """You are a helpful assistant.

RULES:
1. Answer directly from your knowledge
2. Be accurate and concise
3. Match your response language to the user's query language
4. Use markdown formatting for readability"""


class ExecutorAgent:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._openai = OpenAIClient(api_key=api_key, model=model)

    async def execute(
        self,
        message: str,
        search_results: list[SearchResult],
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        if search_results:
            formatted = self._format_search_results(search_results)
            system_prompt = EXECUTOR_SYSTEM_PROMPT_WITH_SEARCH.format(
                search_results=formatted
            )
        else:
            system_prompt = EXECUTOR_SYSTEM_PROMPT_NO_SEARCH

        messages = list(history or [])
        messages.append({"role": "user", "content": message})

        async for chunk in self._openai.chat_stream(
            system_prompt=system_prompt,
            messages=messages,
        ):
            yield chunk

    def build_citations(self, search_results: list[SearchResult]) -> list[Citation]:
        return [
            Citation(
                index=i + 1,
                title=r.title,
                url=r.url,
                snippet=r.content[:200],
            )
            for i, r in enumerate(search_results)
        ]

    def _format_search_results(self, results: list[SearchResult]) -> str:
        parts = []
        for i, r in enumerate(results, 1):
            parts.append(f"[{i}] {r.title}\nURL: {r.url}\n{r.content}\n")
        return "\n".join(parts)
