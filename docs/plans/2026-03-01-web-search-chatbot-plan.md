# Web Search Chatbot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a web search chatbot with a 2-Agent architecture (Planner + Executor) that intelligently searches the web and responds with cited sources via streaming.

**Architecture:** FastAPI backend with Planner Agent (decides if search needed) and Executor Agent (synthesizes answers with citations). Next.js frontend with ChatGPT-style UI. SSE for real-time streaming.

**Tech Stack:** Python 3.11+, FastAPI, OpenAI GPT-4o, Tavily API, Next.js 14, React 18, TypeScript, Tailwind CSS, pytest, Vitest

---

### Task 1: Backend Project Scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/exceptions.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/schemas.py`
- Create: `backend/app/agents/__init__.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/.env.example`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "vulcan-chatbot"
version = "0.1.0"
description = "Web search chatbot with 2-Agent architecture"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "openai>=1.0.0",
    "httpx>=0.27.0",
    "sse-starlette>=2.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "respx>=0.21.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Create app/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    tavily_api_key: str = ""
    frontend_url: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
```

**Step 3: Create app/models/schemas.py**

```python
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
```

**Step 4: Create app/core/exceptions.py**

```python
from fastapi import Request
from fastapi.responses import JSONResponse


class ChatError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code


async def chat_error_handler(request: Request, exc: ChatError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message},
    )
```

**Step 5: Create app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import ChatError, chat_error_handler


def create_app() -> FastAPI:
    app = FastAPI(title="Vulcan Web Search Chatbot", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url, "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(ChatError, chat_error_handler)

    return app


app = create_app()
```

**Step 6: Create .env.example and all __init__.py files**

`.env.example`:
```
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-4o
TAVILY_API_KEY=tvly-your-tavily-api-key
FRONTEND_URL=http://localhost:3000
```

All `__init__.py` files are empty.

`tests/conftest.py`:
```python
import pytest

from app.config import Settings


@pytest.fixture
def test_settings():
    return Settings(
        openai_api_key="test-key",
        tavily_api_key="test-tavily-key",
    )
```

**Step 7: Create venv and install deps**

Run:
```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

**Step 8: Verify with a quick import test**

Run: `cd backend && source .venv/bin/activate && python -c "from app.main import app; print(app.title)"`
Expected: `Vulcan Web Search Chatbot`

**Step 9: Commit**

```bash
git add backend/
git commit -m "build(backend): scaffold FastAPI project with config, schemas, and exceptions"
```

---

### Task 2: Search Service (Tavily)

**Files:**
- Create: `backend/app/services/search_service.py`
- Create: `backend/tests/services/__init__.py`
- Create: `backend/tests/services/test_search_service.py`

**Step 1: Write the failing tests**

```python
# tests/services/test_search_service.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.search_service import SearchService
from app.models.schemas import SearchResult


@pytest.fixture
def search_service():
    return SearchService(api_key="test-tavily-key")


def _mock_tavily_response():
    return {
        "results": [
            {
                "title": "TSMC Stock Price",
                "url": "https://example.com/tsmc",
                "content": "TSMC stock is at $180",
                "score": 0.95,
            },
            {
                "title": "TSMC News",
                "url": "https://example.com/tsmc-news",
                "content": "TSMC reported Q4 earnings",
                "score": 0.85,
            },
        ]
    }


