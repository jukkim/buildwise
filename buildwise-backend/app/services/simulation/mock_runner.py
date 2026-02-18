"""Mock simulation runner for demo/development without EnergyPlus.

Returns pre-computed realistic energy results based on building type,
climate city, and strategy. Values derived from energyplus_sim 450+ results.
"""

from __future__ import annotations

import random

# Base EUI values per building type (kWh/m2/year) from validated simulations
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

# Strategy savings percentages (relative to baseline)
_STRATEGY_SAVINGS: dict[str, dict[str, float]] = {
    "baseline": {"savings_pct": 0.0},
    "m0": {"savings_pct": 3.2},   # Night Stop
    "m1": {"savings_pct": 4.5},   # Smart Start
    "m2": {"savings_pct": 5.8},   # Economizer
    "m3": {"savings_pct": 2.1},   # Setpoint Adjustment
    "m4": {"savings_pct": 6.3},   # Chiller Staging
    "m5": {"savings_pct": 4.0},   # Daylighting + DCV
    "m6": {"savings_pct": 7.5},   # Integrated Normal
    "m7": {"savings_pct": 12.8},  # Full Normal
    "m8": {"savings_pct": 15.2},  # Full Savings
}

# Energy breakdown ratios (fraction of total)
_BREAKDOWN: dict[str, float] = {
    "hvac": 0.45,
    "cooling": 0.22,
    "heating": 0.15,
    "fan": 0.08,
    "pump": 0.05,
    "lighting": 0.15,
    "equipment": 0.35,
}

# KRW per kWh (simplified)
_KRW_PER_KWH = 120


def generate_mock_result(
    building_type: str,
    climate_city: str,
    strategy: str,
    total_floor_area_m2: float,
) -> dict:
    """Generate realistic mock energy simulation results.

    Returns dict compatible with EnergyResult model fields.
    """
    base_eui = _BASE_EUI.get(building_type, 180.0)
    climate_factor = _CLIMATE_FACTOR.get(climate_city, 1.0)
    savings_info = _STRATEGY_SAVINGS.get(strategy, {"savings_pct": 0.0})

    # Add small random variation (±3%)
    noise = 1.0 + random.uniform(-0.03, 0.03)

    # Calculate EUI
    baseline_eui = base_eui * climate_factor * noise
    savings_pct = savings_info["savings_pct"]
    strategy_eui = baseline_eui * (1 - savings_pct / 100)

    # Total energy
    total_energy = strategy_eui * total_floor_area_m2

    # Breakdown
    hvac = total_energy * _BREAKDOWN["hvac"]
    cooling = total_energy * _BREAKDOWN["cooling"]
    heating = total_energy * _BREAKDOWN["heating"]
    fan = total_energy * _BREAKDOWN["fan"]
    pump = total_energy * _BREAKDOWN["pump"]
    lighting = total_energy * _BREAKDOWN["lighting"]
    equipment = total_energy * _BREAKDOWN["equipment"]

    # Peak demand (rough: total / 8760 * peak factor)
    peak_kw = total_energy / 8760 * 2.5

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
        "peak_demand_month": 7,  # July (summer peak)
        "savings_kwh": round(savings_kwh, 1) if savings_kwh else None,
        "savings_pct": round(savings_pct, 1) if strategy != "baseline" else None,
        "annual_cost_krw": annual_cost,
        "annual_savings_krw": annual_savings,
    }
