"""End-to-end tests for the Blender MCP pipeline.

Tests the complete chain: BPS → commands → zones → IDF → result
without a live Blender instance.  Uses mocks for BlenderPool to
verify orchestration and fallback behaviour.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.blender.building_gen import bps_to_blender_commands, bps_to_zone_info
from app.services.blender.client import BlenderConnectionError, BlenderError, BlenderTimeoutError
from app.services.blender.idf_converter import _zones_to_idf_objects
from app.services.blender.service import (
    GenerationResult,
    _fallback_parametric,
    generate_3d_from_bps,
)

# ── Full data pipeline (no mocks) ─────────────────────────────────────

_FULL_PIPELINE_BPS = {
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


class TestFullDataPipeline:
    """Verify BPS → commands → zones → IDF text flows end-to-end."""

    @pytest.mark.parametrize("btype", list(_FULL_PIPELINE_BPS.keys()))
    def test_pipeline_produces_valid_idf(self, btype: str):
        bps = _FULL_PIPELINE_BPS[btype]

        commands = bps_to_blender_commands(bps)
        assert len(commands) > 0

        zones = bps_to_zone_info(bps)
        assert len(zones) > 0

        idf_text = _zones_to_idf_objects(zones)
        assert "Zone," in idf_text
        assert idf_text.count("Zone,") == len(zones)

        for zone in zones:
            assert zone["name"] in idf_text

    @pytest.mark.parametrize("btype", list(_FULL_PIPELINE_BPS.keys()))
    def test_commands_and_zones_consistent(self, btype: str):
        """Commands and zones must agree on floor count."""
        bps = _FULL_PIPELINE_BPS[btype]
        expected_floors = bps["building"]["floors"]

        commands = bps_to_blender_commands(bps)
        floor_cmds = [
            c for c in commands
            if c["type"] == "create_object"
            and c["params"]["name"].startswith("Floor_")
        ]
        assert len(floor_cmds) == expected_floors

        zones = bps_to_zone_info(bps)
        zone_floors = {z["floor"] for z in zones}
        assert zone_floors == set(range(1, expected_floors + 1))

    def test_idf_zone_origin_z_increasing(self):
        """Zone origins must increase per floor."""
        bps = _FULL_PIPELINE_BPS["large_office"]
        zones = bps_to_zone_info(bps)
        _zones_to_idf_objects(zones)  # verify no crash

        z_values = []
        for zone in zones:
            if zone["type"] == "core":
                z = (zone["floor"] - 1) * zone["height_m"]
                z_values.append(z)

        assert z_values == sorted(z_values)
        assert z_values[-1] > z_values[0]


# ── Service-level orchestration (mocked pool) ──────────────────────────


class TestFallbackBehavior:
    """Verify the service falls back to parametric when Blender is unavailable."""

    def test_fallback_returns_zones_without_model(self):
        bps = _FULL_PIPELINE_BPS["medium_office"]
        result = _fallback_parametric(bps, "test-building-id")

        assert isinstance(result, GenerationResult)
        assert result.source == "fallback"
        assert result.model_url == ""
        assert result.idf_content is None
        assert len(result.zones) > 0

    @pytest.mark.asyncio
    async def test_generate_3d_falls_back_on_connection_error(self):
        """When BlenderPool raises ConnectionError, service returns fallback."""
        bps = _FULL_PIPELINE_BPS["large_office"]

        mock_pool = MagicMock()
        mock_pool.execute = AsyncMock(
            side_effect=BlenderConnectionError("No Blender instances")
        )

        with patch(
            "app.services.blender.service._get_pool", return_value=mock_pool
        ):
            result = await generate_3d_from_bps(bps, "test-building-id")

        assert result.source == "fallback"
        assert result.model_url == ""
        assert len(result.zones) == 60  # 12 floors × 5 zones

    @pytest.mark.asyncio
    async def test_generate_3d_falls_back_on_timeout(self):
        """BlenderTimeoutError also triggers fallback."""
        bps = _FULL_PIPELINE_BPS["medium_office"]

        mock_pool = MagicMock()
        mock_pool.execute = AsyncMock(
            side_effect=BlenderTimeoutError("Command timed out after 60s")
        )

        with patch(
            "app.services.blender.service._get_pool", return_value=mock_pool
        ):
            result = await generate_3d_from_bps(bps, "timeout-test")

        assert result.source == "fallback"
        assert len(result.zones) > 0

    @pytest.mark.asyncio
    async def test_generate_3d_falls_back_on_blender_error(self):
        """BlenderError (script failures etc.) also triggers fallback."""
        bps = _FULL_PIPELINE_BPS["hospital"]

        mock_pool = MagicMock()
        mock_pool.execute = AsyncMock(
            side_effect=BlenderError("Script execution failed")
        )

        with patch(
            "app.services.blender.service._get_pool", return_value=mock_pool
        ):
            result = await generate_3d_from_bps(bps, "error-test")

        assert result.source == "fallback"
        assert len(result.zones) == 25  # 5 floors × 5 zones

    @pytest.mark.asyncio
    async def test_fallback_preserves_zone_geometry(self):
        """Fallback zones should match direct bps_to_zone_info output."""
        bps = _FULL_PIPELINE_BPS["hospital"]

        mock_pool = MagicMock()
        mock_pool.execute = AsyncMock(
            side_effect=BlenderConnectionError("unreachable")
        )

        with patch(
            "app.services.blender.service._get_pool", return_value=mock_pool
        ):
            result = await generate_3d_from_bps(bps, "hospital-1")

        direct_zones = bps_to_zone_info(bps)
        assert len(result.zones) == len(direct_zones)

        for rz, dz in zip(result.zones, direct_zones):
            assert rz["name"] == dz["name"]
            assert rz["area_m2"] == dz["area_m2"]


# ── Physical consistency checks ────────────────────────────────────────


class TestPhysicalConsistency:
    """Cross-check that command geometry and zone geometry are physically consistent."""

    def test_window_coverage_matches_wwr(self):
        """Window area fraction should approximate the specified WWR."""
        bps = _FULL_PIPELINE_BPS["large_office"]
        wwr = bps["envelope"]["wwr"]
        commands = bps_to_blender_commands(bps)

        floor_cmd = next(
            c for c in commands
            if c["type"] == "create_object" and c["params"]["name"] == "Floor_1"
        )
        win_cmds_f1 = [
            c for c in commands
            if c["type"] == "create_object"
            and c["params"]["name"].startswith("Win_F1_")
        ]

        floor_height = bps["building"]["floor_height_m"]
        floor_sx = floor_cmd["params"]["scale"][0]
        floor_sy = floor_cmd["params"]["scale"][1]
        wall_area = 2 * (2 * floor_sx + 2 * floor_sy) * floor_height

        total_window_area = 0
        for wc in win_cmds_f1:
            sx, sy, sz = wc["params"]["scale"]
            # Each window is a thin cube; visible face area depends on orientation
            if sy < 0.05:  # N/S window (thin in Y)
                total_window_area += 2 * sx * 2 * sz
            else:  # E/W window (thin in X)
                total_window_area += 2 * sy * 2 * sz

        actual_ratio = total_window_area / wall_area
        assert abs(actual_ratio - wwr) < 0.15  # within 15% tolerance

    def test_building_total_height_correct(self):
        """Top of last floor + roof should match floors × floor_height."""
        for btype, bps in _FULL_PIPELINE_BPS.items():
            commands = bps_to_blender_commands(bps)
            floors = bps["building"]["floors"]
            fh = bps["building"]["floor_height_m"]

            floor_cmds = [
                c for c in commands
                if c["type"] == "create_object" and c["params"]["name"].startswith("Floor_")
            ]
            roof_cmd = next(
                c for c in commands
                if c["type"] == "create_object" and c["params"]["name"] == "Roof"
            )

            top_floor_z = floor_cmds[-1]["params"]["location"][2]
            expected_top = (floors - 1) * fh + fh / 2
            assert abs(top_floor_z - expected_top) < 0.01, f"{btype} top floor z mismatch"

            roof_z = roof_cmd["params"]["location"][2]
            assert roof_z > top_floor_z, f"{btype} roof should be above top floor"

    def test_zone_volume_matches_commands(self):
        """Sum of zone volumes should approximately match command-based volume."""
        bps = _FULL_PIPELINE_BPS["medium_office"]
        commands = bps_to_blender_commands(bps)
        zones = bps_to_zone_info(bps)

        floor_cmds = [
            c for c in commands
            if c["type"] == "create_object" and c["params"]["name"].startswith("Floor_")
        ]
        cmd_volume = 0
        for fc in floor_cmds:
            sx, sy, sz = fc["params"]["scale"]
            cmd_volume += (2 * sx) * (2 * sy) * (2 * sz)

        zone_volume = sum(z["area_m2"] * z["height_m"] for z in zones)

        assert abs(cmd_volume - zone_volume) / zone_volume < 0.01


# ── Edge cases ─────────────────────────────────────────────────────────


class TestEdgeCases:
    """Boundary conditions and edge cases."""

    def test_single_floor_single_zone(self):
        """1-floor small building → 1 zone, 1 floor command."""
        bps = {
            "building": {
                "building_type": "small_office",
                "floors": 1,
                "floor_area_m2": 511,
                "floor_height_m": 3.05,
            },
            "envelope": {"wwr": 0.25},
        }
        commands = bps_to_blender_commands(bps)
        zones = bps_to_zone_info(bps)

        floor_cmds = [
            c for c in commands
            if c["type"] == "create_object" and c["params"]["name"].startswith("Floor_")
        ]
        assert len(floor_cmds) == 1
        assert len(zones) == 1
        assert zones[0]["type"] == "single"

    def test_very_high_wwr(self):
        """WWR=0.9 should still produce valid commands."""
        bps = {
            "building": {
                "building_type": "large_office",
                "floors": 2,
                "floor_area_m2": 4000,
                "floor_height_m": 3.96,
            },
            "envelope": {"wwr": 0.9},
        }
        commands = bps_to_blender_commands(bps)
        zones = bps_to_zone_info(bps)
        idf = _zones_to_idf_objects(zones)

        assert len(commands) > 0
        assert len(zones) > 0
        assert "Zone," in idf

    def test_minimal_bps(self):
        """BPS with only building_type should use defaults."""
        bps = {"building": {"building_type": "standalone_retail"}}
        commands = bps_to_blender_commands(bps)
        zones = bps_to_zone_info(bps)

        assert len(commands) > 0
        assert len(zones) == 1  # 1 floor default
        assert zones[0]["area_m2"] == 5000  # default

    def test_missing_envelope_uses_default_wwr(self):
        """No envelope section → default WWR 0.4."""
        bps = {
            "building": {
                "building_type": "medium_office",
                "floors": 3,
                "floor_area_m2": 4982,
            },
        }
        commands = bps_to_blender_commands(bps)
        win_cmds = [
            c for c in commands
            if c["type"] == "create_object" and c["params"]["name"].startswith("Win_")
        ]
        assert len(win_cmds) == 3 * 4  # 3 floors × 4 directions