@pytest.mark.asyncio
async def test_search_returns_results(search_service):
    with patch.object(
        search_service._client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_tavily_response()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        results = await search_service.search("TSMC stock price")

        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "TSMC Stock Price"
        assert results[0].url == "https://example.com/tsmc"


@pytest.mark.asyncio
async def test_search_returns_empty_on_error(search_service):
    with patch.object(
        search_service._client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.side_effect = Exception("API Error")

        results = await search_service.search("failing query")

        assert results == []


@pytest.mark.asyncio
async def test_search_multiple_queries(search_service):
    with patch.object(
        search_service._client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_tavily_response()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        results = await search_service.search_multiple(
            ["query1", "query2"]
        )

        assert len(results) == 4  # 2 results per query, 2 queries
        assert mock_post.call_count == 2
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/services/test_search_service.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write the implementation**

```python
# app/services/search_service.py
import asyncio
import logging

import httpx

from app.models.schemas import SearchResult

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"


class SearchService:
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=10.0)

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        try:
            response = await self._client.post(
                TAVILY_API_URL,
                json={
                    "api_key": self._api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
            )
            response.raise_for_status()
            data = response.json()
            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=r.get("content", ""),
                    score=r.get("score", 0.0),
                )
                for r in data.get("results", [])
            ]
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            return []

    async def search_multiple(
        self, queries: list[str], max_results: int = 5
    ) -> list[SearchResult]:
        tasks = [self.search(q, max_results) for q in queries]
        results_lists = await asyncio.gather(*tasks)
        seen_urls: set[str] = set()
        unique_results: list[SearchResult] = []
        for results in results_lists:
            for r in results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    unique_results.append(r)
        return unique_results

    async def close(self):
        await self._client.aclose()
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/services/test_search_service.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add backend/app/services/search_service.py backend/tests/services/
git commit -m "feat(backend): add Tavily search service with multi-query support"
```

---

### Task 3: OpenAI Client Service

**Files:**
- Create: `backend/app/services/openai_client.py`
- Create: `backend/tests/services/test_openai_client.py`

**Step 1: Write the failing tests**

```python
# tests/services/test_openai_client.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.openai_client import OpenAIClient


@pytest.fixture
def openai_client():
    return OpenAIClient(api_key="test-key", model="gpt-4o")


@pytest.mark.asyncio
async def test_chat_completion_returns_content(openai_client):
    mock_choice = MagicMock()
    mock_choice.message.content = "Hello, world!"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch.object(
        openai_client._client.chat.completions,
        "create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await openai_client.chat(
            system_prompt="You are helpful.",
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert result == "Hello, world!"


@pytest.mark.asyncio
async def test_chat_stream_yields_chunks(openai_client):
    async def mock_stream():
        for text in ["Hello", ", ", "world!"]:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = text
            yield chunk

    with patch.object(
        openai_client._client.chat.completions,
        "create",
        new_callable=AsyncMock,
        return_value=mock_stream(),
    ):
        chunks = []
        async for chunk in openai_client.chat_stream(
            system_prompt="You are helpful.",
            messages=[{"role": "user", "content": "Hi"}],
        ):
            chunks.append(chunk)
        assert chunks == ["Hello", ", ", "world!"]
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/services/test_openai_client.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# app/services/openai_client.py
import logging
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.3,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system_prompt}, *messages],
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    async def chat_stream(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system_prompt}, *messages],
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/services/test_openai_client.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add backend/app/services/openai_client.py backend/tests/services/test_openai_client.py
git commit -m "feat(backend): add OpenAI client with streaming support"
```

---

### Task 4: Planner Agent

**Files:**
- Create: `backend/app/agents/planner.py`
- Create: `backend/tests/agents/__init__.py`
- Create: `backend/tests/agents/test_planner.py`

**Step 1: Write the failing tests**

```python
# tests/agents/test_planner.py
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
        # Falls back to search to be safe
        assert decision.needs_search is True
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/agents/test_planner.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# app/agents/planner.py
import json
import logging

from app.models.schemas import PlannerDecision
from app.services.openai_client import OpenAIClient

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
            # Strip markdown code fences if present
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
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/agents/test_planner.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add backend/app/agents/planner.py backend/tests/agents/
git commit -m "feat(backend): add Planner Agent with search decision logic"
```

---

### Task 5: Executor Agent

**Files:**
- Create: `backend/app/agents/executor.py`
- Create: `backend/tests/agents/test_executor.py`

**Step 1: Write the failing tests**

```python
# tests/agents/test_executor.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.executor import ExecutorAgent
from app.models.schemas import SearchResult, Citation


@pytest.fixture
def executor():
    return ExecutorAgent(api_key="test-key", model="gpt-4o")


@pytest.fixture
def sample_search_results():
    return [
        SearchResult(
            title="TSMC Stock",
            url="https://example.com/tsmc",
            content="TSMC stock is at $180",
            score=0.95,
        ),
        SearchResult(
            title="TSMC News",
            url="https://example.com/tsmc-news",
            content="TSMC Q4 earnings beat expectations",
            score=0.85,
        ),
    ]


@pytest.mark.asyncio
async def test_executor_streams_answer_with_search_results(
    executor, sample_search_results
):
    async def mock_stream():
        for text in ["TSMC ", "is at ", "$180 [1]"]:
            yield text

    with patch.object(
        executor._openai, "chat_stream", return_value=mock_stream()
    ):
        chunks = []
        async for chunk in executor.execute(
            message="What is TSMC stock price?",
            search_results=sample_search_results,
        ):
            chunks.append(chunk)
        assert len(chunks) == 3
        assert "".join(chunks) == "TSMC is at $180 [1]"


@pytest.mark.asyncio
async def test_executor_streams_answer_without_search(executor):
    async def mock_stream():
        for text in ["Hello! ", "How can ", "I help?"]:
            yield text

    with patch.object(
        executor._openai, "chat_stream", return_value=mock_stream()
    ):
        chunks = []
        async for chunk in executor.execute(
            message="Hi there!",
            search_results=[],
        ):
            chunks.append(chunk)
        assert "".join(chunks) == "Hello! How can I help?"


def test_build_citations(executor, sample_search_results):
    citations = executor.build_citations(sample_search_results)
    assert len(citations) == 2
    assert citations[0].index == 1
    assert citations[0].title == "TSMC Stock"
    assert citations[1].index == 2
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/agents/test_executor.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# app/agents/executor.py
import logging
from collections.abc import AsyncGenerator

from app.models.schemas import Citation, SearchResult
from app.services.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

EXECUTOR_SYSTEM_PROMPT_WITH_SEARCH = """You are a helpful assistant that answers questions based on web search results.

RULES:
1. Answer based on the provided search results
2. Cite sources using [1], [2], etc. markers that correspond to the search result indices
3. Be accurate and concise
4. If search results don't contain relevant information, say so honestly
5. Match your response language to the user's query language (Chinese → Chinese, English → English)
6. Use markdown formatting for readability

SEARCH RESULTS:
{search_results}"""

EXECUTOR_SYSTEM_PROMPT_NO_SEARCH = """You are a helpful assistant.

RULES:
1. Answer directly from your knowledge
2. Be accurate and concise
3. Match your response language to the user's query language
4. Use markdown formatting for readability"""


class ExecutorAgent:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._openai = OpenAIClient(api_key=api_key, model=model)

    async def execute(
        self,
        message: str,
        search_results: list[SearchResult],
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        if search_results:
            formatted = self._format_search_results(search_results)
            system_prompt = EXECUTOR_SYSTEM_PROMPT_WITH_SEARCH.format(
                search_results=formatted
            )
        else:
            system_prompt = EXECUTOR_SYSTEM_PROMPT_NO_SEARCH

        messages = list(history or [])
        messages.append({"role": "user", "content": message})

        async for chunk in self._openai.chat_stream(
            system_prompt=system_prompt,
            messages=messages,
        ):
            yield chunk

    def build_citations(self, search_results: list[SearchResult]) -> list[Citation]:
        return [
            Citation(
                index=i + 1,
                title=r.title,
                url=r.url,
                snippet=r.content[:200],
            )
            for i, r in enumerate(search_results)
        ]

    def _format_search_results(self, results: list[SearchResult]) -> str:
        parts = []
        for i, r in enumerate(results, 1):
            parts.append(f"[{i}] {r.title}\nURL: {r.url}\n{r.content}\n")
        return "\n".join(parts)
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/agents/test_executor.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add backend/app/agents/executor.py backend/tests/agents/test_executor.py
git commit -m "feat(backend): add Executor Agent with streaming and citation support"
```

---

### Task 6: Chat Service (Orchestrator)

**Files:**
- Create: `backend/app/services/chat_service.py`
- Create: `backend/tests/services/test_chat_service.py`

**Step 1: Write the failing tests**

```python
# tests/services/test_chat_service.py
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.chat_service import ChatService
from app.models.schemas import PlannerDecision, SearchResult


@pytest.fixture
def chat_service():
    return ChatService(
        openai_api_key="test-key",
        openai_model="gpt-4o",
        tavily_api_key="test-tavily",
    )


@pytest.mark.asyncio
async def test_chat_stream_with_search(chat_service):
    planner_decision = PlannerDecision(
        needs_search=True,
        reasoning="Need latest stock info",
        search_queries=["TSMC stock price"],
        query_type="temporal",
    )
    search_results = [
        SearchResult(
            title="TSMC Stock",
            url="https://example.com",
            content="TSMC is at $180",
            score=0.9,
        )
    ]

    async def mock_execute(*args, **kwargs):
        for chunk in ["TSMC ", "is $180 [1]"]:
            yield chunk

    with (
        patch.object(
            chat_service._planner, "plan",
            new_callable=AsyncMock, return_value=planner_decision,
        ),
        patch.object(
            chat_service._search, "search_multiple",
            new_callable=AsyncMock, return_value=search_results,
        ),
        patch.object(
            chat_service._executor, "execute", side_effect=mock_execute,
        ),
        patch.object(
            chat_service._executor, "build_citations",
            return_value=[],
        ),
    ):
        events = []
        async for event_type, data in chat_service.chat_stream("TSMC stock?"):
            events.append((event_type, data))

        event_types = [e[0] for e in events]
        assert "planner" in event_types
        assert "chunk" in event_types
        assert "done" in event_types


@pytest.mark.asyncio
async def test_chat_stream_without_search(chat_service):
    planner_decision = PlannerDecision(
        needs_search=False,
        reasoning="Simple greeting",
        search_queries=[],
        query_type="conversational",
    )

    async def mock_execute(*args, **kwargs):
        for chunk in ["Hello!"]:
            yield chunk

    with (
        patch.object(
            chat_service._planner, "plan",
            new_callable=AsyncMock, return_value=planner_decision,
        ),
        patch.object(
            chat_service._executor, "execute", side_effect=mock_execute,
        ),
        patch.object(
            chat_service._executor, "build_citations",
            return_value=[],
        ),
    ):
        events = []
        async for event_type, data in chat_service.chat_stream("Hello!"):
            events.append((event_type, data))

        event_types = [e[0] for e in events]
        assert "planner" in event_types
        assert "searching" not in event_types
        assert "chunk" in event_types
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/services/test_chat_service.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# app/services/chat_service.py
import json
import logging
from collections.abc import AsyncGenerator

from app.agents.planner import PlannerAgent
from app.agents.executor import ExecutorAgent
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        openai_api_key: str,
        openai_model: str,
        tavily_api_key: str,
    ):
        self._planner = PlannerAgent(api_key=openai_api_key, model=openai_model)
        self._executor = ExecutorAgent(api_key=openai_api_key, model=openai_model)
        self._search = SearchService(api_key=tavily_api_key)

    async def chat_stream(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[tuple[str, dict], None]:
        # Step 1: Planner decides
        decision = await self._planner.plan(message, history)
        yield "planner", decision.model_dump()

        # Step 2: Search if needed
        search_results = []
        if decision.needs_search and decision.search_queries:
            for query in decision.search_queries:
                yield "searching", {"query": query, "status": "searching"}

            search_results = await self._search.search_multiple(
                decision.search_queries
            )

            for query in decision.search_queries:
                yield "searching", {
                    "query": query,
                    "status": "done",
                    "results_count": len(search_results),
                }

        # Step 3: Executor generates answer
        async for chunk in self._executor.execute(
            message=message,
            search_results=search_results,
            history=history,
        ):
            yield "chunk", {"content": chunk}

        # Step 4: Send citations
        if search_results:
            citations = self._executor.build_citations(search_results)
            yield "citations", {
                "citations": [c.model_dump() for c in citations]
            }

        yield "done", {}
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/services/test_chat_service.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add backend/app/services/chat_service.py backend/tests/services/test_chat_service.py
git commit -m "feat(backend): add ChatService orchestrator for Planner→Search→Executor flow"
```

---

### Task 7: API Routes (Chat + Health)

**Files:**
- Create: `backend/app/api/routes/health.py`
- Create: `backend/app/api/routes/chat.py`
- Modify: `backend/app/main.py` — add route registration
- Create: `backend/tests/api/__init__.py`
- Create: `backend/tests/api/test_chat.py`

**Step 1: Write the failing tests**

```python
# tests/api/test_chat.py
import json
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_chat_rejects_empty_message(client):
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422


def test_chat_returns_sse_stream(client):
    async def mock_chat_stream(*args, **kwargs):
        yield "planner", {"needs_search": False, "reasoning": "test", "search_queries": [], "query_type": "conversational"}
        yield "chunk", {"content": "Hello!"}
        yield "done", {}

    with patch(
        "app.api.routes.chat.get_chat_service"
    ) as mock_get_service:
        mock_service = AsyncMock()
        mock_service.chat_stream = mock_chat_stream
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/chat",
            json={"message": "Hi there"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # Parse SSE events
        lines = response.text.strip().split("\n")
        events = []
        for line in lines:
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        assert len(events) >= 2  # at least planner + chunk + done
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/api/test_chat.py -v`
Expected: FAIL

**Step 3: Write health route**

```python
# app/api/routes/health.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
async def health():
    return {"status": "ok"}
```

**Step 4: Write chat route**

```python
# app/api/routes/chat.py
import json
import logging

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.models.schemas import ChatRequest
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_chat_service() -> ChatService:
    return ChatService(
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        tavily_api_key=settings.tavily_api_key,
    )


@router.post("/api/chat")
async def chat(request: ChatRequest):
    service = get_chat_service()
    history = [msg.model_dump() for msg in request.history]

    async def event_generator():
        try:
            async for event_type, data in service.chat_stream(
                message=request.message,
                history=history,
            ):
                yield {
                    "event": event_type,
                    "data": json.dumps(data, ensure_ascii=False),
                }
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)}),
            }

    return EventSourceResponse(event_generator())
```

**Step 5: Update main.py to register routes**

```python
# app/main.py — updated
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import ChatError, chat_error_handler
from app.api.routes import chat, health


def create_app() -> FastAPI:
    app = FastAPI(title="Vulcan Web Search Chatbot", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url, "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(ChatError, chat_error_handler)

    app.include_router(health.router)
    app.include_router(chat.router)

    return app


app = create_app()
```

**Step 6: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/api/test_chat.py -v`
Expected: 3 passed

**Step 7: Run all backend tests**

Run: `cd backend && source .venv/bin/activate && python -m pytest -v`
Expected: All tests passed (11 total)

**Step 8: Commit**

```bash
git add backend/app/api/ backend/app/main.py backend/tests/api/
git commit -m "feat(backend): add chat and health API routes with SSE streaming"
```

---

### Task 8: Backend Dockerfile and Makefile

**Files:**
- Create: `backend/Dockerfile`
- Create: `Makefile`

**Step 1: Create Backend Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY app/ app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 2: Create root Makefile**

```makefile
.PHONY: help setup-backend run-backend test-backend setup-frontend run-frontend test-frontend

help:
	@echo "Available targets:"
	@echo "  setup-backend   - Create venv and install backend deps"
	@echo "  run-backend     - Run FastAPI dev server"
	@echo "  test-backend    - Run backend tests"
	@echo "  setup-frontend  - Install frontend deps"
	@echo "  run-frontend    - Run Next.js dev server"
	@echo "  test-frontend   - Run frontend tests"

setup-backend:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"

run-backend:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

test-backend:
	cd backend && . .venv/bin/activate && python -m pytest -v

setup-frontend:
	cd frontend && npm install

run-frontend:
	cd frontend && npm run dev

test-frontend:
	cd frontend && npm test
```

**Step 3: Verify backend runs locally**

Run: `cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000 &`
Then: `curl http://localhost:8000/api/health`
Expected: `{"status":"ok"}`
Kill the server after verification.

**Step 4: Commit**

```bash
git add backend/Dockerfile Makefile
git commit -m "build: add backend Dockerfile and root Makefile"
```

---

### Task 9: Frontend Project Scaffold

**Files:**
- Create: `frontend/` — via `npx create-next-app`
- Modify: `frontend/package.json` — add dependencies
- Create: `frontend/src/lib/types.ts`
- Create: `frontend/.env.example`

**Step 1: Create Next.js project**

Run:
```bash
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --no-import-alias --use-npm
```

**Step 2: Install additional dependencies**

Run:
```bash
cd frontend && npm install react-markdown uuid && npm install -D @types/uuid vitest @testing-library/react @testing-library/jest-dom @vitejs/plugin-react jsdom
```

**Step 3: Create types.ts**

```typescript
// src/lib/types.ts
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface PlannerData {
  needs_search: boolean;
  reasoning: string;
  search_queries: string[];
  query_type: "temporal" | "factual" | "conversational";
}

export interface SearchingData {
  query: string;
  status: "searching" | "done";
  results_count?: number;
}

export interface ChunkData {
  content: string;
}

export interface CitationItem {
  index: number;
  title: string;
  url: string;
  snippet: string;
}

export interface CitationsData {
  citations: CitationItem[];
}

export type SSEEvent =
  | { event: "planner"; data: PlannerData }
  | { event: "searching"; data: SearchingData }
  | { event: "chunk"; data: ChunkData }
  | { event: "citations"; data: CitationsData }
  | { event: "done"; data: Record<string, unknown> }
  | { event: "error"; data: { message: string } };

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  citations: CitationItem[];
  createdAt: string;
}
```

**Step 4: Create .env.example**

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Step 5: Create vitest.config.ts**

```typescript
// frontend/vitest.config.ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: [],
  },
});
```

**Step 6: Add test script to package.json**

In `frontend/package.json`, add to scripts:
```json
"test": "vitest run",
"test:watch": "vitest"
```

**Step 7: Commit**

```bash
git add frontend/
echo "node_modules/" >> frontend/.gitignore
git commit -m "build(frontend): scaffold Next.js project with TypeScript, Tailwind, and types"
```

---

### Task 10: Frontend SSE Hook

**Files:**
- Create: `frontend/src/hooks/useSSE.ts`

**Step 1: Write the SSE hook**

```typescript
// src/hooks/useSSE.ts
import { useCallback, useRef } from "react";
import type {
  PlannerData,
  SearchingData,
  ChunkData,
  CitationsData,
} from "@/lib/types";

interface SSECallbacks {
  onPlanner?: (data: PlannerData) => void;
  onSearching?: (data: SearchingData) => void;
  onChunk?: (data: ChunkData) => void;
  onCitations?: (data: CitationsData) => void;
  onDone?: () => void;
  onError?: (error: string) => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useSSE() {
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (
      message: string,
      history: { role: string; content: string }[],
      callbacks: SSECallbacks
    ) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await fetch(`${API_URL}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message, history }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          let currentEvent = "";
          for (const line of lines) {
            if (line.startsWith("event: ")) {
              currentEvent = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              const rawData = line.slice(6);
              try {
                const data = JSON.parse(rawData);
                switch (currentEvent) {
                  case "planner":
                    callbacks.onPlanner?.(data);
                    break;
                  case "searching":
                    callbacks.onSearching?.(data);
                    break;
                  case "chunk":
                    callbacks.onChunk?.(data);
                    break;
                  case "citations":
                    callbacks.onCitations?.(data);
                    break;
                  case "done":
                    callbacks.onDone?.();
                    break;
                  case "error":
                    callbacks.onError?.(data.message);
                    break;
                }
              } catch {
                // skip malformed JSON
              }
              currentEvent = "";
            }
          }
        }

        callbacks.onDone?.();
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") {
          callbacks.onError?.(err.message);
        }
      }
    },
    []
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { sendMessage, abort };
}
```

**Step 2: Commit**

```bash
git add frontend/src/hooks/useSSE.ts
git commit -m "feat(frontend): add useSSE hook for streaming chat responses"
```

---

### Task 11: Frontend Chat Hook

**Files:**
- Create: `frontend/src/hooks/useChat.ts`

**Step 1: Write the chat state management hook**

```typescript
// src/hooks/useChat.ts
"use client";

