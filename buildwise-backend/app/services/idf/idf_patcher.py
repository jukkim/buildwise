"""Post-process ems_simulation-generated IDF to apply user BPS overrides.

ems_simulation uses fixed DOE Reference Building parameters. When users
modify settings (setpoint temperatures, chiller COP, boiler efficiency)
in the BuildWise UI, this module patches the generated IDF text to reflect
those changes.

Approach: text-based patching (no eppy dependency) to avoid
Schedule:Compact saveas() bugs and IDD path issues in Docker.
"""

from __future__ import annotations

import logging
import math
import re

logger = logging.getLogger(__name__)

# ems_simulation default values per building type (from actual IDF analysis).
# Used to detect when user BPS differs from ems_simulation defaults.
#
# Schedule names include _w_SB variants that some strategies (M0 night setback)
# reference for specific zones (e.g., Perimeter_mid_ZN_2).
_EMS_DEFAULTS: dict[str, dict] = {
    "large_office": {
        "cooling_occupied": 24.0,
        "heating_occupied": 20.0,
        "cooling_unoccupied": 29.0,
        "heating_unoccupied": 15.6,
        "chiller_cop": 6.1,
        "boiler_efficiency": 0.8125,
        "heating_schedules": [
            "HTGSETP_SCH_YES_OPTIMUM",
            "HTGSETP_SCH_YES_OPTIMUM_w_SB",
        ],
        "cooling_schedules": [
            "CLGSETP_SCH_YES_OPTIMUM",
            "CLGSETP_SCH_YES_OPTIMUM_w_SB",
        ],
    },
    "medium_office": {
        "cooling_occupied": 26.0,
        "heating_occupied": 20.0,
        "cooling_unoccupied": 30.0,
        "heating_unoccupied": 15.0,
        "heating_schedules": ["HeatingSPSch"],
        "cooling_schedules": ["CoolingSPSch"],
        # VRF system — no chiller/boiler objects
    },
    "small_office": {
        "cooling_occupied": 24.0,
        "heating_occupied": 20.0,
        "cooling_unoccupied": 29.0,
        "heating_unoccupied": 15.6,
        "heating_schedules": [
            "HTGSETP_SCH_NO_OPTIMUM",
            "HTGSETP_SCH_NO_OPTIMUM_w_SB",
        ],
        "cooling_schedules": [
            "CLGSETP_SCH_YES_OPTIMUM",
            "CLGSETP_SCH_YES_OPTIMUM_w_SB",
        ],
        # PSZ-HP — no chiller/boiler objects
    },
    "standalone_retail": {
        # DOE Reference: 75°F/85°F → 23.89/29.44°C (NO_SETBACK = constant on weekdays)
        "cooling_occupied": 23.89,
        "heating_occupied": 20.0,
        "cooling_unoccupied": 29.44,
        "heating_unoccupied": 15.6,
        "heating_schedules": [
            "HTGSETP_SCH_NO_OPTIMUM",
            "HTGSETP_SCH_NO_OPTIMUM_w_SB",
        ],
        "cooling_schedules": [
            "CLGSETP_SCH_NO_SETBACK",
        ],
        # PSZ-AC — no chiller/boiler objects
    },
    "primary_school": {
        "cooling_occupied": 24.0,
        "heating_occupied": 20.0,
        "cooling_unoccupied": 29.0,
        "heating_unoccupied": 15.6,
        # DX coil (Coil:Cooling:DX:TwoSpeed) — no Chiller:Electric:EIR
        "boiler_efficiency": 0.80,
        "heating_schedules": [
            "HTGSETP_SCH_YES_OPTIMUM",
            "HTGSETP_SCH_YES_OPTIMUM_w_SB",
        ],
        "cooling_schedules": [
            "CLGSETP_SCH_YES_OPTIMUM",
            "CLGSETP_SCH_YES_OPTIMUM_w_SB",
        ],
    },
    "hospital": {
        # 24/7 constant schedule (Until: 24:00,temp; — no occupied/unoccupied split)
        "cooling_occupied": 24.0,
        "heating_occupied": 21.0,
        "cooling_unoccupied": 24.0,
        "heating_unoccupied": 21.0,
        # Multiple chillers with varying COPs (4.47, 5.33) — patch all
        "chiller_cop": 5.33,
        "boiler_efficiency": 0.8125,
        "heating_schedules": ["HTGSETP_SCH"],
        "cooling_schedules": ["CLGSETP_SCH"],
    },
}


