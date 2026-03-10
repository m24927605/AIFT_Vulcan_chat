import asyncio
import ast
import logging
import re
from collections.abc import AsyncGenerator

from app.core.agents.planner import PlannerAgent
from app.core.agents.executor import ExecutorAgent
from app.core.agents.verifier import VerifierAgent
from app.core.security import guard_model_output, normalize_search_results, sanitize_search_results
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
    VerificationEvent,
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
_SIMPLE_MATH_PATTERN = re.compile(r"^\s*[\d\.\+\-\*\/\(\)\s]+\s*$")
_TRAILING_MATH_QUESTION_PATTERN = re.compile(r"\s*(?:=\s*)?[?？]+\s*$")
_TRAILING_EQUALS_PATTERN = re.compile(r"\s*=\s*$")
_FOREX_PATTERN = re.compile(
    r"(匯率|換.*幣|兌換|exchange\s*rate|forex|USD.?TWD|EUR.?USD|JPY|GBP)",
    re.IGNORECASE,
)
_FOREX_BASE_MAP = {
    "美元": "USD", "美金": "USD", "usd": "USD",
    "歐元": "EUR", "eur": "EUR",
    "日圓": "JPY", "日幣": "JPY", "日元": "JPY", "jpy": "JPY",
    "英鎊": "GBP", "gbp": "GBP",
    "澳幣": "AUD", "aud": "AUD",
    "加幣": "CAD", "cad": "CAD",
    "人民幣": "CNY", "cny": "CNY",
}
_GREETING_PATTERN = re.compile(
    r"^\s*(hi|hello|hey|yo|你好|哈囉|哈啰|嗨|早安|午安|晚安)([!\s,.?].*)?$",
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
        self._verifier = VerifierAgent(llm=llm)
        self._search = SearchService(api_key=tavily_api_key)
        self._fugle = FugleService(api_key=fugle_api_key) if fugle_api_key else None
        self._finnhub = FinnhubService(api_key=finnhub_api_key) if finnhub_api_key else None

    async def process_message(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[ChatEvent, None]:
        direct_greeting = _reply_greeting(message)
        if direct_greeting is not None:
            yield PlannerEvent(
                needs_search=False,
                reasoning="Deterministic fast-path for greeting",
                search_queries=[],
                query_type="conversational",
            )
            yield ChunkEvent(content=direct_greeting)
            yield DoneEvent()
            return

        direct_math = _solve_simple_math(message)
        if direct_math is not None:
            yield PlannerEvent(
                needs_search=False,
                reasoning="Deterministic fast-path for simple arithmetic",
                search_queries=[],
                query_type="conversational",
            )
            yield ChunkEvent(content=direct_math)
            yield DoneEvent()
            return

        # Step 1: Planner decides
        decision = await self._planner.plan(message, history)

        # Deterministic override: force search for temporal keywords
        if not decision.needs_search and _TEMPORAL_PATTERNS.search(message):
            logger.info(f"Rule-based override: forcing search for '{message[:50]}'")
            decision.needs_search = True
            decision.query_type = "temporal"
            if not decision.search_queries:
                decision.search_queries = [message]

        # Deterministic override: inject finnhub_forex if query is about exchange rates
        if _FOREX_PATTERN.search(message) and self._finnhub:
            has_forex = any(
                isinstance(src, FinnhubSource) and src.type == "finnhub_forex"
                for src in (decision.data_sources or [])
            )
            if not has_forex:
                base = _detect_forex_base(message)
                logger.info(f"Rule-based override: injecting finnhub_forex('{base}') for '{message[:50]}'")
                decision.data_sources = list(decision.data_sources or [])
                decision.data_sources.append(FinnhubSource(type="finnhub_forex", symbol=base))

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
        all_results = sanitize_search_results(all_results)
        normalized_results = normalize_search_results(all_results)

        # Step 2.5: Warn if search was needed but returned nothing
        search_failed = decision.needs_search and not all_results
        if search_failed:
            logger.warning("Search returned 0 results for temporal query: '%s'", message[:80])
            yield SearchFailedEvent(
                message="Web search returned no results. The answer below may not reflect the latest information."
            )

        # Step 3: Executor generates answer
        answer_chunks = []
        async for chunk in self._executor.execute(
            message=message,
            search_results=normalized_results,
            history=history,
        ):
            guarded = guard_model_output(chunk)
            answer_chunks.append(guarded)
            yield ChunkEvent(content=guarded)

        # Step 3.5: Verify answer against sources (only when search was used)
        if normalized_results:
            full_answer = "".join(answer_chunks)
            verification = await self._verifier.verify(
                query=message,
                answer=full_answer,
                search_results=normalized_results,
            )
            yield VerificationEvent(
                is_consistent=verification.is_consistent,
                confidence=verification.confidence,
                issues=verification.issues,
                suggestion=verification.suggestion,
            )

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


def _solve_simple_math(message: str) -> str | None:
    normalized = _normalize_math_message(message)
    if not _SIMPLE_MATH_PATTERN.fullmatch(normalized):
        return None
    try:
        expr = ast.parse(normalized, mode="eval")
        value = _eval_math_expr(expr.body)
    except Exception:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def _normalize_math_message(message: str) -> str:
    normalized = message.strip()
    normalized = _TRAILING_MATH_QUESTION_PATTERN.sub("", normalized)
    normalized = _TRAILING_EQUALS_PATTERN.sub("", normalized)
    return normalized.strip()


def _reply_greeting(message: str) -> str | None:
    stripped = message.strip()
    if not _GREETING_PATTERN.fullmatch(stripped):
        return None
    if re.search(r"[A-Za-z]", stripped):
        return "Hello! How can I help you today?"
    return "你好！我可以怎麼幫你？"


def _eval_math_expr(node) -> int | float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval_math_expr(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left = _eval_math_expr(node.left)
        right = _eval_math_expr(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        return left / right
    raise ValueError("Unsupported expression")


def _detect_forex_base(message: str) -> str:
    """Extract base currency from a forex query. Defaults to USD."""
    lower = message.lower()
    for keyword, code in _FOREX_BASE_MAP.items():
        if keyword in lower:
            return code
    return "USD"
