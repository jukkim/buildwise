"""Mock simulation runner for demo/development without EnergyPlus.

Returns pre-computed energy results based on building type, climate city,
and strategy. Values are EXACT per-city EUI from ems_simulation eplustbl.csv
(m0-m8 model, Feb 2026, EnergyPlus 24.1 runs).

For building/strategy/city combinations without eplustbl data, estimated
fallback savings are applied to the baseline EUI.

IMPORTANT: This is a mock runner for development/demo only. Results are
from pre-computed EnergyPlus runs, NOT live simulations.
"""

from __future__ import annotations

import hashlib
import random

# ═══════════════════════════════════════════════════════════════════════════════
# Exact EUI lookup table (kWh/m2/year) from eplustbl.csv
# Source: ems_simulation/buildings/*/results/default/*/1year/*/eplustbl.csv
#         "Total Site Energy" MJ/m2 ÷ 3.6
# Extracted: 2026-02-20 via tests/extract_eplustbl_data.py
# ═══════════════════════════════════════════════════════════════════════════════
_EUI_TABLE: dict[str, dict[str, dict[str, float]]] = {
    "large_office": {
        "baseline": {
            "Seoul": 119.75,
            "Busan": 120.65,
            "Daegu": 118.21,
            "Daejeon": 121.66,
            "Gwangju": 122.49,
            "Incheon": 118.77,
            "Gangneung": 119.59,
            "Jeju": 120.81,
            "Cheongju": 119.34,
            "Ulsan": 119.86,
        },
        "m0": {
            "Seoul": 117.95,
            "Busan": 117.17,
            "Daegu": 115.64,
            "Daejeon": 119.12,
            "Gwangju": 119.49,
            "Incheon": 116.99,
            "Gangneung": 116.65,
            "Jeju": 118.06,
            "Cheongju": 117.02,
            "Ulsan": 116.7,
        },
        "m1": {
            "Seoul": 118.1,
            "Busan": 118.82,
            "Daegu": 116.42,
            "Daejeon": 119.88,
            "Gwangju": 120.68,
            "Incheon": 117.38,
            "Gangneung": 117.9,
            "Jeju": 118.93,
            "Cheongju": 117.7,
            "Ulsan": 117.99,
        },
        "m2": {
            "Seoul": 111.72,
            "Busan": 111.16,
            "Daegu": 109.56,
            "Daejeon": 112.75,
            "Gwangju": 114.04,
            "Incheon": 110.55,
            "Gangneung": 110.55,
            "Jeju": 111.92,
            "Cheongju": 110.81,
            "Ulsan": 110.27,
        },
        "m3": {
            "Seoul": 114.47,
            "Busan": 115.04,
            "Daegu": 112.65,
            "Daejeon": 115.91,
            "Gwangju": 117.06,
            "Incheon": 113.84,
            "Gangneung": 114.3,
            "Jeju": 114.66,
            "Cheongju": 114.11,
            "Ulsan": 113.91,
        },
        "m4": {
            "Seoul": 113.17,
            "Busan": 113.12,
            "Daegu": 111.76,
            "Daejeon": 114.48,
            "Gwangju": 114.63,
            "Incheon": 112.92,
            "Gangneung": 113.15,
            "Jeju": 112.51,
            "Cheongju": 113.13,
            "Ulsan": 112.73,
        },
        "m5": {
            "Seoul": 112.81,
            "Busan": 112.22,
            "Daegu": 111.21,
            "Daejeon": 113.92,
            "Gwangju": 113.93,
            "Incheon": 112.54,
            "Gangneung": 112.52,
            "Jeju": 111.71,
            "Cheongju": 112.76,
            "Ulsan": 111.93,
        },
        "m6": {
            "Seoul": 109.83,
            "Busan": 109.48,
            "Daegu": 107.74,
            "Daejeon": 110.89,
            "Gwangju": 112.11,
            "Incheon": 109.02,
            "Gangneung": 108.94,
            "Jeju": 109.84,
            "Cheongju": 109.15,
            "Ulsan": 108.42,
        },
        "m7": {
            "Seoul": 110.57,
            "Busan": 109.96,
            "Daegu": 108.89,
            "Daejeon": 111.53,
            "Gwangju": 111.91,
            "Incheon": 110.07,
            "Gangneung": 109.9,
            "Jeju": 110.05,
            "Cheongju": 110.12,
            "Ulsan": 109.36,
        },
        "m8": {
            "Seoul": 110.29,
            "Busan": 109.18,
            "Daegu": 108.48,
            "Daejeon": 111.07,
            "Gwangju": 111.32,
            "Incheon": 109.83,
            "Gangneung": 109.41,
            "Jeju": 109.38,
            "Cheongju": 109.85,
            "Ulsan": 108.71,
        },
    },
    "medium_office": {
        "baseline": {
            "Seoul": 77.57,
            "Busan": 77.97,
            "Daegu": 77.5,
            "Daejeon": 78.41,
            "Gwangju": 78.64,
            "Incheon": 76.68,
            "Gangneung": 78.19,
            "Jeju": 77.0,
            "Cheongju": 77.56,
            "Ulsan": 78.18,
        },
        "m0": {
            "Seoul": 77.57,
            "Busan": 77.97,
            "Daegu": 77.5,
            "Daejeon": 78.41,
            "Gwangju": 78.64,
            "Incheon": 76.68,
            "Gangneung": 78.19,
            "Jeju": 77.0,
            "Cheongju": 77.56,
            "Ulsan": 78.18,
        },
        "m4": {
            "Seoul": 76.32,
            "Busan": 77.14,
            "Daegu": 76.35,
            "Daejeon": 77.59,
            "Gwangju": 77.88,
            "Incheon": 75.39,
            "Gangneung": 77.3,
            "Jeju": 75.86,
            "Cheongju": 76.4,
            "Ulsan": 77.33,
        },
        "m5": {
            "Seoul": 75.74,
            "Busan": 76.51,
            "Daegu": 75.77,
            "Daejeon": 77.03,
            "Gwangju": 77.29,
            "Incheon": 74.78,
            "Gangneung": 76.69,
            "Jeju": 75.24,
            "Cheongju": 75.86,
            "Ulsan": 76.74,
        },
    },
    "small_office": {
        "baseline": {
            "Seoul": 97.78,
            "Busan": 98.06,
            "Daegu": 97.06,
            "Daejeon": 98.35,
            "Gwangju": 98.97,
            "Incheon": 96.96,
            "Gangneung": 98.0,
            "Jeju": 97.38,
            "Cheongju": 97.61,
            "Ulsan": 97.88,
        },
        "m2": {
            "Seoul": 90.5,
            "Busan": 88.83,
            "Daegu": 89.16,
            "Daejeon": 90.62,
            "Gwangju": 90.71,
            "Incheon": 89.8,
            "Gangneung": 89.51,
            "Jeju": 88.82,
            "Cheongju": 90.24,
            "Ulsan": 88.78,
        },
        "m4": {
            "Seoul": 87.88,
            "Busan": 87.0,
            "Daegu": 86.82,
            "Daejeon": 88.15,
            "Gwangju": 88.29,
            "Incheon": 87.38,
            "Gangneung": 87.6,
            "Jeju": 86.41,
            "Cheongju": 87.81,
            "Ulsan": 87.12,
        },
        "m5": {
            "Seoul": 86.58,
            "Busan": 85.89,
            "Daegu": 85.62,
            "Daejeon": 86.94,
            "Gwangju": 87.11,
            "Incheon": 86.03,
            "Gangneung": 86.42,
            "Jeju": 85.26,
            "Cheongju": 86.53,
            "Ulsan": 85.99,
        },
        "m6": {
            "Seoul": 90.5,
            "Busan": 88.83,
            "Daegu": 89.16,
            "Daejeon": 90.62,
            "Gwangju": 90.71,
            "Incheon": 89.8,
            "Gangneung": 89.51,
            "Jeju": 88.82,
            "Cheongju": 90.24,
            "Ulsan": 88.78,
        },
        "m7": {
            "Seoul": 86.32,
            "Busan": 84.82,
            "Daegu": 85.01,
            "Daejeon": 86.41,
            "Gwangju": 86.58,
            "Incheon": 85.63,
            "Gangneung": 85.5,
            "Jeju": 84.48,
            "Cheongju": 86.06,
            "Ulsan": 84.8,
        },
        "m8": {
            "Seoul": 85.02,
            "Busan": 83.78,
            "Daegu": 83.86,
            "Daejeon": 85.21,
            "Gwangju": 85.43,
            "Incheon": 84.33,
            "Gangneung": 84.3,
            "Jeju": 83.36,
            "Cheongju": 84.8,
            "Ulsan": 83.69,
        },
    },
    "standalone_retail": {
        "baseline": {
            "Seoul": 130.36,
            "Busan": 120.25,
            "Daegu": 123.58,
            "Daejeon": 127.9,
            "Gwangju": 125.46,
            "Incheon": 131.56,
            "Gangneung": 124.62,
            "Jeju": 122.4,
            "Cheongju": 129.0,
            "Ulsan": 120.78,
        },
        "m0": {
            "Seoul": 151.83,
            "Busan": 133.8,
            "Daegu": 142.38,
            "Daejeon": 148.2,
            "Gwangju": 142.92,
            "Incheon": 153.02,
            "Gangneung": 142.47,
            "Jeju": 135.65,
            "Cheongju": 148.72,
            "Ulsan": 135.67,
        },
        "m2": {
            "Seoul": 130.83,
            "Busan": 118.04,
            "Daegu": 123.46,
            "Daejeon": 127.73,
            "Gwangju": 124.82,
            "Incheon": 132.22,
            "Gangneung": 123.62,
            "Jeju": 120.78,
            "Cheongju": 129.14,
            "Ulsan": 118.62,
        },
        "m4": {
            "Seoul": 119.08,
            "Busan": 109.79,
            "Daegu": 112.61,
            "Daejeon": 116.93,
            "Gwangju": 114.44,
            "Incheon": 120.06,
            "Gangneung": 113.97,
            "Jeju": 111.8,
            "Cheongju": 117.84,
            "Ulsan": 110.3,
        },
        "m5": {
            "Seoul": 115.59,
            "Busan": 107.31,
            "Daegu": 109.61,
            "Daejeon": 113.76,
            "Gwangju": 111.46,
            "Incheon": 116.33,
            "Gangneung": 111.16,
            "Jeju": 109.08,
            "Cheongju": 114.37,
            "Ulsan": 107.71,
        },
        "m6": {
            "Seoul": 130.83,
            "Busan": 118.04,
            "Daegu": 123.46,
            "Daejeon": 127.73,
            "Gwangju": 124.82,
            "Incheon": 132.22,
            "Gangneung": 123.62,
            "Jeju": 120.78,
            "Cheongju": 129.14,
            "Ulsan": 118.62,
        },
        "m7": {
            "Seoul": 118.46,
            "Busan": 108.92,
            "Daegu": 111.89,
            "Daejeon": 116.11,
            "Gwangju": 113.63,
            "Incheon": 119.45,
            "Gangneung": 113.09,
            "Jeju": 111.09,
            "Cheongju": 117.1,
            "Ulsan": 109.33,
        },
        "m8": {
            "Seoul": 114.98,
            "Busan": 106.46,
            "Daegu": 108.92,
            "Daejeon": 112.96,
            "Gwangju": 110.69,
            "Incheon": 115.72,
            "Gangneung": 110.3,
            "Jeju": 108.38,
            "Cheongju": 113.63,
            "Ulsan": 106.78,
        },
    },
    "primary_school": {
        "baseline": {
            "Seoul": 143.3,
            "Busan": 134.89,
            "Daegu": 137.96,
            "Daejeon": 142.71,
            "Gwangju": 140.21,
            "Incheon": 143.99,
            "Gangneung": 138.86,
            "Jeju": 134.18,
            "Cheongju": 142.83,
            "Ulsan": 135.57,
        },
        "m0": {
            "Seoul": 143.21,
            "Busan": 133.07,
            "Daegu": 136.63,
            "Daejeon": 142.72,
            "Gwangju": 139.17,
            "Incheon": 143.99,
            "Gangneung": 138.41,
            "Jeju": 131.7,
            "Cheongju": 142.28,
            "Ulsan": 134.12,
        },
        "m1": {
            "Seoul": 143.85,
            "Busan": 135.0,
            "Daegu": 138.22,
            "Daejeon": 143.34,
            "Gwangju": 140.5,
            "Incheon": 144.59,
            "Gangneung": 139.33,
            "Jeju": 134.0,
            "Cheongju": 143.3,
            "Ulsan": 135.8,
        },
        "m2": {
            "Seoul": 139.5,
            "Busan": 129.62,
            "Daegu": 133.6,
            "Daejeon": 138.54,
            "Gwangju": 135.47,
            "Incheon": 140.25,
            "Gangneung": 134.32,
            "Jeju": 129.11,
            "Cheongju": 138.92,
            "Ulsan": 130.41,
        },
        "m3": {
            "Seoul": 143.03,
            "Busan": 133.72,
            "Daegu": 137.29,
            "Daejeon": 142.43,
            "Gwangju": 139.3,
            "Incheon": 143.9,
            "Gangneung": 138.65,
            "Jeju": 132.69,
            "Cheongju": 142.65,
            "Ulsan": 134.72,
        },
        "m4": {
            "Seoul": 136.92,
            "Busan": 129.05,
            "Daegu": 131.32,
            "Daejeon": 136.58,
            "Gwangju": 133.74,
            "Incheon": 137.91,
            "Gangneung": 132.99,
            "Jeju": 127.71,
            "Cheongju": 136.24,
            "Ulsan": 129.63,
        },
        "m5": {
            "Seoul": 134.8,
            "Busan": 127.87,
            "Daegu": 129.56,
            "Daejeon": 134.75,
            "Gwangju": 132.16,
            "Incheon": 135.65,
            "Gangneung": 131.34,
            "Jeju": 126.16,
            "Cheongju": 134.07,
            "Ulsan": 128.2,
        },
        "m6": {
            "Seoul": 139.5,
            "Busan": 129.62,
            "Daegu": 133.6,
            "Daejeon": 138.54,
            "Gwangju": 135.47,
            "Incheon": 140.25,
            "Gangneung": 134.32,
            "Jeju": 129.11,
            "Cheongju": 138.92,
            "Ulsan": 130.41,
        },
        "m7": {
            "Seoul": 134.22,
            "Busan": 125.81,
            "Daegu": 128.47,
            "Daejeon": 133.46,
            "Gwangju": 130.69,
            "Incheon": 135.12,
            "Gangneung": 129.52,
            "Jeju": 125.0,
            "Cheongju": 133.35,
            "Ulsan": 126.19,
        },
        "m8": {
            "Seoul": 132.16,
            "Busan": 124.77,
            "Daegu": 126.76,
            "Daejeon": 131.73,
            "Gwangju": 129.23,
            "Incheon": 132.95,
            "Gangneung": 128.01,
            "Jeju": 123.52,
            "Cheongju": 131.25,
            "Ulsan": 124.91,
        },
    },
    "hospital": {
        "baseline": {
            "Daegu": 340.2,
            "Daejeon": 342.57,
            "Gwangju": 340.21,
            "Incheon": 340.92,
            "Gangneung": 342.84,
            "Jeju": 331.58,
            "Cheongju": 341.96,
            "Ulsan": 336.73,
        },
    },
}

