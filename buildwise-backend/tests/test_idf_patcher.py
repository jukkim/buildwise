"""Tests for IDF post-processing (user BPS overrides)."""

import pytest

from app.services.idf.idf_patcher import (
    _extract_schedule_block,
    _patch_boiler_efficiency,
    _patch_chiller_cop,
    _patch_pmv_csv_files,
    _patch_setpoint_schedules,
    _replace_temps_in_block,
    _to_float,
    apply_user_overrides,
)

# ---------------------------------------------------------------------------
# Fixtures: realistic IDF snippets from ems_simulation large_office baseline
# ---------------------------------------------------------------------------

COOLING_SCHEDULE = """\
Schedule:Compact,
    CLGSETP_SCH_YES_OPTIMUM,    !- Name
    Temperature,              !- Schedule Type Limits Name
    Through: 12/31,           !- Field 1
    For: Weekdays,            !- Field 2
    Until: 06:00,             !- Field 3
    29.0,                     !- Field 4
    Until: 22:00,             !- Field 5
    24.0,                     !- Field 6
    Until: 24:00,             !- Field 7
    29.0,                     !- Field 8
    For: Saturday,            !- Field 9
    Until: 06:00,             !- Field 10
    29.0,                     !- Field 11
    Until: 22:00,             !- Field 12
    24.0,                     !- Field 13
    Until: 24:00,             !- Field 14
    29.0,                     !- Field 15
    For: Sunday Holidays AllOtherDays,    !- Field 16
    Until: 06:00,             !- Field 17
    29.0,                     !- Field 18
    Until: 22:00,             !- Field 19
    24.0,                     !- Field 20
    Until: 24:00,             !- Field 21
    29.0;                     !- Field 22"""

HEATING_SCHEDULE = """\
Schedule:Compact,
    HTGSETP_SCH_YES_OPTIMUM,    !- Name
    Temperature,              !- Schedule Type Limits Name
    Through: 12/31,           !- Field 1
    For: Weekdays,            !- Field 2
    Until: 06:00,             !- Field 3
    15.6,                     !- Field 4
    Until: 22:00,             !- Field 5
    20.0,                     !- Field 6
    Until: 24:00,             !- Field 7
    15.6,                     !- Field 8
    For: Saturday,            !- Field 9
    Until: 06:00,             !- Field 10
    15.6,                     !- Field 11
    Until: 22:00,             !- Field 12
    20.0,                     !- Field 13
    Until: 24:00,             !- Field 14
    15.6,                     !- Field 15
    For: Sunday Holidays AllOtherDays,    !- Field 16
    Until: 06:00,             !- Field 17
    15.6,                     !- Field 18
    Until: 22:00,             !- Field 19
    20.0,                     !- Field 20
    Until: 24:00,             !- Field 21
    15.6;                     !- Field 22"""

