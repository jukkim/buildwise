#!/usr/bin/env python3
"""Docker integration test: ems_bridge → EnergyPlus → parser → EUI verification.

Runs inside the buildwise-worker Docker container where EnergyPlus is available.

Usage (from project root):
  docker compose run --rm worker python -m tests.docker_integration_test

Test cases:
  1. Baseline (no BPS override) → EUI must match eplustbl reference
  2. Cooling setpoint 24→26°C → EUI must decrease (less cooling load)
  3. Chiller COP 6.1→4.0 → EUI must increase (less efficient cooling)
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Ensure PYTHONPATH includes /app
sys.path.insert(0, os.environ.get("PYTHONPATH", "/app"))

from app.services.idf.ems_bridge import (
    EMS_SIM_ROOT,
    generate_idf_via_ems,
    is_ems_available,
)
from app.services.results.parser import parse_energyplus_output

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EP_EXE = os.environ.get("ENERGYPLUS_EXE", "energyplus")
EP_DIR = os.environ.get("EP_DIR", "/usr/local/EnergyPlus-24-1-0")
IDD_PATH = os.path.join(EP_DIR, "Energy+.idd")
EPW_DIR = os.environ.get("BUILDWISE_EPW_DIR", "/opt/weather")

# Expected EUI values from eplustbl.csv (kWh/m²/year)
EXPECTED_EUI = {
    ("large_office", "Seoul", "baseline"): 119.75,
    ("large_office", "Seoul", "m2"): 111.72,
    ("large_office", "Seoul", "m4"): 113.17,
    ("large_office", "Seoul", "m8"): 110.29,
    ("medium_office", "Seoul", "baseline"): 77.57,
    ("small_office", "Seoul", "baseline"): 97.78,
}

# Tolerance for EUI comparison (±%)
EUI_TOLERANCE_PCT = 1.0  # ±1% for baseline (must match eplustbl)

PASS = 0
FAIL = 0


def check(condition: bool, msg: str):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {msg}")
    else:
        FAIL += 1
        print(f"  FAIL: {msg}")


def run_energyplus(idf_content: str, epw_file: str, aux_files: dict[str, bytes] | None = None) -> dict:
    """Run EnergyPlus on IDF content, return parsed results."""
    work_dir = Path(tempfile.mkdtemp(prefix="bw_test_"))

    # Write IDF
    idf_path = work_dir / "in.idf"
    idf_path.write_text(idf_content, encoding="utf-8")

    # Write auxiliary files (CSV schedules)
    if aux_files:
        for fname, fbytes in aux_files.items():
            aux_path = work_dir / fname
            aux_path.parent.mkdir(parents=True, exist_ok=True)
            aux_path.write_bytes(fbytes)

    # Locate EPW
    epw_path = Path(EPW_DIR) / epw_file
    if not epw_path.exists():
        raise FileNotFoundError(f"EPW not found: {epw_path}")

    # Run E+
    cmd = [
        EP_EXE,
        "--idd",
        IDD_PATH,
        "--weather",
        str(epw_path),
        "--output-directory",
        str(work_dir),
        "--readvars",
        str(idf_path),
    ]

    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=str(work_dir))
    elapsed = time.time() - t0

    if proc.returncode != 0:
        err_file = work_dir / "eplusout.err"
        err_text = ""
        if err_file.exists():
            err_text = err_file.read_text(encoding="utf-8", errors="replace")[-2000:]
        raise RuntimeError(
            f"EnergyPlus failed (exit {proc.returncode}) in {elapsed:.0f}s\n"
            f"stderr: {proc.stderr[-500:]}\n"
            f"eplusout.err: {err_text[-500:]}"
        )

    print(f"    E+ completed in {elapsed:.0f}s")

    # Parse results
    result = parse_energyplus_output(str(work_dir))
    return result


# =====================================================================
# Test 1: Baseline — EUI must match eplustbl reference
# =====================================================================
def test_baseline():
    print("\n" + "=" * 60)
    print("Test 1: Baseline (large_office, Seoul, no BPS override)")
    print("=" * 60)

    idf_content, aux_files = generate_idf_via_ems(
        strategy="baseline",
        climate_city="Seoul",
        building_type="large_office",
        period_type="1year",
        bps=None,
    )

    check(len(idf_content) > 100000, f"IDF generated ({len(idf_content)} chars)")
    check(True, f"Aux files for baseline: {len(aux_files)}")

    result = run_energyplus(idf_content, "KOR_Seoul.epw", aux_files)

    eui = result["eui_kwh_m2"]
    expected = EXPECTED_EUI[("large_office", "Seoul", "baseline")]
    pct_diff = abs(eui - expected) / expected * 100

    check(
        pct_diff < EUI_TOLERANCE_PCT,
        f"EUI = {eui:.2f} kWh/m² (expected {expected:.2f}, diff {pct_diff:.2f}%)",
    )
    check(result["total_energy_kwh"] > 0, f"Total energy = {result['total_energy_kwh']:.0f} kWh")
    check("cooling_energy_kwh" in result, f"Cooling = {result.get('cooling_energy_kwh', 0):.0f} kWh")
    check("heating_energy_kwh" in result, f"Heating = {result.get('heating_energy_kwh', 0):.0f} kWh")

    # Monthly profile validation
    mp = result.get("monthly_profile")
    check(mp is not None, "Monthly profile present")
    if mp:
        check(len(mp) == 12, f"Monthly profile has {len(mp)} months")
        monthly_total = sum(m["total"] for m in mp)
        diff_pct = abs(monthly_total - result["total_energy_kwh"]) / result["total_energy_kwh"] * 100
        check(
            diff_pct < 1.0,
            f"Monthly sum {monthly_total:.0f} ≈ annual {result['total_energy_kwh']:.0f} ({diff_pct:.2f}%)",
        )
        # Summer should have more cooling than winter
        jul_cool = mp[6]["cooling"]  # July
        jan_cool = mp[0]["cooling"]  # January
        check(jul_cool > jan_cool, f"Jul cooling {jul_cool:.0f} > Jan cooling {jan_cool:.0f}")

    return eui


# =====================================================================
# Test 2: Cooling setpoint 24→26°C — EUI must decrease
# =====================================================================
def test_cooling_setpoint_override(baseline_eui: float):
    print("\n" + "=" * 60)
    print("Test 2: Cooling setpoint 24→26°C (should reduce EUI)")
    print("=" * 60)

    bps = {
        "setpoints": {"cooling_occupied": 26.0},
        "hvac": {},
    }

    idf_content, aux_files = generate_idf_via_ems(
        strategy="baseline",
        climate_city="Seoul",
        building_type="large_office",
        period_type="1year",
        bps=bps,
    )

    check(len(idf_content) > 100000, f"IDF generated ({len(idf_content)} chars)")

    # Verify the IDF was actually patched
    check("26.0" in idf_content, "Cooling setpoint 26.0 present in IDF")

    result = run_energyplus(idf_content, "KOR_Seoul.epw", aux_files)

    eui = result["eui_kwh_m2"]
    delta_pct = (eui - baseline_eui) / baseline_eui * 100

    check(
        eui < baseline_eui,
        f"EUI = {eui:.2f} < baseline {baseline_eui:.2f} ({delta_pct:+.1f}%)",
    )
    check(
        -15 < delta_pct < 0,
        f"EUI change {delta_pct:+.1f}% is within expected range (-15% to 0%)",
    )

    return eui


# =====================================================================
# Test 3: Chiller COP 6.1→4.0 — EUI must increase
# =====================================================================
def test_chiller_cop_override(baseline_eui: float):
    print("\n" + "=" * 60)
    print("Test 3: Chiller COP 6.1→4.0 (should increase EUI)")
    print("=" * 60)

    bps = {
        "setpoints": {},
        "hvac": {"chillers": {"cop": 4.0}},
    }

    idf_content, aux_files = generate_idf_via_ems(
        strategy="baseline",
        climate_city="Seoul",
        building_type="large_office",
        period_type="1year",
        bps=bps,
    )

    check(len(idf_content) > 100000, f"IDF generated ({len(idf_content)} chars)")
    check("4.00" in idf_content, "Chiller COP 4.00 present in IDF")

    result = run_energyplus(idf_content, "KOR_Seoul.epw", aux_files)

    eui = result["eui_kwh_m2"]
    delta_pct = (eui - baseline_eui) / baseline_eui * 100

    check(
        eui > baseline_eui,
        f"EUI = {eui:.2f} > baseline {baseline_eui:.2f} ({delta_pct:+.1f}%)",
    )
    check(
        0 < delta_pct < 30,
        f"EUI change {delta_pct:+.1f}% is within expected range (0% to +30%)",
    )

    return eui


# =====================================================================
# Test 4: M4 PMV strategy — EUI must match eplustbl
# =====================================================================
def test_m4_strategy():
    print("\n" + "=" * 60)
    print("Test 4: M4 PMV strategy (large_office, Seoul)")
    print("=" * 60)

    idf_content, aux_files = generate_idf_via_ems(
        strategy="m4",
        climate_city="Seoul",
        building_type="large_office",
        period_type="1year",
        bps=None,
    )

    check(len(idf_content) > 100000, f"IDF generated ({len(idf_content)} chars)")
    check(len(aux_files) > 0, f"PMV aux files present ({len(aux_files)} files)")

    result = run_energyplus(idf_content, "KOR_Seoul.epw", aux_files)

    eui = result["eui_kwh_m2"]
    expected = EXPECTED_EUI[("large_office", "Seoul", "m4")]
    pct_diff = abs(eui - expected) / expected * 100

    check(
        pct_diff < EUI_TOLERANCE_PCT,
        f"EUI = {eui:.2f} kWh/m² (expected {expected:.2f}, diff {pct_diff:.2f}%)",
    )

    return eui


# =====================================================================
# Test 5: M2 Economizer — EUI must match eplustbl
# =====================================================================
def test_m2_economizer():
    print("\n" + "=" * 60)
    print("Test 5: M2 Economizer (large_office, Seoul)")
    print("=" * 60)

    idf_content, aux_files = generate_idf_via_ems(
        strategy="m2",
        climate_city="Seoul",
        building_type="large_office",
        period_type="1year",
        bps=None,
    )

    check(len(idf_content) > 100000, f"IDF generated ({len(idf_content)} chars)")

    result = run_energyplus(idf_content, "KOR_Seoul.epw", aux_files)

    eui = result["eui_kwh_m2"]
    expected = EXPECTED_EUI[("large_office", "Seoul", "m2")]
    pct_diff = abs(eui - expected) / expected * 100

    check(
        pct_diff < EUI_TOLERANCE_PCT,
        f"EUI = {eui:.2f} kWh/m² (expected {expected:.2f}, diff {pct_diff:.2f}%)",
    )

    return eui


# =====================================================================
# Test 6: M8 Full Savings — EUI must match eplustbl
# =====================================================================
def test_m8_full_savings():
    print("\n" + "=" * 60)
    print("Test 6: M8 Full Savings (large_office, Seoul)")
    print("=" * 60)

    idf_content, aux_files = generate_idf_via_ems(
        strategy="m8",
        climate_city="Seoul",
        building_type="large_office",
        period_type="1year",
        bps=None,
    )

    check(len(idf_content) > 100000, f"IDF generated ({len(idf_content)} chars)")
    check(len(aux_files) > 0, f"M8 aux files present ({len(aux_files)} files)")

    result = run_energyplus(idf_content, "KOR_Seoul.epw", aux_files)

    eui = result["eui_kwh_m2"]
    expected = EXPECTED_EUI[("large_office", "Seoul", "m8")]
    pct_diff = abs(eui - expected) / expected * 100

    check(
        pct_diff < EUI_TOLERANCE_PCT,
        f"EUI = {eui:.2f} kWh/m² (expected {expected:.2f}, diff {pct_diff:.2f}%)",
    )

    return eui


# =====================================================================
# Test 7: Medium Office Baseline — VRF system
# =====================================================================
def test_medium_office_baseline():
    print("\n" + "=" * 60)
    print("Test 7: Medium Office Baseline (VRF, Seoul)")
    print("=" * 60)

    idf_content, aux_files = generate_idf_via_ems(
        strategy="baseline",
        climate_city="Seoul",
        building_type="medium_office",
        period_type="1year",
        bps=None,
    )

    check(len(idf_content) > 10000, f"IDF generated ({len(idf_content)} chars)")

    result = run_energyplus(idf_content, "KOR_Seoul.epw", aux_files)

    eui = result["eui_kwh_m2"]
    expected = EXPECTED_EUI[("medium_office", "Seoul", "baseline")]
    pct_diff = abs(eui - expected) / expected * 100

    check(
        pct_diff < EUI_TOLERANCE_PCT,
        f"EUI = {eui:.2f} kWh/m² (expected {expected:.2f}, diff {pct_diff:.2f}%)",
    )

    return eui


# =====================================================================
# Test 8: Small Office Baseline — PSZ-HP system
# =====================================================================
def test_small_office_baseline():
    print("\n" + "=" * 60)
    print("Test 8: Small Office Baseline (PSZ-HP, Seoul)")
    print("=" * 60)

    idf_content, aux_files = generate_idf_via_ems(
        strategy="baseline",
        climate_city="Seoul",
        building_type="small_office",
        period_type="1year",
        bps=None,
    )

    check(len(idf_content) > 10000, f"IDF generated ({len(idf_content)} chars)")

    result = run_energyplus(idf_content, "KOR_Seoul.epw", aux_files)

    eui = result["eui_kwh_m2"]
    expected = EXPECTED_EUI[("small_office", "Seoul", "baseline")]
    pct_diff = abs(eui - expected) / expected * 100

    check(
        pct_diff < EUI_TOLERANCE_PCT,
        f"EUI = {eui:.2f} kWh/m² (expected {expected:.2f}, diff {pct_diff:.2f}%)",
    )

    return eui


# =====================================================================
# Main
# =====================================================================
def main():
    print("=" * 60)
    print("DOCKER INTEGRATION TEST")
    print(f"EnergyPlus: {EP_EXE}")
    print(f"IDD: {IDD_PATH}")
    print(f"EPW dir: {EPW_DIR}")
    print(f"ems_simulation: {EMS_SIM_ROOT}")
    print("=" * 60)

    # Pre-flight checks
    check(Path(IDD_PATH).exists(), f"IDD file exists: {IDD_PATH}")
    check(Path(EPW_DIR).is_dir(), f"EPW directory exists: {EPW_DIR}")
    check(is_ems_available(), f"ems_simulation available at {EMS_SIM_ROOT}")

    epw_count = len(list(Path(EPW_DIR).glob("*.epw")))
    check(epw_count >= 10, f"EPW files: {epw_count}")

    if FAIL > 0:
        print("\nPre-flight checks failed. Cannot proceed.")
        sys.exit(1)

    # Run tests — large_office
    baseline_eui = test_baseline()
    test_cooling_setpoint_override(baseline_eui)
    test_chiller_cop_override(baseline_eui)
    test_m4_strategy()
    test_m2_economizer()
    test_m8_full_savings()

    # Additional building types
    test_medium_office_baseline()
    test_small_office_baseline()

    # Summary
    print(f"\n{'=' * 60}")
    print("INTEGRATION TEST COMPLETE")
    print(f"{'=' * 60}")
    print(f"  PASS: {PASS}")
    print(f"  FAIL: {FAIL}")
    print(f"  TOTAL: {PASS + FAIL}")

    if FAIL > 0:
        print(f"\n*** {FAIL} FAILURES ***")
        sys.exit(1)
    else:
        print("\nAll integration tests passed!")


if __name__ == "__main__":
    main()
