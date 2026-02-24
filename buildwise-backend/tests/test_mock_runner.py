"""Mock simulation runner unit tests.

Tests verify that generate_mock_result returns exact eplustbl.csv EUI values
for known building/city/strategy combinations, with correct fallback for
unknown combinations.
"""

from app.services.simulation.mock_runner import (
    _DOE_DEFAULTS,
    _EUI_TABLE,
    _compute_adjustment_factor,
    _compute_schedule_factor,
    _generate_monthly_profile,
    _parse_hour,
    extract_user_config,
    generate_mock_result,
)


class TestExactEUI:
    """Test that known building/city/strategy returns exact eplustbl EUI."""

    def test_large_office_seoul_baseline(self):
        result = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        assert result["eui_kwh_m2"] == 119.75

    def test_large_office_jeju_m8(self):
        result = generate_mock_result("large_office", "Jeju", "m8", 46320)
        assert result["eui_kwh_m2"] == 109.38

    def test_medium_office_seoul_baseline(self):
        result = generate_mock_result("medium_office", "Seoul", "baseline", 4982)
        assert result["eui_kwh_m2"] == 77.57

    def test_small_office_busan_m7(self):
        result = generate_mock_result("small_office", "Busan", "m7", 511)
        assert result["eui_kwh_m2"] == 84.82

    def test_standalone_retail_daegu_m5(self):
        result = generate_mock_result("standalone_retail", "Daegu", "m5", 2294)
        assert result["eui_kwh_m2"] == 109.61

    def test_primary_school_gangneung_m2(self):
        result = generate_mock_result("primary_school", "Gangneung", "m2", 6871)
        assert result["eui_kwh_m2"] == 134.32

    def test_hospital_daegu_baseline(self):
        result = generate_mock_result("hospital", "Daegu", "baseline", 22422)
        assert result["eui_kwh_m2"] == 340.2

    def test_all_table_entries_exact(self):
        """Every entry in _EUI_TABLE must produce exact EUI match."""
        for btype, strategies in _EUI_TABLE.items():
            for strategy, cities in strategies.items():
                for city, expected_eui in cities.items():
                    result = generate_mock_result(btype, city, strategy, 10000)
                    assert result["eui_kwh_m2"] == expected_eui, (
                        f"{btype}/{strategy}/{city}: expected {expected_eui}, got {result['eui_kwh_m2']}"
                    )


class TestSavings:
    """Test savings calculations."""

    def test_baseline_has_no_savings(self):
        result = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        assert result["savings_pct"] is None
        assert result["annual_savings_krw"] is None

    def test_strategy_savings_kwh_consistent(self):
        baseline = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        m8 = generate_mock_result("large_office", "Seoul", "m8", 46320)
        expected_savings = baseline["total_energy_kwh"] - m8["total_energy_kwh"]
        assert abs(m8["savings_kwh"] - expected_savings) < 1.0

    def test_savings_pct_matches_eui_difference(self):
        baseline = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        m8 = generate_mock_result("large_office", "Seoul", "m8", 46320)
        actual_pct = (baseline["eui_kwh_m2"] - m8["eui_kwh_m2"]) / baseline["eui_kwh_m2"] * 100
        assert abs(actual_pct - m8["savings_pct"]) < 0.15

    def test_savings_vary_by_city(self):
        """Per-city savings should NOT be identical (they differ in eplustbl)."""
        savings = {}
        for city in ["Seoul", "Busan", "Daegu", "Jeju"]:
            r = generate_mock_result("large_office", city, "m8", 46320)
            savings[city] = r["savings_pct"]
        assert len(set(savings.values())) > 1, "Savings should vary by city"

    def test_standalone_retail_m0_negative_savings(self):
        """NightCycle is counterproductive for retail — savings should be negative."""
        result = generate_mock_result("standalone_retail", "Seoul", "m0", 2294)
        assert result["savings_pct"] < 0
        assert result["eui_kwh_m2"] == 151.83  # exact eplustbl: higher than baseline


