"""BPS (Building Parameter Schema) Pydantic models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Sub-schemas
# ---------------------------------------------------------------------------


class BPSLocation(BaseModel):
    city: Literal[
        "Seoul",
        "Busan",
        "Daegu",
        "Daejeon",
        "Gwangju",
        "Incheon",
        "Gangneung",
        "Jeju",
        "Cheongju",
        "Ulsan",
    ]
    district: str | None = None
    latitude: float | None = Field(None, ge=33.0, le=39.0)
    longitude: float | None = Field(None, ge=124.0, le=132.0)
    climate_zone: Literal["3A", "4A", "5A"] | None = None
    epw_file: str | None = None


class WWRPerFacade(BaseModel):
    north: float = Field(ge=0.0, le=0.95)
    south: float = Field(ge=0.0, le=0.95)
    east: float = Field(ge=0.0, le=0.95)
    west: float = Field(ge=0.0, le=0.95)


class BPSGeometry(BaseModel):
    building_type: Literal[
        "large_office",
        "medium_office",
        "small_office",
        "standalone_retail",
        "primary_school",
        "hospital",
    ]
    num_floors_above: int = Field(ge=1, le=100)
    num_floors_below: int = Field(0, ge=0, le=10)
    total_floor_area_m2: float = Field(ge=100, le=500000)
    conditioned_floor_area_m2: float | None = None
    floor_to_floor_height_m: float = Field(3.96, ge=2.5, le=10.0)
    aspect_ratio: float = Field(1.5, ge=0.5, le=5.0)
    footprint_shape: Literal["rectangle", "L", "U", "T", "H"] = "rectangle"
    wwr: float | WWRPerFacade = 0.38
    orientation_deg: float = Field(0, ge=0, le=360)


class BPSEnvelope(BaseModel):
    wall_type: Literal["curtain_wall", "masonry", "metal_panel", "concrete", "wood_frame"] = "curtain_wall"
    wall_u_value: float | None = Field(None, ge=0.1, le=5.0)
    roof_u_value: float | None = Field(None, ge=0.1, le=3.0)
    floor_u_value: float | None = Field(None, ge=0.1, le=3.0)
    window_type: Literal["single_clear", "double_clear", "double_low_e", "triple_low_e"] = "double_low_e"
    window_u_value: float | None = Field(None, ge=0.5, le=6.0)
    window_shgc: float = Field(0.25, ge=0.1, le=0.9)
    infiltration_ach: float = Field(0.5, ge=0.0, le=2.0)


class BPSZone(BaseModel):
    name: str
    floor: int = Field(ge=-10, le=100)
    area_m2: float | None = Field(None, ge=1)
    usage: Literal[
        "office",
        "lobby",
        "conference",
        "restroom",
        "storage",
        "mechanical",
        "parking",
        "retail",
        "classroom",
        "corridor",
        "cafeteria",
        "data_center",
        "kitchen",
        "patient_room",
        "operating_room",
    ] = "office"
    occupancy_density: float | None = Field(None, ge=0.0, le=1.0)
    has_data_center: bool = False


class ChillerSpec(BaseModel):
    count: int = Field(2, ge=1, le=10)
    capacity_kw: float | None = None
    cop: float = Field(6.1, ge=2.0, le=10.0)


class BoilerSpec(BaseModel):
    count: int = Field(2, ge=1, le=10)
    capacity_kw: float | None = None
    efficiency: float = Field(0.8125, ge=0.5, le=1.0)


class AHUSpec(BaseModel):
    count: int = Field(2, ge=1, le=10)
    supply_fan_power_kw: float | None = None
    has_economizer: bool = True
    economizer_type: Literal["DifferentialEnthalpy", "DifferentialDryBulb", "FixedEnthalpy"] = "DifferentialEnthalpy"


class VAVSpec(BaseModel):
    reheat_type: Literal["hot_water", "electric", "none"] = "hot_water"
    min_airflow_ratio: float = Field(0.30, ge=0.1, le=0.5)


class VRFOutdoorSpec(BaseModel):
    count: int = Field(3, ge=1, le=20)
    capacity_cooling_kw: float | None = None
    capacity_heating_kw: float | None = None
    cop_cooling: float = Field(4.0, ge=2.0, le=10.0)
    cop_heating: float = Field(3.5, ge=2.0, le=8.0)
    heat_recovery: bool = True


class PSZSpec(BaseModel):
    count: int = Field(ge=1, le=20)
    capacity_cooling_kw: float | None = None
    capacity_heating_kw: float | None = None
    cop_cooling: float = Field(3.67)
    cop_heating: float = Field(3.2)
    has_economizer: bool = True


class BPSHVAC(BaseModel):
    system_type: Literal["vav_chiller_boiler", "vrf", "psz_hp", "psz_ac", "vav_chiller_boiler_school"]
    autosize: bool = True
    # VAV + Chiller/Boiler
    chillers: ChillerSpec | None = None
    boilers: BoilerSpec | None = None
    ahu: AHUSpec | None = None
    vav_terminals: VAVSpec | None = None
    # VRF
    vrf_outdoor_units: VRFOutdoorSpec | None = None
    # PSZ
    psz_units: PSZSpec | None = None


class BPSInternalLoads(BaseModel):
    people_density: float = Field(0.0565, ge=0.0, le=1.0)
    lighting_power_density: float = Field(10.76, ge=0.0, le=50.0)
    equipment_power_density: float = Field(10.76, ge=0.0, le=100.0)
    has_data_center: bool = False
    data_center_load_factor: float = Field(0.01, ge=0.0, le=1.0)


class BPSOperatingHours(BaseModel):
    start: str = Field("08:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    end: str = Field("18:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")


class BPSSchedules(BaseModel):
    occupancy_type: Literal["office_standard", "school", "retail", "hospital_24h"] = "office_standard"
    workdays: list[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]] = ["mon", "tue", "wed", "thu", "fri"]
    saturday: Literal["full_day", "half_day", "off"] = "half_day"
    operating_hours: BPSOperatingHours = BPSOperatingHours()
    holidays: Literal["KR_standard", "none", "custom"] = "KR_standard"


class BPSSetpoints(BaseModel):
    cooling_occupied: float = Field(24.0, ge=18.0, le=30.0)
    heating_occupied: float = Field(20.0, ge=15.0, le=25.0)
    cooling_unoccupied: float = Field(29.0, ge=25.0, le=35.0)
    heating_unoccupied: float = Field(15.6, ge=10.0, le=20.0)


class BPSSimulation(BaseModel):
    period: Literal["1year", "1month_summer", "1month_winter", "custom"] = "1year"
    timestep: Literal[1, 2, 4, 6] = 4
    strategies: list[Literal["baseline", "m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"]] | None = (
        None  # None = 건물유형에 따라 자동 결정
    )


# ---------------------------------------------------------------------------
# Top-level BPS
# ---------------------------------------------------------------------------


class BPS(BaseModel):
    """Building Parameter Schema - 전체 시스템의 SSOT."""

    location: BPSLocation
    geometry: BPSGeometry
    envelope: BPSEnvelope = BPSEnvelope()
    zones: list[BPSZone] | None = None
    hvac: BPSHVAC
    internal_loads: BPSInternalLoads = BPSInternalLoads()
    schedules: BPSSchedules = BPSSchedules()
    setpoints: BPSSetpoints = BPSSetpoints()
    simulation: BPSSimulation = BPSSimulation()


class BPSPatch(BaseModel):
    """BPS 부분 수정용."""

    location: BPSLocation | None = None
    geometry: BPSGeometry | None = None
    envelope: BPSEnvelope | None = None
    zones: list[BPSZone] | None = None
    hvac: BPSHVAC | None = None
    internal_loads: BPSInternalLoads | None = None
    schedules: BPSSchedules | None = None
    setpoints: BPSSetpoints | None = None
    simulation: BPSSimulation | None = None
