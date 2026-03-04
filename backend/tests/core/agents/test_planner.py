import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.agents.planner import PlannerAgent
from app.core.models.schemas import PlannerDecision


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.provider_name = "openai"
    llm.chat = AsyncMock()
    return llm


@pytest.fixture
def planner(mock_llm):
    return PlannerAgent(llm=mock_llm)


def _mock_planner_response(needs_search: bool, query_type: str = "temporal"):
    return json.dumps({
        "needs_search": needs_search,
        "reasoning": "This is a test reasoning",
        "search_queries": ["test query"] if needs_search else [],
        "query_type": query_type,
    })


@pytest.mark.asyncio
async def test_planner_decides_search_for_temporal_query(planner, mock_llm):
    mock_llm.chat.return_value = _mock_planner_response(True, "temporal")
    decision = await planner.plan("What is TSMC stock price today?")
    assert isinstance(decision, PlannerDecision)
    assert decision.needs_search is True
    assert decision.query_type == "temporal"
    assert len(decision.search_queries) > 0


@pytest.mark.asyncio
async def test_planner_decides_no_search_for_greeting(planner, mock_llm):
    mock_llm.chat.return_value = _mock_planner_response(False, "conversational")
    decision = await planner.plan("Hello! How are you?")
    assert decision.needs_search is False
    assert decision.query_type == "conversational"
    assert decision.search_queries == []


@pytest.mark.asyncio
async def test_planner_handles_invalid_json_gracefully(planner, mock_llm):
    mock_llm.chat.return_value = "not valid json"
    decision = await planner.plan("some query")
    assert isinstance(decision, PlannerDecision)
    assert decision.needs_search is True


@pytest.mark.asyncio
async def test_planner_outputs_data_sources_for_tw_stock(planner, mock_llm):
    mock_llm.chat.return_value = json.dumps({
        "needs_search": True,
        "reasoning": "Taiwan stock price query",
        "search_queries": ["台積電 股價"],
        "query_type": "temporal",
        "data_sources": [{"type": "fugle_quote", "symbol": "2330"}],
    })
    decision = await planner.plan("台積電今天股價多少？")
    assert decision.needs_search is True
    assert len(decision.data_sources) == 1
    assert decision.data_sources[0].type == "fugle_quote"
    assert decision.data_sources[0].symbol == "2330"


@pytest.mark.asyncio
async def test_planner_strips_markdown_code_block(planner, mock_llm):
    """LLM sometimes wraps JSON in ```json ... ``` — planner should strip it."""
    mock_llm.chat.return_value = (
        "```json\n"
        '{"needs_search": true, "reasoning": "stock query", '
        '"search_queries": ["TSMC"], "query_type": "temporal"}\n'
        "```"
    )
    decision = await planner.plan("TSMC stock price?")
    assert decision.needs_search is True
    assert decision.query_type == "temporal"
    assert decision.search_queries == ["TSMC"]


@pytest.mark.asyncio
async def test_planner_empty_data_sources_for_non_tw_query(planner, mock_llm):
    mock_llm.chat.return_value = _mock_planner_response(True, "temporal")
    decision = await planner.plan("What is Apple stock price?")
    assert decision.data_sources == []


@pytest.mark.asyncio
async def test_planner_outputs_finnhub_source_for_us_stock(planner, mock_llm):
    mock_llm.chat.return_value = json.dumps({
        "needs_search": True,
        "reasoning": "US stock price query",
        "search_queries": ["AAPL stock price"],
        "query_type": "temporal",
        "data_sources": [{"type": "finnhub_quote", "symbol": "AAPL"}],
    })
    decision = await planner.plan("What is Apple stock price?")
    assert decision.needs_search is True
    assert len(decision.data_sources) == 1
    assert decision.data_sources[0].type == "finnhub_quote"
    assert decision.data_sources[0].symbol == "AAPL"


@pytest.mark.asyncio
async def test_planner_outputs_finnhub_forex(planner, mock_llm):
    mock_llm.chat.return_value = json.dumps({
        "needs_search": True,
        "reasoning": "Forex rate query",
        "search_queries": ["USD TWD exchange rate"],
        "query_type": "temporal",
        "data_sources": [{"type": "finnhub_forex", "symbol": "USD"}],
    })
    decision = await planner.plan("美金換台幣匯率多少？")
    assert decision.data_sources[0].type == "finnhub_forex"
    assert decision.data_sources[0].symbol == "USD"


def test_planner_prompt_contains_finnhub_instructions():
    from app.core.agents.planner import PLANNER_SYSTEM_PROMPT
    assert "finnhub_quote" in PLANNER_SYSTEM_PROMPT
    assert "finnhub_forex" in PLANNER_SYSTEM_PROMPT
    assert "finnhub_candles" in PLANNER_SYSTEM_PROMPT
