# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: BuildWise

건물 에너지 시뮬레이션 SaaS 플랫폼. 자연어 입력 → 3D 건물 생성 → EnergyPlus 시뮬레이션 → EMS 전략(M0~M8) 비교 → 결과 분석 대시보드.

- **제품명**: BuildWise (buildwise.ai)
- **대상 사용자**: 비전문가(건물주) ~ 전문가(에너지 컨설턴트)
- **설계서**: `SPEC_v0.2.md` (전체 아키텍처, 5단계 워크플로우, 과금, 로드맵)
- **상태**: Phase 1 MVP 개발 중 (mock_runner 보정 완료, 사용자 설정 반영 진행 중)

## Architecture

```
Frontend: React 19 + TypeScript + Vite 6 + Tailwind 4 + React Three Fiber + Recharts
Backend:  FastAPI + Celery + Redis + SQLAlchemy 2.0 (async) + Alembic
DB:       TimescaleDB 2.17.2 (PostgreSQL 16)
Auth:     Auth0 (JWT RS256) / 개발 시 X-User-Id 헤더
Infra:    Railway (백엔드+워커) + Vercel (프론트) / 로컬 Docker Compose
Engine:   EnergyPlus 24.1+ (Docker 컨테이너)
AI:       Claude API (자연어→BPS) + 규칙기반 NL 파서 fallback (API 키 없을 때)
3D:       Three.js 주력(80%) + Blender headless 보조(5%)
Billing:  Stripe (예정)
```

## 5단계 워크플로우 (SPEC v0.2 §3)

```
① 건물 생성 → ② 건물 설정 → ③ Baseline 시뮬레이션 → ④ M0~M8 비교 → ⑤ 결과 대시보드
   (자연어/사진     (기후,운영시간     (BPS→IDF→E+)       (9 Pod 병렬)      (차트,필터,
    /템플릿)         HVAC,설정온도)                                            PDF,추천)
```

**핵심**: 사용자가 운영시간, HVAC 설비, 설정온도, 외피 등을 조정하면 결과가 달라져야 함.

## API Routes

| Prefix | 파일 | 주요 기능 |
|--------|------|----------|
| `/api/v1/auth` | `api/v1/auth.py` | Auth0 설정, 로그인, /me |
| `/api/v1/projects` | `api/v1/projects.py` | 프로젝트 CRUD |
| `/api/v1/projects/{id}/buildings` | `api/v1/buildings.py` | 건물 CRUD, BPS 설정, IDF 업로드/다운로드 |
| `/api/v1/buildings/templates` | `api/v1/templates.py` | DOE 건물 템플릿 (6종) |
| `/api/v1/simulations` | `api/v1/simulations.py` | 시뮬 생성(202), 배치, 진행상황, 취소 |
| `/api/v1/simulations/{id}/results` | `api/v1/results.py` | 전략 비교 + 시계열 결과 |
| `/api/v1/billing` | `api/v1/billing.py` | 요금제, 사용량, 구독 |
| `/api/v1/ai` | `api/v1/ai.py` | 자연어 → BPS 파싱 (Claude API / 규칙기반 fallback) |

## Frontend Routes

| Path | Page | 설명 |
|------|------|------|
| `/` | LandingPage | 랜딩 |
| `/login` | Login | Auth0 로그인 |
| `/projects` | Dashboard | 프로젝트 목록 |
| `/projects/:id` | ProjectDetail | 프로젝트 상세 |
| `/projects/:id/buildings/:id` | BuildingEditor | 건물 BPS 편집 + 3D 뷰어 |
| `/simulations/:id/progress` | SimulationProgress | 시뮬 진행 상태 |
| `/simulations/:id/results` | Results | 전략 비교 대시보드 |
| `/compare` | CityComparison | 다도시 비교 |
| `/compare/progress` | MultiCityProgress | 다도시 시뮬 진행 |
| `/settings` | Settings | 사용자 설정 |