CHILLER_SNIPPET = """\
Chiller:Electric:EIR,
    CoolSys1 Chiller1,        !- Name
    999070.745,               !- Reference Capacity
    6.1,                      !- Reference COP
    6.67,                     !- Reference Leaving Chilled Water Temperature
    29.44,                    !- Reference Entering Condenser Fluid Temperature
    4.280734e-02,             !- Reference Chilled Water Flow Rate
    5.517136e-02,             !- Reference Condenser Fluid Flow Rate
    WC_PD_2019_BD_X_CAPFT,    !- Cooling Capacity Function of Temperature Curve Name
    WC_PD_2019_BD_X_EIRFT,    !- Electric Input to Cooling Output Ratio Function of Temperature Curve Name
    WC_PD_2019_BD_X_EIRFPLR,    !- Electric Input to Cooling Output Ratio Function of Part Load Ratio Curve Name
    0.25,                     !- Minimum Part Load Ratio
    1,                        !- Maximum Part Load Ratio
    1,                        !- Optimum Part Load Ratio
    0.25,                     !- Minimum Unloading Ratio
    CoolSys1 Pump-CoolSys1 Chiller1Node,    !- Chilled Water Inlet Node Name
    CoolSys1 Supply Equipment Outlet Node 1,    !- Chilled Water Outlet Node Name
    CoolSys1 Chiller1 Water Inlet Node,    !- Condenser Inlet Node Name
    CoolSys1 Chiller1 Water Outlet Node,    !- Condenser Outlet Node Name
    WaterCooled,              !- Condenser Type
    ,                         !- Condenser Fan Power Ratio
    ,                         !- Fraction of Compressor Electric Consumption Rejected by Condenser
    2,                        !- Leaving Chilled Water Lower Temperature Limit
    ConstantFlow,             !- Chiller Flow Mode
    0;                        !- Design Heat Recovery Water Flow Rate

Chiller:Electric:EIR,
    CoolSys1 Chiller2,        !- Name
    999070.745,               !- Reference Capacity
    6.1,                      !- Reference COP
    6.67,                     !- Reference Leaving Chilled Water Temperature
    29.44,                    !- Reference Entering Condenser Fluid Temperature
    4.280734e-02,             !- Reference Chilled Water Flow Rate
    5.517136e-02,             !- Reference Condenser Fluid Flow Rate
    WC_PD_2019_BD_X_CAPFT,    !- Cooling Capacity Function of Temperature Curve Name
    WC_PD_2019_BD_X_EIRFT,    !- Electric Input to Cooling Output Ratio Function of Temperature Curve Name
    WC_PD_2019_BD_X_EIRFPLR,    !- Electric Input to Cooling Output Ratio Function of Part Load Ratio Curve Name
    0.25,                     !- Minimum Part Load Ratio
    1,                        !- Maximum Part Load Ratio
    1,                        !- Optimum Part Load Ratio
    0.25,                     !- Minimum Unloading Ratio
    CoolSys1 Pump-CoolSys1 Chiller2Node,    !- Chilled Water Inlet Node Name
    CoolSys1 Supply Equipment Outlet Node 2,    !- Chilled Water Outlet Node Name
    CoolSys1 Chiller2 Water Inlet Node,    !- Condenser Inlet Node Name
    CoolSys1 Chiller2 Water Outlet Node,    !- Condenser Outlet Node Name
    WaterCooled,              !- Condenser Type
    ,                         !- Condenser Fan Power Ratio
    ,                         !- Fraction of Compressor Electric Consumption Rejected by Condenser
    2,                        !- Leaving Chilled Water Lower Temperature Limit
    ConstantFlow,             !- Chiller Flow Mode
    0;                        !- Design Heat Recovery Water Flow Rate"""

BOILER_SNIPPET = """\
Boiler:HotWater,
    HeatSys1 Boiler,          !- Name
    NATURALGAS,               !- Fuel Type
    1614618.465,              !- Nominal Capacity
    0.8125,                   !- Nominal Thermal Efficiency
    LeavingBoiler,            !- Efficiency Curve Temperature Evaluation Variable
    HeatSys1 Boiler Efficiency Curve,    !- Normalized Boiler Efficiency Curve Name
    AUTOSIZE,                 !- Design Water Flow Rate
    0,                        !- Minimum Part Load Ratio
    1.2,                      !- Maximum Part Load Ratio
    1,                        !- Optimum Part Load Ratio
    HeatSys1 Pump-HeatSys1 BoilerNode,    !- Boiler Water Inlet Node Name
    HeatSys1 Supply Equipment Outlet Node,    !- Boiler Water Outlet Node Name
    95,                       !- Water Outlet Upper Temperature Limit
    LeavingSetpointModulated;    !- Boiler Flow Mode

Boiler:HotWater,
    Dummy Boiler,             !- Name
    NaturalGas,               !- Fuel Type
    93894.07,                 !- Nominal Capacity
    0.8,                      !- Nominal Thermal Efficiency
    LeavingBoiler,            !- Efficiency Curve Temperature Evaluation Variable
    Dummy Boiler Efficiency Curve,    !- Normalized Boiler Efficiency Curve Name
    autosize,                 !- Design Water Flow Rate
    0,                        !- Minimum Part Load Ratio
    1.2,                      !- Maximum Part Load Ratio
    1,                        !- Optimum Part Load Ratio
    Dummy Boiler Inlet Node,    !- Boiler Water Inlet Node Name
    Dummy Boiler Outlet Node,    !- Boiler Water Outlet Node Name
    95,                       !- Water Outlet Upper Temperature Limit
    ConstantFlow;             !- Boiler Flow Mode"""

# Composite IDF for integration tests
SAMPLE_IDF = "\n\n".join(
    [
        "! === Some header ===",
        HEATING_SCHEDULE,
        COOLING_SCHEDULE,
        CHILLER_SNIPPET,
        BOILER_SNIPPET,
        "! === End ===",
    ]
)

