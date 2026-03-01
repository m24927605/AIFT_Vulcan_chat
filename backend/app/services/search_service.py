import asyncio
import logging

import httpx

from app.models.schemas import SearchResult

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"


class SearchService:
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=10.0)

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        try:
            response = await self._client.post(
                TAVILY_API_URL,
                json={
                    "api_key": self._api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
            )
            response.raise_for_status()
            data = response.json()
            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=r.get("content", ""),
                    score=r.get("score", 0.0),
                )
                for r in data.get("results", [])
            ]
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            return []

    async def search_multiple(
        self, queries: list[str], max_results: int = 5
    ) -> list[SearchResult]:
        tasks = [self.search(q, max_results) for q in queries]
        results_lists = await asyncio.gather(*tasks)
        seen_urls: set[str] = set()
        unique_results: list[SearchResult] = []
        for results in results_lists:
            for r in results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    unique_results.append(r)
        return unique_results

    async def close(self):
        await self._client.aclose()
