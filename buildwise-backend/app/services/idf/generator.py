"""IDF generation pipeline: BPS + strategy → EnergyPlus IDF file.

Pipeline stages:
1. Load building BPS from DB
2. Select base template for building type
3. Inject geometry parameters
4. Inject envelope parameters
5. Inject HVAC system parameters
6. Generate schedules
7. Inject EMS strategy (Jinja2 template)
8. Add output variables
9. Final validation
"""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2.sandbox import SandboxedEnvironment
from jinja2 import FileSystemLoader

logger = logging.getLogger(__name__)

# Strategy → EMS template mapping (from docs/strategy-naming-reconciliation.md)
STRATEGY_TEMPLATE_MAP: dict[str, list[str]] = {
    "baseline": [],
    "m0": ["optimal_start_stop.j2"],
    "m1": ["occupancy_control.j2"],
    "m2": ["m2_night_ventilation.j2"],
    "m3": ["setpoint_adjustment.j2"],
    "m4": ["m4_peak_limiting.j2"],
    "m5": ["m5_daylighting.j2", "m5_dcv.j2"],
    "m6": ["staging_control.j2"],
    "m7": [
        "optimal_start_stop.j2",
        "occupancy_control.j2",
        "setpoint_adjustment.j2",
        "m4_peak_limiting.j2",
    ],
    "m8": [
        "optimal_start_stop.j2",
        "occupancy_control.j2",
        "setpoint_adjustment.j2",
        "m4_peak_limiting.j2",
        "staging_control.j2",
    ],
}

# Building type → HVAC-specific EMS overrides
_VRF_STRATEGY_MAP: dict[str, list[str]] = {
    "m0": ["optimal_start_vrf_v2.j2"],
    "m1": ["occupancy_control.j2"],
    "m4": ["vrf_demand_limit.j2"],
    "m7": ["vrf_full_control.j2"],
    "m8": ["vrf_full_control.j2", "vrf_night_setback.j2"],
}


def _get_ems_templates(strategy: str, hvac_type: str) -> list[str]:
    """Select EMS templates based on strategy and HVAC type."""
    if hvac_type == "vrf" and strategy in _VRF_STRATEGY_MAP:
        return _VRF_STRATEGY_MAP[strategy]
    return STRATEGY_TEMPLATE_MAP.get(strategy, [])


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


def _generate_idf_geometry(bps: dict) -> str:
    """Generate IDF geometry objects from BPS."""
    geom = bps.get("geometry", {})
    building_type = geom.get("building_type", "large_office")
    floors = geom.get("num_floors_above", 1)
    area = geom.get("total_floor_area_m2", 1000)
    height = geom.get("floor_to_floor_height_m", 3.96)
    aspect = geom.get("aspect_ratio", 1.5)
    wwr = geom.get("wwr", 0.38)
    orientation = geom.get("orientation_deg", 0)

    floor_area = area / floors
    width = (floor_area / aspect) ** 0.5
    length = width * aspect

    lines = [
        "Building,",
        f"  {building_type},             !- Name",
        f"  {orientation},               !- North Axis",
        "  Suburbs,                      !- Terrain",
        "  0.04,                         !- Loads Convergence Tolerance Value",
        "  0.4,                          !- Temperature Convergence Tolerance Value",
        "  FullExterior,                 !- Solar Distribution",
        "  25,                           !- Maximum Number of Warmup Days",
        "  6;                            !- Minimum Number of Warmup Days",
        "",
    ]

    # Generate floor zones (simplified: Core + 4 Perimeter per floor)
    for f in range(1, floors + 1):
        floor_label = f"F{f}"
        z_origin = (f - 1) * height

        zones = [f"{floor_label}_Core"]
        if isinstance(wwr, dict) or (isinstance(wwr, (int, float)) and wwr > 0):
            zones.extend([
                f"{floor_label}_Perimeter_N",
                f"{floor_label}_Perimeter_S",
                f"{floor_label}_Perimeter_E",
                f"{floor_label}_Perimeter_W",
            ])

        for zone_name in zones:
            lines.append("Zone,")
            lines.append(f"  {zone_name},                 !- Name")
            lines.append(f"  0,                           !- Direction of Relative North")
            lines.append(f"  0, 0, {z_origin},            !- X,Y,Z Origin")
            lines.append("  1,                           !- Type")
            lines.append("  1,                           !- Multiplier")
            lines.append(f"  {height},                    !- Ceiling Height")
            lines.append("  autocalculate;               !- Volume")
            lines.append("")

    return "\n".join(lines)


def _generate_idf_envelope(bps: dict) -> str:
    """Generate IDF envelope (construction/material) objects."""
    env = bps.get("envelope", {})
    window_u = env.get("window_u_value", 1.5)
    window_shgc = env.get("window_shgc", 0.25)
    wall_u = env.get("wall_u_value", 0.5)
    infiltration = env.get("infiltration_ach", 0.5)

    lines = [
        "! === Envelope Parameters ===",
        f"! Wall U-value: {wall_u} W/m2K",
        f"! Window U-value: {window_u} W/m2K, SHGC: {window_shgc}",
        f"! Infiltration: {infiltration} ACH",
        "",
        "WindowMaterial:SimpleGlazingSystem,",
        f"  SimpleWindow,                 !- Name",
        f"  {window_u},                   !- U-Factor",
        f"  {window_shgc};                !- Solar Heat Gain Coefficient",
        "",
    ]
    return "\n".join(lines)


