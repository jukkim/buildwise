# IDF 생성 파이프라인 기술 설계

> **작성일**: 2026-02-18
> **핵심 결정**: MVP는 scratch 생성이 아닌 **base_template.idf 수정 방식**

---

## 1. 아키텍처 개요

```
BPS JSON (사용자 입력)
    │
    ▼
┌─────────────────────────────────────────────┐
│ IDF Generation Pipeline (Python, 서버사이드)  │
│                                              │
│ Stage 1: BPS 검증                            │
│ Stage 2: 템플릿 선택                          │
│ Stage 3: 파라미터 수정                        │
│ Stage 4: 스케줄 생성                          │
│ Stage 5: EMS 주입 (전략별)                    │
│ Stage 6: 출력 변수 설정                       │
│ Stage 7: 최종 검증                            │
└─────────────────────────────────────────────┘
    │
    ▼
model.idf + metadata.json → GCS 업로드 → EnergyPlus 실행
```

---

## 2. MVP 핵심 결정: 템플릿 수정 방식

### 왜 scratch 생성이 아닌가

IDF를 처음부터 생성하려면:
- Zone 기하학 (Surface, Subsurface, 인접 관계) 자동 생성
- HVAC 시스템 배선 (AirLoop, PlantLoop, Branch, Connector)
- 수백 개의 EnergyPlus 객체 간 참조 무결성 보장

이는 **4~6개월** 분량의 작업이며 MVP에 부적합.

### 템플릿 수정 방식

1. 건물 유형별 `base_template.idf` 6개를 미리 준비 (DOE Reference Building 기반)
2. 사용자 BPS에 따라 **파라미터만 수정** (설정온도, 스케줄, 외피 물성 등)
3. 기하학/HVAC 배선은 템플릿 그대로 유지
4. 사용자가 층수/면적을 변경하면 → 가장 가까운 템플릿 선택 + 스케일링 계수 적용

### 제약

- MVP에서 건물 형상 커스터마이징 제한 (6종 템플릿 중 선택)
- 층수 변경 → `floor multiplier` 조정 (실제 기하학 변경 아님)
- Phase 2에서 파라메트릭 기하학 생성 추가

---

## 3. 파이프라인 상세

### Stage 1: BPS 검증

```python
class BPSValidator:
    """BPS JSON을 bps.schema.json 대비 검증 + 물리적 교차검증"""

    def validate(self, bps: dict) -> ValidationResult:
        # 1. JSON Schema 검증 (jsonschema 라이브러리)
        # 2. 도시 → 기후대 자동 매핑 검증
        # 3. 건물유형 → HVAC 타입 호환성 (large_office ↔ vav_chiller_boiler)
        # 4. 설정온도 범위 (cooling > heating)
        # 5. WWR 범위 (0~0.95)
        # 6. 전략 적용 가능성 (strategy_applicability 매트릭스)
```

**입력**: BPS JSON
**출력**: `ValidationResult` (pass/fail + error list)
**소스 재사용**: `energyplus_sim/validation/invariants.py`

### Stage 2: 템플릿 선택

```python
TEMPLATE_MAP = {
    "large_office": "building_templates/large_office/base_template.idf",
    "medium_office": "building_templates/medium_office/base_template.idf",
    "small_office": "building_templates/small_office/base_template.idf",
    "standalone_retail": "building_templates/standalone_retail/base_template.idf",
    "primary_school": "building_templates/primary_school/base_template.idf",
    "hospital": "building_templates/hospital/base_template.idf",
}
```

**현재 상태**: `medium_office` 템플릿만 존재 (`energyplus_sim/buildings/medium_office_backup/base_template.idf`)
**TODO**: 나머지 5종 생성 필요 (DOE Reference Building IDF 다운로드 → 한국 기후 적용)

**라이브러리**: `eppy` (Python EnergyPlus IDF 파서/에디터)

### Stage 3: 파라미터 수정

```python
class ParameterModifier:
    """base_template.idf의 파라미터를 BPS 값으로 수정"""

    def modify(self, idf, bps: dict) -> IDF:
        # 1. RunPeriod 설정 (1year / 1month 등)
        self._set_run_period(idf, bps["simulation"]["period"])

        # 2. Location 설정 (Site:Location, WeatherFile)
        self._set_location(idf, bps["location"])

        # 3. 설정온도 수정
        self._set_thermostat(idf, bps["setpoints"])

        # 4. 외피 물성 수정 (U-value → Material 두께/전도율 역산)
        self._set_envelope(idf, bps["envelope"])

        # 5. 내부 부하 수정 (조명/기기/인원 밀도)
        self._set_internal_loads(idf, bps.get("internal_loads", {}))

        # 6. WWR 수정 (FenestrationSurface:Detailed 크기 조정)
        self._set_wwr(idf, bps["geometry"].get("wwr"))

        # 7. 층 승수 (Building:Zone 의 Multiplier)
        self._set_floor_multiplier(idf, bps["geometry"])

        return idf
```