import { useState, useCallback } from "react";
import { v4 as uuidv4 } from "uuid";
import { useSSE } from "./useSSE";
import type {
  ChatMessage,
  CitationItem,
  PlannerData,
  SearchingData,
  Conversation,
} from "@/lib/types";

interface ChatState {
  isLoading: boolean;
  messages: ChatMessage[];
  citations: CitationItem[];
  planner: PlannerData | null;
  searchStatus: SearchingData[];
  streamingContent: string;
}

export function useChat() {
  const { sendMessage: sseMessage, abort } = useSSE();
  const [conversations, setConversations] = useState<Conversation[]>(() => {
    if (typeof window === "undefined") return [];
    const saved = localStorage.getItem("conversations");
    return saved ? JSON.parse(saved) : [];
  });
  const [activeId, setActiveId] = useState<string | null>(null);
  const [state, setState] = useState<ChatState>({
    isLoading: false,
    messages: [],
    citations: [],
    planner: null,
    searchStatus: [],
    streamingContent: "",
  });

  const saveConversations = useCallback((convs: Conversation[]) => {
    setConversations(convs);
    localStorage.setItem("conversations", JSON.stringify(convs));
  }, []);

  const newChat = useCallback(() => {
    const id = uuidv4();
    setActiveId(id);
    setState({
      isLoading: false,
      messages: [],
      citations: [],
      planner: null,
      searchStatus: [],
      streamingContent: "",
    });
    return id;
  }, []);

  const loadConversation = useCallback((conv: Conversation) => {
    setActiveId(conv.id);
    setState({
      isLoading: false,
      messages: conv.messages,
      citations: conv.citations,
      planner: null,
      searchStatus: [],
      streamingContent: "",
    });
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      const userMessage: ChatMessage = { role: "user", content };
      const currentMessages = [...state.messages, userMessage];

      setState((prev) => ({
        ...prev,
        messages: currentMessages,
        isLoading: true,
        planner: null,
        searchStatus: [],
        streamingContent: "",
        citations: [],
      }));

      let fullContent = "";
      let finalCitations: CitationItem[] = [];
      let currentId = activeId || newChat();

      await sseMessage(
        content,
        currentMessages.slice(0, -1).map((m) => ({
          role: m.role,
          content: m.content,
        })),
        {
          onPlanner: (data) => {
            setState((prev) => ({ ...prev, planner: data }));
          },
          onSearching: (data) => {
            setState((prev) => ({
              ...prev,
              searchStatus: [...prev.searchStatus.filter(
                (s) => !(s.query === data.query && data.status === "done")
              ), data],
            }));
          },
          onChunk: (data) => {
            fullContent += data.content;
            setState((prev) => ({
              ...prev,
              streamingContent: fullContent,
            }));
          },
          onCitations: (data) => {
            finalCitations = data.citations;
            setState((prev) => ({
              ...prev,
              citations: data.citations,
            }));
          },
          onDone: () => {
            const assistantMessage: ChatMessage = {
              role: "assistant",
              content: fullContent,
            };
            const updatedMessages = [...currentMessages, assistantMessage];

            setState((prev) => ({
              ...prev,
              messages: updatedMessages,
              isLoading: false,
              streamingContent: "",
            }));

            // Save conversation
            setConversations((prev) => {
              const title =
                content.length > 30
                  ? content.slice(0, 30) + "..."
                  : content;
              const existing = prev.find((c) => c.id === currentId);
              let updated: Conversation[];
              if (existing) {
                updated = prev.map((c) =>
                  c.id === currentId
                    ? {
                        ...c,
                        messages: updatedMessages,
                        citations: finalCitations,
                      }
                    : c
                );
              } else {
                updated = [
                  {
                    id: currentId,
                    title,
                    messages: updatedMessages,
                    citations: finalCitations,
                    createdAt: new Date().toISOString(),
                  },
                  ...prev,
                ];
              }
              localStorage.setItem("conversations", JSON.stringify(updated));
              return updated;
            });
          },
          onError: (error) => {
            setState((prev) => ({
              ...prev,
              isLoading: false,
              streamingContent: "",
            }));
            console.error("Chat error:", error);
          },
        }
      );
    },
    [state.messages, activeId, sseMessage, newChat]
  );

  const deleteConversation = useCallback(
    (id: string) => {
      const updated = conversations.filter((c) => c.id !== id);
      saveConversations(updated);
      if (activeId === id) {
        setActiveId(null);
        setState({
          isLoading: false,
          messages: [],
          citations: [],
          planner: null,
          searchStatus: [],
          streamingContent: "",
        });
      }
    },
    [conversations, activeId, saveConversations]
  );

  return {
    ...state,
    conversations,
    activeId,
    sendMessage,
    newChat,
    loadConversation,
    deleteConversation,
    abort,
  };
}
```

**Step 2: Commit**

```bash
git add frontend/src/hooks/useChat.ts
git commit -m "feat(frontend): add useChat hook with conversation state management"
```

---

### Task 12: Frontend UI Components

**Files:**
- Create: `frontend/src/components/ChatInput.tsx`
- Create: `frontend/src/components/StreamingText.tsx`
- Create: `frontend/src/components/AgentThinking.tsx`
- Create: `frontend/src/components/SearchProgress.tsx`
- Create: `frontend/src/components/CitationCard.tsx`
- Create: `frontend/src/components/CitationList.tsx`
- Create: `frontend/src/components/MessageBubble.tsx`
- Create: `frontend/src/components/ChatPanel.tsx`
- Create: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/ChatLayout.tsx`

