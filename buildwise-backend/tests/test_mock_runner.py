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
        # With deterministic seed, M8 should always be lower
        assert m8["eui_kwh_m2"] < baseline["eui_kwh_m2"]

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
        assert jeju["eui_kwh_m2"] < seoul["eui_kwh_m2"]

    def test_area_scales_total_energy(self):
        small = generate_mock_result("large_office", "Seoul", "baseline", 1000)
        large = generate_mock_result("large_office", "Seoul", "baseline", 10000)
        # Total energy should scale exactly with area (same seed = same noise)
        ratio = large["total_energy_kwh"] / small["total_energy_kwh"]
        assert 9.9 < ratio < 10.1  # Should be exactly 10x with deterministic seed

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

    # --- New tests for audit findings ---

    def test_breakdown_sums_to_total(self):
        """Verify energy breakdown components sum to <= total energy (hierarchical)."""
        for btype in ["large_office", "hospital", "small_office"]:
            result = generate_mock_result(btype, "Seoul", "baseline", 10000)
            # Top-level: hvac + lighting + equipment should be <= total
            component_sum = (
                result["hvac_energy_kwh"]
                + result["lighting_energy_kwh"]
                + result["equipment_energy_kwh"]
            )
            assert component_sum <= result["total_energy_kwh"] * 1.01, (
                f"{btype}: component sum {component_sum:.0f} exceeds total {result['total_energy_kwh']:.0f}"
            )

    def test_hvac_subcomponents_sum_to_hvac(self):
        """Verify HVAC sub-components (cooling+heating+fan+pump) sum to HVAC total."""
        result = generate_mock_result("large_office", "Seoul", "baseline", 10000)
        hvac_sub_sum = (
            result["cooling_energy_kwh"]
            + result["heating_energy_kwh"]
            + result["fan_energy_kwh"]
            + result["pump_energy_kwh"]
        )
        assert abs(hvac_sub_sum - result["hvac_energy_kwh"]) < 1.0, (
            f"HVAC sub-sum {hvac_sub_sum:.0f} != HVAC total {result['hvac_energy_kwh']:.0f}"
        )

    def test_deterministic_seed_same_building(self):
        """Same building params should produce identical results on repeated calls."""
        r1 = generate_mock_result("large_office", "Seoul", "baseline", 10000)
        r2 = generate_mock_result("large_office", "Seoul", "baseline", 10000)
        assert r1["total_energy_kwh"] == r2["total_energy_kwh"]
        assert r1["eui_kwh_m2"] == r2["eui_kwh_m2"]

    def test_deterministic_seed_different_strategies_consistent_baseline(self):
        """Different strategies for same building should show consistent savings."""
        baseline = generate_mock_result("large_office", "Seoul", "baseline", 10000)
        m8 = generate_mock_result("large_office", "Seoul", "m8", 10000)

        # The savings_pct stored in m8 should match the actual EUI difference
        actual_savings_pct = (baseline["eui_kwh_m2"] - m8["eui_kwh_m2"]) / baseline["eui_kwh_m2"] * 100
        declared_savings_pct = m8["savings_pct"]
        assert abs(actual_savings_pct - declared_savings_pct) < 0.5, (
            f"Actual savings {actual_savings_pct:.1f}% != declared {declared_savings_pct:.1f}%"
        )

    def test_savings_kwh_consistent_with_energy_difference(self):
        """Savings kWh should match baseline_total - strategy_total."""
        baseline = generate_mock_result("large_office", "Seoul", "baseline", 10000)
        m3 = generate_mock_result("large_office", "Seoul", "m3", 10000)

        expected_savings = baseline["total_energy_kwh"] - m3["total_energy_kwh"]
        assert abs(m3["savings_kwh"] - expected_savings) < 1.0, (
            f"savings_kwh {m3['savings_kwh']:.0f} != expected {expected_savings:.0f}"
        )
