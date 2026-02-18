# EMS 전략 매핑: energyplus_sim → BuildWise

> **작성일**: 2026-02-18
> **참조**: `docs/strategy-naming-reconciliation.md` (명칭 통합)

---

## 1. Jinja2 EMS 템플릿 매핑 (15개)

### 소스 경로
`C:\Users\User\Desktop\myjob\energyplus_sim\ems_templates\`

### BuildWise 전략 매핑

| # | 템플릿 파일 | BuildWise 전략 | 건물 유형 | 이관 방법 |
|---|------------|--------------|----------|----------|
| 1 | `m2_night_ventilation.j2` | M0 야간정지 | Large Office, School | 복사 → `energyplus/ems_templates/` |
| 2 | `occupancy_control.j2` | M0 야간정지 | Small/Retail (AHU 없는 건물) | 복사 |
| 3 | `optimal_start.j2` | M1 스마트시작 | Large Office, School (VAV) | 복사 |
| 4 | `optimal_start_vrf.j2` | M1 스마트시작 | Medium Office (VRF) | 복사 |
| 5 | `optimal_start_vrf_v2.j2` | M1 스마트시작 | Medium Office (VRF 개선) | 복사, v2 우선 사용 |
| 6 | `optimal_start_stop.j2` | M1 스마트시작 | Small/Retail (PSZ) | 복사 |
| 7 | `enthalpy_economizer.j2` | M2 외기냉방 | Large/Small/Retail/School | 복사 |
| 8 | `staging_control.j2` | M3 냉동기단계 | Large Office, School | 복사 |
| 9 | `m4_peak_limiting.j2` | M4/M5 쾌적최적화 | 전체 (피크 전력 부분) | 복사 |
| 10 | `setpoint_adjustment.j2` | M4/M5 쾌적최적화 | 전체 (PMV 설정온도 부분) | 복사 |
| 11 | `m5_daylighting.j2` | M2 외기냉방 변형 | Retail (자연채광) | 복사 |
| 12 | `m5_dcv.j2` | M2 외기냉방 변형 | School (CO2 DCV) | 복사 |
| 13 | `vrf_demand_limit.j2` | M4/M5 (VRF 전용) | Medium Office | 복사 |
| 14 | `vrf_full_control.j2` | M7/M8 통합 (VRF) | Medium Office | 복사 |
| 15 | `vrf_night_setback.j2` | M0 야간정지 (VRF) | Medium Office | 복사 |

---

## 2. 설정 파일 매핑

### 소스 경로
`C:\Users\User\Desktop\myjob\energyplus_sim\config\`

| 소스 파일 | BuildWise 대상 | 용도 |
|----------|--------------|------|
| `fair_comparison_baseline.yaml` | `config/fair_comparison.yaml` | 공정비교 불변 원칙 (INV-009), 설비 크기 잠금 |
| `master_taxonomy.yaml` | `config/strategy_definitions.yaml` | 전략 정의, 적용 가능성 매트릭스, HVAC 제약 |
| `building_specific/large_office.yaml` | `config/building_defaults/large_office.yaml` | BPS 기본값, HVAC 스펙, 존 레이아웃 |
| `building_specific/medium_office.yaml` | `config/building_defaults/medium_office.yaml` | VRF 스펙, 실내기/실외기 구성 |
| `building_specific/small_office.yaml` | `config/building_defaults/small_office.yaml` | PSZ-HP 스펙 |
| `building_specific/standalone_retail.yaml` | `config/building_defaults/standalone_retail.yaml` | PSZ-AC 스펙, 높은 천장 |
| `building_specific/primary_school.yaml` | `config/building_defaults/primary_school.yaml` | VAV+Chiller/Boiler, 교실 존 |
| `simulation_standard.yaml` | `config/simulation_standard.yaml` | 기본 시뮬레이션 조건, 출력 변수 |
| `schedule_templates.yaml` | `config/schedule_templates.yaml` | M0~M6 스케줄 정의 |
| `validation_rules.yaml` | `config/validation_rules.yaml` | INV-001~009, 물리 검증 규칙 |

---

## 3. 검증 모듈 매핑

### 소스 경로
`C:\Users\User\Desktop\myjob\energyplus_sim\validation\`

| 소스 파일 | BuildWise 대상 | 기능 |
|----------|--------------|------|
| `physics_validator.py` | `backend/app/services/validation/physics.py` | PHY-001~004: 설정온도-에너지 상관, 계절 패턴, 기후 영향, EMS 효과 |
| `idf_validator.py` | `backend/app/services/validation/idf.py` | IDF 구조 무결성, RunPeriod, EMS 존재/부재 |
| `result_validator.py` | `backend/app/services/validation/results.py` | CSV 출력 검증, 값 범위, 단위 |
| `invariants.py` | `backend/app/services/validation/invariants.py` | INV-001~009 불변 규칙 적용 |

---

## 4. 날씨 데이터 매핑

### 소스 경로
`C:\Users\User\Desktop\myjob\energyplus_sim\weather\`

| EPW 파일 | 도시 | 기후대 | GCS 버킷 경로 |
|---------|------|-------|-------------|
| `KOR_Seoul.epw` | Seoul | 4A | `gs://buildwise-weather/KOR_Seoul.epw` |
| `KOR_Busan.epw` | Busan | 3A | `gs://buildwise-weather/KOR_Busan.epw` |
| `KOR_Daegu.epw` | Daegu | 4A | `gs://buildwise-weather/KOR_Daegu.epw` |
| `KOR_Daejeon.epw` | Daejeon | 4A | `gs://buildwise-weather/KOR_Daejeon.epw` |
| `KOR_Gwangju.epw` | Gwangju | 4A | `gs://buildwise-weather/KOR_Gwangju.epw` |
| `KOR_Incheon.epw` | Incheon | 4A | `gs://buildwise-weather/KOR_Incheon.epw` |
| `KOR_Gangneung.epw` | Gangneung | 4A | `gs://buildwise-weather/KOR_Gangneung.epw` |
| `KOR_Jeju.epw` | Jeju | 3A | `gs://buildwise-weather/KOR_Jeju.epw` |
| `KOR_Cheongju.epw` | Cheongju | 4A | `gs://buildwise-weather/KOR_Cheongju.epw` |
| `KOR_Ulsan.epw` | Ulsan | 4A | `gs://buildwise-weather/KOR_Ulsan.epw` |

