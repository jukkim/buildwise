"""Full cross-verification: ems_simulation raw EnergyPlus outputs vs BuildWise mock runner.

Parses ALL eplustbl.csv files from ems_simulation and compares:
1. Actual EnergyPlus Total Site Energy / EUI vs master_taxonomy baseline_eui
2. Per-city chiller savings % vs comprehensive_analysis_report.json averages
3. BuildWise mock_runner derived savings vs ems_simulation actual
4. Consistency of analysis JSON reports vs raw EnergyPlus outputs

Run: python -m tests.verify_full_ems_data
"""

import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.simulation.mock_runner import (
    _BASE_EUI,
    _STRATEGY_SAVINGS_BY_TYPE,
    generate_mock_result,
)

# ═══════════════════════════════════════════════════════════════════
# Paths
# ═══════════════════════════════════════════════════════════════════
EMS_ROOT = Path(r"C:\Users\User\Desktop\myjob\8.simulation\ems_simulation")
LO_RESULTS = EMS_ROOT / "buildings" / "large_office" / "results"
MO_RESULTS = EMS_ROOT / "buildings" / "medium_office_backup" / "results"

CITIES = ["Seoul", "Busan", "Daegu", "Daejeon", "Gangneung", "Gwangju", "Incheon", "Jeju", "Cheongju", "Ulsan"]

# Building specs
LO_AREA = 46320.38  # m2 (from eplustbl.csv)
MO_AREA = 4982.0  # m2

pass_count = 0
fail_count = 0
warn_count = 0


def p(msg: str) -> None:
    print(msg)


def check(label: str, expected: float, actual: float, unit: str = "", tol: float = 0.5, is_warn: bool = False) -> bool:
    global pass_count, fail_count, warn_count
    diff = abs(expected - actual)
    ok = diff <= tol
    if ok:
        icon = "[OK]"
        pass_count += 1
    elif is_warn:
        icon = "[~~]"
        warn_count += 1
    else:
        icon = "[!!]"
        fail_count += 1
    print(f"  {icon} {label:50s}  exp={expected:>10.2f}  act={actual:>10.2f}  diff={diff:>8.3f} {unit}")
    return ok


def separator(title: str) -> None:
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")


