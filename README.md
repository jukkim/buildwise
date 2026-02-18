# BuildWise

건물 에너지 시뮬레이션 SaaS 플랫폼.
자연어 입력 → 3D 건물 생성 → EnergyPlus 시뮬레이션 → EMS 전략(M0~M8) 비교 → 결과 분석 대시보드.

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose

### 1. Start Infrastructure

```bash
# PostgreSQL + TimescaleDB, Redis
make db
```

### 2. Backend Setup

```bash
cd buildwise-backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run database migration
alembic upgrade head

# Seed demo data (demo@buildwise.ai, PRO plan)
python -m scripts.seed

# Start API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

```bash
cd buildwise-frontend
npm install
npm run dev   # → http://localhost:5173
```

### 4. Login

Open http://localhost:5173 and sign in with `demo@buildwise.ai`.

### One-line Setup (Make)

```bash
make setup    # install deps → start db → migrate → seed
make dev      # start backend (port 8000)
# In another terminal:
make frontend-dev  # start frontend (port 5173)
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://buildwise:buildwise_dev@localhost:5432/buildwise` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for Celery |
| `DEBUG` | `true` | Enable mock simulation mode |
| `ENERGYPLUS_IMAGE` | (empty) | Docker image for E+ (empty = mock mode) |

### API Documentation

- Swagger UI: http://localhost:8000/docs
- OpenAPI Spec: `schemas/openapi.yaml`

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | Dev login by email |
| GET | `/api/v1/auth/me` | Current user info |
| GET/POST | `/api/v1/projects` | List / Create projects |
| GET/PATCH/DELETE | `/api/v1/projects/{id}` | Project CRUD |
| GET/POST | `/api/v1/projects/{id}/buildings` | List / Create buildings |
| GET/PATCH/DELETE | `/api/v1/projects/{id}/buildings/{id}` | Building CRUD |
| PATCH | `/api/v1/projects/{id}/buildings/{id}/bps` | Update BPS parameters |
| GET | `/api/v1/projects/{id}/buildings/{id}/simulations` | Simulation history |
| GET | `/api/v1/buildings/templates` | Building templates (6 types) |
| POST | `/api/v1/simulations` | Start simulation |
| GET | `/api/v1/simulations/{id}/progress` | Simulation progress |
| POST | `/api/v1/simulations/{id}/cancel` | Cancel simulation |
| GET | `/api/v1/simulations/{id}/results` | Strategy comparison results |

## Architecture

```
Frontend: React 19 + TypeScript + Tailwind CSS 4 + Recharts
Backend:  FastAPI + Celery + Redis + SQLAlchemy 2.0 (async)
DB:       PostgreSQL 16 + TimescaleDB
Infra:    GCP (Cloud Run + GKE + Cloud SQL + GCS)
Engine:   EnergyPlus 24.1+ (Docker)
```

## Project Structure

```
buildwise/
├── schemas/                    # Contracts (JSON Schema, OpenAPI, DDL)
│   ├── bps.schema.json         # Building Parameter Schema
│   ├── database.sql            # PostgreSQL DDL
│   └── openapi.yaml            # API contract
├── docs/                       # Design documents
├── buildwise-backend/          # FastAPI backend
│   ├── app/
│   │   ├── api/v1/             # API routes
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── services/           # Business logic
│   │   │   ├── bps/            # BPS validation/defaults
│   │   │   ├── idf/            # IDF generation pipeline
│   │   │   ├── simulation/     # E+ runner + mock runner
│   │   │   ├── ems/            # EMS strategy rendering
│   │   │   └── results/        # Result parsing + comparison
│   │   └── tasks/              # Celery tasks
│   ├── tests/                  # pytest tests
│   ├── alembic/                # Database migrations
│   ├── scripts/                # Seed data, utilities
│   ├── Dockerfile
│   └── pyproject.toml
├── buildwise-frontend/         # React frontend
│   ├── src/
│   │   ├── api/                # API client + types
│   │   ├── components/         # Shared components
│   │   └── pages/              # Route pages
│   └── package.json
├── energyplus/                 # EnergyPlus container
│   ├── ems_templates/          # Jinja2 EMS templates (15)
│   ├── building_templates/     # Base IDF templates (6 types)
│   ├── weather/                # EPW files (10 Korean cities)
│   └── Dockerfile
├── Makefile                    # Dev commands
└── docker-compose.yml          # Local dev environment
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| BPS as SSOT | Single source of truth for entire system |
| Template-based IDF | Modify base_template instead of generating from scratch (10x faster for MVP) |
| Mock simulation mode | Pre-computed results when DEBUG=true (no E+ needed for dev) |
| Soft delete | Projects use status=DELETED instead of hard delete |
| SSE (not WebSocket) | MVP simplification, WebSocket in Phase 2 |

## EMS Strategies (M0~M8)

| Code | Name | Description |
|------|------|-------------|
| M0 | Night Stop | Auto-stop HVAC after work hours |
| M1 | Smart Start | Pre-heat/cool based on outdoor temp |
| M2 | Economizer | Use outdoor air when conditions are favorable |
| M3 | Chiller Staging | Match chiller count to load |
| M4 | Comfort Optimize (Normal) | Auto-adjust setpoints, PMV 0.5 |
| M5 | Comfort Optimize (Savings) | Wider comfort band, PMV 0.7 |
| M6 | Integrated Control | M2 + M3 combined |
| M7 | Full Normal | M6 + M4 optimal combination |
| M8 | Full Savings | M6 + M5 maximum savings |

## Spec

Full specification: `SPEC_v0.2.md`
