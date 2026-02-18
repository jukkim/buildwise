"""BPS validation service."""

from __future__ import annotations

from app.schemas.bps import BPS

# HVAC ↔ Building type compatibility matrix
_HVAC_BUILDING_MATRIX: dict[str, list[str]] = {
    "vav_chiller_boiler": ["large_office"],
    "vrf": ["medium_office"],
    "psz_hp": ["small_office"],
    "psz_ac": ["standalone_retail"],
    "vav_chiller_boiler_school": ["primary_school"],
}

# Strategy ↔ HVAC applicability
_STRATEGY_HVAC: dict[str, list[str]] = {
    "baseline": ["vav_chiller_boiler", "vrf", "psz_hp", "psz_ac", "vav_chiller_boiler_school"],
    "m0": ["vav_chiller_boiler", "vrf", "psz_hp", "psz_ac", "vav_chiller_boiler_school"],
    "m1": ["vav_chiller_boiler", "vrf", "psz_hp", "psz_ac", "vav_chiller_boiler_school"],
    "m2": ["vav_chiller_boiler", "vrf", "psz_hp", "psz_ac", "vav_chiller_boiler_school"],
    "m3": ["vav_chiller_boiler", "vrf", "psz_hp", "psz_ac", "vav_chiller_boiler_school"],
    "m4": ["vav_chiller_boiler", "vrf", "psz_hp", "psz_ac", "vav_chiller_boiler_school"],
    "m5": ["vav_chiller_boiler", "vrf", "psz_hp", "psz_ac", "vav_chiller_boiler_school"],
    "m6": ["vav_chiller_boiler", "vav_chiller_boiler_school"],  # chiller staging
    "m7": ["vav_chiller_boiler", "vrf", "vav_chiller_boiler_school"],
    "m8": ["vav_chiller_boiler", "vrf", "vav_chiller_boiler_school"],
}


class BPSValidationError(Exception):
    """Raised when BPS fails domain validation."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"BPS validation failed: {'; '.join(errors)}")


def validate_bps(bps: BPS) -> list[str]:
    """Validate BPS beyond Pydantic type checks. Returns list of error messages."""
    errors: list[str] = []

    # 1. HVAC ↔ building type compatibility
    building_type = bps.geometry.building_type
    hvac_type = bps.hvac.system_type
    allowed_buildings = _HVAC_BUILDING_MATRIX.get(hvac_type, [])
    if building_type not in allowed_buildings:
        errors.append(
            f"HVAC '{hvac_type}' is not compatible with building type '{building_type}'. "
            f"Allowed: {allowed_buildings}"
        )

    # 2. Conditioned area <= total area
    if bps.geometry.conditioned_floor_area_m2 is not None:
        if bps.geometry.conditioned_floor_area_m2 > bps.geometry.total_floor_area_m2:
            errors.append("conditioned_floor_area_m2 cannot exceed total_floor_area_m2")

    # 3. Heating setpoint < Cooling setpoint
    if bps.setpoints.heating_occupied >= bps.setpoints.cooling_occupied:
        errors.append(
            f"heating_occupied ({bps.setpoints.heating_occupied}) "
            f"must be less than cooling_occupied ({bps.setpoints.cooling_occupied})"
        )

    # 4. Strategy applicability
    if bps.simulation.strategies:
        for strat in bps.simulation.strategies:
            allowed_hvac = _STRATEGY_HVAC.get(strat, [])
            if hvac_type not in allowed_hvac:
                errors.append(f"Strategy '{strat}' not applicable to HVAC type '{hvac_type}'")

    # 5. HVAC sub-specs presence
    if hvac_type in ("vav_chiller_boiler", "vav_chiller_boiler_school"):
        if bps.hvac.chillers is None:
            errors.append(f"HVAC '{hvac_type}' requires chillers specification")
        if bps.hvac.boilers is None:
            errors.append(f"HVAC '{hvac_type}' requires boilers specification")
    elif hvac_type == "vrf":
        if bps.hvac.vrf_outdoor_units is None:
            errors.append("HVAC 'vrf' requires vrf_outdoor_units specification")
    elif hvac_type in ("psz_hp", "psz_ac"):
        if bps.hvac.psz_units is None:
            errors.append(f"HVAC '{hvac_type}' requires psz_units specification")

    return errors


def get_applicable_strategies(building_type: str, hvac_type: str) -> list[str]:
    """Return list of applicable strategy names for the given building/HVAC combo."""
    return [
        strat
        for strat, hvac_list in _STRATEGY_HVAC.items()
        if hvac_type in hvac_list
    ]