# ---------------------------------------------------------------------------
# Derived: average baseline EUI per building type (for external reference)
# ---------------------------------------------------------------------------
_BASE_EUI: dict[str, float] = {}
for _bt, _strats in _EUI_TABLE.items():
    _bl = _strats.get("baseline", {})
    if _bl:
        _BASE_EUI[_bt] = round(sum(_bl.values()) / len(_bl.values()), 1)

# ---------------------------------------------------------------------------
# Fallback savings (%) for strategies WITHOUT eplustbl data
# Applied as: strategy_eui = baseline_eui × (1 - pct / 100)
# ---------------------------------------------------------------------------
_FALLBACK_SAVINGS: dict[str, dict[str, float]] = {
    "medium_office": {
        # VRF — no eplustbl for m1, m2, m3, m6, m7, m8
        "m1": 1.7,
        "m2": 0.0,
        "m3": 0.0,
        "m6": 0.0,
        "m7": 2.5,
        "m8": 3.0,
    },
    "small_office": {
        # PSZ-HP — no eplustbl for m0, m1, m3
        "m0": 1.0,
        "m1": 2.0,
        "m3": 0.0,
    },
    "standalone_retail": {
        # PSZ-AC — no eplustbl for m1, m3
        "m1": 2.0,
        "m3": 0.0,
    },
    "hospital": {
        # No strategy eplustbl at all — industry estimates
        "m0": 0.8,
        "m1": 2.0,
        "m2": 1.2,
        "m3": 2.5,
        "m4": 1.0,
        "m5": 1.5,
        "m6": 2.5,
        "m7": 3.5,
        "m8": 4.5,
    },
}

