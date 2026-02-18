.PHONY: dev db up down test lint

# Local infrastructure
up:
	docker-compose up -d

down:
	docker-compose down

db:
	docker-compose up -d db redis

db-reset:
	docker-compose down -v
	docker-compose up -d db redis

# Backend
backend-dev:
	cd buildwise-backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-test:
	cd buildwise-backend && pytest tests/ -v

backend-lint:
	cd buildwise-backend && ruff check app/ && mypy app/

# Frontend
frontend-dev:
	cd buildwise-frontend && npm run dev

frontend-test:
	cd buildwise-frontend && npm test

frontend-lint:
	cd buildwise-frontend && npm run lint

# Celery worker
worker:
	cd buildwise-backend && celery -A app.worker worker --loglevel=info

# Full development
dev: up backend-dev

# Tests
test: backend-test frontend-test

# Lint
lint: backend-lint frontend-lint
