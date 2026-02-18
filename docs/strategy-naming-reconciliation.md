# BuildWise EMS 전략 명칭 통합 문서

> **문서 상태**: APPROVED
> **작성일**: 2026-02-18
> **목적**: 세 가지 전략 명명 체계를 통합하여 BuildWise 공식 명칭 확정

---

## 1. 문제: 세 가지 명명 체계 충돌

BuildWise는 기존 `energyplus_sim/` 프로젝트의 자산을 재사용하는데, 해당 프로젝트에 **두 가지 독립적인 전략 체계**가 존재하며, SPEC v0.2에서 **세 번째 체계**를 정의했다.

### 체계 A: fair_comparison_baseline.yaml (스케줄 기반)
설정온도/스케줄 조정만으로 구현. EMS 코드 불필요 (M7, M8 제외).

| 코드 | 설명 | EMS |
|------|------|-----|
| M0 | Baseline - 고정 설정온도 20/24C | No |
| M1 | 재실 난방 -1C (20->19C) | No |
| M2 | 재실 냉방 +0.5C (24->24.5C) | No |
| M3 | M1과 동일 (INV-004) | No |
| M4 | Setback 강화 (난방14C, 냉방30C) | No |
| M5 | 토요일 단축 (09:00-13:00) | No |
| M6 | M1+M2+M4+M5 통합 | No |
| M7 | 최적 기동/정지 (EMS) | Yes |
| M8 | 엔탈피 이코노마이저 | No* |

### 체계 B: master_taxonomy.yaml (EMS 제어 기반)
고급 EMS 프로그램으로 구현. 건물유형별 변형 존재.

| 코드 | 설명 | 적용 건물 |
|------|------|----------|
| M1 | Baseline (EMS 미적용) | 전체 |
| M2 | Night Ventilation (야간 외기 축냉) | Large Office |
| M3 | Optimal Start (최적 기동) | 전체 |
| M4 | Peak Limiting (피크 전력 제한) | Large/Medium/Retail |
| M5 | 건물별 특화 (Economizer/Daylighting/DCV) | 전체 (변형) |
| M6 | Chiller Staging (냉동기 대수제어) | Large/School |
| M7 | Full MPC (통합 예측 제어) | 전체 (조합) |

### 체계 C: SPEC v0.2 (사용자 UI)
BuildWise 제품에서 사용자에게 보여줄 이름.

| 코드 | 사용자 이름 | 설명 |
|------|-----------|------|
| M0 | 야간 정지 | 퇴근 후 HVAC 자동 정지 |
| M1 | 스마트 시작 | 기온에 따라 출근 전 예열/예냉 |
| M2 | 외기 냉방 | 외기가 시원할 때 자연 환기 활용 |
| M3 | 냉동기 단계제어 | 부하에 맞게 냉동기 대수 조절 |
| M4 | 쾌적 최적화 (보통) | PMV 0.5 기준 설정온도 자동 조정 |
| M5 | 쾌적 최적화 (절약) | PMV 0.7 기준 더 넓은 허용 범위 |
| M6 | 설비 통합제어 | M2+M3 복합 적용 |
| M7 | 통합+쾌적(보통) | M6+M4 최적 조합 |
| M8 | 통합+쾌적(절약) | M6+M5 최대 절감 |

---

## 2. 결정: BuildWise 통합 명명

### 2.1 공식 명칭 = SPEC v0.2 (체계 C) 채택

BuildWise는 사용자 제품이므로 **SPEC v0.2의 명칭을 공식(canonical)으로 사용**한다.

### 2.2 내부 구현 매핑

BuildWise의 M0~M8은 `master_taxonomy.yaml`(체계 B)의 EMS 전략에 매핑된다. `fair_comparison_baseline.yaml`(체계 A)은 공정비교 프레임워크로만 사용한다.