# ---------------------------------------------------------------------------
# Energy breakdown fractions (sum to 1.0)
# Source: eplustbl.csv Seoul baseline end use analysis
# ---------------------------------------------------------------------------
_BREAKDOWN_BY_TYPE: dict[str, dict[str, float]] = {
    "large_office": {"hvac": 0.28, "lighting": 0.23, "equipment": 0.48, "other": 0.01},
    "medium_office": {"hvac": 0.45, "lighting": 0.17, "equipment": 0.33, "other": 0.05},
    "small_office": {"hvac": 0.28, "lighting": 0.30, "equipment": 0.32, "other": 0.10},
    "standalone_retail": {"hvac": 0.37, "lighting": 0.41, "equipment": 0.14, "other": 0.08},
    "primary_school": {"hvac": 0.39, "lighting": 0.13, "equipment": 0.44, "other": 0.04},
    "hospital": {"hvac": 0.55, "lighting": 0.15, "equipment": 0.25, "other": 0.05},
}

_BREAKDOWN_DEFAULT: dict[str, float] = {"hvac": 0.50, "lighting": 0.15, "equipment": 0.30, "other": 0.05}

# HVAC sub-breakdown fractions (fan/pump are fixed; cooling/heating vary by climate)
_HVAC_FAN_FRACTION = 0.13
_HVAC_PUMP_FRACTION = 0.07

# Climate-based cooling/heating ratio (cooling fraction of HVAC)
_CLIMATE_COOLING_RATIO: dict[str, float] = {
    "Seoul": 0.48,
    "Busan": 0.52,
    "Daegu": 0.55,
    "Daejeon": 0.47,
    "Gwangju": 0.50,
    "Incheon": 0.45,
    "Gangneung": 0.40,
    "Jeju": 0.58,
    "Cheongju": 0.46,
    "Ulsan": 0.53,
}

# Peak demand factor (avg demand × factor = peak demand)
_PEAK_FACTOR: dict[str, float] = {
    "large_office": 2.3,
    "medium_office": 2.5,
    "small_office": 2.8,
    "standalone_retail": 2.6,
    "primary_school": 3.3,
    "hospital": 1.8,
}

# Summer peak months by climate
_PEAK_MONTH: dict[str, int] = {
    "Seoul": 7,
    "Busan": 8,
    "Daegu": 7,
    "Daejeon": 7,
    "Gwangju": 7,
    "Incheon": 8,
    "Gangneung": 8,
    "Jeju": 8,
    "Cheongju": 7,
    "Ulsan": 8,
}

# KRW per kWh (simplified Korean electricity tariff)
_KRW_PER_KWH = 120