class TestEnergyBreakdown:
    """Test energy component breakdown."""

    def test_components_sum_to_total(self):
        for btype in ["large_office", "hospital", "small_office"]:
            result = generate_mock_result(btype, "Seoul", "baseline", 10000)
            component_sum = result["hvac_energy_kwh"] + result["lighting_energy_kwh"] + result["equipment_energy_kwh"]
            assert component_sum <= result["total_energy_kwh"] * 1.01, (
                f"{btype}: components {component_sum:.0f} > total {result['total_energy_kwh']:.0f}"
            )

    def test_hvac_subcomponents_sum_to_hvac(self):
        result = generate_mock_result("large_office", "Seoul", "baseline", 10000)
        hvac_sub_sum = (
            result["cooling_energy_kwh"]
            + result["heating_energy_kwh"]
            + result["fan_energy_kwh"]
            + result["pump_energy_kwh"]
        )
        assert abs(hvac_sub_sum - result["hvac_energy_kwh"]) < 1.0


class TestFallback:
    """Test fallback behavior for missing data."""

    def test_unknown_building_type(self):
        result = generate_mock_result("warehouse", "Seoul", "baseline", 5000)
        assert result["eui_kwh_m2"] > 0
        assert result["total_energy_kwh"] > 0

    def test_unknown_city_uses_average(self):
        result = generate_mock_result("large_office", "Tokyo", "baseline", 10000)
        assert result["eui_kwh_m2"] > 0
        # Should be close to average baseline (~120.1)
        assert 115.0 < result["eui_kwh_m2"] < 125.0

    def test_hospital_strategy_uses_fallback(self):
        """Hospital has no strategy eplustbl — uses baseline × (1 - fallback%)."""
        bl = generate_mock_result("hospital", "Daegu", "baseline", 22422)
        m8 = generate_mock_result("hospital", "Daegu", "m8", 22422)
        assert bl["eui_kwh_m2"] == 340.2  # exact eplustbl
        # m8 = 340.2 × (1 - 4.5%) = 324.89
        assert abs(m8["eui_kwh_m2"] - 324.89) < 0.02

    def test_medium_office_fallback_strategies(self):
        """Medium office m1 has no eplustbl — uses baseline × (1 - 1.7%)."""
        generate_mock_result("medium_office", "Seoul", "baseline", 4982)
        m1 = generate_mock_result("medium_office", "Seoul", "m1", 4982)
        expected_m1 = round(77.57 * (1 - 1.7 / 100), 2)
        assert abs(m1["eui_kwh_m2"] - expected_m1) < 0.02


class TestResultFields:
    """Test result structure and fields."""

    def test_all_required_fields(self):
        result = generate_mock_result("large_office", "Seoul", "m3", 10000)
        required = [
            "total_energy_kwh",
            "hvac_energy_kwh",
            "cooling_energy_kwh",
            "heating_energy_kwh",
            "fan_energy_kwh",
            "eui_kwh_m2",
            "peak_demand_kw",
            "savings_pct",
            "annual_cost_krw",
            "annual_savings_krw",
            "is_mock",
        ]
        for field in required:
            assert field in result, f"Missing field: {field}"

    def test_is_mock_flag(self):
        result = generate_mock_result("large_office", "Seoul", "baseline", 10000)
        assert result["is_mock"] is True

    def test_all_building_types_produce_results(self):
        types = ["large_office", "medium_office", "small_office", "standalone_retail", "primary_school", "hospital"]
        for btype in types:
            result = generate_mock_result(btype, "Seoul", "baseline", 10000)
            assert result["eui_kwh_m2"] > 50, f"{btype} EUI too low"
            assert result["eui_kwh_m2"] < 400, f"{btype} EUI too high"

    def test_all_strategies_produce_results(self):
        strategies = ["baseline", "m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"]
        for strat in strategies:
            result = generate_mock_result("large_office", "Seoul", strat, 10000)
            assert result["total_energy_kwh"] > 0
            assert result["eui_kwh_m2"] > 0

    def test_area_scales_total_energy(self):
        small = generate_mock_result("large_office", "Seoul", "baseline", 1000)
        large = generate_mock_result("large_office", "Seoul", "baseline", 10000)
        # EUI is same, total scales with area
        assert small["eui_kwh_m2"] == large["eui_kwh_m2"]
        ratio = large["total_energy_kwh"] / small["total_energy_kwh"]
        assert 9.99 < ratio < 10.01

    def test_deterministic_results(self):
        r1 = generate_mock_result("large_office", "Seoul", "baseline", 10000)
        r2 = generate_mock_result("large_office", "Seoul", "baseline", 10000)
        assert r1["total_energy_kwh"] == r2["total_energy_kwh"]
        assert r1["eui_kwh_m2"] == r2["eui_kwh_m2"]