LARGE_OFFICE_DEFAULTS = {
    "cooling_occupied": 24.0,
    "heating_occupied": 20.0,
    "cooling_unoccupied": 29.0,
    "heating_unoccupied": 15.6,
    "chiller_cop": 6.1,
    "boiler_efficiency": 0.8125,
    "heating_schedules": ["HTGSETP_SCH_YES_OPTIMUM"],
    "cooling_schedules": ["CLGSETP_SCH_YES_OPTIMUM"],
}


# ---------------------------------------------------------------------------
# Schedule extraction tests
# ---------------------------------------------------------------------------


class TestExtractScheduleBlock:
    def test_extracts_cooling_schedule(self):
        block = _extract_schedule_block(SAMPLE_IDF, "CLGSETP_SCH_YES_OPTIMUM")
        assert block is not None
        assert "CLGSETP_SCH_YES_OPTIMUM" in block
        assert "24.0" in block
        assert block.rstrip().endswith(";")

    def test_extracts_heating_schedule(self):
        block = _extract_schedule_block(SAMPLE_IDF, "HTGSETP_SCH_YES_OPTIMUM")
        assert block is not None
        assert "20.0" in block
        assert "15.6" in block

    def test_returns_none_for_missing(self):
        block = _extract_schedule_block(SAMPLE_IDF, "NONEXISTENT_SCHEDULE")
        assert block is None


# ---------------------------------------------------------------------------
# Temperature replacement tests
# ---------------------------------------------------------------------------


class TestReplaceTempInBlock:
    def test_replaces_occupied_cooling(self):
        result = _replace_temps_in_block(COOLING_SCHEDULE, [(24.0, 26.0)])
        assert "26.0" in result
        # Unoccupied (29.0) should remain
        assert "29.0" in result

    def test_replaces_unoccupied_cooling(self):
        result = _replace_temps_in_block(COOLING_SCHEDULE, [(29.0, 32.0)])
        assert "32.0" in result
        # Occupied (24.0) should remain
        assert "24.0" in result

    def test_replaces_occupied_heating(self):
        result = _replace_temps_in_block(HEATING_SCHEDULE, [(20.0, 22.0)])
        assert "22.0" in result
        assert "15.6" in result  # unoccupied unchanged

    def test_no_change_when_same(self):
        result = _replace_temps_in_block(COOLING_SCHEDULE, [(24.0, 24.0)])
        assert result == COOLING_SCHEDULE

    def test_replaces_all_occurrences(self):
        """24.0 appears 3 times (weekday, saturday, sunday) — all should change."""
        result = _replace_temps_in_block(COOLING_SCHEDULE, [(24.0, 26.0)])
        assert result.count("26.0") == 3
        assert "24.0" not in result

    def test_multiple_replacements_single_pass(self):
        """Both occupied and unoccupied replaced in single pass."""
        result = _replace_temps_in_block(COOLING_SCHEDULE, [(24.0, 26.0), (29.0, 32.0)])
        assert result.count("26.0") == 3
        assert result.count("32.0") == 6  # 29.0 appears 6 times
        assert "24.0" not in result
        assert "29.0" not in result

    def test_collision_new_occupied_equals_old_unoccupied(self):
        """Critical: user sets occupied=29.0 (same as default unoccupied).

        Without single-pass, sequential replacement would first replace
        24.0→29.0, making all values 29.0, then replace 29.0→32.0.
        Single-pass avoids this by matching original values only.
        """
        result = _replace_temps_in_block(COOLING_SCHEDULE, [(24.0, 29.0), (29.0, 32.0)])
        # Occupied slots (was 24.0) → 29.0
        assert result.count("29.0") == 3
        # Unoccupied slots (was 29.0) → 32.0
        assert result.count("32.0") == 6
        # No original 24.0 left
        assert "24.0" not in result

    def test_empty_replacements(self):
        result = _replace_temps_in_block(COOLING_SCHEDULE, [])
        assert result == COOLING_SCHEDULE


# ---------------------------------------------------------------------------
# Chiller COP patch tests
# ---------------------------------------------------------------------------


