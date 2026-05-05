# 설계서: Blender MCP 기반 3D 건물 생성

> **문서 상태**: DRAFT
> **작성일**: 2026-05-05
> **관련 PRD**: `docs/PRD-blender-mcp-integration.md`

---

## 1. 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Frontend                                   │
│  React 19 + React Three Fiber                                           │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────┐  ┌────────────────┐  │
│  │ NL Input │→ │ BPS Form     │→ │ 3D Viewer   │→ │ Results        │  │
│  │ (채팅)    │  │ (파라미터)    │  │ (glTF 렌더) │  │ (대시보드)     │  │
│  └──────────┘  └──────────────┘  └──────────────┘  └────────────────┘  │
│       │              │                  ↑                               │
│       │              │           glTF/glb URL                           │
└───────┼──────────────┼──────────────────┼───────────────────────────────┘
        │              │                  │
        ▼              ▼                  │
┌───────────────────────────────────────────────────────────────────────┐
│                          Backend (FastAPI)                             │
│                                                                       │
│  ┌──────────────┐    ┌──────────────────┐    ┌────────────────────┐  │
│  │ /api/v1/ai   │    │ /api/v1/buildings │    │ /api/v1/simulations│  │
│  │ parse-building│    │ /{id}/generate-3d│    │                    │  │
│  └──────┬───────┘    └────────┬─────────┘    └────────────────────┘  │
│         │                     │                                       │
│         ▼                     ▼                                       │
│  ┌──────────────┐    ┌──────────────────┐                            │
│  │ NL Parser    │    │ Blender Service  │                            │
│  │ (Claude API) │    │ (MCP 클라이언트)  │                            │
│  │ → BPS JSON   │    │ → 3D 생성/수정   │                            │
│  └──────────────┘    │ → glTF export    │                            │
│                      │ → IDF 변환       │                            │
│                      └────────┬─────────┘                            │
│                               │ TCP Socket (9876)                    │
└───────────────────────────────┼───────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│                    Blender Container (headless)                        │
│                                                                       │
│  ┌──────────────────┐    ┌───────────────┐    ┌───────────────────┐  │
│  │ MCP Addon        │    │ Building Gen  │    │ Export Pipeline   │  │
│  │ (TCP server)     │    │ (Python scripts│    │ glTF / gbXML     │  │
│  │ 명령 수신/실행    │    │  파라메트릭)   │    │ / IDF 변환       │  │
│  └──────────────────┘    └───────────────┘    └───────────────────┘  │
│                                                                       │
│  Blender 4.x + Python 3.11 + blender-mcp addon                      │
└───────────────────────────────────────────────────────────────────────┘
```

## 2. 컴포넌트 상세

### 2.1 Blender Container

Blender를 headless Docker 컨테이너로 실행. MCP 애드온이 TCP 소켓으로 명령 수신.

```dockerfile
# Dockerfile.blender (신규)
FROM nytimes/blender:4.2-cpu

# MCP addon 설치
COPY blender-mcp/addon.py /root/.config/blender/4.2/scripts/addons/
# 건축 생성 스크립트
COPY blender_scripts/ /opt/blender_scripts/

# headless + addon 자동 활성화
CMD ["blender", "--background", "--python", "/opt/blender_scripts/start_mcp_server.py"]
EXPOSE 9876
```

**프로세스 풀**: 동시 요청 처리를 위해 N개 컨테이너. docker-compose에서 `replicas: 3`.

### 2.2 Blender Service (백엔드)

`buildwise-backend/app/services/blender/` 디렉토리 신규 생성.

```
app/services/blender/
├── __init__.py
├── client.py          # Blender MCP TCP 클라이언트 (연결 풀)
├── building_gen.py    # BPS → Blender 건물 생성 명령 변환
├── exporter.py        # glTF/gbXML export 요청 + 파일 회수
└── idf_converter.py   # gbXML → IDF 변환 (또는 zone 직접 매핑)
```

#### 2.2.1 client.py — MCP TCP 클라이언트

```python
import asyncio
import json
from dataclasses import dataclass

