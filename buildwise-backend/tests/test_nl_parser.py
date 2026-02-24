"""Tests for NL → BPS parser with mock Claude API responses."""

from __future__ import annotations

import copy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai.nl_parser import NLParseResult, parse_building_from_text


def _make_mock_response(tool_input: dict) -> MagicMock:
    """Create a mock Claude API response with tool_use block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = "extract_building_params"
    block.input = tool_input

    response = MagicMock()
    response.content = [block]
    return response


@pytest.fixture
def mock_settings():
    """Patch settings to have a valid API key."""
    with patch("app.services.ai.nl_parser.settings") as mock:
        mock.anthropic_api_key = "sk-ant-test-key"
        yield mock


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the singleton client between tests."""
    import app.services.ai.nl_parser as mod
    mod._client = None
    yield
    mod._client = None


@pytest.fixture
def mock_client(mock_settings):
    """Patch AsyncAnthropic to return controlled responses."""
    with patch("app.services.ai.nl_parser.anthropic.AsyncAnthropic") as cls:
        client_instance = AsyncMock()
        cls.return_value = client_instance
        yield client_instance


# ---------------------------------------------------------------------------
# Basic parsing tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_large_office_korean(mock_client):
    """한국어 입력: '서울 12층 유리 오피스' → large_office."""
    mock_client.messages.create = AsyncMock(
        return_value=_make_mock_response({
            "building_type": "large_office",
            "name": "서울 유리 오피스",
            "confidence": 0.85,
            "city": "Seoul",
            "num_floors": 12,
            "total_area_m2": 46320,
            "wall_type": "curtain_wall",
            "wwr": 0.6,
        })
    )

    result = await parse_building_from_text("서울 12층 유리 오피스")

    assert isinstance(result, NLParseResult)
    assert result.building_type == "large_office"
    assert result.name == "서울 유리 오피스"
    assert result.confidence == 0.85
    assert result.bps["location"]["city"] == "Seoul"
    assert result.bps["geometry"]["num_floors_above"] == 12
    assert result.bps["geometry"]["total_floor_area_m2"] == 46320
    assert result.bps["envelope"]["wall_type"] == "curtain_wall"
    assert result.bps["geometry"]["wwr"] == 0.6
    # HVAC must match building_type
    assert result.bps["hvac"]["system_type"] == "vav_chiller_boiler"
    assert "building_type" in result.extracted_params
    assert "city" in result.extracted_params
    assert "num_floors" in result.extracted_params


@pytest.mark.asyncio
async def test_parse_small_retail_jeju(mock_client):
    """영어 입력: 'small retail shop in Jeju' → standalone_retail."""
    mock_client.messages.create = AsyncMock(
        return_value=_make_mock_response({
            "building_type": "standalone_retail",
            "name": "Jeju Retail Shop",
            "confidence": 0.7,
            "city": "Jeju",
            "num_floors": 1,
        })
    )

    result = await parse_building_from_text("small retail shop in Jeju")

    assert result.building_type == "standalone_retail"
    assert result.bps["location"]["city"] == "Jeju"
    assert result.bps["hvac"]["system_type"] == "psz_ac"
    assert "operating_hours" in result.default_params


@pytest.mark.asyncio
async def test_parse_hospital_busan(mock_client):
    """한국어 입력: '부산 5층 병원' → hospital."""
    mock_client.messages.create = AsyncMock(
        return_value=_make_mock_response({
            "building_type": "hospital",
            "name": "부산 종합병원",
            "confidence": 0.8,
            "city": "Busan",
            "num_floors": 5,
            "total_area_m2": 22422,
        })
    )

    result = await parse_building_from_text("부산 5층 병원")

    assert result.building_type == "hospital"
    assert result.bps["location"]["city"] == "Busan"
    assert result.bps["geometry"]["num_floors_above"] == 5
    assert result.bps["hvac"]["system_type"] == "vav_chiller_boiler"
    assert result.bps["schedules"]["occupancy_type"] == "hospital_24h"


@pytest.mark.asyncio
async def test_parse_medium_office_vrf(mock_client):
    """medium_office → VRF system."""
    mock_client.messages.create = AsyncMock(
        return_value=_make_mock_response({
            "building_type": "medium_office",
            "name": "Medium Office",
            "confidence": 0.6,
        })
    )

    result = await parse_building_from_text("3층짜리 중규모 사무실")

    assert result.building_type == "medium_office"
    assert result.bps["hvac"]["system_type"] == "vrf"


