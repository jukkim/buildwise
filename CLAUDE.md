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
Frontend: React 19 + TypeScript + React Three Fiber + Recharts
Backend:  FastAPI + Celery + Redis
Infra:    GCP (Cloud Run + GKE + Cloud SQL + GCS)
Engine:   EnergyPlus 24.1+ (Docker 컨테이너)
AI:       Claude API (자연어), Gemini Pro Vision (사진)
3D:       Three.js 주력(80%) + Blender headless 보조(5%)
```

## 5단계 워크플로우 (SPEC v0.2 §3)

```
① 건물 생성 → ② 건물 설정 → ③ Baseline 시뮬레이션 → ④ M0~M8 비교 → ⑤ 결과 대시보드
   (자연어/사진     (기후,운영시간     (BPS→IDF→E+)       (9 Pod 병렬)      (차트,필터,
    /템플릿)         HVAC,설정온도)                                            PDF,추천)
```

**핵심**: 사용자가 운영시간, HVAC 설비, 설정온도, 외피 등을 조정하면 결과가 달라져야 함.

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
| `buildwise-backend/app/services/simulation/mock_runner.py` | EUI 룩업 테이블 + 결과 생성 |
| `buildwise-backend/config/building_reference/__init__.py` | DOE 건물 레퍼런스 데이터 |
| `buildwise-backend/app/services/results/validator.py` | 결과 검증 (EUI 범위, 물리법칙) |
| `buildwise-backend/config/validation_rules.yaml` | 검증 규칙 정의 |
| `buildwise-backend/tests/verify_ems_calibration.py` | 430개 검증 (eplustbl 정확성) |
| `buildwise-backend/tests/test_mock_runner.py` | 25개 pytest |
| `buildwise-backend/tests/scan_all_buildings_eui.py` | eplustbl.csv 스캔 유틸리티 |
| `buildwise-backend/tests/extract_eplustbl_data.py` | eplustbl 데이터 추출 (Python dict) |

## Related Projects

- **ems_simulation**: `C:\Users\User\Desktop\myjob\8.simulation\ems_simulation`
  - EMS 템플릿 (`.j2`), 검증 로직, EPW, 10도시 결과 데이터
  - eplustbl.csv = mock_runner의 ground truth
  - 경로: `buildings/{type}/results/default/{city}/1year/{strategy}/eplustbl.csv`

## Commands

```bash
# 테스트
cd buildwise-backend
DEBUG=true python -m pytest tests/test_mock_runner.py -v
DEBUG=true python -m tests.verify_ems_calibration

# eplustbl 데이터 추출
DEBUG=true python -m tests.extract_eplustbl_data
DEBUG=true python -m tests.scan_all_buildings_eui
```
