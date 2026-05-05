"""Tests for Blender MCP integration (unit tests with mocked connections)."""

from __future__ import annotations

import pytest

from app.services.blender.building_gen import bps_to_blender_commands, bps_to_zone_info
from app.services.blender.client import (
    BlenderConnectionError,
    BlenderPool,
)

# ── BPS fixtures ──────────────────────────────────────────────────────

_LARGE_OFFICE_BPS = {
    "building": {
        "building_type": "large_office",
        "floors": 12,
        "floor_area_m2": 46320,
        "floor_height_m": 3.96,
    },
    "envelope": {"wwr": 0.4},
}

_SMALL_OFFICE_BPS = {
    "building": {
        "building_type": "small_office",
        "floors": 1,
        "floor_area_m2": 511,
    },
    "envelope": {"wwr": 0.25},
}

_HOSPITAL_BPS = {
    "building": {
        "building_type": "hospital",
        "floors": 5,
        "floor_area_m2": 22422,
    },
    "envelope": {"wwr": 0.3},
}


# ── building_gen tests ────────────────────────────────────────────────


class TestBPSToBlenderCommands:
    def test_large_office_command_count(self):
        commands = bps_to_blender_commands(_LARGE_OFFICE_BPS)
        # 1 clear + 12 floors + 12*4 windows + 1 roof + 12 materials + 1 glass
        assert len(commands) > 60

    def test_first_command_is_clear(self):
        commands = bps_to_blender_commands(_LARGE_OFFICE_BPS)
        assert commands[0]["type"] == "execute_script"
        assert "select_all" in commands[0]["params"]["script"]

    def test_floor_names_sequential(self):
        commands = bps_to_blender_commands(_LARGE_OFFICE_BPS)
        floor_commands = [
            c for c in commands
            if c["type"] == "create_object" and c["params"]["name"].startswith("Floor_")
        ]
        assert len(floor_commands) == 12
        for i, cmd in enumerate(floor_commands):
            assert cmd["params"]["name"] == f"Floor_{i + 1}"

    def test_window_wwr_affects_height(self):
        bps_40 = {**_LARGE_OFFICE_BPS, "envelope": {"wwr": 0.4}}
        bps_80 = {**_LARGE_OFFICE_BPS, "envelope": {"wwr": 0.8}}

        cmds_40 = bps_to_blender_commands(bps_40)
        cmds_80 = bps_to_blender_commands(bps_80)

        win_40 = [c for c in cmds_40 if c["type"] == "create_object" and c["params"]["name"].startswith("Win_")]
        win_80 = [c for c in cmds_80 if c["type"] == "create_object" and c["params"]["name"].startswith("Win_")]

        # Higher WWR → taller windows
        h_40 = win_40[0]["params"]["scale"][2]
        h_80 = win_80[0]["params"]["scale"][2]
        assert h_80 > h_40

    def test_roof_on_top(self):
        commands = bps_to_blender_commands(_LARGE_OFFICE_BPS)
        roof = [c for c in commands if c["type"] == "create_object" and c["params"]["name"] == "Roof"]
        assert len(roof) == 1
        expected_z = 12 * 3.96 + 0.1
        assert abs(roof[0]["params"]["location"][2] - expected_z) < 0.01

    def test_single_floor_building(self):
        commands = bps_to_blender_commands(_SMALL_OFFICE_BPS)
        floors = [c for c in commands if c["type"] == "create_object" and c["params"]["name"].startswith("Floor_")]
        assert len(floors) == 1


class TestBPSToZoneInfo:
    def test_large_office_core_perimeter(self):
        zones = bps_to_zone_info(_LARGE_OFFICE_BPS)
        # 12 floors × 5 zones (core + N/S/E/W) = 60
        assert len(zones) == 60
        core_zones = [z for z in zones if z["type"] == "core"]
        perim_zones = [z for z in zones if z["type"] == "perimeter"]
        assert len(core_zones) == 12
        assert len(perim_zones) == 48

    def test_small_office_single_zone(self):
        zones = bps_to_zone_info(_SMALL_OFFICE_BPS)
        assert len(zones) == 1
        assert zones[0]["type"] == "single"
        assert zones[0]["floor"] == 1

    def test_hospital_core_perimeter(self):
        zones = bps_to_zone_info(_HOSPITAL_BPS)
        # 5 floors × 5 zones = 25
        assert len(zones) == 25

    def test_zone_areas_sum_to_total(self):
        zones = bps_to_zone_info(_LARGE_OFFICE_BPS)
        total = sum(z["area_m2"] for z in zones)
        expected = _LARGE_OFFICE_BPS["building"]["floor_area_m2"]
        assert abs(total - expected) < 1.0  # floating point tolerance

    def test_zone_heights_match(self):
        zones = bps_to_zone_info(_LARGE_OFFICE_BPS)
        for z in zones:
            assert z["height_m"] == 3.96


# ── client tests (mocked TCP) ────────────────────────────────────────


class TestBlenderPool:
    @pytest.mark.asyncio
    async def test_connection_error_on_no_hosts(self):
        pool = BlenderPool(hosts=[("nonexistent", 19876)], timeout=2.0)
        with pytest.raises(BlenderConnectionError):
            await pool.execute({"type": "ping"})

    @pytest.mark.asyncio
    async def test_close_all_empty(self):
        pool = BlenderPool(hosts=[])
        await pool.close_all()  # should not raise