| BuildWise | 내부 코드 | 매핑 대상 (체계 B) | EMS 템플릿 | 비고 |
|-----------|----------|-------------------|-----------|------|
| **M0** 야간 정지 | `bw_m0_night_stop` | B-M2 Night Ventilation + occupancy_control | `m2_night_ventilation.j2`, `occupancy_control.j2` | HVAC 정지 + 야간 환기 |
| **M1** 스마트 시작 | `bw_m1_smart_start` | B-M3 Optimal Start | `optimal_start.j2`, `optimal_start_vrf.j2` | 건물유형별 변형 |
| **M2** 외기 냉방 | `bw_m2_economizer` | B-M5 건물별 특화 (Economizer variant) | `enthalpy_economizer.j2` | Large Office/School |
| **M3** 냉동기 단계제어 | `bw_m3_chiller_staging` | B-M6 Chiller Staging | `staging_control.j2` | Large Office/School |
| **M4** 쾌적 최적화(보통) | `bw_m4_pmv_normal` | B-M4 Peak Limiting + PMV setpoint | `m4_peak_limiting.j2`, `setpoint_adjustment.j2` | PMV 0.5 |
| **M5** 쾌적 최적화(절약) | `bw_m5_pmv_savings` | B-M4 Peak Limiting + PMV setpoint | `m4_peak_limiting.j2`, `setpoint_adjustment.j2` | PMV 0.7 |
| **M6** 설비 통합제어 | `bw_m6_integrated` | B-M2 + B-M6 조합 | M2+M3 템플릿 조합 | 경제기+대수제어 |
| **M7** 통합+쾌적(보통) | `bw_m7_full_normal` | B-M7 Full MPC (PMV 0.5) | `vrf_full_control.j2` 등 | M6+M4 |
| **M8** 통합+쾌적(절약) | `bw_m8_full_savings` | B-M7 Full MPC (PMV 0.7) | `vrf_full_control.j2` 등 | M6+M5 |

### 2.3 공정비교 프레임워크 (체계 A) 활용

`fair_comparison_baseline.yaml`의 체계 A는 **BuildWise의 전략이 아니라**, BuildWise 내부의 공정비교 검증에 사용한다:

- **INV-009**: M0 autosize 결과를 M1~M8에 고정
- **설비 크기 잠금**: M0에서 산출된 설비 용량을 모든 전략에 동일 적용
- **스케줄 일관성**: 동일 재실/비재실 스케줄 보장
- **DataCenter 부하**: 고정 계수 적용

### 2.4 건물유형별 적용 가능성 (최종)

| 전략 | Large Office | Medium Office | Small Office | Retail | School |
|------|:-----------:|:------------:|:-----------:|:------:|:------:|
| M0 야간정지 | O | O* | O* | O* | O |
| M1 스마트시작 | O | O (VRF) | O (PSZ) | O (PSZ) | O |
| M2 외기냉방 | O | - | O (PSZ) | O (PSZ) | O |
| M3 냉동기단계 | O | - | - | - | O |
| M4 쾌적(보통) | O | O | O | O | O |
| M5 쾌적(절약) | O | O | O | O | O |
| M6 통합제어 | O | - | - | - | O |
| M7 통합+쾌적(보통) | O | O** | O** | O** | O |
| M8 통합+쾌적(절약) | O | O** | O** | O** | O |

- `O*`: AHU 없는 건물은 야간 환기 대신 야간 HVAC 정지만 적용
- `O**`: 건물유형별 적용 가능 전략만 조합 (예: VRF는 M1+M4+M5)

---

## 3. 코드 구현 가이드

### 3.1 전략 Enum (Backend)

```python
class BuildWiseStrategy(str, Enum):
    BASELINE = "baseline"
    M0_NIGHT_STOP = "m0"
    M1_SMART_START = "m1"
    M2_ECONOMIZER = "m2"
    M3_CHILLER_STAGING = "m3"
    M4_PMV_NORMAL = "m4"
    M5_PMV_SAVINGS = "m5"
    M6_INTEGRATED = "m6"
    M7_FULL_NORMAL = "m7"
    M8_FULL_SAVINGS = "m8"
```

### 3.2 전략 → 템플릿 매핑 (서비스 레이어)