**핵심**: `eppy`의 `IDF` 객체를 통해 개별 필드 수정. 참조 무결성은 템플릿이 보장.

### Stage 4: 스케줄 생성

```python
class ScheduleGenerator:
    """BPS schedules → EnergyPlus Schedule:Compact 객체"""

    def generate(self, idf, bps: dict) -> IDF:
        schedules = bps.get("schedules", {})

        # 1. 재실 스케줄 (operating_hours, workdays, saturday)
        self._set_occupancy_schedule(idf, schedules)

        # 2. 설정온도 스케줄 (occupied/unoccupied 전환)
        self._set_thermostat_schedule(idf, bps["setpoints"], schedules)

        # 3. 조명/기기 스케줄 (operating_hours 기반)
        self._set_lighting_schedule(idf, schedules)

        # 4. 공휴일 (KR_standard: 한국 법정 공휴일)
        if schedules.get("holidays") == "KR_standard":
            self._add_korean_holidays(idf)

        return idf
```

**소스 재사용**: `energyplus_sim/config/schedule_templates.yaml` 참조

### Stage 5: EMS 주입 (전략별)

```python
class EMSInjector:
    """BuildWise 전략 → Jinja2 EMS 템플릿 렌더링 → IDF 삽입"""

    def inject(self, idf, strategy: str, bps: dict) -> IDF:
        building_type = bps["geometry"]["building_type"]

        # 1. 전략→템플릿 매핑 조회
        templates = STRATEGY_TEMPLATE_MAP[strategy].get(
            building_type,
            STRATEGY_TEMPLATE_MAP[strategy].get("*", [])
        )

        if not templates:
            raise StrategyNotApplicable(strategy, building_type)

        # 2. 템플릿 변수 준비 (건물/HVAC 파라미터에서 추출)
        context = self._build_template_context(bps)

        # 3. Jinja2 렌더링
        for template_name in templates:
            ems_code = self._render_template(template_name, context)
            self._append_ems_to_idf(idf, ems_code)

        # 4. 공정비교 조건 적용
        self._apply_fair_comparison(idf, strategy)

        return idf

    def _build_template_context(self, bps: dict) -> dict:
        """BPS에서 EMS 템플릿이 필요로 하는 변수 추출"""
        return {
            # 존 이름 목록 (템플릿이 반복문에 사용)
            "zones": self._get_zone_names(bps),
            # AHU/AirLoop 이름
            "airloops": self._get_airloop_names(bps),
            # Chiller 이름 목록
            "chillers": self._get_chiller_names(bps),
            # 설정온도
            "cooling_setpoint": bps["setpoints"]["cooling_occupied"],
            "heating_setpoint": bps["setpoints"]["heating_occupied"],
            # PMV 파라미터 (M4/M5)
            "pmv_target": self._get_pmv_target(bps),
            # 운영 시간
            "occupied_start": bps["schedules"]["operating_hours"]["start"],
            "occupied_end": bps["schedules"]["operating_hours"]["end"],
        }
```

**소스 재사용**: `energyplus_sim/ems_templates/*.j2` 15개 전체

### Stage 6: 출력 변수 설정

```python
STANDARD_OUTPUT_VARIABLES = [
    # 전체 에너지
    ("Facility Total Electric Demand Power", "Timestep"),
    ("Facility Total HVAC Electric Demand Power", "Timestep"),
    # 냉방
    ("Cooling Coil Electricity Energy", "Timestep"),
    ("Chiller Electricity Energy", "Timestep"),
    # 난방
    ("Boiler NaturalGas Energy", "Timestep"),
    ("Heating Coil Electricity Energy", "Timestep"),
    # 팬/펌프
    ("Fan Electricity Energy", "Timestep"),
    ("Pump Electricity Energy", "Timestep"),
    # 쾌적성
    ("Zone Mean Air Temperature", "Timestep"),
    ("Zone Operative Temperature", "Timestep"),
]

# Output:Meter
STANDARD_METERS = [
    ("Electricity:Facility", "Monthly"),
    ("Electricity:HVAC", "Monthly"),
    ("NaturalGas:Facility", "Monthly"),
]
```

