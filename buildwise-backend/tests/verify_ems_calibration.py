"""Verify BuildWise mock runner produces EXACT eplustbl.csv EUI values.

Checks that generate_mock_result returns the precise per-city EUI from
ems_simulation eplustbl.csv data for every known building/city/strategy.

Source: ems_simulation/buildings/*/results/default/*/1year/*/eplustbl.csv
Run: python -m tests.verify_ems_calibration
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.simulation.mock_runner import (
    _BASE_EUI,
    _EUI_TABLE,
    generate_mock_result,
)

# Reference floor areas (m2)
FLOOR_AREAS = {
    "large_office": 46320,
    "medium_office": 4982,
    "small_office": 511,
    "standalone_retail": 2294,
    "primary_school": 6871,
    "hospital": 22422,
}

# Expected average baseline EUI (kWh/m2) from eplustbl
EXPECTED_AVG_EUI = {
    "large_office": 120.1,
    "medium_office": 77.8,
    "small_office": 97.8,
    "standalone_retail": 125.6,
    "primary_school": 139.5,
    "hospital": 339.6,
}


def separator(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def check(label: str, expected: float, actual: float, unit: str = "", tol: float = 0.01) -> bool:
    diff = abs(expected - actual)
    status = "PASS" if diff <= tol else "FAIL"
    icon = "[OK]" if status == "PASS" else "[!!]"
    print(f"  {icon} {label:45s}  exp={expected:>8.2f}  act={actual:>8.2f}  d={diff:.3f} {unit}")
    return status == "PASS"


def main():
    all_pass = True
    fail_count = 0
    pass_count = 0

    # ═══════════════════════════════════════════════════════════════
    # Test 1: Average baseline EUI matches
    # ═══════════════════════════════════════════════════════════════
    separator("Test 1: Average baseline EUI (_BASE_EUI)")

    for btype, expected in EXPECTED_AVG_EUI.items():
        actual = _BASE_EUI.get(btype, 0.0)
        ok = check(f"{btype} avg EUI", expected, actual, "kWh/m2", tol=0.15)
        if ok:
            pass_count += 1
        else:
            fail_count += 1
            all_pass = False

    # ═══════════════════════════════════════════════════════════════
    # Test 2: Per-city EXACT EUI match for ALL strategies
    # ═══════════════════════════════════════════════════════════════
    separator("Test 2: Per-city exact EUI (generate_mock_result vs _EUI_TABLE)")

    for btype, strategies in _EUI_TABLE.items():
        area = float(FLOOR_AREAS.get(btype, 10000))
        strategy_count = 0
        strategy_pass = 0

        for strategy, cities in strategies.items():
            for city, expected_eui in cities.items():
                result = generate_mock_result(btype, city, strategy, area)
                actual_eui = result["eui_kwh_m2"]
                ok = check(
                    f"{btype}/{strategy}/{city}",
                    expected_eui,
                    actual_eui,
                    "kWh/m2",
                    tol=0.01,
                )
                strategy_count += 1
                if ok:
                    pass_count += 1
                    strategy_pass += 1
                else:
                    fail_count += 1
                    all_pass = False

        print(f"\n  >>> {btype}: {strategy_pass}/{strategy_count} exact matches")

    # ═══════════════════════════════════════════════════════════════
    # Test 3: Savings consistency (savings_kwh = baseline - strategy)
    # ═══════════════════════════════════════════════════════════════
    separator("Test 3: Savings kWh consistency")

    test_cases = [
        ("large_office", "Seoul", "m8"),
        ("large_office", "Jeju", "m2"),
        ("small_office", "Seoul", "m8"),
        ("standalone_retail", "Busan", "m5"),
        ("primary_school", "Daegu", "m7"),
        ("medium_office", "Seoul", "m4"),
    ]

    for btype, city, strategy in test_cases:
        area = float(FLOOR_AREAS.get(btype, 10000))
        baseline = generate_mock_result(btype, city, "baseline", area)
        strat = generate_mock_result(btype, city, strategy, area)
        expected_savings = baseline["total_energy_kwh"] - strat["total_energy_kwh"]
        if strat["savings_kwh"] is not None:
            ok = check(
                f"{btype}/{city}/{strategy} savings_kwh",
                expected_savings,
                strat["savings_kwh"],
                "kWh",
                tol=1.0,
            )
        else:
            ok = False
            print(f"  [!!] {btype}/{city}/{strategy}: savings_kwh is None")
        if ok:
            pass_count += 1
        else:
            fail_count += 1
            all_pass = False

    # ═══════════════════════════════════════════════════════════════
    # Test 4: Per-city savings_pct varies by city (not fixed)
    # ═══════════════════════════════════════════════════════════════
    separator("Test 4: Per-city savings_pct variation")

    # large_office m8: savings should differ by city
    m8_savings = {}
    for city in ["Seoul", "Busan", "Daegu", "Jeju", "Gangneung"]:
        r = generate_mock_result("large_office", city, "m8", 46320.0)
        m8_savings[city] = r["savings_pct"]
        print(f"  large_office/m8/{city}: savings = {r['savings_pct']:.1f}%")

    # Verify savings are NOT all identical (they should vary by city)
    unique_savings = len(set(m8_savings.values()))
    ok = unique_savings > 1
    icon = "[OK]" if ok else "[!!]"
    print(f"\n  {icon} {unique_savings} unique savings values across 5 cities (expected >1)")
    if ok:
        pass_count += 1
    else:
        fail_count += 1
        all_pass = False

    # ═══════════════════════════════════════════════════════════════
    # Test 5: Standalone retail m0 shows energy INCREASE (counterproductive)
    # ═══════════════════════════════════════════════════════════════
    separator("Test 5: Standalone retail m0 = counterproductive")

    r_bl = generate_mock_result("standalone_retail", "Seoul", "baseline", 2294.0)
    r_m0 = generate_mock_result("standalone_retail", "Seoul", "m0", 2294.0)

    print(f"  baseline EUI = {r_bl['eui_kwh_m2']}")
    print(f"  m0 EUI      = {r_m0['eui_kwh_m2']}")
    print(f"  savings_pct = {r_m0['savings_pct']}%")

    ok = r_m0["eui_kwh_m2"] > r_bl["eui_kwh_m2"]
    icon = "[OK]" if ok else "[!!]"
    print(f"  {icon} m0 EUI > baseline (counterproductive NightCycle)")
    if ok:
        pass_count += 1
    else:
        fail_count += 1
        all_pass = False

    ok = r_m0["savings_pct"] < 0
    icon = "[OK]" if ok else "[!!]"
    print(f"  {icon} savings_pct is negative: {r_m0['savings_pct']}%")
    if ok:
        pass_count += 1
    else:
        fail_count += 1
        all_pass = False

    # ═══════════════════════════════════════════════════════════════
    # Test 6: Energy breakdown consistency
    # ═══════════════════════════════════════════════════════════════
    separator("Test 6: Energy breakdown consistency")

    for btype in FLOOR_AREAS:
        area = float(FLOOR_AREAS[btype])
        r = generate_mock_result(btype, "Seoul", "baseline", area)
        total = r["total_energy_kwh"]
        components = r["hvac_energy_kwh"] + r["lighting_energy_kwh"] + r["equipment_energy_kwh"]
        ratio = components / total * 100
        ok = 88.0 <= ratio <= 100.0
        icon = "[OK]" if ok else "[!!]"
        print(f"  {icon} {btype:20s}  components/total = {ratio:.1f}%")
        if ok:
            pass_count += 1
        else:
            fail_count += 1
            all_pass = False

        # HVAC sub-components sum
        hvac_sum = r["cooling_energy_kwh"] + r["heating_energy_kwh"] + r["fan_energy_kwh"] + r["pump_energy_kwh"]
        hvac_diff = abs(hvac_sum - r["hvac_energy_kwh"])
        ok = hvac_diff < 1.0
        icon = "[OK]" if ok else "[!!]"
        print(f"  {icon} {btype:20s}  HVAC diff = {hvac_diff:.2f}")
        if ok:
            pass_count += 1
        else:
            fail_count += 1
            all_pass = False

    # ═══════════════════════════════════════════════════════════════
    # Test 7: Fallback for unknown city uses average
    # ═══════════════════════════════════════════════════════════════
    separator("Test 7: Fallback for unknown city")

    r = generate_mock_result("large_office", "Tokyo", "baseline", 10000.0)
    avg_eui = _BASE_EUI["large_office"]
    ok = check("large_office/Tokyo/baseline → avg", avg_eui, r["eui_kwh_m2"], "kWh/m2", tol=0.15)
    if ok:
        pass_count += 1
    else:
        fail_count += 1
        all_pass = False

    # ═══════════════════════════════════════════════════════════════
    # Test 8: Fallback for unknown building type
    # ═══════════════════════════════════════════════════════════════
    separator("Test 8: Fallback for unknown building type")

    r = generate_mock_result("warehouse", "Seoul", "baseline", 5000.0)
    ok = r["eui_kwh_m2"] > 0
    icon = "[OK]" if ok else "[!!]"
    print(f"  {icon} warehouse/Seoul/baseline EUI = {r['eui_kwh_m2']:.2f} (default)")
    if ok:
        pass_count += 1
    else:
        fail_count += 1
        all_pass = False

    # ═══════════════════════════════════════════════════════════════
    # Test 9: Hospital fallback strategies (baseline only in eplustbl)
    # ═══════════════════════════════════════════════════════════════
    separator("Test 9: Hospital fallback strategies")

    # Hospital has baseline for 8 cities, no strategy data
    # Strategy EUI should be baseline × (1 - fallback%)
    r_bl = generate_mock_result("hospital", "Daegu", "baseline", 22422.0)
    r_m8 = generate_mock_result("hospital", "Daegu", "m8", 22422.0)

    expected_bl = 340.2  # exact eplustbl
    ok = check("hospital/Daegu/baseline", expected_bl, r_bl["eui_kwh_m2"], "kWh/m2", tol=0.01)
    if ok:
        pass_count += 1
    else:
        fail_count += 1
        all_pass = False

    # m8 = baseline × (1 - 4.5/100) = 340.2 × 0.955 = 324.891
    expected_m8 = round(340.2 * (1 - 4.5 / 100), 2)
    ok = check("hospital/Daegu/m8 (fallback)", expected_m8, r_m8["eui_kwh_m2"], "kWh/m2", tol=0.01)
    if ok:
        pass_count += 1
    else:
        fail_count += 1
        all_pass = False

    ok = r_m8["savings_pct"] == 4.5
    icon = "[OK]" if ok else "[!!]"
    print(f"  {icon} hospital/m8 savings = {r_m8['savings_pct']}% (expected 4.5%)")
    if ok:
        pass_count += 1
    else:
        fail_count += 1
        all_pass = False

    # ═══════════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════════
    separator("SUMMARY")
    total = pass_count + fail_count
    print(f"\n  Total: {total} checks")
    print(f"  Passed: {pass_count}")
    print(f"  Failed: {fail_count}")

    if all_pass:
        print("\n  *** ALL CHECKS PASSED — mock runner matches eplustbl.csv exactly ***")
    else:
        print(f"\n  *** {fail_count} CHECKS FAILED — review calibration ***")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