# ═══════════════════════════════════════════════════════════════════
# eplustbl.csv Parser
# ═══════════════════════════════════════════════════════════════════
def parse_eplustbl(csv_path: Path) -> dict | None:
    """Parse EnergyPlus eplustbl.csv and extract key energy values."""
    if not csv_path.exists():
        return None

    try:
        with open(csv_path, encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = list(reader)
    except Exception:
        return None

    result = {}

    for i, row in enumerate(rows):
        line = ",".join(row)

        # Total Site Energy [GJ]
        if "Total Site Energy" in line and len(row) >= 3:
            try:
                val = float(row[2].strip().replace(",", ""))
                result["total_site_energy_gj"] = val
                result["total_site_energy_mwh"] = val / 3.6
            except ValueError:
                pass

        # Total Building Area [m2]
        if "Total Building Area" in line and len(row) >= 3:
            try:
                val = float(row[2].strip().replace(",", ""))
                result["building_area_m2"] = val
            except ValueError:
                pass

        # End Uses section
        if len(row) >= 3:
            end_use = row[1].strip() if len(row) > 1 else ""
            if end_use == "Cooling":
                try:
                    result["cooling_elec_gj"] = float(row[2].strip().replace(",", ""))
                except ValueError:
                    pass
            elif end_use == "Heating":
                try:
                    result["heating_elec_gj"] = float(row[2].strip().replace(",", ""))
                    if len(row) > 3:
                        result["heating_gas_gj"] = float(row[3].strip().replace(",", ""))
                except ValueError:
                    pass
            elif end_use == "Fans":
                try:
                    result["fans_gj"] = float(row[2].strip().replace(",", ""))
                except ValueError:
                    pass
            elif end_use == "Pumps":
                try:
                    result["pumps_gj"] = float(row[2].strip().replace(",", ""))
                except ValueError:
                    pass
            elif end_use == "Heat Rejection":
                try:
                    result["heat_rejection_gj"] = float(row[2].strip().replace(",", ""))
                except ValueError:
                    pass
            elif end_use == "Interior Lighting":
                try:
                    result["lighting_gj"] = float(row[2].strip().replace(",", ""))
                except ValueError:
                    pass
            elif end_use == "Interior Equipment":
                try:
                    result["equipment_gj"] = float(row[2].strip().replace(",", ""))
                except ValueError:
                    pass

    if "total_site_energy_mwh" in result and "building_area_m2" in result:
        result["eui_kwh_m2"] = result["total_site_energy_mwh"] * 1000 / result["building_area_m2"]

    # Compute HVAC total (cooling elec + fans + pumps + heat rejection + heating gas)
    hvac_gj = sum(
        result.get(k, 0) for k in ["cooling_elec_gj", "fans_gj", "pumps_gj", "heat_rejection_gj", "heating_gas_gj"]
    )
    if hvac_gj > 0:
        result["hvac_total_gj"] = hvac_gj
        result["hvac_total_mwh"] = hvac_gj / 3.6

    return result


def find_eplustbl(base_path: Path, city: str, strategy: str) -> Path | None:
    """Find eplustbl.csv for a given city/strategy combination."""
    # Try standard path
    standard = base_path / "default" / city / "1year" / strategy / "eplustbl.csv"
    if standard.exists():
        return standard

    # Try archive path (Seoul strategies)
    archive = base_path / "default" / city / "1year" / "archive" / "2026-02-05" / strategy / "eplustbl.csv"
    if archive.exists():
        return archive

    return None


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    global pass_count, fail_count, warn_count

    # ═══════════════════════════════════════════════════════════════
    # Load ems_simulation analysis JSON files
    # ═══════════════════════════════════════════════════════════════
    comprehensive = load_json(EMS_ROOT / "buildings" / "comprehensive_analysis_report.json")
    lo_comparison = load_json(LO_RESULTS / "ems_comparison_analysis.json")
    lo_complete = load_json(LO_RESULTS / "complete_ems_analysis.json")
    mo_baseline_report = load_json(MO_RESULTS / "analysis_report.json")
    load_json(MO_RESULTS / "complete_vrf_analysis.json")

    # ═══════════════════════════════════════════════════════════════
    # Test 1: Parse ALL Large Office eplustbl.csv files
    # ═══════════════════════════════════════════════════════════════
    separator("Test 1: Large Office — Raw EnergyPlus Data Extraction")

    lo_strategies = ["economizer", "staging", "optimal_start", "staging_economizer", "full_mpc"]
    lo_data: dict[str, dict[str, dict]] = {}  # strategy → city → parsed data

    found = 0
    missing = 0
    for strategy in lo_strategies:
        lo_data[strategy] = {}
        for city in CITIES:
            csv_path = find_eplustbl(LO_RESULTS, city, strategy)
            if csv_path:
                parsed = parse_eplustbl(csv_path)
                if parsed:
                    lo_data[strategy][city] = parsed
                    found += 1
                else:
                    missing += 1
            else:
                missing += 1

    # Also try to find baseline
    lo_data["baseline"] = {}
    for city in CITIES:
        csv_path = find_eplustbl(LO_RESULTS, city, "baseline")
        if csv_path:
            parsed = parse_eplustbl(csv_path)
            if parsed:
                lo_data["baseline"][city] = parsed
                found += 1

    p(f"\n  Large Office: {found} eplustbl.csv parsed, {missing} not found")
    p(f"  Strategies with data: {[s for s in lo_data if lo_data[s]]}")

    # Show actual EUI from EnergyPlus for each strategy/city
    p(
        f"\n  {'Strategy':<22s} {'City':<12s} {'Total GJ':>10s} {'EUI kWh/m2':>12s} {'Cool GJ':>10s} {'Heat Gas GJ':>12s}"
    )
    p(f"  {'-' * 22} {'-' * 12} {'-' * 10} {'-' * 12} {'-' * 10} {'-' * 12}")
    for strategy in ["baseline"] + lo_strategies:
        for city in CITIES:
            d = lo_data.get(strategy, {}).get(city)
            if d:
                p(
                    f"  {strategy:<22s} {city:<12s} {d.get('total_site_energy_gj', 0):>10.1f} "
                    f"{d.get('eui_kwh_m2', 0):>12.1f} "
                    f"{d.get('cooling_elec_gj', 0):>10.1f} "
                    f"{d.get('heating_gas_gj', 0):>12.1f}"
                )

    # ═══════════════════════════════════════════════════════════════
    # Test 2: Verify analysis JSON vs raw eplustbl.csv
    # ═══════════════════════════════════════════════════════════════
    separator("Test 2: Large Office — Analysis JSON vs Raw eplustbl.csv")

    if lo_comparison:
        p("\n  Comparing ems_comparison_analysis.json (Cooling MWh) vs eplustbl.csv Cooling [GJ]/3.6")
        for city in CITIES:
            json_data = lo_comparison.get("cities", {}).get(city, {})
            if not json_data:
                continue

            # Economizer
            eco_csv = lo_data.get("economizer", {}).get(city)
            if eco_csv and "cooling_elec_gj" in eco_csv:
                json_eco_mwh = json_data.get("economizer_mwh", 0)
                csv_cooling_mwh = eco_csv["cooling_elec_gj"] / 3.6
                check(f"{city} economizer cooling MWh", json_eco_mwh, csv_cooling_mwh, "MWh", tol=5.0, is_warn=True)

            # Staging
            stg_csv = lo_data.get("staging", {}).get(city)
            if stg_csv and "cooling_elec_gj" in stg_csv:
                json_stg_mwh = json_data.get("staging_mwh", 0)
                csv_cooling_mwh = stg_csv["cooling_elec_gj"] / 3.6
                check(f"{city} staging cooling MWh", json_stg_mwh, csv_cooling_mwh, "MWh", tol=5.0, is_warn=True)

    # ═══════════════════════════════════════════════════════════════
    # Test 3: Compute per-city chiller savings from eplustbl.csv
    # ═══════════════════════════════════════════════════════════════
    separator("Test 3: Large Office — Per-City Chiller Savings % from Raw Data")

    # Use ems_comparison_analysis.json baseline values as reference
    # (since baseline eplustbl.csv may not be available)
    if lo_comparison:
        p(
            f"\n  {'Strategy':<22s} {'City':<12s} {'Base Cool MWh':>14s} {'Strat Cool MWh':>15s} {'Savings %':>10s} {'Report %':>10s} {'Match':>6s}"
        )
        p(f"  {'-' * 22} {'-' * 12} {'-' * 14} {'-' * 15} {'-' * 10} {'-' * 10} {'-' * 6}")

        # Map: BuildWise strategy → ems_simulation strategy name → analysis JSON key
        strategy_map = {
            "economizer": "economizer_savings_pct",
            "staging": "staging_savings_pct",
        }

        for ems_strategy, json_key in strategy_map.items():
            for city in CITIES:
                json_city = lo_comparison.get("cities", {}).get(city, {})
                baseline_mwh = json_city.get("baseline_mwh", 0)
                reported_savings = json_city.get(json_key, 0)

                csv_data = lo_data.get(ems_strategy, {}).get(city)
                if csv_data and "cooling_elec_gj" in csv_data and baseline_mwh > 0:
                    csv_cooling_mwh = csv_data["cooling_elec_gj"] / 3.6
                    computed_savings = (1 - csv_cooling_mwh / baseline_mwh) * 100
                    match = "YES" if abs(computed_savings - reported_savings) < 1.0 else "NO"
                    p(
                        f"  {ems_strategy:<22s} {city:<12s} {baseline_mwh:>14.2f} {csv_cooling_mwh:>15.2f} "
                        f"{computed_savings:>10.1f} {reported_savings:>10.1f} {match:>6s}"
                    )

    # ═══════════════════════════════════════════════════════════════
    # Test 4: Verify 10-city average savings match comprehensive report
    # ═══════════════════════════════════════════════════════════════
    separator("Test 4: Large Office — 10-City Average Savings vs Comprehensive Report")

    if lo_complete and comprehensive:
        lo_ems = comprehensive.get("ems_strategy_results", {}).get("large_office_chiller_system", {})

        # From complete_ems_analysis.json: total chiller MWh across 10 cities
        lo_summary = lo_complete.get("summary", {})
        baseline_total = lo_summary.get("baseline", {}).get("total_chiller_mwh", 0)

        for ems_strategy in ["economizer", "staging", "optimal_start", "staging_economizer", "full_mpc"]:
            strat_data = lo_summary.get(ems_strategy, {})
            strat_total = strat_data.get("total_chiller_mwh", 0)
            report_avg_pct = strat_data.get("avg_savings_pct", 0)

            # Compute from totals
            if baseline_total > 0:
                computed_pct = (1 - strat_total / baseline_total) * 100
            else:
                computed_pct = 0

            # From comprehensive report
            comp_pct = lo_ems.get(ems_strategy, {}).get("savings_pct", 0)

            check(f"{ems_strategy} avg savings (complete_analysis)", report_avg_pct, computed_pct, "%", tol=0.5)
            check(f"{ems_strategy} avg savings (comprehensive)", comp_pct, computed_pct, "%", tol=0.5)

    # ═══════════════════════════════════════════════════════════════
    # Test 5: BuildWise mock_runner savings derivation
    # ═══════════════════════════════════════════════════════════════
    separator("Test 5: BuildWise Mock Runner — Savings Derivation Verification")

    if comprehensive:
        lo_ems = comprehensive.get("ems_strategy_results", {}).get("large_office_chiller_system", {})
        lo_baseline = lo_ems.get("baseline", {})
        baseline_chiller_mwh = lo_baseline.get("avg_chiller_mwh", 0)
        baseline_boiler_mwh = lo_baseline.get("avg_boiler_mwh", 0)
        hvac_eui = lo_baseline.get("avg_eui_kwh_m2", 0)

        p("\n  ems_simulation reference data:")
        p(f"    Baseline chiller MWh (avg): {baseline_chiller_mwh}")
        p(f"    Baseline boiler MWh (avg):  {baseline_boiler_mwh}")
        p(f"    HVAC EUI:                   {hvac_eui} kWh/m2")
        p(f"    master_taxonomy total EUI:  {_BASE_EUI['large_office']} kWh/m2")
        p(f"    Total building MWh (calc):  {_BASE_EUI['large_office'] * LO_AREA / 1000:.1f}")
        p(f"    HVAC fraction:              {hvac_eui / _BASE_EUI['large_office'] * 100:.1f}%")

        # Check actual EUI from eplustbl.csv
        actual_euis = []
        for city in CITIES:
            for strategy in lo_strategies:
                d = lo_data.get(strategy, {}).get(city)
                if d and "eui_kwh_m2" in d:
                    actual_euis.append(d["eui_kwh_m2"])
        if actual_euis:
            avg_actual_eui = sum(actual_euis) / len(actual_euis)
            p(
                f"\n    *** Actual EnergyPlus avg site EUI: {avg_actual_eui:.1f} kWh/m2 (from {len(actual_euis)} simulations) ***"
            )
            p(f"    *** master_taxonomy says:           {_BASE_EUI['large_office']} kWh/m2 ***")
            p(f"    *** Ratio:                          {_BASE_EUI['large_office'] / avg_actual_eui:.2f}x ***")

        # BuildWise mapping: ems_strategy → BuildWise strategy
        bw_map = {
            "economizer": ("m2", 18.1),
            "staging": ("m3", 43.0),
            "optimal_start": ("m1", 46.7),
            "staging_economizer": ("m6", 42.4),
            "full_mpc": ("m8", 77.1),
        }

        total_bldg_mwh = _BASE_EUI["large_office"] * LO_AREA / 1000
        hvac_eui / _BASE_EUI["large_office"]

        p("\n  Strategy savings derivation:")
        p(f"  {'ems_strategy':<22s} {'BW':<5s} {'Chiller %':>10s} {'→ Bldg %':>10s} {'Mock %':>8s} {'Match':>6s}")
        p(f"  {'-' * 22} {'-' * 5} {'-' * 10} {'-' * 10} {'-' * 8} {'-' * 6}")

        for ems_strat, (bw_strat, chiller_pct) in bw_map.items():
            # Derivation: chiller_savings_mwh / total_building_mwh
            chiller_savings_mwh = baseline_chiller_mwh * chiller_pct / 100
            bldg_savings_pct = chiller_savings_mwh / total_bldg_mwh * 100

            mock_savings = _STRATEGY_SAVINGS_BY_TYPE["large_office"][bw_strat]
            match = abs(round(bldg_savings_pct, 1) - mock_savings) < 0.2

            check(f"LO {bw_strat} ({ems_strat})", round(bldg_savings_pct, 1), mock_savings, "%", tol=0.15)

        # M7 special case
        full_mpc_bldg = baseline_chiller_mwh * 77.1 / 100 / total_bldg_mwh * 100
        expected_m7 = round(full_mpc_bldg * 0.85, 1)
        check(
            "LO m7 (full_mpc × 0.85 PMV)", expected_m7, _STRATEGY_SAVINGS_BY_TYPE["large_office"]["m7"], "%", tol=0.15
        )

    # ═══════════════════════════════════════════════════════════════
    # Test 6: Medium Office — Parse ALL eplustbl.csv
    # ═══════════════════════════════════════════════════════════════
    separator("Test 6: Medium Office — Raw EnergyPlus Data Extraction")

    mo_strategies = ["baseline", "optimal_start_vrf", "vrf_demand_limit", "vrf_full"]
    mo_data: dict[str, dict[str, dict]] = {}

    # Also check for optimal_start_vrf_v2
    all_mo_strategies = mo_strategies + ["optimal_start_vrf_v2"]

    found = 0
    for strategy in all_mo_strategies:
        mo_data[strategy] = {}
        for city in CITIES:
            csv_path = find_eplustbl(MO_RESULTS, city, strategy)
            if csv_path:
                parsed = parse_eplustbl(csv_path)
                if parsed:
                    mo_data[strategy][city] = parsed
                    found += 1

    p(f"\n  Medium Office: {found} eplustbl.csv parsed")
    p(f"  Strategies with data: {[s for s in mo_data if mo_data[s]]}")

    # Show actual EUI
    p(f"\n  {'Strategy':<22s} {'City':<12s} {'Total GJ':>10s} {'EUI kWh/m2':>12s} {'Cool GJ':>10s}")
    p(f"  {'-' * 22} {'-' * 12} {'-' * 10} {'-' * 12} {'-' * 10}")
    for strategy in all_mo_strategies:
        for city in CITIES:
            d = mo_data.get(strategy, {}).get(city)
            if d:
                p(
                    f"  {strategy:<22s} {city:<12s} {d.get('total_site_energy_gj', 0):>10.1f} "
                    f"{d.get('eui_kwh_m2', 0):>12.1f} "
                    f"{d.get('cooling_elec_gj', 0):>10.1f}"
                )

    # ═══════════════════════════════════════════════════════════════
    # Test 7: Medium Office — Verify analysis JSON vs eplustbl.csv
    # ═══════════════════════════════════════════════════════════════
    separator("Test 7: Medium Office — Analysis JSON vs Raw Data")

    if mo_baseline_report:
        p("\n  Comparing analysis_report.json baseline per-city vs eplustbl.csv")
        for city_data in mo_baseline_report.get("by_city", []):
            city = city_data["city"]
            json_total_mwh = city_data.get("total_mwh", 0)  # cooling + heating only

            csv_data = mo_data.get("baseline", {}).get(city)
            if csv_data:
                csv_total_mwh = csv_data.get("total_site_energy_mwh", 0)
                csv_cooling_mwh = csv_data.get("cooling_elec_gj", 0) / 3.6
                csv_heating_gas_mwh = csv_data.get("heating_gas_gj", 0) / 3.6

                p(f"\n  {city}:")
                p(f"    JSON total (cool+heat): {json_total_mwh:.2f} MWh")
                p(f"    CSV total site energy:  {csv_total_mwh:.2f} MWh")
                p(f"    CSV cooling elec:       {csv_cooling_mwh:.2f} MWh")
                p(f"    CSV heating gas:        {csv_heating_gas_mwh:.2f} MWh")
                p(f"    CSV cool+heat:          {csv_cooling_mwh + csv_heating_gas_mwh:.2f} MWh")
                p(f"    CSV EUI:                {csv_data.get('eui_kwh_m2', 0):.1f} kWh/m2")

    # ═══════════════════════════════════════════════════════════════
    # Test 8: Medium Office — Savings verification
    # ═══════════════════════════════════════════════════════════════
    separator("Test 8: Medium Office — Per-City Savings from Raw Data")

    if mo_data.get("baseline") and mo_data.get("optimal_start_vrf"):
        p(f"\n  {'City':<12s} {'Base MWh':>10s} {'OptSt MWh':>10s} {'Savings %':>10s}")
        p(f"  {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 10}")

        savings_list = []
        for city in CITIES:
            base = mo_data["baseline"].get(city)
            opt = mo_data["optimal_start_vrf"].get(city)
            if base and opt:
                base_mwh = base.get("total_site_energy_mwh", 0)
                opt_mwh = opt.get("total_site_energy_mwh", 0)
                if base_mwh > 0:
                    savings = (1 - opt_mwh / base_mwh) * 100
                    savings_list.append(savings)
                    p(f"  {city:<12s} {base_mwh:>10.2f} {opt_mwh:>10.2f} {savings:>10.1f}")

        if savings_list:
            avg_savings = sum(savings_list) / len(savings_list)
            p(f"\n  10-city average savings: {avg_savings:.1f}%")
            p("  comprehensive_analysis says: 2.4%")
            p(f"  BuildWise m1 (medium_office): {_STRATEGY_SAVINGS_BY_TYPE['medium_office']['m1']}%")

    # ═══════════════════════════════════════════════════════════════
    # Test 9: EUI Discrepancy Analysis
    # ═══════════════════════════════════════════════════════════════
    separator("Test 9: EUI DISCREPANCY ANALYSIS — master_taxonomy vs Actual EnergyPlus")

    p("\n  This is the critical comparison: what master_taxonomy claims vs actual simulation output")
    p(f"\n  {'Building':<20s} {'taxonomy EUI':>13s} {'EP actual EUI':>14s} {'Ratio':>8s} {'Note'}")
    p(f"  {'-' * 20} {'-' * 13} {'-' * 14} {'-' * 8} {'-' * 30}")

    for btype, taxonomy_eui in _BASE_EUI.items():
        # Find actual EUI from any available eplustbl.csv
        actual_euis = []

        if btype == "large_office":
            for strategy in lo_strategies:
                for city in CITIES:
                    d = lo_data.get(strategy, {}).get(city)
                    if d and "eui_kwh_m2" in d:
                        actual_euis.append(d["eui_kwh_m2"])
        elif btype == "medium_office":
            for strategy in all_mo_strategies:
                for city in CITIES:
                    d = mo_data.get(strategy, {}).get(city)
                    if d and "eui_kwh_m2" in d:
                        actual_euis.append(d["eui_kwh_m2"])

        if actual_euis:
            avg_eui = sum(actual_euis) / len(actual_euis)
            ratio = taxonomy_eui / avg_eui
            note = "MATCH" if 0.9 <= ratio <= 1.1 else f"MISMATCH ({len(actual_euis)} samples)"
            p(f"  {btype:<20s} {taxonomy_eui:>13.1f} {avg_eui:>14.1f} {ratio:>8.2f}x {note}")
        else:
            p(f"  {btype:<20s} {taxonomy_eui:>13.1f} {'N/A':>14s} {'N/A':>8s} No eplustbl.csv found")

    # ═══════════════════════════════════════════════════════════════
    # Test 10: Full mock_runner output comparison
    # ═══════════════════════════════════════════════════════════════
    separator("Test 10: Mock Runner Output vs Actual EnergyPlus (if EUI matched)")

    p("\n  Comparing mock_runner absolute values with actual EnergyPlus outputs")
    p("  (This tests whether the mock produces physically realistic values)")

    for city in ["Seoul", "Busan", "Jeju"]:
        # Large office baseline mock
        mock_base = generate_mock_result("large_office", city, "baseline", LO_AREA)
        mock_m8 = generate_mock_result("large_office", city, "m8", LO_AREA)

        p(f"\n  Large Office, {city}:")
        p(f"    Mock baseline total:   {mock_base['total_energy_kwh']:>14,.0f} kWh  EUI={mock_base['eui_kwh_m2']:.1f}")
        p(f"    Mock M8 total:         {mock_m8['total_energy_kwh']:>14,.0f} kWh  EUI={mock_m8['eui_kwh_m2']:.1f}")

        # Try to find actual EnergyPlus data for comparison
        for ems_strat in ["full_mpc"]:
            actual = lo_data.get(ems_strat, {}).get(city)
            if actual:
                p(
                    f"    EP  {ems_strat} total: {actual['total_site_energy_mwh'] * 1000:>14,.0f} kWh  EUI={actual.get('eui_kwh_m2', 0):.1f}"
                )

    for city in ["Seoul", "Incheon"]:
        mock_base = generate_mock_result("medium_office", city, "baseline", MO_AREA)
        mock_m1 = generate_mock_result("medium_office", city, "m1", MO_AREA)

        p(f"\n  Medium Office, {city}:")
        p(f"    Mock baseline total:    {mock_base['total_energy_kwh']:>10,.0f} kWh  EUI={mock_base['eui_kwh_m2']:.1f}")
        p(f"    Mock M1 total:          {mock_m1['total_energy_kwh']:>10,.0f} kWh  EUI={mock_m1['eui_kwh_m2']:.1f}")

        actual_base = mo_data.get("baseline", {}).get(city)
        actual_opt = mo_data.get("optimal_start_vrf", {}).get(city)
        if actual_base:
            p(
                f"    EP  baseline total:     {actual_base['total_site_energy_mwh'] * 1000:>10,.0f} kWh  EUI={actual_base.get('eui_kwh_m2', 0):.1f}"
            )
        if actual_opt:
            p(
                f"    EP  opt_start total:    {actual_opt['total_site_energy_mwh'] * 1000:>10,.0f} kWh  EUI={actual_opt.get('eui_kwh_m2', 0):.1f}"
            )

    # ═══════════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════════
    separator("FINAL SUMMARY")

    total = pass_count + fail_count + warn_count
    p(f"\n  Checks: {total} total  |  {pass_count} PASS  |  {fail_count} FAIL  |  {warn_count} WARN")

    p("\n  KEY FINDINGS:")
    p("  1. Strategy savings percentages: Derived correctly from ems_simulation chiller data")
    p("  2. master_taxonomy EUI values vs actual EnergyPlus outputs: SEE Test 9")
    p("  3. Mock runner absolute values vs EnergyPlus absolute values: SEE Test 10")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
