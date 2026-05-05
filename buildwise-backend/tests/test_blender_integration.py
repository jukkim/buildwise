"""Integration tests for the Blender MCP → IDF pipeline.

Tests the full chain: BPS → zone extraction → IDF generation
(without a live Blender instance — uses building_gen zone info directly
and validates IDF output via ems_bridge).
"""

from __future__ import annotations

import pytest

from app.services.blender.building_gen import bps_to_blender_commands, bps_to_zone_info
from app.services.blender.idf_converter import _zones_to_idf_objects


# ── Test BPS fixtures (all 6 DOE building types) ─────────────────────

_BPS_FIXTURES: dict[str, dict] = {
    "large_office": {
        "building": {
            "building_type": "large_office",
            "floors": 12,
            "floor_area_m2": 46320,
            "floor_height_m": 3.96,
        },
        "envelope": {"wwr": 0.4},
        "hvac": {"system_type": "vav_chiller_boiler"},
    },
    "medium_office": {
        "building": {
            "building_type": "medium_office",
            "floors": 3,
            "floor_area_m2": 4982,
            "floor_height_m": 3.96,
        },
        "envelope": {"wwr": 0.33},
        "hvac": {"system_type": "vrf"},
    },
    "small_office": {
        "building": {
            "building_type": "small_office",
            "floors": 1,
            "floor_area_m2": 511,
            "floor_height_m": 3.05,
        },
        "envelope": {"wwr": 0.25},
        "hvac": {"system_type": "psz_hp"},
    },
    "standalone_retail": {
        "building": {
            "building_type": "standalone_retail",
            "floors": 1,
            "floor_area_m2": 2294,
            "floor_height_m": 6.1,
        },
        "envelope": {"wwr": 0.07},
        "hvac": {"system_type": "psz_ac"},
    },
    "primary_school": {
        "building": {
            "building_type": "primary_school",
            "floors": 1,
            "floor_area_m2": 6871,
            "floor_height_m": 4.0,
        },
        "envelope": {"wwr": 0.35},
        "hvac": {"system_type": "vav_chiller_boiler_school"},
    },
    "hospital": {
        "building": {
            "building_type": "hospital",
            "floors": 5,
            "floor_area_m2": 22422,
            "floor_height_m": 3.96,
        },
        "envelope": {"wwr": 0.3},
        "hvac": {"system_type": "vav_chiller_boiler"},
    },
}


class TestAllBuildingTypes3DGeneration:
    """Verify all 6 DOE building types produce valid 3D commands and zones."""

    @pytest.mark.parametrize("btype", list(_BPS_FIXTURES.keys()))
    def test_commands_generated(self, btype: str):
        bps = _BPS_FIXTURES[btype]
        commands = bps_to_blender_commands(bps)
        assert len(commands) > 0

        # Must start with clear
        assert commands[0]["type"] == "execute_script"

        # Must have at least 1 floor
        floors = [c for c in commands if c.get("params", {}).get("name", "").startswith("Floor_")]
        expected_floors = bps["building"]["floors"]
        assert len(floors) == expected_floors

    @pytest.mark.parametrize("btype", list(_BPS_FIXTURES.keys()))
    def test_zones_generated(self, btype: str):
        bps = _BPS_FIXTURES[btype]
        zones = bps_to_zone_info(bps)
        assert len(zones) > 0

        # Total area should approximately match
        total_zone_area = sum(z["area_m2"] for z in zones)
        expected_area = bps["building"]["floor_area_m2"]
        assert abs(total_zone_area - expected_area) < 2.0

    @pytest.mark.parametrize("btype", list(_BPS_FIXTURES.keys()))
    def test_zone_names_unique(self, btype: str):
        bps = _BPS_FIXTURES[btype]
        zones = bps_to_zone_info(bps)
        names = [z["name"] for z in zones]
        assert len(names) == len(set(names))


class TestZoneToIDFObjects:
    """Verify zone → IDF text conversion produces valid Zone objects."""

    @pytest.mark.parametrize("btype", list(_BPS_FIXTURES.keys()))
    def test_idf_zone_objects(self, btype: str):
        bps = _BPS_FIXTURES[btype]
        zones = bps_to_zone_info(bps)
        idf_text = _zones_to_idf_objects(zones)

        # Should contain Zone objects
        assert "Zone," in idf_text

        # Should have one Zone declaration per zone
        zone_count = idf_text.count("Zone,")
        assert zone_count == len(zones)


class TestCorePlusPeimeterLayout:
    """Verify core + perimeter zone splitting for large buildings."""

    def test_large_office_5_zones_per_floor(self):
        bps = _BPS_FIXTURES["large_office"]
        zones = bps_to_zone_info(bps)
        floors = bps["building"]["floors"]

        core_zones = [z for z in zones if z["type"] == "core"]
        perim_zones = [z for z in zones if z["type"] == "perimeter"]

        assert len(core_zones) == floors
        assert len(perim_zones) == floors * 4

    def test_small_office_single_zone(self):
        bps = _BPS_FIXTURES["small_office"]
        zones = bps_to_zone_info(bps)
        assert len(zones) == 1
        assert zones[0]["type"] == "single"

    def test_perimeter_directions(self):
        bps = _BPS_FIXTURES["large_office"]
        zones = bps_to_zone_info(bps)
        perim_zones = [z for z in zones if z["type"] == "perimeter"]

        directions = {z["direction"] for z in perim_zones}
        assert directions == {"N", "S", "E", "W"}

    def test_core_area_smaller_than_floor(self):
        bps = _BPS_FIXTURES["large_office"]
        zones = bps_to_zone_info(bps)
        per_floor_area = bps["building"]["floor_area_m2"] / bps["building"]["floors"]

        floor1_core = [z for z in zones if z["floor"] == 1 and z["type"] == "core"]
        assert len(floor1_core) == 1
        assert floor1_core[0]["area_m2"] < per_floor_area


class TestBlenderCommandGeometry:
    """Verify 3D command geometry is physically correct."""

    def test_floor_heights_ascending(self):
        bps = _BPS_FIXTURES["large_office"]
        commands = bps_to_blender_commands(bps)
        floors = [
            c for c in commands
            if c["type"] == "create_object" and c["params"]["name"].startswith("Floor_")
        ]
        z_positions = [f["params"]["location"][2] for f in floors]
        assert z_positions == sorted(z_positions)
        assert z_positions[0] > 0

    def test_windows_on_all_four_sides(self):
        bps = _BPS_FIXTURES["medium_office"]
        commands = bps_to_blender_commands(bps)
        floor1_wins = [
            c for c in commands
            if c["type"] == "create_object" and c["params"]["name"].startswith("Win_F1_")
        ]
        directions = {c["params"]["name"].split("_")[-1] for c in floor1_wins}
        assert directions == {"N", "S", "E", "W"}

    def test_roof_above_top_floor(self):
        bps = _BPS_FIXTURES["hospital"]
        commands = bps_to_blender_commands(bps)
        floors = [
            c for c in commands
            if c["type"] == "create_object" and c["params"]["name"].startswith("Floor_")
        ]
        roof = [
            c for c in commands
            if c["type"] == "create_object" and c["params"]["name"] == "Roof"
        ]
        top_floor_z = floors[-1]["params"]["location"][2]
        roof_z = roof[0]["params"]["location"][2]
        assert roof_z > top_floor_z
