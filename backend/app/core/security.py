import re

from app.core.models.schemas import (
    ExtractedFact,
    ExtractedNumber,
    NormalizedSearchResult,
    SearchResult,
)

_PROMPT_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"ignore (all|previous|prior) instructions",
        r"disregard (all|previous|prior) instructions",
        r"reveal (the )?(system prompt|hidden prompt)",
        r"show (the )?(system prompt|hidden prompt)",
        r"print (your )?(chain[- ]of[- ]thought|cot)",
        r"exfiltrat(e|ion)",
        r"developer message",
        r"tool instructions",
        r"api[_ -]?key",
        r"secret",
        r"token",
    ]
]

_SECRET_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"sk-[A-Za-z0-9_-]{20,}",
        r"sess-[A-Za-z0-9_-]{16,}",
        r"(?<![A-Za-z0-9])[A-Za-z0-9+/]{32,}={0,2}(?![A-Za-z0-9])",
        r"api[_ -]?key\s*[:=]\s*\S+",
        r"authorization\s*:\s*bearer\s+\S+",
    ]
]

_REDACTION_NOTICE = "[REDACTED: sensitive content removed]"
_NUMBER_PATTERN = re.compile(r"(?P<value>[$€£]?\d[\d,]*(?:\.\d+)?%?)")


def sanitize_search_result(result: SearchResult) -> SearchResult:
    title = _sanitize_text(result.title, max_len=300)
    content = _sanitize_text(result.content, max_len=4000)
    return SearchResult(title=title, url=result.url, content=content, score=result.score)


def sanitize_search_results(results: list[SearchResult]) -> list[SearchResult]:
    return [sanitize_search_result(result) for result in results]


def normalize_search_results(results: list[SearchResult]) -> list[NormalizedSearchResult]:
    return [_normalize_search_result(result) for result in results]


def guard_model_output(text: str) -> str:
    guarded = text
    for pattern in _SECRET_PATTERNS:
        guarded = pattern.sub(_REDACTION_NOTICE, guarded)
    return guarded


def _sanitize_text(text: str, *, max_len: int) -> str:
    sanitized = text.strip()
    for pattern in _PROMPT_INJECTION_PATTERNS:
        sanitized = pattern.sub("[filtered]", sanitized)
    return sanitized[:max_len]


def _normalize_search_result(result: SearchResult) -> NormalizedSearchResult:
    title = _sanitize_text(result.title, max_len=300)
    excerpt = _sanitize_text(result.content, max_len=600)
    facts = [ExtractedFact(text=fact) for fact in _extract_facts(result.content)]
    numbers = [
        ExtractedNumber(label=f"value_{idx + 1}", value=value)
        for idx, value in enumerate(_extract_numbers(result.content))
    ]
    publisher, published_at = _extract_metadata(title, excerpt)
    return NormalizedSearchResult(
        source_kind=_classify_source_kind(result),
        title=title or "Untitled source",
        url=result.url,
        publisher=publisher,
        published_at=published_at,
        excerpt=excerpt,
        facts=facts,
        numbers=numbers,
    )


def _extract_facts(text: str) -> list[str]:
    segments = [
        _sanitize_text(segment, max_len=300)
        for segment in re.split(r"[\n\r]+|(?<=[。.!?])\s+", text)
    ]
    facts: list[str] = []
    for segment in segments:
        cleaned = segment.strip(" -•\t")
        if len(cleaned) < 20:
            continue
        facts.append(cleaned)
        if len(facts) >= 3:
            break
    return facts


def _extract_numbers(text: str) -> list[str]:
    numbers: list[str] = []
    for match in _NUMBER_PATTERN.finditer(text):
        value = match.group("value")
        if value not in numbers:
            numbers.append(value)
        if len(numbers) >= 5:
            break
    return numbers


def _extract_metadata(title: str, excerpt: str) -> tuple[str, str]:
    publisher = ""
    published_at = ""
    combined = f"{title} {excerpt}"
    date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", combined)
    if date_match:
        published_at = date_match.group(1)
    title_parts = [part.strip() for part in re.split(r"\s+[|:-]\s+", title) if part.strip()]
    if len(title_parts) > 1:
        publisher = title_parts[-1][:120]
    return publisher, published_at


def _classify_source_kind(result: SearchResult) -> str:
    if not result.url:
        if result.title.startswith(("Fugle:", "Finnhub:", "tw.rter.info:")):
            return "market_data"
        return "ai_summary"
    return "web"


_DATA_SOURCE_PREFIXES = ("Fugle:", "Finnhub:", "tw.rter.info:")


def filter_renderable_results(results: list[SearchResult]) -> list[SearchResult]:
    """Remove AI-generated summaries (no URL, not a known data source).

    Keeps: web results (have URL) and market data (Fugle/Finnhub/tw.rter.info).
    Removes: Tavily AI Answer and similar AI summaries with no URL.
    """
    return [
        r for r in results
        if r.url or r.title.startswith(_DATA_SOURCE_PREFIXES)
    ]
