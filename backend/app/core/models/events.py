from dataclasses import dataclass


@dataclass
class PlannerEvent:
    needs_search: bool
    reasoning: str
    search_queries: list[str]
    query_type: str


@dataclass
class SearchingEvent:
    query: str
    status: str  # "searching" | "done"
    results_count: int | None = None


@dataclass
class ChunkEvent:
    content: str


@dataclass
class CitationsEvent:
    citations: list[dict]


@dataclass
class DoneEvent:
    pass


ChatEvent = PlannerEvent | SearchingEvent | ChunkEvent | CitationsEvent | DoneEvent
