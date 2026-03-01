import re

from app.core.models.events import (
    PlannerEvent,
    SearchingEvent,
    CitationsEvent,
)

_ESCAPE_CHARS = r"_*[]()~`>#+-=|{}.!"


class TelegramFormatter:
    @staticmethod
    def escape_md(text: str) -> str:
        return re.sub(r"([" + re.escape(_ESCAPE_CHARS) + r"])", r"\\\1", text)

    @staticmethod
    def format_planner(event: PlannerEvent) -> str:
        if event.needs_search:
            queries = ", ".join(event.search_queries)
            return f"🔍 {event.reasoning}\n📝 Queries: {queries}"
        return f"💬 {event.reasoning}"

    @staticmethod
    def format_searching(event: SearchingEvent) -> str:
        if event.status == "searching":
            return f"🔍 Searching: {event.query}..."
        return f"✅ Found {event.results_count} results for: {event.query}"

    @staticmethod
    def format_citations(event: CitationsEvent) -> str:
        lines = ["\n📚 Sources:"]
        for c in event.citations:
            lines.append(f"  [{c['index']}] {c['title']}\n      {c['url']}")
        return "\n".join(lines)

    @staticmethod
    def format_final_message(
        answer: str,
        citations: CitationsEvent | None,
        needs_search: bool | None = None,
    ) -> str:
        parts = []
        if needs_search is True:
            parts.append("🔍 Searched the web")
        elif needs_search is False:
            parts.append("💬 Answered directly")
        parts.append(answer)
        if citations and citations.citations:
            citation_text = TelegramFormatter.format_citations(citations)
            parts.append(citation_text)
        return "\n".join(parts)
