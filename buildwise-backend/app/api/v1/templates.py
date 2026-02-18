"""Building template routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.api import BuildingTemplateResponse

router = APIRouter()

# ---------------------------------------------------------------------------
# Static template definitions (from energyplus_sim configs)
# ---------------------------------------------------------------------------
_TEMPLATES: dict[str, dict] = {
    "large_office": {
        "building_type": "large_office",
        "name": "Large Office",
        "description": "46,320m^2, 12-story office building. VAV + Chiller/Boiler system.",
        "default_bps": {
            "location": {"city": "Seoul"},
            "geometry": {
                "building_type": "large_office",
                "num_floors_above": 12,
                "num_floors_below": 1,
                "total_floor_area_m2": 46320,
                "floor_to_floor_height_m": 3.96,
                "aspect_ratio": 1.5,
                "footprint_shape": "rectangle",
                "wwr": 0.38,
                "orientation_deg": 0,
            },
            "envelope": {
                "wall_type": "curtain_wall",
                "window_type": "double_low_e",
                "window_shgc": 0.25,
                "infiltration_ach": 0.5,
            },
            "hvac": {
                "system_type": "vav_chiller_boiler",
                "autosize": True,
                "chillers": {"count": 3, "cop": 6.1},
                "boilers": {"count": 2, "efficiency": 0.80},
                "ahu": {"count": 3, "has_economizer": True},
                "vav_terminals": {"reheat_type": "hot_water", "min_airflow_ratio": 0.30},
            },
            "internal_loads": {"people_density": 0.0565, "lighting_power_density": 10.76, "equipment_power_density": 10.76},
            "schedules": {"occupancy_type": "office_standard"},
            "setpoints": {"cooling_occupied": 24.0, "heating_occupied": 20.0},
            "simulation": {"period": "1year", "timestep": 4},
        },
        "baseline_eui_kwh_m2": 215.0,
        "available_strategies": ["baseline", "m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"],
    },
    "medium_office": {
        "building_type": "medium_office",
        "name": "Medium Office",
        "description": "4,982m^2, 3-story office building. VRF 3-pipe heat recovery system.",
        "default_bps": {
            "location": {"city": "Seoul"},
            "geometry": {
                "building_type": "medium_office",
                "num_floors_above": 3,
                "num_floors_below": 0,
                "total_floor_area_m2": 4982,
                "floor_to_floor_height_m": 3.96,
                "aspect_ratio": 1.5,
                "footprint_shape": "rectangle",
                "wwr": 0.33,
                "orientation_deg": 0,
            },
            "envelope": {
                "wall_type": "curtain_wall",
                "window_type": "double_low_e",
                "window_shgc": 0.25,
                "infiltration_ach": 0.5,
            },
            "hvac": {
                "system_type": "vrf",
                "autosize": True,
                "vrf_outdoor_units": {"count": 3, "cop_cooling": 4.0, "cop_heating": 3.5, "heat_recovery": True},
            },
            "internal_loads": {"people_density": 0.0565, "lighting_power_density": 10.76, "equipment_power_density": 10.76},
            "schedules": {"occupancy_type": "office_standard"},
            "setpoints": {"cooling_occupied": 24.0, "heating_occupied": 20.0},
            "simulation": {"period": "1year", "timestep": 4},
        },
        "baseline_eui_kwh_m2": 145.0,
        "available_strategies": ["baseline", "m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"],
    },
    "small_office": {
        "building_type": "small_office",
        "name": "Small Office",
        "description": "511m^2, 1-story office building. PSZ-HP packaged system.",
        "default_bps": {
            "location": {"city": "Seoul"},
            "geometry": {
                "building_type": "small_office",
                "num_floors_above": 1,
                "num_floors_below": 0,
                "total_floor_area_m2": 511,
                "floor_to_floor_height_m": 3.05,
                "aspect_ratio": 1.5,
                "footprint_shape": "rectangle",
                "wwr": 0.21,
                "orientation_deg": 0,
            },
            "envelope": {
                "wall_type": "wood_frame",
                "window_type": "double_clear",
                "window_shgc": 0.39,
                "infiltration_ach": 0.5,
            },
            "hvac": {
                "system_type": "psz_hp",
                "autosize": True,
                "psz_units": {"count": 5, "cop_cooling": 3.67, "cop_heating": 3.2, "has_economizer": True},
            },
            "internal_loads": {"people_density": 0.0565, "lighting_power_density": 10.76, "equipment_power_density": 10.76},
            "schedules": {"occupancy_type": "office_standard"},
            "setpoints": {"cooling_occupied": 24.0, "heating_occupied": 20.0},
            "simulation": {"period": "1year", "timestep": 4},
        },
        "baseline_eui_kwh_m2": 120.0,
        "available_strategies": ["baseline", "m0", "m1", "m2", "m3", "m4", "m5"],
    },
    "standalone_retail": {
        "building_type": "standalone_retail",
        "name": "Standalone Retail",
        "description": "2,294m^2, 1-story retail building. PSZ-AC packaged system.",
        "default_bps": {
            "location": {"city": "Seoul"},
            "geometry": {
                "building_type": "standalone_retail",
                "num_floors_above": 1,
                "num_floors_below": 0,
                "total_floor_area_m2": 2294,
                "floor_to_floor_height_m": 6.1,
                "aspect_ratio": 1.28,
                "footprint_shape": "rectangle",
                "wwr": 0.07,
                "orientation_deg": 0,
            },
            "envelope": {
                "wall_type": "metal_panel",
                "window_type": "double_clear",
                "window_shgc": 0.39,
                "infiltration_ach": 0.5,
            },
            "hvac": {
                "system_type": "psz_ac",
                "autosize": True,
                "psz_units": {"count": 4, "cop_cooling": 3.67, "cop_heating": 3.2, "has_economizer": True},
            },
            "internal_loads": {"people_density": 0.15, "lighting_power_density": 15.07, "equipment_power_density": 3.23},
            "schedules": {"occupancy_type": "retail"},
            "setpoints": {"cooling_occupied": 24.0, "heating_occupied": 21.0},
            "simulation": {"period": "1year", "timestep": 4},
        },
        "baseline_eui_kwh_m2": 180.0,
        "available_strategies": ["baseline", "m0", "m1", "m2", "m3", "m4", "m5"],
    },
    "primary_school": {
        "building_type": "primary_school",
        "name": "Primary School",
        "description": "6,871m^2, 1-story school building. VAV + Chiller/Boiler system.",
        "default_bps": {
            "location": {"city": "Seoul"},
            "geometry": {
                "building_type": "primary_school",
                "num_floors_above": 1,
                "num_floors_below": 0,
                "total_floor_area_m2": 6871,
                "floor_to_floor_height_m": 4.0,
                "aspect_ratio": 1.0,
                "footprint_shape": "U",
                "wwr": 0.35,
                "orientation_deg": 0,
            },
            "envelope": {
                "wall_type": "masonry",
                "window_type": "double_low_e",
                "window_shgc": 0.25,
                "infiltration_ach": 0.5,
            },
            "hvac": {
                "system_type": "vav_chiller_boiler_school",
                "autosize": True,
                "chillers": {"count": 1, "cop": 5.5},
                "boilers": {"count": 2, "efficiency": 0.80},
                "ahu": {"count": 2, "has_economizer": True},
                "vav_terminals": {"reheat_type": "hot_water", "min_airflow_ratio": 0.30},
            },
            "internal_loads": {"people_density": 0.25, "lighting_power_density": 12.92, "equipment_power_density": 5.38},
            "schedules": {"occupancy_type": "school"},
            "setpoints": {"cooling_occupied": 24.0, "heating_occupied": 21.0},
            "simulation": {"period": "1year", "timestep": 4},
        },
        "baseline_eui_kwh_m2": 160.0,
        "available_strategies": ["baseline", "m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"],
    },
    "hospital": {
        "building_type": "hospital",
        "name": "Hospital",
        "description": "22,422m^2, 5-story hospital. VAV + Chiller/Boiler system. Phase 2.",
        "default_bps": {
            "location": {"city": "Seoul"},
            "geometry": {
                "building_type": "hospital",
                "num_floors_above": 5,
                "num_floors_below": 1,
                "total_floor_area_m2": 22422,
                "floor_to_floor_height_m": 3.96,
                "aspect_ratio": 1.33,
                "footprint_shape": "H",
                "wwr": 0.27,
                "orientation_deg": 0,
            },
            "envelope": {
                "wall_type": "concrete",
                "window_type": "double_low_e",
                "window_shgc": 0.25,
                "infiltration_ach": 0.5,
            },
            "hvac": {
                "system_type": "vav_chiller_boiler",
                "autosize": True,
                "chillers": {"count": 2, "cop": 5.5},
                "boilers": {"count": 2, "efficiency": 0.80},
                "ahu": {"count": 4, "has_economizer": True},
                "vav_terminals": {"reheat_type": "hot_water", "min_airflow_ratio": 0.30},
            },
            "internal_loads": {"people_density": 0.10, "lighting_power_density": 11.84, "equipment_power_density": 16.15},
            "schedules": {"occupancy_type": "hospital_24h"},
            "setpoints": {"cooling_occupied": 24.0, "heating_occupied": 21.0},
            "simulation": {"period": "1year", "timestep": 4},
        },
        "baseline_eui_kwh_m2": 280.0,
        "available_strategies": ["baseline", "m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"],
    },
}


@router.get("", response_model=list[BuildingTemplateResponse])
async def list_templates() -> list[dict]:
    """GET /buildings/templates - 건물 유형 템플릿 목록."""
    return list(_TEMPLATES.values())


@router.get("/{building_type}", response_model=BuildingTemplateResponse)
async def get_template(building_type: str) -> dict:
    """GET /buildings/templates/{building_type} - 특정 건물 유형 템플릿."""
    template = _TEMPLATES.get(building_type)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown building type: {building_type}",
        )
    return template
