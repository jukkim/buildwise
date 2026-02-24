"""NL → BPS parser: Claude API를 사용하여 자연어에서 BPS JSON 생성."""

from __future__ import annotations

import copy
import logging
from typing import Any

import anthropic
from pydantic import BaseModel

from app.api.v1.templates import _TEMPLATES
from app.config import settings
from app.schemas.bps import BPS
from app.services.ai.prompts import EXTRACT_BUILDING_TOOL, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Singleton client — 연결 풀 재사용으로 latency 절감
_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
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


class NLParseResult(BaseModel):
    name: str
    building_type: str
    bps: dict[str, Any]
    confidence: float
    extracted_params: list[str]
    default_params: list[str]
    warnings: list[str]


async def parse_building_from_text(text: str) -> NLParseResult:
    """자연어 → BPS JSON 변환.

    1. Claude API 호출 (tool_use로 구조화된 응답)
    2. 응답에서 building_type 추출
    3. 해당 템플릿의 default_bps를 base로 사용
    4. AI가 추출한 파라미터로 override
    5. BPS Pydantic 모델로 검증
    6. NLParseResult 반환
    """
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured")

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
        raise ValueError("AI did not return structured building parameters")

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
