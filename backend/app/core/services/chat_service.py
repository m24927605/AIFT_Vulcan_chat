import asyncio
import logging
import re
from collections.abc import AsyncGenerator

from app.core.agents.planner import PlannerAgent
from app.core.agents.executor import ExecutorAgent
from app.core.services.llm_client import LLMClient
from app.core.services.search_service import SearchService
from app.core.services.fugle_service import FugleService
from app.core.services.finnhub_service import FinnhubService
from app.core.models.schemas import SearchResult, FugleSource, FinnhubSource
from app.core.models.events import (
    ChatEvent,
    PlannerEvent,
    SearchingEvent,
    ChunkEvent,
    CitationsEvent,
    SearchFailedEvent,
    DoneEvent,
)

logger = logging.getLogger(__name__)

# Deterministic pre-check: keywords that MUST trigger web search
_TEMPORAL_PATTERNS = re.compile(
    r"(股價|股票|新聞|匯率|天氣|比分|即時|最新|今[天日]|現在|目前|當前"
    r"|stock.?price|exchange.?rate|weather|score|latest|current|today|right\s?now"
    r"|news|headline|breaking)",
    re.IGNORECASE,
)


class ChatService:
    def __init__(
        self,
        llm: LLMClient,
        tavily_api_key: str,
        fugle_api_key: str = "",
        finnhub_api_key: str = "",
    ):
        self._planner = PlannerAgent(llm=llm)
        self._executor = ExecutorAgent(llm=llm)
        self._search = SearchService(api_key=tavily_api_key)
        self._fugle = FugleService(api_key=fugle_api_key) if fugle_api_key else None
        self._finnhub = FinnhubService(api_key=finnhub_api_key) if finnhub_api_key else None

    async def process_message(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[ChatEvent, None]:
        # Step 1: Planner decides
        decision = await self._planner.plan(message, history)

        # Deterministic override: force search for temporal keywords
        if not decision.needs_search and _TEMPORAL_PATTERNS.search(message):
            logger.info(f"Rule-based override: forcing search for '{message[:50]}'")
            decision.needs_search = True
            decision.query_type = "temporal"
            if not decision.search_queries:
                decision.search_queries = [message]

        yield PlannerEvent(
            needs_search=decision.needs_search,
            reasoning=decision.reasoning,
            search_queries=decision.search_queries,
            query_type=decision.query_type,
        )

        # Step 2: Fetch data sources (Fugle/Finnhub) + Tavily in parallel
        search_results = []
        data_results = []

        if decision.needs_search and decision.search_queries:
            for query in decision.search_queries:
                yield SearchingEvent(query=query, status="searching")

            data_task = self._fetch_data_sources(decision.data_sources)
            tavily_task = self._search.search_multiple(decision.search_queries)
            data_results, search_results = await asyncio.gather(data_task, tavily_task)

            for query in decision.search_queries:
                yield SearchingEvent(
                    query=query,
                    status="done",
                    results_count=len(search_results) + len(data_results),
                )
        elif decision.data_sources:
            # data_sources but no search queries (edge case)
            data_results = await self._fetch_data_sources(decision.data_sources)

        all_results = data_results + search_results

        # Step 2.5: Warn if search was needed but returned nothing
        search_failed = decision.needs_search and not all_results
        if search_failed:
            logger.warning("Search returned 0 results for temporal query: '%s'", message[:80])
            yield SearchFailedEvent(
                message="Web search returned no results. The answer below may not reflect the latest information."
            )

        # Step 3: Executor generates answer
        async for chunk in self._executor.execute(
            message=message,
            search_results=all_results,
            history=history,
        ):
            yield ChunkEvent(content=chunk)

        # Step 4: Send citations
        if all_results:
            citations = self._executor.build_citations(all_results)
            yield CitationsEvent(
                citations=[
                    {"index": c.index, "title": c.title, "url": c.url, "snippet": c.snippet}
                    for c in citations
                ]
            )

        yield DoneEvent()

    async def _fetch_data_sources(
        self, data_sources: list,
    ) -> list[SearchResult]:
        if not data_sources:
            return []

        results = []
        for src in data_sources:
            text = ""
            if isinstance(src, FugleSource) and self._fugle:
                if src.type == "fugle_quote":
                    text = await self._fugle.get_quote(src.symbol)
                elif src.type == "fugle_historical":
                    text = await self._fugle.get_historical(src.symbol, src.timeframe or "D")
            elif isinstance(src, FinnhubSource) and self._finnhub:
                text = await self._dispatch_finnhub(src)

            if text:
                provider = "Fugle" if isinstance(src, FugleSource) else "Finnhub"
                results.append(SearchResult(
                    title=f"{provider}: {src.symbol} {src.type}",
                    url="",
                    content=text,
                    score=1.0,
                ))
        return results

    async def _dispatch_finnhub(self, src: FinnhubSource) -> str:
        dispatch = {
            "finnhub_quote": lambda: self._finnhub.get_quote(src.symbol),
            "finnhub_candles": lambda: self._finnhub.get_candles(src.symbol, src.timeframe or "D", src.from_date, src.to_date),
            "finnhub_forex": lambda: self._finnhub.get_forex_rates(src.symbol),
            "finnhub_profile": lambda: self._finnhub.get_profile(src.symbol),
            "finnhub_financials": lambda: self._finnhub.get_financials(src.symbol),
            "finnhub_news": lambda: self._finnhub.get_news(src.symbol, src.from_date, src.to_date),
            "finnhub_earnings": lambda: self._finnhub.get_earnings(src.symbol),
            "finnhub_price_target": lambda: self._finnhub.get_price_target(src.symbol),
            "finnhub_recommendation": lambda: self._finnhub.get_recommendation(src.symbol),
            "finnhub_insider": lambda: self._finnhub.get_insider(src.symbol),
        }
        handler = dispatch.get(src.type)
        if handler:
            return await handler()
        return ""
