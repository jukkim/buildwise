"""IDF generator unit tests."""

from unittest.mock import patch

import pytest

from app.services.idf.generator import (
    _compute_zone_geometry,
    _generate_constructions,
    _generate_design_days,
    _generate_global_geometry_rules,
    _generate_ground_temps,
    _generate_hvac,
    _generate_idf_envelope,
    _generate_idf_geometry,
    _generate_infiltration,
    _generate_internal_loads,
    _generate_output_variables,
    _generate_schedules,
    _get_ems_templates,
    _resolve_run_period,
    generate_idf,
    sanitize_idf_field,
)


# --- Sample BPS for testing ---
def _sample_bps(**overrides) -> dict:
    """Create a sample BPS dict for testing."""
    bps = {
        "geometry": {
            "building_type": "large_office",
            "num_floors_above": 2,
            "total_floor_area_m2": 2000,
            "floor_to_floor_height_m": 3.96,
            "aspect_ratio": 1.5,
            "wwr": 0.38,
            "orientation_deg": 0,
        },
        "envelope": {
            "window_u_value": 1.5,
            "window_shgc": 0.25,
            "wall_u_value": 0.5,
            "roof_u_value": 0.3,
            "floor_u_value": 0.5,
            "infiltration_ach": 0.5,
        },
        "setpoints": {
            "cooling_occupied": 24.0,
            "heating_occupied": 20.0,
            "cooling_unoccupied": 29.0,
            "heating_unoccupied": 15.0,
        },
        "hvac": {
            "system_type": "vav_chiller_boiler",
        },
        "simulation": {
            "timestep": 4,
        },
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and k in bps:
            bps[k].update(v)
        else:
            bps[k] = v
    return bps


class TestSanitizeIdfField:
    """Test IDF field sanitization."""

    def test_removes_comma(self):
        assert sanitize_idf_field("hello,world") == "helloworld"

    def test_removes_semicolon(self):
        assert sanitize_idf_field("hello;world") == "helloworld"

    def test_removes_comment(self):
        assert sanitize_idf_field("hello!world") == "helloworld"

    def test_removes_newlines(self):
        assert sanitize_idf_field("hello\nworld\r") == "helloworld"

    def test_strips_whitespace(self):
        assert sanitize_idf_field("  hello  ") == "hello"

    def test_converts_non_string(self):
        assert sanitize_idf_field(42) == "42"

    def test_empty_string(self):
        assert sanitize_idf_field("") == ""

    def test_safe_string_unchanged(self):
        assert sanitize_idf_field("large_office") == "large_office"


class TestStrategyTemplateMapping:
    """Test strategy to EMS template selection per building type."""

    def test_baseline_has_no_templates(self):
        templates = _get_ems_templates("baseline", "large_office")
        assert templates == []

    def test_m0_large_office(self):
        templates = _get_ems_templates("m0", "large_office")
        assert templates == ["m0_occupancy_setback.j2"]

    def test_m0_medium_office(self):
        templates = _get_ems_templates("m0", "medium_office")
        assert templates == ["m0_occupancy_setback.j2"]

    def test_m1_large_office(self):
        templates = _get_ems_templates("m1", "large_office")
        assert templates == ["m1_optimal_start.j2"]

    def test_m1_medium_office(self):
        templates = _get_ems_templates("m1", "medium_office")
        assert templates == ["m1_optimal_start.j2"]

    def test_m2_economizer(self):
        templates = _get_ems_templates("m2", "large_office")
        assert templates == ["m2_free_cooling.j2"]

    def test_m2_not_applicable_medium_office(self):
        templates = _get_ems_templates("m2", "medium_office")
        assert templates == []

    def test_m3_staging_large_office(self):
        templates = _get_ems_templates("m3", "large_office")
        assert templates == ["m3_load_limiting.j2"]

    def test_m3_not_applicable_small_office(self):
        templates = _get_ems_templates("m3", "small_office")
        assert templates == []

    def test_m4_wildcard_all_buildings(self):
        for bt in ["large_office", "medium_office", "small_office", "standalone_retail", "primary_school"]:
            templates = _get_ems_templates("m4", bt)
            assert templates == ["m4_comfort_normal.j2"]

    def test_m7_large_office(self):
        templates = _get_ems_templates("m7", "large_office")
        assert templates == ["m7_full_normal.j2"]

    def test_m7_medium_office(self):
        templates = _get_ems_templates("m7", "medium_office")
        assert templates == ["m7_full_normal.j2"]

    def test_unknown_strategy(self):
        templates = _get_ems_templates("unknown", "large_office")
        assert templates == []

    def test_unknown_building_no_wildcard(self):
        templates = _get_ems_templates("m3", "unknown_type")
        assert templates == []

    def test_unknown_building_with_wildcard(self):
        templates = _get_ems_templates("m4", "unknown_type")
        assert templates == ["m4_comfort_normal.j2"]


class TestZoneGeometry:
    """Test zone geometry computation."""

    def test_single_floor_produces_5_zones(self):
        zones = _compute_zone_geometry(width=30, length=45, floors=1, height=3.96)
        assert len(zones) == 5
        names = {z["name"] for z in zones}
        assert "F1_Core" in names
        assert "F1_Perimeter_N" in names
        assert "F1_Perimeter_S" in names
        assert "F1_Perimeter_E" in names
        assert "F1_Perimeter_W" in names

    def test_two_floors_produces_10_zones(self):
        zones = _compute_zone_geometry(width=30, length=45, floors=2, height=3.96)
        assert len(zones) == 10

    def test_zone_z_coordinates(self):
        zones = _compute_zone_geometry(width=30, length=45, floors=3, height=4.0)
        f1_zones = [z for z in zones if z["floor"] == 1]
        f2_zones = [z for z in zones if z["floor"] == 2]
        f3_zones = [z for z in zones if z["floor"] == 3]
        assert f1_zones[0]["z_min"] == 0
        assert f1_zones[0]["z_max"] == 4.0
        assert f2_zones[0]["z_min"] == 4.0
        assert f2_zones[0]["z_max"] == 8.0
        assert f3_zones[0]["z_min"] == 8.0
        assert f3_zones[0]["z_max"] == 12.0

    def test_perimeter_depth_clamped(self):
        # Very narrow building: perimeter depth should be < width/3
        zones = _compute_zone_geometry(width=6, length=6, floors=1, height=3.96)
        core = [z for z in zones if "Core" in z["name"]][0]
        # Core should have positive area
        assert core["x_max"] > core["x_min"]
        assert core["y_max"] > core["y_min"]


class TestGenerateIdfSections:
    """Test individual IDF section generators."""

    def test_global_geometry_rules(self):
        result = _generate_global_geometry_rules()
        assert "GlobalGeometryRules" in result
        assert "UpperLeftCorner" in result
        assert "Counterclockwise" in result

    def test_design_days_seoul(self):
        result = _generate_design_days("Seoul")
        assert "Site:Location" in result
        assert "Seoul" in result
        assert "SummerDesignDay" in result
        assert "WinterDesignDay" in result
        assert "33.3" in result  # Summer design temp
        assert "-11.3" in result  # Winter design temp

    def test_design_days_jeju(self):
        result = _generate_design_days("Jeju")
        assert "Jeju" in result
        assert "0.1" in result  # Winter design temp (mild)

    def test_design_days_unknown_city_defaults_to_seoul(self):
        result = _generate_design_days("UnknownCity")
        assert "33.3" in result  # Seoul summer temp

    def test_ground_temps_seoul(self):
        result = _generate_ground_temps("Seoul")
        assert "Site:GroundTemperature:BuildingSurface" in result
        assert "1.5" in result  # Jan
        assert "26.0" in result  # Aug

    def test_ground_temps_jeju(self):
        result = _generate_ground_temps("Jeju")
        assert "6.5" in result  # Jan (milder)
        assert "27.0" in result  # Aug

    def test_ground_temps_unknown_defaults_to_seoul(self):
        result = _generate_ground_temps("UnknownCity")
        assert "1.5" in result  # Seoul Jan

    def test_constructions(self):
        bps = _sample_bps()
        result = _generate_constructions(bps)
        assert "ExtWallMaterial" in result
        assert "RoofMaterial" in result
        assert "FloorMaterial" in result
        assert "Construction," in result
        # Wall R-value = 1/0.5 = 2.0
        assert "2.0000" in result

    def test_envelope(self):
        bps = _sample_bps()
        result = _generate_idf_envelope(bps)
        assert "SimpleWindow" in result
        assert "1.5" in result  # U-Factor
        assert "0.25" in result  # SHGC

    def test_schedules(self):
        bps = _sample_bps()
        result = _generate_schedules(bps)
        assert "ScheduleTypeLimits" in result
        assert "Fraction" in result
        assert "Temperature" in result
        assert "OccupancySchedule" in result
        assert "LightingSchedule" in result
        assert "EquipmentSchedule" in result
        assert "CoolingSetpoint" in result
        assert "HeatingSetpoint" in result
        # Setpoint values
        assert "24.0" in result
        assert "20.0" in result

    def test_internal_loads(self):
        bps = _sample_bps()
        zone_names = ["F1_Core", "F1_Perimeter_S"]
        result = _generate_internal_loads(bps, zone_names)
        assert "People," in result
        assert "Lights," in result
        assert "ElectricEquipment," in result
        assert "F1_Core_People" in result
        assert "F1_Perimeter_S_Lights" in result

    def test_infiltration(self):
        bps = _sample_bps()
        zone_names = ["F1_Core"]
        result = _generate_infiltration(bps, zone_names)
        assert "ZoneInfiltration:DesignFlowRate" in result
        assert "0.5" in result  # ACH

    def test_hvac(self):
        bps = _sample_bps()
        zone_names = ["F1_Core"]
        result = _generate_hvac(zone_names, bps)
        assert "ZoneHVAC:" in result
        assert "ZoneControl:Thermostat" in result or "ZoneHVAC:EquipmentConnections" in result

    def test_output_variables(self):
        result = _generate_output_variables("baseline")
        assert "Output:Variable" in result
        assert "Output:Meter" in result
        assert "AllSummary" in result


class TestGeometryWithSurfaces:
    """Test that geometry generation includes surfaces and windows."""

    def test_geometry_has_building_object(self):
        bps = _sample_bps()
        result = _generate_idf_geometry(bps)
        assert "Building," in result
        assert "large_office" in result

    def test_geometry_has_zones(self):
        bps = _sample_bps()
        result = _generate_idf_geometry(bps)
        assert "Zone," in result
        assert "F1_Core" in result
        assert "F2_Perimeter_N" in result

    def test_geometry_has_surfaces(self):
        bps = _sample_bps()
        result = _generate_idf_geometry(bps)
        assert "BuildingSurface:Detailed" in result
        assert "_Floor" in result
        assert "_Ceiling" in result
        assert "_Wall_" in result

    def test_geometry_has_windows(self):
        bps = _sample_bps()
        result = _generate_idf_geometry(bps)
        assert "FenestrationSurface:Detailed" in result
        assert "_Win" in result

    def test_geometry_no_windows_with_zero_wwr(self):
        bps = _sample_bps(geometry={"wwr": 0})
        result = _generate_idf_geometry(bps)
        assert "FenestrationSurface:Detailed" not in result

    def test_ground_floor_has_ground_bc(self):
        bps = _sample_bps()
        result = _generate_idf_geometry(bps)
        assert "Ground," in result or "Ground,                      !- Outside Boundary Condition" in result

    def test_top_floor_has_roof(self):
        bps = _sample_bps()
        result = _generate_idf_geometry(bps)
        assert "Roof," in result


class TestResolveRunPeriod:
    """Test RunPeriod resolution from period_type."""

    def test_default_annual(self):
        name, sm, sd, em, ed = _resolve_run_period("1year")
        assert name == "AnnualRun"
        assert (sm, sd, em, ed) == (1, 1, 12, 31)

    def test_summer_month(self):
        name, sm, sd, em, ed = _resolve_run_period("1month_summer")
        assert name == "SummerMonth"
        assert (sm, sd, em, ed) == (7, 1, 7, 31)

    def test_winter_month(self):
        name, sm, sd, em, ed = _resolve_run_period("1month_winter")
        assert name == "WinterMonth"
        assert (sm, sd, em, ed) == (1, 1, 1, 31)

    def test_custom_period(self):
        name, sm, sd, em, ed = _resolve_run_period("custom", "3/15", "9/30")
        assert name == "CustomPeriod"
        assert (sm, sd, em, ed) == (3, 15, 9, 30)

    def test_custom_missing_dates_falls_back_to_annual(self):
        name, sm, sd, em, ed = _resolve_run_period("custom")
        assert name == "AnnualRun"
        assert (sm, sd, em, ed) == (1, 1, 12, 31)

    def test_custom_invalid_format_falls_back(self):
        name, sm, sd, em, ed = _resolve_run_period("custom", "bad", "data")
        assert name == "AnnualRun"

    def test_unknown_period_type_falls_back(self):
        name, sm, sd, em, ed = _resolve_run_period("unknown_type")
        assert name == "AnnualRun"
        assert (sm, sd, em, ed) == (1, 1, 12, 31)


class TestGenerateIdf:
    """Test the main generate_idf entry point.

    These tests patch is_ems_supported to False so the BuildWise generator
    is used instead of ems_simulation (which may or may not be available).
    """

    def test_requires_bps(self):
        with pytest.raises(ValueError, match="bps dict required"):
            generate_idf("b1", "c1", "baseline", "Seoul", "KOR_Seoul.Ws.108.epw")

    @patch("app.services.idf.generator.is_ems_supported", return_value=False)
    def test_full_idf_has_all_sections(self, _mock):
        bps = _sample_bps()
        idf, aux_files = generate_idf("b1", "c1", "baseline", "Seoul", "KOR_Seoul.Ws.108.epw", bps=bps)

        # Header
        assert "Version,24.1;" in idf
        assert "SimulationControl," in idf
        assert "RunPeriod," in idf

        # Required sections
        assert "GlobalGeometryRules," in idf
        assert "SizingPeriod:DesignDay," in idf
        assert "Site:Location," in idf
        assert "Building," in idf
        assert "Zone," in idf
        assert "BuildingSurface:Detailed," in idf
        assert "Material:NoMass," in idf
        assert "Construction," in idf
        assert "WindowMaterial:SimpleGlazingSystem," in idf
        assert "Site:GroundTemperature:BuildingSurface," in idf
        assert "ScheduleTypeLimits," in idf
        assert "People," in idf
        assert "Lights," in idf
        assert "ElectricEquipment," in idf
        assert "ZoneInfiltration:DesignFlowRate," in idf
        assert "ZoneHVAC:" in idf
        assert "Output:Variable," in idf or "Output:Meter," in idf
        assert "Output:Table:SummaryReports," in idf

    @patch("app.services.idf.generator.is_ems_supported", return_value=False)
    def test_full_idf_line_count(self, _mock):
        bps = _sample_bps()
        idf, _ = generate_idf("b1", "c1", "baseline", "Seoul", "KOR_Seoul.Ws.108.epw", bps=bps)
        line_count = idf.count("\n")
        # A 2-floor, 10-zone building should generate a substantial IDF
        assert line_count > 500

    @patch("app.services.idf.generator.is_ems_supported", return_value=False)
    def test_idf_sanitizes_city(self, _mock):
        bps = _sample_bps()
        idf, _ = generate_idf("b1", "c1", "baseline", "Seoul;DROP TABLE", "KOR_Seoul.Ws.108.epw", bps=bps)
        assert "Seoul;DROP TABLE" not in idf
        assert "SeoulDROP TABLE" in idf

    @patch("app.services.idf.generator.is_ems_supported", return_value=False)
    def test_idf_different_strategies(self, _mock):
        bps = _sample_bps()
        baseline, _ = generate_idf("b1", "c1", "baseline", "Seoul", "test.epw", bps=bps)
        m3, _ = generate_idf("b1", "c1", "m3", "Seoul", "test.epw", bps=bps)
        # Both should have same structure but different strategy in header
        assert "Strategy: baseline" in baseline
        assert "Strategy: m3" in m3

    @patch("app.services.idf.generator.is_ems_supported", return_value=False)
    def test_single_floor_building(self, _mock):
        bps = _sample_bps(geometry={"num_floors_above": 1, "total_floor_area_m2": 500})
        idf, _ = generate_idf("b1", "c1", "baseline", "Seoul", "test.epw", bps=bps)
        assert "F1_Core" in idf
        assert "F2_Core" not in idf  # Only 1 floor

    @patch("app.services.idf.generator.is_ems_supported", return_value=False)
    def test_three_floor_building(self, _mock):
        bps = _sample_bps(geometry={"num_floors_above": 3, "total_floor_area_m2": 9000})
        idf, _ = generate_idf("b1", "c1", "baseline", "Seoul", "test.epw", bps=bps)
        assert "F1_Core" in idf
        assert "F2_Core" in idf
        assert "F3_Core" in idf
        assert "F4_Core" not in idf

    @patch("app.services.idf.generator.is_ems_supported", return_value=False)
    def test_summer_period_in_idf(self, _mock):
        bps = _sample_bps()
        idf, _ = generate_idf("b1", "c1", "baseline", "Seoul", "test.epw", bps=bps, period_type="1month_summer")
        assert "SummerMonth" in idf
        assert "7," in idf  # Start July

    @patch("app.services.idf.generator.is_ems_supported", return_value=False)
    def test_custom_period_in_idf(self, _mock):
        bps = _sample_bps()
        idf, _ = generate_idf(
            "b1",
            "c1",
            "baseline",
            "Seoul",
            "test.epw",
            bps=bps,
            period_type="custom",
            period_start="4/1",
            period_end="10/31",
        )
        assert "CustomPeriod" in idf
        assert "4," in idf
        assert "10," in idf