def apply_user_overrides(
    idf_content: str,
    aux_files: dict[str, bytes],
    bps: dict,
    building_type: str,
) -> tuple[str, dict[str, bytes]]:
    """Apply user BPS settings to ems_simulation-generated IDF.

    Only patches fields that differ from ems_simulation defaults.
    Returns original content unchanged if no overrides needed.
    On any error, logs a warning and returns original content (fail-safe).

    Args:
        idf_content: Raw IDF text from ems_simulation.
        aux_files: Auxiliary files (CSV schedules).
        bps: User's Building Parameter Schema dict.
        building_type: DOE Reference Building type key.

    Returns:
        Tuple of (patched_idf_content, patched_aux_files).
    """
    defaults = _EMS_DEFAULTS.get(building_type)
    if not defaults:
        logger.warning("No EMS defaults for building_type=%s, skipping overrides", building_type)
        return idf_content, aux_files

    try:
        return _apply_overrides_inner(idf_content, aux_files, bps, defaults)
    except Exception as exc:
        logger.warning(
            "IDF patching failed, returning original IDF: %s",
            exc,
            exc_info=True,
        )
        return idf_content, aux_files


def _apply_overrides_inner(
    idf_content: str,
    aux_files: dict[str, bytes],
    bps: dict,
    defaults: dict,
) -> tuple[str, dict[str, bytes]]:
    """Inner implementation of apply_user_overrides (may raise)."""
    setpoints = bps.get("setpoints", {})
    hvac = bps.get("hvac", {})
    patched_idf = idf_content
    patched_aux = dict(aux_files)

    # --- 1. Setpoint temperature overrides ---
    cool_occ = _to_float(setpoints.get("cooling_occupied"))
    heat_occ = _to_float(setpoints.get("heating_occupied"))
    cool_unocc = _to_float(setpoints.get("cooling_unoccupied"))
    heat_unocc = _to_float(setpoints.get("heating_unoccupied"))

    if _any_setpoint_changed(defaults, cool_occ, heat_occ, cool_unocc, heat_unocc):
        patched_idf = _patch_setpoint_schedules(
            patched_idf,
            defaults,
            cool_occ,
            heat_occ,
            cool_unocc,
            heat_unocc,
        )
        # Offset PMV CSV schedules (M4/M5/M7/M8 strategies)
        def_cool = defaults["cooling_occupied"]
        def_heat = defaults["heating_occupied"]
        def_cool_unocc = defaults["cooling_unoccupied"]
        def_heat_unocc = defaults["heating_unoccupied"]

        cooling_delta = (cool_occ if cool_occ is not None else def_cool) - def_cool
        heating_delta = (heat_occ if heat_occ is not None else def_heat) - def_heat
        cool_unocc_new = cool_unocc if cool_unocc is not None else def_cool_unocc
        heat_unocc_new = heat_unocc if heat_unocc is not None else def_heat_unocc

        if (
            cooling_delta != 0
            or heating_delta != 0
            or cool_unocc_new != def_cool_unocc
            or heat_unocc_new != def_heat_unocc
        ):
            patched_aux = _patch_pmv_csv_files(
                patched_aux,
                defaults,
                cooling_delta,
                heating_delta,
                cool_unocc_new,
                heat_unocc_new,
            )

        logger.info(
            "Patched setpoints: cool=%s→%s heat=%s→%s",
            def_cool,
            cool_occ,
            def_heat,
            heat_occ,
        )

    # --- 2. Chiller COP override ---
    chillers = hvac.get("chillers", {})
    user_cop = _to_float(chillers.get("cop"))
    default_cop = defaults.get("chiller_cop")
    if (
        user_cop is not None
        and default_cop is not None
        and math.isfinite(user_cop)
        and 1.0 <= user_cop <= 15.0
        and abs(user_cop - default_cop) > 0.01
    ):
        patched_idf = _patch_chiller_cop(patched_idf, user_cop)
        logger.info("Patched chiller COP: %s → %s", default_cop, user_cop)

    # --- 3. Boiler efficiency override ---
    boilers = hvac.get("boilers", {})
    user_eff = _to_float(boilers.get("efficiency"))
    default_eff = defaults.get("boiler_efficiency")
    if (
        user_eff is not None
        and default_eff is not None
        and math.isfinite(user_eff)
        and 0.1 <= user_eff <= 1.0
        and abs(user_eff - default_eff) > 0.001
    ):
        patched_idf = _patch_boiler_efficiency(patched_idf, user_eff)
        logger.info("Patched boiler efficiency: %s → %s", default_eff, user_eff)

    return patched_idf, patched_aux


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_float(val: object) -> float | None:
    """Safely convert a value to float, returning None for invalid/non-finite."""
    if val is None:
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _any_setpoint_changed(
    defaults: dict,
    cool_occ: float | None,
    heat_occ: float | None,
    cool_unocc: float | None,
    heat_unocc: float | None,
) -> bool:
    """Check if any user setpoint differs from ems_simulation default."""
    pairs = [
        (cool_occ, defaults.get("cooling_occupied")),
        (heat_occ, defaults.get("heating_occupied")),
        (cool_unocc, defaults.get("cooling_unoccupied")),
        (heat_unocc, defaults.get("heating_unoccupied")),
    ]
    return any(user is not None and default is not None and abs(user - default) > 0.01 for user, default in pairs)


