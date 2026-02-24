"""Building reference data from DOE Reference Buildings (Korean climate).

Source: ems_simulation/buildings/*/results/default/*/1year/baseline/eplustbl.csv
        ems_simulation/config/building_specific/*.yaml

This module provides validated reference data for BuildWise building types.
Used by: mock_runner (EUI reference), validator (HVAC checks), IDF generator.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HVACSpec:
    system_type: str
    chillers: int = 0
    chiller_capacity_kw: float = 0
    chiller_cop: float = 0
    boilers: int = 0
    boiler_capacity_kw: float = 0
    boiler_efficiency: float = 0
    vrf_outdoor_units: int = 0
    vrf_cop_cooling: float = 0
    psz_units: int = 0


@dataclass(frozen=True)
class BuildingReference:
    name: str
    building_type: str
    floor_area_m2: float
    stories: int
    aspect_ratio: float
    floor_height_m: float
    wwr: float
    zone_count: int
    baseline_eui: float  # kWh/m2/year (total building)
    hvac_eui: float  # kWh/m2/year (HVAC only)
    hvac: HVACSpec = field(default_factory=lambda: HVACSpec(system_type="unknown"))
    applicable_strategies: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Building Reference Database
# ---------------------------------------------------------------------------

BUILDINGS: dict[str, BuildingReference] = {
    "large_office": BuildingReference(
        name="DOE Reference Large Office",
        building_type="large_office",
        floor_area_m2=46320,
        stories=12,
        aspect_ratio=1.5,
        floor_height_m=3.96,
        wwr=0.38,
        zone_count=16,
        baseline_eui=120.1,  # eplustbl 10-city avg
        hvac_eui=33.6,  # 120.1 × 0.28 (HVAC fraction from eplustbl)
        hvac=HVACSpec(
            system_type="vav_chiller_boiler",
            chillers=3,
            chiller_capacity_kw=2110,
            chiller_cop=6.1,
            boilers=2,
            boiler_capacity_kw=1200,
            boiler_efficiency=0.80,
        ),
        applicable_strategies=[
            "baseline",
            "m0",
            "m1",
            "m2",
            "m3",
            "m4",
            "m5",
            "m6",
            "m7",
            "m8",
        ],
    ),
    "medium_office": BuildingReference(
        name="Korean Standard Medium Office",
        building_type="medium_office",
        floor_area_m2=4982,
        stories=3,
        aspect_ratio=1.5,
        floor_height_m=3.35,
        wwr=0.33,
        zone_count=15,
        baseline_eui=77.8,  # eplustbl 10-city avg
        hvac_eui=35.0,  # 77.8 × 0.45 (HVAC fraction from eplustbl)
        hvac=HVACSpec(
            system_type="vrf",
            vrf_outdoor_units=3,
            vrf_cop_cooling=4.5,
        ),
        applicable_strategies=[
            "baseline",
            "m0",
            "m1",
            "m4",
            "m5",
            "m7",
            "m8",
        ],
    ),
    "small_office": BuildingReference(
        name="DOE Reference Small Office",
        building_type="small_office",
        floor_area_m2=511,
        stories=1,
        aspect_ratio=1.5,
        floor_height_m=3.05,
        wwr=0.24,
        zone_count=5,
        baseline_eui=97.8,  # eplustbl 10-city avg
        hvac_eui=27.4,  # 97.8 × 0.28 (HVAC fraction from eplustbl)
        hvac=HVACSpec(
            system_type="psz_hp",
            psz_units=5,
        ),
        applicable_strategies=[
            "baseline",
            "m0",
            "m1",
            "m2",
            "m4",
            "m5",
            "m7",
            "m8",
        ],
    ),
    "standalone_retail": BuildingReference(
        name="DOE Reference Standalone Retail",
        building_type="standalone_retail",
        floor_area_m2=2294,
        stories=1,
        aspect_ratio=1.28,
        floor_height_m=6.1,
        wwr=0.07,
        zone_count=4,
        baseline_eui=125.6,  # eplustbl 10-city avg
        hvac_eui=46.5,  # 125.6 × 0.37 (HVAC fraction from eplustbl)
        hvac=HVACSpec(
            system_type="psz_ac",
            psz_units=4,
        ),
        applicable_strategies=[
            "baseline",
            "m0",
            "m1",
            "m2",
            "m4",
            "m5",
            "m7",
            "m8",
        ],
    ),
    "primary_school": BuildingReference(
        name="DOE Reference Primary School",
        building_type="primary_school",
        floor_area_m2=6871,
        stories=1,
        aspect_ratio=1.77,
        floor_height_m=3.96,
        wwr=0.35,
        zone_count=25,
        baseline_eui=139.5,  # eplustbl 10-city avg
        hvac_eui=54.4,  # 139.5 × 0.39 (HVAC fraction from eplustbl)
        hvac=HVACSpec(
            system_type="vav_chiller_boiler_school",
            chillers=1,
            chiller_capacity_kw=530,
            chiller_cop=5.5,
            boilers=1,
            boiler_capacity_kw=670,
            boiler_efficiency=0.80,
        ),
        applicable_strategies=[
            "baseline",
            "m0",
            "m1",
            "m2",
            "m3",
            "m4",
            "m5",
            "m6",
            "m7",
            "m8",
        ],
    ),
}


def get_building_reference(building_type: str) -> BuildingReference | None:
    """Get reference data for a building type."""
    return BUILDINGS.get(building_type)


def get_all_building_types() -> list[str]:
    """Get list of all supported building types."""
    return list(BUILDINGS.keys())
