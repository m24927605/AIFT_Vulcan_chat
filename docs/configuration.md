# Configuration

## Backend Environment Variables (.env)

| Variable | Description | Required |
|----------|-----------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `OPENAI_MODEL` | Model name (default: gpt-4o) | No |
| `ANTHROPIC_API_KEY` | Anthropic API key (for fallback) | No |
| `ANTHROPIC_MODEL` | Anthropic model (default: claude-sonnet-4-20250514) | No |
| `PRIMARY_LLM` | Primary LLM provider: `openai` or `anthropic` (default: openai) | No |
| `FALLBACK_LLM` | Fallback LLM provider: `openai`, `anthropic`, or `""` to disable (default: anthropic) | No |
| `TAVILY_API_KEY` | Tavily search API key | Yes |
| `FUGLE_API_KEY` | Fugle MarketData API key (for TW stock data) | No |
| `FINNHUB_API_KEY` | Finnhub API key (for US/global stock data) | No |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | For Telegram |
| `TELEGRAM_ADMIN_IDS` | Admin chat IDs (JSON array) | For Telegram |
| `MODE` | Run mode: `web`, `telegram`, or `all` | No |
| `DATA_DIR` | Directory for SQLite databases | No |
| `FRONTEND_URL` | Frontend URL for CORS | No |
| `API_SECRET_KEY` | Protects `/api/notify` endpoints, Telegram link-code hashing, and production web auth boot validation | For production |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key for LLM tracing | No |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key for LLM tracing | No |
| `LANGFUSE_HOST` | Langfuse host URL | No |
| `CELERY_BROKER_URL` | Redis URL for Celery broker (default: `redis://localhost:6379/0`) | For deep analysis |
| `CELERY_RESULT_BACKEND` | Redis URL for Celery results (default: `redis://localhost:6379/1`) | For deep analysis |

## Frontend Environment Variables (.env.local)

| Variable | Description | Required |
|----------|-----------|---------|
| `BACKEND_URL` | Backend API URL (server-side only, used by Next.js rewrites) | No (defaults to `http://localhost:8000`) |
