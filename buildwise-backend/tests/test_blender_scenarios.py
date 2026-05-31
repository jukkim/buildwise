"""Predetermined scenario tests for the Blender MCP pipeline.

Every expected value is HARDCODED (hand-calculated from the formulas in
building_gen.py), NOT computed from the code under test.

Formulas reference (building_gen.py):
  per_floor_area = total_area / floors
  aspect = _ASPECT_RATIOS[building_type]
  width = sqrt(per_floor_area / aspect)
  length = per_floor_area / width
  core_area = (length - 2*4.57) * (width - 2*4.57)   [core+perim types]
  perim_area = (per_floor_area - core_area) / 4
  command_count = 1(clear) + F(floors) + F*4(windows) + 1(roof) + F(materials) + 1(glass)
  roof_z = floors * floor_height + 0.1
  window_height = floor_height * wwr
"""

from __future__ import annotations

import pytest

from app.services.blender.building_gen import bps_to_blender_commands, bps_to_zone_info
from app.services.blender.idf_converter import _zones_to_idf_objects
from app.services.blender.service import _fallback_parametric

# ── Tolerance ────────────────────────────────────────────────────────────

_ABS_TOL = 0.01  # 0.01 m2 for area, 0.01 m for height/position


# ══════════════════════════════════════════════════════════════════════════
# Group A -- Building Type Diversity
# ══════════════════════════════════════════════════════════════════════════


