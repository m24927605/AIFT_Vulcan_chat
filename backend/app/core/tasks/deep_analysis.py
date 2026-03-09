"""
Multi-round deep analysis task.
Runs iterative Planner -> Search -> Refine loops, then synthesizes
a final answer with the Executor.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.agents.planner import PlannerAgent
from app.core.agents.executor import ExecutorAgent
from app.core.security import sanitize_search_results, normalize_search_results
from app.core.services.llm_client import LLMClient
from app.core.services.search_service import SearchService

logger = logging.getLogger(__name__)


async def run_deep_analysis_async(
    *,
    query: str,
    llm: LLMClient,
    search_service: SearchService,
    max_rounds: int = 3,
) -> dict[str, Any]:
    planner = PlannerAgent(llm=llm)
    executor = ExecutorAgent(llm=llm)
    all_search_results = []
    rounds_executed = 0
    round_logs = []

    for round_num in range(1, max_rounds + 1):
        rounds_executed = round_num
        history = []
        if round_logs:
            context = "\n".join(
                f"Round {r['round']}: searched '{', '.join(r['queries'])}' -> {r['results_count']} results"
                for r in round_logs
            )
            history = [
                {"role": "user", "content": query},
                {
                    "role": "assistant",
                    "content": f"Previous research:\n{context}\nLet me check if more search is needed.",
                },
            ]
        decision = await planner.plan(query, history if history else None)
        if not decision.needs_search:
            break
        results = await search_service.search_multiple(decision.search_queries)
        sanitized = sanitize_search_results(results)
        all_search_results.extend(sanitized)
        round_logs.append(
            {
                "round": round_num,
                "queries": decision.search_queries,
                "results_count": len(results),
                "reasoning": decision.reasoning,
            }
        )

    normalized = normalize_search_results(all_search_results)
    chunks = []
    async for chunk in executor.execute(message=query, search_results=normalized):
        chunks.append(chunk)

    return {
        "status": "completed",
        "query": query,
        "answer": "".join(chunks),
        "rounds": rounds_executed,
        "round_details": round_logs,
        "search_results": [
            {"title": r.title, "url": r.url, "content": r.content[:200]}
            for r in all_search_results
        ],
    }


def run_deep_analysis_sync(query: str, max_rounds: int = 3) -> dict[str, Any]:
    from app.core.config import settings
    from app.core.services.llm_factory import create_llm_client

    llm = create_llm_client(settings)
    search = SearchService(api_key=settings.tavily_api_key)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            run_deep_analysis_async(
                query=query, llm=llm, search_service=search, max_rounds=max_rounds
            )
        )
    finally:
        loop.close()
