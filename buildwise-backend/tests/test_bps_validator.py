"""BPS validator unit tests (no DB needed)."""

import pytest

from app.schemas.bps import (
    BPS,
    BPSHVAC,
    AHUSpec,
    BoilerSpec,
    BPSEnvelope,
    BPSGeometry,
    BPSLocation,
    BPSSetpoints,
    BPSSimulation,
    ChillerSpec,
    PSZSpec,
    VAVSpec,
    VRFOutdoorSpec,
)
from app.services.bps.validator import get_applicable_strategies, validate_bps


def _make_bps(building_type="large_office", hvac_type="vav_chiller_boiler", **kwargs) -> BPS:
    """Helper to build a valid BPS for testing."""
    hvac_kwargs: dict = {"system_type": hvac_type, "autosize": True}

    if hvac_type in ("vav_chiller_boiler", "vav_chiller_boiler_school"):
        hvac_kwargs.update(
            chillers=ChillerSpec(),
            boilers=BoilerSpec(),
            ahu=AHUSpec(),
            vav_terminals=VAVSpec(),
        )
    elif hvac_type == "vrf":
        hvac_kwargs["vrf_outdoor_units"] = VRFOutdoorSpec()
    elif hvac_type in ("psz_hp", "psz_ac"):
        hvac_kwargs["psz_units"] = PSZSpec(count=5)

    geom_kwargs = {
        "building_type": building_type,
        "num_floors_above": 12,
        "total_floor_area_m2": 46320,
    }
    if "geometry" in kwargs:
        geom_kwargs.update(kwargs.pop("geometry"))

    return BPS(
        location=BPSLocation(city="Seoul"),
        geometry=BPSGeometry(**geom_kwargs),
        envelope=kwargs.get("envelope", BPSEnvelope()),
        hvac=BPSHVAC(**hvac_kwargs),
        setpoints=kwargs.get("setpoints", BPSSetpoints()),
        simulation=kwargs.get("simulation", BPSSimulation()),
    )


class TestBasicValidation:
    """Test basic valid BPS configurations."""

    def test_valid_large_office(self):
        bps = _make_bps("large_office", "vav_chiller_boiler")
        errors = validate_bps(bps)
        assert errors == []

    def test_valid_medium_office(self):
        bps = _make_bps("medium_office", "vrf")
        errors = validate_bps(bps)
        assert errors == []

    def test_valid_small_office(self):
        bps = _make_bps("small_office", "psz_hp")
        errors = validate_bps(bps)
        assert errors == []


class TestHVACCompatibility:
    """Test HVAC ↔ building type compatibility."""

    def test_hvac_building_mismatch(self):
        bps = _make_bps("large_office", "vrf")
        errors = validate_bps(bps)
        assert any("not compatible" in e for e in errors)

    def test_missing_chiller_for_vav(self):
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

    def test_missing_vrf_outdoor_units(self):
        bps = BPS(
            location=BPSLocation(city="Seoul"),
            geometry=BPSGeometry(
                building_type="medium_office",
                num_floors_above=5,
                total_floor_area_m2=5000,
            ),
            hvac=BPSHVAC(system_type="vrf"),
        )
        errors = validate_bps(bps)
        assert any("vrf_outdoor_units" in e for e in errors)

    def test_missing_psz_units(self):
        bps = BPS(
            location=BPSLocation(city="Seoul"),
            geometry=BPSGeometry(
                building_type="small_office",
                num_floors_above=2,
                total_floor_area_m2=500,
            ),
            hvac=BPSHVAC(system_type="psz_hp"),
        )
        errors = validate_bps(bps)
        assert any("psz_units" in e for e in errors)