class TestGroupABuildingTypeDiversity:
    """A1-A4: Verify zone/command generation for each major building type."""

    # ── A1: Large office 12F (core+perimeter = 60 zones) ─────────────

    _A1_BPS = {
        "building": {
            "building_type": "large_office",
            "floors": 12,
            "floor_area_m2": 46320,
            "floor_height_m": 3.96,
        },
        "envelope": {"wwr": 0.4},
    }

    def test_a1_zone_count(self):
        zones = bps_to_zone_info(self._A1_BPS)
        assert len(zones) == 60

    def test_a1_core_zone_count(self):
        zones = bps_to_zone_info(self._A1_BPS)
        cores = [z for z in zones if z["type"] == "core"]
        assert len(cores) == 12

    def test_a1_perimeter_zone_count(self):
        zones = bps_to_zone_info(self._A1_BPS)
        perims = [z for z in zones if z["type"] == "perimeter"]
        assert len(perims) == 48

    def test_a1_core_area_per_floor(self):
        """core_area = (76.0920 - 2*4.57) * (50.7280 - 2*4.57) = 2784.40"""
        zones = bps_to_zone_info(self._A1_BPS)
        core_f1 = next(z for z in zones if z["name"] == "F1_Core")
        assert abs(core_f1["area_m2"] - 2784.40) < 0.1

    def test_a1_perimeter_area_per_floor(self):
        """perim_area = (3860 - 2784.40) / 4 = 268.90"""
        zones = bps_to_zone_info(self._A1_BPS)
        perim_f1_n = next(z for z in zones if z["name"] == "F1_N")
        assert abs(perim_f1_n["area_m2"] - 268.90) < 0.1

    def test_a1_zone_names_floor1(self):
        zones = bps_to_zone_info(self._A1_BPS)
        f1_names = [z["name"] for z in zones if z["floor"] == 1]
        assert f1_names == ["F1_Core", "F1_N", "F1_S", "F1_E", "F1_W"]

    def test_a1_zone_names_floor12(self):
        zones = bps_to_zone_info(self._A1_BPS)
        f12_names = [z["name"] for z in zones if z["floor"] == 12]
        assert f12_names == ["F12_Core", "F12_N", "F12_S", "F12_E", "F12_W"]

    def test_a1_command_count(self):
        """1 clear + 12 floors + 48 windows + 1 roof + 12 materials + 1 glass = 75"""
        commands = bps_to_blender_commands(self._A1_BPS)
        assert len(commands) == 75

    def test_a1_floor_height_uniform(self):
        zones = bps_to_zone_info(self._A1_BPS)
        for z in zones:
            assert z["height_m"] == 3.96

    def test_a1_roof_z(self):
        """roof_z = 12 * 3.96 + 0.1 = 47.62"""
        commands = bps_to_blender_commands(self._A1_BPS)
        roof = next(c for c in commands if c.get("params", {}).get("name") == "Roof")
        assert abs(roof["params"]["location"][2] - 47.62) < _ABS_TOL

    # ── A2: Small office 1F (single zone = 1 zone) ──────────────────

    _A2_BPS = {
        "building": {
            "building_type": "small_office",
            "floors": 1,
            "floor_area_m2": 511,
        },
        "envelope": {"wwr": 0.25},
    }

    def test_a2_zone_count(self):
        zones = bps_to_zone_info(self._A2_BPS)
        assert len(zones) == 1

    def test_a2_zone_type_single(self):
        zones = bps_to_zone_info(self._A2_BPS)
        assert zones[0]["type"] == "single"

    def test_a2_zone_name(self):
        zones = bps_to_zone_info(self._A2_BPS)
        assert zones[0]["name"] == "F1"

    def test_a2_zone_area(self):
        """Single zone area = total area = 511 m2"""
        zones = bps_to_zone_info(self._A2_BPS)
        assert abs(zones[0]["area_m2"] - 511.0) < _ABS_TOL

    def test_a2_default_floor_height(self):
        """small_office default height = 3.05 m"""
        zones = bps_to_zone_info(self._A2_BPS)
        assert zones[0]["height_m"] == 3.05

    def test_a2_command_count(self):
        """1 clear + 1 floor + 4 windows + 1 roof + 1 material + 1 glass = 9"""
        commands = bps_to_blender_commands(self._A2_BPS)
        assert len(commands) == 9

    def test_a2_window_height(self):
        """window_height = 3.05 * 0.25 = 0.7625"""
        commands = bps_to_blender_commands(self._A2_BPS)
        win = next(c for c in commands if c.get("params", {}).get("name", "").startswith("Win_"))
        # Window scale z = window_height / 2 = 0.38125
        assert abs(win["params"]["scale"][2] - 0.38125) < _ABS_TOL

    def test_a2_roof_z(self):
        """roof_z = 1 * 3.05 + 0.1 = 3.15"""
        commands = bps_to_blender_commands(self._A2_BPS)
        roof = next(c for c in commands if c.get("params", {}).get("name") == "Roof")
        assert abs(roof["params"]["location"][2] - 3.15) < _ABS_TOL

    # ── A3: Hospital 5F (core+perimeter = 25 zones) ─────────────────

    _A3_BPS = {
        "building": {
            "building_type": "hospital",
            "floors": 5,
            "floor_area_m2": 22422,
        },
        "envelope": {"wwr": 0.3},
    }

    def test_a3_zone_count(self):
        zones = bps_to_zone_info(self._A3_BPS)
        assert len(zones) == 25

    def test_a3_core_zone_count(self):
        zones = bps_to_zone_info(self._A3_BPS)
        cores = [z for z in zones if z["type"] == "core"]
        assert len(cores) == 5

    def test_a3_core_area_per_floor(self):
        """
        per_floor = 22422/5 = 4484.4
        aspect = 1.8
        width = sqrt(4484.4/1.8) = 49.9132...
        length = 4484.4/49.9132 = 89.8438...
        core = (89.8438 - 9.14) * (49.9132 - 9.14) = 80.7038 * 40.7732 = 3290.56
        """
        zones = bps_to_zone_info(self._A3_BPS)
        core_f1 = next(z for z in zones if z["name"] == "F1_Core")
        assert abs(core_f1["area_m2"] - 3290.56) < 0.1

    def test_a3_perimeter_area_per_floor(self):
        """perim = (4484.4 - 3290.56) / 4 = 298.46"""
        zones = bps_to_zone_info(self._A3_BPS)
        perim_f1_n = next(z for z in zones if z["name"] == "F1_N")
        assert abs(perim_f1_n["area_m2"] - 298.46) < 0.1

    def test_a3_default_floor_height(self):
        """hospital default = 3.96 m"""
        zones = bps_to_zone_info(self._A3_BPS)
        assert zones[0]["height_m"] == 3.96

    def test_a3_command_count(self):
        """1 clear + 5 floors + 20 windows + 1 roof + 5 materials + 1 glass = 33"""
        commands = bps_to_blender_commands(self._A3_BPS)
        assert len(commands) == 33

    def test_a3_roof_z(self):
        """roof_z = 5 * 3.96 + 0.1 = 19.90"""
        commands = bps_to_blender_commands(self._A3_BPS)
        roof = next(c for c in commands if c.get("params", {}).get("name") == "Roof")
        assert abs(roof["params"]["location"][2] - 19.90) < _ABS_TOL

    # ── A4: Standalone retail 1F 6.1m height (single zone, tall) ─────

    _A4_BPS = {
        "building": {
            "building_type": "standalone_retail",
            "floors": 1,
            "floor_area_m2": 2294,
        },
        "envelope": {"wwr": 0.35},
    }

    def test_a4_zone_count(self):
        """standalone_retail is NOT in (large_office, hospital) => single zone"""
        zones = bps_to_zone_info(self._A4_BPS)
        assert len(zones) == 1

    def test_a4_zone_type_single(self):
        zones = bps_to_zone_info(self._A4_BPS)
        assert zones[0]["type"] == "single"

    def test_a4_zone_area(self):
        zones = bps_to_zone_info(self._A4_BPS)
        assert abs(zones[0]["area_m2"] - 2294.0) < _ABS_TOL

    def test_a4_default_floor_height(self):
        """standalone_retail default = 6.1 m"""
        zones = bps_to_zone_info(self._A4_BPS)
        assert zones[0]["height_m"] == 6.1

    def test_a4_command_count(self):
        """1 clear + 1 floor + 4 windows + 1 roof + 1 material + 1 glass = 9"""
        commands = bps_to_blender_commands(self._A4_BPS)
        assert len(commands) == 9

    def test_a4_window_height(self):
        """window_height = 6.1 * 0.35 = 2.135; scale_z = 2.135/2 = 1.0675"""
        commands = bps_to_blender_commands(self._A4_BPS)
        win = next(c for c in commands if c.get("params", {}).get("name", "").startswith("Win_"))
        assert abs(win["params"]["scale"][2] - 1.0675) < _ABS_TOL

    def test_a4_floor_z_center(self):
        """z = 0 * 6.1 + 6.1/2 = 3.05"""
        commands = bps_to_blender_commands(self._A4_BPS)
        floor_cmd = next(c for c in commands if c.get("params", {}).get("name") == "Floor_1")
        assert abs(floor_cmd["params"]["location"][2] - 3.05) < _ABS_TOL

    def test_a4_roof_z(self):
        """roof_z = 1 * 6.1 + 0.1 = 6.20"""
        commands = bps_to_blender_commands(self._A4_BPS)
        roof = next(c for c in commands if c.get("params", {}).get("name") == "Roof")
        assert abs(roof["params"]["location"][2] - 6.20) < _ABS_TOL

    def test_a4_material_name(self):
        """standalone_retail material = Precast_Concrete"""
        commands = bps_to_blender_commands(self._A4_BPS)
        mat_cmds = [c for c in commands if c["type"] == "set_material"]
        assert len(mat_cmds) == 1
        assert mat_cmds[0]["params"]["material"] == "Precast_Concrete"


