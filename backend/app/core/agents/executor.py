import logging
from collections.abc import AsyncGenerator

from app.core.models.schemas import Citation, SearchResult
from app.core.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

EXECUTOR_SYSTEM_PROMPT_WITH_SEARCH = """You are a helpful assistant that answers questions based on web search results.

RULES:
1. Answer based ONLY on the provided search results — do not add information from your own knowledge
2. Cite sources using [1], [2], etc. markers that correspond to the search result indices
3. NUMERICAL PRECISION: Quote numbers (prices, rates, scores, statistics) EXACTLY as they appear in the search results. NEVER round, average, estimate, or infer numbers. If multiple sources show different numbers, present each with its citation
4. If search results don't contain relevant information, say so honestly — do not guess
5. Match your response language AND script exactly to the user's query (Traditional Chinese → Traditional Chinese 繁體中文, Simplified Chinese → Simplified Chinese 简体中文, English → English). Never mix scripts.
6. Use markdown formatting for readability

SEARCH RESULTS:
{search_results}"""

EXECUTOR_SYSTEM_PROMPT_NO_SEARCH = """You are a helpful assistant.

RULES:
1. Answer directly from your knowledge
2. Be accurate and concise
3. Match your response language AND script exactly to the user's query (Traditional Chinese → Traditional Chinese 繁體中文, Simplified Chinese → Simplified Chinese 简体中文, English → English). Never mix scripts.
4. Use markdown formatting for readability"""


class ExecutorAgent:
    def __init__(self, llm: LLMClient):
        self._llm = llm

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

        async for chunk in self._llm.chat_stream(
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
            if r.url  # exclude Tavily AI answer (no URL)
        ]

    def _format_search_results(self, results: list[SearchResult]) -> str:
        parts = []
        for i, r in enumerate(results, 1):
            parts.append(f"[{i}] {r.title}\nURL: {r.url}\n{r.content}\n")
        return "\n".join(parts)