## DB Schema (Alembic)

3개 마이그레이션 (`buildwise-backend/alembic/versions/`):
- `001_initial_schema` — users, projects, buildings, simulation_configs, simulation_runs, energy_results
- `002_add_is_mock_to_energy_results`
- `003_add_monthly_profile_json`

## Mock Runner 데이터 보정 (완료: 2026-02-20)

### 데이터 소스
- **Ground truth**: `ems_simulation/buildings/*/results/default/*/1year/*/eplustbl.csv`
- **모델**: m0-m8 EnergyPlus 시뮬레이션 (2026-02-11 실행, EnergyPlus 24.1)
- **범위**: 6건물 × 최대10전략 × 10도시 = **398개** 정확한 EUI 값

### 건물별 Baseline EUI (kWh/m²/year, eplustbl 10도시 평균)

| Building | EUI | HVAC | System | Floor Area |
|---|---|---|---|---|
| large_office | 120.1 | 28% | Chiller+VAV | 46,320m² |
| medium_office | 77.8 | 45% | VRF | 4,982m² |
| small_office | 97.8 | 28% | PSZ-HP | 511m² |
| standalone_retail | 125.6 | 37% | PSZ-AC | 2,294m² |
| primary_school | 139.5 | 39% | VAV+Chiller/Boiler | 6,871m² |
| hospital | 339.6 | 55% | Chiller+VAV | 22,422m² |

### mock_runner 구조

```python
_EUI_TABLE[building_type][strategy][city] → 정확한 EUI (kWh/m²)
# 폴백 체인: 정확값 → baseline×(1-fallback%) → 도시평균 → 기본값 180
```

### 전략 적용 가능성 (HVAC 의존)

| 전략 | large_office | medium_office | small_office | retail | school | hospital |
|---|---|---|---|---|---|---|
| M0 야간정지 | ✓ | =(baseline) | est | 역효과(-14%) | ✓ | ✓ |
| M1 스마트시작 | ✓ | est | est | est | =(baseline) | ✓ |
| M2 외기냉방 | ✓ | N/A(VRF) | ✓ | ✓ | ✓ | ✓ |
| M3 냉동기단계 | ✓ | N/A | N/A | N/A | ✓ | ✓ |
| M4 PMV보통 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| M5 PMV절약 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| M6 통합(M2+M3) | ✓ | N/A | =M2 | =M2 | =M2 | ✓ |
| M7 전체보통 | ✓ | est | ✓ | ✓ | ✓ | ✓ |
| M8 전체절약 | ✓ | est | ✓ | ✓ | ✓ | ✓ |

✓=eplustbl, est=추정, N/A=해당없음, =동일

### TODO: 사용자 설정 반영 보정
mock_runner가 BPS 사용자 설정에 따라 결과를 조정해야 함:
- 운영시간 (08~18 기본 → 사용자 변경 시 보정)
- 냉방/난방 설정온도 (24°C/20°C 기본)
- HVAC COP/효율
- WWR, 외피 U-value
- 재실밀도, 토요근무

## Key Files

