# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: BuildWise

건물 에너지 시뮬레이션 SaaS 플랫폼. 자연어 입력 → 3D 건물 생성 → EnergyPlus 시뮬레이션 → EMS 전략(M0~M8) 비교 → 결과 분석 대시보드.

- **제품명**: BuildWise (buildwise.ai)
- **대상 사용자**: 비전문가(건물주) ~ 전문가(에너지 컨설턴트)
- **상태**: 기획 완료 (SPEC_v0.2.md), Phase 1 MVP 개발 대기

## Architecture

```
Frontend: React 19 + TypeScript + React Three Fiber + Recharts
Backend:  FastAPI + Celery + Redis
Infra:    GCP (Cloud Run + GKE + Cloud SQL + GCS)
Engine:   EnergyPlus 24.1+ (Docker 컨테이너)
AI:       Claude API (자연어), Gemini Pro Vision (사진)
3D:       Three.js 주력(80%) + Blender headless 보조(5%)
```

## Key Design Decisions

- **BPS (Building Parameter Schema)**: 전체 시스템의 SSOT. 사용자 수정, 3D 생성, IDF 생성 모두 BPS JSON 기반.
- **3D 하이브리드**: 파라메트릭 건물은 Three.js 프론트엔드에서 즉시 생성 (서버 불필요). Blender는 복잡 형상/임포트 전용.
- **자연어 처리**: 자동채움 + 사후확인 카드 패턴. 질문 최소화로 비전문가 이탈 방지.
- **시뮬레이션**: Cloud Run (단일) + GKE Jobs (M0~M8 병렬 9 Pod). 유휴 비용 $0.
- **과금**: Free($0) / Pro($79/월) / Enterprise(문의). Free에서 M0~M3만 제공 → 업그레이드 유도.
- **기후**: Phase 1은 한국 10도시 (검증 완료 데이터). 단계적 글로벌 확장.

## Spec Document

상세 스펙: `SPEC_v0.2.md` (전체 아키텍처, 모듈 스펙, 과금, 로드맵 포함)

## Related Projects

- `energyplus_sim/` (C:\Users\User\Desktop\myjob\energyplus_sim): 기존 로컬 시뮬레이션 프로젝트. EMS 템플릿, 검증 로직, EPW, 10도시 결과 데이터 재사용 가능.
