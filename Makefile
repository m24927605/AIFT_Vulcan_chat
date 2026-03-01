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