def _generate_idf_setpoints(bps: dict) -> str:
    """Generate thermostat setpoint schedules."""
    sp = bps.get("setpoints", {})
    cool_occ = sp.get("cooling_occupied", 24.0)
    heat_occ = sp.get("heating_occupied", 20.0)
    cool_unocc = sp.get("cooling_unoccupied", 29.0)
    heat_unocc = sp.get("heating_unoccupied", 15.0)

    lines = [
        "! === Thermostat Setpoints ===",
        "Schedule:Compact,",
        "  CoolingSetpoint,              !- Name",
        "  Temperature,                  !- Schedule Type Limits Name",
        "  Through: 12/31,               !- Field 1",
        "  For: Weekdays SummerDesignDay, !- Field 2",
        f"  Until: 06:00, {cool_unocc},   !- Field 3",
        f"  Until: 18:00, {cool_occ},      !- Field 5",
        f"  Until: 24:00, {cool_unocc},    !- Field 7",
        "  For: AllOtherDays,            !- Field 8",
        f"  Until: 24:00, {cool_unocc};    !- Field 9",
        "",
        "Schedule:Compact,",
        "  HeatingSetpoint,              !- Name",
        "  Temperature,                  !- Schedule Type Limits Name",
        "  Through: 12/31,               !- Field 1",
        "  For: Weekdays WinterDesignDay, !- Field 2",
        f"  Until: 06:00, {heat_unocc},    !- Field 3",
        f"  Until: 18:00, {heat_occ},      !- Field 5",
        f"  Until: 24:00, {heat_unocc},    !- Field 7",
        "  For: AllOtherDays,            !- Field 8",
        f"  Until: 24:00, {heat_unocc};    !- Field 9",
        "",
    ]
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


def generate_idf(
    building_id: str,
    config_id: str,
    strategy: str,
    climate_city: str,
    epw_file: str,
    bps: dict | None = None,
    ems_template_dir: Path | None = None,
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

    Returns:
        Complete IDF file content as string.
    """
    if bps is None:
        # In production, this would load from DB
        raise ValueError("bps dict required for IDF generation")

    geom = bps.get("geometry", {})
    hvac_type = bps.get("hvac", {}).get("system_type", "vav_chiller_boiler")
    floors = geom.get("num_floors_above", 1)
    floor_height = geom.get("floor_to_floor_height_m", 3.96)

    # Build zone list for EMS context
    zones = []
    for f in range(1, floors + 1):
        label = f"F{f}"
        zones.append({"name": f"{label}_Core", "floor": f})
        for direction in ["N", "S", "E", "W"]:
            zones.append({"name": f"{label}_Perimeter_{direction}", "floor": f})

    # Header
    header = f"""\
! BuildWise Generated IDF
! Building: {building_id}
! Config: {config_id}
! Strategy: {strategy}
! City: {climate_city}
! EPW: {epw_file}

Version,24.1;

Timestep,{bps.get('simulation', {}).get('timestep', 4)};

SimulationControl,
  Yes,  !- Do Zone Sizing Calculation
  Yes,  !- Do System Sizing Calculation
  Yes,  !- Do Plant Sizing Calculation
  No,   !- Run Simulation for Sizing Periods
  Yes;  !- Run Simulation for Weather File Run Periods

RunPeriod,
  AnnualRun,               !- Name
  1, 1,                    !- Start Month, Day
  12, 31,                  !- End Month, Day
  UseWeatherFile,          !- Day of Week for Start Day
  Yes,                     !- Use Weather File Holidays and Special Days
  Yes,                     !- Use Weather File Daylight Saving Period
  No,                      !- Apply Weekend Holiday Rule
  Yes,                     !- Use Weather File Rain Indicators
  Yes;                     !- Use Weather File Snow Indicators

"""

    # Assemble IDF sections
    geometry = _generate_idf_geometry(bps)
    envelope = _generate_idf_envelope(bps)
    setpoints = _generate_idf_setpoints(bps)
    outputs = _generate_output_variables(strategy)

    # EMS injection
    ems_templates = _get_ems_templates(strategy, hvac_type)
    ems_context = {
        "zones": zones,
        "zone_name": zones[0]["name"] if zones else "F1_Core",
        "representative_zone": zones[0]["name"] if zones else "F1_Core",
        "airloops": [f"AirLoop_{f}" for f in range(1, min(floors + 1, 4))],
        "return_air_node": "AirLoop_1_Return",
        "hvac_type": hvac_type,
        "building_type": geom.get("building_type", "large_office"),
        "strategy": strategy,
    }
    ems_section = _render_ems_templates(ems_templates, ems_context, ems_template_dir)

    # Combine
    idf_content = "\n".join([
        header,
        geometry,
        envelope,
        setpoints,
        ems_section,
        outputs,
    ])

    logger.info(
        "Generated IDF: building=%s strategy=%s lines=%d",
        building_id, strategy, idf_content.count("\n"),
    )
    return idf_content