# ═══════════════════════════════════════════════════════════════════════════════
# User Config Sensitivity Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestUserConfigBackwardCompat:
    """user_config=None must produce identical results to current behavior."""

    def test_none_matches_exact_eui(self):
        """Every _EUI_TABLE entry: None gives exact eplustbl value."""
        for btype, strategies in _EUI_TABLE.items():
            for strategy, cities in strategies.items():
                for city, expected_eui in cities.items():
                    result = generate_mock_result(btype, city, strategy, 10000, user_config=None)
                    assert result["eui_kwh_m2"] == expected_eui, (
                        f"{btype}/{strategy}/{city}: expected {expected_eui}, got {result['eui_kwh_m2']}"
                    )

    def test_empty_config_matches_exact_eui(self):
        """Empty dict → factor=1.0 → exact eplustbl value."""
        for btype, strategies in _EUI_TABLE.items():
            for strategy, cities in strategies.items():
                for city, expected_eui in cities.items():
                    result = generate_mock_result(btype, city, strategy, 10000, user_config={})
                    assert result["eui_kwh_m2"] == expected_eui, (
                        f"{btype}/{strategy}/{city}: expected {expected_eui}, got {result['eui_kwh_m2']}"
                    )


class TestDOEDefaultsIdentity:
    """user_config matching DOE defaults must produce factor=1.0."""

    def test_large_office_doe_defaults_exact(self):
        config = dict(_DOE_DEFAULTS["large_office"])
        result = generate_mock_result("large_office", "Seoul", "baseline", 46320, user_config=config)
        assert result["eui_kwh_m2"] == 119.75

    def test_all_building_types_doe_defaults_exact(self):
        """For each building type, DOE defaults → exact eplustbl baseline."""
        for btype, defaults in _DOE_DEFAULTS.items():
            baseline_cities = _EUI_TABLE.get(btype, {}).get("baseline", {})
            config = dict(defaults)
            for city, expected_eui in baseline_cities.items():
                result = generate_mock_result(btype, city, "baseline", 10000, user_config=config)
                assert abs(result["eui_kwh_m2"] - expected_eui) < 0.01, (
                    f"{btype}/{city}: expected {expected_eui}, got {result['eui_kwh_m2']}"
                )