```python
STRATEGY_TEMPLATE_MAP = {
    "m0": {
        "large_office": ["m2_night_ventilation.j2", "occupancy_control.j2"],
        "medium_office": ["vrf_night_setback.j2"],
        "small_office": ["occupancy_control.j2"],
        "standalone_retail": ["occupancy_control.j2"],
        "primary_school": ["m2_night_ventilation.j2", "occupancy_control.j2"],
    },
    "m1": {
        "large_office": ["optimal_start.j2"],
        "medium_office": ["optimal_start_vrf_v2.j2"],
        "small_office": ["optimal_start_stop.j2"],
        "standalone_retail": ["optimal_start_stop.j2"],
        "primary_school": ["optimal_start.j2"],
    },
    "m2": {
        "large_office": ["enthalpy_economizer.j2"],
        "small_office": ["enthalpy_economizer.j2"],
        "standalone_retail": ["enthalpy_economizer.j2"],
        "primary_school": ["enthalpy_economizer.j2"],
    },
    "m3": {
        "large_office": ["staging_control.j2"],
        "primary_school": ["staging_control.j2"],
    },
    "m4": {
        "*": ["m4_peak_limiting.j2", "setpoint_adjustment.j2"],
    },
    "m5": {
        "*": ["m4_peak_limiting.j2", "setpoint_adjustment.j2"],
    },
    "m6": {
        "large_office": ["enthalpy_economizer.j2", "staging_control.j2"],
        "primary_school": ["enthalpy_economizer.j2", "staging_control.j2"],
    },
    "m7": {
        "large_office": ["enthalpy_economizer.j2", "staging_control.j2", "m4_peak_limiting.j2", "setpoint_adjustment.j2"],
        "medium_office": ["vrf_full_control.j2", "setpoint_adjustment.j2"],
        "small_office": ["optimal_start_stop.j2", "setpoint_adjustment.j2"],
        "standalone_retail": ["optimal_start_stop.j2", "m4_peak_limiting.j2", "setpoint_adjustment.j2"],
        "primary_school": ["enthalpy_economizer.j2", "staging_control.j2", "setpoint_adjustment.j2"],
    },
    "m8": {
        "large_office": ["enthalpy_economizer.j2", "staging_control.j2", "m4_peak_limiting.j2", "setpoint_adjustment.j2"],
        "medium_office": ["vrf_full_control.j2", "setpoint_adjustment.j2"],
        "small_office": ["optimal_start_stop.j2", "setpoint_adjustment.j2"],
        "standalone_retail": ["optimal_start_stop.j2", "m4_peak_limiting.j2", "setpoint_adjustment.j2"],
        "primary_school": ["enthalpy_economizer.j2", "staging_control.j2", "setpoint_adjustment.j2"],
    },
}
```

### 3.3 PMV 파라미터 차이 (M4 vs M5)

| 파라미터 | M4 (보통) | M5 (절약) |
|---------|----------|----------|
| PMV 목표 | +/-0.5 | +/-0.7 |
| 냉방 설정온도 범위 | 23~25C | 22~26C |
| 난방 설정온도 범위 | 19~21C | 18~22C |
| cooling_sp_adjustment | +1.0C | +2.0C |
| heating_sp_adjustment | -1.0C | -2.0C |

---

## 4. fair_comparison_baseline.yaml 내부 전략 ↔ BuildWise 전략 교차 참조

BuildWise의 시뮬레이션 실행 시, 공정비교를 보장하기 위해 `fair_comparison_baseline.yaml`의 불변 원칙을 적용한다. 그러나 전략 코드는 다르므로 다음 매핑을 사용한다:

| 공정비교 원칙 | BuildWise 적용 방식 |
|-------------|------------------|
| M0 autosize → M1~M8 설비 고정 | BASELINE autosize → M0~M8 설비 고정 |
| 동일 건물/기후/타임스텝 | 동일 BPS + SimulationConfig 사용 |
| 동일 재실 스케줄 | BPS schedules 고정 |
| DataCenter 부하 고정 | BPS internal_loads 고정 |
| 설비 크기 허용 오차 0.1% | IDF validator에서 검증 |