class TestPatchChillerCop:
    def test_patches_both_chillers(self):
        result = _patch_chiller_cop(CHILLER_SNIPPET, 5.0)
        assert result.count("5.00") == 2  # Both Chiller1 and Chiller2
        assert "6.1" not in result.split("!- Reference COP")[0].split("\n")[-1]

    def test_preserves_other_fields(self):
        result = _patch_chiller_cop(CHILLER_SNIPPET, 5.0)
        assert "999070.745" in result  # capacity unchanged
        assert "6.67" in result  # leaving temp unchanged
        assert "29.44" in result  # entering temp unchanged

    def test_decimal_precision(self):
        result = _patch_chiller_cop(CHILLER_SNIPPET, 4.567)
        assert "4.57" in result


# ---------------------------------------------------------------------------
# Boiler efficiency patch tests
# ---------------------------------------------------------------------------


class TestPatchBoilerEfficiency:
    def test_patches_both_boilers(self):
        result = _patch_boiler_efficiency(BOILER_SNIPPET, 0.95)
        assert "0.9500" in result
        # Both HeatSys1 Boiler (0.8125) and Dummy Boiler (0.8) should change
        assert "0.8125" not in result
        # Check the 0.8 in Dummy Boiler changed too
        lines_with_eff = [line for line in result.split("\n") if "Nominal Thermal Efficiency" in line]
        assert len(lines_with_eff) == 2
        for line in lines_with_eff:
            assert "0.9500" in line

    def test_preserves_other_fields(self):
        result = _patch_boiler_efficiency(BOILER_SNIPPET, 0.95)
        assert "1614618.465" in result  # capacity unchanged
        assert "NATURALGAS" in result


# ---------------------------------------------------------------------------
# Setpoint schedule patch tests (integration)
# ---------------------------------------------------------------------------


class TestPatchSetpointSchedules:
    def test_cooling_occupied_change(self):
        result = _patch_setpoint_schedules(
            SAMPLE_IDF,
            LARGE_OFFICE_DEFAULTS,
            cool_occ=26.0,
            heat_occ=None,
            cool_unocc=None,
            heat_unocc=None,
        )
        block = _extract_schedule_block(result, "CLGSETP_SCH_YES_OPTIMUM")
        assert "26.0" in block
        assert "29.0" in block  # unoccupied unchanged

    def test_heating_occupied_change(self):
        result = _patch_setpoint_schedules(
            SAMPLE_IDF,
            LARGE_OFFICE_DEFAULTS,
            cool_occ=None,
            heat_occ=22.0,
            cool_unocc=None,
            heat_unocc=None,
        )
        block = _extract_schedule_block(result, "HTGSETP_SCH_YES_OPTIMUM")
        assert "22.0" in block
        assert "15.6" in block  # unoccupied unchanged

    def test_both_occupied_and_unoccupied(self):
        result = _patch_setpoint_schedules(
            SAMPLE_IDF,
            LARGE_OFFICE_DEFAULTS,
            cool_occ=26.0,
            heat_occ=22.0,
            cool_unocc=32.0,
            heat_unocc=12.0,
        )
        cool_block = _extract_schedule_block(result, "CLGSETP_SCH_YES_OPTIMUM")
        heat_block = _extract_schedule_block(result, "HTGSETP_SCH_YES_OPTIMUM")
        assert "26.0" in cool_block
        assert "32.0" in cool_block
        assert "22.0" in heat_block
        assert "12.0" in heat_block


# ---------------------------------------------------------------------------
# PMV CSV patch tests
# ---------------------------------------------------------------------------


