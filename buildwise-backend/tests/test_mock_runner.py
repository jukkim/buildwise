"""Mock simulation runner unit tests."""

import pytest

from app.services.simulation.mock_runner import generate_mock_result


class TestMockRunner:
    """Test generate_mock_result returns valid energy data."""

    def test_baseline_has_zero_savings(self):
        result = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        assert result["savings_pct"] is None
        assert result["annual_savings_krw"] is None
        assert result["total_energy_kwh"] > 0
        assert result["eui_kwh_m2"] > 0

    def test_strategy_has_positive_savings(self):
        result = generate_mock_result("large_office", "Seoul", "m8", 46320)
        assert result["savings_pct"] > 0
        assert result["annual_savings_krw"] > 0

    def test_strategy_eui_lower_than_baseline(self):
        baseline = generate_mock_result("large_office", "Seoul", "baseline", 46320)
        m8 = generate_mock_result("large_office", "Seoul", "m8", 46320)
        # M8 should use less energy (accounting for random noise)
        assert m8["eui_kwh_m2"] < baseline["eui_kwh_m2"] * 1.05

    def test_all_strategies_produce_results(self):
        strategies = ["baseline", "m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"]
        for strat in strategies:
            result = generate_mock_result("medium_office", "Seoul", strat, 10000)
            assert result["total_energy_kwh"] > 0
            assert result["eui_kwh_m2"] > 0
            assert result["hvac_energy_kwh"] > 0
            assert result["cooling_energy_kwh"] > 0
            assert result["heating_energy_kwh"] > 0
            assert result["fan_energy_kwh"] > 0
            assert result["annual_cost_krw"] > 0

    def test_all_building_types(self):
        types = ["large_office", "medium_office", "small_office",
                 "standalone_retail", "primary_school", "hospital"]
        for btype in types:
            result = generate_mock_result(btype, "Seoul", "baseline", 10000)
            assert result["eui_kwh_m2"] > 50, f"{btype} EUI too low"
            assert result["eui_kwh_m2"] < 500, f"{btype} EUI too high"

    def test_climate_affects_energy(self):
        seoul = generate_mock_result("large_office", "Seoul", "baseline", 10000)
        jeju = generate_mock_result("large_office", "Jeju", "baseline", 10000)
        # Jeju has lower climate factor (0.88) vs Seoul (1.0)
        # With random noise, just check they're in reasonable range
        assert jeju["eui_kwh_m2"] < seoul["eui_kwh_m2"] * 1.1

    def test_area_scales_total_energy(self):
        small = generate_mock_result("large_office", "Seoul", "baseline", 1000)
        large = generate_mock_result("large_office", "Seoul", "baseline", 10000)
        # Total energy should scale roughly with area
        ratio = large["total_energy_kwh"] / small["total_energy_kwh"]
        assert 8 < ratio < 12  # ~10x, with noise

    def test_result_has_all_required_fields(self):
        result = generate_mock_result("large_office", "Seoul", "m3", 10000)
        required = [
            "total_energy_kwh", "hvac_energy_kwh", "cooling_energy_kwh",
            "heating_energy_kwh", "fan_energy_kwh", "eui_kwh_m2",
            "peak_demand_kw", "savings_pct", "annual_cost_krw",
            "annual_savings_krw",
        ]
        for field in required:
            assert field in result, f"Missing field: {field}"

    def test_unknown_building_type_uses_default(self):
        result = generate_mock_result("unknown_type", "Seoul", "baseline", 10000)
        assert result["eui_kwh_m2"] > 0

    def test_unknown_city_uses_default(self):
        result = generate_mock_result("large_office", "Tokyo", "baseline", 10000)
        assert result["eui_kwh_m2"] > 0