@dataclass
class BlenderConnection:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    busy: bool = False

class BlenderPool:
    """Blender 인스턴스 연결 풀."""

    def __init__(self, hosts: list[tuple[str, int]], timeout: float = 60.0):
        self._hosts = hosts        # [("blender-1", 9876), ("blender-2", 9876)]
        self._timeout = timeout
        self._connections: list[BlenderConnection] = []

    async def execute(self, command: dict) -> dict:
        """MCP 명령 전송 + 응답 수신."""
        conn = await self._acquire()
        try:
            payload = json.dumps(command).encode() + b"\n"
            conn.writer.write(payload)
            await conn.writer.drain()

            data = await asyncio.wait_for(
                conn.reader.readline(), timeout=self._timeout
            )
            return json.loads(data.decode())
        finally:
            conn.busy = False

    async def _acquire(self) -> BlenderConnection:
        """유휴 연결 획득 또는 신규 생성."""
        ...
```

#### 2.2.2 building_gen.py — BPS → 3D 변환 로직

BPS JSON을 Blender 파이썬 스크립트로 변환하는 핵심 모듈.

```python
def bps_to_blender_commands(bps: dict) -> list[dict]:
    """BPS JSON → Blender MCP 명령 시퀀스.

    건물 유형별 파라메트릭 생성:
    - 층별 바닥판 (면적, 높이)
    - 외벽 + 창호 (WWR 비율)
    - 지붕
    - HVAC 존 분할
    """
    building_type = bps["building"]["building_type"]
    floors = bps["building"]["floors"]
    floor_area = bps["building"]["floor_area_m2"]
    wwr = bps.get("envelope", {}).get("wwr", 0.4)
    floor_height = bps.get("building", {}).get("floor_height_m", 3.5)

    commands = []

    # 1. 바닥판 생성 (층별)
    per_floor_area = floor_area / floors
    side_length = per_floor_area ** 0.5  # 정방형 근사
    for i in range(floors):
        z = i * floor_height
        commands.append({
            "type": "create_object",
            "params": {
                "type": "cube",
                "name": f"Floor_{i+1}",
                "location": [0, 0, z + floor_height / 2],
                "scale": [side_length / 2, side_length / 2, floor_height / 2],
            }
        })

    # 2. 창호 (WWR 기반)
    commands.append({
        "type": "execute_script",
        "params": {
            "script": f"exec(open('/opt/blender_scripts/add_windows.py').read())",
            "args": {"wwr": wwr, "floors": floors}
        }
    })

    # 3. 머티리얼 적용
    commands.append({
        "type": "set_material",
        "params": {
            "object": "Floor_*",
            "material": _get_material(building_type)
        }
    })

    return commands
```

#### 2.2.3 exporter.py — 결과물 추출

```python
async def export_gltf(pool: BlenderPool, scene_id: str) -> bytes:
    """현재 씬을 glTF 바이너리로 export."""
    result = await pool.execute({
        "type": "export",
        "params": {
            "format": "gltf",
            "path": f"/tmp/export/{scene_id}.glb"
        }
    })
    # 컨테이너에서 파일 회수 (공유 볼륨 또는 GCS)
    ...

async def export_gbxml(pool: BlenderPool, scene_id: str) -> str:
    """gbXML 형식으로 export (IDF 변환용)."""
    ...
```

#### 2.2.4 idf_converter.py — 3D → IDF

두 가지 접근법:

```
방법 A: Blender → gbXML → OpenStudio → IDF
  장점: 표준 파이프라인, zone 자동 매핑
  단점: OpenStudio 의존성 추가

방법 B: Blender zone 정보 → eppy로 IDF 직접 생성 (권장)
  장점: 기존 ems_bridge.py 활용, 의존성 최소
  단점: zone 매핑 로직 자체 구현 필요
