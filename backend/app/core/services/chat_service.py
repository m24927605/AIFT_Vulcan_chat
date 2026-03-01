import logging
from collections.abc import AsyncGenerator

from app.core.agents.planner import PlannerAgent
from app.core.agents.executor import ExecutorAgent
from app.core.services.search_service import SearchService
from app.core.models.events import (
    ChatEvent,
    PlannerEvent,
    SearchingEvent,
    ChunkEvent,
    CitationsEvent,
    DoneEvent,
)

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        openai_api_key: str,
        openai_model: str,
        tavily_api_key: str,
    ):
        self._planner = PlannerAgent(api_key=openai_api_key, model=openai_model)
        self._executor = ExecutorAgent(api_key=openai_api_key, model=openai_model)
        self._search = SearchService(api_key=tavily_api_key)

    async def process_message(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[ChatEvent, None]:
        # Step 1: Planner decides
        decision = await self._planner.plan(message, history)
        yield PlannerEvent(
            needs_search=decision.needs_search,
            reasoning=decision.reasoning,
            search_queries=decision.search_queries,
            query_type=decision.query_type,
        )

        # Step 2: Search if needed
        search_results = []
        if decision.needs_search and decision.search_queries:
            for query in decision.search_queries:
                yield SearchingEvent(query=query, status="searching")

            search_results = await self._search.search_multiple(
                decision.search_queries
            )

            for query in decision.search_queries:
                yield SearchingEvent(
                    query=query,
                    status="done",
                    results_count=len(search_results),
                )

        # Step 3: Executor generates answer
        async for chunk in self._executor.execute(
            message=message,
            search_results=search_results,
            history=history,
        ):
            yield ChunkEvent(content=chunk)

        # Step 4: Send citations
        if search_results:
            citations = self._executor.build_citations(search_results)
            yield CitationsEvent(
                citations=[
                    {"index": c.index, "title": c.title, "url": c.url, "snippet": c.snippet}
                    for c in citations
                ]
            )

        yield DoneEvent()