class TestSensitivityDirection:
    """Test that parameter changes affect EUI in the correct direction."""

    def _get_default_and_custom(self, btype, param, custom_val):
        config_default = dict(_DOE_DEFAULTS[btype])
        config_custom = dict(config_default)
        config_custom[param] = custom_val
        r_d = generate_mock_result(btype, "Seoul", "baseline", 10000, user_config=config_default)
        r_c = generate_mock_result(btype, "Seoul", "baseline", 10000, user_config=config_custom)
        return r_d["eui_kwh_m2"], r_c["eui_kwh_m2"]

    def test_higher_cooling_sp_reduces_eui(self):
        """Raising cooling setpoint (less cooling) should reduce EUI."""
        eui_d, eui_c = self._get_default_and_custom("large_office", "cooling_occupied", 26.0)
        assert eui_c < eui_d

    def test_lower_heating_sp_reduces_eui(self):
        """Lowering heating setpoint (less heating) should reduce EUI."""
        eui_d, eui_c = self._get_default_and_custom("large_office", "heating_occupied", 19.0)
        assert eui_c < eui_d

    def test_higher_cop_reduces_eui(self):
        """Higher COP means more efficient → lower EUI."""
        eui_d, eui_c = self._get_default_and_custom("large_office", "cop_cooling", 8.0)
        assert eui_c < eui_d

    def test_higher_lpd_increases_eui(self):
        """More lighting power density → higher EUI."""
        eui_d, eui_c = self._get_default_and_custom("large_office", "lpd", 16.0)
        assert eui_c > eui_d

    def test_higher_wwr_increases_eui(self):
        """More glass area → more solar gain → higher EUI."""
        eui_d, eui_c = self._get_default_and_custom("large_office", "wwr", 0.60)
        assert eui_c > eui_d


class TestSensitivityMagnitude:
    """Test that adjustments are within physically reasonable bounds."""

    def test_extreme_params_stay_in_bounds(self):
        """Even extreme configs should not produce absurd EUI."""
        extreme = {
            "cooling_occupied": 18.0,
            "heating_occupied": 25.0,
            "cop_cooling": 2.0,
            "efficiency_heating": 0.5,
            "wwr": 0.80,
            "lpd": 30.0,
            "epd": 30.0,
        }
        result = generate_mock_result("large_office", "Seoul", "baseline", 10000, user_config=extreme)
        # Factor clamped to [0.5, 2.0] → EUI in [~60, ~240]
        assert result["eui_kwh_m2"] <= 119.75 * 2.0 + 0.1
        assert result["eui_kwh_m2"] >= 119.75 * 0.5 - 0.1
        assert result["eui_kwh_m2"] > 0

    def test_2degree_setpoint_change_reasonable(self):
        """A 2-degree cooling setpoint change should produce ~0.5-5% EUI change."""
        config_default = dict(_DOE_DEFAULTS["large_office"])
        config_warm = dict(config_default)
        config_warm["cooling_occupied"] = 26.0
        r_d = generate_mock_result("large_office", "Seoul", "baseline", 10000, user_config=config_default)
        r_w = generate_mock_result("large_office", "Seoul", "baseline", 10000, user_config=config_warm)
        pct_change = abs(r_d["eui_kwh_m2"] - r_w["eui_kwh_m2"]) / r_d["eui_kwh_m2"] * 100
        assert 0.3 < pct_change < 5.0, f"2-degree change caused {pct_change:.2f}% EUI change"

    def test_savings_pct_preserved_with_config(self):
        """Strategy savings_pct should be similar regardless of user_config
        because the same factor applies to both strategy and baseline EUI."""
        config = {"lpd": 15.0, "epd": 15.0}
        generate_mock_result("large_office", "Seoul", "baseline", 10000, user_config=config)
        m8 = generate_mock_result("large_office", "Seoul", "m8", 10000, user_config=config)
        ref_m8 = generate_mock_result("large_office", "Seoul", "m8", 10000)
        if m8["savings_pct"] is not None and ref_m8["savings_pct"] is not None:
            assert abs(m8["savings_pct"] - ref_m8["savings_pct"]) < 0.5


