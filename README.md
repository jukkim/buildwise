# BuildWise

건물 에너지 시뮬레이션 SaaS 플랫폼.
자연어 입력 → 3D 건물 생성 → EnergyPlus 시뮬레이션 → EMS 전략(M0~M8) 비교 → 결과 분석 대시보드.

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose

### Development Setup

```bash
# 1. 로컬 인프라 (PostgreSQL + TimescaleDB, Redis)
docker-compose up -d

# 2. 백엔드
cd buildwise-backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload

# 3. 프론트엔드
cd buildwise-frontend
npm install
npm run dev
```

### API Documentation

- Swagger UI: http://localhost:8000/docs
- OpenAPI Spec: `schemas/openapi.yaml`

## Architecture

```
Frontend: React 19 + TypeScript + React Three Fiber + Recharts
Backend:  FastAPI + Celery + Redis
DB:       PostgreSQL 16 + TimescaleDB
Infra:    GCP (Cloud Run + GKE + Cloud SQL + GCS)
Engine:   EnergyPlus 24.1+ (Docker)
```

## Project Structure

```
buildwise/
├── schemas/                    # 계약 (JSON Schema, OpenAPI, DDL)
│   ├── bps.schema.json         # Building Parameter Schema
│   ├── database.sql            # PostgreSQL DDL
│   └── openapi.yaml            # API 계약
├── docs/                       # 설계 문서
├── buildwise-backend/          # FastAPI 백엔드
│   ├── app/
│   │   ├── api/v1/             # API 라우트
│   │   ├── models/             # SQLAlchemy 모델
│   │   ├── schemas/            # Pydantic 스키마
│   │   └── services/           # 비즈니스 로직
│   │       ├── bps/            # BPS 검증/기본값
│   │       ├── idf/            # IDF 생성 파이프라인
│   │       ├── simulation/     # E+ 실행, Celery 태스크
│   │       ├── ems/            # EMS 전략 적용
│   │       ├── results/        # 결과 처리
│   │       └── validation/     # 물리/IDF/결과 검증
│   └── pyproject.toml
├── buildwise-frontend/         # React 프론트엔드
├── energyplus/                 # EnergyPlus 관련
│   ├── ems_templates/          # Jinja2 EMS 템플릿 (15개)
│   ├── building_templates/     # Base IDF 템플릿 (6종)
│   ├── weather/                # EPW 파일 (10도시)
│   └── Dockerfile
├── config/                     # 설정 파일
│   ├── building_defaults/      # 건물유형별 기본값
│   ├── fair_comparison.yaml    # 공정비교 프레임워크
│   └── strategy_definitions/   # 전략 정의
├── tests/                      # 테스트
└── docker-compose.yml          # 로컬 개발 환경
```

## Key Design Decisions

| 결정 | 근거 |
|------|------|
| BPS as SSOT | 전체 시스템 단일 진실 소스 |
| Template-based IDF | MVP에서 base_template 수정 방식 (scratch 대비 10배 빠름) |
| Three.js 80% + Blender 5% | 서버 비용 90% 절감 |
| SSE (not WebSocket) | MVP 단순화, Phase 2에서 WebSocket 전환 |

## EMS Strategies (M0~M8)

| 코드 | 이름 | 설명 |
|------|------|------|
| M0 | 야간 정지 | 퇴근 후 HVAC 자동 정지 |
| M1 | 스마트 시작 | 기온에 따라 출근 전 예열/예냉 |
| M2 | 외기 냉방 | 외기가 시원할 때 자연 환기 활용 |
| M3 | 냉동기 단계제어 | 부하에 맞게 냉동기 대수 조절 |
| M4 | 쾌적 최적화 (보통) | PMV 0.5 기준 설정온도 자동 조정 |
| M5 | 쾌적 최적화 (절약) | PMV 0.7 기준 더 넓은 허용 범위 |
| M6 | 설비 통합제어 | M2+M3 복합 적용 |
| M7 | 통합+쾌적(보통) | M6+M4 최적 조합 |
| M8 | 통합+쾌적(절약) | M6+M5 최대 절감 |

## Spec

상세 스펙: `SPEC_v0.2.md`
