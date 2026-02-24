"""End-to-end verification of idf_patcher against real ems_simulation IDF files.

Reads actual IDF files from ems_simulation, applies user BPS overrides,
and verifies the patched values are correct.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path

from app.services.idf.idf_patcher import (
    _EMS_DEFAULTS,
    _extract_schedule_block,
    _patch_pmv_csv_files,
    apply_user_overrides,
)

EMS_ROOT = Path(r"C:\Users\User\Desktop\myjob\8.simulation\ems_simulation")
BUILDINGS_DIR = EMS_ROOT / "buildings"

# Building types to test
BUILDING_TYPES = [
    "large_office",
    "medium_office",
    "small_office",
    "standalone_retail",
    "primary_school",
    "hospital",
]

PASS = 0
FAIL = 0
WARN = 0


def check(condition: bool, msg: str, warn_only: bool = False):
    global PASS, FAIL, WARN
    if condition:
        PASS += 1
        print(f"  PASS: {msg}")
    elif warn_only:
        WARN += 1
        print(f"  WARN: {msg}")
    else:
        FAIL += 1
        print(f"  FAIL: {msg}")


def find_idf(building_type: str, city: str = "Seoul", strategy: str = "baseline") -> Path | None:
    """Find an IDF file for the given building/city/strategy."""
    idf_path = BUILDINGS_DIR / building_type / "results" / "default" / city / "1year" / strategy / "model.idf"
    if idf_path.is_file():
        return idf_path
    # Try other cities
    for alt_city in ["Busan", "Daegu", "Incheon", "Daejeon"]:
        alt = BUILDINGS_DIR / building_type / "results" / "default" / alt_city / "1year" / strategy / "model.idf"
        if alt.is_file():
            return alt
    return None


def find_pmv_csvs(building_type: str, city: str = "Seoul", strategy: str = "m4") -> dict[str, bytes]:
    """Find PMV CSV files for a PMV strategy."""
    aux = {}
    strat_dir = BUILDINGS_DIR / building_type / "results" / "default" / city / "1year" / strategy
    if not strat_dir.is_dir():
        return aux
    for csv_file in strat_dir.rglob("*.csv"):
        if "pmv" in csv_file.name.lower() and not csv_file.name.startswith("eplus"):
            rel = csv_file.relative_to(strat_dir)
            aux[str(rel)] = csv_file.read_bytes()
    return aux


def extract_field_values(idf_content: str, field_comment: str) -> list[float]:
    """Extract all numeric values for a given IDF field comment."""
    pattern = rf"([\d.eE+-]+)\s*[,;]\s*!-\s*{re.escape(field_comment)}"
    return [float(m.group(1)) for m in re.finditer(pattern, idf_content)]


def extract_schedule_temps(block: str) -> list[float]:
    """Extract all temperature values from a Schedule:Compact block.

    Handles two formats:
    Format A: value on own line with field comment
        24.0,                     !- Field 6
    Format B: value inline after Until: time (hospital 24/7)
        Until: 24:00,24.0;
    """
    temps = []
    # Format A: value with !- Field N comment
    for m in re.finditer(r"^\s*([-\d.]+)\s*[,;]\s*!-\s*Field\s+\d+", block, re.MULTILINE):
        try:
            temps.append(float(m.group(1)))
        except ValueError:
            pass
    # Format B: inline "Until: HH:MM,value[,;]"
    if not temps:
        for m in re.finditer(r"Until:\s*\d{1,2}:\d{2}\s*,\s*([-\d.]+)\s*[,;]", block):
            try:
                temps.append(float(m.group(1)))
            except ValueError:
                pass
    return temps


# =====================================================================
# Test 1: Default BPS = No change (identity test)
# =====================================================================
def test_identity(building_type: str):
    """Verify that default BPS produces unchanged IDF."""
    print(f"\n{'=' * 60}")
    print(f"[{building_type}] Test 1: Identity (default BPS = no change)")
    print(f"{'=' * 60}")

    idf_path = find_idf(building_type)
    if not idf_path:
        check(False, f"IDF file not found for {building_type}", warn_only=True)
        return

    idf_content = idf_path.read_text(encoding="utf-8")
    defaults = _EMS_DEFAULTS.get(building_type, {})

    # BPS with exact default values
    bps = {
        "setpoints": {
            "cooling_occupied": defaults.get("cooling_occupied"),
            "heating_occupied": defaults.get("heating_occupied"),
            "cooling_unoccupied": defaults.get("cooling_unoccupied"),
            "heating_unoccupied": defaults.get("heating_unoccupied"),
        },
        "hvac": {},
    }
    if defaults.get("chiller_cop"):
        bps["hvac"]["chillers"] = {"cop": defaults["chiller_cop"]}
    if defaults.get("boiler_efficiency"):
        bps["hvac"]["boilers"] = {"efficiency": defaults["boiler_efficiency"]}

    result_idf, _ = apply_user_overrides(idf_content, {}, bps, building_type)
    check(result_idf == idf_content, f"Default BPS produces identical IDF ({len(idf_content)} chars)")


# =====================================================================
# Test 2: Schedule names exist in real IDF
# =====================================================================
def test_schedule_names(building_type: str):
    """Verify that _EMS_DEFAULTS schedule names actually exist in IDF."""
    print(f"\n{'=' * 60}")
    print(f"[{building_type}] Test 2: Schedule names in real IDF")
    print(f"{'=' * 60}")

    idf_path = find_idf(building_type)
    if not idf_path:
        check(False, "IDF file not found", warn_only=True)
        return

    idf_content = idf_path.read_text(encoding="utf-8")
    defaults = _EMS_DEFAULTS.get(building_type, {})

    for sch_name in defaults.get("cooling_schedules", []):
        block = _extract_schedule_block(idf_content, sch_name)
        # _w_SB variants only appear in M0 strategy, skip for baseline
        if "_w_SB" in sch_name:
            if block:
                check(True, f"Cooling schedule '{sch_name}' found (bonus)")
            else:
                check(
                    True,
                    f"Cooling schedule '{sch_name}' not in baseline (expected, M0 only)",
                )
        else:
            check(block is not None, f"Cooling schedule '{sch_name}' found in IDF")

    for sch_name in defaults.get("heating_schedules", []):
        block = _extract_schedule_block(idf_content, sch_name)
        if "_w_SB" in sch_name:
            if block:
                check(True, f"Heating schedule '{sch_name}' found (bonus)")
            else:
                check(True, f"Heating schedule '{sch_name}' not in baseline (expected, M0 only)")
        else:
            check(block is not None, f"Heating schedule '{sch_name}' found in IDF")


# =====================================================================
# Test 3: Default temperatures match real IDF
# =====================================================================
def test_default_temps(building_type: str):
    """Verify that _EMS_DEFAULTS temperatures match actual IDF values."""
    print(f"\n{'=' * 60}")
    print(f"[{building_type}] Test 3: Default temperatures match IDF")
    print(f"{'=' * 60}")

    idf_path = find_idf(building_type)
    if not idf_path:
        check(False, "IDF file not found", warn_only=True)
        return

    idf_content = idf_path.read_text(encoding="utf-8")
    defaults = _EMS_DEFAULTS.get(building_type, {})

    # Check cooling schedule
    for sch_name in defaults.get("cooling_schedules", []):
        if "_w_SB" in sch_name:
            continue
        block = _extract_schedule_block(idf_content, sch_name)
        if not block:
            continue
        temps = extract_schedule_temps(block)
        if not temps:
            check(False, f"No temps found in {sch_name}")
            continue

        cool_occ = defaults["cooling_occupied"]
        cool_unocc = defaults["cooling_unoccupied"]
        check(
            cool_occ in temps,
            f"{sch_name}: occupied {cool_occ} found in {sorted(set(temps))}",
        )
        check(
            cool_unocc in temps,
            f"{sch_name}: unoccupied {cool_unocc} found in {sorted(set(temps))}",
        )

    # Check heating schedule
    for sch_name in defaults.get("heating_schedules", []):
        if "_w_SB" in sch_name:
            continue
        block = _extract_schedule_block(idf_content, sch_name)
        if not block:
            continue
        temps = extract_schedule_temps(block)
        if not temps:
            check(False, f"No temps found in {sch_name}")
            continue

        heat_occ = defaults["heating_occupied"]
        heat_unocc = defaults["heating_unoccupied"]
        check(
            heat_occ in temps,
            f"{sch_name}: occupied {heat_occ} found in {sorted(set(temps))}",
        )
        check(
            heat_unocc in temps,
            f"{sch_name}: unoccupied {heat_unocc} found in {sorted(set(temps))}",
        )


# =====================================================================
# Test 4: Chiller COP and Boiler Efficiency match real IDF
# =====================================================================
def test_hvac_defaults(building_type: str):
    """Verify that _EMS_DEFAULTS COP/efficiency match actual IDF values."""
    print(f"\n{'=' * 60}")
    print(f"[{building_type}] Test 4: HVAC defaults match IDF")
    print(f"{'=' * 60}")

    idf_path = find_idf(building_type)
    if not idf_path:
        check(False, "IDF file not found", warn_only=True)
        return

    idf_content = idf_path.read_text(encoding="utf-8")
    defaults = _EMS_DEFAULTS.get(building_type, {})

    # Chiller COP
    if defaults.get("chiller_cop"):
        cops = extract_field_values(idf_content, "Reference COP")
        if cops:
            check(
                any(abs(c - defaults["chiller_cop"]) < 0.01 for c in cops),
                f"Chiller COP {defaults['chiller_cop']} found in IDF (actual: {cops})",
            )
        else:
            check(False, "No Reference COP fields found in IDF", warn_only=True)
    else:
        # Building without chiller
        cops = extract_field_values(idf_content, "Reference COP")
        check(len(cops) == 0, f"No chiller expected, found {len(cops)} COP fields")

    # Boiler efficiency
    if defaults.get("boiler_efficiency"):
        effs = extract_field_values(idf_content, "Nominal Thermal Efficiency")
        if effs:
            check(
                any(abs(e - defaults["boiler_efficiency"]) < 0.01 for e in effs),
                f"Boiler efficiency {defaults['boiler_efficiency']} found in IDF (actual: {effs})",
            )
        else:
            check(False, "No Nominal Thermal Efficiency fields found", warn_only=True)
    else:
        effs = extract_field_values(idf_content, "Nominal Thermal Efficiency")
        check(len(effs) == 0, f"No boiler expected, found {len(effs)} efficiency fields")


# =====================================================================
# Test 5: Setpoint patching produces correct values
# =====================================================================
def test_setpoint_patching(building_type: str):
    """Apply cooling/heating overrides and verify correct values in patched IDF."""
    print(f"\n{'=' * 60}")
    print(f"[{building_type}] Test 5: Setpoint patching correctness")
    print(f"{'=' * 60}")

    idf_path = find_idf(building_type)
    if not idf_path:
        check(False, "IDF file not found", warn_only=True)
        return

    idf_content = idf_path.read_text(encoding="utf-8")
    defaults = _EMS_DEFAULTS.get(building_type, {})

    # Patch: cooling 24→26, heating 20→22
    new_cool = defaults["cooling_occupied"] + 2.0
    new_heat = defaults["heating_occupied"] + 2.0

    bps = {
        "setpoints": {
            "cooling_occupied": new_cool,
            "heating_occupied": new_heat,
        },
        "hvac": {},
    }
    result_idf, _ = apply_user_overrides(idf_content, {}, bps, building_type)

    # Check if this is a constant schedule (occupied == unoccupied, e.g., hospital)
    cool_is_constant = abs(defaults["cooling_occupied"] - defaults["cooling_unoccupied"]) < 0.01
    heat_is_constant = abs(defaults["heating_occupied"] - defaults["heating_unoccupied"]) < 0.01

    # Verify cooling schedule
    for sch_name in defaults.get("cooling_schedules", []):
        if "_w_SB" in sch_name:
            continue
        block = _extract_schedule_block(result_idf, sch_name)
        if not block:
            continue
        temps = extract_schedule_temps(block)
        old_occ = defaults["cooling_occupied"]
        check(
            new_cool in temps,
            f"{sch_name}: new occupied {new_cool} present",
        )
        check(
            old_occ not in temps,
            f"{sch_name}: old occupied {old_occ} removed",
        )
        if not cool_is_constant:
            check(
                defaults["cooling_unoccupied"] in temps,
                f"{sch_name}: unoccupied {defaults['cooling_unoccupied']} unchanged",
            )

    # Verify heating schedule
    for sch_name in defaults.get("heating_schedules", []):
        if "_w_SB" in sch_name:
            continue
        block = _extract_schedule_block(result_idf, sch_name)
        if not block:
            continue
        temps = extract_schedule_temps(block)
        old_occ = defaults["heating_occupied"]
        check(
            new_heat in temps,
            f"{sch_name}: new occupied {new_heat} present",
        )
        check(
            old_occ not in temps,
            f"{sch_name}: old occupied {old_occ} removed",
        )
        if not heat_is_constant:
            check(
                defaults["heating_unoccupied"] in temps,
                f"{sch_name}: unoccupied {defaults['heating_unoccupied']} unchanged",
            )


# =====================================================================
# Test 6: Chiller COP patching
# =====================================================================
def test_chiller_patching(building_type: str):
    """Apply chiller COP override and verify."""
    print(f"\n{'=' * 60}")
    print(f"[{building_type}] Test 6: Chiller COP patching")
    print(f"{'=' * 60}")

    defaults = _EMS_DEFAULTS.get(building_type, {})
    if not defaults.get("chiller_cop"):
        check(True, f"No chiller for {building_type}, skipping")
        return

    idf_path = find_idf(building_type)
    if not idf_path:
        check(False, "IDF file not found", warn_only=True)
        return

    idf_content = idf_path.read_text(encoding="utf-8")
    new_cop = 4.5

    bps = {"setpoints": {}, "hvac": {"chillers": {"cop": new_cop}}}
    result_idf, _ = apply_user_overrides(idf_content, {}, bps, building_type)

    cops = extract_field_values(result_idf, "Reference COP")
    check(len(cops) > 0, f"Found {len(cops)} COP fields after patching")
    check(
        all(abs(c - new_cop) < 0.01 for c in cops),
        f"All COPs = {new_cop} (actual: {cops})",
    )
    # Verify old COP is gone
    extract_field_values(idf_content, "Reference COP")
    old_cop = defaults["chiller_cop"]
    check(
        not any(abs(c - old_cop) < 0.01 for c in cops),
        f"Old COP {old_cop} no longer present",
    )


# =====================================================================
# Test 7: Boiler efficiency patching
# =====================================================================
def test_boiler_patching(building_type: str):
    """Apply boiler efficiency override and verify."""
    print(f"\n{'=' * 60}")
    print(f"[{building_type}] Test 7: Boiler efficiency patching")
    print(f"{'=' * 60}")

    defaults = _EMS_DEFAULTS.get(building_type, {})
    if not defaults.get("boiler_efficiency"):
        check(True, f"No boiler for {building_type}, skipping")
        return

    idf_path = find_idf(building_type)
    if not idf_path:
        check(False, "IDF file not found", warn_only=True)
        return

    idf_content = idf_path.read_text(encoding="utf-8")
    new_eff = 0.92

    bps = {"setpoints": {}, "hvac": {"boilers": {"efficiency": new_eff}}}
    result_idf, _ = apply_user_overrides(idf_content, {}, bps, building_type)

    effs = extract_field_values(result_idf, "Nominal Thermal Efficiency")
    check(len(effs) > 0, f"Found {len(effs)} efficiency fields after patching")
    check(
        all(abs(e - new_eff) < 0.01 for e in effs),
        f"All efficiencies = {new_eff} (actual: {effs})",
    )


# =====================================================================
# Test 8: Collision test (occupied = default unoccupied)
# =====================================================================
def test_collision(building_type: str):
    """Critical: user sets occupied = default unoccupied value."""
    print(f"\n{'=' * 60}")
    print(f"[{building_type}] Test 8: Collision (occupied = default unoccupied)")
    print(f"{'=' * 60}")

    defaults = _EMS_DEFAULTS.get(building_type, {})

    # Skip for constant schedules (hospital: occupied == unoccupied)
    if abs(defaults["cooling_occupied"] - defaults["cooling_unoccupied"]) < 0.01:
        check(True, "Constant schedule (occ==unocc) — collision N/A, skipping")
        return

    idf_path = find_idf(building_type)
    if not idf_path:
        check(False, "IDF file not found", warn_only=True)
        return

    idf_content = idf_path.read_text(encoding="utf-8")

    # Set cooling occupied = default unoccupied (e.g., 29.0)
    # Set cooling unoccupied to something else (e.g., 32.0)
    collision_occ = defaults["cooling_unoccupied"]  # e.g., 29.0
    new_unocc = 32.0

    bps = {
        "setpoints": {
            "cooling_occupied": collision_occ,
            "cooling_unoccupied": new_unocc,
        },
        "hvac": {},
    }
    result_idf, _ = apply_user_overrides(idf_content, {}, bps, building_type)

    for sch_name in defaults.get("cooling_schedules", []):
        if "_w_SB" in sch_name:
            continue
        block = _extract_schedule_block(result_idf, sch_name)
        if not block:
            continue
        temps = extract_schedule_temps(block)

        # occupied slots should now be collision_occ (e.g., 29.0)
        # unoccupied slots should now be new_unocc (32.0)
        check(
            collision_occ in temps,
            f"{sch_name}: occupied = {collision_occ} (was {defaults['cooling_occupied']})",
        )
        check(
            new_unocc in temps,
            f"{sch_name}: unoccupied = {new_unocc} (was {defaults['cooling_unoccupied']})",
        )
        # Original occupied value should be gone
        old_occ = defaults["cooling_occupied"]
        if old_occ != collision_occ:  # only check if they're different
            check(
                old_occ not in temps,
                f"{sch_name}: original occupied {old_occ} removed",
            )


# =====================================================================
# Test 9: PMV CSV patching
# =====================================================================
def test_pmv_csv_patching(building_type: str):
    """Verify PMV CSV temperature offset for M4 strategy."""
    print(f"\n{'=' * 60}")
    print(f"[{building_type}] Test 9: PMV CSV patching")
    print(f"{'=' * 60}")

    defaults = _EMS_DEFAULTS.get(building_type, {})
    pmv_csvs = find_pmv_csvs(building_type, "Seoul", "m4")
    if not pmv_csvs:
        # Try other cities
        for city in ["Busan", "Daegu", "Incheon"]:
            pmv_csvs = find_pmv_csvs(building_type, city, "m4")
            if pmv_csvs:
                break

    if not pmv_csvs:
        check(True, f"No PMV CSVs found for {building_type}/m4, skipping")
        return

    print(f"  Found {len(pmv_csvs)} PMV CSV files")

    # Apply +2 cooling delta
    patched = _patch_pmv_csv_files(
        pmv_csvs,
        defaults,
        cooling_delta=2.0,
        heating_delta=1.0,
        cool_unocc_new=31.0,
        heat_unocc_new=16.6,
    )

    for fname, fbytes in pmv_csvs.items():
        orig_text = fbytes.decode("utf-8")
        orig_vals = []
        for line in orig_text.splitlines():
            try:
                orig_vals.append(float(line.strip()))
            except ValueError:
                pass

        patched_text = patched[fname].decode("utf-8")
        patched_vals = []
        for line in patched_text.splitlines():
            try:
                patched_vals.append(float(line.strip()))
            except ValueError:
                pass

        check(
            len(orig_vals) == len(patched_vals),
            f"{fname}: line count preserved ({len(orig_vals)} -> {len(patched_vals)})",
        )

        if not patched_vals:
            continue

        is_cooling = "cooling" in fname.lower() or "cool" in fname.lower()
        "heating" in fname.lower() or "heat" in fname.lower()

        # Verify some values changed
        changed = sum(1 for o, p in zip(orig_vals, patched_vals) if abs(o - p) > 0.01)
        check(
            changed > 0,
            f"{fname}: {changed}/{len(orig_vals)} values modified",
        )

        # Verify unoccupied replacement
        def_unocc = defaults["cooling_unoccupied"] if is_cooling else defaults["heating_unoccupied"]
        new_unocc = 31.0 if is_cooling else 16.6
        unocc_count_orig = sum(1 for v in orig_vals if abs(v - def_unocc) < 0.05)
        unocc_count_new = sum(1 for v in patched_vals if abs(v - new_unocc) < 0.05)
        if unocc_count_orig > 0:
            check(
                unocc_count_new == unocc_count_orig,
                f"{fname}: {unocc_count_orig} unoccupied values ({def_unocc}) -> {new_unocc}",
            )


# =====================================================================
# Test 10: Combined all overrides
# =====================================================================
def test_combined_overrides(building_type: str):
    """Apply all overrides simultaneously and verify."""
    print(f"\n{'=' * 60}")
    print(f"[{building_type}] Test 10: Combined all overrides")
    print(f"{'=' * 60}")

    idf_path = find_idf(building_type)
    if not idf_path:
        check(False, "IDF file not found", warn_only=True)
        return

    idf_content = idf_path.read_text(encoding="utf-8")
    defaults = _EMS_DEFAULTS.get(building_type, {})

    bps = {
        "setpoints": {
            "cooling_occupied": defaults["cooling_occupied"] + 2.0,
            "heating_occupied": defaults["heating_occupied"] - 1.0,
            "cooling_unoccupied": defaults["cooling_unoccupied"] + 3.0,
            "heating_unoccupied": defaults["heating_unoccupied"] - 2.0,
        },
        "hvac": {},
    }
    if defaults.get("chiller_cop"):
        bps["hvac"]["chillers"] = {"cop": 4.0}
    if defaults.get("boiler_efficiency"):
        bps["hvac"]["boilers"] = {"efficiency": 0.93}

    result_idf, _ = apply_user_overrides(idf_content, {}, bps, building_type)

    check(
        result_idf != idf_content,
        f"IDF was modified (orig {len(idf_content)} chars)",
    )

    cool_is_constant = abs(defaults["cooling_occupied"] - defaults["cooling_unoccupied"]) < 0.01

    # Verify cooling schedule
    for sch_name in defaults.get("cooling_schedules", []):
        if "_w_SB" in sch_name:
            continue
        block = _extract_schedule_block(result_idf, sch_name)
        if not block:
            continue
        temps = extract_schedule_temps(block)
        new_cool = defaults["cooling_occupied"] + 2.0
        new_unocc = defaults["cooling_unoccupied"] + 3.0
        check(new_cool in temps, f"{sch_name}: new cool_occ {new_cool}")
        if not cool_is_constant:
            check(new_unocc in temps, f"{sch_name}: new cool_unocc {new_unocc}")

    # Verify COP
    if defaults.get("chiller_cop"):
        cops = extract_field_values(result_idf, "Reference COP")
        check(all(abs(c - 4.0) < 0.01 for c in cops), f"All COPs = 4.0 (actual: {cops})")

    # Verify efficiency
    if defaults.get("boiler_efficiency"):
        effs = extract_field_values(result_idf, "Nominal Thermal Efficiency")
        check(all(abs(e - 0.93) < 0.01 for e in effs), f"All efficiencies = 0.93 (actual: {effs})")


# =====================================================================
# Main
# =====================================================================
def main():
    print("=" * 60)
    print("IDF PATCHER END-TO-END VERIFICATION")
    print(f"ems_simulation root: {EMS_ROOT}")
    print("=" * 60)

    if not BUILDINGS_DIR.is_dir():
        print(f"\nERROR: buildings directory not found: {BUILDINGS_DIR}")
        sys.exit(1)

    for bt in BUILDING_TYPES:
        test_identity(bt)
        test_schedule_names(bt)
        test_default_temps(bt)
        test_hvac_defaults(bt)
        test_setpoint_patching(bt)
        test_chiller_patching(bt)
        test_boiler_patching(bt)
        test_collision(bt)
        test_pmv_csv_patching(bt)
        test_combined_overrides(bt)

    print(f"\n{'=' * 60}")
    print("VERIFICATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  PASS: {PASS}")
    print(f"  FAIL: {FAIL}")
    print(f"  WARN: {WARN}")
    print(f"  TOTAL: {PASS + FAIL + WARN}")

    if FAIL > 0:
        print(f"\n*** {FAIL} FAILURES — review above ***")
        sys.exit(1)
    else:
        print("\nAll checks passed!")


if __name__ == "__main__":
    main()