class TestExtractUserConfig:
    """Test BPS JSON → flat config extraction."""

    def test_empty_bps_returns_empty(self):
        assert extract_user_config({}, "large_office") == {}

    def test_none_bps_returns_empty(self):
        assert extract_user_config(None, "large_office") == {}

    def test_extracts_setpoints(self):
        # Only values differing from BPS Pydantic defaults are extracted
        bps = {"setpoints": {"cooling_occupied": 25.0, "heating_occupied": 21.0}}
        config = extract_user_config(bps, "large_office")
        assert config["cooling_occupied"] == 25.0
        assert config["heating_occupied"] == 21.0

    def test_filters_bps_defaults(self):
        # Values matching BPS Pydantic defaults are excluded (user didn't set)
        bps = {"setpoints": {"cooling_occupied": 24.0, "heating_occupied": 20.0}}
        config = extract_user_config(bps, "large_office")
        assert "cooling_occupied" not in config
        assert "heating_occupied" not in config

    def test_extracts_chiller_cop(self):
        bps = {"hvac": {"system_type": "vav_chiller_boiler", "chillers": {"cop": 7.0}}}
        config = extract_user_config(bps, "large_office")
        assert config["cop_cooling"] == 7.0

    def test_extracts_vrf_cop(self):
        bps = {"hvac": {"system_type": "vrf", "vrf_outdoor_units": {"cop_cooling": 5.0, "cop_heating": 4.0}}}
        config = extract_user_config(bps, "medium_office")
        assert config["cop_cooling"] == 5.0
        assert config["efficiency_heating"] == 4.0

    def test_extracts_wwr_scalar(self):
        bps = {"geometry": {"wwr": 0.45}}
        config = extract_user_config(bps, "large_office")
        assert config["wwr"] == 0.45

    def test_extracts_wwr_per_facade(self):
        bps = {"geometry": {"wwr": {"north": 0.2, "south": 0.6, "east": 0.3, "west": 0.3}}}
        config = extract_user_config(bps, "large_office")
        assert config["wwr"] == 0.35

    def test_extracts_envelope(self):
        bps = {"envelope": {"wall_u_value": 0.50, "window_shgc": 0.35}}
        config = extract_user_config(bps, "large_office")
        assert config["wall_u_value"] == 0.50
        assert config["window_shgc"] == 0.35

    def test_extracts_internal_loads(self):
        bps = {"internal_loads": {"lighting_power_density": 12.0, "equipment_power_density": 8.0}}
        config = extract_user_config(bps, "large_office")
        assert config["lpd"] == 12.0
        assert config["epd"] == 8.0


class TestComputeAdjustmentFactor:
    """Test the core factor computation in isolation."""

    def test_empty_config_returns_one(self):
        assert _compute_adjustment_factor("large_office", "Seoul", {}) == 1.0

    def test_doe_defaults_returns_one(self):
        defaults = dict(_DOE_DEFAULTS["large_office"])
        factor = _compute_adjustment_factor("large_office", "Seoul", defaults)
        assert abs(factor - 1.0) < 1e-10

    def test_all_building_doe_defaults_return_one(self):
        """Every building type's DOE defaults should produce factor=1.0."""
        for btype, defaults in _DOE_DEFAULTS.items():
            factor = _compute_adjustment_factor(btype, "Seoul", dict(defaults))
            assert abs(factor - 1.0) < 1e-10, f"{btype}: DOE defaults produced factor={factor}, expected 1.0"

    def test_factor_clamped_at_bounds(self):
        extreme = {"cop_cooling": 0.5, "lpd": 50.0, "epd": 100.0}
        factor = _compute_adjustment_factor("large_office", "Seoul", extreme)
        assert factor <= 2.0
        assert factor >= 0.5


