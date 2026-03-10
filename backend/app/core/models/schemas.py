from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = Field(None, pattern=r"^[0-9a-f\-]{36}$")
    history: list[ChatMessage] = Field(default_factory=list)


class FugleSource(BaseModel):
    type: str = Field(..., pattern="^(fugle_quote|fugle_historical)$")
    symbol: str = Field(..., min_length=1, max_length=10)
    timeframe: str | None = Field(None, pattern="^[DWMK]$")


class FinnhubSource(BaseModel):
    type: str = Field(
        ...,
        pattern="^(finnhub_quote|finnhub_candles|finnhub_profile|finnhub_financials|finnhub_news|finnhub_earnings|finnhub_price_target|finnhub_recommendation|finnhub_insider)$",
    )
    symbol: str = Field(..., min_length=1, max_length=20)
    timeframe: str | None = Field(None, pattern="^(1|5|15|30|60|D|W|M)$")
    from_date: str | None = None
    to_date: str | None = None


class RterInfoSource(BaseModel):
    type: str = Field("rter_forex", pattern="^rter_forex$")
    symbol: str = Field(..., min_length=1, max_length=10)


class PlannerDecision(BaseModel):
    needs_search: bool
    reasoning: str
    search_queries: list[str] = Field(default_factory=list, max_length=3)
    query_type: str = Field(..., pattern="^(temporal|factual|conversational)$")
    data_sources: list[FugleSource | FinnhubSource | RterInfoSource] = Field(default_factory=list)


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


class ExtractedFact(BaseModel):
    text: str = Field(..., min_length=1, max_length=300)


class ExtractedNumber(BaseModel):
    label: str = Field(..., min_length=1, max_length=80)
    value: str = Field(..., min_length=1, max_length=80)


class NormalizedSearchResult(BaseModel):
    source_kind: str = Field(..., pattern="^(web|market_data|ai_summary)$")
    title: str = Field(..., min_length=1, max_length=300)
    url: str = Field(default="")
    publisher: str = Field(default="", max_length=120)
    published_at: str = Field(default="", max_length=40)
    excerpt: str = Field(default="", max_length=600)
    facts: list[ExtractedFact] = Field(default_factory=list, max_length=5)
    numbers: list[ExtractedNumber] = Field(default_factory=list, max_length=8)

    @property
    def content(self) -> str:
        """Compatibility alias for older code/tests expecting SearchResult.content."""
        return self.excerpt


class CreateConversationRequest(BaseModel):
    id: str | None = Field(None, pattern=r"^[0-9a-f\-]{36}$")
    title: str = Field(..., min_length=1, max_length=200)

class LinkTelegramRequest(BaseModel):
    telegram_chat_id: int

class AddMessageRequest(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str
    source: str = Field(..., pattern="^(web|telegram)$")
    search_used: bool | None = None
    citations: list[dict] | None = None