```

**권장: 방법 B** — 기존 ems_bridge.py + IDF generator를 확장.

```python
async def blender_to_idf(pool: BlenderPool, bps: dict) -> str:
    """Blender 씬에서 zone 정보 추출 → IDF 생성.

    1. Blender에서 오브젝트별 geometry 추출 (위치, 크기, 면적)
    2. Zone 자동 분할 (층별 1 zone 기본)
    3. 기존 IDF generator에 geometry 주입
    4. EMS 전략 적용 (기존 ems_bridge 사용)
    """
    # Blender에서 geometry 추출
    scene_info = await pool.execute({"type": "get_scene_info"})

    zones = _extract_zones(scene_info)
    surfaces = _extract_surfaces(scene_info)

    # 기존 generator에 위임
    from app.services.idf.generator import generate_idf
    idf_content = generate_idf(bps, zones=zones, surfaces=surfaces)

    return idf_content
```

### 2.3 API 확장

#### 새 엔드포인트

```python
# app/api/v1/buildings.py 확장

@router.post("/{project_id}/buildings/{building_id}/generate-3d")
async def generate_3d_model(
    project_id: UUID,
    building_id: UUID,
    request: Generate3DRequest,  # {"source": "bps" | "natural_language", "prompt": "..."}
    db: AsyncSession = Depends(get_db),
):
    """BPS 또는 자연어로 3D 모델 생성.

    Returns:
        {"model_url": "https://.../model.glb", "idf_ready": true}
    """
    ...

@router.patch("/{project_id}/buildings/{building_id}/modify-3d")
async def modify_3d_model(
    project_id: UUID,
    building_id: UUID,
    request: Modify3DRequest,  # {"instruction": "창호비를 60%로 변경"}
    db: AsyncSession = Depends(get_db),
):
    """자연어로 기존 3D 모델 수정."""
    ...