# ═══════════════════════════════════════════════════════════════════════════════
# DOE Reference Building defaults (from ems_simulation building_specific/*.yaml)
# These are the exact conditions under which eplustbl.csv EUI values were computed.
# When user_config matches these → factor=1.0 → exact eplustbl results.
# ═══════════════════════════════════════════════════════════════════════════════
_DOE_DEFAULTS: dict[str, dict[str, float]] = {
    "large_office": {
        "cooling_occupied": 24.0,
        "heating_occupied": 20.0,
        "cooling_unoccupied": 29.0,
        "heating_unoccupied": 15.6,
        "cop_cooling": 6.1,
        "efficiency_heating": 0.80,
        "wwr": 0.38,
        "wall_u_value": 0.45,
        "window_shgc": 0.25,
        "roof_u_value": 0.27,
        "window_u_value": 2.0,
        "lpd": 10.76,
        "epd": 10.76,
        "infiltration_ach": 0.5,
        "people_density": 0.0565,
        "operating_hours_start": 8,
        "operating_hours_end": 18,
        "workdays_per_week": 5,
        "saturday_factor": 0.5,
    },
    "medium_office": {
        "cooling_occupied": 26.0,
        "heating_occupied": 20.0,
        "cooling_unoccupied": 30.0,
        "heating_unoccupied": 15.0,
        "cop_cooling": 4.0,
        "efficiency_heating": 3.5,
        "wwr": 0.33,
        "wall_u_value": 0.45,
        "window_shgc": 0.25,
        "roof_u_value": 0.27,
        "window_u_value": 2.0,
        "lpd": 10.76,
        "epd": 8.07,
        "infiltration_ach": 0.5,
        "people_density": 0.0565,
        "operating_hours_start": 8,
        "operating_hours_end": 18,
        "workdays_per_week": 5,
        "saturday_factor": 0.5,
    },
    "small_office": {
        "cooling_occupied": 24.0,
        "heating_occupied": 20.0,
        "cooling_unoccupied": 29.0,
        "heating_unoccupied": 15.6,
        "cop_cooling": 3.2,
        "efficiency_heating": 2.8,
        "wwr": 0.21,
        "wall_u_value": 0.45,
        "window_shgc": 0.25,
        "roof_u_value": 0.27,
        "window_u_value": 2.0,
        "lpd": 10.76,
        "epd": 10.76,
        "infiltration_ach": 0.5,
        "people_density": 0.0565,
        "operating_hours_start": 8,
        "operating_hours_end": 18,
        "workdays_per_week": 5,
        "saturday_factor": 0.5,
    },
    "standalone_retail": {
        "cooling_occupied": 23.89,
        "heating_occupied": 20.0,
        "cooling_unoccupied": 29.44,
        "heating_unoccupied": 15.6,
        "cop_cooling": 3.0,
        "efficiency_heating": 0.80,
        "wwr": 0.11,
        "wall_u_value": 0.45,
        "window_shgc": 0.25,
        "roof_u_value": 0.27,
        "window_u_value": 2.0,
        "lpd": 16.4,
        "epd": 4.3,
        "infiltration_ach": 0.5,
        "people_density": 0.0637,
        "operating_hours_start": 8,
        "operating_hours_end": 21,
        "workdays_per_week": 6,
        "saturday_factor": 1.0,
    },
    "primary_school": {
        "cooling_occupied": 24.0,
        "heating_occupied": 20.0,
        "cooling_unoccupied": 29.0,
        "heating_unoccupied": 15.6,
        "cop_cooling": 5.5,
        "efficiency_heating": 0.85,
        "wwr": 0.35,
        "wall_u_value": 0.45,
        "window_shgc": 0.25,
        "roof_u_value": 0.27,
        "window_u_value": 2.0,
        "lpd": 12.9,
        "epd": 6.5,
        "infiltration_ach": 0.5,
        "people_density": 0.0890,
        "operating_hours_start": 7,
        "operating_hours_end": 16,
        "workdays_per_week": 5,
        "saturday_factor": 0.0,
    },
    "hospital": {
        "cooling_occupied": 24.0,
        "heating_occupied": 21.0,
        "cooling_unoccupied": 24.0,
        "heating_unoccupied": 21.0,
        "cop_cooling": 5.33,
        "efficiency_heating": 0.80,
        "wwr": 0.35,
        "wall_u_value": 0.45,
        "window_shgc": 0.25,
        "roof_u_value": 0.27,
        "window_u_value": 2.0,
        "lpd": 12.0,
        "epd": 10.0,
        "infiltration_ach": 0.5,
        "people_density": 0.0300,
        "operating_hours_start": 0,
        "operating_hours_end": 24,
        "workdays_per_week": 7,
        "saturday_factor": 1.0,
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# Sensitivity coefficients: physically motivated adjustment factors
# Each entry defines how a parameter change affects a specific energy component.
# Sources: ASHRAE Research, LBNL parametric studies, DOE Reference Building analysis
# ═══════════════════════════════════════════════════════════════════════════════
_SENSITIVITY: dict[str, dict] = {
    # Setpoint effects on HVAC sub-components
    # ASHRAE: +1°C cooling SP → ~3.5% less cooling energy
    "cooling_occupied": {
        "component": "cooling",
        "type": "linear_per_degree",
        "coefficient": -0.035,
    },
    "heating_occupied": {
        "component": "heating",
        "type": "linear_per_degree",
        "coefficient": 0.035,
    },
    # Unoccupied setback: smaller effect (~1%/°C)
    "cooling_unoccupied": {
        "component": "cooling",
        "type": "linear_per_degree",
        "coefficient": -0.010,
    },
    "heating_unoccupied": {
        "component": "heating",
        "type": "linear_per_degree",
        "coefficient": 0.010,
    },
    # COP/efficiency: thermodynamic inverse (E ∝ 1/COP)
    "cop_cooling": {
        "component": "cooling",
        "type": "inverse_ratio",
    },
    "efficiency_heating": {
        "component": "heating",
        "type": "inverse_ratio",
    },
    # WWR: +10% WWR → ~+5% cooling, ~+1.5% heating (LBNL)
    "wwr": {
        "component": "cooling_and_heating",
        "type": "wwr_sensitivity",
        "cooling_coefficient": 0.50,
        "heating_coefficient": 0.15,
    },
    # Wall U-value: +0.1 W/m²K → ~+0.8% HVAC (conductive heat transfer)
    "wall_u_value": {
        "component": "cooling_and_heating",
        "type": "envelope_u_value",
        "cooling_coefficient": 0.04,
        "heating_coefficient": 0.04,
    },
    # Window SHGC: +0.1 → ~+3% cooling energy (solar heat gain)
    "window_shgc": {
        "component": "cooling",
        "type": "linear_per_unit",
        "coefficient": 0.30,
    },
    # LPD/EPD: directly proportional
    "lpd": {
        "component": "lighting",
        "type": "linear_ratio",
    },
    "epd": {
        "component": "equipment",
        "type": "linear_ratio",
    },
    # Roof U-value: similar to wall_u_value but only significant for low-rise
    # Single-story buildings (retail, school) have roof_area ≈ footprint_area
    "roof_u_value": {
        "component": "cooling_and_heating",
        "type": "envelope_u_value",
        "cooling_coefficient": 0.03,
        "heating_coefficient": 0.03,
    },
    # Window U-value: conductive heat transfer through glazing (complements SHGC)
    # Effect scaled by WWR (more glass → more conductive loss/gain)
    "window_u_value": {
        "component": "cooling_and_heating",
        "type": "window_u_sensitivity",
        "cooling_coefficient": 0.015,
        "heating_coefficient": 0.025,
    },
    # Infiltration: +ACH → more outdoor air → more HVAC load
    # Doubling infiltration from 0.5 to 1.0 → ~40% more HVAC
    "infiltration_ach": {
        "component": "cooling_and_heating",
        "type": "infiltration_sensitivity",
        "coefficient": 0.40,
    },
    # People density: higher occupancy → more internal heat gain → more cooling, less heating
    # Also increases ventilation load (ASHRAE 62.1)
    "people_density": {
        "component": "cooling_and_heating",
        "type": "occupancy_sensitivity",
        "cooling_coefficient": 0.15,
        "heating_coefficient": -0.10,
    },
    # Operating schedule: HVAC/lighting/equipment runtime proportional to weekly hours
    # Affects all load-dependent components
    "operating_schedule": {
        "component": "all",
        "type": "schedule_ratio",
    },
}


def _compute_schedule_factor(
    defaults: dict[str, float],
    user_config: dict[str, float],
) -> float:
    """Compute weekly operating hours ratio (user vs DOE default).

    Returns ratio of user weekly hours to default weekly hours.
    If no schedule parameters changed, returns 1.0.
    """
    sched_keys = ("operating_hours_start", "operating_hours_end", "workdays_per_week", "saturday_factor")
    if not any(k in user_config for k in sched_keys):
        return 1.0

    def _weekly_hours(start: float, end: float, wdays: float, sat: float) -> float:
        daily = max(0.0, end - start)
        return wdays * daily + sat * daily

    d_start = defaults.get("operating_hours_start", 8)
    d_end = defaults.get("operating_hours_end", 18)
    d_wdays = defaults.get("workdays_per_week", 5)
    d_sat = defaults.get("saturday_factor", 0.5)

    u_start = float(user_config.get("operating_hours_start", d_start))
    u_end = float(user_config.get("operating_hours_end", d_end))
    u_wdays = float(user_config.get("workdays_per_week", d_wdays))
    u_sat = float(user_config.get("saturday_factor", d_sat))

    default_hours = _weekly_hours(d_start, d_end, d_wdays, d_sat)
    user_hours = _weekly_hours(u_start, u_end, u_wdays, u_sat)

    if default_hours <= 0:
        return 1.0

    return max(0.3, min(3.0, user_hours / default_hours))


def _compute_adjustment_factor(
    building_type: str,
    climate_city: str,
    user_config: dict[str, float],
) -> float:
    """Compute EUI adjustment factor from user_config vs DOE defaults.

    Returns a multiplicative factor: adjusted_eui = eplustbl_eui × factor.
    Factor of 1.0 means no change (user_config matches DOE defaults).

    Algorithm:
    1. For each user-specified parameter, compute component-level delta
    2. Weight by energy breakdown fractions and climate cooling/heating split
    3. Combine into single overall factor, clamped to [0.5, 2.0]
    """
    if not user_config:
        return 1.0

    defaults = _DOE_DEFAULTS.get(building_type, _DOE_DEFAULTS.get("large_office", {}))
    breakdown = _BREAKDOWN_BY_TYPE.get(building_type, _BREAKDOWN_DEFAULT)
    cooling_ratio = _CLIMATE_COOLING_RATIO.get(climate_city, 0.48)
    heating_ratio = max(0.0, 1.0 - cooling_ratio - _HVAC_FAN_FRACTION - _HVAC_PUMP_FRACTION)

    # Per-component factors (start at 1.0 = no change)
    cooling_factor = 1.0
    heating_factor = 1.0
    lighting_factor = 1.0
    equipment_factor = 1.0

    # Schedule ratio: computed separately because it affects multiple components
    schedule_factor = _compute_schedule_factor(defaults, user_config)

    for param, user_val in user_config.items():
        default_val = defaults.get(param)
        if default_val is None:
            continue
        sens = _SENSITIVITY.get(param)
        if sens is None:
            continue

        sens_type = sens["type"]

        if sens_type == "linear_per_degree":
            delta = float(user_val) - float(default_val)
            change = delta * sens["coefficient"]
            if sens["component"] == "cooling":
                cooling_factor += change
            elif sens["component"] == "heating":
                heating_factor += change

        elif sens_type == "inverse_ratio":
            u = float(user_val)
            d = float(default_val)
            if u > 0 and d > 0:
                ratio = d / u
                if sens["component"] == "cooling":
                    cooling_factor *= ratio
                elif sens["component"] == "heating":
                    heating_factor *= ratio

        elif sens_type == "wwr_sensitivity":
            delta = float(user_val) - float(default_val)
            cooling_factor += delta * sens["cooling_coefficient"]
            heating_factor += delta * sens["heating_coefficient"]

        elif sens_type == "envelope_u_value":
            delta = float(user_val) - float(default_val)
            cooling_factor += delta * sens["cooling_coefficient"]
            heating_factor += delta * sens["heating_coefficient"]

        elif sens_type == "window_u_sensitivity":
            # Window U-value effect scales with actual WWR
            wwr = float(user_config.get("wwr", defaults.get("wwr", 0.38)))
            delta = float(user_val) - float(default_val)
            cooling_factor += delta * sens["cooling_coefficient"] * (wwr / 0.38)
            heating_factor += delta * sens["heating_coefficient"] * (wwr / 0.38)

        elif sens_type == "infiltration_sensitivity":
            d = float(default_val)
            if d > 0:
                ratio_change = (float(user_val) - d) / d
                change = ratio_change * sens["coefficient"]
                cooling_factor += change
                heating_factor += change

        elif sens_type == "occupancy_sensitivity":
            d = float(default_val)
            if d > 0:
                ratio_change = (float(user_val) - d) / d
                cooling_factor += ratio_change * sens["cooling_coefficient"]
                heating_factor += ratio_change * sens["heating_coefficient"]

        elif sens_type == "linear_per_unit":
            delta = float(user_val) - float(default_val)
            change = delta * sens["coefficient"]
            if sens["component"] == "cooling":
                cooling_factor += change

        elif sens_type == "linear_ratio":
            d = float(default_val)
            if d > 0:
                ratio = float(user_val) / d
                if sens["component"] == "lighting":
                    lighting_factor = ratio
                elif sens["component"] == "equipment":
                    equipment_factor = ratio

    # Apply schedule factor to all load-dependent components
    cooling_factor *= schedule_factor
    heating_factor *= schedule_factor
    lighting_factor *= schedule_factor
    equipment_factor *= schedule_factor

    # Clamp individual factors to physical limits
    cooling_factor = max(0.3, min(3.0, cooling_factor))
    heating_factor = max(0.3, min(3.0, heating_factor))
    lighting_factor = max(0.0, min(3.0, lighting_factor))
    equipment_factor = max(0.0, min(3.0, equipment_factor))

    # Weighted combination using energy breakdown fractions
    hvac_frac = breakdown["hvac"]
    hvac_factor = (
        cooling_ratio * cooling_factor
        + heating_ratio * heating_factor
        + _HVAC_FAN_FRACTION * schedule_factor  # fan follows schedule
        + _HVAC_PUMP_FRACTION * schedule_factor  # pump follows schedule
    )

    overall = (
        hvac_frac * hvac_factor
        + breakdown["lighting"] * lighting_factor
        + breakdown["equipment"] * equipment_factor
        + breakdown.get("other", 0.05) * 1.0  # 'other': not adjustable
    )

    return max(0.5, min(2.0, overall))


# ---------------------------------------------------------------------------
# BPS Pydantic schema defaults (from app/schemas/bps.py)
# Values at these defaults indicate "user didn't explicitly set this parameter".
# They are excluded from user_config so adjustment factor stays at 1.0 for
# unmodified buildings, ensuring exact eplustbl EUI regardless of building type.
# ---------------------------------------------------------------------------
_BPS_PYDANTIC_DEFAULTS: dict[str, float] = {
    "cooling_occupied": 24.0,
    "heating_occupied": 20.0,
    "cooling_unoccupied": 29.0,
    "heating_unoccupied": 15.6,
    "wwr": 0.38,
    "window_shgc": 0.25,
    "infiltration_ach": 0.5,
    "people_density": 0.0565,
    "lpd": 10.76,
    "epd": 10.76,
    "operating_hours_start": 8.0,
    "operating_hours_end": 18.0,
    "workdays_per_week": 5.0,
    "saturday_factor": 0.5,
}

_BPS_HVAC_PYDANTIC_DEFAULTS: dict[str, dict[str, float]] = {
    "vav_chiller_boiler": {"cop_cooling": 6.1, "efficiency_heating": 0.8125},
    "vav_chiller_boiler_school": {"cop_cooling": 6.1, "efficiency_heating": 0.8125},
    "vrf": {"cop_cooling": 4.0, "efficiency_heating": 3.5},
    "psz_hp": {"cop_cooling": 3.67, "efficiency_heating": 3.2},
    "psz_ac": {"cop_cooling": 3.67, "efficiency_heating": 3.2},
}


def extract_user_config(bps_json: dict, building_type: str) -> dict[str, float]:
    """Extract sensitivity-relevant parameters from BPS JSON.

    Maps nested BPS structure to flat key-value pairs matching _DOE_DEFAULTS keys.
    Only parameters that differ from BPS Pydantic schema defaults are returned.
    Parameters at schema defaults are considered "not explicitly set by user"
    and excluded, ensuring unmodified buildings get exact eplustbl EUI values.
    """
    if not bps_json:
        return {}

    config: dict[str, float] = {}

    # Setpoints
    sp = bps_json.get("setpoints", {})
    if isinstance(sp, dict):
        for key in ("cooling_occupied", "heating_occupied", "cooling_unoccupied", "heating_unoccupied"):
            if key in sp:
                config[key] = float(sp[key])

    # HVAC COP / efficiency
    hvac = bps_json.get("hvac", {})
    if isinstance(hvac, dict):
        sys_type = hvac.get("system_type", "")

        if sys_type in ("vav_chiller_boiler", "vav_chiller_boiler_school"):
            chillers = hvac.get("chillers")
            if isinstance(chillers, dict) and "cop" in chillers:
                config["cop_cooling"] = float(chillers["cop"])
            boilers = hvac.get("boilers")
            if isinstance(boilers, dict) and "efficiency" in boilers:
                config["efficiency_heating"] = float(boilers["efficiency"])

        elif sys_type == "vrf":
            vrf = hvac.get("vrf_outdoor_units")
            if isinstance(vrf, dict):
                if "cop_cooling" in vrf:
                    config["cop_cooling"] = float(vrf["cop_cooling"])
                if "cop_heating" in vrf:
                    config["efficiency_heating"] = float(vrf["cop_heating"])

        elif sys_type in ("psz_hp", "psz_ac"):
            psz = hvac.get("psz_units")
            if isinstance(psz, dict):
                if "cop_cooling" in psz:
                    config["cop_cooling"] = float(psz["cop_cooling"])
                if "cop_heating" in psz:
                    config["efficiency_heating"] = float(psz["cop_heating"])

    # Geometry: WWR
    geom = bps_json.get("geometry", {})
    if isinstance(geom, dict):
        wwr = geom.get("wwr")
        if wwr is not None:
            if isinstance(wwr, int | float):
                config["wwr"] = float(wwr)
            elif isinstance(wwr, dict):
                vals = [float(wwr.get(d, 0.38)) for d in ("north", "south", "east", "west")]
                config["wwr"] = sum(vals) / len(vals)

    # Envelope
    env = bps_json.get("envelope", {})
    if isinstance(env, dict):
        if "wall_u_value" in env and env["wall_u_value"] is not None:
            config["wall_u_value"] = float(env["wall_u_value"])
        if "window_shgc" in env and env["window_shgc"] is not None:
            config["window_shgc"] = float(env["window_shgc"])
        if "roof_u_value" in env and env["roof_u_value"] is not None:
            config["roof_u_value"] = float(env["roof_u_value"])
        if "window_u_value" in env and env["window_u_value"] is not None:
            config["window_u_value"] = float(env["window_u_value"])
        if "infiltration_ach" in env:
            config["infiltration_ach"] = float(env["infiltration_ach"])

    # Internal loads
    loads = bps_json.get("internal_loads", {})
    if isinstance(loads, dict):
        if "lighting_power_density" in loads:
            config["lpd"] = float(loads["lighting_power_density"])
        if "equipment_power_density" in loads:
            config["epd"] = float(loads["equipment_power_density"])
        if "people_density" in loads:
            config["people_density"] = float(loads["people_density"])

    # Schedules / operating hours
    schedules = bps_json.get("schedules", {})
    if isinstance(schedules, dict):
        oh = schedules.get("operating_hours", {})
        if isinstance(oh, dict):
            if "start" in oh:
                config["operating_hours_start"] = _parse_hour(oh["start"])
            if "end" in oh:
                config["operating_hours_end"] = _parse_hour(oh["end"])
        workdays = schedules.get("workdays")
        if isinstance(workdays, list) and workdays:
            config["workdays_per_week"] = float(len(workdays))
        saturday = schedules.get("saturday")
        if isinstance(saturday, str):
            sat_map = {"full_day": 1.0, "half_day": 0.5, "off": 0.0}
            config["saturday_factor"] = sat_map.get(saturday, 0.5)

    # Filter out parameters at BPS Pydantic schema defaults.
    # Values matching schema defaults mean "user didn't change this" — exclude
    # them so DOE template results are returned without spurious adjustments.
    hvac_sys = bps_json.get("hvac", {}).get("system_type", "")
    hvac_defaults = _BPS_HVAC_PYDANTIC_DEFAULTS.get(hvac_sys, {})
    all_defaults = {**_BPS_PYDANTIC_DEFAULTS, **hvac_defaults}

    filtered: dict[str, float] = {}
    for k, v in config.items():
        schema_default = all_defaults.get(k)
        if schema_default is not None and abs(float(v) - schema_default) < 0.001:
            continue  # At schema default → user didn't set → skip
        filtered[k] = v

    return filtered


def _parse_hour(time_str: str) -> float:
    """Parse 'HH:MM' string to hour as float (e.g., '08:30' → 8.5)."""
    try:
        parts = str(time_str).split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return h + m / 60.0
    except (ValueError, IndexError):
        return 8.0  # fallback to default


def _lookup_eui(
    building_type: str,
    climate_city: str,
    strategy: str,
) -> tuple[float, float]:
    """Look up exact EUI from eplustbl table, with fallback chain.

    Returns (strategy_eui, baseline_eui) in kWh/m2/year.

    Lookup priority:
    1. Exact match: _EUI_TABLE[building][strategy][city]
    2. Baseline + fallback savings: _EUI_TABLE[building][baseline][city] × (1 - pct)
    3. Average of available cities for this strategy
    4. Average of available cities for baseline + fallback
    5. Generic default (180 kWh/m2)
    """
    table = _EUI_TABLE.get(building_type, {})
    strategy_data = table.get(strategy, {})
    baseline_data = table.get("baseline", {})

    # Priority 1: Exact match for both strategy and baseline
    if climate_city in strategy_data and climate_city in baseline_data:
        return strategy_data[climate_city], baseline_data[climate_city]

    # Priority 2: Have baseline for this city, apply fallback savings
    if climate_city in baseline_data:
        bl = baseline_data[climate_city]
        if strategy == "baseline":
            return bl, bl
        fallback = _FALLBACK_SAVINGS.get(building_type, {}).get(strategy, 0.0)
        return bl * (1 - fallback / 100), bl

    # Priority 3/4: Use averages of available cities
    if strategy_data:
        s_avg = sum(strategy_data.values()) / len(strategy_data)
    else:
        s_avg = None

    if baseline_data:
        b_avg = sum(baseline_data.values()) / len(baseline_data)
    else:
        b_avg = None

    if s_avg is not None and b_avg is not None:
        return s_avg, b_avg

    if b_avg is not None:
        if strategy == "baseline":
            return b_avg, b_avg
        fallback = _FALLBACK_SAVINGS.get(building_type, {}).get(strategy, 0.0)
        return b_avg * (1 - fallback / 100), b_avg

    # Priority 5: Generic default with deterministic noise
    seed_str = f"{building_type}:{climate_city}"
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    noise = 1.0 + rng.uniform(-0.03, 0.03)
    default = 180.0 * noise
    return default, default


# ═══════════════════════════════════════════════════════════════════════════════
# Monthly energy profile generation
# ═══════════════════════════════════════════════════════════════════════════════

_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Cooling distribution by city (fraction per month, sums to 1.0)
# Based on CDD (Cooling Degree Days) from Korean weather data
_MONTHLY_COOLING: dict[str, list[float]] = {
    "Seoul": [0, 0, 0.01, 0.04, 0.09, 0.18, 0.26, 0.24, 0.12, 0.04, 0.01, 0],
    "Busan": [0, 0, 0.01, 0.04, 0.08, 0.16, 0.24, 0.26, 0.14, 0.05, 0.01, 0],
    "Daegu": [0, 0, 0.01, 0.04, 0.10, 0.18, 0.27, 0.24, 0.11, 0.04, 0.01, 0],
    "Daejeon": [0, 0, 0.01, 0.04, 0.09, 0.17, 0.26, 0.25, 0.12, 0.04, 0.01, 0],
    "Gwangju": [0, 0, 0.01, 0.04, 0.09, 0.17, 0.25, 0.25, 0.13, 0.04, 0.01, 0],
    "Incheon": [0, 0, 0.01, 0.03, 0.08, 0.16, 0.25, 0.27, 0.14, 0.04, 0.01, 0],
    "Gangneung": [0, 0, 0.01, 0.03, 0.07, 0.15, 0.24, 0.28, 0.15, 0.05, 0.01, 0],
    "Jeju": [0, 0, 0.02, 0.05, 0.09, 0.16, 0.23, 0.25, 0.13, 0.05, 0.02, 0],
    "Cheongju": [0, 0, 0.01, 0.04, 0.09, 0.17, 0.26, 0.25, 0.12, 0.04, 0.01, 0],
    "Ulsan": [0, 0, 0.01, 0.04, 0.08, 0.16, 0.24, 0.26, 0.14, 0.05, 0.01, 0],
}

# Heating distribution by city (fraction per month, sums to 1.0)
# Based on HDD (Heating Degree Days) from Korean weather data
_MONTHLY_HEATING: dict[str, list[float]] = {
    "Seoul": [0.22, 0.18, 0.12, 0.05, 0.01, 0, 0, 0, 0.01, 0.06, 0.15, 0.20],
    "Busan": [0.23, 0.19, 0.14, 0.06, 0.01, 0, 0, 0, 0, 0.05, 0.13, 0.19],
    "Daegu": [0.22, 0.18, 0.13, 0.05, 0.01, 0, 0, 0, 0, 0.05, 0.15, 0.21],
    "Daejeon": [0.22, 0.18, 0.12, 0.05, 0.01, 0, 0, 0, 0.01, 0.06, 0.15, 0.20],
    "Gwangju": [0.22, 0.18, 0.13, 0.05, 0.01, 0, 0, 0, 0, 0.06, 0.14, 0.21],
    "Incheon": [0.21, 0.18, 0.13, 0.06, 0.02, 0, 0, 0, 0.01, 0.06, 0.14, 0.19],
    "Gangneung": [0.21, 0.17, 0.13, 0.06, 0.02, 0, 0, 0, 0.01, 0.07, 0.14, 0.19],
    "Jeju": [0.24, 0.20, 0.15, 0.06, 0.01, 0, 0, 0, 0, 0.04, 0.12, 0.18],
    "Cheongju": [0.22, 0.18, 0.12, 0.05, 0.01, 0, 0, 0, 0.01, 0.06, 0.15, 0.20],
    "Ulsan": [0.23, 0.19, 0.13, 0.06, 0.01, 0, 0, 0, 0, 0.05, 0.13, 0.20],
}


def _generate_monthly_profile(
    cooling_kwh: float,
    heating_kwh: float,
    fan_kwh: float,
    pump_kwh: float,
    lighting_kwh: float,
    equipment_kwh: float,
    climate_city: str,
) -> list[dict]:
    """Generate 12-month energy profile.

    Returns list of 12 dicts with keys:
    month, cooling, heating, fan, pump, lighting, equipment, total
    """
    cool_pattern = _MONTHLY_COOLING.get(climate_city, _MONTHLY_COOLING["Seoul"])
    heat_pattern = _MONTHLY_HEATING.get(climate_city, _MONTHLY_HEATING["Seoul"])

    # Fan/pump follow combined HVAC load pattern
    total_hvac_pattern = [c + h for c, h in zip(cool_pattern, heat_pattern)]
    hvac_sum = sum(total_hvac_pattern) or 1.0
    fan_pump_pattern = [x / hvac_sum for x in total_hvac_pattern]

    profile = []
    for i in range(12):
        month_data = {
            "month": _MONTH_NAMES[i],
            "cooling": round(cooling_kwh * cool_pattern[i], 1),
            "heating": round(heating_kwh * heat_pattern[i], 1),
            "fan": round(fan_kwh * fan_pump_pattern[i], 1),
            "pump": round(pump_kwh * fan_pump_pattern[i], 1),
            "lighting": round(lighting_kwh / 12, 1),
            "equipment": round(equipment_kwh / 12, 1),
        }
        month_data["total"] = round(sum(v for k, v in month_data.items() if k != "month"), 1)
        profile.append(month_data)

    return profile


def generate_mock_result(
    building_type: str,
    climate_city: str,
    strategy: str,
    total_floor_area_m2: float,
    user_config: dict[str, float] | None = None,
) -> dict:
    """Generate realistic mock energy simulation results.

    Returns dict compatible with EnergyResult model fields.
    Uses exact eplustbl.csv EUI values for known building/city/strategy
    combinations, with fallback estimation for unknown combinations.

    When user_config is provided, a physics-based adjustment factor is applied
    to account for deviations from DOE Reference Building defaults. When
    user_config matches DOE defaults, factor=1.0 (exact eplustbl values).

    MOCK DATA DISCLAIMER: These results are from pre-computed EnergyPlus
    simulation runs, not live simulations.
    """
    strategy_eui, baseline_eui = _lookup_eui(building_type, climate_city, strategy)

    # Apply user_config adjustment if provided
    if user_config:
        factor = _compute_adjustment_factor(building_type, climate_city, user_config)
        strategy_eui *= factor
        baseline_eui *= factor

    # Total energy
    total_energy = strategy_eui * total_floor_area_m2

    # Building-type-specific breakdown
    breakdown = _BREAKDOWN_BY_TYPE.get(building_type, _BREAKDOWN_DEFAULT)
    hvac = total_energy * breakdown["hvac"]
    lighting = total_energy * breakdown["lighting"]
    equipment = total_energy * breakdown["equipment"]

    # Climate-aware HVAC sub-components
    cooling_ratio = _CLIMATE_COOLING_RATIO.get(climate_city, 0.48)
    heating_ratio = 1.0 - cooling_ratio - _HVAC_FAN_FRACTION - _HVAC_PUMP_FRACTION
    cooling = hvac * cooling_ratio
    heating = hvac * heating_ratio
    fan = hvac * _HVAC_FAN_FRACTION
    pump = hvac * _HVAC_PUMP_FRACTION

    # Peak demand (building-type-specific factor)
    peak_factor = _PEAK_FACTOR.get(building_type, 2.5)
    peak_kw = total_energy / 8760 * peak_factor

    # Peak month by climate
    peak_month = _PEAK_MONTH.get(climate_city, 7)

    # Cost
    annual_cost = int(total_energy * _KRW_PER_KWH)

    # Savings vs baseline
    if strategy != "baseline" and baseline_eui > 0:
        savings_pct = round((baseline_eui - strategy_eui) / baseline_eui * 100, 1)
        baseline_total = baseline_eui * total_floor_area_m2
        savings_kwh = baseline_total - total_energy
        annual_savings = int(savings_kwh * _KRW_PER_KWH)
    else:
        savings_pct = None
        savings_kwh = None
        annual_savings = None

    # Monthly energy profile
    monthly_profile = _generate_monthly_profile(
        cooling_kwh=cooling,
        heating_kwh=heating,
        fan_kwh=fan,
        pump_kwh=pump,
        lighting_kwh=lighting,
        equipment_kwh=equipment,
        climate_city=climate_city,
    )

    return {
        "total_energy_kwh": round(total_energy, 1),
        "hvac_energy_kwh": round(hvac, 1),
        "cooling_energy_kwh": round(cooling, 1),
        "heating_energy_kwh": round(heating, 1),
        "fan_energy_kwh": round(fan, 1),
        "pump_energy_kwh": round(pump, 1),
        "lighting_energy_kwh": round(lighting, 1),
        "equipment_energy_kwh": round(equipment, 1),
        "eui_kwh_m2": round(strategy_eui, 2),
        "peak_demand_kw": round(peak_kw, 1),
        "peak_demand_month": peak_month,
        "savings_kwh": round(savings_kwh, 1) if savings_kwh is not None else None,
        "savings_pct": savings_pct if strategy != "baseline" else None,
        "annual_cost_krw": annual_cost,
        "annual_savings_krw": annual_savings,
        "monthly_profile": monthly_profile,
        "is_mock": True,
    }