class TestMonthlyProfile:
    """Test monthly energy profile generation."""

    def test_profile_has_12_months(self):
        profile = _generate_monthly_profile(
            cooling_kwh=50000,
            heating_kwh=30000,
            fan_kwh=8000,
            pump_kwh=4000,
            lighting_kwh=20000,
            equipment_kwh=40000,
            climate_city="Seoul",
        )
        assert len(profile) == 12
        assert profile[0]["month"] == "Jan"
        assert profile[11]["month"] == "Dec"

    def test_profile_sums_match_annual(self):
        cooling, heating = 50000.0, 30000.0
        fan, pump = 8000.0, 4000.0
        lighting, equipment = 20000.0, 40000.0
        total_annual = cooling + heating + fan + pump + lighting + equipment

        profile = _generate_monthly_profile(
            cooling_kwh=cooling,
            heating_kwh=heating,
            fan_kwh=fan,
            pump_kwh=pump,
            lighting_kwh=lighting,
            equipment_kwh=equipment,
            climate_city="Seoul",
        )
        profile_total = sum(m["total"] for m in profile)
        # Allow small rounding tolerance
        assert abs(profile_total - total_annual) < total_annual * 0.02

    def test_cooling_peak_in_summer(self):
        profile = _generate_monthly_profile(
            cooling_kwh=100000,
            heating_kwh=50000,
            fan_kwh=10000,
            pump_kwh=5000,
            lighting_kwh=20000,
            equipment_kwh=30000,
            climate_city="Seoul",
        )
        cooling_values = [m["cooling"] for m in profile]
        peak_month_idx = cooling_values.index(max(cooling_values))
        assert peak_month_idx in (5, 6, 7), f"Cooling peak in month {peak_month_idx}, expected Jun-Aug"

    def test_heating_peak_in_winter(self):
        profile = _generate_monthly_profile(
            cooling_kwh=50000,
            heating_kwh=100000,
            fan_kwh=10000,
            pump_kwh=5000,
            lighting_kwh=20000,
            equipment_kwh=30000,
            climate_city="Seoul",
        )
        heating_values = [m["heating"] for m in profile]
        peak_month_idx = heating_values.index(max(heating_values))
        assert peak_month_idx in (0, 1, 11), f"Heating peak in month {peak_month_idx}, expected Dec-Feb"

    def test_lighting_equipment_uniform(self):
        profile = _generate_monthly_profile(
            cooling_kwh=50000,
            heating_kwh=30000,
            fan_kwh=8000,
            pump_kwh=4000,
            lighting_kwh=12000,
            equipment_kwh=24000,
            climate_city="Jeju",
        )
        # All months should have same lighting and equipment
        lighting_values = set(m["lighting"] for m in profile)
        equipment_values = set(m["equipment"] for m in profile)
        assert len(lighting_values) == 1, "Lighting should be uniform"
        assert len(equipment_values) == 1, "Equipment should be uniform"

    def test_generate_mock_result_includes_monthly(self):
        result = generate_mock_result(
            building_type="large_office",
            climate_city="Seoul",
            strategy="baseline",
            total_floor_area_m2=10000,
        )
        assert "monthly_profile" in result
        assert len(result["monthly_profile"]) == 12
        assert all("total" in m for m in result["monthly_profile"])

    def test_all_cities_have_profiles(self):
        cities = ["Seoul", "Busan", "Daegu", "Daejeon", "Gwangju", "Incheon", "Gangneung", "Jeju", "Cheongju", "Ulsan"]
        for city in cities:
            result = generate_mock_result(
                building_type="medium_office",
                climate_city=city,
                strategy="baseline",
                total_floor_area_m2=5000,
            )
            assert len(result["monthly_profile"]) == 12, f"Missing profile for {city}"


# =====================================================================
# New sensitivity parameters: schedule, infiltration, occupancy, envelope
# =====================================================================


