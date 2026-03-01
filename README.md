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
- **Executor Agent**: Synthesizes answers from search results (when available) or model knowledge. Generates responses with citation markers `[1]`, `[2]` and streams them via SSE.

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