# ══════════════════════════════════════════════════════════════════════════
# Group B -- Edge Cases
# ══════════════════════════════════════════════════════════════════════════


class TestGroupBEdgeCases:
    """B5-B9: Edge cases that stress defaults and boundary conditions."""

    # ── B5: Minimum viable BPS (only building_type) ──────────────────

    _B5_BPS = {
        "building": {"building_type": "large_office"},
    }

    def test_b5_defaults_applied(self):
        """Defaults: floors=1, floor_area=5000, floor_height=3.96, wwr=0.4"""
        zones = bps_to_zone_info(self._B5_BPS)
        # large_office with 5000 m2 / 1 floor = 5000 per floor > 1000 => core+perim
        assert len(zones) == 5

    def test_b5_zone_names(self):
        zones = bps_to_zone_info(self._B5_BPS)
        names = [z["name"] for z in zones]
        assert names == ["F1_Core", "F1_N", "F1_S", "F1_E", "F1_W"]

    def test_b5_core_area(self):
        """
        per_floor = 5000, aspect = 1.5
        width = sqrt(5000/1.5) = 57.7350
        length = 5000/57.7350 = 86.6025
        core = (86.6025-9.14) * (57.7350-9.14) = 77.4625 * 48.5950 = 3764.29
        """
        zones = bps_to_zone_info(self._B5_BPS)
        core = next(z for z in zones if z["type"] == "core")
        assert abs(core["area_m2"] - 3764.29) < 0.1

    def test_b5_command_count(self):
        """1 clear + 1 floor + 4 windows + 1 roof + 1 material + 1 glass = 9"""
        commands = bps_to_blender_commands(self._B5_BPS)
        assert len(commands) == 9

    def test_b5_floor_height(self):
        zones = bps_to_zone_info(self._B5_BPS)
        assert zones[0]["height_m"] == 3.96

    # ── B6: Very tall building (20 floors) ───────────────────────────

    _B6_BPS = {
        "building": {
            "building_type": "large_office",
            "floors": 20,
            "floor_area_m2": 80000,
            "floor_height_m": 3.96,
        },
        "envelope": {"wwr": 0.4},
    }

    def test_b6_zone_count(self):
        """20 floors * 5 zones (per_floor=4000 > 1000) = 100"""
        zones = bps_to_zone_info(self._B6_BPS)
        assert len(zones) == 100

    def test_b6_command_count(self):
        """1 + 20 + 80 + 1 + 20 + 1 = 123"""
        commands = bps_to_blender_commands(self._B6_BPS)
        assert len(commands) == 123

    def test_b6_roof_z(self):
        """roof_z = 20 * 3.96 + 0.1 = 79.30"""
        commands = bps_to_blender_commands(self._B6_BPS)
        roof = next(c for c in commands if c.get("params", {}).get("name") == "Roof")
        assert abs(roof["params"]["location"][2] - 79.30) < _ABS_TOL

    def test_b6_top_floor_z(self):
        """Floor_20 z = 19 * 3.96 + 3.96/2 = 75.24 + 1.98 = 77.22"""
        commands = bps_to_blender_commands(self._B6_BPS)
        f20 = next(c for c in commands if c.get("params", {}).get("name") == "Floor_20")
        assert abs(f20["params"]["location"][2] - 77.22) < _ABS_TOL

    def test_b6_core_area(self):
        """
        per_floor = 4000, aspect = 1.5
        width = sqrt(4000/1.5) = 51.6397
        length = 4000/51.6397 = 77.4596
        core = (77.4596-9.14) * (51.6397-9.14) = 68.3196 * 42.4997 = 2903.57
        """
        zones = bps_to_zone_info(self._B6_BPS)
        core = next(z for z in zones if z["name"] == "F1_Core")
        assert abs(core["area_m2"] - 2903.57) < 0.1

    # ── B7: Very small area (100 m2) ─────────────────────────────────

    _B7_BPS = {
        "building": {
            "building_type": "small_office",
            "floors": 1,
            "floor_area_m2": 100,
        },
        "envelope": {"wwr": 0.4},
    }

    def test_b7_zone_count(self):
        zones = bps_to_zone_info(self._B7_BPS)
        assert len(zones) == 1

    def test_b7_zone_area(self):
        zones = bps_to_zone_info(self._B7_BPS)
        assert abs(zones[0]["area_m2"] - 100.0) < _ABS_TOL

    def test_b7_dimensions(self):
        """
        width = sqrt(100/1.5) = 8.1649
        length = 100/8.1649 = 12.2474
        Floor_1 scale = [length/2, width/2, h/2] = [6.1237, 4.0824, 1.525]
        """
        commands = bps_to_blender_commands(self._B7_BPS)
        f1 = next(c for c in commands if c.get("params", {}).get("name") == "Floor_1")
        assert abs(f1["params"]["scale"][0] - 6.1237) < _ABS_TOL
        assert abs(f1["params"]["scale"][1] - 4.0824) < _ABS_TOL
        assert abs(f1["params"]["scale"][2] - 1.525) < _ABS_TOL

    # ── B8: Maximum WWR (0.95) ───────────────────────────────────────

    _B8_BPS = {
        "building": {
            "building_type": "large_office",
            "floors": 3,
            "floor_area_m2": 15000,
            "floor_height_m": 3.96,
        },
        "envelope": {"wwr": 0.95},
    }

    def test_b8_window_height(self):
        """window_height = 3.96 * 0.95 = 3.762; scale_z = 3.762/2 = 1.881"""
        commands = bps_to_blender_commands(self._B8_BPS)
        win = next(c for c in commands if c.get("params", {}).get("name", "").startswith("Win_"))
        assert abs(win["params"]["scale"][2] - 1.881) < _ABS_TOL

    def test_b8_zone_count(self):
        """3 floors * 5 zones (per_floor=5000 > 1000) = 15"""
        zones = bps_to_zone_info(self._B8_BPS)
        assert len(zones) == 15

    def test_b8_command_count(self):
        """1 + 3 + 12 + 1 + 3 + 1 = 21"""
        commands = bps_to_blender_commands(self._B8_BPS)
        assert len(commands) == 21

    # ── B9: Zero WWR (0.0) ───────────────────────────────────────────

    _B9_BPS = {
        "building": {
            "building_type": "small_office",
            "floors": 2,
            "floor_area_m2": 1000,
            "floor_height_m": 3.05,
        },
        "envelope": {"wwr": 0.0},
    }

    def test_b9_zero_window_height(self):
        """window_height = 3.05 * 0.0 = 0.0; scale_z = 0.0"""
        commands = bps_to_blender_commands(self._B9_BPS)
        wins = [c for c in commands if c.get("params", {}).get("name", "").startswith("Win_")]
        for w in wins:
            assert abs(w["params"]["scale"][2]) < _ABS_TOL

    def test_b9_windows_still_created(self):
        """Even with WWR=0, window objects are still created (zero height)."""
        commands = bps_to_blender_commands(self._B9_BPS)
        wins = [c for c in commands if c.get("params", {}).get("name", "").startswith("Win_")]
        # 2 floors * 4 directions = 8
        assert len(wins) == 8

    def test_b9_zone_count(self):
        zones = bps_to_zone_info(self._B9_BPS)
        assert len(zones) == 2

    def test_b9_command_count(self):
        """1 + 2 + 8 + 1 + 2 + 1 = 15"""
        commands = bps_to_blender_commands(self._B9_BPS)
        assert len(commands) == 15