def _extract_schedule_block(idf_content: str, schedule_name: str) -> str | None:
    """Extract a Schedule:Compact block from IDF by name.

    Returns the full block text from "Schedule:Compact," to the terminating ";".
    Returns None if not found.

    SECURITY: schedule_name must come from _EMS_DEFAULTS (hardcoded constants).
    """
    pattern = r"Schedule:Compact,\s*\n" r"\s*" + re.escape(schedule_name) + r"\s*," r"[\s\S]*?;"
    match = re.search(pattern, idf_content)
    if match:
        return match.group(0)
    return None


def _replace_temps_in_block(
    block: str,
    replacements: list[tuple[float, float]],
) -> str:
    """Replace temperature values in a Schedule:Compact block (single-pass).

    Uses a single regex pass to avoid collision when new_occupied == old_unoccupied.
    Each (old_temp, new_temp) pair is checked; first match wins.

    Supports two IDF formats:
    Format A (most buildings): value on its own line with field comment
        29.0,                     !- Field 4
    Format B (hospital): value inline after Until: time
        Until: 24:00,24.0;
    """
    if not replacements:
        return block

    # Filter out no-op replacements
    active = [(old, new) for old, new in replacements if abs(old - new) >= 0.01]
    if not active:
        return block

    def _replacer(m: re.Match) -> str:
        orig_text = m.group(2)
        val = float(orig_text)
        for old_temp, new_temp in active:
            if abs(val - old_temp) < 0.05:
                # Preserve original decimal precision (e.g., 23.89 → 2 places)
                dot_pos = orig_text.find(".")
                decimals = len(orig_text) - dot_pos - 1 if dot_pos >= 0 else 0
                decimals = max(decimals, 1)  # at least 1 decimal
                return m.group(1) + f"{new_temp:.{decimals}f}" + m.group(3)
        return m.group(0)

    # Format A: value on own line with !- Field N comment
    result = re.sub(
        r"^(\s*)([-\d.]+)(\s*[,;]\s*!-\s*Field\s+\d+.*)$",
        _replacer,
        block,
        flags=re.MULTILINE,
    )

    # Format B: inline "Until: HH:MM,value[,;]" (hospital 24/7 schedules)
    result = re.sub(
        r"(Until:\s*\d{1,2}:\d{2}\s*,\s*)([-\d.]+)(\s*[,;])",
        _replacer,
        result,
    )

    return result


