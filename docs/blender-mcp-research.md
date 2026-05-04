# Blender MCP + AI 3D 기술 조사 (2026-05-05)

## 배경

BuildWise Phase 1은 React Three Fiber로 간이 3D 박스 뷰어를 사용 중.
2026년 4월 Anthropic 공식 Blender 커넥터 발표를 계기로 Blender MCP 도입 가능성 조사.

## 핵심 기술: Blender MCP

### 개요

Anthropic이 2026-04-28 발표한 공식 MCP 통합. Claude가 Blender를 자연어로 직접 제어.

### 아키텍처

```
사용자 (자연어)
  → Claude AI (MCP Server)
    → TCP Socket (port 9876)
      → Blender Addon (Python API)
        → 3D 모델 생성/수정
```

- Blender 애드온이 TCP 소켓 오픈
- MCP 서버가 자연어를 Blender Python API 호출로 변환
- JSON 기반 프로토콜: `{type, params}` → `{status, result}`

### 주요 기능

- 자연어 → 3D 오브젝트 생성/수정/삭제
- 머티리얼/색상 적용
- 씬 정보 조회 및 분석
- 배치 작업 (반복 씬 세팅, 재료 일괄 적용)
- 건축 요소/환경을 텍스트나 참조 이미지에서 생성

### 참조

- GitHub: https://github.com/ahujasid/blender-mcp
- 공식: https://www.anthropic.com/news/claude-for-creative-work
- 사이트: https://blender-mcp.com/

## 주요 경쟁 도구 (2026)

| 도구 | 특징 | 장점 | 단점 |
|------|------|------|------|
| **Blender MCP** | Claude ↔ Blender 공식 커넥터 | 자연어 제어, 공식 지원, 오픈소스 | 복잡한 건축 모델은 한계 |
| **3D-Agent** | Blender 네이티브 Text-to-3D | Clean quad topology, MCP 기반 | 유료 |
| **Meshy.ai** | 텍스트/이미지 → 3D + 텍스처 | 빠른 생성, Blender 플러그인 | 웹 기반, triangle mesh |
| **Dream Textures** | Stable Diffusion 텍스처 | 오픈소스, 로컬 실행 | 텍스처만 (모델 생성 불가) |
| **BlenderGPT** | GPT 기반 스크립트 생성 | 범용 자동화 | 3D 모델링 특화 아님 |
| **MyArchitectAI** | 건축 시각화 특화 | 조명/재료/분위기 자동 | Blender 외부 도구 |

## 2026 트렌드

1. **MCP가 표준 프로토콜** — Blender 공식팀도 자연어 입력을 MCP로 탐색 중
2. **Generative mesh** — 텍스트에서 메시 직접 생성
3. **Image-to-3D** 파이프라인 성숙
4. **에셋 제작 시간 60~80% 단축** 보고

## BuildWise 적용 시사점

### 현재 (Phase 1)
- React Three Fiber: 간이 박스 3D 뷰어
- 자연어 → BPS JSON (Claude API) → mock_runner EUI 룩업

### Blender MCP 도입 시 (Phase 2~3 후보)
1. **자연어 → Blender 건축 3D 모델** (간이 뷰어 → 실제 3D)
2. **Blender → IDF 변환** (gbXML/IFC 경유)
3. **결과 시각화 고도화** (Blender 렌더링)
4. **건물 사진 → 3D 역모델링** (Image-to-3D)

### 기술적 고려사항
- Blender는 headless 모드 실행 가능 (서버 백엔드 통합 가능)
- MCP 소켓 기반이라 Docker 컨테이너에서도 작동
- 건축 모델의 정확도/디테일 수준은 추가 검증 필요
- IDF 변환 파이프라인 (Blender → gbXML → IDF) 구축 필요
