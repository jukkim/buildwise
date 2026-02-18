.PHONY: dev db up down test lint seed migrate worker logs full build

# ---- Local infrastructure ----

up:
	docker-compose up -d

down:
	docker-compose down

db:
	docker-compose up -d db redis

db-reset:
	docker-compose down -v
	docker-compose up -d db redis

logs:
	docker-compose logs -f --tail=100

# ---- Backend ----

backend-dev:
	cd buildwise-backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-test:
	cd buildwise-backend && pytest tests/ -v

backend-lint:
	cd buildwise-backend && ruff check app/ && mypy app/

# ---- Frontend ----

frontend-dev:
	cd buildwise-frontend && npm run dev

frontend-test:
	cd buildwise-frontend && npm test

frontend-lint:
	cd buildwise-frontend && npm run lint

frontend-install:
	cd buildwise-frontend && npm install

# ---- Celery worker ----

worker:
	cd buildwise-backend && celery -A app.worker worker --loglevel=info -Q simulation

# ---- Database ----

migrate:
	cd buildwise-backend && alembic upgrade head

migrate-create:
	cd buildwise-backend && alembic revision --autogenerate -m "$(msg)"

seed:
	cd buildwise-backend && python -m scripts.seed

# ---- Full development ----

dev: up backend-dev

install:
	cd buildwise-backend && pip install -e ".[dev]"
	cd buildwise-frontend && npm install

# ---- Tests ----

test: backend-test

# ---- Lint ----

lint: backend-lint frontend-lint

# ---- Docker full stack ----

full:
	docker-compose --profile full up -d --build

full-down:
	docker-compose --profile full down

build:
	cd buildwise-frontend && npm run build

# ---- Quick Start ----

setup: install db migrate seed
	@echo "Setup complete. Run 'make dev' to start the backend."
