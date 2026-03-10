"""
Multi-round deep analysis task.
Runs iterative Planner -> Search -> Refine loops, then synthesizes
a final answer through the shared secured pipeline.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.agents.planner import PlannerAgent
from app.core.agents.executor import ExecutorAgent
from app.core.agents.verifier import VerifierAgent
from app.core.security import (
    filter_renderable_results,
    sanitize_search_results,
    normalize_search_results,
)
from app.core.pipelines.secure_answer import secure_answer_pipeline
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
    verifier = VerifierAgent(llm=llm)
    all_search_results = []
    rounds_executed = 0
    round_logs = []
    any_round_needed_search = False

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
        any_round_needed_search = True
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

    # Pre-filter: remove AI summaries, keep market data and web results
    renderable_results = filter_renderable_results(all_search_results)
    normalized = normalize_search_results(renderable_results)

    # Use shared secured pipeline
    pipeline_result = await secure_answer_pipeline(
        message=query,
        needs_search=any_round_needed_search,
        normalized_results=normalized,
        executor=executor,
        verifier=verifier,
    )

    if pipeline_result["refused"]:
        return {
            "status": "refused",
            "query": query,
            "answer": pipeline_result["refusal_message"],
            "rounds": rounds_executed,
            "round_details": round_logs,
            "search_results": [],
            "verification": None,
        }

    verification_dict = None
    if pipeline_result["verification"] is not None:
        v = pipeline_result["verification"]
        verification_dict = {
            "is_consistent": v.is_consistent,
            "confidence": v.confidence,
            "issues": v.issues,
            "suggestion": v.suggestion,
        }

    return {
        "status": "completed",
        "query": query,
        "answer": pipeline_result["answer"],
        "rounds": rounds_executed,
        "round_details": round_logs,
        "search_results": [
            {"title": r.title, "url": r.url, "content": r.content[:200]}
            for r in renderable_results
        ],
        "verification": verification_dict,
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