class TestScheduleSensitivity:
    """Test operating hours / schedule sensitivity."""

    def test_longer_hours_increases_eui(self):
        """Building running 06:00-22:00 should use more energy than 08:00-18:00."""
        base = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        long_hours = generate_mock_result(
            "large_office",
            "Seoul",
            "baseline",
            46320,
            user_config={"operating_hours_start": 6, "operating_hours_end": 22},
        )
        assert long_hours["eui_kwh_m2"] > base["eui_kwh_m2"]

    def test_shorter_hours_decreases_eui(self):
        """Building running 09:00-17:00 should use less energy."""
        base = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        short_hours = generate_mock_result(
            "large_office",
            "Seoul",
            "baseline",
            46320,
            user_config={"operating_hours_start": 9, "operating_hours_end": 17},
        )
        assert short_hours["eui_kwh_m2"] < base["eui_kwh_m2"]

    def test_more_workdays_increases_eui(self):
        """6-day workweek should use more energy than 5-day."""
        base = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        six_day = generate_mock_result(
            "large_office",
            "Seoul",
            "baseline",
            46320,
            user_config={"workdays_per_week": 6},
        )
        assert six_day["eui_kwh_m2"] > base["eui_kwh_m2"]

    def test_saturday_full_day_increases_eui(self):
        """Full Saturday (1.0) vs half day (0.5) should increase energy."""
        base = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        full_sat = generate_mock_result(
            "large_office",
            "Seoul",
            "baseline",
            46320,
            user_config={"saturday_factor": 1.0},
        )
        assert full_sat["eui_kwh_m2"] > base["eui_kwh_m2"]

    def test_schedule_factor_identity(self):
        """Default schedule params should return factor=1.0."""
        defaults = _DOE_DEFAULTS["large_office"]
        sched_cfg = {
            "operating_hours_start": defaults["operating_hours_start"],
            "operating_hours_end": defaults["operating_hours_end"],
            "workdays_per_week": defaults["workdays_per_week"],
            "saturday_factor": defaults["saturday_factor"],
        }
        factor = _compute_schedule_factor(defaults, sched_cfg)
        assert abs(factor - 1.0) < 1e-10

    def test_schedule_factor_range(self):
        """Extreme schedules should stay within [0.3, 3.0]."""
        defaults = _DOE_DEFAULTS["large_office"]
        # Near-24/7 operation
        extreme = {
            "operating_hours_start": 0,
            "operating_hours_end": 24,
            "workdays_per_week": 7,
            "saturday_factor": 1.0,
        }
        factor = _compute_schedule_factor(defaults, extreme)
        assert 0.3 <= factor <= 3.0

    def test_parse_hour(self):
        assert _parse_hour("08:00") == 8.0
        assert _parse_hour("08:30") == 8.5
        assert _parse_hour("22:00") == 22.0
        assert _parse_hour("00:00") == 0.0


class TestInfiltrationSensitivity:
    """Test infiltration ACH sensitivity."""

    def test_higher_infiltration_increases_eui(self):
        """Doubling infiltration should increase EUI."""
        base = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        high_inf = generate_mock_result(
            "large_office",
            "Seoul",
            "baseline",
            46320,
            user_config={"infiltration_ach": 1.0},
        )
        assert high_inf["eui_kwh_m2"] > base["eui_kwh_m2"]

    def test_lower_infiltration_decreases_eui(self):
        """Tight envelope (low infiltration) should decrease EUI."""
        base = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        low_inf = generate_mock_result(
            "large_office",
            "Seoul",
            "baseline",
            46320,
            user_config={"infiltration_ach": 0.2},
        )
        assert low_inf["eui_kwh_m2"] < base["eui_kwh_m2"]

    def test_infiltration_magnitude_reasonable(self):
        """Doubling infiltration should change EUI by ~5-15% (not 40% overall)."""
        base = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        double = generate_mock_result(
            "large_office",
            "Seoul",
            "baseline",
            46320,
            user_config={"infiltration_ach": 1.0},
        )
        pct_change = (double["eui_kwh_m2"] - base["eui_kwh_m2"]) / base["eui_kwh_m2"] * 100
        assert 1.0 < pct_change < 20.0, f"Infiltration doubling: {pct_change:.1f}% change"


class TestOccupancySensitivity:
    """Test people density sensitivity."""

    def test_higher_density_increases_eui(self):
        """More people → more cooling + ventilation → higher EUI."""
        base = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        dense = generate_mock_result(
            "large_office",
            "Seoul",
            "baseline",
            46320,
            user_config={"people_density": 0.10},
        )
        assert dense["eui_kwh_m2"] > base["eui_kwh_m2"]

    def test_lower_density_decreases_eui(self):
        """Fewer people → less energy."""
        base = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        sparse = generate_mock_result(
            "large_office",
            "Seoul",
            "baseline",
            46320,
            user_config={"people_density": 0.02},
        )
        assert sparse["eui_kwh_m2"] < base["eui_kwh_m2"]


