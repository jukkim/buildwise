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


def parse_energyplus_output(output_dir: str) -> dict:
    """Parse EnergyPlus simulation output files.

    Reads:
    - eplustbl.csv (or eplustbl.htm) for summary tables
    - eplusout.csv for time-series data

    Returns:
        dict with energy metrics (total_energy_kwh, eui_kwh_m2, etc.)
    """
    out_path = Path(output_dir)

    # Try HTML table summary first
    html_path = out_path / "eplustbl.htm"
    csv_path = out_path / "eplustbl.csv"
    meter_path = out_path / "eplusout.csv"

    result: dict = {}

    # Parse summary table (CSV or fallback to estimations)
    if csv_path.exists():
        result = _parse_summary_csv(csv_path)
    elif html_path.exists():
        result = _parse_summary_html(html_path)
    else:
        logger.warning("No summary table found in %s", output_dir)
        result = _estimate_from_meter_csv(meter_path) if meter_path.exists() else {}

    # Ensure required fields
    if "total_energy_kwh" not in result:
        result["total_energy_kwh"] = 0.0
    if "eui_kwh_m2" not in result:
        result["eui_kwh_m2"] = 0.0

    # Calculate cost
    if "annual_cost_krw" not in result:
        result["annual_cost_krw"] = int(result["total_energy_kwh"] * _ELECTRICITY_RATE_KRW)

    return result


def _parse_summary_csv(csv_path: Path) -> dict:
    """Parse eplustbl.csv for energy totals."""
    result: dict = {}
    try:
        with open(csv_path, encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Look for "Total Site Energy" row
        for line in content.split("\n"):
            if "Total Site Energy" in line:
                parts = line.split(",")
                for part in parts:
                    try:
                        val = float(part.strip())
                        if val > 100:  # likely GJ or kWh
                            result["total_energy_kwh"] = val * 277.78 if val < 10000 else val
                            break
                    except ValueError:
                        continue

            if "Total Building Area" in line:
                parts = line.split(",")
                for part in parts:
                    try:
                        val = float(part.strip())
                        if val > 10:
                            result["total_floor_area_m2"] = val
                            break
                    except ValueError:
                        continue

        if "total_energy_kwh" in result and "total_floor_area_m2" in result:
            result["eui_kwh_m2"] = result["total_energy_kwh"] / result["total_floor_area_m2"]

    except Exception as exc:
        logger.error("Failed to parse %s: %s", csv_path, exc)

    return result


def _parse_summary_html(html_path: Path) -> dict:
    """Parse eplustbl.htm for energy totals (simplified regex)."""
    result: dict = {}
    try:
        content = html_path.read_text(encoding="utf-8", errors="replace")

        # Extract "Total Site Energy" GJ value
        match = re.search(r"Total Site Energy.*?(\d+\.?\d*)\s*GJ", content, re.DOTALL)
        if match:
            gj = float(match.group(1))
            result["total_energy_kwh"] = gj * 277.78

        # Extract total area
        area_match = re.search(r"Total Building Area.*?(\d+\.?\d*)\s*m2", content, re.DOTALL)
        if area_match:
            area = float(area_match.group(1))
            result["total_floor_area_m2"] = area

        if "total_energy_kwh" in result and "total_floor_area_m2" in result:
            result["eui_kwh_m2"] = result["total_energy_kwh"] / result["total_floor_area_m2"]

    except Exception as exc:
        logger.error("Failed to parse %s: %s", html_path, exc)

    return result


def _estimate_from_meter_csv(meter_path: Path) -> dict:
    """Fallback: sum hourly meter data from eplusout.csv."""
    total_j = 0.0
    try:
        with open(meter_path, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                for key, val in row.items():
                    if "Electricity:Facility" in key:
                        try:
                            total_j += float(val)
                        except ValueError:
                            continue
    except Exception as exc:
        logger.error("Failed to parse meter CSV %s: %s", meter_path, exc)

    total_kwh = total_j / 3_600_000  # J → kWh
    return {"total_energy_kwh": total_kwh}