**Step 1: Create ChatInput.tsx**

```tsx
// src/components/ChatInput.tsx
"use client";

import { useState, useRef, type KeyboardEvent } from "react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  };

  return (
    <div className="flex items-end gap-2 p-4 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
      <textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => {
          setInput(e.target.value);
          handleInput();
        }}
        onKeyDown={handleKeyDown}
        placeholder="Ask anything..."
        disabled={disabled}
        rows={1}
        className="flex-1 resize-none rounded-xl border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:text-white placeholder-gray-400 disabled:opacity-50"
      />
      <button
        onClick={handleSend}
        disabled={disabled || !input.trim()}
        className="rounded-xl bg-blue-600 px-4 py-3 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        Send
      </button>
    </div>
  );
}
```

**Step 2: Create StreamingText.tsx**

```tsx
// src/components/StreamingText.tsx
"use client";

import ReactMarkdown from "react-markdown";

interface StreamingTextProps {
  content: string;
  isStreaming?: boolean;
}

export function StreamingText({ content, isStreaming }: StreamingTextProps) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none">
      <ReactMarkdown>{content}</ReactMarkdown>
      {isStreaming && (
        <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-0.5" />
      )}
    </div>
  );
}
```

**Step 3: Create AgentThinking.tsx**

```tsx
// src/components/AgentThinking.tsx
"use client";

import { useState } from "react";
import type { PlannerData } from "@/lib/types";

interface AgentThinkingProps {
  planner: PlannerData;
}

export function AgentThinking({ planner }: AgentThinkingProps) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="mb-3 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/30 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
      >
        <span className="font-medium">
          {planner.needs_search ? "Searching the web" : "Answering directly"}
        </span>
        <span className="ml-auto">{expanded ? "▼" : "▶"}</span>
      </button>
      {expanded && (
        <div className="px-3 pb-2 text-xs text-blue-600 dark:text-blue-400 space-y-1">
          <p>{planner.reasoning}</p>
          {planner.search_queries.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {planner.search_queries.map((q, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 bg-blue-100 dark:bg-blue-800 rounded-full text-xs"
                >
                  {q}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

**Step 4: Create SearchProgress.tsx**

```tsx
// src/components/SearchProgress.tsx
"use client";

