# Docker Compose Local Development Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add docker-compose setup supporting both development (hot reload) and production-like (build artifacts) modes.

**Architecture:** Uses Docker Compose override pattern — `docker-compose.yml` as production-like base, `docker-compose.override.yml` for dev overrides. Worker runs under `worker` profile. Each service reads its own `.env` file.

**Tech Stack:** Docker Compose, existing Dockerfiles (frontend: node:20-alpine, backend: python:3.13-slim), Redis 7

**Design Doc:** `docs/designs/2026-03-11-docker-compose-local-dev.md`

---

## Chunk 1: Core Setup

### Task 1: Modify frontend Dockerfile to accept BACKEND_URL build arg

**Why:** `next.config.ts` uses `process.env.BACKEND_URL` in rewrites, which are compiled at build time in production mode (`npm run build`). Docker Compose needs to pass the internal network URL (`http://backend:8000`) during build. Without this, the production-like frontend would try to proxy to `localhost:8000` which doesn't exist inside the container.

**Files:**
- Modify: `frontend/Dockerfile`

- [ ] **Step 1: Add ARG and ENV to frontend Dockerfile**

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
ARG BACKEND_URL=http://localhost:8000
ENV BACKEND_URL=$BACKEND_URL
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

Default value `http://localhost:8000` preserves existing behavior for standalone Docker builds.

- [ ] **Step 2: Verify existing frontend Docker build still works**

Run: `cd frontend && docker build -t vulcan-frontend-test . && docker rmi vulcan-frontend-test`
Expected: Build succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/Dockerfile
git commit -m "feat: add BACKEND_URL build arg to frontend Dockerfile for Docker Compose support"
```

---

### Task 2: Create docker-compose.yml (production-like base)

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
services:
  frontend:
    build:
      context: ./frontend
      args:
        BACKEND_URL: http://backend:8000
    ports:
      - "3000:3000"
    env_file: ./frontend/.env
    environment:
      - BACKEND_URL=http://backend:8000
    depends_on:
      backend:
        condition: service_healthy

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: ./backend/.env
    environment:
      - FRONTEND_URL=http://localhost:3000
      - MODE=web
      - DATA_DIR=/app/data
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    volumes:
      - backend-data:/app/data
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 15s

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    env_file: ./backend/.env
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on:
      redis:
        condition: service_healthy
    profiles:
      - worker

volumes:
  backend-data:
  redis-data:
```

- [ ] **Step 2: Validate compose file syntax**

Run: `docker compose config --quiet`
Expected: No errors (exit code 0). Note: this validates with override too, which is fine — we create the override next.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add docker-compose.yml for production-like local setup"
```

---

### Task 3: Create docker-compose.override.yml (development mode)

**Files:**
- Create: `docker-compose.override.yml`

- [ ] **Step 1: Create docker-compose.override.yml**

```yaml
services:
  frontend:
    build:
      context: ./frontend
      target: builder
    command: npm run dev
    volumes:
      - ./frontend/src:/app/src
      - ./frontend/public:/app/public
    environment:
      - NODE_ENV=development
      - BACKEND_URL=http://backend:8000

  backend:
    command: uvicorn app.web.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend/app:/app/app
    environment:
      - DATA_DIR=/app/data

  worker:
    volumes:
      - ./backend/app:/app/app
```

Key points:
- Frontend: stops at `builder` stage (has node_modules), runs `npm run dev`, mounts src/ and public/ for hot reload
- Backend: adds `--reload` flag, mounts app/ for hot reload
- Worker: mounts app/ so task code stays in sync (requires manual restart)
- Ports, env_file, depends_on, healthcheck all inherited from base

- [ ] **Step 2: Validate combined compose config**

Run: `docker compose config --quiet`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.override.yml
git commit -m "feat: add docker-compose.override.yml for development mode with hot reload"
```

---

## Chunk 2: Documentation & Verification

### Task 4: Add Docker Compose section to README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add Docker Compose section after the "Using Makefile" section (after line 187)**

Insert the following after the Makefile section and before the Testing section:

```markdown
### Using Docker Compose

Docker Compose supports two modes: **development** (hot reload) and **production-like** (built artifacts).

**Prerequisites:**

```bash
cp frontend/.env.example frontend/.env
cp backend/.env.example backend/.env
# Edit both .env files with your API keys
```

**Development mode** (default — auto-loads override file, supports hot reload):

```bash
docker compose up                        # frontend + backend + redis
docker compose --profile worker up       # also start Celery worker
docker compose up -d                     # run in background
docker compose logs -f backend           # follow logs
```

**Production-like mode** (builds images, runs production artifacts):

```bash
docker compose -f docker-compose.yml up --build
docker compose -f docker-compose.yml --profile worker up --build
```

**Common operations:**

```bash
docker compose down                      # stop all services
docker compose down -v                   # stop and delete all data (SQLite, Redis)
docker compose up --build backend        # rebuild a single service
docker compose restart worker            # restart worker after code change
```

| Service | URL | Description |
|---------|-----|-------------|
| frontend | http://localhost:3000 | Next.js web UI |
| backend | http://localhost:8000 | FastAPI API server |
| redis | localhost:6379 | Celery message broker |
| worker | — | Celery worker (requires `--profile worker`) |

> **Note:** In development mode, frontend and backend code changes auto-reload. Celery worker requires manual restart (`docker compose restart worker`) after code changes.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add Docker Compose usage section to README"
```

---

### Task 5: Smoke test — production-like mode

- [ ] **Step 1: Build and start in production-like mode**

Run: `docker compose -f docker-compose.yml up --build -d`
Expected: All 3 services (frontend, backend, redis) start without errors.

- [ ] **Step 2: Verify backend health**

Run: `curl -s http://localhost:8000/api/health`
Expected: 200 response with health status.

- [ ] **Step 3: Verify frontend loads**

Run: `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000`
Expected: 200.

- [ ] **Step 4: Verify frontend proxies to backend**

Run: `curl -s http://localhost:3000/api/health`
Expected: Same response as direct backend health check.

- [ ] **Step 5: Tear down**

Run: `docker compose -f docker-compose.yml down`

---

### Task 6: Smoke test — development mode

- [ ] **Step 1: Start in development mode**

Run: `docker compose up -d`
Expected: All 3 services start without errors.

- [ ] **Step 2: Verify backend responds**

Run: `curl -s http://localhost:8000/api/health`
Expected: 200 response.

- [ ] **Step 3: Verify frontend responds**

Run: `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000`
Expected: 200.

- [ ] **Step 4: Tear down**

Run: `docker compose down`

- [ ] **Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: docker-compose adjustments from smoke testing"
```
