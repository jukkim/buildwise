"""IDF generation pipeline: BPS + strategy → EnergyPlus IDF file.

Pipeline stages:
1. Header + simulation control
2. GlobalGeometryRules
3. DesignDay objects (summer/winter sizing)
4. Building + Zone geometry
5. Surface geometry (walls, floors, roofs, windows)
6. Materials + Constructions
7. Envelope (glazing)
8. Schedules (occupancy, lighting, equipment, setpoints)
9. Internal loads (People, Lights, Equipment)
10. Infiltration
11. HVAC (IdealLoadsAirSystem)
12. EMS strategy injection (Jinja2 templates)
13. Output variables
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from jinja2.sandbox import SandboxedEnvironment
from jinja2 import FileSystemLoader

logger = logging.getLogger(__name__)

# Regex to strip IDF-special characters from field values
_IDF_UNSAFE_RE = re.compile(r"[,;!\n\r]")


def sanitize_idf_field(value: str) -> str:
    """Remove IDF metacharacters (comma, semicolon, comment, newlines) from a field value."""
    return _IDF_UNSAFE_RE.sub("", str(value)).strip()

# Strategy → EMS template mapping per building type
# Source: docs/strategy-naming-reconciliation.md section 3.2 (APPROVED)
STRATEGY_TEMPLATE_MAP: dict[str, dict[str, list[str]]] = {
    "baseline": {},
    "m0": {  # 야간 정지
        "large_office": ["m2_night_ventilation.j2", "occupancy_control.j2"],
        "medium_office": ["vrf_night_setback.j2"],
        "small_office": ["occupancy_control.j2"],
        "standalone_retail": ["occupancy_control.j2"],
        "primary_school": ["m2_night_ventilation.j2", "occupancy_control.j2"],
    },
    "m1": {  # 스마트 시작
        "large_office": ["optimal_start.j2"],
        "medium_office": ["optimal_start_vrf_v2.j2"],
        "small_office": ["optimal_start_stop.j2"],
        "standalone_retail": ["optimal_start_stop.j2"],
        "primary_school": ["optimal_start.j2"],
    },
    "m2": {  # 외기 냉방
        "large_office": ["enthalpy_economizer.j2"],
        "small_office": ["enthalpy_economizer.j2"],
        "standalone_retail": ["enthalpy_economizer.j2"],
        "primary_school": ["enthalpy_economizer.j2"],
    },
    "m3": {  # 냉동기 단계제어
        "large_office": ["staging_control.j2"],
        "primary_school": ["staging_control.j2"],
    },
    "m4": {  # 쾌적 최적화 (보통, PMV 0.5)
        "*": ["m4_peak_limiting.j2", "setpoint_adjustment.j2"],
    },
    "m5": {  # 쾌적 최적화 (절약, PMV 0.7)
        "*": ["m4_peak_limiting.j2", "setpoint_adjustment.j2"],
    },
    "m6": {  # 설비 통합제어 (M2+M3)
        "large_office": ["enthalpy_economizer.j2", "staging_control.j2"],
        "primary_school": ["enthalpy_economizer.j2", "staging_control.j2"],
    },
    "m7": {  # 통합+쾌적(보통) (M6+M4)
        "large_office": ["enthalpy_economizer.j2", "staging_control.j2", "m4_peak_limiting.j2", "setpoint_adjustment.j2"],
        "medium_office": ["vrf_full_control.j2", "setpoint_adjustment.j2"],
        "small_office": ["optimal_start_stop.j2", "setpoint_adjustment.j2"],
        "standalone_retail": ["optimal_start_stop.j2", "m4_peak_limiting.j2", "setpoint_adjustment.j2"],
        "primary_school": ["enthalpy_economizer.j2", "staging_control.j2", "setpoint_adjustment.j2"],
    },
    "m8": {  # 통합+쾌적(절약) (M6+M5)
        "large_office": ["enthalpy_economizer.j2", "staging_control.j2", "m4_peak_limiting.j2", "setpoint_adjustment.j2"],
        "medium_office": ["vrf_full_control.j2", "setpoint_adjustment.j2"],
        "small_office": ["optimal_start_stop.j2", "setpoint_adjustment.j2"],
        "standalone_retail": ["optimal_start_stop.j2", "m4_peak_limiting.j2", "setpoint_adjustment.j2"],
        "primary_school": ["enthalpy_economizer.j2", "staging_control.j2", "setpoint_adjustment.j2"],
    },
}

# PMV parameters: M4 (normal) vs M5 (savings)
_PMV_PARAMS: dict[str, dict[str, float]] = {
    "m4": {"cooling_sp_adjustment": 1.0, "heating_sp_adjustment": -1.0},
    "m5": {"cooling_sp_adjustment": 2.0, "heating_sp_adjustment": -2.0},
    "m7": {"cooling_sp_adjustment": 1.0, "heating_sp_adjustment": -1.0},
    "m8": {"cooling_sp_adjustment": 2.0, "heating_sp_adjustment": -2.0},
}

# Korean city design day data: (summer_db_C, summer_wb_C, winter_db_C, latitude, longitude, elevation_m)
_CITY_DESIGN_DATA: dict[str, tuple[float, float, float, float, float, float]] = {
    "Seoul": (33.3, 25.4, -11.3, 37.57, 126.97, 86),
    "Busan": (33.0, 26.1, -5.1, 35.10, 129.03, 70),
    "Daegu": (35.4, 25.4, -8.6, 35.88, 128.62, 64),
    "Daejeon": (34.2, 25.7, -10.2, 36.37, 127.37, 69),
    "Gwangju": (34.3, 26.0, -6.8, 35.17, 126.89, 73),
    "Incheon": (32.3, 25.6, -10.4, 37.48, 126.63, 68),
    "Gangneung": (33.8, 26.5, -7.5, 37.75, 128.90, 26),
    "Jeju": (33.0, 26.7, 0.1, 33.51, 126.53, 21),
    "Cheongju": (34.5, 25.8, -11.0, 36.64, 127.44, 58),
    "Ulsan": (34.0, 26.0, -5.8, 35.55, 129.32, 35),
}

# Monthly ground temperatures (°C) for Korean cities (Jan-Dec)
# Source: KMA ground surface measurements + ASHRAE Fundamentals correlation
_CITY_GROUND_TEMPS: dict[str, list[float]] = {
    "Seoul":     [1.5,  2.8,  6.5, 12.0, 17.5, 22.5, 25.5, 26.0, 22.5, 16.5, 10.0,  4.0],
    "Busan":     [5.0,  5.5,  8.5, 13.5, 18.0, 22.0, 25.0, 26.5, 23.5, 18.5, 12.5,  7.5],
    "Daegu":     [2.5,  3.5,  7.5, 13.0, 18.5, 23.0, 26.0, 27.0, 23.0, 17.0, 10.5,  5.0],
    "Daejeon":   [1.0,  2.5,  6.5, 12.0, 17.5, 22.5, 25.5, 26.0, 22.0, 16.0,  9.5,  3.5],
    "Gwangju":   [3.0,  4.0,  7.5, 13.0, 18.0, 22.5, 25.5, 26.5, 23.0, 17.0, 11.0,  5.5],
    "Incheon":   [0.5,  1.5,  5.5, 11.0, 16.5, 21.5, 25.0, 26.0, 22.5, 16.5,  9.5,  3.5],
    "Gangneung": [2.0,  2.5,  6.0, 11.5, 16.5, 21.0, 24.5, 26.0, 22.5, 17.0, 10.5,  5.0],
    "Jeju":      [6.5,  6.5,  9.0, 13.5, 17.5, 21.5, 25.5, 27.0, 24.0, 19.5, 13.5,  9.0],
    "Cheongju":  [1.0,  2.0,  6.0, 12.0, 17.5, 22.5, 25.5, 26.5, 22.5, 16.0,  9.5,  3.5],
    "Ulsan":     [4.0,  4.5,  7.5, 12.5, 17.5, 22.0, 25.0, 26.5, 23.5, 18.0, 12.0,  6.5],
}

# Building type → internal loads defaults (W/m2 for lighting/equipment, m2/person for people)
_BUILDING_LOADS: dict[str, dict[str, float]] = {
    "large_office": {"people_m2_per_person": 18.58, "lighting_w_m2": 10.76, "equipment_w_m2": 10.76},
    "medium_office": {"people_m2_per_person": 18.58, "lighting_w_m2": 10.76, "equipment_w_m2": 10.76},
    "small_office": {"people_m2_per_person": 18.58, "lighting_w_m2": 10.76, "equipment_w_m2": 10.76},
    "standalone_retail": {"people_m2_per_person": 6.20, "lighting_w_m2": 16.89, "equipment_w_m2": 5.38},
    "primary_school": {"people_m2_per_person": 3.72, "lighting_w_m2": 12.92, "equipment_w_m2": 14.31},
}

# Perimeter depth in meters (ASHRAE 90.1 standard)
_PERIMETER_DEPTH = 4.57


def _get_ems_templates(strategy: str, building_type: str) -> list[str]:
    """Select EMS templates based on strategy and building type.

    Looks up per-building-type mapping first, then falls back to wildcard '*'.
    Returns empty list for unknown strategy or building type not in mapping.
    """
    strategy_map = STRATEGY_TEMPLATE_MAP.get(strategy, {})
    if not strategy_map:
        return []
    # Check specific building type first, then wildcard
    templates = strategy_map.get(building_type, strategy_map.get("*", []))
    return templates


def _render_ems_templates(
    templates: list[str],
    context: dict,
    ems_template_dir: Path | None = None,
) -> str:
    """Render Jinja2 EMS templates with building context."""
    if not templates:
        return ""

    if ems_template_dir is None:
        ems_template_dir = Path(__file__).parent.parent.parent.parent / "config" / "ems_templates"

    if not ems_template_dir.exists():
        logger.warning("EMS template dir not found: %s", ems_template_dir)
        return f"! EMS templates directory not found: {ems_template_dir}\n"

    env = SandboxedEnvironment(
        loader=FileSystemLoader(str(ems_template_dir)),
        keep_trailing_newline=True,
    )

    rendered_parts = []
    for tmpl_name in templates:
        try:
            tmpl = env.get_template(tmpl_name)
            rendered = tmpl.render(**context)
            rendered_parts.append(f"! === EMS: {tmpl_name} ===\n{rendered}")
        except Exception as exc:
            logger.error("Failed to render EMS template %s: %s", tmpl_name, exc)
            rendered_parts.append(f"! ERROR rendering {tmpl_name}: {exc}\n")

    return "\n\n".join(rendered_parts)


def _generate_global_geometry_rules() -> str:
    """Generate GlobalGeometryRules required by EnergyPlus."""
    return "\n".join([
        "GlobalGeometryRules,",
        "  UpperLeftCorner,          !- Starting Vertex Position",
        "  Counterclockwise,         !- Vertex Entry Direction",
        "  Relative;                 !- Coordinate System",
        "",
    ])


def _generate_design_days(climate_city: str) -> str:
    """Generate SizingPeriod:DesignDay for summer and winter."""
    data = _CITY_DESIGN_DATA.get(climate_city, _CITY_DESIGN_DATA["Seoul"])
    summer_db, summer_wb, winter_db, lat, lon, elev = data

    lines = [
        "! === Design Days ===",
        "",
        "Site:Location,",
        f"  {sanitize_idf_field(climate_city)},  !- Name",
        f"  {lat},                       !- Latitude",
        f"  {lon},                       !- Longitude",
        "  9,                           !- Time Zone (KST = UTC+9)",
        f"  {elev};                      !- Elevation",
        "",
        "SizingPeriod:DesignDay,",
        f"  {sanitize_idf_field(climate_city)} Summer Design Day,  !- Name",
        "  7,                           !- Month",
        "  21,                          !- Day of Month",
        "  SummerDesignDay,             !- Day Type",
        f"  {summer_db},                 !- Maximum Dry-Bulb Temperature",
        "  10.0,                        !- Daily Dry-Bulb Temperature Range",
        "  DefaultMultipliers,          !- Dry-Bulb Temperature Range Modifier Type",
        "  ,                            !- Dry-Bulb Temperature Range Modifier Day Schedule Name",
        "  Wetbulb,                     !- Humidity Condition Type",
        f"  {summer_wb},                 !- Wetbulb or DewPoint at Maximum Dry-Bulb",
        "  ,                            !- Humidity Condition Day Schedule Name",
        "  ,                            !- Humidity Ratio at Maximum Dry-Bulb",
        "  ,                            !- Enthalpy at Maximum Dry-Bulb",
        "  ,                            !- Daily Wet-Bulb Temperature Range",
        "  101325,                      !- Barometric Pressure",
        "  3.0,                         !- Wind Speed",
        "  180,                         !- Wind Direction",
        "  No,                          !- Rain Indicator",
        "  No,                          !- Snow Indicator",
        "  No,                          !- Daylight Saving Time Indicator",
        "  ASHRAEClearSky,              !- Solar Model Indicator",
        "  ,                            !- Beam Solar Day Schedule Name",
        "  ,                            !- Diffuse Solar Day Schedule Name",
        "  1.0;                         !- ASHRAE Clear Sky Optical Depth for Beam Irradiance",
        "",
        "SizingPeriod:DesignDay,",
        f"  {sanitize_idf_field(climate_city)} Winter Design Day,  !- Name",
        "  1,                           !- Month",
        "  21,                          !- Day of Month",
        "  WinterDesignDay,             !- Day Type",
        f"  {winter_db},                 !- Maximum Dry-Bulb Temperature",
        "  0.0,                         !- Daily Dry-Bulb Temperature Range",
        "  DefaultMultipliers,          !- Dry-Bulb Temperature Range Modifier Type",
        "  ,                            !- Dry-Bulb Temperature Range Modifier Day Schedule Name",
        "  Wetbulb,                     !- Humidity Condition Type",
        f"  {winter_db},                 !- Wetbulb or DewPoint at Maximum Dry-Bulb",
        "  ,                            !- Humidity Condition Day Schedule Name",
        "  ,                            !- Humidity Ratio at Maximum Dry-Bulb",
        "  ,                            !- Enthalpy at Maximum Dry-Bulb",
        "  ,                            !- Daily Wet-Bulb Temperature Range",
        "  101325,                      !- Barometric Pressure",
        "  3.0,                         !- Wind Speed",
        "  0,                           !- Wind Direction",
        "  No,                          !- Rain Indicator",
        "  Yes,                         !- Snow Indicator",
        "  No,                          !- Daylight Saving Time Indicator",
        "  ASHRAEClearSky,              !- Solar Model Indicator",
        "  ,                            !- Beam Solar Day Schedule Name",
        "  ,                            !- Diffuse Solar Day Schedule Name",
        "  0.0;                         !- ASHRAE Clear Sky Optical Depth for Beam Irradiance",
        "",
    ]
    return "\n".join(lines)


def _generate_ground_temps(climate_city: str) -> str:
    """Generate Site:GroundTemperature:BuildingSurface for the given city."""
    temps = _CITY_GROUND_TEMPS.get(climate_city, _CITY_GROUND_TEMPS["Seoul"])
    lines = [
        "! === Ground Temperatures ===",
        "",
        "Site:GroundTemperature:BuildingSurface,",
    ]
    for i, t in enumerate(temps):
        sep = ";" if i == 11 else ","
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        lines.append(f"  {t:.1f}{sep}                          !- {month_names[i]} Ground Temperature {{C}}")
    lines.append("")
    return "\n".join(lines)


def _generate_constructions(bps: dict) -> str:
    """Generate Material:NoMass and Construction objects from BPS envelope."""
    env = bps.get("envelope", {})
    wall_u = env.get("wall_u_value", 0.5)
    roof_u = env.get("roof_u_value", 0.3)
    floor_u = env.get("floor_u_value", 0.5)

    # R-values = 1/U (m2·K/W)
    wall_r = 1.0 / wall_u if wall_u > 0 else 2.0
    roof_r = 1.0 / roof_u if roof_u > 0 else 3.33
    floor_r = 1.0 / floor_u if floor_u > 0 else 2.0

    lines = [
        "! === Materials & Constructions ===",
        "",
        "Material:NoMass,",
        "  ExtWallMaterial,             !- Name",
        "  MediumRough,                 !- Roughness",
        f"  {wall_r:.4f},               !- Thermal Resistance {{m2-K/W}}",
        "  0.9,                         !- Thermal Absorptance",
        "  0.7,                         !- Solar Absorptance",
        "  0.7;                         !- Visible Absorptance",
        "",
        "Material:NoMass,",
        "  RoofMaterial,                !- Name",
        "  MediumRough,                 !- Roughness",
        f"  {roof_r:.4f},               !- Thermal Resistance {{m2-K/W}}",
        "  0.9,                         !- Thermal Absorptance",
        "  0.7,                         !- Solar Absorptance",
        "  0.7;                         !- Visible Absorptance",
        "",
        "Material:NoMass,",
        "  FloorMaterial,               !- Name",
        "  MediumRough,                 !- Roughness",
        f"  {floor_r:.4f},              !- Thermal Resistance {{m2-K/W}}",
        "  0.9,                         !- Thermal Absorptance",
        "  0.7,                         !- Solar Absorptance",
        "  0.7;                         !- Visible Absorptance",
        "",
        "Material:NoMass,",
        "  IntWallMaterial,             !- Name",
        "  MediumSmooth,                !- Roughness",
        "  0.2,                         !- Thermal Resistance {m2-K/W}",
        "  0.9,                         !- Thermal Absorptance",
        "  0.5,                         !- Solar Absorptance",
        "  0.5;                         !- Visible Absorptance",
        "",
        "Material:NoMass,",
        "  IntFloorMaterial,            !- Name",
        "  MediumSmooth,                !- Roughness",
        "  0.3,                         !- Thermal Resistance {m2-K/W}",
        "  0.9,                         !- Thermal Absorptance",
        "  0.5,                         !- Solar Absorptance",
        "  0.5;                         !- Visible Absorptance",
        "",
        "Construction,",
        "  ExtWall,                     !- Name",
        "  ExtWallMaterial;             !- Layer",
        "",
        "Construction,",
        "  Roof,                        !- Name",
        "  RoofMaterial;                !- Layer",
        "",
        "Construction,",
        "  GroundFloor,                 !- Name",
        "  FloorMaterial;               !- Layer",
        "",
        "Construction,",
        "  IntWall,                     !- Name",
        "  IntWallMaterial;             !- Layer",
        "",
        "Construction,",
        "  IntFloor,                    !- Name",
        "  IntFloorMaterial;            !- Layer",
        "",
        "Construction,",
        "  ExtWindow,                   !- Name",
        "  SimpleWindow;                !- Layer",
        "",
    ]
    return "\n".join(lines)


def _compute_zone_geometry(
    width: float, length: float, floors: int, height: float
) -> list[dict]:
    """Compute zone boundary coordinates for a perimeter/core model.

    Returns list of dicts: {name, floor, x_min, x_max, y_min, y_max, z_min, z_max,
                            has_north, has_south, has_east, has_west}
    """
    pd = min(_PERIMETER_DEPTH, width / 3, length / 3)
    zones = []

    for f in range(1, floors + 1):
        fl = f"F{f}"
        z_min = (f - 1) * height
        z_max = f * height

        # South perimeter
        zones.append({
            "name": f"{fl}_Perimeter_S", "floor": f,
            "x_min": 0, "x_max": width, "y_min": 0, "y_max": pd,
            "z_min": z_min, "z_max": z_max,
            "has_south": True, "has_north": False, "has_east": True, "has_west": True,
        })
        # North perimeter
        zones.append({
            "name": f"{fl}_Perimeter_N", "floor": f,
            "x_min": 0, "x_max": width, "y_min": length - pd, "y_max": length,
            "z_min": z_min, "z_max": z_max,
            "has_south": False, "has_north": True, "has_east": True, "has_west": True,
        })
        # East perimeter (between S and N perimeters)
        zones.append({
            "name": f"{fl}_Perimeter_E", "floor": f,
            "x_min": width - pd, "x_max": width, "y_min": pd, "y_max": length - pd,
            "z_min": z_min, "z_max": z_max,
            "has_south": False, "has_north": False, "has_east": True, "has_west": False,
        })
        # West perimeter (between S and N perimeters)
        zones.append({
            "name": f"{fl}_Perimeter_W", "floor": f,
            "x_min": 0, "x_max": pd, "y_min": pd, "y_max": length - pd,
            "z_min": z_min, "z_max": z_max,
            "has_south": False, "has_north": False, "has_east": False, "has_west": True,
        })
        # Core
        zones.append({
            "name": f"{fl}_Core", "floor": f,
            "x_min": pd, "x_max": width - pd, "y_min": pd, "y_max": length - pd,
            "z_min": z_min, "z_max": z_max,
            "has_south": False, "has_north": False, "has_east": False, "has_west": False,
        })

    return zones


def _generate_idf_geometry(bps: dict) -> str:
    """Generate IDF Building + Zone + Surface objects from BPS."""
    geom = bps.get("geometry", {})
    building_type = geom.get("building_type", "large_office")
    floors = geom.get("num_floors_above", 1)
    area = geom.get("total_floor_area_m2", 1000)
    height = geom.get("floor_to_floor_height_m", 3.96)
    aspect = geom.get("aspect_ratio", 1.5)
    wwr_val = geom.get("wwr", 0.38)
    orientation = geom.get("orientation_deg", 0)

    floor_area = area / floors
    width = (floor_area / aspect) ** 0.5
    length = width * aspect
    wall_height = height

    # Sanitize user-supplied strings
    safe_building_type = sanitize_idf_field(building_type)

    lines = [
        "! === Building & Zones ===",
        "",
        "Building,",
        f"  {safe_building_type},             !- Name",
        f"  {orientation},               !- North Axis",
        "  Suburbs,                      !- Terrain",
        "  0.04,                         !- Loads Convergence Tolerance Value",
        "  0.4,                          !- Temperature Convergence Tolerance Value",
        "  FullExterior,                 !- Solar Distribution",
        "  25,                           !- Maximum Number of Warmup Days",
        "  6;                            !- Minimum Number of Warmup Days",
        "",
    ]

    # Compute zones
    zone_geoms = _compute_zone_geometry(width, length, floors, height)

    # Generate Zone objects
    for zg in zone_geoms:
        lines.append("Zone,")
        lines.append(f"  {zg['name']},                 !- Name")
        lines.append("  0,                           !- Direction of Relative North")
        lines.append(f"  0, 0, {zg['z_min']},          !- X,Y,Z Origin")
        lines.append("  1,                           !- Type")
        lines.append("  1,                           !- Multiplier")
        lines.append(f"  {wall_height},                !- Ceiling Height")
        lines.append("  autocalculate;               !- Volume")
        lines.append("")

    # Generate surfaces for each zone
    surf_idx = 0
    for zg in zone_geoms:
        zn = zg["name"]
        x0, x1 = zg["x_min"], zg["x_max"]
        y0, y1 = zg["y_min"], zg["y_max"]
        h = wall_height
        is_ground = (zg["floor"] == 1)
        is_top = (zg["floor"] == floors)

        # Floor surface
        surf_idx += 1
        floor_bc = "Ground" if is_ground else "Surface"
        floor_bc_obj = "" if is_ground else f"F{zg['floor']-1}_{zn.split('_', 1)[1]}_Ceiling"
        floor_construction = "GroundFloor" if is_ground else "IntFloor"
        lines.append("BuildingSurface:Detailed,")
        lines.append(f"  {zn}_Floor,                  !- Name")
        lines.append("  Floor,                       !- Surface Type")
        lines.append(f"  {floor_construction},         !- Construction Name")
        lines.append(f"  {zn},                        !- Zone Name")
        lines.append("  ,                            !- Space Name")
        if is_ground:
            lines.append("  Ground,                      !- Outside Boundary Condition")
            lines.append("  ,                            !- Outside Boundary Condition Object")
        else:
            lines.append("  Surface,                     !- Outside Boundary Condition")
            lines.append(f"  {floor_bc_obj},              !- Outside Boundary Condition Object")
        lines.append("  NoSun,                       !- Sun Exposure")
        lines.append("  NoWind,                      !- Wind Exposure")
        lines.append("  ,                            !- View Factor to Ground")
        lines.append("  4,                           !- Number of Vertices")
        lines.append(f"  {x0}, {y0}, 0,               !- Vertex 1")
        lines.append(f"  {x0}, {y1}, 0,               !- Vertex 2")
        lines.append(f"  {x1}, {y1}, 0,               !- Vertex 3")
        lines.append(f"  {x1}, {y0}, 0;               !- Vertex 4")
        lines.append("")

        # Ceiling/Roof surface
        surf_idx += 1
        if is_top:
            ceil_type = "Roof"
            ceil_construction = "Roof"
            ceil_bc = "Outdoors"
            ceil_bc_obj = ""
            sun = "SunExposed"
            wind = "WindExposed"
        else:
            ceil_type = "Ceiling"
            ceil_construction = "IntFloor"
            ceil_bc = "Surface"
            ceil_bc_obj = f"F{zg['floor']+1}_{zn.split('_', 1)[1]}_Floor"
            sun = "NoSun"
            wind = "NoWind"
        lines.append("BuildingSurface:Detailed,")
        lines.append(f"  {zn}_Ceiling,                !- Name")
        lines.append(f"  {ceil_type},                  !- Surface Type")
        lines.append(f"  {ceil_construction},          !- Construction Name")
        lines.append(f"  {zn},                        !- Zone Name")
        lines.append("  ,                            !- Space Name")
        lines.append(f"  {ceil_bc},                   !- Outside Boundary Condition")
        if ceil_bc_obj:
            lines.append(f"  {ceil_bc_obj},               !- Outside Boundary Condition Object")
        else:
            lines.append("  ,                            !- Outside Boundary Condition Object")
        lines.append(f"  {sun},                       !- Sun Exposure")
        lines.append(f"  {wind},                      !- Wind Exposure")
        lines.append("  ,                            !- View Factor to Ground")
        lines.append("  4,                           !- Number of Vertices")
        lines.append(f"  {x0}, {y1}, {h},              !- Vertex 1")
        lines.append(f"  {x0}, {y0}, {h},              !- Vertex 2")
        lines.append(f"  {x1}, {y0}, {h},              !- Vertex 3")
        lines.append(f"  {x1}, {y1}, {h};              !- Vertex 4")
        lines.append("")

        # Exterior walls + windows
        ext_walls = []
        if zg.get("has_south"):
            ext_walls.append(("South", x1, y0, 0, x0, y0, 0))
        if zg.get("has_north"):
            ext_walls.append(("North", x0, y1, 0, x1, y1, 0))
        if zg.get("has_east"):
            ext_walls.append(("East", x1, y1, 0, x1, y0, 0))
        if zg.get("has_west"):
            ext_walls.append(("West", x0, y0, 0, x0, y1, 0))

        for direction, wx0, wy0, _, wx1, wy1, _ in ext_walls:
            surf_idx += 1
            wall_name = f"{zn}_Wall_{direction}"
            lines.append("BuildingSurface:Detailed,")
            lines.append(f"  {wall_name},                 !- Name")
            lines.append("  Wall,                        !- Surface Type")
            lines.append("  ExtWall,                     !- Construction Name")
            lines.append(f"  {zn},                        !- Zone Name")
            lines.append("  ,                            !- Space Name")
            lines.append("  Outdoors,                    !- Outside Boundary Condition")
            lines.append("  ,                            !- Outside Boundary Condition Object")
            lines.append("  SunExposed,                  !- Sun Exposure")
            lines.append("  WindExposed,                 !- Wind Exposure")
            lines.append("  ,                            !- View Factor to Ground")
            lines.append("  4,                           !- Number of Vertices")
            lines.append(f"  {wx0}, {wy0}, {h},           !- Vertex 1")
            lines.append(f"  {wx0}, {wy0}, 0,             !- Vertex 2")
            lines.append(f"  {wx1}, {wy1}, 0,             !- Vertex 3")
            lines.append(f"  {wx1}, {wy1}, {h};           !- Vertex 4")
            lines.append("")

            # Window on this wall
            wwr = wwr_val if isinstance(wwr_val, (int, float)) else 0.38
            if wwr > 0:
                wall_width = ((wx1 - wx0) ** 2 + (wy1 - wy0) ** 2) ** 0.5
                win_height = h * (wwr ** 0.5)
                win_width = wall_width * (wwr ** 0.5)
                # Center the window
                sill = (h - win_height) / 2
                h_offset = (wall_width - win_width) / 2

                lines.append("FenestrationSurface:Detailed,")
                lines.append(f"  {wall_name}_Win,             !- Name")
                lines.append("  Window,                      !- Surface Type")
                lines.append("  ExtWindow,                   !- Construction Name")
                lines.append(f"  {wall_name},                 !- Building Surface Name")
                lines.append("  ,                            !- Outside Boundary Condition Object")
                lines.append("  ,                            !- View Factor to Ground")
                lines.append("  ,                            !- Frame and Divider Name")
                lines.append("  1,                           !- Multiplier")
                lines.append("  4,                           !- Number of Vertices")

                # Window vertices (relative to wall, using interpolation along wall direction)
                dx = (wx1 - wx0) / wall_width if wall_width > 0 else 0
                dy = (wy1 - wy0) / wall_width if wall_width > 0 else 0
                # UL, LL, LR, UR
                v1x = wx0 + dx * h_offset
                v1y = wy0 + dy * h_offset
                v2x = wx0 + dx * (h_offset + win_width)
                v2y = wy0 + dy * (h_offset + win_width)

                lines.append(f"  {v1x:.3f}, {v1y:.3f}, {sill + win_height:.3f},  !- Vertex 1")
                lines.append(f"  {v1x:.3f}, {v1y:.3f}, {sill:.3f},               !- Vertex 2")
                lines.append(f"  {v2x:.3f}, {v2y:.3f}, {sill:.3f},               !- Vertex 3")
                lines.append(f"  {v2x:.3f}, {v2y:.3f}, {sill + win_height:.3f};  !- Vertex 4")
                lines.append("")

    return "\n".join(lines)


def _generate_idf_envelope(bps: dict) -> str:
    """Generate IDF envelope (glazing) objects."""
    env = bps.get("envelope", {})
    window_u = env.get("window_u_value", 1.5)
    window_shgc = env.get("window_shgc", 0.25)

    lines = [
        "! === Glazing ===",
        "",
        "WindowMaterial:SimpleGlazingSystem,",
        "  SimpleWindow,                 !- Name",
        f"  {window_u},                   !- U-Factor",
        f"  {window_shgc};                !- Solar Heat Gain Coefficient",
        "",
    ]
    return "\n".join(lines)


def _generate_schedules(bps: dict) -> str:
    """Generate schedule type limits and operation schedules."""
    sp = bps.get("setpoints", {})
    cool_occ = sp.get("cooling_occupied", 24.0)
    heat_occ = sp.get("heating_occupied", 20.0)
    cool_unocc = sp.get("cooling_unoccupied", 29.0)
    heat_unocc = sp.get("heating_unoccupied", 15.0)

    lines = [
        "! === Schedule Type Limits ===",
        "",
        "ScheduleTypeLimits,",
        "  Any Number;                    !- Name",
        "",
        "ScheduleTypeLimits,",
        "  Fraction,                      !- Name",
        "  0.0,                           !- Lower Limit Value",
        "  1.0,                           !- Upper Limit Value",
        "  Continuous;                    !- Numeric Type",
        "",
        "ScheduleTypeLimits,",
        "  Temperature,                   !- Name",
        "  -60,                           !- Lower Limit Value",
        "  200,                           !- Upper Limit Value",
        "  Continuous;                    !- Numeric Type",
        "",
        "ScheduleTypeLimits,",
        "  On/Off,                        !- Name",
        "  0,                             !- Lower Limit Value",
        "  1,                             !- Upper Limit Value",
        "  Discrete;                      !- Numeric Type",
        "",
        "! === Operation Schedules ===",
        "",
        "Schedule:Compact,",
        "  Always On,                     !- Name",
        "  On/Off,                        !- Schedule Type Limits Name",
        "  Through: 12/31,                !- Field 1",
        "  For: AllDays,                  !- Field 2",
        "  Until: 24:00, 1;              !- Field 3",
        "",
        "Schedule:Compact,",
        "  OccupancySchedule,             !- Name",
        "  Fraction,                      !- Schedule Type Limits Name",
        "  Through: 12/31,                !- Field 1",
        "  For: Weekdays SummerDesignDay, !- Field 2",
        "  Until: 06:00, 0.0,            !- Field 3",
        "  Until: 07:00, 0.2,            !- Field 5",
        "  Until: 08:00, 0.5,            !- Field 7",
        "  Until: 12:00, 1.0,            !- Field 9",
        "  Until: 13:00, 0.5,            !- Field 11",
        "  Until: 17:00, 1.0,            !- Field 13",
        "  Until: 18:00, 0.5,            !- Field 15",
        "  Until: 22:00, 0.1,            !- Field 17",
        "  Until: 24:00, 0.0,            !- Field 19",
        "  For: Saturday,                 !- Field 20",
        "  Until: 06:00, 0.0,            !- Field 21",
        "  Until: 08:00, 0.1,            !- Field 23",
        "  Until: 14:00, 0.5,            !- Field 25",
        "  Until: 17:00, 0.1,            !- Field 27",
        "  Until: 24:00, 0.0,            !- Field 29",
        "  For: AllOtherDays,             !- Field 30",
        "  Until: 24:00, 0.0;            !- Field 31",
        "",
        "Schedule:Compact,",
        "  LightingSchedule,              !- Name",
        "  Fraction,                      !- Schedule Type Limits Name",
        "  Through: 12/31,                !- Field 1",
        "  For: Weekdays SummerDesignDay, !- Field 2",
        "  Until: 06:00, 0.05,           !- Field 3",
        "  Until: 07:00, 0.2,            !- Field 5",
        "  Until: 08:00, 0.5,            !- Field 7",
        "  Until: 17:00, 0.9,            !- Field 9",
        "  Until: 18:00, 0.5,            !- Field 11",
        "  Until: 22:00, 0.3,            !- Field 13",
        "  Until: 24:00, 0.05,           !- Field 15",
        "  For: Saturday,                 !- Field 16",
        "  Until: 06:00, 0.05,           !- Field 17",
        "  Until: 08:00, 0.15,           !- Field 19",
        "  Until: 14:00, 0.5,            !- Field 21",
        "  Until: 17:00, 0.15,           !- Field 23",
        "  Until: 24:00, 0.05,           !- Field 25",
        "  For: AllOtherDays,             !- Field 26",
        "  Until: 24:00, 0.05;           !- Field 27",
        "",
        "Schedule:Compact,",
        "  EquipmentSchedule,             !- Name",
        "  Fraction,                      !- Schedule Type Limits Name",
        "  Through: 12/31,                !- Field 1",
        "  For: Weekdays SummerDesignDay, !- Field 2",
        "  Until: 08:00, 0.4,            !- Field 3",
        "  Until: 12:00, 0.9,            !- Field 5",
        "  Until: 13:00, 0.8,            !- Field 7",
        "  Until: 17:00, 0.9,            !- Field 9",
        "  Until: 18:00, 0.5,            !- Field 11",
        "  Until: 24:00, 0.4,            !- Field 13",
        "  For: Saturday,                 !- Field 14",
        "  Until: 08:00, 0.3,            !- Field 15",
        "  Until: 14:00, 0.5,            !- Field 17",
        "  Until: 24:00, 0.3,            !- Field 19",
        "  For: AllOtherDays,             !- Field 20",
        "  Until: 24:00, 0.3;            !- Field 21",
        "",
        "! === Thermostat Setpoints ===",
        "",
        "Schedule:Compact,",
        "  CoolingSetpoint,               !- Name",
        "  Temperature,                   !- Schedule Type Limits Name",
        "  Through: 12/31,                !- Field 1",
        "  For: Weekdays SummerDesignDay, !- Field 2",
        f"  Until: 06:00, {cool_unocc},   !- Field 3",
        f"  Until: 18:00, {cool_occ},      !- Field 5",
        f"  Until: 24:00, {cool_unocc},    !- Field 7",
        "  For: AllOtherDays,             !- Field 8",
        f"  Until: 24:00, {cool_unocc};    !- Field 9",
        "",
        "Schedule:Compact,",
        "  HeatingSetpoint,               !- Name",
        "  Temperature,                   !- Schedule Type Limits Name",
        "  Through: 12/31,                !- Field 1",
        "  For: Weekdays WinterDesignDay, !- Field 2",
        f"  Until: 06:00, {heat_unocc},    !- Field 3",
        f"  Until: 18:00, {heat_occ},      !- Field 5",
        f"  Until: 24:00, {heat_unocc},    !- Field 7",
        "  For: AllOtherDays,             !- Field 8",
        f"  Until: 24:00, {heat_unocc};    !- Field 9",
        "",
    ]
    return "\n".join(lines)


def _generate_internal_loads(bps: dict, zone_names: list[str]) -> str:
    """Generate People, Lights, ElectricEquipment for each zone."""
    building_type = bps.get("geometry", {}).get("building_type", "large_office")
    loads = _BUILDING_LOADS.get(building_type, _BUILDING_LOADS["large_office"])

    lines = ["! === Internal Loads ===", ""]

    for zn in zone_names:
        # People
        lines.extend([
            "People,",
            f"  {zn}_People,                  !- Name",
            f"  {zn},                         !- Zone Name",
            "  OccupancySchedule,            !- Number of People Schedule Name",
            "  Area/Person,                  !- Number of People Calculation Method",
            "  ,                             !- Zone Floor Area per Person",
            f"  {loads['people_m2_per_person']},  !- Zone Floor Area per Person {{m2/person}}",
            "  ,                             !- People per Floor Area",
            "  0.3,                          !- Fraction Radiant",
            "  autocalculate;                !- Sensible Heat Fraction",
            "",
        ])

        # Lights
        lines.extend([
            "Lights,",
            f"  {zn}_Lights,                  !- Name",
            f"  {zn},                         !- Zone Name",
            "  LightingSchedule,             !- Schedule Name",
            "  Watts/Area,                   !- Design Level Calculation Method",
            "  ,                             !- Lighting Level",
            f"  {loads['lighting_w_m2']},      !- Watts per Floor Area {{W/m2}}",
            "  ,                             !- Watts per Person",
            "  0.0,                          !- Return Air Fraction",
            "  0.7,                          !- Fraction Radiant",
            "  0.2;                          !- Fraction Visible",
            "",
        ])

        # Equipment
        lines.extend([
            "ElectricEquipment,",
            f"  {zn}_Equipment,               !- Name",
            f"  {zn},                         !- Zone Name",
            "  EquipmentSchedule,            !- Schedule Name",
            "  Watts/Area,                   !- Design Level Calculation Method",
            "  ,                             !- Design Level",
            f"  {loads['equipment_w_m2']},     !- Watts per Floor Area {{W/m2}}",
            "  ,                             !- Watts per Person",
            "  0.0,                          !- Fraction Latent",
            "  0.5,                          !- Fraction Radiant",
            "  0.0;                          !- Fraction Lost",
            "",
        ])

    return "\n".join(lines)


def _generate_infiltration(bps: dict, zone_names: list[str]) -> str:
    """Generate ZoneInfiltration:DesignFlowRate for each zone."""
    ach = bps.get("envelope", {}).get("infiltration_ach", 0.5)

    lines = ["! === Infiltration ===", ""]
    for zn in zone_names:
        lines.extend([
            "ZoneInfiltration:DesignFlowRate,",
            f"  {zn}_Infiltration,            !- Name",
            f"  {zn},                         !- Zone Name",
            "  Always On,                    !- Schedule Name",
            "  AirChanges/Hour,              !- Design Flow Rate Calculation Method",
            "  ,                             !- Design Flow Rate",
            "  ,                             !- Flow Rate per Floor Area",
            "  ,                             !- Flow Rate per Exterior Surface Area",
            f"  {ach};                        !- Air Changes per Hour",
            "",
        ])

    return "\n".join(lines)


def _generate_hvac(zone_names: list[str]) -> str:
    """Generate IdealLoadsAirSystem HVAC for each zone."""
    lines = ["! === HVAC (Ideal Loads Air System) ===", ""]

    for zn in zone_names:
        lines.extend([
            "ZoneHVAC:IdealLoadsAirSystem,",
            f"  {zn}_IdealLoads,              !- Name",
            "  ,                             !- Availability Schedule Name",
            f"  {zn}_IdealLoads_InletNode,    !- Zone Supply Air Node Name",
            f"  {zn}_IdealLoads_ExhaustNode,  !- Zone Exhaust Air Node Name",
            "  ,                             !- System Inlet Air Node Name",
            "  50,                           !- Maximum Heating Supply Air Temperature",
            "  13,                           !- Minimum Cooling Supply Air Temperature",
            "  0.0156,                       !- Maximum Heating Supply Air Humidity Ratio",
            "  0.0077,                       !- Minimum Cooling Supply Air Humidity Ratio",
            "  NoLimit,                      !- Heating Limit",
            "  ,                             !- Maximum Heating Air Flow Rate",
            "  ,                             !- Maximum Sensible Heating Capacity",
            "  NoLimit,                      !- Cooling Limit",
            "  ,                             !- Maximum Cooling Air Flow Rate",
            "  ,                             !- Maximum Total Cooling Capacity",
            "  CoolingSetpoint,              !- Heating Availability Schedule Name",
            "  ,                             !- Cooling Availability Schedule Name",
            "  ConstantSensibleHeatRatio,    !- Dehumidification Control Type",
            "  0.7,                          !- Cooling Sensible Heat Ratio",
            "  None,                         !- Humidification Control Type",
            "  ,                             !- Design Specification Outdoor Air Object Name",
            "  ,                             !- Outdoor Air Inlet Node Name",
            "  None,                         !- Demand Controlled Ventilation Type",
            "  NoEconomizer,                 !- Outdoor Air Economizer Type",
            "  None,                         !- Heat Recovery Type",
            "  0.7,                          !- Sensible Heat Recovery Effectiveness",
            "  0.65;                         !- Latent Heat Recovery Effectiveness",
            "",
            "ZoneHVAC:EquipmentConnections,",
            f"  {zn},                         !- Zone Name",
            f"  {zn}_EquipmentList,           !- Zone Conditioning Equipment List Name",
            f"  {zn}_IdealLoads_InletNode,    !- Zone Air Inlet Node or NodeList Name",
            f"  {zn}_IdealLoads_ExhaustNode,  !- Zone Air Exhaust Node or NodeList Name",
            f"  {zn}_AirNode,                 !- Zone Air Node Name",
            f"  {zn}_ReturnAirNode;           !- Zone Return Air Node or NodeList Name",
            "",
            "ZoneHVAC:EquipmentList,",
            f"  {zn}_EquipmentList,           !- Name",
            "  SequentialLoad,               !- Load Distribution Scheme",
            "  ZoneHVAC:IdealLoadsAirSystem,  !- Zone Equipment Object Type 1",
            f"  {zn}_IdealLoads,              !- Zone Equipment Name 1",
            "  1,                            !- Zone Equipment Cooling Sequence 1",
            "  1,                            !- Zone Equipment Heating or No-Load Sequence 1",
            "  ,                             !- Zone Equipment Sequential Cooling Fraction Schedule Name 1",
            "  ;                             !- Zone Equipment Sequential Heating Fraction Schedule Name 1",
            "",
            "ZoneControl:Thermostat,",
            f"  {zn}_Thermostat,              !- Name",
            f"  {zn},                         !- Zone Name",
            "  Always On,                    !- Control Type Schedule Name",
            "  ThermostatSetpoint:DualSetpoint,  !- Control Object Type 1",
            f"  {zn}_DualSetpoint;            !- Control Name 1",
            "",
            "ThermostatSetpoint:DualSetpoint,",
            f"  {zn}_DualSetpoint,            !- Name",
            "  HeatingSetpoint,              !- Heating Setpoint Temperature Schedule Name",
            "  CoolingSetpoint;              !- Cooling Setpoint Temperature Schedule Name",
            "",
        ])

    return "\n".join(lines)


def _generate_output_variables(strategy: str) -> str:
    """Add standard EnergyPlus output variables for result parsing."""
    lines = [
        "! === Output Variables ===",
        "Output:Variable,*,Zone Ideal Loads Supply Air Total Heating Energy,Hourly;",
        "Output:Variable,*,Zone Ideal Loads Supply Air Total Cooling Energy,Hourly;",
        "Output:Variable,*,Facility Total Electric Demand Power,Hourly;",
        "Output:Variable,*,Zone Mean Air Temperature,Hourly;",
        "",
        "Output:Meter,Electricity:Facility,Hourly;",
        "Output:Meter,NaturalGas:Facility,Hourly;",
        "Output:Meter,DistrictCooling:Facility,Hourly;",
        "Output:Meter,DistrictHeating:Facility,Hourly;",
        "",
        "OutputControl:Table:Style,CommaAndHTML;",
        "",
        "Output:Table:SummaryReports,",
        "  AllSummary;",
        "",
    ]
    return "\n".join(lines)


def _resolve_run_period(
    period_type: str,
    period_start: str | None = None,
    period_end: str | None = None,
) -> tuple[str, int, int, int, int]:
    """Resolve RunPeriod name and dates from period_type.

    Returns (name, start_month, start_day, end_month, end_day).
    """
    if period_type == "1month_summer":
        return ("SummerMonth", 7, 1, 7, 31)
    elif period_type == "1month_winter":
        return ("WinterMonth", 1, 1, 1, 31)
    elif period_type == "custom" and period_start and period_end:
        try:
            sm, sd = (int(x) for x in period_start.split("/"))
            em, ed = (int(x) for x in period_end.split("/"))
            return ("CustomPeriod", sm, sd, em, ed)
        except (ValueError, AttributeError):
            pass
    # Default: full year
    return ("AnnualRun", 1, 1, 12, 31)


def generate_idf(
    building_id: str,
    config_id: str,
    strategy: str,
    climate_city: str,
    epw_file: str,
    bps: dict | None = None,
    ems_template_dir: Path | None = None,
    period_type: str = "1year",
    period_start: str | None = None,
    period_end: str | None = None,
) -> str:
    """Generate a complete IDF file from BPS + strategy.

    Args:
        building_id: UUID of the building.
        config_id: UUID of the simulation config.
        strategy: EMS strategy name (e.g. 'baseline', 'm7').
        climate_city: Korean city name.
        epw_file: EPW weather filename.
        bps: Building Parameter Schema dict. If None, loads from DB.
        ems_template_dir: Override path to EMS .j2 templates.
        period_type: Simulation period type ('1year', '1month_summer', '1month_winter', 'custom').
        period_start: Custom period start (MM/DD format).
        period_end: Custom period end (MM/DD format).

    Returns:
        Complete IDF file content as string.
    """
    if bps is None:
        raise ValueError("bps dict required for IDF generation")

    geom = bps.get("geometry", {})
    hvac_type = bps.get("hvac", {}).get("system_type", "vav_chiller_boiler")
    floors = geom.get("num_floors_above", 1)
    area = geom.get("total_floor_area_m2", 1000)
    aspect = geom.get("aspect_ratio", 1.5)
    floor_height = geom.get("floor_to_floor_height_m", 3.96)

    floor_area = area / floors
    width = (floor_area / aspect) ** 0.5
    length = width * aspect

    # Compute zone geometry for surface generation
    zone_geoms = _compute_zone_geometry(width, length, floors, floor_height)
    zone_names = [zg["name"] for zg in zone_geoms]

    # Build zone list for EMS context
    zones_ctx = [{"name": zg["name"], "floor": zg["floor"]} for zg in zone_geoms]

    # Header (sanitize all interpolated values in IDF content)
    safe_city = sanitize_idf_field(climate_city)
    safe_epw = sanitize_idf_field(epw_file)
    safe_strategy = sanitize_idf_field(strategy)

    # Resolve run period from period_type
    rp_name, rp_sm, rp_sd, rp_em, rp_ed = _resolve_run_period(
        period_type, period_start, period_end
    )

    header = f"""\