import type { SearchingData } from "@/lib/types";

interface SearchProgressProps {
  searches: SearchingData[];
}

export function SearchProgress({ searches }: SearchProgressProps) {
  if (searches.length === 0) return null;

  return (
    <div className="mb-3 space-y-1">
      {searches.map((s, i) => (
        <div
          key={`${s.query}-${i}`}
          className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400"
        >
          {s.status === "searching" ? (
            <span className="inline-block w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          ) : (
            <span className="text-green-500">✓</span>
          )}
          <span>
            {s.query}
            {s.status === "done" && s.results_count !== undefined && (
              <span className="ml-1 text-gray-400">
                ({s.results_count} results)
              </span>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}
```

**Step 5: Create CitationCard.tsx and CitationList.tsx**

```tsx
// src/components/CitationCard.tsx
"use client";

import type { CitationItem } from "@/lib/types";

interface CitationCardProps {
  citation: CitationItem;
}

export function CitationCard({ citation }: CitationCardProps) {
  const domain = (() => {
    try {
      return new URL(citation.url).hostname.replace("www.", "");
    } catch {
      return citation.url;
    }
  })();

  return (
    <a
      href={citation.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex flex-col gap-1 p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 hover:border-blue-300 dark:hover:border-blue-600 transition-colors min-w-[180px] max-w-[240px]"
    >
      <div className="flex items-center gap-1.5">
        <span className="flex items-center justify-center w-5 h-5 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300 text-xs font-bold">
          {citation.index}
        </span>
        <span className="text-xs text-gray-400 truncate">{domain}</span>
      </div>
      <span className="text-xs font-medium text-gray-700 dark:text-gray-300 line-clamp-2">
        {citation.title}
      </span>
    </a>
  );
}
```

```tsx
// src/components/CitationList.tsx
"use client";

import type { CitationItem } from "@/lib/types";
import { CitationCard } from "./CitationCard";

interface CitationListProps {
  citations: CitationItem[];
}

export function CitationList({ citations }: CitationListProps) {
  if (citations.length === 0) return null;

  return (
    <div className="mt-3">
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
        Sources
      </p>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {citations.map((c) => (
          <CitationCard key={c.index} citation={c} />
        ))}
      </div>
    </div>
  );
}
```

**Step 6: Create MessageBubble.tsx**

```tsx
// src/components/MessageBubble.tsx
"use client";

import type { ChatMessage, CitationItem, PlannerData, SearchingData } from "@/lib/types";
import { StreamingText } from "./StreamingText";
import { AgentThinking } from "./AgentThinking";
import { SearchProgress } from "./SearchProgress";
import { CitationList } from "./CitationList";

interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
  streamingContent?: string;
  planner?: PlannerData | null;
  searchStatus?: SearchingData[];
  citations?: CitationItem[];
}

export function MessageBubble({
  message,
  isStreaming,
  streamingContent,
  planner,
  searchStatus = [],
  citations = [],
}: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[80%] ${
          isUser
            ? "bg-blue-600 text-white rounded-2xl rounded-br-md px-4 py-2.5"
            : "bg-transparent"
        }`}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div>
            {planner && <AgentThinking planner={planner} />}
            {searchStatus.length > 0 && (
              <SearchProgress searches={searchStatus} />
            )}
            <StreamingText
              content={isStreaming ? (streamingContent || "") : message.content}
              isStreaming={isStreaming}
            />
            {!isStreaming && <CitationList citations={citations} />}
          </div>
        )}
      </div>
    </div>
  );
}
```

**Step 7: Create ChatPanel.tsx**

```tsx
// src/components/ChatPanel.tsx
"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage, CitationItem, PlannerData, SearchingData } from "@/lib/types";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";

interface ChatPanelProps {
  messages: ChatMessage[];
  isLoading: boolean;
  streamingContent: string;
  planner: PlannerData | null;
  searchStatus: SearchingData[];
  citations: CitationItem[];
  onSend: (message: string) => void;
}

export function ChatPanel({
  messages,
  isLoading,
  streamingContent,
  planner,
  searchStatus,
  citations,
  onSend,
}: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const showEmpty = messages.length === 0 && !isLoading;

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {showEmpty && (
          <div className="flex flex-col items-center justify-center h-full text-gray-400 dark:text-gray-500">
            <h2 className="text-2xl font-semibold mb-2">Web Search Chatbot</h2>
            <p className="text-sm">Ask me anything. I can search the web for the latest info.</p>
          </div>
        )}
        {messages.map((msg, i) => {
          const isLast = i === messages.length - 1;
          const isAssistantStreaming =
            isLast && msg.role === "assistant" && isLoading;

          return (
            <MessageBubble
              key={i}
              message={msg}
              isStreaming={isAssistantStreaming}
              streamingContent={isAssistantStreaming ? streamingContent : undefined}
              citations={isLast && msg.role === "assistant" ? citations : []}
            />
          );
        })}

        {isLoading && messages[messages.length - 1]?.role === "user" && (
          <MessageBubble
            message={{ role: "assistant", content: "" }}
            isStreaming={true}
            streamingContent={streamingContent}
            planner={planner}
            searchStatus={searchStatus}
            citations={[]}
          />
        )}

        <div ref={bottomRef} />
      </div>
      <ChatInput onSend={onSend} disabled={isLoading} />
    </div>
  );
}
```

**Step 8: Create Sidebar.tsx**

```tsx
// src/components/Sidebar.tsx
"use client";

import type { Conversation } from "@/lib/types";

interface SidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  onNewChat: () => void;
  onSelect: (conv: Conversation) => void;
  onDelete: (id: string) => void;
  onClose?: () => void;
}

export function Sidebar({
  conversations,
  activeId,
  onNewChat,
  onSelect,
  onDelete,
  onClose,
}: SidebarProps) {
  return (
    <div className="flex flex-col h-full bg-gray-900 text-white">
      <div className="p-3">
        <button
          onClick={() => {
            onNewChat();
            onClose?.();
          }}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border border-gray-600 hover:bg-gray-700 transition-colors text-sm"
        >
          <span>+</span>
          <span>New Chat</span>
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
        {conversations.map((conv) => (
          <div
            key={conv.id}
            className={`group flex items-center gap-1 px-3 py-2 rounded-lg cursor-pointer text-sm transition-colors ${
              activeId === conv.id
                ? "bg-gray-700"
                : "hover:bg-gray-800"
            }`}
            onClick={() => {
              onSelect(conv);
              onClose?.();
            }}
          >
            <span className="flex-1 truncate text-gray-300">
              {conv.title}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(conv.id);
              }}
              className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-opacity text-xs"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Step 9: Create ChatLayout.tsx**

```tsx
// src/components/ChatLayout.tsx
"use client";

import { useState } from "react";
import { useChat } from "@/hooks/useChat";
import { ChatPanel } from "./ChatPanel";
import { Sidebar } from "./Sidebar";

export function ChatLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const {
    messages,
    isLoading,
    streamingContent,
    planner,
    searchStatus,
    citations,
    conversations,
    activeId,
    sendMessage,
    newChat,
    loadConversation,
    deleteConversation,
  } = useChat();

  return (
    <div className="flex h-screen bg-white dark:bg-gray-900">
      {/* Desktop sidebar */}
      <div className="hidden md:block w-64 flex-shrink-0 border-r border-gray-200 dark:border-gray-700">
        <Sidebar
          conversations={conversations}
          activeId={activeId}
          onNewChat={newChat}
          onSelect={loadConversation}
          onDelete={deleteConversation}
        />
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="w-64">
            <Sidebar
              conversations={conversations}
              activeId={activeId}
              onNewChat={newChat}
              onSelect={loadConversation}
              onDelete={deleteConversation}
              onClose={() => setSidebarOpen(false)}
            />
          </div>
          <div
            className="flex-1 bg-black/50"
            onClick={() => setSidebarOpen(false)}
          />
        </div>
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <button
            className="md:hidden text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            onClick={() => setSidebarOpen(true)}
          >
            ☰
          </button>
          <h1 className="text-sm font-semibold text-gray-700 dark:text-gray-200">
            Web Search Chatbot
          </h1>
        </div>

        <ChatPanel
          messages={messages}
          isLoading={isLoading}
          streamingContent={streamingContent}
          planner={planner}
          searchStatus={searchStatus}
          citations={citations}
          onSend={sendMessage}
        />
      </div>
    </div>
  );
}
```

**Step 10: Update page.tsx**

Replace `frontend/app/page.tsx` with:

```tsx
import { ChatLayout } from "@/components/ChatLayout";

export default function Home() {
  return <ChatLayout />;
}
```

**Step 11: Update layout.tsx**

Replace `frontend/app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Web Search Chatbot",
  description: "AI-powered chatbot with web search capabilities",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
```

**Step 12: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 13: Commit**

```bash
git add frontend/src/components/ frontend/app/
git commit -m "feat(frontend): add complete ChatGPT-style UI with streaming, citations, and sidebar"
```

---

### Task 13: Frontend Styling Polish

**Files:**
- Modify: `frontend/app/globals.css`

**Step 1: Update globals.css for dark mode and typography**

Replace the `globals.css` content (keep Tailwind directives, add custom styles):

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  html {
    color-scheme: dark;
  }

  body {
    @apply bg-gray-900 text-gray-100;
  }

  /* Scrollbar styling */
  ::-webkit-scrollbar {
    width: 6px;
  }

  ::-webkit-scrollbar-track {
    background: transparent;
  }

  ::-webkit-scrollbar-thumb {
    @apply bg-gray-700 rounded-full;
  }

  ::-webkit-scrollbar-thumb:hover {
    @apply bg-gray-600;
  }
}

/* Markdown prose overrides */
.prose pre {
  @apply bg-gray-800 rounded-lg;
}

.prose code {
  @apply text-blue-300 bg-gray-800 px-1 py-0.5 rounded text-xs;
}

.prose a {
  @apply text-blue-400 hover:text-blue-300;
}
```

**Step 2: Verify frontend runs**

Run: `cd frontend && npm run dev`
Open: `http://localhost:3000`
Expected: Dark-themed ChatGPT-style UI renders

**Step 3: Commit**

```bash
git add frontend/app/globals.css
git commit -m "style(frontend): add dark mode styling and typography polish"
```

---

### Task 14: Frontend Tests

**Files:**
- Create: `frontend/src/__tests__/ChatInput.test.tsx`

**Step 1: Write ChatInput tests**

```tsx
// src/__tests__/ChatInput.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatInput } from "@/components/ChatInput";

describe("ChatInput", () => {
  it("renders input and send button", () => {
    render(<ChatInput onSend={vi.fn()} />);
    expect(screen.getByPlaceholderText("Ask anything...")).toBeDefined();
    expect(screen.getByText("Send")).toBeDefined();
  });

  it("calls onSend when button clicked with text", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    const textarea = screen.getByPlaceholderText("Ask anything...");
    fireEvent.change(textarea, { target: { value: "Hello" } });
    fireEvent.click(screen.getByText("Send"));

    expect(onSend).toHaveBeenCalledWith("Hello");
  });

  it("does not send empty messages", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    fireEvent.click(screen.getByText("Send"));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables input when disabled prop is true", () => {
    render(<ChatInput onSend={vi.fn()} disabled />);
    const textarea = screen.getByPlaceholderText("Ask anything...");
    expect(textarea).toHaveProperty("disabled", true);
  });
});
```

**Step 2: Add testing library setup for vitest**

Update `frontend/vitest.config.ts`:

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
```

**Step 3: Run tests**

Run: `cd frontend && npx vitest run`
Expected: All tests pass

**Step 4: Commit**

```bash
git add frontend/src/__tests__/ frontend/vitest.config.ts
git commit -m "test(frontend): add ChatInput component tests"
```

---

### Task 15: Frontend Dockerfile

**Files:**
- Create: `frontend/Dockerfile`

**Step 1: Create Dockerfile**

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
```

**Step 2: Update next.config.ts for standalone output**

In `frontend/next.config.ts`, add:
```typescript
const nextConfig = {
  output: "standalone",
};
```

**Step 3: Commit**

```bash
git add frontend/Dockerfile frontend/next.config.ts
git commit -m "build(frontend): add Dockerfile with standalone output"
```

---

### Task 16: README

**Files:**
- Create: `README.md`

**Step 1: Write comprehensive README**

```markdown
# Web Search Chatbot

A web search chatbot powered by a 2-Agent AI architecture that intelligently searches the web and provides answers with cited sources.

## Architecture

```
User → Next.js Frontend → FastAPI Backend
                              │
                        Chat Service (Orchestrator)
                              │
                ┌─────────────┼─────────────┐
                │             │             │
          Planner Agent  Search Service  Executor Agent
          (GPT-4o)       (Tavily API)    (GPT-4o)
```

### 2-Agent Design

- **Planner Agent**: Analyzes user queries to decide if web search is needed. Classifies queries as temporal, factual, or conversational, and generates optimized search keywords.
- **Executor Agent**: Synthesizes answers from search results (when available) or model knowledge. Generates responses with citation markers [1], [2] and streams them via SSE.

### Key Features

- Real-time streaming responses (SSE)
- Intelligent search decision making
- Source citations with clickable references
- Agent thinking process visualization
- Multi-conversation management
- Responsive ChatGPT-style UI
- Dark mode

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS |
| Backend | Python 3.11+, FastAPI, Pydantic |
| LLM | OpenAI GPT-4o |
| Search | Tavily API |
| Streaming | Server-Sent Events (SSE) |
| Testing | pytest (backend), Vitest (frontend) |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- OpenAI API key
- Tavily API key (free tier: https://tavily.com)

### Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Create .env file
cp .env.example .env
# Edit .env and add your API keys

# Run dev server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install

# Create .env.local
cp .env.example .env.local

# Run dev server
npm run dev
```

Open http://localhost:3000

### Using Makefile

```bash
make setup-backend    # Create venv and install deps
make setup-frontend   # Install npm deps
make run-backend      # Start FastAPI dev server
make run-frontend     # Start Next.js dev server
make test-backend     # Run backend tests
make test-frontend    # Run frontend tests
```

## API

### POST /api/chat

Send a chat message and receive a streaming SSE response.

**Request:**
```json
{
  "message": "What is TSMC stock price today?",
  "history": []
}
```

**SSE Events:**
| Event | Description |
|-------|-----------|
| `planner` | Planner Agent's decision (search/no-search, reasoning) |
| `searching` | Search progress for each query |
| `chunk` | Answer text chunk (streaming) |
| `citations` | Source references |
| `done` | Stream complete |

### GET /api/health

Health check endpoint.

## Testing

```bash
# Backend tests (all mocked, no API keys needed)
make test-backend

# Frontend tests
make test-frontend
```

## Environment Variables

### Backend (.env)
| Variable | Description | Required |
|----------|-----------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `OPENAI_MODEL` | Model name (default: gpt-4o) | No |
| `TAVILY_API_KEY` | Tavily search API key | Yes |
| `FRONTEND_URL` | Frontend URL for CORS | No |

### Frontend (.env.local)
| Variable | Description | Required |
|----------|-----------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | Yes |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── agents/          # Planner + Executor agents
│   │   ├── api/routes/      # FastAPI routes
│   │   ├── services/        # Chat, OpenAI, Search services
│   │   ├── models/          # Pydantic schemas
│   │   └── core/            # Exceptions
│   └── tests/               # pytest test suite
├── frontend/
│   ├── app/                 # Next.js app router
│   └── src/
│       ├── components/      # React components
│       ├── hooks/           # Custom hooks (useChat, useSSE)
│       └── lib/             # Types and utilities
├── docs/
│   └── plans/               # Design documents
└── Makefile
```
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add comprehensive README with architecture, setup, and API documentation"
```

---

### Task 17: AI Usage Documentation

**Files:**
- Create: `docs/ai_usage.md`

**Step 1: Write AI usage documentation**

```markdown
# AI Tool Usage

This project was developed with assistance from AI tools as encouraged by the assignment guidelines.

## Tools Used

- **Claude Code (Anthropic)** — Used for architecture design, code generation, and debugging

## Usage Approach

1. **Design Phase**: Used Claude Code to brainstorm and validate the 2-Agent architecture design (Planner + Executor)
2. **Implementation**: Generated boilerplate code and service layer implementations with AI assistance, then reviewed and refined manually
3. **Testing**: AI-assisted test case generation, ensuring comprehensive coverage of edge cases
4. **Documentation**: AI-assisted README and design document writing

## Prompts

Key prompts used during development:

- "Design a 2-Agent architecture for a web search chatbot that decides when to search"
- "Implement a FastAPI SSE streaming endpoint for chat responses"
- "Create a ChatGPT-style React UI with Tailwind CSS"
- "Write pytest tests for the Planner Agent with mocked OpenAI calls"

All AI-generated code was reviewed, tested, and modified as needed.
```

**Step 2: Commit**

```bash
git add docs/ai_usage.md
git commit -m "docs: add AI tool usage documentation"
```

---

### Task 18: Gitignore and Final Cleanup

**Files:**
- Create: `.gitignore`
- Verify: No API keys or assignment PDF in tracked files

**Step 1: Create root .gitignore**

```
# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/
dist/
build/

# Node
node_modules/
.next/
out/

# Environment
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Assignment (do not include per instructions)
Vulcan_SWE_Assignment_Senior.pdf

# Claude
.claude/
```

**Step 2: Remove PDF from git tracking if present**

Run: `git rm --cached Vulcan_SWE_Assignment_Senior.pdf 2>/dev/null; echo "done"`

**Step 3: Commit**

```bash
git add .gitignore
git commit -m "build: add .gitignore and exclude assignment PDF"
```

**Step 4: Verify final state**

Run: `git log --oneline`
Expected: Clean conventional commit history showing incremental development

Run: `git ls-files | grep -E '\.(env|key|token)' || echo "No secrets found"`
Expected: "No secrets found"

---

## Summary

| Task | Description | Commit |
|------|-----------|--------|
| 1 | Backend project scaffold | `build(backend): scaffold FastAPI project` |
| 2 | Search Service (Tavily) | `feat(backend): add Tavily search service` |
| 3 | OpenAI Client Service | `feat(backend): add OpenAI client with streaming` |
| 4 | Planner Agent | `feat(backend): add Planner Agent` |
| 5 | Executor Agent | `feat(backend): add Executor Agent` |
| 6 | Chat Service Orchestrator | `feat(backend): add ChatService orchestrator` |
| 7 | API Routes (Chat + Health) | `feat(backend): add chat and health API routes` |
| 8 | Backend Dockerfile + Makefile | `build: add backend Dockerfile and Makefile` |
| 9 | Frontend project scaffold | `build(frontend): scaffold Next.js project` |
| 10 | SSE Hook | `feat(frontend): add useSSE hook` |
| 11 | Chat Hook | `feat(frontend): add useChat hook` |
| 12 | UI Components | `feat(frontend): add ChatGPT-style UI` |
| 13 | Styling Polish | `style(frontend): dark mode styling` |
| 14 | Frontend Tests | `test(frontend): add ChatInput tests` |
| 15 | Frontend Dockerfile | `build(frontend): add Dockerfile` |
| 16 | README | `docs: add comprehensive README` |
| 17 | AI Usage Documentation | `docs: add AI tool usage documentation` |
| 18 | Gitignore + Cleanup | `build: add .gitignore` |
