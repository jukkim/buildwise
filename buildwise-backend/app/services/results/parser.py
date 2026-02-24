"""EnergyPlus output parser.

Reads EnergyPlus CSV/HTML summary outputs and extracts key metrics.
"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Korean electricity tariff (simplified: KRW/kWh)
_ELECTRICITY_RATE_KRW = 120

# Facility meters to sum for total energy
_FACILITY_METERS = [
    "Electricity:Facility",
    "NaturalGas:Facility",
    "DistrictCooling:Facility",
    "DistrictHeating:Facility",
]

# Unit conversion factors to kWh
_UNIT_TO_KWH: dict[str, float] = {
    "gj": 277.78,
    "kwh": 1.0,
    "kbtu": 0.293071,
    "mj": 0.27778,
}

# End-use category mapping for eplustbl.csv
_END_USE_MAP: dict[str, str] = {
    "heating": "heating_energy_kwh",
    "cooling": "cooling_energy_kwh",
    "interior lighting": "lighting_energy_kwh",
    "interior equipment": "equipment_energy_kwh",
    "fans": "fan_energy_kwh",
    "pumps": "pump_energy_kwh",
}


def parse_energyplus_output(output_dir: str) -> dict:
    """Parse EnergyPlus simulation output files.

    Reads:
    - eplustbl.csv (or eplustbl.htm) for summary tables
    - eplusout.csv for time-series data

    Returns:
        dict with energy metrics (total_energy_kwh, eui_kwh_m2, etc.)

    Raises:
        ValueError: If no valid energy data could be extracted (prevents
            silent zero-energy results from being stored as COMPLETED).
    """
    out_path = Path(output_dir)

    html_path = out_path / "eplustbl.htm"
    csv_path = out_path / "eplustbl.csv"
    meter_path = out_path / "eplusout.csv"

    result: dict = {}

    # Parse summary table (CSV or fallback to estimations)
    if csv_path.exists():
        result = _parse_summary_csv(csv_path)
    elif html_path.exists():
        result = _parse_summary_html(html_path)
    elif meter_path.exists():
        result = _estimate_from_meter_csv(meter_path)
    else:
        logger.warning("No EnergyPlus output files found in %s", output_dir)

    # Validate: total energy must be positive
    total = result.get("total_energy_kwh", 0.0)
    if total <= 0.0:
        raise ValueError(
            f"Parsed total_energy_kwh={total} from {output_dir}. "
            "No valid energy data found — likely parse failure or "
            "EnergyPlus produced no output."
        )

    # Calculate EUI if area is available
    if "eui_kwh_m2" not in result and "total_floor_area_m2" in result:
        area = result["total_floor_area_m2"]
        if area > 0:
            result["eui_kwh_m2"] = result["total_energy_kwh"] / area

    if "eui_kwh_m2" not in result:
        result["eui_kwh_m2"] = 0.0

    # Warn on physically unreasonable EUI
    eui = result.get("eui_kwh_m2", 0.0)
    if eui > 0 and (eui < 10 or eui > 2000):
        logger.warning(
            "Parsed EUI=%.1f kWh/m2 from %s — outside typical range [10, 2000]",
            eui,
            output_dir,
        )

    # Run result validation
    from app.services.results.validator import validate_result

    report = validate_result(result)
    if report.errors:
        for issue in report.errors:
            logger.error("Result validation [%s] %s", issue.rule_id, issue.message)
    for issue in report.warnings:
        logger.warning("Result validation [%s] %s", issue.rule_id, issue.message)

    # Compute HVAC total from components
    hvac_components = ["cooling_energy_kwh", "heating_energy_kwh", "fan_energy_kwh", "pump_energy_kwh"]
    hvac_total = sum(result.get(k, 0.0) for k in hvac_components)
    if hvac_total > 0:
        result["hvac_energy_kwh"] = hvac_total

    # Calculate cost
    if "annual_cost_krw" not in result:
        result["annual_cost_krw"] = int(result["total_energy_kwh"] * _ELECTRICITY_RATE_KRW)

    # Parse monthly energy profile from eplusmtr.csv
    mtr_path = out_path / "eplusmtr.csv"
    if mtr_path.exists():
        monthly = _parse_monthly_profile(mtr_path, result)
        if monthly:
            result["monthly_profile"] = monthly

    return result


def _parse_summary_csv(csv_path: Path) -> dict:
    """Parse eplustbl.csv — extracts total energy, area, EUI, and End Uses breakdown."""
    result: dict = {}
    try:
        with open(csv_path, encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Find the energy summary header row containing unit information
        header_row_idx = None
        for i, row in enumerate(rows):
            joined = ",".join(row).lower()
            if "total energy" in joined and any(u in joined for u in ("gj", "kwh", "kbtu", "mj")):
                header_row_idx = i
                break

        if header_row_idx is not None:
            headers = [h.strip().lower() for h in rows[header_row_idx]]

            # Determine energy column and unit from header
            energy_col = None
            unit_multiplier = 1.0
            for idx, h in enumerate(headers):
                if "total energy" in h:
                    for unit_key, multiplier in _UNIT_TO_KWH.items():
                        if unit_key in h:
                            energy_col = idx
                            unit_multiplier = multiplier
                            break
                    if energy_col is not None:
                        break

            # Find "Total Site Energy" data row
            for row in rows[header_row_idx + 1 :]:
                if any("total site energy" in cell.lower() for cell in row):
                    if energy_col is not None and energy_col < len(row):
                        try:
                            val = float(row[energy_col].strip().replace(",", ""))
                            result["total_energy_kwh"] = val * unit_multiplier
                        except ValueError:
                            pass
                    break

            # Find area row
            for row in rows[header_row_idx + 1 :]:
                if any("total building area" in cell.lower() for cell in row):
                    for cell in row[1:]:
                        try:
                            val = float(cell.strip().replace(",", ""))
                            if val > 10:
                                result["total_floor_area_m2"] = val
                                break
                        except ValueError:
                            continue
                    break
        else:
            # Fallback: legacy heuristic parsing for non-standard formats
            result = _parse_summary_csv_legacy(csv_path, rows)

        if "total_energy_kwh" in result and "total_floor_area_m2" in result:
            result["eui_kwh_m2"] = result["total_energy_kwh"] / result["total_floor_area_m2"]

        # Parse End Uses breakdown
        _parse_end_uses(rows, result)

    except Exception as exc:
        logger.error("Failed to parse %s: %s", csv_path, exc)

    return result


def _parse_end_uses(rows: list[list[str]], result: dict) -> None:
    """Extract End Uses breakdown from eplustbl.csv rows.

    The End Uses section looks like:
    End Uses
    ,,Electricity [GJ],Natural Gas [GJ],...,District Cooling [GJ],...
    ,Heating,0.00,0.00,...
    ,Cooling,0.00,...,123.14,...
    ...
    """
    # Find "End Uses" section header
    end_uses_start = None
    for i, row in enumerate(rows):
        if len(row) >= 1 and row[0].strip().lower() == "end uses":
            end_uses_start = i
            break

    if end_uses_start is None:
        return

    # The header row with fuel columns is the next non-empty row
    header_row = None
    for i in range(end_uses_start + 1, min(end_uses_start + 5, len(rows))):
        joined = ",".join(rows[i]).lower()
        if "electricity" in joined or "district cooling" in joined:
            header_row = i
            break

    if header_row is None:
        return

    headers = [h.strip().lower() for h in rows[header_row]]

    # Find all energy columns and their unit multipliers
    energy_cols: list[tuple[int, float]] = []
    for idx, h in enumerate(headers):
        for unit_key, multiplier in _UNIT_TO_KWH.items():
            if f"[{unit_key}]" in h:
                energy_cols.append((idx, multiplier))
                break

    if not energy_cols:
        return

    # Parse end-use rows (after header)
    for row in rows[header_row + 1 :]:
        if len(row) < 2:
            continue

        # End use name is in column 1 (column 0 is often empty)
        end_use_name = ""
        for cell in row[:3]:
            stripped = cell.strip().lower()
            if stripped and stripped != ",":
                end_use_name = stripped
                break

        if not end_use_name or end_use_name.startswith("total end"):
            break  # Stop at "Total End Uses" or empty row

        target_key = _END_USE_MAP.get(end_use_name)
        if target_key is None:
            continue

        # Sum all fuel columns for this end use
        total_kwh = 0.0
        for col_idx, multiplier in energy_cols:
            if col_idx < len(row):
                try:
                    val = float(row[col_idx].strip().replace(",", ""))
                    total_kwh += val * multiplier
                except ValueError:
                    continue

        if total_kwh > 0:
            result[target_key] = total_kwh


def _parse_summary_csv_legacy(csv_path: Path, rows: list[list[str]]) -> dict:
    """Legacy fallback parser for eplustbl.csv without structured headers."""
    result: dict = {}
    for row in rows:
        line = ",".join(row)
        if "Total Site Energy" in line:
            for cell in row:
                try:
                    val = float(cell.strip().replace(",", ""))
                    if val > 100:
                        # Assume GJ if < 10000, else kWh
                        result["total_energy_kwh"] = val * 277.78 if val < 10000 else val
                        break
                except ValueError:
                    continue

        if "Total Building Area" in line:
            for cell in row:
                try:
                    val = float(cell.strip().replace(",", ""))
                    if val > 10:
                        result["total_floor_area_m2"] = val
                        break
                except ValueError:
                    continue
    return result


def _parse_summary_html(html_path: Path) -> dict:
    """Parse eplustbl.htm for energy totals with multi-unit support."""
    result: dict = {}
    try:
        content = html_path.read_text(encoding="utf-8", errors="replace")

        # Match "Total Site Energy" with any supported unit
        match = re.search(
            r"Total Site Energy.*?([\d,]+\.?\d*)\s*(GJ|kWh|kBtu|MJ)",
            content,
            re.DOTALL,
        )
        if match:
            val = float(match.group(1).replace(",", ""))
            unit = match.group(2).lower()
            multiplier = _UNIT_TO_KWH.get(unit, 1.0)
            result["total_energy_kwh"] = val * multiplier

        # Extract total area
        area_match = re.search(
            r"Total Building Area.*?([\d,]+\.?\d*)\s*m2",
            content,
            re.DOTALL,
        )
        if area_match:
            area = float(area_match.group(1).replace(",", ""))
            result["total_floor_area_m2"] = area

        if "total_energy_kwh" in result and "total_floor_area_m2" in result:
            result["eui_kwh_m2"] = result["total_energy_kwh"] / result["total_floor_area_m2"]

    except Exception as exc:
        logger.error("Failed to parse %s: %s", html_path, exc)

    return result


def _estimate_from_meter_csv(meter_path: Path) -> dict:
    """Fallback: sum hourly meter data from eplusout.csv for all fuel types."""
    totals_j: dict[str, float] = {}
    try:
        with open(meter_path, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                for key, val in row.items():
                    for meter in _FACILITY_METERS:
                        if meter in key:
                            try:
                                totals_j[meter] = totals_j.get(meter, 0.0) + float(val)
                            except ValueError:
                                continue
    except Exception as exc:
        logger.error("Failed to parse meter CSV %s: %s", meter_path, exc)

    total_kwh = sum(totals_j.values()) / 3_600_000  # J -> kWh
    return {"total_energy_kwh": total_kwh}


# Meter name patterns for monthly profile extraction
# Order matters: more specific patterns first to avoid partial matches
_METER_PATTERNS: list[tuple[str, str]] = [
    ("Cooling:Electricity", "cooling_direct"),
    ("Heating:Electricity", "heating_direct"),
    ("DistrictCooling:Facility", "district_cooling"),
    ("DistrictHeating:Facility", "district_heating"),
    ("Electricity:Facility", "electricity"),
    ("NaturalGas:Facility", "gas"),
    ("Fans:Electricity", "fan"),
    ("Pumps:Electricity", "pump"),
    ("InteriorLights:Electricity", "lighting"),
    ("InteriorEquipment:Electricity", "equipment"),
]

# Month name → number mapping for Monthly timestep format
_MONTH_NAME_TO_NUM: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_J_TO_KWH = 1.0 / 3_600_000


def _parse_monthly_profile(mtr_path: Path, annual: dict) -> list[dict] | None:
    """Parse eplusmtr.csv for monthly energy profile.

    Sums hourly meter data by month, then distributes annual cooling/heating
    totals (from eplustbl End Uses) across months proportional to HVAC load.

    Args:
        mtr_path: Path to eplusmtr.csv.
        annual: Annual results dict (must contain end-use breakdowns).

    Returns:
        List of 12 monthly dicts compatible with mock_runner format, or None.
    """
    try:
        with open(mtr_path, encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            headers = next(reader)

        # Map column indices to meter keys (skip RunPeriod columns)
        col_map: dict[str, int] = {}
        for idx, h in enumerate(headers):
            h_stripped = h.strip()
            if "RunPeriod" in h_stripped:
                continue
            for pattern, key in _METER_PATTERNS:
                if pattern in h_stripped:
                    col_map[key] = idx
                    break

        if not col_map:
            return None

        # Detect timestep: "Hourly" or "Monthly"
        first_header = headers[1].strip() if len(headers) > 1 else ""
        is_monthly = "Monthly" in first_header

        # Accumulate monthly sums (in Joules)
        monthly_j: dict[int, dict[str, float]] = {m: {} for m in range(1, 13)}

        with open(mtr_path, encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for row in reader:
                if not row or not row[0].strip():
                    continue
                dt = row[0].strip()

                if is_monthly:
                    # Monthly format: "January", "February", ...
                    month = _MONTH_NAME_TO_NUM.get(dt.lower())
                else:
                    # Hourly format: "01/15  13:00:00"
                    try:
                        month = int(dt.split("/")[0])
                    except (ValueError, IndexError):
                        month = None

                if month is None or month < 1 or month > 12:
                    continue

                for key, col_idx in col_map.items():
                    if col_idx < len(row):
                        try:
                            val = float(row[col_idx].strip())
                            monthly_j[month][key] = monthly_j[month].get(key, 0.0) + val
                        except ValueError:
                            continue

        # Convert J → kWh and build profile
        annual_cooling = annual.get("cooling_energy_kwh", 0.0)
        annual_heating = annual.get("heating_energy_kwh", 0.0)

        # Compute monthly cooling/heating proxy from meter data
        # If direct Cooling/Heating meters exist, use them
        has_direct_cool = "cooling_direct" in col_map
        has_direct_heat = "heating_direct" in col_map

        monthly_cool_proxy: list[float] = []
        monthly_heat_proxy: list[float] = []
        for m in range(1, 13):
            d = monthly_j[m]
            if has_direct_cool:
                cool = d.get("cooling_direct", 0.0)
            else:
                # Proxy: chiller electricity (Elec - non-HVAC) + DistrictCooling
                elec = d.get("electricity", 0.0)
                fans = d.get("fan", 0.0)
                pumps = d.get("pump", 0.0)
                lights = d.get("lighting", 0.0)
                equip = d.get("equipment", 0.0)
                dc = d.get("district_cooling", 0.0)
                cool = max(0.0, elec - fans - pumps - lights - equip) + dc

            if has_direct_heat:
                heat = d.get("heating_direct", 0.0)
            else:
                # Proxy: NaturalGas + DistrictHeating
                gas = d.get("gas", 0.0)
                dh = d.get("district_heating", 0.0)
                heat = gas + dh

            monthly_cool_proxy.append(cool)
            monthly_heat_proxy.append(heat)

        cool_total = sum(monthly_cool_proxy)
        heat_total = sum(monthly_heat_proxy)

        # Fallback: if no proxy data, distribute evenly across 12 months
        if cool_total == 0.0:
            monthly_cool_proxy = [1.0] * 12
            cool_total = 12.0
        if heat_total == 0.0:
            monthly_heat_proxy = [1.0] * 12
            heat_total = 12.0

        # Check if we have facility-level meters for total calculation
        has_facility = any(k in col_map for k in ("electricity", "gas", "district_cooling", "district_heating"))
        annual_total = annual.get("total_energy_kwh", 0.0)

        profile = []
        for m in range(1, 13):
            d = monthly_j[m]
            if has_facility:
                # Total from facility meters
                total_kwh = (
                    sum(d.get(k, 0.0) for k in ("electricity", "gas", "district_cooling", "district_heating"))
                    * _J_TO_KWH
                )
            else:
                # Fallback: distribute annual total evenly
                total_kwh = annual_total / 12

            fan_kwh = d.get("fan", 0.0) * _J_TO_KWH
            pump_kwh = d.get("pump", 0.0) * _J_TO_KWH
            lighting_kwh = d.get("lighting", 0.0) * _J_TO_KWH
            equipment_kwh = d.get("equipment", 0.0) * _J_TO_KWH

            # Distribute annual cooling/heating by monthly proxy fraction
            cooling_kwh = annual_cooling * (monthly_cool_proxy[m - 1] / cool_total)
            heating_kwh = annual_heating * (monthly_heat_proxy[m - 1] / heat_total)

            profile.append(
                {
                    "month": _MONTH_NAMES[m - 1],
                    "total": round(total_kwh, 1),
                    "cooling": round(cooling_kwh, 1),
                    "heating": round(heating_kwh, 1),
                    "fan": round(fan_kwh, 1),
                    "pump": round(pump_kwh, 1),
                    "lighting": round(lighting_kwh, 1),
                    "equipment": round(equipment_kwh, 1),
                }
            )

        return profile

    except Exception as exc:
        logger.error("Failed to parse monthly profile from %s: %s", mtr_path, exc)
        return None
