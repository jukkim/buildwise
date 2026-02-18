# BuildWise MVP 범위 재조정

> **작성일**: 2026-02-18
> **원본**: SPEC_v0.2.md Phase 1 (8~12주)
> **조정**: 16주 현실적 타임라인

---

## 1. 왜 조정이 필요한가

| 원래 계획의 문제 | 영향 |
|----------------|------|
| BPS→IDF 변환기를 2주 배정 | 실제 4~6주 필요 (6종 건물 × HVAC 다형성) |
| Auth0 + 과금을 마지막 2주에 배치 | 버퍼 제로, 지연 시 MVP 출시 불가 |
| base_template.idf 5종 미존재 | DOE IDF 다운로드 + 한국 기후 적응 필요 |
| WebSocket 진행률 구현 복잡 | E+에 진행률 API 없음, stdout 파싱 필요 |
| 테스트 전략 부재 | 릴리스 품질 보증 불가 |

---

## 2. 조정된 타임라인 (16주)

### Phase 1a: 기반 (Week 1~4)

| 주차 | 작업 | 산출물 |
|------|------|--------|
| **1** | 개발 환경 셋업, Git repo, CI/CD, Docker Compose, Auth0 기본 통합 | 로컬 개발 환경 가동, Auth0 로그인 |
| **2** | DB 스키마 마이그레이션 (Alembic), BPS Pydantic 모델, API 뼈대 (FastAPI) | DB 가동, /health + /auth/me API |
| **3** | 건물 템플릿 6종 BPS 기본값 정의, 템플릿 API (`GET /buildings/templates`) | 6종 템플릿 반환 API |
| **4** | base_template.idf 6종 준비 (DOE Reference → 한국 기후 적용) | 6개 IDF 파일 검증 완료 |

### Phase 1b: IDF 파이프라인 (Week 5~9)

| 주차 | 작업 | 산출물 |
|------|------|--------|
| **5** | IDF 파이프라인 Stage 1~3 (BPS 검증, 템플릿 선택, 파라미터 수정) | BPS→IDF 기본 변환 |
| **6** | IDF 파이프라인 Stage 4 (스케줄 생성) + eppy 통합 | 스케줄 반영된 IDF |
| **7** | IDF 파이프라인 Stage 5 (EMS 주입) - M0~M3 우선 | 4개 전략 IDF 생성 |
| **8** | EMS 주입 M4~M8 + 건물유형별 변형 | 전체 전략 IDF 생성 |
| **9** | IDF 검증 (Stage 7) + 스모크 테스트 (6종 × baseline) | 파이프라인 안정화 |

### Phase 1c: 시뮬레이션 (Week 10~11)

| 주차 | 작업 | 산출물 |
|------|------|--------|
| **10** | Cloud Run E+ 실행 + Celery 태스크 + 결과 수집 (CSV→DB) | 단일 시뮬레이션 API |
| **11** | GKE Jobs M0~M8 병렬 실행 + SSE 진행률 + 결과 처리 | 전략 비교 API |

### Phase 1d: 프론트엔드 (Week 12~13)

| 주차 | 작업 | 산출물 |
|------|------|--------|
| **12** | 설정 위저드 (5단계) + 템플릿 선택 UI + 간단한 3D 박스 프리뷰 | 위저드 완성 |
| **13** | 결과 대시보드 (비교 테이블 + 4종 핵심 차트 + 필터) | 대시보드 기본 |

### Phase 1e: 마무리 (Week 14~16)

| 주차 | 작업 | 산출물 |
|------|------|--------|
| **14** | Stripe 과금 통합 (Free/Pro), 사용량 제한, 업그레이드 유도 | 과금 작동 |
| **15** | 통합 테스트, E2E 테스트, 버그 수정, 성능 최적화 | 테스트 커버리지 80%+ |
| **16** | 배포, 도메인 연결, SSL, 모니터링, 소프트 런치 | **MVP 릴리스** |

---

## 3. 핵심 단순화 결정

### 3.1 WebSocket → SSE (Server-Sent Events)

| 항목 | WebSocket | SSE |
|------|----------|-----|
| 구현 복잡도 | 높음 (양방향) | 낮음 (단방향) |
| 인프라 | 별도 WS 서버 또는 프록시 | FastAPI 기본 지원 |
| 재연결 | 수동 구현 | 브라우저 자동 |
| 용도 | 실시간 양방향 | 진행률 (서버→클라이언트) |

```python
# FastAPI SSE endpoint
@app.get("/api/v1/simulations/{config_id}/progress")
async def simulation_progress(config_id: UUID):
    async def event_generator():
        while True:
            status = await get_simulation_status(config_id)
            yield f"data: {status.json()}\n\n"
            if status.is_complete:
                break
            await asyncio.sleep(2)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 3.2 3D 뷰어 (MVP 최소화)

- **MVP**: 건물유형별 정적 3D 박스 모델 (Three.js 프리미티브)
  - 층수에 따라 높이 조정
  - 건물유형에 따라 색상/텍스처 변경
  - 회전/줌만 가능
- **Phase 2**: 파라메트릭 3D 빌더 (WWR 슬라이더, 형상 편집)

### 3.3 PDF 내보내기 — MVP 제외

- 대시보드 UI에서 "PDF 내보내기" 버튼은 비활성 + "Pro에서 제공" 배지
- Phase 2에서 구현

### 3.4 차트 — 8종 → 4종 (MVP)

| MVP 포함 | Phase 2 |
|---------|---------|
| 전략 비교 막대 차트 | 시간별 히트맵 |
| 월별 에너지 스택 차트 | Sankey 에너지 흐름도 |
| 부하 지속곡선 | PMV 분포 히스토그램 |
| 산점도 (외기온도 vs 에너지) | ROI 타임라인 |

### 3.5 건물 유형 — 6종 유지 (Hospital은 Phase 2)

MVP: 5종 (Large Office, Medium Office, Small Office, Retail, School)
Hospital: base_template.idf 부재 + 24h 운영 스케줄 복잡 → Phase 2

---

## 4. 마일스톤 & 게이트

| 마일스톤 | 주차 | 게이트 기준 |
|---------|------|-----------|
| **M1: 환경 완성** | Week 2 | DB 가동, API 응답, Auth0 로그인 성공 |
| **M2: IDF 생성** | Week 9 | 5종 건물 × baseline IDF → E+ Severe Error 0 |
| **M3: 시뮬레이션** | Week 11 | 5종 × M0~M8 시뮬레이션 → 결과 DB 저장 |
| **M4: UI 완성** | Week 13 | 설정 위저드 + 대시보드 E2E 통과 |
| **M5: MVP 릴리스** | Week 16 | 과금 + 테스트 + 배포 완료 |

---

## 5. 비용 재추정 (현실적)

| 항목 | 원래 추정 | 재추정 | 비고 |
|------|---------|-------|------|
| Cloud Run (E+) | $90/월 | $120/월 | 콜드스타트 + 재시도 비용 |
| Cloud SQL | $50/월 | $70/월 | TimescaleDB 메모리 요구 |
| GCS | $10/월 | $15/월 | IDF + 결과 파일 |
| Redis | $30/월 | $30/월 | 동일 |
| Auth0 | $0/월 | $23/월 | Essential plan 필요 |
| Stripe | $0/월 | $0/월 | 거래 수수료만 |
| 도메인 + SSL | $15/월 | $15/월 | 동일 |
| CI/CD (GitHub Actions) | - | $0/월 | Free tier 충분 |
| **합계 (MVP)** | **$250** | **$273/월** | +9% |
| **손익분기** | Pro 4명 | **Pro 4명** ($79×4=$316) | 동일 |
