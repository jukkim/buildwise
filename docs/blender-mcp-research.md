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

---

## 프로시저럴 건축 고급 기법 (2026-05-05 검증)

v1~v4 반복 개발을 통해 검증한 Blender Python/BMesh 기반 프로시저럴 건축 기법.

### 포토리얼리즘 핵심 8기법

| # | 기법 | API | 품질 영향 | 비고 |
|---|------|-----|----------|------|
| 1 | **True Displacement** | `mat.cycles.displacement_method = 'BOTH'` + ShaderNodeDisplacement | 극대 | EXPERIMENTAL feature set 필요. Bump만으로는 실루엣 변형 불가 |
| 2 | **Weathering 시스템** | Normal Z축(이끼) + AO(먼지) + Wave(빗물) + Height(풍화) | 극대 | 깨끗한 표면 = CG 느낌의 최대 원인 |
| 3 | **Caustics** | `cycles.caustics_refractive = True` + transmission_bounces 16 | 높음 | 스테인드글라스 god rays에 필수 |
| 4 | **Multi-scale Roughness** | MapRange로 노이즈→거칠기 변환 (0.55~0.92 범위) | 높음 | 균일한 거칠기 = 플라스틱 느낌 |
| 5 | **Triple Bump Chain** | 3개 Bump 노드 직렬 (macro→meso→micro) | 중상 | Normal 입력을 체이닝 |
| 6 | **Volumetric Atmosphere** | VolumeScatter(density 0.003, anisotropy 0.7) + VolumeAbsorption | 극대 | 빈 공기 vs 먼지 가득한 성당 |
| 7 | **AgX 톤매핑** | `view_settings.view_transform = 'AgX'` + Medium High Contrast | 중상 | Filmic 대비 하이라이트 보존 우수 |
| 8 | **높은 Light Path** | diffuse 8, glossy 8, transmission 16, volume 2 | 높음 | 기본값(4)은 인테리어에 부족 |

### 수학적 표면 생성 (가우디 건축)

| 곡면 | 수식 | 건축 용도 |
|------|------|----------|
| 쌍곡면 (Hyperboloid) | `x = r·cosh(z/a)·cos(θ)` | 타워, 기둥 |
| 카테나리 볼트 | `z = h - a·(cosh(x/a) + cosh(y/a) - 2)` | 천장 |
| 쌍곡 포물면 | `z = x·y` | 지붕 패널 |
| 나선면 (Helicoid) | `x = r·cos(t), y = r·sin(t), z = c·t` | 나선 계단 |
| 별형 단면 | `r + A·cos(θ·n)` (n=4→12 변형) | 나무기둥 |

### BMesh 패턴 정리

```python
# 회전 곡면 (타워, 기둥) — 링×세그먼트 그리드
grid = []
for i in range(rings + 1):
    ring = []
    for j in range(segs):
        r = profile_func(i / rings)
        theta = TAU * j / segs + twist_func(i)
        ring.append(bm.verts.new((r*cos(theta)+x, r*sin(theta)+y, z)))
    grid.append(ring)
for i in range(rings):
    for j in range(segs):
        jn = (j + 1) % segs
        bm.faces.new([grid[i][j], grid[i][jn], grid[i+1][jn], grid[i+1][j]])

# 패치 곡면 (볼트, 지붕) — u×v 그리드
grid = []
for i in range(res + 1):
    row = []
    for j in range(res + 1):
        u, v = map_to_domain(i, j, res)
        z = surface_func(u, v)
        row.append(bm.verts.new((u, v, z)))
    grid.append(row)
```

### 셰이더 노드 패턴

```python
# Weathering mask: 면 방향 기반 이끼
geom = N.new("ShaderNodeNewGeometry")
sep = N.new("ShaderNodeSeparateXYZ")
L.new(geom.outputs["Normal"], sep.inputs["Vector"])
# Z > 0.4 = 위를 향하는 면 → 이끼 성장
range_node = N.new("ShaderNodeMapRange")
range_node.inputs["From Min"].default_value = 0.4
range_node.inputs["From Max"].default_value = 0.85
L.new(sep.outputs["Z"], range_node.inputs["Value"])
# 노이즈로 패치 분산
noise = N.new("ShaderNodeTexNoise")
mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
L.new(range_node.outputs["Result"], mul.inputs[0])
L.new(noise.outputs["Fac"], mul.inputs[1])

# AO 기반 먼지 (오목한 부분에 어두운 먼지 축적)
ao = N.new("ShaderNodeAmbientOcclusion")
ao.inputs["Distance"].default_value = 0.8
```

### Blender 4.2 호환성 주의사항

| 이슈 | 해결 |
|------|------|
| `ShaderNodeColorRamp` 없음 | `ShaderNodeValToRGB` 사용 |
| `Subsurface Color` 입력 없음 | 해당 입력 할당 제거 |
| `AgX` look enum 불일치 | try/except로 래핑 |
| `aperture_fvalue` 없음 | `aperture_fstop` 사용 |
| `select.select()` Windows 비호환 | 소켓 직접 사용 시 주의 |
| 50KB+ 코드 전송 시 버퍼 잘림 | 파일 기반 `exec(open(...).read())` 사용 |

### 렌더 설정 권장값 (건축 인테리어)

```python
cycles.samples = 512
cycles.adaptive_threshold = 0.005
cycles.max_bounces = 14
cycles.diffuse_bounces = 8
cycles.transmission_bounces = 16
cycles.volume_bounces = 2
cycles.caustics_refractive = True
cycles.feature_set = 'EXPERIMENTAL'  # displacement용
view_settings.view_transform = 'AgX'
render.resolution_x = 3840  # 4K
```

### 참고 자료 (2026-05-05 조사)

- [IRCSS Procedural Cathedral](https://github.com/IRCSS/Blender-Geometry-Node-French-Houses) — 40,000 GeoNodes로 성당 생성
- [geonodes Python API](https://al1brn.github.io/geonodes/) — Geometry Nodes 파이썬 DSL
- [NodeToPython](https://github.com/BrendanParmer/NodeToPython) — 노드 트리 ↔ 파이썬 변환
- [BMesh Operators](https://docs.blender.org/api/current/bmesh.ops.html)
- [Coding Blender Materials](https://behreajj.medium.com/coding-blender-materials-with-nodes-python-66d950c0bc02)
- [Gaudi Geometry (EscherMath)](https://eschermath.org/wiki/The_Geometry_of_Antoni_Gaudi.html)