# ══════════════════════════════════════════════════════════════════════════
# Group C -- Physical Consistency
# ══════════════════════════════════════════════════════════════════════════


class TestGroupCPhysicalConsistency:
    """C10-C13: Invariants that must hold for any valid BPS."""

    # Shared BPS set for multi-type validation
    _ALL_BPS = [
        {
            "building": {
                "building_type": "large_office",
                "floors": 12,
                "floor_area_m2": 46320,
                "floor_height_m": 3.96,
            },
            "envelope": {"wwr": 0.4},
        },
        {
            "building": {
                "building_type": "small_office",
                "floors": 1,
                "floor_area_m2": 511,
            },
            "envelope": {"wwr": 0.25},
        },
        {
            "building": {
                "building_type": "hospital",
                "floors": 5,
                "floor_area_m2": 22422,
            },
            "envelope": {"wwr": 0.3},
        },
        {
            "building": {
                "building_type": "standalone_retail",
                "floors": 1,
                "floor_area_m2": 2294,
            },
            "envelope": {"wwr": 0.35},
        },
        {
            "building": {
                "building_type": "medium_office",
                "floors": 3,
                "floor_area_m2": 4982,
                "floor_height_m": 3.96,
            },
            "envelope": {"wwr": 0.4},
        },
        {
            "building": {
                "building_type": "primary_school",
                "floors": 1,
                "floor_area_m2": 6871,
            },
            "envelope": {"wwr": 0.35},
        },
    ]

    # ── C10: Zone areas sum to total_floor_area_m2 ───────────────────

    @pytest.mark.parametrize("bps", _ALL_BPS, ids=lambda b: b["building"]["building_type"])
    def test_c10_zone_areas_sum_to_total(self, bps):
        zones = bps_to_zone_info(bps)
        total = sum(z["area_m2"] for z in zones)
        expected = bps["building"]["floor_area_m2"]
        assert abs(total - expected) < 0.1, f"Zone area sum {total:.2f} != total_floor_area {expected}"

    # ── C11: Floor z-positions monotonically increasing ──────────────

    @pytest.mark.parametrize("bps", _ALL_BPS, ids=lambda b: b["building"]["building_type"])
    def test_c11_floor_z_monotonic(self, bps):
        commands = bps_to_blender_commands(bps)
        floor_cmds = sorted(
            [c for c in commands if c.get("params", {}).get("name", "").startswith("Floor_")],
            key=lambda c: int(c["params"]["name"].split("_")[1]),
        )
        z_positions = [c["params"]["location"][2] for c in floor_cmds]
        for i in range(1, len(z_positions)):
            assert z_positions[i] > z_positions[i - 1], (
                f"Floor z not monotonic: z[{i}]={z_positions[i]} <= z[{i - 1}]={z_positions[i - 1]}"
            )

    # ── C12: Roof z > top floor z ────────────────────────────────────

    @pytest.mark.parametrize("bps", _ALL_BPS, ids=lambda b: b["building"]["building_type"])
    def test_c12_roof_above_top_floor(self, bps):
        commands = bps_to_blender_commands(bps)
        floor_cmds = [c for c in commands if c.get("params", {}).get("name", "").startswith("Floor_")]
        top_floor_z = max(c["params"]["location"][2] for c in floor_cmds)
        roof = next(c for c in commands if c.get("params", {}).get("name") == "Roof")
        roof_z = roof["params"]["location"][2]
        assert roof_z > top_floor_z, f"Roof z {roof_z} not above top floor z {top_floor_z}"

    # ── C13: Window count = floors * 4 ───────────────────────────────

    @pytest.mark.parametrize("bps", _ALL_BPS, ids=lambda b: b["building"]["building_type"])
    def test_c13_window_count(self, bps):
        commands = bps_to_blender_commands(bps)
        wins = [c for c in commands if c.get("params", {}).get("name", "").startswith("Win_")]
        floors = bps["building"].get("floors", 1)
        assert len(wins) == floors * 4, f"Window count {len(wins)} != {floors}*4 = {floors * 4}"

    # ── C13b: Window directions per floor ────────────────────────────

    @pytest.mark.parametrize("bps", _ALL_BPS, ids=lambda b: b["building"]["building_type"])
    def test_c13b_window_directions(self, bps):
        """Each floor must have exactly N, S, E, W windows."""
        commands = bps_to_blender_commands(bps)
        wins = [c for c in commands if c.get("params", {}).get("name", "").startswith("Win_")]
        floors = bps["building"].get("floors", 1)
        for i in range(floors):
            floor_wins = [w for w in wins if w["params"]["name"].startswith(f"Win_F{i + 1}_")]
            directions = sorted(w["params"]["name"].split("_")[-1] for w in floor_wins)
            assert directions == ["E", "N", "S", "W"], f"Floor {i + 1} window directions: {directions}"