! BuildWise Generated IDF
! Building: {building_id}
! Config: {config_id}
! Strategy: {safe_strategy}
! City: {safe_city}
! EPW: {safe_epw}

Version,24.1;

Timestep,{bps.get('simulation', {}).get('timestep', 4)};

SimulationControl,
  Yes,  !- Do Zone Sizing Calculation
  Yes,  !- Do System Sizing Calculation
  Yes,  !- Do Plant Sizing Calculation
  No,   !- Run Simulation for Sizing Periods
  Yes;  !- Run Simulation for Weather File Run Periods

RunPeriod,
  {rp_name},               !- Name
  {rp_sm}, {rp_sd},        !- Start Month, Day
  {rp_em}, {rp_ed},        !- End Month, Day
  UseWeatherFile,          !- Day of Week for Start Day
  Yes,                     !- Use Weather File Holidays and Special Days
  Yes,                     !- Use Weather File Daylight Saving Period
  No,                      !- Apply Weekend Holiday Rule
  Yes,                     !- Use Weather File Rain Indicators
  Yes;                     !- Use Weather File Snow Indicators

"""

    # Assemble IDF sections
    global_rules = _generate_global_geometry_rules()
    design_days = _generate_design_days(climate_city)
    ground_temps = _generate_ground_temps(climate_city)
    geometry = _generate_idf_geometry(bps)
    constructions = _generate_constructions(bps)
    envelope = _generate_idf_envelope(bps)
    schedules = _generate_schedules(bps)
    internal_loads = _generate_internal_loads(bps, zone_names)
    infiltration = _generate_infiltration(bps, zone_names)
    hvac = _generate_hvac(zone_names)
    outputs = _generate_output_variables(strategy)

    # EMS injection
    building_type = geom.get("building_type", "large_office")
    ems_templates = _get_ems_templates(strategy, building_type)

    # Setpoint values from BPS
    setpoints = bps.get("setpoints", {})
    cool_occ = setpoints.get("cooling_occupied", 24.0)
    heat_occ = setpoints.get("heating_occupied", 20.0)
    cool_unocc = setpoints.get("cooling_unoccupied", 29.0)
    heat_unocc = setpoints.get("heating_unoccupied", 15.0)

    # Operating hours from BPS schedules
    op_hours = bps.get("schedules", {}).get("operating_hours", {})
    op_start = op_hours.get("start", 9)
    op_end = op_hours.get("end", 18)

    # PMV-based adjustment parameters (M4/M5/M7/M8)
    pmv = _PMV_PARAMS.get(strategy, {})

    # Airloop / AHU context
    ahu_name = "AHU1"
    airloops = [{"name": f"AirLoop_{f}", "original_name": f"AirLoop_{f}", "full_name": f"AirLoop_{f}"}
                for f in range(1, floors + 1)]
    zones_with_occ = [{"name": z["name"], "original_name": z["name"]} for z in zones_ctx]

    # Chiller capacity estimate (for staging_control.j2)
    chiller_capacity_kw = max(50, int(area * 0.12))  # ~120 W/m2 peak cooling

    ems_context = {
        # Zone info
        "zones": zones_ctx,
        "zones_with_occupancy": zones_with_occ,
        "zone_name": zones_ctx[0]["name"] if zones_ctx else "F1_Core",
        "representative_zone": zones_ctx[0]["name"] if zones_ctx else "F1_Core",
        # HVAC references
        "airloops": airloops,
        "ahu_name": ahu_name,
        "return_air_node": f"{ahu_name}_Return",
        "oa_controller_name": f"{ahu_name}_OAController",
        # Setpoints
        "cooling_setpoint": cool_occ,
        "heating_setpoint": heat_occ,
        "day_cooling_sp": cool_occ,
        "day_heating_sp": heat_occ,
        "night_cooling_sp": cool_unocc,
        "night_heating_sp": heat_unocc,
        # Schedule
        "occupancy_start": op_start,
        "occupancy_end": op_end,
        "target_hour": op_start,
        "operation_start": float(op_start),
        "operation_end": float(op_end),
        # PMV / peak limiting
        "cooling_sp_adjustment": pmv.get("cooling_sp_adjustment", "2.0"),
        # Staging
        "chiller_capacity_kw": chiller_capacity_kw,
        # Meta
        "hvac_type": hvac_type,
        "building_type": building_type,
        "strategy": strategy,
    }
    ems_section = _render_ems_templates(ems_templates, ems_context, ems_template_dir)

    # Combine
    idf_content = "\n".join([
        header,
        global_rules,
        design_days,
        ground_temps,
        geometry,
        constructions,
        envelope,
        schedules,
        internal_loads,
        infiltration,
        hvac,
        ems_section,
        outputs,
    ])

    logger.info(
        "Generated IDF: building=%s strategy=%s lines=%d",
        building_id, strategy, idf_content.count("\n"),
    )
    return idf_content
