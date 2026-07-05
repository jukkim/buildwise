# BuildWise Backend — 4090 Self-Host Plan

> **상태**: DRAFT — Track 3 본격 진입 시 적용 (사용자 결정 2026-06-05 18:55)
> **이전**: Railway Hobby plan ($5/월) — 2026-06-05 정지 결정
> **목표**: 4090 (workspace localhost) 통합 self-host — 비용 $0 + 다른 5 backend 와 같은 패턴

---

## 1. 배경

- BuildWise = AI 챔피언 Track 3 (Simulation / AI 모델) 의 일부
- Stack: FastAPI + Celery worker + Alembic migrations + PostgreSQL + Redis (Celery broker)
- Railway 4월 한달 사용량 = vCPU $0.17 + Memory $3.56 + Disk $0.05 = $3.78 (Hobby plan $5 credit 안 흡수)
- 정지 결정 = Track 3 미진입 + workspace 통합 의도

---

## 2. 4090 Self-Host 단계 (재진입 시)

### 2.1 PostgreSQL 설치

```powershell
# Option A: Windows native service
winget install -e --id PostgreSQL.PostgreSQL.16
# Option B: Docker (다른 backend 와 일관)
docker run -d --name buildwise-postgres -p 5432:5432 \
  -e POSTGRES_PASSWORD=... -v buildwise-pg-data:/var/lib/postgresql/data \
  postgres:16-alpine
```

### 2.2 Redis 설치 (Celery broker)

```powershell
# Docker (가장 simple)
docker run -d --name buildwise-redis -p 6379:6379 redis:7-alpine
```

### 2.3 buildwise-backend 환경 setup

```powershell
cd 8.simulation/blender/buildwise-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .

# .env 설정
# DATABASE_URL=postgresql://buildwise:...@localhost:5432/buildwise
# CELERY_BROKER_URL=redis://localhost:6379/0
# CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Alembic migrations
PYTHONPATH=. python -m alembic upgrade head
PYTHONPATH=. python scripts/seed.py
```

### 2.4 Port 할당

- **:8070** = buildwise-backend (FastAPI) — `myjob/docs/PORTS.md` 갱신 의무
- :5432 = PostgreSQL (internal)
- :6379 = Redis (internal)

(다른 backend 와 충돌 회피: 8005/8010/8011/8020/8021/8030/8040/8050/8060 사용 중)

### 2.5 Startup wrapper (Windows Startup folder)

```bat
@echo off
REM buildwise-api.bat (Startup folder 등록)
cd /d C:\Users\User\Desktop\myjob\8.simulation\blender\buildwise-backend
call .venv\Scripts\activate.bat
start /B uvicorn app.main:app --host 127.0.0.1 --port 8070 >> logs/buildwise-api.log 2>&1
start /B celery -A app.worker worker -Q simulation --loglevel=info --concurrency=2 >> logs/buildwise-worker.log 2>&1
```

Startup folder:
- `buildwise-api.bat`
- (PostgreSQL service 는 자동, Redis docker 도 `--restart unless-stopped`)

### 2.6 Cloudflare Tunnel hostname 추가

```yaml
# ~/.cloudflared/config.yml ingress 추가
- hostname: buildwise-api.building-energy.xyz
  service: http://127.0.0.1:8070
```

DNS CNAME 추가:
```
buildwise-api.building-energy.xyz → 39a65ef6-8e7d-4fc7-900a-771910f8b986.cfargotunnel.com
```

### 2.7 SSOT 갱신

| 파일 | 추가 |
|------|------|
| `myjob/CLAUDE.md` §4090 Backend Services | port 8070 row 추가 |
| `myjob/docs/PORTS.md` | :8070 BuildWise entry |
| `myjob/docs/DEPLOYMENTS.md` | `buildwise-api.building-energy.xyz` 등재 (현 "미배포" → "4090 self-host") |
| `8.simulation/CLAUDE.md` | 운영 서비스 표 갱신 |

---

## 3. 작업 시간 + 비용

| 단계 | 시간 | 비용 |
|------|---:|---:|
| PostgreSQL 설치 + 설정 | 1h | $0 |
| Redis 설치 (Docker) | 30분 | $0 |
| venv + dependencies + migrations | 30분 | $0 |
| Startup wrapper + Cloudflare Tunnel | 30분 | $0 |
| SSOT 갱신 (4 docs) | 30분 | $0 |
| 검증 + smoke test | 30분 | $0 |
| **총** | **~3.5h** | **$0** |

---

## 4. 4090 자원 영향 (예상)

| 자원 | 현재 (5 backend 합) | BuildWise 추가 | 여유 |
|------|---:|---:|---:|
| CPU | ~30-40% | +5-10% (idle 시 minimal) | 50%+ |
| RAM | ~12-16 GB | +1-2 GB | 10+ GB |
| Disk | NVMe 충분 | PostgreSQL ~5-20 GB | 500+ GB |
| GPU | ~10-12 GB | 0 (CPU 작업) | 12+ GB |

→ **4090 여유 충분, 영향 minimal**.

---

## 5. 진입 조건 (사용자 결정)

본 plan = **Track 3 본격 진입 시점** 에 진행. trigger:
- ① 사용자 명시 "buildwise 진행" / "Track 3 진행"
- ② AI 챔포니언 다른 Track (1/2/4) 종료 + Track 3 우선순위 진입
- ③ 외부 demo 요청 (Track 3 frontend `buildwise.ai` deploy 필요)

미진입 시 = 본 plan 유보, 자원 0.

---

## 6. SSOT cross-link

- 사용자 결정 ledger: memory `project_session_2026-06-05_v24_deprecate_exaone_active` (Cascade 룰 강화 + 자원 정리)
- Railway 정지 결정: 2026-06-05 18:57 (사용자 명시 "A, self host")
- 4090 backend pattern: `myjob/CLAUDE.md §4090 Backend Services` (현 6 backend, BuildWise 추가 시 7 backend)
- 글로벌 룰: `~/.claude/CLAUDE.md` Cascade 룰
