"""NL → BPS parser: Claude API를 사용하여 자연어에서 BPS JSON 생성.

API 키가 없을 때는 규칙 기반 파서(regex/키워드)로 폴백.
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any

from pydantic import BaseModel

from app.api.v1.templates import _TEMPLATES
from app.config import settings
from app.schemas.bps import BPS
from app.services.ai.prompts import EXTRACT_BUILDING_TOOL, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Singleton Anthropic client — 연결 풀 재사용으로 latency 절감
_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=30.0,
        )
    return _client


# HVAC mapping: building_type → system_type (1:1, not configurable)
_HVAC_MAP: dict[str, str] = {
    "large_office": "vav_chiller_boiler",
    "medium_office": "vrf",
    "small_office": "psz_hp",
    "standalone_retail": "psz_ac",
    "primary_school": "vav_chiller_boiler_school",
    "hospital": "vav_chiller_boiler",
}

# 도시 매핑 (한국어 → 영어)
_CITY_KO: dict[str, str] = {
    "서울": "Seoul", "seoul": "Seoul",
    "부산": "Busan", "busan": "Busan",
    "대구": "Daegu", "daegu": "Daegu",
    "대전": "Daejeon", "daejeon": "Daejeon",
    "광주": "Gwangju", "gwangju": "Gwangju",
    "인천": "Incheon", "incheon": "Incheon",
    "강릉": "Gangneung", "gangneung": "Gangneung",
    "제주": "Jeju", "제주도": "Jeju", "jeju": "Jeju",
    "청주": "Cheongju", "cheongju": "Cheongju",
    "울산": "Ulsan", "ulsan": "Ulsan",
}

# 건물 유형별 한국어/영어 키워드
_BLDG_KEYWORDS: list[tuple[str, list[str]]] = [
    ("hospital",          ["병원", "의원", "클리닉", "clinic", "hospital", "medical"]),
    ("primary_school",    ["학교", "초등학교", "중학교", "고등학교", "school"]),
    ("standalone_retail", ["소매", "매장", "쇼핑", "편의점", "마트", "상점", "리테일",
                           "retail", "shop", "store", "mart", "supermarket"]),
]

# 오피스 관련 키워드 (크기 판별 별도)
_OFFICE_KW = ["오피스", "사무실", "사무소", "office", "빌딩", "building"]

# 건물 유형 한글 이름 (이름 생성용)
_BLDG_KO_NAME: dict[str, str] = {
    "large_office": "대형 오피스",
    "medium_office": "오피스",
    "small_office": "소규모 사무실",
    "standalone_retail": "소매점",
    "primary_school": "학교",
    "hospital": "병원",
}


class NLParseResult(BaseModel):
    name: str
    building_type: str
    bps: dict[str, Any]
    confidence: float
    extracted_params: list[str]
    default_params: list[str]
    warnings: list[str]


# ─────────────────────────────────────────────
# 규칙 기반 파서 (API 키 없을 때 폴백)
# ─────────────────────────────────────────────

def _detect_city(text: str) -> str | None:
    """텍스트에서 도시 이름 추출."""
    t = text.lower()
    for ko, en in _CITY_KO.items():
        if ko in t:
            return en
    return None


def _detect_floors(text: str) -> int | None:
    """층수 추출: '12층', '12F', '12-story' 등."""
    # 한국어: 숫자 + 층
    m = re.search(r"(\d+)\s*층", text)
    if m:
        return int(m.group(1))
    # 영어: 숫자 + F/floor(s)/story/stories
    m = re.search(r"(\d+)\s*[-\s]?(f\b|floor|floors|story|stories)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _detect_area(text: str) -> float | None:
    """면적 추출: '46320m²', '1000평' 등."""
    # m² / m2 / sqm
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*(m²|m2|sqm)", text, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ""))
    # 평 → m² (1평 ≈ 3.306m²)
    m = re.search(r"([\d,]+)\s*평", text)
    if m:
        return round(float(m.group(1).replace(",", "")) * 3.306, 1)
    return None


def _detect_wall_type(text: str) -> str | None:
    """외벽 유형 추출."""
    t = text.lower()
    if any(kw in t for kw in ["커튼월", "유리", "glass", "curtain"]):
        return "curtain_wall"
    if any(kw in t for kw in ["조적", "brick", "masonry"]):
        return "masonry"
    if any(kw in t for kw in ["콘크리트", "concrete"]):
        return "concrete"
    if any(kw in t for kw in ["metal", "metal panel", "금속"]):
        return "metal_panel"
    return None


def _detect_wwr(text: str) -> float | None:
    """WWR 추출: '커튼월/유리' → 0.7."""
    t = text.lower()
    # 명시적 숫자: "wwr 0.6", "wwr60%", "창면적비 60%"
    m = re.search(r"wwr\s*[=:‥]?\s*(0\.\d+)", t)
    if m:
        return float(m.group(1))
    m = re.search(r"(wwr|창면적비|창비율)\s*(\d{1,2})\s*%", t, re.IGNORECASE)
    if m:
        return round(int(m.group(2)) / 100, 2)
    # 간접 표현
    if any(kw in t for kw in ["전면유리", "전유리", "full glass", "all glass", "유리 외벽"]):
        return 0.75
    if any(kw in t for kw in ["유리", "glass", "curtain"]):
        return 0.6
    return None


def _classify_office(floors: int | None, area: float | None) -> str:
    """층수·면적으로 오피스 크기 분류."""
    if floors is not None:
        if floors >= 11:
            return "large_office"
        if floors >= 4:
            return "medium_office"
        return "small_office"
    if area is not None:
        if area >= 15000:
            return "large_office"
        if area >= 2000:
            return "medium_office"
        return "small_office"
    return "medium_office"  # 기본값


def _detect_building_type(text: str, floors: int | None, area: float | None) -> str:
    """건물 유형 감지."""
    t = text.lower()
    # 특수 유형 우선 (오피스보다 명확)
    for btype, keywords in _BLDG_KEYWORDS:
        if any(kw in t for kw in keywords):
            return btype
    # 오피스 계열
    is_office = any(kw in t for kw in _OFFICE_KW)
    # '대형', 'large' 등 명시적 크기
    if any(kw in t for kw in ["대형", "high-rise", "고층", "large office", "대규모"]):
        return "large_office"
    if any(kw in t for kw in ["소형", "small office", "소규모"]):
        return "small_office"
    if is_office:
        return _classify_office(floors, area)
    # 키워드 없으면 층수·면적으로 추론
    if floors is not None or area is not None:
        return _classify_office(floors, area)
    return "medium_office"  # 최종 기본값


def _make_name(text: str, building_type: str, city: str | None) -> str:
    """입력 텍스트에서 건물 이름 추론."""
    # 텍스트가 짧고 의미 있으면 그대로 사용
    stripped = text.strip()
    if 3 <= len(stripped) <= 30:
        return stripped
    # 도시 + 유형 조합
    city_part = city or "서울"
    type_part = _BLDG_KO_NAME.get(building_type, "빌딩")
    return f"{city_part} {type_part}"


def _rule_based_parse(text: str) -> NLParseResult:
    """키워드/정규식 기반 파서 — API 키 없을 때 폴백.

    정확도는 낮지만 외부 API 없이 동작한다.
    """
    extracted: list[str] = []
    warnings: list[str] = [
        "규칙 기반 파서 사용 (ANTHROPIC_API_KEY 미설정). "
        "정확도가 낮을 수 있으며 일부 파라미터는 기본값이 적용됩니다."
    ]

    city = _detect_city(text)
    floors = _detect_floors(text)
    area = _detect_area(text)
    wall_type = _detect_wall_type(text)
    wwr = _detect_wwr(text)

    building_type = _detect_building_type(text, floors, area)
    extracted.append("building_type")

    template = _TEMPLATES.get(building_type)
    if template is None:
        building_type = "medium_office"
        template = _TEMPLATES["medium_office"]

    bps = copy.deepcopy(template["default_bps"])

    if city:
        bps["location"]["city"] = city
        extracted.append("city")

    if floors is not None:
        bps["geometry"]["num_floors_above"] = floors
        extracted.append("num_floors")
        # 층수에서 면적 미입력 시 추정
        if area is None:
            per_floor = {
                "large_office": 3860, "medium_office": 1660, "small_office": 500,
                "standalone_retail": 2294, "primary_school": 6871, "hospital": 4484,
            }.get(building_type, 1000)
            area = floors * per_floor

    if area is not None:
        bps["geometry"]["total_floor_area_m2"] = area
        extracted.append("total_area_m2")

    if wall_type:
        bps["envelope"]["wall_type"] = wall_type
        extracted.append("wall_type")

    if wwr is not None:
        bps["geometry"]["wwr"] = wwr
        extracted.append("wwr")

    # HVAC 강제 적용
    bps["hvac"]["system_type"] = _HVAC_MAP[building_type]

    # Pydantic 검증
    try:
        validated = BPS.model_validate(bps)
        bps = validated.model_dump(mode="json")
    except Exception as e:
        warnings.append(f"Validation adjusted: {e}")
        logger.warning("Rule-based BPS validation issue: %s", e)

    all_params = [
        "city", "num_floors", "total_area_m2", "wall_type", "window_type",
        "wwr", "footprint_shape", "orientation_deg", "cooling_setpoint",
        "heating_setpoint", "operating_hours", "equipment_power_density",
        "lighting_power_density", "people_density",
    ]
    default_params = [p for p in all_params if p not in extracted]

    # confidence: 추출된 파라미터 수에 비례 (max 0.65 — AI보다 낮음)
    confidence = min(0.25 + len(extracted) * 0.08, 0.65)

    name = _make_name(text, building_type, city)

    return NLParseResult(
        name=name,
        building_type=building_type,
        bps=bps,
        confidence=confidence,
        extracted_params=extracted,
        default_params=default_params,
        warnings=warnings,
    )


# ─────────────────────────────────────────────
# 메인 파서 (Claude API → 규칙 기반 폴백)
# ─────────────────────────────────────────────

async def parse_building_from_text(text: str) -> NLParseResult:
    """자연어 → BPS JSON 변환.

    ANTHROPIC_API_KEY가 설정된 경우: Claude Haiku로 구조화 추출.
    미설정된 경우: 규칙 기반 파서(regex/키워드)로 폴백.
    """
    if not settings.anthropic_api_key:
        logger.info("ANTHROPIC_API_KEY not set — using rule-based parser fallback")
        return _rule_based_parse(text)

    client = _get_client()

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        tools=[EXTRACT_BUILDING_TOOL],
        tool_choice={"type": "tool", "name": "extract_building_params"},
        messages=[{"role": "user", "content": text}],
    )

    # Extract tool_use result
    tool_input: dict[str, Any] | None = None
    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_building_params":
            tool_input = block.input
            break

    if tool_input is None:
        logger.warning("Claude did not return structured params — falling back to rule-based")
        return _rule_based_parse(text)

    building_type: str = tool_input["building_type"]
    ai_name: str = tool_input.get("name", "New Building")
    confidence: float = tool_input.get("confidence", 0.5)

    # Get template default_bps as base
    template = _TEMPLATES.get(building_type)
    if template is None:
        raise ValueError(f"Unknown building type from AI: {building_type}")

    bps = copy.deepcopy(template["default_bps"])
    extracted: list[str] = ["building_type"]
    warnings: list[str] = []

    # Override with AI-extracted parameters
    city = tool_input.get("city")
    if city:
        bps["location"]["city"] = city
        extracted.append("city")

    num_floors = tool_input.get("num_floors")
    if num_floors is not None:
        bps["geometry"]["num_floors_above"] = num_floors
        extracted.append("num_floors")

    total_area = tool_input.get("total_area_m2")
    if total_area is not None:
        bps["geometry"]["total_floor_area_m2"] = total_area
        extracted.append("total_area_m2")

    wall_type = tool_input.get("wall_type")
    if wall_type:
        bps["envelope"]["wall_type"] = wall_type
        extracted.append("wall_type")

    window_type = tool_input.get("window_type")
    if window_type:
        bps["envelope"]["window_type"] = window_type
        extracted.append("window_type")

    wwr = tool_input.get("wwr")
    if wwr is not None:
        bps["geometry"]["wwr"] = wwr
        extracted.append("wwr")

    footprint = tool_input.get("footprint_shape")
    if footprint:
        bps["geometry"]["footprint_shape"] = footprint
        extracted.append("footprint_shape")

    orientation = tool_input.get("orientation_deg")
    if orientation is not None:
        bps["geometry"]["orientation_deg"] = orientation
        extracted.append("orientation_deg")

    cooling = tool_input.get("cooling_setpoint")
    if cooling is not None:
        bps["setpoints"]["cooling_occupied"] = cooling
        extracted.append("cooling_setpoint")

    heating = tool_input.get("heating_setpoint")
    if heating is not None:
        bps["setpoints"]["heating_occupied"] = heating
        extracted.append("heating_setpoint")

    # Ensure HVAC system_type matches building_type (override if AI changed it)
    expected_hvac = _HVAC_MAP[building_type]
    if bps["hvac"]["system_type"] != expected_hvac:
        bps["hvac"]["system_type"] = expected_hvac

    # Validate with Pydantic
    try:
        validated = BPS.model_validate(bps)
        bps = validated.model_dump(mode="json")
    except Exception as e:
        warnings.append(f"Validation adjusted: {e}")
        logger.warning("BPS validation issue: %s", e)

    # Determine which params used template defaults
    all_params = [
        "city", "num_floors", "total_area_m2", "wall_type", "window_type",
        "wwr", "footprint_shape", "orientation_deg", "cooling_setpoint",
        "heating_setpoint", "operating_hours", "equipment_power_density",
        "lighting_power_density", "people_density",
    ]
    default_params = [p for p in all_params if p not in extracted]

    return NLParseResult(
        name=ai_name,
        building_type=building_type,
        bps=bps,
        confidence=confidence,
        extracted_params=extracted,
        default_params=default_params,
        warnings=warnings,
    )