class TestPatchPmvCsvFiles:
    def _make_csv(self, values: list[float]) -> bytes:
        return "\n".join(f"{v:.2f}" for v in values).encode("utf-8")

    def test_cooling_csv_offset(self):
        """Cooling delta +2°C: occupied values shift, unoccupied replaced."""
        aux = {
            "pmv_schedules/busan_pmv50_cooling.csv": self._make_csv([29.00, 29.00, 24.50, 25.75, 29.00]),
        }
        result = _patch_pmv_csv_files(
            aux,
            LARGE_OFFICE_DEFAULTS,
            cooling_delta=2.0,
            heating_delta=0.0,
            cool_unocc_new=31.0,
            heat_unocc_new=15.6,
        )
        patched = result["pmv_schedules/busan_pmv50_cooling.csv"].decode("utf-8")
        lines = patched.strip().split("\n")
        vals = [float(v) for v in lines]
        # 29.00 (unoccupied) → 31.00
        assert vals[0] == pytest.approx(31.0)
        assert vals[1] == pytest.approx(31.0)
        # 24.50 + 2.0 = 26.50
        assert vals[2] == pytest.approx(26.5)
        # 25.75 + 2.0 = 27.75
        assert vals[3] == pytest.approx(27.75)
        assert vals[4] == pytest.approx(31.0)

    def test_heating_csv_offset(self):
        aux = {
            "pmv_schedules/busan_pmv50_heating.csv": self._make_csv([15.60, 15.60, 19.66, 20.00, 15.60]),
        }
        result = _patch_pmv_csv_files(
            aux,
            LARGE_OFFICE_DEFAULTS,
            cooling_delta=0.0,
            heating_delta=2.0,
            cool_unocc_new=29.0,
            heat_unocc_new=13.0,
        )
        patched = result["pmv_schedules/busan_pmv50_heating.csv"].decode("utf-8")
        vals = [float(v) for v in patched.strip().split("\n")]
        # 15.60 (unoccupied) → 13.00
        assert vals[0] == pytest.approx(13.0)
        # 19.66 + 2.0 = 21.66
        assert vals[2] == pytest.approx(21.66)
        # 20.00 + 2.0 = 22.00
        assert vals[3] == pytest.approx(22.0)

    def test_ignores_non_pmv_files(self):
        aux = {
            "baseline_availability.csv": b"0\n0\n1\n1\n",
            "pmv_schedules/cooling.csv": self._make_csv([29.00, 24.50]),
        }
        result = _patch_pmv_csv_files(
            aux,
            LARGE_OFFICE_DEFAULTS,
            cooling_delta=1.0,
            heating_delta=0.0,
            cool_unocc_new=30.0,
            heat_unocc_new=15.6,
        )
        # Non-PMV file unchanged
        assert result["baseline_availability.csv"] == b"0\n0\n1\n1\n"


# ---------------------------------------------------------------------------
# Full integration: apply_user_overrides
# ---------------------------------------------------------------------------


class TestApplyUserOverrides:
    def test_no_change_with_default_bps(self):
        """BPS matching ems defaults → no modifications."""
        bps = {
            "setpoints": {
                "cooling_occupied": 24.0,
                "heating_occupied": 20.0,
                "cooling_unoccupied": 29.0,
                "heating_unoccupied": 15.6,
            },
            "hvac": {
                "chillers": {"cop": 6.1},
                "boilers": {"efficiency": 0.8125},
            },
        }
        result_idf, result_aux = apply_user_overrides(
            SAMPLE_IDF,
            {},
            bps,
            "large_office",
        )
        assert result_idf == SAMPLE_IDF  # no changes

    def test_cooling_setpoint_override(self):
        bps = {
            "setpoints": {"cooling_occupied": 26.0},
            "hvac": {},
        }
        result_idf, _ = apply_user_overrides(
            SAMPLE_IDF,
            {},
            bps,
            "large_office",
        )
        block = _extract_schedule_block(result_idf, "CLGSETP_SCH_YES_OPTIMUM")
        assert "26.0" in block
        assert "24.0" not in block  # old value gone

    def test_chiller_cop_override(self):
        bps = {
            "setpoints": {},
            "hvac": {"chillers": {"cop": 4.0}},
        }
        result_idf, _ = apply_user_overrides(
            SAMPLE_IDF,
            {},
            bps,
            "large_office",
        )
        assert "4.00" in result_idf

    def test_boiler_efficiency_override(self):
        bps = {
            "setpoints": {},
            "hvac": {"boilers": {"efficiency": 0.95}},
        }
        result_idf, _ = apply_user_overrides(
            SAMPLE_IDF,
            {},
            bps,
            "large_office",
        )
        assert "0.9500" in result_idf

    def test_unsupported_building_type_passthrough(self):
        """Unknown building type → returns original unchanged."""
        result_idf, result_aux = apply_user_overrides(
            SAMPLE_IDF,
            {},
            {"setpoints": {"cooling_occupied": 26.0}},
            "unknown_type",
        )
        assert result_idf == SAMPLE_IDF

    def test_empty_bps_passthrough(self):
        """Empty BPS → no changes."""
        result_idf, _ = apply_user_overrides(
            SAMPLE_IDF,
            {},
            {},
            "large_office",
        )
        assert result_idf == SAMPLE_IDF

    def test_medium_office_schedule_names(self):
        """medium_office uses different schedule names (CoolingSPSch/HeatingSPSch)."""
        med_cooling = """\
Schedule:Compact,
    CoolingSPSch,             !- Name
    Temperature,              !- Schedule Type Limits Name
    Through: 12/31,           !- Field 1
    For: WeekDays SummerDesignDay,    !- Field 2
    Until: 06:00,             !- Field 3
    30.0,                     !- Field 4
    Until: 18:00,             !- Field 5
    26.0,                     !- Field 6
    Until: 24:00,             !- Field 7
    30.0;                     !- Field 8"""

        bps = {"setpoints": {"cooling_occupied": 24.0}, "hvac": {}}
        result_idf, _ = apply_user_overrides(
            med_cooling,
            {},
            bps,
            "medium_office",
        )
        block = _extract_schedule_block(result_idf, "CoolingSPSch")
        assert "24.0" in block
        assert "26.0" not in block  # old occupied value gone

    def test_combined_setpoint_and_cop(self):
        """Multiple overrides applied together."""
        bps = {
            "setpoints": {"cooling_occupied": 26.0, "heating_occupied": 22.0},
            "hvac": {"chillers": {"cop": 5.0}, "boilers": {"efficiency": 0.90}},
        }
        result_idf, _ = apply_user_overrides(
            SAMPLE_IDF,
            {},
            bps,
            "large_office",
        )
        cool_block = _extract_schedule_block(result_idf, "CLGSETP_SCH_YES_OPTIMUM")
        heat_block = _extract_schedule_block(result_idf, "HTGSETP_SCH_YES_OPTIMUM")
        assert "26.0" in cool_block
        assert "22.0" in heat_block
        assert "5.00" in result_idf  # COP
        assert "0.9000" in result_idf  # efficiency


