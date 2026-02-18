# BuildWise 테스트 전략

> **작성일**: 2026-02-18

---

## 1. 테스트 피라미드

```
              E2E (5%)
           Playwright
          /          \
     Integration (25%)
     API + DB + Celery
    /                  \
   Unit Tests (70%)
   pytest + Vitest
```

---

## 2. 백엔드 테스트 (pytest)

### 2.1 단위 테스트

| 모듈 | 테스트 대상 | 테스트 케이스 |
|------|-----------|-------------|
| `services/bps/` | BPS 검증 | 유효 BPS 6종 통과, 누락 필드 거부, 범위 초과 거부, HVAC-건물유형 불일치 거부 |
| `services/idf/pipeline.py` | IDF 생성 | 6종 건물별 IDF 생성 성공, 설정온도 반영 확인, EMS 주입 확인, 공정비교 불변식 |
| `services/idf/parameter_modifier.py` | 파라미터 수정 | 설정온도 변경, WWR 변경, 층 승수 적용 |
| `services/idf/schedule_generator.py` | 스케줄 생성 | 평일/토요일/공휴일 스케줄, 운영시간 반영 |
| `services/idf/ems_injector.py` | EMS 주입 | 15개 템플릿 렌더링, 건물유형별 context 변수, 적용불가 전략 거부 |
| `services/validation/` | 검증 규칙 | PHY-001~004 물리 검증, INV-001~009 불변 규칙 |
| `services/results/` | 결과 처리 | CSV 파싱, EUI 계산, savings 퍼센트, 월별 집계 |
| `schemas/` | Pydantic 모델 | 요청/응답 직렬화, 기본값 적용 |

### 2.2 통합 테스트

| 시나리오 | 범위 |
|---------|------|
| API 엔드포인트 | FastAPI TestClient + 테스트 DB, 전체 CRUD 흐름 |
| BPS → IDF 라운드트립 | BPS 입력 → IDF 생성 → 파일 검증 |
| Celery 태스크 | 시뮬레이션 태스크 시작/완료/실패 흐름 |
| 과금 제한 | Free 유저 M0~M3 제한, Pro 전체 허용, 월 한도 |
| 공정비교 | baseline → M0~M8 설비 크기 일치 검증 |

### 2.3 시뮬레이션 스모크 테스트

**목적**: BuildWise가 생성한 IDF가 실제 EnergyPlus에서 에러 없이 실행되는지 검증

```python
@pytest.mark.slow
@pytest.mark.parametrize("building_type", [
    "large_office", "medium_office", "small_office",
    "standalone_retail", "primary_school",
])
def test_simulation_smoke(building_type):
    """1개월 시뮬레이션을 실행하여 Severe Error 없음 확인"""
    bps = load_default_bps(building_type)
    bps["simulation"]["period"] = "1month_summer"

    result = pipeline.generate(bps, strategy="baseline")
    assert result.is_valid

    # EnergyPlus 실행 (Docker)
    sim_result = run_energyplus(result.idf_path, timeout=300)
    assert sim_result.severe_errors == 0
    assert sim_result.exit_code == 0
```

---

## 3. Ground Truth 검증

### 소스
`energyplus_sim/buildings/*/results/` — 450+ 검증된 시뮬레이션 결과

### 검증 방법

BuildWise가 동일한 BPS로 생성한 IDF의 시뮬레이션 결과를 ground truth와 비교:

```python
@pytest.mark.parametrize("city,building_type,strategy", GROUND_TRUTH_CASES)
def test_against_ground_truth(city, building_type, strategy):
    """BuildWise 결과가 검증된 결과와 5% 이내 일치"""
    expected = load_ground_truth(city, building_type, strategy)
    bps = load_default_bps(building_type, city=city)

    result = pipeline.generate(bps, strategy=strategy)
    actual = run_and_parse(result.idf_path)

    assert abs(actual.total_energy - expected.total_energy) / expected.total_energy < 0.05
    assert abs(actual.eui - expected.eui) / expected.eui < 0.05
```

### 허용 오차

| 지표 | 허용 오차 | 근거 |
|------|---------|------|
| 총 에너지 | 5% | 템플릿 수정 방식에서 예상되는 파라미터 차이 |
| EUI | 5% | 동일 |
| 피크 전력 | 10% | 피크는 변동성이 높음 |
| 절감률 순위 | 일치 | M7 > M8 > ... > M0 순위는 동일해야 함 |

---

## 4. 프론트엔드 테스트 (Vitest)

### 4.1 단위 테스트

| 컴포넌트 | 테스트 |
|---------|-------|
| BPS 폼 | 입력 검증, 기본값 적용, 건물유형 변경 시 HVAC 자동 변경 |
| 전략 선택기 | 건물유형별 비활성화, 다중 선택 |
| 결과 테이블 | 정렬, 필터링, savings 표시 |
| 차트 컴포넌트 | 데이터 바인딩, 빈 데이터 처리 |

### 4.2 통합 테스트

| 시나리오 | 범위 |
|---------|------|
| 설정 위저드 플로우 | Step 1~5 네비게이션, 데이터 유지 |
| API 목 테스트 | MSW(Mock Service Worker) 기반 API 응답 시뮬레이션 |
| 3D 뷰어 | R3F 렌더링, 건물 모델 로딩 |

---

## 5. E2E 테스트 (Playwright)

```
Scenario: 템플릿 → 시뮬레이션 → 결과 확인
  1. 로그인
  2. 프로젝트 생성
  3. Large Office 템플릿 선택
  4. 기본값으로 설정 완료
  5. 시뮬레이션 시작
  6. 진행률 표시 확인
  7. 결과 대시보드 로딩
  8. M0~M8 비교 테이블 데이터 확인
  9. 차트 렌더링 확인
```

---

## 6. CI/CD 파이프라인

```yaml
# .github/workflows/ci.yml
on: [push, pull_request]

jobs:
  backend:
    steps:
      - ruff check (lint)
      - mypy (type check)
      - pytest --cov (unit + integration)

  frontend:
    steps:
      - eslint (lint)
      - tsc --noEmit (type check)
      - vitest run (unit)

  e2e:
    needs: [backend, frontend]
    steps:
      - docker-compose up
      - playwright test

  smoke:
    needs: [backend]
    if: github.ref == 'refs/heads/main'
    steps:
      - 6종 건물 × 1month 스모크 테스트
```

---

## 7. 테스트 Fixtures 경로

```
tests/
├── fixtures/
│   ├── bps/                    # 샘플 BPS JSON (건물유형별)
│   │   ├── large_office.json
│   │   ├── medium_office.json
│   │   └── ...
│   ├── idf/                    # 검증된 IDF 파일
│   ├── results/                # Ground truth CSV
│   └── invalid/                # 유효하지 않은 입력 샘플
├── unit/
├── integration/
└── conftest.py
```
