# Docker Compose Local Development Setup

**Date**: 2026-03-11
**Status**: Approved

## Goal

Provide a `docker compose` setup that supports both **development mode** (hot reload) and **production-like mode** (build artifacts) for running the full Vulcan stack locally.

## Architecture

### File Structure

```
Vulcan/
├── docker-compose.yml           # production-like base
├── docker-compose.override.yml  # development mode overrides
├── frontend/
│   ├── Dockerfile               # modified: BACKEND_URL build arg added
│   └── .env                     # user-created, gitignored
├── backend/
│   ├── Dockerfile               # existing, unchanged
│   ├── Dockerfile.worker        # existing, unchanged
│   └── .env                     # user-created, gitignored
```

No new Dockerfiles. Reuses all existing ones.

### Services

| Service | Port | Description | Always On |
|---------|------|-------------|-----------|
| frontend | 3000 | Next.js | Yes |
| backend | 8000 | FastAPI + uvicorn | Yes |
| redis | 6379 | Celery broker + result backend | Yes |
| worker | (none) | Celery worker | No (`--profile worker`) |

### Mode Switching

Uses Docker Compose's native override mechanism:

- **Development mode**: `docker compose up` — auto-loads both `docker-compose.yml` and `docker-compose.override.yml`
- **Production-like mode**: `docker compose -f docker-compose.yml up --build` — only loads the base file

### Environment Variables

Each service reads from its own `.env` file (`env_file` directive):
- `frontend/.env` — based on `frontend/.env.example`
- `backend/.env` — based on `backend/.env.example`

Service-to-service URLs (e.g., `BACKEND_URL`, `CELERY_BROKER_URL`) are set via `environment` in compose, overriding `.env` values to use Docker's internal network.

### Data Persistence

- **SQLite**: Named volume `backend-data` mounted at `/app/data`
- **Redis**: Named volume `redis-data`
- `docker compose down -v` clears all data

## Design Decisions

### Why `override.yml` instead of profiles or separate files

- Docker official recommended pattern for dev/prod separation
- Default behavior (`docker compose up`) is development mode — most common use case
- No config duplication between dev and prod
- Production-like mode is explicit opt-in via `-f docker-compose.yml`

### Why Redis always runs

Backend code initializes Celery config referencing Redis by default. Running Redis avoids connection errors even when the worker profile is inactive. Redis is lightweight (~5MB memory).

### Why worker is a profile

Not all developers need async analysis. Making it optional keeps the default stack lean. Activated with `--profile worker` when needed.

### Why env_file per service (not root .env)

Matches production behavior (Railway sets env vars per service) and existing project structure (`frontend/.env.example`, `backend/.env.example`). Reduces confusion between local and production configuration.

## Development Mode Details

`docker-compose.override.yml` overrides:

- **frontend**: Stops at `builder` stage, runs `npm run dev`, mounts `src/` and `public/`
- **backend**: Runs `uvicorn --reload`, mounts `app/`
- **worker**: Mounts `app/` (requires manual restart for code changes)

## Usage

### Prerequisites

```bash
cp frontend/.env.example frontend/.env
cp backend/.env.example backend/.env
# Edit both .env files with your API keys
```

### Development Mode (default)

```bash
docker compose up                      # frontend + backend + redis
docker compose --profile worker up     # also start celery worker
docker compose up -d                   # background
docker compose logs -f backend         # follow logs
```

### Production-like Mode

```bash
docker compose -f docker-compose.yml up --build
docker compose -f docker-compose.yml --profile worker up --build
```

### Common Operations

```bash
docker compose down                    # stop all
docker compose down -v                 # stop + delete volumes
docker compose up --build backend      # rebuild single service
docker compose restart worker          # restart worker after code change
```