```

### 2.4 프론트엔드 변경

#### BuildingEditor.tsx 확장

```
현재:                           변경 후:
┌───────────────────────┐      ┌───────────────────────┐
│ BPS Form | [Box 3D]   │      │ BPS Form | [실제 3D]  │
│                       │ →    │          | [glTF 모델] │
│ [시뮬 시작]           │      │ [3D 생성] [수정] [시뮬]│
└───────────────────────┘      └───────────────────────┘
```

- `BuildingViewer3D.tsx`: glTF 모델 로더 추가 (`useGLTF` hook)
- "3D 생성" 버튼 → `/generate-3d` API 호출 → 로딩 → glTF URL 수신 → 뷰어 갱신
- "자연어 수정" 채팅 입력 → `/modify-3d` API → 모델 갱신

### 2.5 Docker Compose 확장

```yaml
# docker-compose.yml에 추가

  blender:
    build:
      context: ./blender-service
      dockerfile: Dockerfile.blender
    deploy:
      replicas: 3
    ports:
      - "9876"
    volumes:
      - blender-export:/tmp/export
    healthcheck:
      test: ["CMD", "python3", "-c", "import socket; s=socket.socket(); s.connect(('localhost',9876)); s.close()"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  blender-export:
```

## 3. 데이터 흐름 (전체 파이프라인)

```
사용자: "서울에 있는 8층 대형 오피스, 유리 커튼월 60%"
                    │
                    ▼
         ┌─── NL Parser (Claude API) ───┐
         │  BPS JSON 추출:              │
         │  {building_type: "large_office",│
         │   floors: 8, wwr: 0.6,       │
         │   city: "Seoul", ...}         │
         └──────────┬───────────────────┘
                    │
                    ▼
         ┌─── BPS Form (프론트) ────────┐
         │  사용자 확인/수정 후 "3D 생성"│
         └──────────┬───────────────────┘
                    │ POST /generate-3d
                    ▼
         ┌─── Blender Service ──────────┐
         │  1. BPS → Blender 명령 변환  │
         │  2. MCP로 Blender 전송       │
         │  3. 3D 모델 생성 (headless)  │
         │  4. glTF export → GCS 업로드 │
         │  5. zone 추출 → IDF 생성     │
         └──────────┬───────────────────┘
                    │
              ┌─────┴─────┐
              ▼           ▼
         model.glb    building.idf
         (3D 뷰어)   (EnergyPlus 시뮬)
              │           │
              ▼           ▼
         BuildingViewer  SimulationRunner
         (React Three)  (Celery → E+ 또는 mock)
```

## 4. Zone 매핑 전략

EnergyPlus IDF의 핵심은 Thermal Zone 정의. Blender 3D 오브젝트를 zone으로 변환하는 규칙:

```
기본 규칙: 1 Floor = 1 Zone

예외:
- large_office: core + 4 perimeter zones/floor (DOE 기준)
- hospital: 부서별 zone (수술실, 병실, 로비 등)
- primary_school: 교실/복도/체육관 분리

Blender 오브젝트 명명 규칙:
  Zone_F{층}_Core       → 코어 존
  Zone_F{층}_N/S/E/W    → 방위별 페리미터 존
  Zone_F{층}_{용도}      → 특수 용도 존
```

## 5. 폴백 전략

Blender 생성 실패 시 기존 Phase 1 파이프라인으로 fallback:

```python
async def generate_building_3d(bps: dict) -> BuildingModel:
    try:
        # Phase 2: Blender MCP 생성
        model = await blender_service.generate(bps)
        return model
    except (BlenderTimeoutError, BlenderConnectionError):
        logger.warning("Blender generation failed, falling back to parametric")
        # Phase 1: React Three Fiber 파라메트릭 박스
        return ParametricBoxModel(bps)
```

## 6. 테스트 전략

| 계층 | 대상 | 도구 |
|------|------|------|
| Unit | building_gen.py (BPS→명령 변환) | pytest, mock |
| Unit | idf_converter.py (zone 매핑) | pytest, eppy 검증 |
| Integration | Blender MCP 소켓 통신 | Docker + pytest-docker |
| Integration | 전체 파이프라인 (NL→3D→IDF→시뮬) | Docker Compose + httpx |
| E2E | 프론트 3D 뷰어 렌더링 | Playwright |
| Validation | 생성된 IDF의 EnergyPlus 실행 가능성 | EnergyPlus Docker |

### 검증 기준 (DOE 6종 건물)

```
DOE 건물 6종 × 10 도시 = 60 케이스
각 케이스:
  □ BPS → 3D 생성 성공
  □ glTF export 유효
  □ zone 추출 정확 (기대 zone 수 일치)
  □ IDF 생성 → EnergyPlus 실행 → EUI 산출
  □ EUI가 mock_runner 룩업 값 대비 ±15% 이내
```

## 7. 성능 예산

| 구간 | 목표 | 비고 |
|------|------|------|
| NL → BPS | ≤ 3초 | 기존 Claude API |
| BPS → Blender 3D | ≤ 15초 | 소켓 통신 + 모델링 |
| glTF export | ≤ 5초 | 파일 크기 < 10MB |
| glTF → 프론트 렌더 | ≤ 3초 | React Three Fiber |
| 3D → IDF 변환 | ≤ 5초 | zone 매핑 + eppy |
| **전체** | **≤ 30초** | NL 입력 → 3D 표시 |

## 8. 파일 구조 변경 (예상)

```
buildwise-backend/
├── app/services/blender/     ← 신규
│   ├── __init__.py
│   ├── client.py             # MCP TCP 연결 풀
│   ├── building_gen.py       # BPS → Blender 명령
│   ├── exporter.py           # glTF/gbXML export
│   └── idf_converter.py      # 3D → IDF 변환

blender-service/              ← 신규 (최상위)
├── Dockerfile.blender
├── addon.py                  # blender-mcp fork/확장
└── blender_scripts/
    ├── start_mcp_server.py
    ├── building_parametric.py  # 파라메트릭 건물 생성
    ├── add_windows.py          # WWR 기반 창호 생성
    ├── zone_splitter.py        # zone 자동 분할
    └── export_utils.py         # glTF/gbXML export
```
