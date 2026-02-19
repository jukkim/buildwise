"""Mock simulation runner for demo/development without EnergyPlus.

Returns pre-computed realistic energy results based on building type,
climate city, and strategy. Values derived from ASHRAE 90.1 reference
buildings and energyplus_sim validated simulation results.
"""

from __future__ import annotations

import hashlib
import random

# Base EUI values per building type (kWh/m2/year) from ASHRAE 90.1 reference buildings
_BASE_EUI: dict[str, float] = {
    "large_office": 215.0,
    "medium_office": 145.0,
    "small_office": 120.0,
    "standalone_retail": 180.0,
    "primary_school": 160.0,
    "hospital": 280.0,
}

# Climate adjustment factors (relative to Seoul baseline)
_CLIMATE_FACTOR: dict[str, float] = {
    "Seoul": 1.00,
    "Busan": 0.92,
    "Daegu": 1.05,
    "Daejeon": 0.98,
    "Gwangju": 0.95,
    "Incheon": 1.02,
    "Gangneung": 1.08,
    "Jeju": 0.88,
    "Cheongju": 1.00,
    "Ulsan": 0.93,
}

# Climate-based cooling/heating ratio (cooling fraction of HVAC)
# Hot climates → more cooling; cold climates → more heating
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

# Strategy savings percentages (relative to baseline)
_STRATEGY_SAVINGS: dict[str, dict[str, float]] = {
    "baseline": {"savings_pct": 0.0},
    "m0": {"savings_pct": 3.2},   # Optimal Start/Stop
    "m1": {"savings_pct": 4.5},   # Occupancy Control
    "m2": {"savings_pct": 5.8},   # Night Ventilation
    "m3": {"savings_pct": 2.1},   # Setpoint Adjustment
    "m4": {"savings_pct": 6.3},   # Peak Limiting
    "m5": {"savings_pct": 4.0},   # Daylighting + DCV
    "m6": {"savings_pct": 7.5},   # Staging Control
    "m7": {"savings_pct": 12.8},  # Full Normal
    "m8": {"savings_pct": 15.2},  # Full Savings
}

# Building-type-specific top-level energy breakdown (fractions summing to 1.0)
_BREAKDOWN_BY_TYPE: dict[str, dict[str, float]] = {
    "large_office":      {"hvac": 0.50, "lighting": 0.15, "equipment": 0.30, "other": 0.05},
    "medium_office":     {"hvac": 0.45, "lighting": 0.17, "equipment": 0.33, "other": 0.05},
    "small_office":      {"hvac": 0.42, "lighting": 0.18, "equipment": 0.35, "other": 0.05},
    "standalone_retail": {"hvac": 0.48, "lighting": 0.22, "equipment": 0.25, "other": 0.05},
    "primary_school":    {"hvac": 0.52, "lighting": 0.18, "equipment": 0.24, "other": 0.06},
    "hospital":          {"hvac": 0.55, "lighting": 0.12, "equipment": 0.28, "other": 0.05},
}

# Default top-level breakdown
_BREAKDOWN_DEFAULT: dict[str, float] = {"hvac": 0.50, "lighting": 0.15, "equipment": 0.30, "other": 0.05}

# HVAC sub-breakdown base (fan/pump fractions are fixed; cooling/heating vary by climate)
_HVAC_FAN_FRACTION = 0.13
_HVAC_PUMP_FRACTION = 0.07

# Peak demand factor per building type (avg demand × factor = peak demand)
_PEAK_FACTOR: dict[str, float] = {
    "large_office": 2.3,
    "medium_office": 2.5,
    "small_office": 2.8,
    "standalone_retail": 2.6,
    "primary_school": 3.3,
    "hospital": 1.8,
}

# Summer peak months by climate (month with highest cooling load)
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


def generate_mock_result(
    building_type: str,
    climate_city: str,
    strategy: str,
    total_floor_area_m2: float,
) -> dict:
    """Generate realistic mock energy simulation results.

    Returns dict compatible with EnergyResult model fields.
    Uses deterministic noise based on building characteristics so all
    strategies for the same building get consistent baseline values.
    """
    base_eui = _BASE_EUI.get(building_type, 180.0)
    climate_factor = _CLIMATE_FACTOR.get(climate_city, 1.0)
    savings_info = _STRATEGY_SAVINGS.get(strategy, {"savings_pct": 0.0})

    # Deterministic noise based on building characteristics (not strategy)
    # so all strategies for the same building use the same baseline noise
    seed_str = f"{building_type}:{climate_city}:{total_floor_area_m2}"
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    noise = 1.0 + rng.uniform(-0.03, 0.03)

    # Calculate EUI
    baseline_eui = base_eui * climate_factor * noise
    savings_pct = savings_info["savings_pct"]
    strategy_eui = baseline_eui * (1 - savings_pct / 100)

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
    baseline_total = baseline_eui * total_floor_area_m2
    savings_kwh = baseline_total - total_energy if strategy != "baseline" else None
    annual_savings = int(savings_kwh * _KRW_PER_KWH) if savings_kwh else None

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
        "savings_kwh": round(savings_kwh, 1) if savings_kwh else None,
        "savings_pct": round(savings_pct, 1) if strategy != "baseline" else None,
        "annual_cost_krw": annual_cost,
        "annual_savings_krw": annual_savings,
    }