class TestEnvelopeExtendedSensitivity:
    """Test roof U-value and window U-value sensitivity."""

    def test_higher_roof_u_increases_eui(self):
        """Poorly insulated roof → more HVAC → higher EUI."""
        base = generate_mock_result("standalone_retail", "Seoul", "baseline", 2294)
        poor_roof = generate_mock_result(
            "standalone_retail",
            "Seoul",
            "baseline",
            2294,
            user_config={"roof_u_value": 0.60},
        )
        assert poor_roof["eui_kwh_m2"] > base["eui_kwh_m2"]

    def test_lower_roof_u_decreases_eui(self):
        """Well insulated roof → less HVAC."""
        base = generate_mock_result("standalone_retail", "Seoul", "baseline", 2294)
        good_roof = generate_mock_result(
            "standalone_retail",
            "Seoul",
            "baseline",
            2294,
            user_config={"roof_u_value": 0.15},
        )
        assert good_roof["eui_kwh_m2"] < base["eui_kwh_m2"]

    def test_higher_window_u_increases_eui(self):
        """Higher window U-value → more conductive loss → higher EUI."""
        base = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        poor_glass = generate_mock_result(
            "large_office",
            "Seoul",
            "baseline",
            46320,
            user_config={"window_u_value": 4.0},
        )
        assert poor_glass["eui_kwh_m2"] > base["eui_kwh_m2"]

    def test_lower_window_u_decreases_eui(self):
        """Triple-glazing (low U) → less conductive loss."""
        base = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        good_glass = generate_mock_result(
            "large_office",
            "Seoul",
            "baseline",
            46320,
            user_config={"window_u_value": 1.0},
        )
        assert good_glass["eui_kwh_m2"] < base["eui_kwh_m2"]


class TestExtractNewParams:
    """Test extraction of newly added BPS parameters."""

    def test_extract_infiltration(self):
        bps = {"envelope": {"infiltration_ach": 0.8}}
        cfg = extract_user_config(bps, "large_office")
        assert cfg["infiltration_ach"] == 0.8

    def test_extract_people_density(self):
        bps = {"internal_loads": {"people_density": 0.10}}
        cfg = extract_user_config(bps, "large_office")
        assert cfg["people_density"] == 0.10

    def test_extract_roof_u_value(self):
        bps = {"envelope": {"roof_u_value": 0.40}}
        cfg = extract_user_config(bps, "large_office")
        assert cfg["roof_u_value"] == 0.40

    def test_extract_window_u_value(self):
        bps = {"envelope": {"window_u_value": 3.0}}
        cfg = extract_user_config(bps, "large_office")
        assert cfg["window_u_value"] == 3.0

    def test_extract_schedule_params(self):
        bps = {
            "schedules": {
                "operating_hours": {"start": "06:00", "end": "22:00"},
                "workdays": ["mon", "tue", "wed", "thu", "fri", "sat"],
                "saturday": "full_day",
            },
        }
        cfg = extract_user_config(bps, "large_office")
        assert cfg["operating_hours_start"] == 6.0
        assert cfg["operating_hours_end"] == 22.0
        assert cfg["workdays_per_week"] == 6.0
        assert cfg["saturday_factor"] == 1.0

    def test_extract_schedule_off_saturday(self):
        bps = {"schedules": {"saturday": "off"}}
        cfg = extract_user_config(bps, "large_office")
        assert cfg["saturday_factor"] == 0.0

    def test_combined_new_params_all_directions(self):
        """All new params at once should produce factor != 1.0."""
        cfg = {
            "infiltration_ach": 1.0,  # higher → +
            "people_density": 0.10,  # higher → +
            "roof_u_value": 0.50,  # higher → +
            "window_u_value": 3.5,  # higher → +
            "operating_hours_start": 6,  # earlier → +
            "operating_hours_end": 22,  # later → +
        }
        factor = _compute_adjustment_factor("large_office", "Seoul", cfg)
        assert factor > 1.0, f"Combined increases should raise EUI, got factor={factor}"
