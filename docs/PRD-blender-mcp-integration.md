# PRD: Blender MCP 기반 3D 건물 생성 통합

> **문서 상태**: DRAFT
> **작성일**: 2026-05-05
> **대상 Phase**: Phase 2 (SPEC v0.2 §4.1.2 "복잡 형상 15%" + "고급 5%" 구현)
> **선행 조건**: Phase 1 MVP 완성 (mock_runner, BPS 폼, 결과 대시보드)

---

## 1. 목적

Phase 1 MVP는 DOE 템플릿 6종 선택 + React Three Fiber 박스 뷰어로 동작한다.
사용자의 자연어 입력을 실제 건축 3D 모델로 변환하는 기능이 빠져 있어, SPEC v0.2 §1의
"자연어로 건물을 설명하면, AI가 3D 모델을 만들고" 비전을 실현하지 못한다.

2026-04-28 Anthropic 공식 Blender MCP 커넥터 출시로, Claude가 Blender Python API를
자연어로 직접 제어할 수 있게 되었다. 이를 활용하여 **자연어 → 3D 건축 모델 → IDF** 파이프라인을 구축한다.

## 2. 사용자 스토리

### P1 건물주 (비전문가)
> "서울 강남에 있는 12층 유리 커튼월 오피스" → 실제 건물처럼 생긴 3D 모델이 화면에 나타나고,
> 각 층의 용도/면적/창호가 자동 설정되어 바로 시뮬레이션 가능.

### P2 시설관리자 (준전문가)
> 3D 모델에서 층/존을 클릭하면 해당 구역의 HVAC/설정온도를 개별 조정 가능.

### P3 에너지 컨설턴트 (전문가)
> 고객 건물 사진을 올리면 AI가 3D 역모델링 → IDF 생성 → 보고서까지 자동.

## 3. 기능 범위

### 3.1 Phase 2A — Blender MCP 백엔드 통합 (핵심)

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|----------|
| F1 | 자연어 → 3D 건축 모델 | Claude MCP로 Blender에 건물 생성 명령 | P0 |
| F2 | BPS → Blender 파라메트릭 생성 | BPS JSON의 층수/면적/WWR로 자동 모델링 | P0 |
| F3 | Blender → glTF 변환 | 생성된 모델을 glTF/glb로 export → 프론트 뷰어 | P0 |
| F4 | Blender → IDF 변환 | gbXML 또는 직접 zone 매핑으로 IDF 생성 | P0 |
| F5 | 모델 수정 (자연어) | "창호비를 60%로 바꿔" → Blender 모델 업데이트 | P1 |
| F6 | 존 시각화 | 열 구역(zone) 컬러 맵 + 클릭 인터랙션 | P1 |

### 3.2 Phase 2B — 이미지 기반 (후속)

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|----------|
| F7 | 건물 사진 → 3D | Vision AI로 형상 추정 → Blender 모델링 | P2 |
| F8 | 도면 PDF → 3D | 평면도 OCR + zone 추출 → 모델 생성 | P2 |
| F9 | IFC/gbXML 임포트 | BIM 모델 직접 임포트 → IDF 변환 | P2 |

## 4. 비기능 요구사항

| 항목 | 기준 |
|------|------|
| 3D 생성 시간 | 자연어 입력 → 3D 뷰어 표시 ≤ 30초 |
| 동시 생성 | 5명 동시 (Blender 인스턴스 풀) |
| 모델 정확도 | DOE 레퍼런스 대비 면적 ±10%, 층수 정확 |
| IDF 유효성 | EnergyPlus 24.1 에러 없이 시뮬 실행 가능 |
| 가용성 | Blender 프로세스 크래시 시 자동 재시작, 타임아웃 60초 |

## 5. 제외 범위

- 실시간 3D 편집 (드래그 앤 드롭으로 벽/창 이동) — Phase 3+
- 인테리어/가구 배치 — 에너지와 무관
- 구조 해석 — 범위 밖
- Blender GUI 노출 (모든 Blender 조작은 headless 서버에서 수행)

## 6. 성공 지표

| 지표 | 목표 |
|------|------|
| 자연어 → 유효 IDF 변환율 | ≥ 85% (수동 보정 없이) |
| 3D 뷰어 렌더링 FPS | ≥ 30 FPS (glTF 기준) |
| 사용자 이탈률 | 건물 생성 단계에서 ≤ 20% (Phase 1 템플릿 대비 비교) |
| 시뮬 결과 정확도 | 수동 IDF 대비 EUI ±15% 이내 |

## 7. 기술 의존성

| 구성요소 | 버전/상태 | 비고 |
|----------|----------|------|
| Blender | 4.x (headless) | Docker 이미지 필요 |
| blender-mcp | ahujasid/blender-mcp | 오픈소스, Apache 2.0 |
| Claude API | MCP tool_use | 기존 nl_parser.py 확장 |
| gbXML → IDF | 변환기 개발 필요 | 또는 eppy 직접 zone 매핑 |
| Three.js glTF Loader | 기존 프론트 확장 | @react-three/drei |

## 8. 리스크

| 리스크 | 영향 | 완화 |
|--------|------|------|
| Blender headless 안정성 | 높음 | 프로세스 풀 + watchdog + 타임아웃 |
| 복잡한 건물 형상 생성 실패 | 중간 | DOE 템플릿 fallback 유지 |
| IDF 변환 시 zone 매핑 오류 | 높음 | 검증기(validator) + 수동 보정 UI |
| Blender Docker 이미지 크기 (2GB+) | 중간 | 별도 컨테이너, 온디맨드 스케일링 |
| MCP 프로토콜 변경 | 낮음 | Anthropic 공식 지원, 안정적 |

## 9. 마일스톤

| 마일스톤 | 산출물 | 예상 기간 |
|----------|--------|----------|
| M1: Blender MCP 연결 PoC | Docker + MCP 소켓 통신 확인 | 1주 |
| M2: BPS → 3D 파라메트릭 생성 | 6종 건물 자동 생성 | 2주 |
| M3: glTF export + 프론트 통합 | 3D 뷰어에 실제 모델 표시 | 1주 |
| M4: 3D → IDF 변환 | zone 매핑 + EnergyPlus 검증 | 2주 |
| M5: 자연어 통합 | NL → BPS → Blender → glTF + IDF 전체 파이프라인 | 1주 |
| M6: 안정화 + 테스트 | 에러 핸들링, 폴백, 성능 테스트 | 1주 |