---

## 5. Ground Truth 데이터 (검증용)

| 소스 | 용도 |
|------|------|
| `buildings/*/results/default/*/1year/m0~m8/` | 450+ 시뮬레이션 결과 → regression 테스트 oracle |
| `analysis/10city_results_all_v3.csv` | 10도시 전체 결과 요약 → AI 추천 학습 데이터 |
| `analysis/expert_review_report.md` | 전문가 검증 보고서 → 도메인 지식 |

---

## 6. 이관 실행 체크리스트

- [ ] `ems_templates/` 15개 파일 → `buildwise/energyplus/ems_templates/` 복사
- [ ] `config/building_specific/` 5개 파일 → `buildwise/config/building_defaults/` 복사
- [ ] `config/fair_comparison_baseline.yaml` → `buildwise/config/` 복사
- [ ] `config/master_taxonomy.yaml` → `buildwise/config/` 복사
- [ ] `config/validation_rules.yaml` → `buildwise/config/` 복사
- [ ] `config/simulation_standard.yaml` → `buildwise/config/` 복사
- [ ] `config/schedule_templates.yaml` → `buildwise/config/` 복사
- [ ] `validation/*.py` 4개 파일 → `buildwise/backend/app/services/validation/` 이관+리팩토링
- [ ] `weather/KOR_*.epw` 10개 파일 → GCS 버킷 업로드
- [ ] `analysis/10city_results_all_v3.csv` → 테스트 fixtures 변환
