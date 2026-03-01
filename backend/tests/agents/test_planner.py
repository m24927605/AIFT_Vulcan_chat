import json
import pytest
from unittest.mock import AsyncMock, patch

from app.agents.planner import PlannerAgent
from app.models.schemas import PlannerDecision


@pytest.fixture
def planner():
    return PlannerAgent(api_key="test-key", model="gpt-4o")


def _mock_planner_response(needs_search: bool, query_type: str = "temporal"):
    return json.dumps({
        "needs_search": needs_search,
        "reasoning": "This is a test reasoning",
        "search_queries": ["test query"] if needs_search else [],
        "query_type": query_type,
    })


@pytest.mark.asyncio
async def test_planner_decides_search_for_temporal_query(planner):
    with patch.object(
        planner._openai, "chat", new_callable=AsyncMock,
        return_value=_mock_planner_response(True, "temporal"),
    ):
        decision = await planner.plan("What is TSMC stock price today?")
        assert isinstance(decision, PlannerDecision)
        assert decision.needs_search is True
        assert decision.query_type == "temporal"
        assert len(decision.search_queries) > 0


@pytest.mark.asyncio
async def test_planner_decides_no_search_for_greeting(planner):
    with patch.object(
        planner._openai, "chat", new_callable=AsyncMock,
        return_value=_mock_planner_response(False, "conversational"),
    ):
        decision = await planner.plan("Hello! How are you?")
        assert decision.needs_search is False
        assert decision.query_type == "conversational"
        assert decision.search_queries == []


@pytest.mark.asyncio
async def test_planner_handles_invalid_json_gracefully(planner):
    with patch.object(
        planner._openai, "chat", new_callable=AsyncMock,
        return_value="not valid json",
    ):
        decision = await planner.plan("some query")
        assert isinstance(decision, PlannerDecision)
        assert decision.needs_search is True