### Stage 7: 최종 검증

```python
class IDFValidator:
    """생성된 IDF의 구조적 무결성 검증"""

    def validate(self, idf, strategy: str) -> ValidationResult:
        errors = []

        # 1. RunPeriod 존재 확인
        # 2. Zone 참조 무결성 (Surface→Zone 매핑)
        # 3. HVAC 노드 연결 확인
        # 4. EMS 객체 존재/부재 (baseline은 EMS 없어야 함)
        # 5. Schedule 참조 누락 확인
        # 6. Output:Variable 존재 확인

        # 공정비교 검증 (M0~M8)
        if strategy != "baseline":
            # 설비 크기가 baseline과 동일한지 확인
            errors += self._verify_equipment_sizing(idf)

        return ValidationResult(errors=errors)
```

**소스 재사용**: `energyplus_sim/validation/idf_validator.py`

---

## 4. 파이프라인 전체 흐름 (코드 레벨)

```python
class IDFGenerationPipeline:
    """BPS → IDF 변환 파이프라인"""

    def __init__(self):
        self.bps_validator = BPSValidator()
        self.param_modifier = ParameterModifier()
        self.schedule_gen = ScheduleGenerator()
        self.ems_injector = EMSInjector()
        self.idf_validator = IDFValidator()

    def generate(self, bps: dict, strategy: str = "baseline") -> PipelineResult:
        # Stage 1: BPS 검증
        validation = self.bps_validator.validate(bps)
        if not validation.is_valid:
            return PipelineResult(error=validation.errors)

        # Stage 2: 템플릿 선택
        building_type = bps["geometry"]["building_type"]
        idf = self._load_template(building_type)

        # Stage 3: 파라미터 수정
        idf = self.param_modifier.modify(idf, bps)

        # Stage 4: 스케줄 생성
        idf = self.schedule_gen.generate(idf, bps)

        # Stage 5: EMS 주입 (baseline 이외)
        if strategy != "baseline":
            idf = self.ems_injector.inject(idf, strategy, bps)

        # Stage 6: 출력 변수
        self._add_output_variables(idf)

        # Stage 7: 최종 검증
        validation = self.idf_validator.validate(idf, strategy)
        if not validation.is_valid:
            return PipelineResult(error=validation.errors)

        # IDF 저장 + 메타데이터
        idf_path = self._save_idf(idf, bps, strategy)
        metadata = self._create_metadata(idf_path, bps, strategy)

        return PipelineResult(idf_path=idf_path, metadata=metadata)
```

---

## 5. 리스크 레지스터

| # | 리스크 | 심각도 | 완화 방법 |
|---|-------|-------|---------|
| R1 | base_template.idf가 5종 부족 | HIGH | DOE Reference Building IDF 다운로드 → 한국 기후 적응 (2주 작업) |
| R2 | WWR 수정 시 FenestrationSurface 좌표 계산 복잡 | MEDIUM | MVP에서 WWR 수정 범위 제한 (템플릿 기본값 ±20%) |
| R3 | HVAC 배선 건물유형별 완전히 다름 | HIGH | 템플릿 방식이므로 배선 변경 없음. 용량만 조정 |
| R4 | EMS 템플릿의 Zone/AirLoop 이름이 건물마다 다름 | MEDIUM | context 변수로 동적 치환 (Jinja2 반복문) |
| R5 | eppy 라이브러리의 EMS 객체 지원 제한적 | LOW | raw text 삽입 방식으로 우회 가능 |
| R6 | Floor multiplier 적용 시 결과 선형성 가정 | LOW | MVP 허용 범위 내에서 충분히 정확 |

---

## 6. 필요 라이브러리

| 라이브러리 | 버전 | 용도 |
|----------|------|------|
| `eppy` | 0.5.63+ | IDF 파싱/수정 |
| `jinja2` | 3.1+ | EMS 템플릿 렌더링 |
| `jsonschema` | 4.20+ | BPS JSON Schema 검증 |
| `pyyaml` | 6.0+ | YAML 설정 파일 로딩 |

---

## 7. 디렉토리 구조 (백엔드)

```
buildwise-backend/app/services/idf/
├── __init__.py
├── pipeline.py            # IDFGenerationPipeline (메인 진입점)
├── bps_validator.py       # Stage 1
├── parameter_modifier.py  # Stage 3
├── schedule_generator.py  # Stage 4
├── ems_injector.py        # Stage 5
├── idf_validator.py       # Stage 7
└── utils.py               # 공통 유틸리티
```