# ══════════════════════════════════════════════════════════════════════════
# Group D -- Fallback Path
# ══════════════════════════════════════════════════════════════════════════


class TestGroupDFallbackPath:
    """D14-D15: Fallback behavior when Blender is unreachable."""

    _D_BPS = {
        "building": {
            "building_type": "large_office",
            "floors": 12,
            "floor_area_m2": 46320,
            "floor_height_m": 3.96,
        },
        "envelope": {"wwr": 0.4},
    }

    # ── D14: Fallback result structure ───────────────────────────────

    def test_d14_fallback_source(self):
        result = _fallback_parametric(self._D_BPS, "test-building-001")
        assert result.source == "fallback"

    def test_d14_fallback_no_model_url(self):
        result = _fallback_parametric(self._D_BPS, "test-building-001")
        assert result.model_url == ""

    def test_d14_fallback_no_idf(self):
        result = _fallback_parametric(self._D_BPS, "test-building-001")
        assert result.idf_content is None

    def test_d14_fallback_has_zones(self):
        result = _fallback_parametric(self._D_BPS, "test-building-001")
        assert len(result.zones) == 60

    # ── D15: Fallback zones match direct bps_to_zone_info ────────────

    def test_d15_fallback_zones_match_direct(self):
        """Fallback zones must be identical to direct bps_to_zone_info output."""
        direct_zones = bps_to_zone_info(self._D_BPS)
        fallback_result = _fallback_parametric(self._D_BPS, "test-building-001")
        fallback_zones = fallback_result.zones

        assert len(fallback_zones) == len(direct_zones)
        for dz, fz in zip(direct_zones, fallback_zones):
            assert dz["name"] == fz["name"]
            assert abs(dz["area_m2"] - fz["area_m2"]) < _ABS_TOL
            assert dz["height_m"] == fz["height_m"]
            assert dz["type"] == fz["type"]
            assert dz["floor"] == fz["floor"]


