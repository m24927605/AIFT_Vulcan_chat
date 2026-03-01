import json
import logging

from app.core.models.schemas import PlannerDecision
from app.core.services.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are a search planning agent. Your job is to analyze user queries and decide whether a web search is needed.

RULES:
1. Temporal questions (stock prices, news, exchange rates, weather, current events, scores, "today", "now", "latest") → MUST search
2. Factual questions where you are uncertain or the answer might have changed → search
3. Greetings, math, coding, creative writing, general knowledge you're confident about → no search
4. When searching, generate 1-3 precise search queries optimized for the user's language

Respond with ONLY valid JSON in this exact format:
{
  "needs_search": true/false,
  "reasoning": "brief explanation of your decision",
  "search_queries": ["query1", "query2"],
  "query_type": "temporal" | "factual" | "conversational"
}"""


class PlannerAgent:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._openai = OpenAIClient(api_key=api_key, model=model)

    async def plan(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> PlannerDecision:
        messages = list(history or [])
        messages.append({"role": "user", "content": message})

        try:
            response = await self._openai.chat(
                system_prompt=PLANNER_SYSTEM_PROMPT,
                messages=messages,
                temperature=0.1,
            )
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                cleaned = cleaned.rsplit("```", 1)[0]
                cleaned = cleaned.strip()

            data = json.loads(cleaned)
            return PlannerDecision(**data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Planner failed to parse response: {e}")
            return PlannerDecision(
                needs_search=True,
                reasoning="Failed to analyze query, defaulting to search",
                search_queries=[message],
                query_type="factual",
            )
