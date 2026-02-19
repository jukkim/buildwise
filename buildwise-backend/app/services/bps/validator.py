"""BPS validation service."""

from __future__ import annotations

from app.schemas.bps import BPS, WWRPerFacade

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

# Minimum setpoint dead band (cooling - heating must be >= this)
_MIN_DEAD_BAND_C = 2.0


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

    # 3. Heating setpoint < Cooling setpoint (occupied)
    if bps.setpoints.heating_occupied >= bps.setpoints.cooling_occupied:
        errors.append(
            f"heating_occupied ({bps.setpoints.heating_occupied}) "
            f"must be less than cooling_occupied ({bps.setpoints.cooling_occupied})"
        )

    # 4. Setpoint dead band check (occupied)
    dead_band = bps.setpoints.cooling_occupied - bps.setpoints.heating_occupied
    if 0 < dead_band < _MIN_DEAD_BAND_C:
        errors.append(
            f"Setpoint dead band ({dead_band:.1f}°C) is too small. "
            f"Minimum {_MIN_DEAD_BAND_C}°C required between heating and cooling setpoints."
        )

    # 5. Heating setpoint < Cooling setpoint (unoccupied)
    if bps.setpoints.heating_unoccupied >= bps.setpoints.cooling_unoccupied:
        errors.append(
            f"heating_unoccupied ({bps.setpoints.heating_unoccupied}) "
            f"must be less than cooling_unoccupied ({bps.setpoints.cooling_unoccupied})"
        )

    # 6. Strategy applicability
    if bps.simulation.strategies:
        for strat in bps.simulation.strategies:
            allowed_hvac = _STRATEGY_HVAC.get(strat, [])
            if hvac_type not in allowed_hvac:
                errors.append(f"Strategy '{strat}' not applicable to HVAC type '{hvac_type}'")

    # 7. HVAC sub-specs presence
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

    # 8. Floor area per floor reasonableness
    floor_area_per_floor = bps.geometry.total_floor_area_m2 / bps.geometry.num_floors_above
    if floor_area_per_floor < 20:
        errors.append(
            f"Floor area per floor ({floor_area_per_floor:.1f} m2) is unrealistically small. "
            f"Minimum 20 m2 per floor expected."
        )

    # 9. WWR per-facade validation (if dict/per-facade type)
    wwr = bps.geometry.wwr
    if isinstance(wwr, (int, float)):
        if wwr > 0.80:
            errors.append(
                f"Window-to-wall ratio ({wwr}) exceeds practical limit of 0.80. "
                f"Values above 80% are structurally impractical."
            )
    elif isinstance(wwr, WWRPerFacade):
        for direction in ("north", "south", "east", "west"):
            val = getattr(wwr, direction)
            if val > 0.80:
                errors.append(
                    f"WWR for {direction} facade ({val}) exceeds practical limit of 0.80."
                )

    # 10. Aspect ratio × floors sanity check
    if bps.geometry.aspect_ratio > 3.0 and bps.geometry.num_floors_above > 20:
        errors.append(
            f"Combination of high aspect ratio ({bps.geometry.aspect_ratio}) and many floors "
            f"({bps.geometry.num_floors_above}) may produce unrealistic building geometry."
        )

    return errors


def get_applicable_strategies(building_type: str, hvac_type: str) -> list[str]:
    """Return list of applicable strategy names for the given building/HVAC combo."""
    return [
        strat
        for strat, hvac_list in _STRATEGY_HVAC.items()
        if hvac_type in hvac_list
    ]