# ══════════════════════════════════════════════════════════════════════════
# Group E -- IDF Converter
# ══════════════════════════════════════════════════════════════════════════


class TestGroupEIDFConverter:
    """E16-E19: _zones_to_idf_objects generates correct IDF Zone entries."""

    def test_e16_idf_zone_count_large_office(self):
        """60 zones => 60 'Zone,' entries in IDF text."""
        bps = {
            "building": {
                "building_type": "large_office",
                "floors": 12,
                "floor_area_m2": 46320,
                "floor_height_m": 3.96,
            },
            "envelope": {"wwr": 0.4},
        }
        zones = bps_to_zone_info(bps)
        idf_text = _zones_to_idf_objects(zones)
        zone_count = idf_text.count("\nZone,")
        assert zone_count == 60

    def test_e17_idf_zone_count_single(self):
        """1 zone => 1 'Zone,' entry."""
        bps = {
            "building": {
                "building_type": "small_office",
                "floors": 1,
                "floor_area_m2": 511,
            },
            "envelope": {"wwr": 0.25},
        }
        zones = bps_to_zone_info(bps)
        idf_text = _zones_to_idf_objects(zones)
        zone_count = idf_text.count("\nZone,")
        assert zone_count == 1

    def test_e18_idf_zone_names_present(self):
        """Each zone name must appear in the IDF output."""
        bps = {
            "building": {
                "building_type": "hospital",
                "floors": 5,
                "floor_area_m2": 22422,
            },
            "envelope": {"wwr": 0.3},
        }
        zones = bps_to_zone_info(bps)
        idf_text = _zones_to_idf_objects(zones)
        for z in zones:
            assert z["name"] in idf_text, f"Zone name '{z['name']}' not found in IDF"

    def test_e19_idf_z_base_per_floor(self):
        """Floor N should have z_base = (N-1) * height_m in the IDF Zone origin."""
        bps = {
            "building": {
                "building_type": "small_office",
                "floors": 3,
                "floor_area_m2": 1500,
                "floor_height_m": 3.05,
            },
        }
        zones = bps_to_zone_info(bps)
        idf_text = _zones_to_idf_objects(zones)
        # z_base = floor_idx * height where floor_idx = floor - 1
        # F1: 0 * 3.05 = 0.0  (Python float => "0.0")
        # F2: 1 * 3.05 = 3.05
        # F3: 2 * 3.05 = 6.1
        assert "0, 0, 0.0," in idf_text  # F1
        assert "0, 0, 3.05," in idf_text  # F2
        assert "0, 0, 6.1," in idf_text  # F3


