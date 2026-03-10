# Testing

## Running Tests

```bash
# Backend tests (341 tests — unit + integration + E2E, all mocked, no API keys needed)
make test-backend

# Frontend tests (unit + integration)
make test-frontend

# Browser E2E tests (Playwright, requires dev server)
cd frontend && npm run test:e2e

# Adversarial red-team tests only
cd backend && pytest tests/evals/test_adversarial.py -v

# Planner evaluation (offline, no API keys)
cd backend && python -m evals.run_planner_eval --dry-run
```

## CI/CD Pipeline

GitHub Actions (`.github/workflows/ci.yml`) runs automatically:

```
Push to main ──┬── Backend Tests (pytest, ≥90 test gate) ──┬── E2E Tests ──┬── Deploy Backend (Railway)
               │                                           │               │
               └── Frontend Tests (tsc + vitest + build) ──┘               └── Deploy Frontend (Vercel)
```

- **PR**: CI only (test + build, no deploy)
- **Push to main**: CI + CD (deploy after all tests pass)

**Required GitHub Secrets** for CD:

| Secret | Purpose |
|--------|---------|
| `RAILWAY_TOKEN` | Railway deploy token (`railway tokens create`) |
| `VERCEL_TOKEN` | Vercel deploy token (vercel.com → Settings → Tokens) |
| `VERCEL_ORG_ID` | From `frontend/.vercel/project.json` |
| `VERCEL_PROJECT_ID` | From `frontend/.vercel/project.json` |