@pytest.mark.asyncio
async def test_parse_school(mock_client):
    """primary_school → vav_chiller_boiler_school."""
    mock_client.messages.create = AsyncMock(
        return_value=_make_mock_response({
            "building_type": "primary_school",
            "name": "대전 초등학교",
            "confidence": 0.75,
            "city": "Daejeon",
        })
    )

    result = await parse_building_from_text("대전 초등학교")

    assert result.building_type == "primary_school"
    assert result.bps["hvac"]["system_type"] == "vav_chiller_boiler_school"
    assert result.bps["location"]["city"] == "Daejeon"


# ---------------------------------------------------------------------------
# Parameter override tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setpoint_override(mock_client):
    """Setpoint parameters should override template defaults."""
    mock_client.messages.create = AsyncMock(
        return_value=_make_mock_response({
            "building_type": "large_office",
            "name": "Cool Office",
            "confidence": 0.9,
            "cooling_setpoint": 22.0,
            "heating_setpoint": 22.0,
        })
    )

    result = await parse_building_from_text("office with 22C cooling and heating")

    assert result.bps["setpoints"]["cooling_occupied"] == 22.0
    assert result.bps["setpoints"]["heating_occupied"] == 22.0
    assert "cooling_setpoint" in result.extracted_params
    assert "heating_setpoint" in result.extracted_params


@pytest.mark.asyncio
async def test_window_and_orientation(mock_client):
    """Window type and orientation override."""
    mock_client.messages.create = AsyncMock(
        return_value=_make_mock_response({
            "building_type": "large_office",
            "name": "South-facing Office",
            "confidence": 0.8,
            "window_type": "triple_low_e",
            "orientation_deg": 180,
            "footprint_shape": "L",
        })
    )

    result = await parse_building_from_text("L-shaped south-facing office with triple glazing")

    assert result.bps["envelope"]["window_type"] == "triple_low_e"
    assert result.bps["geometry"]["orientation_deg"] == 180
    assert result.bps["geometry"]["footprint_shape"] == "L"


# ---------------------------------------------------------------------------
# Default params tracking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_params_tracking(mock_client):
    """Params not extracted by AI should be listed in default_params."""
    mock_client.messages.create = AsyncMock(
        return_value=_make_mock_response({
            "building_type": "small_office",
            "name": "Simple Office",
            "confidence": 0.5,
        })
    )

    result = await parse_building_from_text("simple office")

    assert "city" in result.default_params
    assert "num_floors" in result.default_params
    assert "total_area_m2" in result.default_params
    assert "wall_type" in result.default_params
    assert "operating_hours" in result.default_params
    assert "building_type" not in result.default_params  # was extracted


# ---------------------------------------------------------------------------
# BPS validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bps_passes_pydantic_validation(mock_client):
    """Result BPS should be valid against Pydantic BPS schema."""
    from app.schemas.bps import BPS

    mock_client.messages.create = AsyncMock(
        return_value=_make_mock_response({
            "building_type": "large_office",
            "name": "Valid Office",
            "confidence": 0.9,
            "city": "Seoul",
            "num_floors": 10,
            "total_area_m2": 38600,
        })
    )

    result = await parse_building_from_text("Seoul 10-story office")

    # Should not raise
    validated = BPS.model_validate(result.bps)
    assert validated.geometry.building_type == "large_office"
    assert validated.location.city == "Seoul"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_api_key_raises():
    """Should raise ValueError when ANTHROPIC_API_KEY is not set."""
    with patch("app.services.ai.nl_parser.settings") as mock:
        mock.anthropic_api_key = ""
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            await parse_building_from_text("some building")


@pytest.mark.asyncio
async def test_no_tool_use_in_response_raises(mock_client):
    """Should raise ValueError when AI doesn't return tool_use block."""
    response = MagicMock()
    response.content = []  # No tool_use blocks
    mock_client.messages.create = AsyncMock(return_value=response)

    with pytest.raises(ValueError, match="structured building parameters"):
        await parse_building_from_text("some building")