# ══════════════════════════════════════════════════════════════════════════
# Group F -- Special Zone Logic
# ══════════════════════════════════════════════════════════════════════════


class TestGroupFSpecialZoneLogic:
    """F20-F24: Core+perimeter threshold and edge behavior."""

    def test_f20_large_office_below_threshold_gets_single_zone(self):
        """large_office with per_floor_area <= 1000 => single zone (not core+perim)."""
        bps = {
            "building": {
                "building_type": "large_office",
                "floors": 10,
                "floor_area_m2": 5000,  # per_floor = 500 < 1000
            },
            "envelope": {"wwr": 0.4},
        }
        zones = bps_to_zone_info(bps)
        # 10 floors * 1 zone = 10 (not 10*5=50)
        assert len(zones) == 10
        for z in zones:
            assert z["type"] == "single"

    def test_f21_hospital_at_threshold_boundary(self):
        """hospital with per_floor_area exactly 1001 => core+perimeter."""
        bps = {
            "building": {
                "building_type": "hospital",
                "floors": 1,
                "floor_area_m2": 1001,
            },
        }
        zones = bps_to_zone_info(bps)
        assert len(zones) == 5
        types = {z["type"] for z in zones}
        assert types == {"core", "perimeter"}

    def test_f22_hospital_at_threshold_exactly_1000(self):
        """hospital with per_floor_area exactly 1000 => single zone (not > 1000)."""
        bps = {
            "building": {
                "building_type": "hospital",
                "floors": 1,
                "floor_area_m2": 1000,
            },
        }
        zones = bps_to_zone_info(bps)
        assert len(zones) == 1
        assert zones[0]["type"] == "single"

    def test_f23_medium_office_always_single(self):
        """medium_office is NOT in (large_office, hospital) => always single zone."""
        bps = {
            "building": {
                "building_type": "medium_office",
                "floors": 3,
                "floor_area_m2": 15000,  # per_floor = 5000, well above 1000
            },
        }
        zones = bps_to_zone_info(bps)
        assert len(zones) == 3
        for z in zones:
            assert z["type"] == "single"

    def test_f24_unknown_building_type_uses_defaults(self):
        """Unknown building_type uses default aspect=1.5, height=3.5, single zone."""
        bps = {
            "building": {
                "building_type": "warehouse",
                "floors": 1,
                "floor_area_m2": 5000,
            },
        }
        zones = bps_to_zone_info(bps)
        assert len(zones) == 1
        assert zones[0]["type"] == "single"
        assert zones[0]["height_m"] == 3.5
        assert abs(zones[0]["area_m2"] - 5000.0) < _ABS_TOL


