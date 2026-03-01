from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)


class PlannerDecision(BaseModel):
    needs_search: bool
    reasoning: str
    search_queries: list[str] = Field(default_factory=list, max_length=3)
    query_type: str = Field(..., pattern="^(temporal|factual|conversational)$")


class Citation(BaseModel):
    index: int
    title: str
    url: str
    snippet: str


class SearchResult(BaseModel):
    title: str
    url: str
    content: str
    score: float = 0.0
