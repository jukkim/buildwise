# Blender MCP 프로시저럴 스크립트 카탈로그

BMesh + Shader Nodes로 Blender headless(port 9876)에 전송하는 프로시저럴 건물 생성 스크립트.

## 실행 방법

```bash
cd buildwise-backend

# 일반 스크립트 (< 30KB)
python scripts/send_to_blender.py scripts/<script>.py localhost 9876

# 대용량 스크립트 (> 30KB) — 파일 기반 exec
python scripts/send_large_to_blender.py scripts/<script>.py localhost 9876
```

**사전 조건**: Blender 4.2+가 MCP 서버(port 9876)로 실행 중이어야 함.
- 로컬: Blender 4.2 + MCP 애드온 활성화
- Docker: `docker compose --profile blender up`

## 스크립트 목록

| 스크립트 | 건물 | 오브젝트 | 버텍스 | 재질 | 렌더 | 비고 |
|----------|------|---------|--------|------|------|------|
| `bmesh_hospital.py` | 병원 | ~50 | ~5K | 5 | EEVEE | 기본 박스 + 컬러 |
| `bmesh_hospital_premium.py` | 병원 (프리미엄) | 421 | ~30K | 20 | Cycles | PBR 재질, 조경, 가로등 |
| `bmesh_sagrada_familia.py` | 사그라다 파밀리아 v1 | 215 | ~15K | 21 | Cycles | 기본 타워, 사인파 |
| `bmesh_sagrada_v2.py` | 사그라다 파밀리아 v2 | 273 | 39,358 | 23 | Cycles | 쌍곡면 타워, 카테나리 아치 |
| `bmesh_sagrada_v3.py` | 사그라다 파밀리아 v3 | 450 | 104,727 | 17 | Cycles 512spp | 나선계단, 과일 피나클, 볼류메트릭 |
| **`bmesh_sagrada_v4.py`** | **사그라다 파밀리아 v4** | **129** | **135,973** | **42** | **Cycles 512spp 4K** | **포토리얼: displacement, weathering, caustics** |

## v4 (최종) 기술 상세

### 재질 구성 (42개)

| 재질 | 기법 | 핵심 노드 |
|------|------|----------|
| Montjuïc Sandstone | True Displacement + Weathering 4레이어 + Triple Bump | Displacement, AO, NewGeometry, Voronoi, 5×Noise |
| Glass Sunrise/Sunset/Nativity | Principled Transmission + Emission + Lead frame | Add Shader, Voronoi lead, surface imperfection bump |
| Trencadís ×5색 | 글레이즈 세라믹 + 그라우트 | Voronoi 3D, Coat Weight, grout mask |
| Gold | 금속 + 미세 지문/마모 | MapRange roughness variation |
| Bronze Patina | 동록 (구리→초록 그래디언트) | Noise + ColorRamp |
| Interior Stone | 내부 돌 + 미세 범프 | Noise bump |
| Plaza | 벽돌 포장 | Brick Texture + bump |
| Water | 반사 수면 | Double noise ripple, IOR 1.33 |
| Tree ×N | 개별 색상 변형 | Random seed 기반 |

### Weathering 4레이어 (포토리얼리즘 핵심)

```
Layer 1: Height-based darkening — 지면(어두움) → 상부(밝음)
Layer 2: Moss — Normal.Z > 0.4 (위를 향한 면) × Noise 패치
Layer 3: Rain streaks — Wave Bands + (1 - Normal.Z) 수직면 마스크
Layer 4: Dirt — AmbientOcclusion 오목면에 어두운 먼지
```

### 렌더 설정

- Engine: Cycles (GPU CUDA, CPU fallback)
- Samples: 512 (adaptive, threshold 0.005)
- Denoiser: OpenImageDenoise
- Light bounces: diffuse 8, glossy 8, transmission 16, volume 2
- Caustics: reflective + refractive ON
- Color: AgX Medium High Contrast, exposure 0.3
- Resolution: 3840×2160 (4K), 16-bit PNG
- Output: `/tmp/blender-export/sagrada_v4_photoreal.png`

### 조명 (3-light archviz setup)

| 라이트 | 타입 | 에너지 | 색온도 | 역할 |
|--------|------|--------|--------|------|
| Sun | SUN | 6.0 | 따뜻한 금빛 | 주광 + god rays |
| SkyFill | SUN | 1.2 | 차가운 파란 | 그림자 채움 |
| Bounce | AREA | 150 | 따뜻한 | 지면 반사광 |
| World Volume | Scatter+Absorb | density 0.003 | — | 대기 산란 (god rays) |

## 진화 과정 요약

```
v1 (215 obj) — 사인파 타워, 랜덤 구체 장식 → "수준 낮음" 피드백
v2 (273 obj) — 쌍곡면/카테나리 수학적 표면, Voronoi 스테인드글라스
v3 (450 obj) — 나선계단, 과일 피나클, 볼류메트릭, 4K
v4 (129 obj) — 인터넷 리서치 기반: displacement, weathering, caustics, 전문가급 Light Path
```

핵심 교훈: 오브젝트 수보다 **재질 품질**과 **렌더 설정**이 포토리얼리즘을 결정한다.