| 파일 | 역할 |
|---|---|
| `buildwise-backend/app/main.py` | FastAPI 엔트리포인트, 라우터 등록, CORS, 보안 헤더 |
| `buildwise-backend/app/config.py` | pydantic-settings 환경변수 (DB, Redis, Auth0, Stripe, AI) |
| `buildwise-backend/app/db.py` | SQLAlchemy async 엔진 + 세션 |
| `buildwise-backend/app/worker.py` | Celery 워커 설정 |
| `buildwise-backend/app/services/ai/nl_parser.py` | 자연어→BPS 파싱 (Claude API + 규칙기반 fallback) |
| `buildwise-backend/app/services/ai/prompts.py` | Claude 시스템 프롬프트 + tool 정의 |
| `buildwise-backend/app/services/simulation/mock_runner.py` | EUI 룩업 테이블 + 결과 생성 |
| `buildwise-backend/app/services/simulation/service.py` | 시뮬 오케스트레이션 (전략 자동 결정, DB 저장) |
| `buildwise-backend/app/services/simulation/runner.py` | EnergyPlus 실행 + mock 분기 |
| `buildwise-backend/app/services/idf/ems_bridge.py` | ems_simulation IDF 생성기 위임 브릿지 |
| `buildwise-backend/app/services/idf/generator.py` | IDF 생성 (ems_bridge 위임 + fallback) |
| `buildwise-backend/app/services/bps/validator.py` | BPS 검증 + 건물별 적용 가능 전략 판별 |
| `buildwise-backend/app/services/results/validator.py` | 결과 검증 (EUI 범위, 물리법칙) |
| `buildwise-backend/config/building_reference/__init__.py` | DOE 건물 레퍼런스 데이터 |
| `buildwise-backend/config/validation_rules.yaml` | 검증 규칙 정의 |
| `buildwise-frontend/src/App.tsx` | React 라우터 + RequireAuth |
| `buildwise-frontend/src/api/client.ts` | Axios API 클라이언트 |
| `buildwise-frontend/src/pages/Results.tsx` | 전략 비교 대시보드 |
| `buildwise-frontend/src/pages/BuildingEditor.tsx` | BPS 폼 + 3D 뷰어 |
| `buildwise-frontend/src/features/pdf-report/` | PDF 보고서 생성 (jsPDF) |
| `buildwise-backend/tests/verify_ems_calibration.py` | 430개 검증 (eplustbl 정확성) |
| `buildwise-backend/tests/test_mock_runner.py` | 25개 pytest |

## Related Projects

- **ems_simulation**: `C:\Users\User\Desktop\myjob\8.simulation\ems_simulation`
  - EMS 템플릿 (`.j2`), 검증 로직, EPW, 10도시 결과 데이터
  - eplustbl.csv = mock_runner의 ground truth
  - 경로: `buildings/{type}/results/default/{city}/1year/{strategy}/eplustbl.csv`

## Commands

```bash
# 로컬 개발 (Docker)
docker compose up -d          # DB + Redis + Backend + Worker
docker compose up -d --build  # 이미지 재빌드 포함

# 프론트엔드 (로컬 Vite 개발서버)
cd buildwise-frontend && npm run dev   # http://localhost:5173

# 테스트
cd buildwise-backend
DEBUG=true python -m pytest tests/test_mock_runner.py -v
DEBUG=true python -m tests.verify_ems_calibration

# eplustbl 데이터 추출
DEBUG=true python -m tests.extract_eplustbl_data
DEBUG=true python -m tests.scan_all_buildings_eui

# 프론트 테스트
cd buildwise-frontend && npm test

# 린트
cd buildwise-backend && ruff check .
cd buildwise-frontend && npm run lint
```

## Deployment

| 서비스 | 플랫폼 | 설정 파일 |
|--------|--------|----------|
| Backend + Celery Worker | Railway (Nixpacks) | `buildwise-backend/railway.json` |
| Frontend SPA | Vercel | `buildwise-frontend/vercel.json` |
| 로컬 전체 스택 | Docker Compose | `docker-compose.yml` |

Railway 시작 커맨드: alembic migrate → seed → Celery worker(백그라운드) + uvicorn

## Docs

| 문서 | 용도 |
|------|------|
| `docs/blender-mcp-research.md` | Blender MCP + AI 3D 기술 조사 (2026-05-05) |
| `docs/ems-strategy-mapping.md` | EMS 전략 매핑 |
| `docs/idf-generation-design.md` | IDF 생성 설계 |
| `docs/mvp-scope-adjustment.md` | MVP 범위 조정 |
| `docs/strategy-naming-reconciliation.md` | 전략 명칭 통일 |
| `docs/test-strategy.md` | 테스트 전략 |
