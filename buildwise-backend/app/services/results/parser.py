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
            eui, output_dir,
        )

    # Calculate cost
    if "annual_cost_krw" not in result:
        result["annual_cost_krw"] = int(result["total_energy_kwh"] * _ELECTRICITY_RATE_KRW)

    return result


def _parse_summary_csv(csv_path: Path) -> dict:
    """Parse eplustbl.csv using column headers for unit-aware extraction."""
    result: dict = {}
    try:
        with open(csv_path, encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Find the energy summary header row containing unit information
        header_row_idx = None
        for i, row in enumerate(rows):
            joined = ",".join(row).lower()
            if "total energy" in joined and any(
                u in joined for u in ("gj", "kwh", "kbtu", "mj")
            ):
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
            for row in rows[header_row_idx + 1:]:
                if any("total site energy" in cell.lower() for cell in row):
                    if energy_col is not None and energy_col < len(row):
                        try:
                            val = float(row[energy_col].strip().replace(",", ""))
                            result["total_energy_kwh"] = val * unit_multiplier
                        except ValueError:
                            pass
                    break

            # Find area row
            for row in rows[header_row_idx + 1:]:
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

    except Exception as exc:
        logger.error("Failed to parse %s: %s", csv_path, exc)

    return result


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
