# Telegram Bot Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Telegram bot support with full chat, scheduled digests, and notification API via a Core + Gateway architecture refactoring.

**Architecture:** Refactor `backend/app/` into three layers: `core/` (shared agents, services, models), `web/` (FastAPI SSE gateway), and `telegram/` (python-telegram-bot gateway). ChatService yields structured `ChatEvent` dataclasses; each gateway converts to its platform format.

**Tech Stack:** python-telegram-bot[ext], APScheduler, aiosqlite, SQLite

---

### Task 1: Add New Dependencies

**Files:**
- Modify: `backend/pyproject.toml`

**Step 1: Update pyproject.toml**

Add telegram, scheduler, and sqlite dependencies:

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
    "python-telegram-bot[ext]>=21.0",
    "apscheduler>=3.10.0",
    "aiosqlite>=0.20.0",
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

**Step 2: Install dependencies**

Run: `cd backend && . .venv/bin/activate && pip install -e ".[dev]"`
Expected: All packages install successfully

**Step 3: Commit**

```bash
git add backend/pyproject.toml
git commit -m "build: add telegram bot, apscheduler, and aiosqlite dependencies"
```

---

### Task 2: Create Core Event Model

**Files:**
- Create: `backend/app/core/__init__.py` (already exists implicitly, ensure it's a package)
- Create: `backend/app/core/models/__init__.py`
- Create: `backend/app/core/models/events.py`

**Step 1: Write the failing test**

Create `backend/tests/core/__init__.py` (empty) and `backend/tests/core/models/__init__.py` (empty).

Create `backend/tests/core/models/test_events.py`:

```python
import pytest
from app.core.models.events import (
    PlannerEvent,
    SearchingEvent,
    ChunkEvent,
    CitationsEvent,
    DoneEvent,
    ChatEvent,
)


def test_planner_event_creation():
    event = PlannerEvent(
        needs_search=True,
        reasoning="Need latest info",
        search_queries=["TSMC stock"],
        query_type="temporal",
    )
    assert event.needs_search is True
    assert event.reasoning == "Need latest info"
    assert event.search_queries == ["TSMC stock"]
    assert event.query_type == "temporal"


def test_searching_event_creation():
    event = SearchingEvent(query="TSMC stock", status="searching")
    assert event.query == "TSMC stock"
    assert event.status == "searching"
    assert event.results_count is None


def test_searching_event_with_results_count():
    event = SearchingEvent(query="TSMC stock", status="done", results_count=5)
    assert event.results_count == 5


def test_chunk_event_creation():
    event = ChunkEvent(content="Hello ")
    assert event.content == "Hello "


def test_citations_event_creation():
    citations = [{"index": 1, "title": "Test", "url": "https://example.com", "snippet": "..."}]
    event = CitationsEvent(citations=citations)
    assert len(event.citations) == 1


def test_done_event_creation():
    event = DoneEvent()
    assert isinstance(event, DoneEvent)


def test_chat_event_type_union():
    """ChatEvent type alias should accept all event types."""
    events: list[ChatEvent] = [
        PlannerEvent(needs_search=False, reasoning="test", search_queries=[], query_type="conversational"),
        SearchingEvent(query="q", status="searching"),
        ChunkEvent(content="hi"),
        CitationsEvent(citations=[]),
        DoneEvent(),
    ]
    assert len(events) == 5
```

**Step 2: Run test to verify it fails**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/core/models/test_events.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.models'`

**Step 3: Write minimal implementation**

Create `backend/app/core/models/__init__.py` (empty file).

Create `backend/app/core/models/events.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/core/models/test_events.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add backend/app/core/models/ backend/tests/core/
git commit -m "feat(core): add ChatEvent dataclass model for gateway abstraction"
```

---

### Task 3: Restructure Backend — Move Code to Core + Web

This task moves existing files into the `core/` and `web/` directory structure. Since moving files changes all imports simultaneously, this is done as one atomic operation.

**Files:**
- Move: `backend/app/agents/` → `backend/app/core/agents/`
- Move: `backend/app/services/` → `backend/app/core/services/`
- Move: `backend/app/models/schemas.py` → `backend/app/core/models/schemas.py`
- Move: `backend/app/config.py` → `backend/app/core/config.py`
- Keep: `backend/app/core/exceptions.py` (already in place)
- Move: `backend/app/api/routes/chat.py` → `backend/app/web/routes/chat.py`
- Move: `backend/app/api/routes/health.py` → `backend/app/web/routes/health.py`
- Move: `backend/app/main.py` → `backend/app/web/main.py`
- Move tests: `backend/tests/agents/` → `backend/tests/core/agents/`
- Move tests: `backend/tests/services/` → `backend/tests/core/services/`
- Move tests: `backend/tests/api/` → `backend/tests/web/`

**Step 1: Create directory structure and move files**

```bash
cd backend

# Create core subdirectories
mkdir -p app/core/agents app/core/services

# Move agents
git mv app/agents/planner.py app/core/agents/planner.py
git mv app/agents/executor.py app/core/agents/executor.py
# Create __init__.py for core/agents
touch app/core/agents/__init__.py

# Move services
git mv app/services/chat_service.py app/core/services/chat_service.py
git mv app/services/openai_client.py app/core/services/openai_client.py
git mv app/services/search_service.py app/core/services/search_service.py
touch app/core/services/__init__.py

# Move models (schemas.py → core/models/ which already has events.py)
git mv app/models/schemas.py app/core/models/schemas.py

# Move config
git mv app/config.py app/core/config.py

# Create web gateway
mkdir -p app/web/routes
touch app/web/__init__.py
touch app/web/routes/__init__.py
git mv app/api/routes/chat.py app/web/routes/chat.py
git mv app/api/routes/health.py app/web/routes/health.py
git mv app/main.py app/web/main.py

# Clean up old empty directories
rm -rf app/agents app/services app/models app/api

# Move tests
mkdir -p tests/core/agents tests/core/services tests/web
touch tests/core/agents/__init__.py
touch tests/core/services/__init__.py
touch tests/web/__init__.py
git mv tests/agents/test_planner.py tests/core/agents/test_planner.py
git mv tests/agents/test_executor.py tests/core/agents/test_executor.py
git mv tests/services/test_chat_service.py tests/core/services/test_chat_service.py
git mv tests/services/test_openai_client.py tests/core/services/test_openai_client.py
git mv tests/services/test_search_service.py tests/core/services/test_search_service.py
git mv tests/api/test_chat.py tests/web/test_chat.py

# Clean up old test directories
rm -rf tests/agents tests/services tests/api
```

**Step 2: Update all imports in core files**

`backend/app/core/agents/planner.py` — update imports:
```python
# Change:
from app.models.schemas import PlannerDecision
from app.services.openai_client import OpenAIClient
# To:
from app.core.models.schemas import PlannerDecision
from app.core.services.openai_client import OpenAIClient
```

`backend/app/core/agents/executor.py` — update imports:
```python
# Change:
from app.models.schemas import Citation, SearchResult
from app.services.openai_client import OpenAIClient
# To:
from app.core.models.schemas import Citation, SearchResult
from app.core.services.openai_client import OpenAIClient
```

`backend/app/core/services/chat_service.py` — update imports:
```python
# Change:
from app.agents.planner import PlannerAgent
from app.agents.executor import ExecutorAgent
from app.services.search_service import SearchService
# To:
from app.core.agents.planner import PlannerAgent
from app.core.agents.executor import ExecutorAgent
from app.core.services.search_service import SearchService
```

`backend/app/core/services/search_service.py` — update imports:
```python
# Change:
from app.models.schemas import SearchResult
# To:
from app.core.models.schemas import SearchResult
```

**Step 3: Update web gateway imports**

`backend/app/web/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import ChatError, chat_error_handler
from app.web.routes import chat, health


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

`backend/app/web/routes/chat.py`:
```python
import json
import logging

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.models.schemas import ChatRequest
from app.core.services.chat_service import ChatService

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

**Step 4: Create new app-level entry point**

Create `backend/app/main.py` (new, replaces old one):
```python
# Re-export for backward compatibility with uvicorn app.main:app
from app.web.main import app  # noqa: F401
```

**Step 5: Update all test imports**

`backend/tests/conftest.py`:
```python
import pytest
from app.core.config import Settings


@pytest.fixture
def test_settings():
    return Settings(
        openai_api_key="test-key",
        tavily_api_key="test-tavily-key",
    )
```

`backend/tests/core/agents/test_planner.py` — update imports:
```python
# Change:
from app.agents.planner import PlannerAgent
from app.models.schemas import PlannerDecision
# To:
from app.core.agents.planner import PlannerAgent
from app.core.models.schemas import PlannerDecision
```

`backend/tests/core/agents/test_executor.py` — update imports:
```python
# Change:
from app.agents.executor import ExecutorAgent
from app.models.schemas import SearchResult, Citation
# To:
from app.core.agents.executor import ExecutorAgent
from app.core.models.schemas import SearchResult, Citation
```

`backend/tests/core/services/test_chat_service.py` — update imports:
```python
# Change:
from app.services.chat_service import ChatService
from app.models.schemas import PlannerDecision, SearchResult
# To:
from app.core.services.chat_service import ChatService
from app.core.models.schemas import PlannerDecision, SearchResult
```

`backend/tests/core/services/test_openai_client.py` — update imports:
```python
# Change:
from app.services.openai_client import OpenAIClient
# To:
from app.core.services.openai_client import OpenAIClient
```

`backend/tests/core/services/test_search_service.py` — update imports:
```python
# Change:
from app.services.search_service import SearchService
from app.models.schemas import SearchResult
# To:
from app.core.services.search_service import SearchService
from app.core.models.schemas import SearchResult
```

`backend/tests/web/test_chat.py` — update imports:
```python
# Change:
from app.main import app
# To:
from app.web.main import app
```

Also update the mock path in `test_chat.py`:
```python
# Change:
with patch("app.api.routes.chat.get_chat_service") as mock_get_service:
# To:
with patch("app.web.routes.chat.get_chat_service") as mock_get_service:
```

**Step 6: Run all tests**

Run: `cd backend && . .venv/bin/activate && python -m pytest -v`
Expected: All existing tests PASS (same count as before + the 7 event model tests)

**Step 7: Commit**

```bash
git add -A
git commit -m "refactor(backend): restructure into core + web gateway architecture"
```

---

### Task 4: Refactor ChatService to Yield ChatEvent Objects

**Files:**
- Modify: `backend/app/core/services/chat_service.py`
- Modify: `backend/app/web/routes/chat.py`
- Modify: `backend/tests/core/services/test_chat_service.py`
- Modify: `backend/tests/web/test_chat.py`

**Step 1: Write the failing test**

Update `backend/tests/core/services/test_chat_service.py` to expect `ChatEvent` objects:

```python
import pytest
from unittest.mock import AsyncMock, patch

from app.core.services.chat_service import ChatService
from app.core.models.schemas import PlannerDecision, SearchResult
from app.core.models.events import (
    PlannerEvent,
    SearchingEvent,
    ChunkEvent,
    CitationsEvent,
    DoneEvent,
)


@pytest.fixture
def chat_service():
    return ChatService(
        openai_api_key="test-key",
        openai_model="gpt-4o",
        tavily_api_key="test-tavily",
    )


@pytest.mark.asyncio
async def test_chat_stream_yields_chat_events_with_search(chat_service):
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
        async for event in chat_service.process_message("TSMC stock?"):
            events.append(event)

        assert isinstance(events[0], PlannerEvent)
        assert events[0].needs_search is True

        searching_events = [e for e in events if isinstance(e, SearchingEvent)]
        assert len(searching_events) >= 2  # at least one "searching" + one "done"

        chunk_events = [e for e in events if isinstance(e, ChunkEvent)]
        assert len(chunk_events) == 2
        assert chunk_events[0].content == "TSMC "

        assert isinstance(events[-1], DoneEvent)


@pytest.mark.asyncio
async def test_chat_stream_yields_chat_events_without_search(chat_service):
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
        async for event in chat_service.process_message("Hello!"):
            events.append(event)

        assert isinstance(events[0], PlannerEvent)
        assert events[0].needs_search is False

        searching_events = [e for e in events if isinstance(e, SearchingEvent)]
        assert len(searching_events) == 0

        chunk_events = [e for e in events if isinstance(e, ChunkEvent)]
        assert len(chunk_events) == 1
        assert chunk_events[0].content == "Hello!"

        assert isinstance(events[-1], DoneEvent)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/core/services/test_chat_service.py -v`
Expected: FAIL — `AttributeError: 'ChatService' object has no attribute 'process_message'`

**Step 3: Implement ChatService.process_message() and update web gateway**

Update `backend/app/core/services/chat_service.py`:

```python
import logging
from collections.abc import AsyncGenerator

from app.core.agents.planner import PlannerAgent
from app.core.agents.executor import ExecutorAgent
from app.core.services.search_service import SearchService
from app.core.models.events import (
    ChatEvent,
    PlannerEvent,
    SearchingEvent,
    ChunkEvent,
    CitationsEvent,
    DoneEvent,
)

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

    async def process_message(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[ChatEvent, None]:
        # Step 1: Planner decides
        decision = await self._planner.plan(message, history)
        yield PlannerEvent(
            needs_search=decision.needs_search,
            reasoning=decision.reasoning,
            search_queries=decision.search_queries,
            query_type=decision.query_type,
        )

        # Step 2: Search if needed
        search_results = []
        if decision.needs_search and decision.search_queries:
            for query in decision.search_queries:
                yield SearchingEvent(query=query, status="searching")

            search_results = await self._search.search_multiple(
                decision.search_queries
            )

            for query in decision.search_queries:
                yield SearchingEvent(
                    query=query,
                    status="done",
                    results_count=len(search_results),
                )

        # Step 3: Executor generates answer
        async for chunk in self._executor.execute(
            message=message,
            search_results=search_results,
            history=history,
        ):
            yield ChunkEvent(content=chunk)

        # Step 4: Send citations
        if search_results:
            citations = self._executor.build_citations(search_results)
            yield CitationsEvent(
                citations=[
                    {"index": c.index, "title": c.title, "url": c.url, "snippet": c.snippet}
                    for c in citations
                ]
            )

        yield DoneEvent()
```

Update `backend/app/web/routes/chat.py` to consume `ChatEvent`:

```python
import json
import logging
from dataclasses import asdict

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.models.schemas import ChatRequest
from app.core.services.chat_service import ChatService
from app.core.models.events import (
    PlannerEvent,
    SearchingEvent,
    ChunkEvent,
    CitationsEvent,
    DoneEvent,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_chat_service() -> ChatService:
    return ChatService(
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        tavily_api_key=settings.tavily_api_key,
    )


def _event_to_sse(event) -> dict:
    match event:
        case PlannerEvent():
            return {"event": "planner", "data": asdict(event)}
        case SearchingEvent():
            return {"event": "searching", "data": asdict(event)}
        case ChunkEvent():
            return {"event": "chunk", "data": {"content": event.content}}
        case CitationsEvent():
            return {"event": "citations", "data": {"citations": event.citations}}
        case DoneEvent():
            return {"event": "done", "data": {}}


@router.post("/api/chat")
async def chat(request: ChatRequest):
    service = get_chat_service()
    history = [msg.model_dump() for msg in request.history]

    async def event_generator():
        try:
            async for event in service.process_message(
                message=request.message,
                history=history,
            ):
                sse = _event_to_sse(event)
                yield {
                    "event": sse["event"],
                    "data": json.dumps(sse["data"], ensure_ascii=False),
                }
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)}),
            }

    return EventSourceResponse(event_generator())
```

Update `backend/tests/web/test_chat.py` to use `process_message`:

```python
import json
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.web.main import app
from app.core.models.events import PlannerEvent, ChunkEvent, DoneEvent


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
    async def mock_process_message(*args, **kwargs):
        yield PlannerEvent(
            needs_search=False,
            reasoning="test",
            search_queries=[],
            query_type="conversational",
        )
        yield ChunkEvent(content="Hello!")
        yield DoneEvent()

    with patch("app.web.routes.chat.get_chat_service") as mock_get_service:
        mock_service = AsyncMock()
        mock_service.process_message = mock_process_message
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/chat",
            json={"message": "Hi there"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        lines = response.text.strip().split("\n")
        events = []
        for line in lines:
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        assert len(events) >= 2
```

**Step 4: Run all tests**

Run: `cd backend && . .venv/bin/activate && python -m pytest -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor(core): ChatService yields ChatEvent objects, web gateway converts to SSE"
```

---

### Task 5: Add Telegram Config Settings

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/tests/conftest.py`

**Step 1: Write the failing test**

Create `backend/tests/core/test_config.py`:

```python
import pytest
from app.core.config import Settings


def test_telegram_settings_have_defaults():
    s = Settings(openai_api_key="k", tavily_api_key="k")
    assert s.telegram_bot_token == ""
    assert s.telegram_admin_ids == []
    assert s.mode == "web"


def test_telegram_admin_ids_parsed_from_comma_string():
    s = Settings(
        openai_api_key="k",
        tavily_api_key="k",
        telegram_admin_ids=[123, 456],
    )
    assert s.telegram_admin_ids == [123, 456]
```

**Step 2: Run test to verify it fails**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/core/test_config.py -v`
Expected: FAIL — `telegram_bot_token` not found

**Step 3: Update config**

Update `backend/app/core/config.py`:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    tavily_api_key: str = ""
    frontend_url: str = "http://localhost:3000"
    telegram_bot_token: str = ""
    telegram_admin_ids: list[int] = []
    mode: str = "web"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
```

**Step 4: Run test to verify it passes**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/core/test_config.py -v`
Expected: PASS

**Step 5: Run all tests to verify no regression**

Run: `cd backend && . .venv/bin/activate && python -m pytest -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add backend/app/core/config.py backend/tests/core/test_config.py
git commit -m "feat(core): add telegram bot config settings"
```

---

### Task 6: Telegram Rate Limiter

**Files:**
- Create: `backend/app/telegram/__init__.py`
- Create: `backend/app/telegram/rate_limiter.py`
- Create: `backend/tests/telegram/__init__.py`
- Create: `backend/tests/telegram/test_rate_limiter.py`

**Step 1: Write the failing test**

Create `backend/tests/telegram/__init__.py` (empty).

Create `backend/tests/telegram/test_rate_limiter.py`:

```python
import pytest
import time
from unittest.mock import patch

from app.telegram.rate_limiter import RateLimiter


@pytest.fixture
def limiter():
    return RateLimiter(max_requests=3, window_seconds=60)


def test_allows_requests_under_limit(limiter):
    assert limiter.is_allowed(chat_id=123) is True
    assert limiter.is_allowed(chat_id=123) is True
    assert limiter.is_allowed(chat_id=123) is True


def test_blocks_requests_over_limit(limiter):
    for _ in range(3):
        limiter.is_allowed(chat_id=123)
    assert limiter.is_allowed(chat_id=123) is False


def test_different_users_have_separate_limits(limiter):
    for _ in range(3):
        limiter.is_allowed(chat_id=123)
    assert limiter.is_allowed(chat_id=123) is False
    assert limiter.is_allowed(chat_id=456) is True


def test_allows_after_window_expires(limiter):
    with patch("app.telegram.rate_limiter.time") as mock_time:
        mock_time.monotonic.return_value = 0.0
        for _ in range(3):
            limiter.is_allowed(chat_id=123)
        assert limiter.is_allowed(chat_id=123) is False

        # Advance past window
        mock_time.monotonic.return_value = 61.0
        assert limiter.is_allowed(chat_id=123) is True


def test_remaining_returns_correct_count(limiter):
    assert limiter.remaining(chat_id=123) == 3
    limiter.is_allowed(chat_id=123)
    assert limiter.remaining(chat_id=123) == 2
```

**Step 2: Run test to verify it fails**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_rate_limiter.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement rate limiter**

Create `backend/app/telegram/__init__.py` (empty).

Create `backend/app/telegram/rate_limiter.py`:

```python
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[int, list[float]] = defaultdict(list)

    def _cleanup(self, chat_id: int) -> None:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        self._requests[chat_id] = [
            t for t in self._requests[chat_id] if t > cutoff
        ]

    def is_allowed(self, chat_id: int) -> bool:
        self._cleanup(chat_id)
        if len(self._requests[chat_id]) >= self._max_requests:
            return False
        self._requests[chat_id].append(time.monotonic())
        return True

    def remaining(self, chat_id: int) -> int:
        self._cleanup(chat_id)
        return max(0, self._max_requests - len(self._requests[chat_id]))
```

**Step 4: Run test to verify it passes**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_rate_limiter.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add backend/app/telegram/ backend/tests/telegram/
git commit -m "feat(telegram): add sliding window rate limiter"
```

---

### Task 7: Telegram Formatter

**Files:**
- Create: `backend/app/telegram/formatter.py`
- Create: `backend/tests/telegram/test_formatter.py`

**Step 1: Write the failing test**

Create `backend/tests/telegram/test_formatter.py`:

```python
import pytest
from app.telegram.formatter import TelegramFormatter
from app.core.models.events import (
    PlannerEvent,
    SearchingEvent,
    ChunkEvent,
    CitationsEvent,
    DoneEvent,
)


@pytest.fixture
def formatter():
    return TelegramFormatter()


def test_format_planner_thinking():
    text = TelegramFormatter.format_planner(
        PlannerEvent(
            needs_search=True,
            reasoning="Need latest stock info",
            search_queries=["TSMC stock"],
            query_type="temporal",
        )
    )
    assert "Need latest stock info" in text


def test_format_planner_no_search():
    text = TelegramFormatter.format_planner(
        PlannerEvent(
            needs_search=False,
            reasoning="General knowledge",
            search_queries=[],
            query_type="conversational",
        )
    )
    assert "General knowledge" in text


def test_format_searching():
    text = TelegramFormatter.format_searching(
        SearchingEvent(query="TSMC stock", status="searching")
    )
    assert "TSMC stock" in text


def test_format_searching_done():
    text = TelegramFormatter.format_searching(
        SearchingEvent(query="TSMC stock", status="done", results_count=5)
    )
    assert "5" in text


def test_format_citations():
    text = TelegramFormatter.format_citations(
        CitationsEvent(citations=[
            {"index": 1, "title": "TSMC Stock", "url": "https://example.com/tsmc", "snippet": "TSMC is at $180"},
            {"index": 2, "title": "TSMC News", "url": "https://example.com/news", "snippet": "Q4 earnings"},
        ])
    )
    assert "TSMC Stock" in text
    assert "https://example.com/tsmc" in text
    assert "TSMC News" in text


def test_format_final_message_with_citations():
    answer = "TSMC stock is at $180 [1]."
    citations = CitationsEvent(citations=[
        {"index": 1, "title": "TSMC Stock", "url": "https://example.com/tsmc", "snippet": "..."},
    ])
    text = TelegramFormatter.format_final_message(answer, citations)
    assert "TSMC stock is at $180" in text
    assert "https://example.com/tsmc" in text


def test_format_final_message_without_citations():
    answer = "Hello! How can I help?"
    text = TelegramFormatter.format_final_message(answer, None)
    assert text == answer


def test_escape_markdown():
    text = TelegramFormatter.escape_md("Hello *world* _test_ [link](url)")
    # Should escape special chars but preserve intentional markdown
    assert isinstance(text, str)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_formatter.py -v`
Expected: FAIL

**Step 3: Implement formatter**

Create `backend/app/telegram/formatter.py`:

```python
import re

from app.core.models.events import (
    PlannerEvent,
    SearchingEvent,
    CitationsEvent,
)

# Telegram MarkdownV2 special characters that need escaping
_ESCAPE_CHARS = r"_*[]()~`>#+-=|{}.!"


class TelegramFormatter:
    @staticmethod
    def escape_md(text: str) -> str:
        """Escape special characters for Telegram MarkdownV2."""
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
        answer: str, citations: CitationsEvent | None
    ) -> str:
        if citations and citations.citations:
            citation_text = TelegramFormatter.format_citations(citations)
            return f"{answer}\n{citation_text}"
        return answer