# ---------------------------------------------------------------------------
# _to_float validation tests
# ---------------------------------------------------------------------------


class TestToFloat:
    def test_valid_float(self):
        assert _to_float(24.0) == 24.0
        assert _to_float(0.95) == 0.95

    def test_valid_int(self):
        assert _to_float(24) == 24.0

    def test_valid_string(self):
        assert _to_float("24.0") == 24.0

    def test_none(self):
        assert _to_float(None) is None

    def test_nan(self):
        assert _to_float(float("nan")) is None

    def test_inf(self):
        assert _to_float(float("inf")) is None
        assert _to_float(float("-inf")) is None

    def test_invalid_string(self):
        assert _to_float("not a number") is None


# ---------------------------------------------------------------------------
# Fail-safe behavior tests
# ---------------------------------------------------------------------------


class TestFailSafe:
    def test_returns_original_on_unsupported_building(self):
        """Unknown building type returns original unchanged."""
        bps = {"setpoints": {"cooling_occupied": 99.0}}
        result_idf, result_aux = apply_user_overrides(
            SAMPLE_IDF,
            {"a.csv": b"data"},
            bps,
            "warehouse",
        )
        assert result_idf == SAMPLE_IDF
        assert result_aux == {"a.csv": b"data"}

    def test_nan_cop_ignored(self):
        """NaN COP should not patch IDF."""
        bps = {"setpoints": {}, "hvac": {"chillers": {"cop": float("nan")}}}
        result_idf, _ = apply_user_overrides(SAMPLE_IDF, {}, bps, "large_office")
        # COP should remain 6.1
        assert "6.1" in result_idf

    def test_inf_efficiency_ignored(self):
        """Inf efficiency should not patch IDF."""
        bps = {"setpoints": {}, "hvac": {"boilers": {"efficiency": float("inf")}}}
        result_idf, _ = apply_user_overrides(SAMPLE_IDF, {}, bps, "large_office")
        assert "0.8125" in result_idf

    def test_cop_out_of_range_ignored(self):
        """COP outside 1.0-15.0 range should not patch IDF."""
        bps = {"setpoints": {}, "hvac": {"chillers": {"cop": 0.5}}}
        result_idf, _ = apply_user_overrides(SAMPLE_IDF, {}, bps, "large_office")
        assert "6.1" in result_idf

    def test_efficiency_out_of_range_ignored(self):
        """Efficiency outside 0.1-1.0 range should not patch IDF."""
        bps = {"setpoints": {}, "hvac": {"boilers": {"efficiency": 1.5}}}
        result_idf, _ = apply_user_overrides(SAMPLE_IDF, {}, bps, "large_office")
        assert "0.8125" in result_idf
