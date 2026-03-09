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
class SearchFailedEvent:
    message: str


@dataclass
class VerificationEvent:
    is_consistent: bool
    confidence: float
    issues: list[str]
    suggestion: str


@dataclass
class DoneEvent:
    pass


ChatEvent = PlannerEvent | SearchingEvent | ChunkEvent | CitationsEvent | SearchFailedEvent | VerificationEvent | DoneEvent