```

**Step 4: Run test to verify it passes**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_formatter.py -v`
Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add backend/app/telegram/formatter.py backend/tests/telegram/test_formatter.py
git commit -m "feat(telegram): add message formatter for core events"
```

---

### Task 8: SQLite Subscription Storage

**Files:**
- Create: `backend/app/telegram/storage.py`
- Create: `backend/tests/telegram/test_storage.py`

**Step 1: Write the failing test**

Create `backend/tests/telegram/test_storage.py`:

```python
import pytest
from app.telegram.storage import SubscriptionStorage


@pytest.fixture
async def storage(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = SubscriptionStorage(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_add_subscription(storage):
    await storage.add(chat_id=123, topic="科技新聞", frequency="daily", time="09:00")
    subs = await storage.list(chat_id=123)
    assert len(subs) == 1
    assert subs[0]["topic"] == "科技新聞"
    assert subs[0]["frequency"] == "daily"
    assert subs[0]["time"] == "09:00"


@pytest.mark.asyncio
async def test_add_duplicate_subscription_raises(storage):
    await storage.add(chat_id=123, topic="科技新聞", frequency="daily", time="09:00")
    with pytest.raises(ValueError, match="already subscribed"):
        await storage.add(chat_id=123, topic="科技新聞", frequency="daily", time="09:00")


@pytest.mark.asyncio
async def test_remove_subscription(storage):
    await storage.add(chat_id=123, topic="科技新聞", frequency="daily", time="09:00")
    removed = await storage.remove(chat_id=123, topic="科技新聞")
    assert removed is True
    subs = await storage.list(chat_id=123)
    assert len(subs) == 0


@pytest.mark.asyncio
async def test_remove_nonexistent_subscription(storage):
    removed = await storage.remove(chat_id=123, topic="不存在")
    assert removed is False


@pytest.mark.asyncio
async def test_list_empty_subscriptions(storage):
    subs = await storage.list(chat_id=999)
    assert subs == []


@pytest.mark.asyncio
async def test_list_all_subscriptions(storage):
    await storage.add(chat_id=123, topic="科技", frequency="daily", time="09:00")
    await storage.add(chat_id=456, topic="財經", frequency="weekly", time="10:00")
    all_subs = await storage.list_all()
    assert len(all_subs) == 2


@pytest.mark.asyncio
async def test_get_all_chat_ids(storage):
    await storage.add(chat_id=123, topic="科技", frequency="daily", time="09:00")
    await storage.add(chat_id=456, topic="財經", frequency="daily", time="10:00")
    await storage.add(chat_id=123, topic="財經", frequency="weekly", time="10:00")
    chat_ids = await storage.get_all_chat_ids()
    assert set(chat_ids) == {123, 456}


@pytest.mark.asyncio
async def test_get_subscriber_chat_ids(storage):
    await storage.add(chat_id=123, topic="科技", frequency="daily", time="09:00")
    await storage.add(chat_id=456, topic="財經", frequency="daily", time="10:00")
    chat_ids = await storage.get_subscriber_chat_ids()
    assert set(chat_ids) == {123, 456}
```

**Step 2: Run test to verify it fails**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_storage.py -v`
Expected: FAIL

**Step 3: Implement storage**

Create `backend/app/telegram/storage.py`:

```python
import aiosqlite


class SubscriptionStorage:
    def __init__(self, db_path: str = "subscriptions.db"):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id BIGINT NOT NULL,
                topic TEXT NOT NULL,
                frequency TEXT NOT NULL,
                time TEXT NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'Asia/Taipei',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, topic)
            )
        """)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def add(
        self,
        chat_id: int,
        topic: str,
        frequency: str,
        time: str,
        timezone: str = "Asia/Taipei",
    ) -> None:
        try:
            await self._db.execute(
                "INSERT INTO subscriptions (chat_id, topic, frequency, time, timezone) VALUES (?, ?, ?, ?, ?)",
                (chat_id, topic, frequency, time, timezone),
            )
            await self._db.commit()
        except aiosqlite.IntegrityError:
            raise ValueError(f"already subscribed to '{topic}'")

    async def remove(self, chat_id: int, topic: str) -> bool:
        cursor = await self._db.execute(
            "DELETE FROM subscriptions WHERE chat_id = ? AND topic = ?",
            (chat_id, topic),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def list(self, chat_id: int) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT topic, frequency, time, timezone FROM subscriptions WHERE chat_id = ?",
            (chat_id,),
        )
        rows = await cursor.fetchall()
        return [
            {"topic": r[0], "frequency": r[1], "time": r[2], "timezone": r[3]}
            for r in rows
        ]

    async def list_all(self) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT chat_id, topic, frequency, time, timezone FROM subscriptions"
        )
        rows = await cursor.fetchall()
        return [
            {"chat_id": r[0], "topic": r[1], "frequency": r[2], "time": r[3], "timezone": r[4]}
            for r in rows
        ]

    async def get_all_chat_ids(self) -> list[int]:
        cursor = await self._db.execute(
            "SELECT DISTINCT chat_id FROM subscriptions"
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

    async def get_subscriber_chat_ids(self) -> list[int]:
        return await self.get_all_chat_ids()
```

**Step 4: Run test to verify it passes**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_storage.py -v`
Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add backend/app/telegram/storage.py backend/tests/telegram/test_storage.py
git commit -m "feat(telegram): add SQLite subscription storage"
```

---

### Task 9: Telegram Bot Setup + /start, /help Commands

**Files:**
- Create: `backend/app/telegram/bot.py`
- Create: `backend/app/telegram/handlers/__init__.py`
- Create: `backend/app/telegram/handlers/chat.py`
- Create: `backend/app/telegram/handlers/subscribe.py`
- Create: `backend/app/telegram/handlers/admin.py`
- Create: `backend/tests/telegram/test_bot.py`

**Step 1: Write the failing test**

Create `backend/tests/telegram/test_bot.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.telegram.bot import create_bot, start_command, help_command


@pytest.mark.asyncio
async def test_start_command_sends_welcome():
    update = AsyncMock()
    update.effective_user.first_name = "Alice"
    context = MagicMock()

    await start_command(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "Alice" in call_text


@pytest.mark.asyncio
async def test_help_command_lists_commands():
    update = AsyncMock()
    context = MagicMock()

    await help_command(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "/start" in call_text
    assert "/help" in call_text
    assert "/subscribe" in call_text


def test_create_bot_returns_application():
    with patch("app.telegram.bot.ApplicationBuilder") as mock_builder:
        mock_app = MagicMock()
        mock_builder.return_value.token.return_value.build.return_value = mock_app
        app = create_bot(token="test-token")
        assert app is not None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_bot.py -v`
Expected: FAIL

**Step 3: Implement bot**

Create `backend/app/telegram/handlers/__init__.py` (empty).

Create `backend/app/telegram/bot.py`:

```python
import logging

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = """👋 Hi {name}! I'm Vulcan, your AI search assistant.

Send me any question and I'll search the web to find the answer!

Type /help to see all available commands."""

HELP_MESSAGE = """📖 Available commands:

/start - Welcome message
/help - Show this help
/subscribe <topic> <daily|weekly> <HH:MM> - Subscribe to digests
/unsubscribe <topic> - Unsubscribe from a topic
/list - List your subscriptions

Or just send me a message to chat!"""


async def start_command(update: Update, context) -> None:
    name = update.effective_user.first_name
    await update.message.reply_text(WELCOME_MESSAGE.format(name=name))


async def help_command(update: Update, context) -> None:
    await update.message.reply_text(HELP_MESSAGE)


def create_bot(
    token: str,
    chat_handler=None,
    subscribe_handler=None,
    unsubscribe_handler=None,
    list_handler=None,
    stats_handler=None,
) -> Application:
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    if subscribe_handler:
        app.add_handler(CommandHandler("subscribe", subscribe_handler))
    if unsubscribe_handler:
        app.add_handler(CommandHandler("unsubscribe", unsubscribe_handler))
    if list_handler:
        app.add_handler(CommandHandler("list", list_handler))
    if stats_handler:
        app.add_handler(CommandHandler("stats", stats_handler))
    if chat_handler:
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))

    return app
```

**Step 4: Run test to verify it passes**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_bot.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add backend/app/telegram/bot.py backend/app/telegram/handlers/ backend/tests/telegram/test_bot.py
git commit -m "feat(telegram): add bot setup with /start and /help commands"
```

---

### Task 10: Telegram Chat Handler

**Files:**
- Create: `backend/app/telegram/handlers/chat.py`
- Create: `backend/tests/telegram/test_chat_handler.py`

**Step 1: Write the failing test**

Create `backend/tests/telegram/test_chat_handler.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.telegram.handlers.chat import ChatHandler
from app.core.models.events import (
    PlannerEvent,
    ChunkEvent,
    CitationsEvent,
    DoneEvent,
)


@pytest.fixture
def mock_chat_service():
    return AsyncMock()


@pytest.fixture
def mock_rate_limiter():
    limiter = MagicMock()
    limiter.is_allowed.return_value = True
    limiter.remaining.return_value = 19
    return limiter


@pytest.fixture
def handler(mock_chat_service, mock_rate_limiter):
    return ChatHandler(
        chat_service=mock_chat_service,
        rate_limiter=mock_rate_limiter,
    )


def _make_update(text="Hello", chat_id=123):
    update = AsyncMock()
    update.message.text = text
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_chat_handler_sends_response(handler, mock_chat_service):
    async def mock_process(message, history=None):
        yield PlannerEvent(needs_search=False, reasoning="test", search_queries=[], query_type="conversational")
        yield ChunkEvent(content="Hello!")
        yield DoneEvent()

    mock_chat_service.process_message = mock_process

    update = _make_update("Hi")
    context = MagicMock()

    await handler.handle(update, context)

    # Should have sent a status message and then edited it
    update.message.reply_text.assert_called()


@pytest.mark.asyncio
async def test_chat_handler_rate_limited(handler, mock_rate_limiter):
    mock_rate_limiter.is_allowed.return_value = False

    update = _make_update("Hi")
    context = MagicMock()

    await handler.handle(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "rate" in call_text.lower() or "limit" in call_text.lower() or "太快" in call_text or "稍後" in call_text


@pytest.mark.asyncio
async def test_chat_handler_with_citations(handler, mock_chat_service):
    async def mock_process(message, history=None):
        yield PlannerEvent(needs_search=True, reasoning="searching", search_queries=["q"], query_type="temporal")
        yield ChunkEvent(content="Answer [1]")
        yield CitationsEvent(citations=[{"index": 1, "title": "T", "url": "https://ex.com", "snippet": "s"}])
        yield DoneEvent()

    mock_chat_service.process_message = mock_process

    update = _make_update("Stock?")
    context = MagicMock()

    await handler.handle(update, context)

    # Verify the status message was edited with final content
    status_msg = update.message.reply_text.return_value
    status_msg.edit_text.assert_called()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_chat_handler.py -v`
Expected: FAIL

**Step 3: Implement chat handler**

Create `backend/app/telegram/handlers/chat.py`:

```python
import logging
import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from app.core.services.chat_service import ChatService
from app.core.models.events import (
    PlannerEvent,
    SearchingEvent,
    ChunkEvent,
    CitationsEvent,
    DoneEvent,
)
from app.telegram.formatter import TelegramFormatter
from app.telegram.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Minimum interval between message edits (seconds)
_EDIT_INTERVAL = 2.0
# Minimum characters accumulated before editing
_EDIT_CHAR_THRESHOLD = 30


class ChatHandler:
    def __init__(self, chat_service: ChatService, rate_limiter: RateLimiter):
        self._chat_service = chat_service
        self._rate_limiter = rate_limiter

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        message_text = update.message.text

        if not self._rate_limiter.is_allowed(chat_id):
            await update.message.reply_text(
                "⏳ 訊息太快了，請稍後再試。"
            )
            return

        status_msg = await update.message.reply_text("🤔 思考中...")

        full_text = ""
        citations_event = None
        last_edit_time = 0.0
        last_edit_len = 0

        try:
            async for event in self._chat_service.process_message(
                message=message_text,
            ):
                match event:
                    case PlannerEvent():
                        status_text = TelegramFormatter.format_planner(event)
                        await status_msg.edit_text(status_text)

                    case SearchingEvent():
                        status_text = TelegramFormatter.format_searching(event)
                        await status_msg.edit_text(status_text)

                    case ChunkEvent():
                        full_text += event.content
                        now = asyncio.get_event_loop().time()
                        chars_since_edit = len(full_text) - last_edit_len
                        time_since_edit = now - last_edit_time

                        if chars_since_edit >= _EDIT_CHAR_THRESHOLD or time_since_edit >= _EDIT_INTERVAL:
                            try:
                                await status_msg.edit_text(full_text)
                                last_edit_time = now
                                last_edit_len = len(full_text)
                            except Exception:
                                pass  # Telegram may reject edits with same content

                    case CitationsEvent():
                        citations_event = event

                    case DoneEvent():
                        pass

            # Final message with citations
            final_text = TelegramFormatter.format_final_message(
                full_text, citations_event
            )
            try:
                await status_msg.edit_text(final_text)
            except Exception:
                # If edit fails (e.g., same content), that's ok
                pass

        except Exception as e:
            logger.error(f"Chat handler error: {e}")
            await status_msg.edit_text(f"❌ 發生錯誤: {str(e)}")
```

**Step 4: Run test to verify it passes**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_chat_handler.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add backend/app/telegram/handlers/chat.py backend/tests/telegram/test_chat_handler.py
git commit -m "feat(telegram): add chat handler with streaming and rate limiting"
```

---

### Task 11: Subscribe/Unsubscribe Handlers

**Files:**
- Create: `backend/app/telegram/handlers/subscribe.py`
- Create: `backend/tests/telegram/test_subscribe_handler.py`

**Step 1: Write the failing test**

Create `backend/tests/telegram/test_subscribe_handler.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.telegram.handlers.subscribe import SubscribeHandler


@pytest.fixture
def mock_storage():
    storage = AsyncMock()
    storage.list.return_value = []
    return storage


@pytest.fixture
def handler(mock_storage):
    return SubscribeHandler(storage=mock_storage)


def _make_update(text, chat_id=123):
    update = AsyncMock()
    update.message.text = text
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_subscribe_success(handler, mock_storage):
    update = _make_update("/subscribe 科技新聞 daily 09:00")
    context = MagicMock()
    context.args = ["科技新聞", "daily", "09:00"]

    await handler.subscribe(update, context)

    mock_storage.add.assert_called_once_with(
        chat_id=123, topic="科技新聞", frequency="daily", time="09:00"
    )
    call_text = update.message.reply_text.call_args[0][0]
    assert "科技新聞" in call_text


@pytest.mark.asyncio
async def test_subscribe_missing_args(handler):
    update = _make_update("/subscribe")
    context = MagicMock()
    context.args = []

    await handler.subscribe(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "usage" in call_text.lower() or "格式" in call_text or "/subscribe" in call_text


@pytest.mark.asyncio
async def test_subscribe_invalid_frequency(handler):
    update = _make_update("/subscribe 科技 monthly 09:00")
    context = MagicMock()
    context.args = ["科技", "monthly", "09:00"]

    await handler.subscribe(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "daily" in call_text or "weekly" in call_text


@pytest.mark.asyncio
async def test_unsubscribe_success(handler, mock_storage):
    mock_storage.remove.return_value = True
    update = _make_update("/unsubscribe 科技新聞")
    context = MagicMock()
    context.args = ["科技新聞"]

    await handler.unsubscribe(update, context)

    mock_storage.remove.assert_called_once_with(chat_id=123, topic="科技新聞")


@pytest.mark.asyncio
async def test_unsubscribe_not_found(handler, mock_storage):
    mock_storage.remove.return_value = False
    update = _make_update("/unsubscribe 不存在")
    context = MagicMock()
    context.args = ["不存在"]

    await handler.unsubscribe(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "找不到" in call_text or "not found" in call_text.lower()


@pytest.mark.asyncio
async def test_list_empty(handler, mock_storage):
    mock_storage.list.return_value = []
    update = _make_update("/list")
    context = MagicMock()

    await handler.list_subscriptions(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "沒有" in call_text or "no " in call_text.lower() or "empty" in call_text.lower()


@pytest.mark.asyncio
async def test_list_with_subscriptions(handler, mock_storage):
    mock_storage.list.return_value = [
        {"topic": "科技新聞", "frequency": "daily", "time": "09:00", "timezone": "Asia/Taipei"},
    ]
    update = _make_update("/list")
    context = MagicMock()

    await handler.list_subscriptions(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "科技新聞" in call_text
    assert "daily" in call_text
```

**Step 2: Run test to verify it fails**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_subscribe_handler.py -v`
Expected: FAIL

**Step 3: Implement subscribe handler**

Create `backend/app/telegram/handlers/subscribe.py`:

```python
import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

from app.telegram.storage import SubscriptionStorage

logger = logging.getLogger(__name__)

VALID_FREQUENCIES = {"daily", "weekly"}
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


class SubscribeHandler:
    def __init__(self, storage: SubscriptionStorage):
        self._storage = storage

    async def subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        args = context.args

        if len(args) < 3:
            await update.message.reply_text(
                "📝 格式: /subscribe <主題> <daily|weekly> <HH:MM>\n"
                "例如: /subscribe 科技新聞 daily 09:00"
            )
            return

        topic = args[0]
        frequency = args[1].lower()
        time_str = args[2]

        if frequency not in VALID_FREQUENCIES:
            await update.message.reply_text(
                f"❌ 頻率必須是 daily 或 weekly，收到: {frequency}"
            )
            return

        if not TIME_PATTERN.match(time_str):
            await update.message.reply_text(
                f"❌ 時間格式錯誤，請使用 HH:MM 格式，例如 09:00"
            )
            return

        try:
            await self._storage.add(
                chat_id=chat_id,
                topic=topic,
                frequency=frequency,
                time=time_str,
            )
            await update.message.reply_text(
                f"✅ 已訂閱「{topic}」\n"
                f"📅 {frequency}，每天 {time_str} 推送"
            )
        except ValueError as e:
            await update.message.reply_text(f"❌ {e}")

    async def unsubscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        args = context.args

        if not args:
            await update.message.reply_text(
                "📝 格式: /unsubscribe <主題>"
            )
            return

        topic = args[0]
        removed = await self._storage.remove(chat_id=chat_id, topic=topic)

        if removed:
            await update.message.reply_text(f"✅ 已取消訂閱「{topic}」")
        else:
            await update.message.reply_text(f"❌ 找不到訂閱「{topic}」")

    async def list_subscriptions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        subs = await self._storage.list(chat_id=chat_id)

        if not subs:
            await update.message.reply_text("📭 目前沒有任何訂閱。")
            return

        lines = ["📋 你的訂閱:"]
        for s in subs:
            lines.append(f"  • {s['topic']} — {s['frequency']} {s['time']} ({s['timezone']})")
        await update.message.reply_text("\n".join(lines))
```

**Step 4: Run test to verify it passes**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_subscribe_handler.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add backend/app/telegram/handlers/subscribe.py backend/tests/telegram/test_subscribe_handler.py
git commit -m "feat(telegram): add subscribe/unsubscribe/list command handlers"
```

---

### Task 12: Scheduler for Digest Delivery

**Files:**
- Create: `backend/app/telegram/scheduler.py`
- Create: `backend/tests/telegram/test_scheduler.py`

**Step 1: Write the failing test**

Create `backend/tests/telegram/test_scheduler.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.telegram.scheduler import DigestScheduler


@pytest.fixture
def mock_chat_service():
    return AsyncMock()


@pytest.fixture
def mock_storage():
    return AsyncMock()


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    return bot


@pytest.fixture
def scheduler(mock_chat_service, mock_storage, mock_bot):
    return DigestScheduler(
        chat_service=mock_chat_service,
        storage=mock_storage,
        bot=mock_bot,
    )


@pytest.mark.asyncio
async def test_execute_digest_sends_message(scheduler, mock_chat_service, mock_bot):
    from app.core.models.events import ChunkEvent, DoneEvent, PlannerEvent

    async def mock_process(message, history=None):
        yield PlannerEvent(needs_search=True, reasoning="r", search_queries=["q"], query_type="temporal")
        yield ChunkEvent(content="Today's news summary")
        yield DoneEvent()

    mock_chat_service.process_message = mock_process

    await scheduler.execute_digest(chat_id=123, topic="科技新聞")

    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args[1]
    assert call_kwargs["chat_id"] == 123
    assert "news summary" in call_kwargs["text"]


@pytest.mark.asyncio
async def test_execute_digest_handles_error(scheduler, mock_chat_service, mock_bot):
    mock_chat_service.process_message = MagicMock(side_effect=Exception("API Error"))

    await scheduler.execute_digest(chat_id=123, topic="科技新聞")

    # Should still try to notify user about error
    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args[1]
    assert "錯誤" in call_kwargs["text"] or "error" in call_kwargs["text"].lower()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_scheduler.py -v`
Expected: FAIL

**Step 3: Implement scheduler**

Create `backend/app/telegram/scheduler.py`:

```python
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.services.chat_service import ChatService
from app.core.models.events import ChunkEvent
from app.telegram.storage import SubscriptionStorage

logger = logging.getLogger(__name__)


class DigestScheduler:
    def __init__(self, chat_service: ChatService, storage: SubscriptionStorage, bot):
        self._chat_service = chat_service
        self._storage = storage
        self._bot = bot
        self._scheduler = AsyncIOScheduler()

    async def start(self) -> None:
        subs = await self._storage.list_all()
        for sub in subs:
            self._add_job(sub)
        self._scheduler.start()
        logger.info(f"Scheduler started with {len(subs)} jobs")

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)

    async def reload(self) -> None:
        self._scheduler.remove_all_jobs()
        subs = await self._storage.list_all()
        for sub in subs:
            self._add_job(sub)
        logger.info(f"Scheduler reloaded with {len(subs)} jobs")

    def _add_job(self, sub: dict) -> None:
        hour, minute = sub["time"].split(":")
        if sub["frequency"] == "daily":
            trigger = CronTrigger(hour=int(hour), minute=int(minute), timezone=sub["timezone"])
        else:  # weekly
            trigger = CronTrigger(
                day_of_week="mon", hour=int(hour), minute=int(minute), timezone=sub["timezone"]
            )

        job_id = f"{sub['chat_id']}_{sub['topic']}"
        self._scheduler.add_job(
            self.execute_digest,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            kwargs={"chat_id": sub["chat_id"], "topic": sub["topic"]},
        )

    async def execute_digest(self, chat_id: int, topic: str) -> None:
        try:
            prompt = f"請搜尋並摘要今天關於「{topic}」的重點新聞，用繁體中文回答"
            full_text = ""
            async for event in self._chat_service.process_message(message=prompt):
                if isinstance(event, ChunkEvent):
                    full_text += event.content

            await self._bot.send_message(
                chat_id=chat_id,
                text=f"📰 {topic} 摘要\n\n{full_text}",
            )
        except Exception as e:
            logger.error(f"Digest delivery failed for {chat_id}/{topic}: {e}")
            await self._bot.send_message(
                chat_id=chat_id,
                text=f"❌ 「{topic}」摘要產生時發生錯誤: {str(e)}",
            )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_scheduler.py -v`
Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add backend/app/telegram/scheduler.py backend/tests/telegram/test_scheduler.py
git commit -m "feat(telegram): add APScheduler-based digest delivery"
```

---

### Task 13: Admin /stats Handler

**Files:**
- Create: `backend/app/telegram/handlers/admin.py`
- Create: `backend/tests/telegram/test_admin_handler.py`

**Step 1: Write the failing test**

Create `backend/tests/telegram/test_admin_handler.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.telegram.handlers.admin import AdminHandler


@pytest.fixture
def mock_storage():
    return AsyncMock()


@pytest.fixture
def handler(mock_storage):
    return AdminHandler(storage=mock_storage, admin_ids=[111, 222])


def _make_update(chat_id):
    update = AsyncMock()
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_stats_shows_info_for_admin(handler, mock_storage):
    mock_storage.list_all.return_value = [
        {"chat_id": 1, "topic": "A", "frequency": "daily", "time": "09:00", "timezone": "Asia/Taipei"},
        {"chat_id": 2, "topic": "B", "frequency": "weekly", "time": "10:00", "timezone": "Asia/Taipei"},
    ]

    update = _make_update(chat_id=111)  # admin
    context = MagicMock()

    await handler.stats(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "2" in call_text  # 2 subscriptions


@pytest.mark.asyncio
async def test_stats_denied_for_non_admin(handler):
    update = _make_update(chat_id=999)  # not admin
    context = MagicMock()

    await handler.stats(update, context)

    call_text = update.message.reply_text.call_args[0][0]
    assert "權限" in call_text or "denied" in call_text.lower() or "unauthorized" in call_text.lower()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_admin_handler.py -v`
Expected: FAIL

**Step 3: Implement admin handler**

Create `backend/app/telegram/handlers/admin.py`:

```python
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.telegram.storage import SubscriptionStorage

logger = logging.getLogger(__name__)


class AdminHandler:
    def __init__(self, storage: SubscriptionStorage, admin_ids: list[int]):
        self._storage = storage
        self._admin_ids = admin_ids

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id

        if chat_id not in self._admin_ids:
            await update.message.reply_text("🚫 你沒有權限使用此指令。")
            return

        subs = await self._storage.list_all()
        unique_users = len(set(s["chat_id"] for s in subs))

        await update.message.reply_text(
            f"📊 Bot 統計\n\n"
            f"📝 總訂閱數: {len(subs)}\n"
            f"👥 訂閱用戶數: {unique_users}"
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/telegram/test_admin_handler.py -v`
Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add backend/app/telegram/handlers/admin.py backend/tests/telegram/test_admin_handler.py
git commit -m "feat(telegram): add admin /stats command handler"
```

---

### Task 14: Notification API (Web Gateway)

**Files:**
- Create: `backend/app/web/routes/notify.py`
- Modify: `backend/app/web/main.py`
- Create: `backend/tests/web/test_notify.py`

**Step 1: Write the failing test**

Create `backend/tests/web/test_notify.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.web.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_notify_sends_message(client):
    with patch("app.web.routes.notify.get_bot") as mock_get_bot:
        mock_bot = AsyncMock()
        mock_get_bot.return_value = mock_bot

        response = client.post("/api/notify", json={
            "chat_id": 123,
            "message": "Test notification",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"


def test_notify_rejects_empty_message(client):
    response = client.post("/api/notify", json={
        "chat_id": 123,
        "message": "",
    })
    assert response.status_code == 422


def test_broadcast_sends_to_subscribers(client):
    with (
        patch("app.web.routes.notify.get_bot") as mock_get_bot,
        patch("app.web.routes.notify.get_storage") as mock_get_storage,
    ):
        mock_bot = AsyncMock()
        mock_get_bot.return_value = mock_bot

        mock_storage = AsyncMock()
        mock_storage.get_subscriber_chat_ids.return_value = [123, 456]
        mock_get_storage.return_value = mock_storage

        response = client.post("/api/notify/broadcast", json={
            "message": "Broadcast test",
            "target": "subscribers",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["sent_count"] == 2
```

**Step 2: Run test to verify it fails**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/web/test_notify.py -v`
Expected: FAIL

**Step 3: Implement notify routes**

Create `backend/app/web/routes/notify.py`:

```python
import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field
from telegram import Bot

from app.core.config import settings
from app.telegram.storage import SubscriptionStorage

logger = logging.getLogger(__name__)

router = APIRouter()


class NotifyRequest(BaseModel):
    chat_id: int
    message: str = Field(..., min_length=1)
    parse_mode: str | None = None


class BroadcastRequest(BaseModel):
    message: str = Field(..., min_length=1)
    target: str = Field(..., pattern="^(all|subscribers)$")


def get_bot() -> Bot:
    return Bot(token=settings.telegram_bot_token)


def get_storage() -> SubscriptionStorage:
    return SubscriptionStorage()


@router.post("/api/notify")
async def notify(request: NotifyRequest):
    bot = get_bot()
    await bot.send_message(
        chat_id=request.chat_id,
        text=request.message,
        parse_mode=request.parse_mode,
    )
    return {"status": "sent"}


@router.post("/api/notify/broadcast")
async def broadcast(request: BroadcastRequest):
    bot = get_bot()
    storage = get_storage()

    chat_ids = await storage.get_subscriber_chat_ids()

    sent_count = 0
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id=chat_id, text=request.message)
            sent_count += 1
        except Exception as e:
            logger.error(f"Broadcast failed for {chat_id}: {e}")

    return {"sent_count": sent_count}
```

Update `backend/app/web/main.py` to include notify router:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import ChatError, chat_error_handler
from app.web.routes import chat, health, notify


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
    app.include_router(notify.router)

    return app


app = create_app()
```

**Step 4: Run all tests**

Run: `cd backend && . .venv/bin/activate && python -m pytest -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/web/routes/notify.py backend/app/web/main.py backend/tests/web/test_notify.py
git commit -m "feat(web): add /api/notify and /api/notify/broadcast endpoints"
```

---

### Task 15: Unified Entrypoint

**Files:**
- Create: `backend/app/entrypoint.py`
- Modify: `backend/Dockerfile`
- Modify: `Makefile`

**Step 1: Write the failing test**

Create `backend/tests/test_entrypoint.py`:

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def test_entrypoint_mode_web():
    with patch.dict("os.environ", {"MODE": "web"}):
        from app.entrypoint import get_mode
        assert get_mode() == "web"


def test_entrypoint_mode_telegram():
    with patch.dict("os.environ", {"MODE": "telegram"}):
        from app.entrypoint import get_mode
        assert get_mode() == "telegram"


def test_entrypoint_mode_all():
    with patch.dict("os.environ", {"MODE": "all"}):
        from app.entrypoint import get_mode
        assert get_mode() == "all"


def test_entrypoint_default_mode():
    with patch.dict("os.environ", {}, clear=True):
        from app.entrypoint import get_mode
        assert get_mode() == "web"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_entrypoint.py -v`
Expected: FAIL

**Step 3: Implement entrypoint**

Create `backend/app/entrypoint.py`:

```python
import asyncio
import logging
import os

import uvicorn

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_mode() -> str:
    return os.environ.get("MODE", settings.mode)


async def start_telegram():
    from app.core.services.chat_service import ChatService
    from app.telegram.bot import create_bot
    from app.telegram.handlers.chat import ChatHandler
    from app.telegram.handlers.subscribe import SubscribeHandler
    from app.telegram.handlers.admin import AdminHandler
    from app.telegram.rate_limiter import RateLimiter
    from app.telegram.storage import SubscriptionStorage
    from app.telegram.scheduler import DigestScheduler

    chat_service = ChatService(
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        tavily_api_key=settings.tavily_api_key,
    )

    storage = SubscriptionStorage()
    await storage.initialize()

    rate_limiter = RateLimiter(max_requests=20, window_seconds=60)
    chat_handler = ChatHandler(chat_service=chat_service, rate_limiter=rate_limiter)
    subscribe_handler = SubscribeHandler(storage=storage)
    admin_handler = AdminHandler(storage=storage, admin_ids=settings.telegram_admin_ids)

    app = create_bot(
        token=settings.telegram_bot_token,
        chat_handler=chat_handler.handle,
        subscribe_handler=subscribe_handler.subscribe,
        unsubscribe_handler=subscribe_handler.unsubscribe,
        list_handler=subscribe_handler.list_subscriptions,
        stats_handler=admin_handler.stats,
    )

    scheduler = DigestScheduler(
        chat_service=chat_service,
        storage=storage,
        bot=app.bot,
    )
    await scheduler.start()

    logger.info("Starting Telegram bot...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Keep running until interrupted
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.stop()
        await storage.close()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


def start_web():
    uvicorn.run(
        "app.web.main:app",
        host="0.0.0.0",
        port=8000,
    )


async def start_all():
    loop = asyncio.get_event_loop()
    # Run web server in a thread, telegram bot in the event loop
    web_task = loop.run_in_executor(None, start_web)
    telegram_task = asyncio.create_task(start_telegram())
    await asyncio.gather(web_task, telegram_task)


def main():
    logging.basicConfig(level=logging.INFO)
    mode = get_mode()
    logger.info(f"Starting in {mode} mode")

    if mode == "web":
        start_web()
    elif mode == "telegram":
        asyncio.run(start_telegram())
    elif mode == "all":
        asyncio.run(start_all())
    else:
        raise ValueError(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_entrypoint.py -v`
Expected: All 4 tests PASS

**Step 5: Update Dockerfile**

Update `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY app/ app/
EXPOSE 8000
ENV MODE=web
CMD ["python", "-m", "app.entrypoint"]
```

**Step 6: Update Makefile**

Add these targets to the root `Makefile`:

```makefile
run-telegram:
	cd backend && . .venv/bin/activate && MODE=telegram python -m app.entrypoint

run-all:
	cd backend && . .venv/bin/activate && MODE=all python -m app.entrypoint

test-telegram:
	cd backend && . .venv/bin/activate && python -m pytest tests/telegram/ -v
```

**Step 7: Run all tests**

Run: `cd backend && . .venv/bin/activate && python -m pytest -v`
Expected: All tests PASS

**Step 8: Commit**

```bash
git add backend/app/entrypoint.py backend/Dockerfile Makefile backend/tests/test_entrypoint.py
git commit -m "feat: add unified entrypoint with web/telegram/all modes"
```

---

### Task 16: Final Integration Verification

**Step 1: Run full test suite**

Run: `cd backend && . .venv/bin/activate && python -m pytest -v --tb=short`
Expected: All tests PASS, zero failures

**Step 2: Verify web mode still works**

Run: `cd backend && . .venv/bin/activate && MODE=web python -c "from app.web.main import app; print('Web app OK')"`
Expected: Prints "Web app OK"

**Step 3: Verify telegram imports work**

Run: `cd backend && . .venv/bin/activate && python -c "from app.telegram.bot import create_bot; print('Telegram bot OK')"`
Expected: Prints "Telegram bot OK"

**Step 4: Commit any remaining changes**

```bash
git add -A
git commit -m "chore: final integration verification"
```
