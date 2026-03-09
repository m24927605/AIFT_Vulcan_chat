# Operational Runbook

## Health Check

```bash
curl https://your-backend-url/api/health
# Expected:
# {
#   "status": "ok",
#   "checks": { "database": "ok" },
#   "uptime_seconds": 3600
# }
```

- `status: "ok"` — all dependencies healthy
- `status: "degraded"` — one or more checks failed (e.g., database unreachable)

## Observability

### Structured Logging

All backend logs include a request ID for tracing:

```
2026-03-02 11:30:00 INFO  [a1b2c3d4e5f6] app.core.middleware – POST /api/chat
2026-03-02 11:30:00 INFO  [a1b2c3d4e5f6] app.core.services.openai_client – OpenAI stream request (model=gpt-4o)
2026-03-02 11:30:02 INFO  [a1b2c3d4e5f6] app.core.middleware – POST /api/chat → 200 (2150ms)
```

- Request ID is auto-generated (`X-Request-ID` header) or forwarded from client
- Response includes `X-Request-ID` header for client-side correlation

### Key Log Patterns

| Pattern | Meaning |
|---------|---------|
| `Rule-based override: forcing search` | Deterministic pre-check overrode Planner's no-search decision |
| `Telegram push OK (chat=X, attempt=Y)` | Message delivered to Telegram (Y=1 means first attempt) |
| `Telegram push attempt X/3 failed` | Transient failure, retrying with backoff |
| `Telegram push failed after 3 attempts` | All retries exhausted — message dropped |
| `Rate limit exceeded for X` | IP hit the 30 req/min limit on `/api/chat` or `/api/analysis` |
| `Search failed for query` | Tavily API error (check quota or network) |

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `CORS: blocked by policy` | `FRONTEND_URL` env var doesn't match actual frontend origin | Set `FRONTEND_URL=https://your-frontend-domain` on backend |
| `HTTP 500` on `/api/chat` | Missing `OPENAI_API_KEY` or `TAVILY_API_KEY` | Verify `.env` has valid keys; check backend logs |
| `HTTP 429` on `/api/chat` or `/api/analysis` | Rate limit exceeded (30 req/min per IP per endpoint) | Wait and retry; adjust `RateLimitMiddleware` params if needed |
| `Search failed for query '...'` | Tavily API error (rate limit, network) | Tavily free tier: 1000 req/month; check quota at tavily.com dashboard |
| Telegram bot not responding | `TELEGRAM_BOT_TOKEN` invalid or bot not started | Verify token with BotFather; ensure `MODE=all` or `MODE=telegram` |
| Telegram messages not syncing | Conversation not fully linked (OTP pending/expired) | In web UI request link code, open bot, tap `Start Linking`, enter 8-digit code via keypad within 10 minutes (or use `/link <code>`) |
| `403 Forbidden` on conversation endpoints | Session cookie mismatch / rotated / expired | Reopen web app to mint a new session, then access only conversations created by that session |
| `sqlite3.OperationalError: database is locked` | Concurrent write from multiple workers | Use single-worker deployment (`--workers 1`) or migrate to PostgreSQL |

## Rate Limits & Timeouts

| Service | Limit | Timeout | Behavior on Exceed |
|---------|-------|---------|--------------------|
| OpenAI API | Depends on plan tier | 60s | SSE `error` event → frontend shows error |
| Tavily Search | 1000 req/month (free) | 10s per query | Returns empty results → Executor answers from knowledge |
| `/api/chat` endpoint | 30 req/min per IP | — | HTTP 429 with `Retry-After` header |
| `/api/analysis` endpoint | 30 req/min per IP | — | HTTP 429 with `Retry-After` header |
| Backend → Telegram push | Telegram rate limit: 30 msg/sec | 5s | 3 attempts with exponential backoff (1s, 2s between attempts); logged on failure |
| SSE connection | No server-side limit | Browser default (~5 min) | Frontend reconnects on next user message |

## Logs

- **Backend**: stdout/stderr via uvicorn; structured with request ID correlation
- **Railway**: `railway logs` CLI or dashboard → Deployments → Logs
- **Vercel**: `vercel logs` CLI or dashboard → Deployments → Functions tab

## Deployment Quick Reference

```bash
# Frontend (Vercel)
cd frontend && vercel --yes --prod

# Backend (Railway)
railway up --detach --service vulcan-backend

# Or via Docker (web server, default)
docker build -t vulcan-backend ./backend
docker run -p 8000:8000 --env-file .env vulcan-backend

# Celery worker (set PROCESS_TYPE=worker)
docker run --env-file .env -e PROCESS_TYPE=worker vulcan-backend
```

> **Note:** `healthcheckPath` is configured per-service via Railway API (not in `railway.toml`)
> so the Celery worker service is not forced to expose an HTTP endpoint.