class TestSetpointValidation:
    """Test thermostat setpoint validation."""

    def test_heating_above_cooling(self):
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

    def test_dead_band_too_small(self):
        bps = _make_bps(
            setpoints=BPSSetpoints(
                cooling_occupied=22.0,
                heating_occupied=21.5,
                cooling_unoccupied=29.0,
                heating_unoccupied=15.0,
            )
        )
        errors = validate_bps(bps)
        assert any("dead band" in e for e in errors)

    def test_dead_band_exactly_2_is_valid(self):
        bps = _make_bps(
            setpoints=BPSSetpoints(
                cooling_occupied=24.0,
                heating_occupied=22.0,
                cooling_unoccupied=29.0,
                heating_unoccupied=15.0,
            )
        )
        errors = validate_bps(bps)
        assert not any("dead band" in e for e in errors)

    def test_unoccupied_heating_above_cooling(self):
        bps = _make_bps(
            setpoints=BPSSetpoints(
                cooling_occupied=24.0,
                heating_occupied=20.0,
                cooling_unoccupied=25.0,
                heating_unoccupied=19.0,
            )
        )
        errors = validate_bps(bps)
        # 25 > 19 → valid
        assert not any("unoccupied" in e for e in errors)

    def test_unoccupied_setpoint_overlap_blocked_by_pydantic(self):
        """Pydantic schema enforces heating_unoccupied <= 20, so overlap is impossible."""
        with pytest.raises(Exception):
            BPSSetpoints(
                cooling_occupied=24.0,
                heating_occupied=20.0,
                cooling_unoccupied=25.0,
                heating_unoccupied=26.0,
            )


class TestGeometryValidation:
    """Test geometry constraint validation."""

    def test_conditioned_area_exceeds_total(self):
        bps = _make_bps(geometry={"conditioned_floor_area_m2": 50000})
        errors = validate_bps(bps)
        assert any("conditioned_floor_area_m2" in e for e in errors)

    def test_conditioned_area_within_total(self):
        bps = _make_bps(geometry={"conditioned_floor_area_m2": 40000})
        errors = validate_bps(bps)
        assert not any("conditioned_floor_area_m2" in e for e in errors)

    def test_tiny_floor_area_per_floor(self):
        bps = _make_bps(geometry={"total_floor_area_m2": 100, "num_floors_above": 10})
        errors = validate_bps(bps)
        assert any("Floor area per floor" in e for e in errors)

    def test_reasonable_floor_area(self):
        bps = _make_bps()  # 46320 / 12 = 3860 m2/floor
        errors = validate_bps(bps)
        assert not any("Floor area per floor" in e for e in errors)

    def test_high_aspect_ratio_many_floors_warning(self):
        bps = _make_bps(
            geometry={
                "aspect_ratio": 4.0,
                "num_floors_above": 30,
                "total_floor_area_m2": 200000,
            }
        )
        errors = validate_bps(bps)
        assert any("aspect ratio" in e for e in errors)

    def test_high_wwr_warning(self):
        bps = _make_bps(geometry={"wwr": 0.85})
        errors = validate_bps(bps)
        assert any("Window-to-wall ratio" in e for e in errors)

    def test_normal_wwr_no_warning(self):
        bps = _make_bps(geometry={"wwr": 0.40})
        errors = validate_bps(bps)
        assert not any("Window-to-wall ratio" in e for e in errors)


class TestStrategyApplicability:
    """Test strategy ↔ HVAC filtering."""

    def test_vav_gets_all_strategies(self):
        strategies = get_applicable_strategies("large_office", "vav_chiller_boiler")
        assert "baseline" in strategies
        assert "m6" in strategies
        assert "m8" in strategies

    def test_psz_excludes_staging(self):
        strategies = get_applicable_strategies("small_office", "psz_hp")
        assert "m6" not in strategies
        assert "m7" not in strategies
        assert "baseline" in strategies

    def test_vrf_includes_m7_m8(self):
        strategies = get_applicable_strategies("medium_office", "vrf")
        assert "m7" in strategies
        assert "m8" in strategies
        assert "m6" not in strategies

    def test_strategy_validation_in_bps(self):
        """M6 on PSZ should fail validation."""
        bps = _make_bps("small_office", "psz_hp", simulation=BPSSimulation(strategies=["baseline", "m6"]))
        errors = validate_bps(bps)
        assert any("m6" in e and "not applicable" in e for e in errors)