# ══════════════════════════════════════════════════════════════════════════
# Group G -- Command Structure Verification
# ══════════════════════════════════════════════════════════════════════════


class TestGroupGCommandStructure:
    """G25-G30: Command ordering and type-specific content."""

    _G_BPS = {
        "building": {
            "building_type": "hospital",
            "floors": 3,
            "floor_area_m2": 15000,
            "floor_height_m": 3.96,
        },
        "envelope": {"wwr": 0.4},
    }

    def test_g25_first_command_is_clear(self):
        commands = bps_to_blender_commands(self._G_BPS)
        assert commands[0]["type"] == "execute_script"
        assert "select_all" in commands[0]["params"]["script"]
        assert "delete" in commands[0]["params"]["script"]

    def test_g26_last_command_is_glass_material(self):
        commands = bps_to_blender_commands(self._G_BPS)
        assert commands[-1]["type"] == "execute_script"
        assert "Glass_Window" in commands[-1]["params"]["script"]

    def test_g27_material_count_equals_floors(self):
        commands = bps_to_blender_commands(self._G_BPS)
        mat_cmds = [c for c in commands if c["type"] == "set_material"]
        assert len(mat_cmds) == 3  # 3 floors

    def test_g28_hospital_material_name(self):
        commands = bps_to_blender_commands(self._G_BPS)
        mat_cmds = [c for c in commands if c["type"] == "set_material"]
        for m in mat_cmds:
            assert m["params"]["material"] == "White_Panel"
            assert m["params"]["color"] == [0.88, 0.91, 0.96]

    def test_g29_floor_scale_dimensions(self):
        """
        per_floor = 5000, aspect = 1.8
        width = sqrt(5000/1.8) = 52.7046
        length = 5000/52.7046 = 94.8683
        Floor scale = [length/2, width/2, h/2] = [47.4341, 26.3523, 1.98]
        """
        commands = bps_to_blender_commands(self._G_BPS)
        f1 = next(c for c in commands if c.get("params", {}).get("name") == "Floor_1")
        assert abs(f1["params"]["scale"][0] - 47.4341) < _ABS_TOL
        assert abs(f1["params"]["scale"][1] - 26.3523) < _ABS_TOL
        assert abs(f1["params"]["scale"][2] - 1.98) < _ABS_TOL

    def test_g30_roof_oversized_by_02(self):
        """Roof scale has +0.2 overhang: [length/2+0.2, width/2+0.2, 0.1]"""
        commands = bps_to_blender_commands(self._G_BPS)
        roof = next(c for c in commands if c.get("params", {}).get("name") == "Roof")
        # length/2 + 0.2 = 47.4341 + 0.2 = 47.6341
        # width/2 + 0.2 = 26.3523 + 0.2 = 26.5523
        assert abs(roof["params"]["scale"][0] - 47.6341) < _ABS_TOL
        assert abs(roof["params"]["scale"][1] - 26.5523) < _ABS_TOL
        assert abs(roof["params"]["scale"][2] - 0.1) < _ABS_TOL
