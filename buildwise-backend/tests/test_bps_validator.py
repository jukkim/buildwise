"""BPS validator unit tests (no DB needed)."""

import pytest

from app.schemas.bps import (
    BPS,
    BPSEnvelope,
    BPSGeometry,
    BPSHVAC,
    BPSLocation,
    BPSSetpoints,
    ChillerSpec,
    BoilerSpec,
    AHUSpec,
    VAVSpec,
    VRFOutdoorSpec,
    PSZSpec,
)
from app.services.bps.validator import get_applicable_strategies, validate_bps


def _make_bps(building_type="large_office", hvac_type="vav_chiller_boiler", **kwargs) -> BPS:
    """Helper to build a valid BPS for testing."""
    hvac_kwargs: dict = {"system_type": hvac_type, "autosize": True}

    if hvac_type in ("vav_chiller_boiler", "vav_chiller_boiler_school"):
        hvac_kwargs.update(
            chillers=ChillerSpec(), boilers=BoilerSpec(),
            ahu=AHUSpec(), vav_terminals=VAVSpec(),
        )
    elif hvac_type == "vrf":
        hvac_kwargs["vrf_outdoor_units"] = VRFOutdoorSpec()
    elif hvac_type in ("psz_hp", "psz_ac"):
        hvac_kwargs["psz_units"] = PSZSpec(count=5)

    return BPS(
        location=BPSLocation(city="Seoul"),
        geometry=BPSGeometry(
            building_type=building_type,
            num_floors_above=12,
            total_floor_area_m2=46320,
        ),
        envelope=BPSEnvelope(),
        hvac=BPSHVAC(**hvac_kwargs),
        setpoints=kwargs.get("setpoints", BPSSetpoints()),
    )


def test_valid_large_office():
    bps = _make_bps("large_office", "vav_chiller_boiler")
    errors = validate_bps(bps)
    assert errors == []


def test_valid_medium_office():
    bps = _make_bps("medium_office", "vrf")
    errors = validate_bps(bps)
    assert errors == []


def test_valid_small_office():
    bps = _make_bps("small_office", "psz_hp")
    errors = validate_bps(bps)
    assert errors == []


def test_hvac_building_mismatch():
    bps = _make_bps("large_office", "vrf")
    errors = validate_bps(bps)
    assert any("not compatible" in e for e in errors)


def test_heating_above_cooling():
    bps = _make_bps(
        setpoints=BPSSetpoints(
            cooling_occupied=20.0,
            heating_occupied=24.0,
            cooling_unoccupied=29.0,
            heating_unoccupied=15.0,
        )
    )
    errors = validate_bps(bps)
    assert any("heating_occupied" in e and "cooling_occupied" in e for e in errors)


def test_missing_chiller_for_vav():
    bps = BPS(
        location=BPSLocation(city="Seoul"),
        geometry=BPSGeometry(
            building_type="large_office",
            num_floors_above=12,
            total_floor_area_m2=46320,
        ),
        hvac=BPSHVAC(system_type="vav_chiller_boiler"),
    )
    errors = validate_bps(bps)
    assert any("chillers" in e for e in errors)
    assert any("boilers" in e for e in errors)


def test_strategy_applicability():
    strategies = get_applicable_strategies("large_office", "vav_chiller_boiler")
    assert "baseline" in strategies
    assert "m6" in strategies  # chiller staging
    assert "m8" in strategies


def test_strategy_not_applicable_psz():
    strategies = get_applicable_strategies("small_office", "psz_hp")
    assert "m6" not in strategies  # chiller staging not for PSZ
    assert "m7" not in strategies
    assert "baseline" in strategies