def _patch_setpoint_schedules(
    idf_content: str,
    defaults: dict,
    cool_occ: float | None,
    heat_occ: float | None,
    cool_unocc: float | None,
    heat_unocc: float | None,
) -> str:
    """Patch Schedule:Compact blocks for setpoint temperature overrides.

    Uses single-pass replacement to avoid collision when new values
    overlap with existing defaults (e.g., user sets occupied=29.0 which
    is also the default unoccupied value).
    """
    result = idf_content

    # Build cooling replacement pairs
    cool_replacements: list[tuple[float, float]] = []
    if cool_occ is not None:
        cool_replacements.append((defaults["cooling_occupied"], cool_occ))
    if cool_unocc is not None:
        cool_replacements.append((defaults["cooling_unoccupied"], cool_unocc))

    for sch_name in defaults.get("cooling_schedules", []):
        block = _extract_schedule_block(result, sch_name)
        if not block:
            logger.debug("Cooling schedule '%s' not found in IDF", sch_name)
            continue
        new_block = _replace_temps_in_block(block, cool_replacements)
        if new_block != block:
            result = result.replace(block, new_block, 1)

    # Build heating replacement pairs
    heat_replacements: list[tuple[float, float]] = []
    if heat_occ is not None:
        heat_replacements.append((defaults["heating_occupied"], heat_occ))
    if heat_unocc is not None:
        heat_replacements.append((defaults["heating_unoccupied"], heat_unocc))

    for sch_name in defaults.get("heating_schedules", []):
        block = _extract_schedule_block(result, sch_name)
        if not block:
            logger.debug("Heating schedule '%s' not found in IDF", sch_name)
            continue
        new_block = _replace_temps_in_block(block, heat_replacements)
        if new_block != block:
            result = result.replace(block, new_block, 1)

    return result


def _patch_chiller_cop(idf_content: str, new_cop: float) -> str:
    """Replace Reference COP in all Chiller:Electric:EIR objects.

    IDF field format:
        6.1,                      !- Reference COP
    """
    return re.sub(
        r"([\s,])(\d+\.?\d*)\s*([,;]\s*!-\s*Reference COP)",
        lambda m: m.group(1) + f"{new_cop:.2f}" + m.group(3).rstrip(),
        idf_content,
    )


def _patch_boiler_efficiency(idf_content: str, new_eff: float) -> str:
    """Replace Nominal Thermal Efficiency in all Boiler:HotWater objects.

    IDF field format:
        0.8125,                   !- Nominal Thermal Efficiency
    """
    return re.sub(
        r"([\s,])(\d+\.?\d*)\s*([,;]\s*!-\s*Nominal Thermal Efficiency)",
        lambda m: m.group(1) + f"{new_eff:.4f}" + m.group(3).rstrip(),
        idf_content,
    )


def _patch_pmv_csv_files(
    aux_files: dict[str, bytes],
    defaults: dict,
    cooling_delta: float,
    heating_delta: float,
    cool_unocc_new: float,
    heat_unocc_new: float,
) -> dict[str, bytes]:
    """Offset temperature values in PMV schedule CSV files.

    PMV CSVs contain one temperature per line (8760 lines for annual).
    - Values matching default unoccupied → replace with user unoccupied value
    - Other values (PMV-adjusted occupied) → add occupied delta
    """
    def_cool_unocc = defaults["cooling_unoccupied"]
    def_heat_unocc = defaults["heating_unoccupied"]
    patched = dict(aux_files)

    for fname, fbytes in aux_files.items():
        lower = fname.lower()
        if "pmv" not in lower:
            continue

        is_cooling = "cooling" in lower or "cool" in lower
        is_heating = "heating" in lower or "heat" in lower
        if not is_cooling and not is_heating:
            continue

        try:
            text = fbytes.decode("utf-8")
            # Detect and preserve line endings
            line_sep = "\r\n" if "\r\n" in text else "\n"
            lines = text.splitlines()
            new_lines = []

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    new_lines.append(line)
                    continue
                try:
                    val = float(stripped)
                except ValueError:
                    new_lines.append(line)
                    continue

                # Reject NaN/Inf
                if not math.isfinite(val):
                    new_lines.append(line)
                    continue

                if is_cooling:
                    if abs(val - def_cool_unocc) < 0.05:
                        new_lines.append(f"{cool_unocc_new:.2f}")
                    else:
                        new_lines.append(f"{val + cooling_delta:.2f}")
                else:  # heating
                    if abs(val - def_heat_unocc) < 0.05:
                        new_lines.append(f"{heat_unocc_new:.2f}")
                    else:
                        new_lines.append(f"{val + heating_delta:.2f}")

            patched[fname] = line_sep.join(new_lines).encode("utf-8")
            logger.debug(
                "Patched PMV CSV %s: %s delta=%.1f",
                fname,
                "cooling" if is_cooling else "heating",
                cooling_delta if is_cooling else heating_delta,
            )
        except (UnicodeDecodeError, ValueError) as exc:
            logger.warning("Failed to patch PMV CSV %s: %s", fname, exc)

    return patched
