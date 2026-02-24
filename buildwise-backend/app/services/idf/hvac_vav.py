"""VAV + Chiller + Boiler HVAC IDF generation.

Generates detailed EnergyPlus HVAC objects replacing IdealLoadsAirSystem:
- Chilled water plant loop with air-cooled Chiller:Electric:EIR
- Hot water plant loop with Boiler:HotWater
- AirLoopHVAC with cooling/heating coils, variable volume fan, OA system
- AirTerminal:SingleDuct:VAV:Reheat with electric reheat per zone
- Sizing objects for zones, system, and plants
"""

from __future__ import annotations


def generate_vav_chiller_boiler(bps: dict, zone_names: list[str]) -> str:
    """Generate complete VAV+Chiller+Boiler HVAC IDF section."""
    hvac = bps.get("hvac", {})
    chillers = hvac.get("chillers") or {}
    boilers = hvac.get("boilers") or {}
    ahu = hvac.get("ahu") or {}
    vav = hvac.get("vav_terminals") or {}

    n_chiller = chillers.get("count", 2)
    chiller_cop = chillers.get("cop", 6.1)
    n_boiler = boilers.get("count", 2)
    boiler_eff = boilers.get("efficiency", 0.80)
    has_eco = ahu.get("has_economizer", True)
    eco_type = ahu.get("economizer_type", "DifferentialEnthalpy")
    min_airflow = vav.get("min_airflow_ratio", 0.30)

    sections = [
        "! === HVAC (VAV + Chiller + Boiler) ===",
        _performance_curves(),
        _chilled_water_loop(n_chiller, chiller_cop),
        _hot_water_loop(n_boiler, boiler_eff),
        _air_loop(zone_names, has_eco, eco_type),
        _zone_equipment(zone_names, min_airflow),
        _supply_return_paths(zone_names),
    ]
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Performance Curves (DOE Reference centrifugal chiller)
# ---------------------------------------------------------------------------


def _performance_curves() -> str:
    return """\
! --- Chiller Performance Curves ---

Curve:Biquadratic,
  ChillerCapFT,                    !- Name
  1.0215158,                       !- Coefficient1 Constant
  0.037035864,                     !- Coefficient2 x
  0.0002332476,                    !- Coefficient3 x**2
  -0.003894048,                    !- Coefficient4 y
  -0.00013427,                     !- Coefficient5 y**2
  -0.00024989,                     !- Coefficient6 x*y
  5.0,                             !- Minimum Value of x
  10.0,                            !- Maximum Value of x
  24.0,                            !- Minimum Value of y
  35.0;                            !- Maximum Value of y

Curve:Biquadratic,
  ChillerEIRFT,                    !- Name
  0.70176857,                      !- Coefficient1 Constant
  -0.00452016,                     !- Coefficient2 x
  0.0005331096,                    !- Coefficient3 x**2
  -0.005498208,                    !- Coefficient4 y
  0.0005445241,                    !- Coefficient5 y**2
  -0.0007290324,                   !- Coefficient6 x*y
  5.0,                             !- Minimum Value of x
  10.0,                            !- Maximum Value of x
  24.0,                            !- Minimum Value of y
  35.0;                            !- Maximum Value of y

Curve:Quadratic,
  ChillerEIRFPLR,                  !- Name
  0.06369119,                      !- Coefficient1 Constant
  0.58488832,                      !- Coefficient2 x
  0.35280274,                      !- Coefficient3 x**2
  0.0,                             !- Minimum Value of x
  1.0;                             !- Maximum Value of x"""


# ---------------------------------------------------------------------------
# Chilled Water Plant Loop
# ---------------------------------------------------------------------------


def _chilled_water_loop(n_chiller: int, cop: float) -> str:
    """Generate chilled water plant loop with air-cooled chillers."""
    parts: list[str] = []

    # --- Sizing ---
    parts.append("""\
! --- Chilled Water Plant Loop ---

Sizing:Plant,
  CoolSys1,                      !- Plant or Condenser Loop Name
  Cooling,                       !- Loop Type
  7.22,                          !- Design Loop Exit Temperature {C}
  5.0;                           !- Loop Design Temperature Difference {deltaC}""")

    # --- Setpoint Manager + Schedule ---
    parts.append("""\
SetpointManager:Scheduled,
  CoolSys1_SPM,                  !- Name
  Temperature,                   !- Control Variable
  CoolSys1_CW_Temp_Sch,          !- Schedule Name
  CoolSys1_Supply_Outlet;        !- Setpoint Node or NodeList Name

Schedule:Constant,
  CoolSys1_CW_Temp_Sch,          !- Name
  Temperature,                   !- Schedule Type Limits Name
  7.22;                          !- Hourly Value {C}""")

    # --- Pump ---
    parts.append("""\
Pump:VariableSpeed,
  CoolSys1_Pump,                 !- Name
  CoolSys1_Supply_Inlet,         !- Inlet Node Name
  CoolSys1_Pump_Outlet,          !- Outlet Node Name
  autosize,                      !- Design Maximum Flow Rate {m3/s}
  179352,                        !- Design Pump Head {Pa}
  autosize,                      !- Design Power Consumption {W}
  0.9,                           !- Motor Efficiency
  0.0,                           !- Fraction of Motor Inefficiencies to Fluid Stream
  0,                             !- Coefficient 1 of the Part Load Performance Curve
  1,                             !- Coefficient 2 of the Part Load Performance Curve
  0,                             !- Coefficient 3 of the Part Load Performance Curve
  0,                             !- Coefficient 4 of the Part Load Performance Curve
  0,                             !- Design Minimum Flow Rate {m3/s}
  Intermittent;                  !- Pump Control Type""")

    # --- Chillers ---
    for i in range(1, n_chiller + 1):
        parts.append(f"""\
Chiller:Electric:EIR,
  CoolSys1 Chiller{i},            !- Name
  autosize,                      !- Reference Capacity {{W}}
  {cop},                          !- Reference COP {{W/W}}
  7.22,                          !- Reference Leaving Chilled Water Temperature {{C}}
  35.0,                          !- Reference Entering Condenser Fluid Temperature {{C}}
  autosize,                      !- Reference Chilled Water Flow Rate {{m3/s}}
  autosize,                      !- Reference Condenser Fluid Flow Rate {{m3/s}}
  ChillerCapFT,                  !- Cooling Capacity Function of Temperature Curve Name
  ChillerEIRFT,                  !- Electric Input to Cooling Output Ratio Function of Temperature Curve Name
  ChillerEIRFPLR,                !- Electric Input to Cooling Output Ratio Function of Part Load Ratio Curve Name
  0.1,                           !- Minimum Part Load Ratio
  1.0,                           !- Maximum Part Load Ratio
  1.0,                           !- Optimum Part Load Ratio
  0.1,                           !- Minimum Unloading Ratio
  CoolSys1_Chiller{i}_Inlet,     !- Chilled Water Inlet Node Name
  CoolSys1_Chiller{i}_Outlet,    !- Chilled Water Outlet Node Name
  ,                              !- Condenser Inlet Node Name
  ,                              !- Condenser Outlet Node Name
  AirCooled,                     !- Condenser Type
  ,                              !- Condenser Fan Power Ratio {{W/W}}
  1.0,                           !- Fraction of Compressor Electric Consumption Rejected by Condenser
  5.0,                           !- Leaving Chilled Water Lower Temperature Limit {{C}}
  LeavingSetpointModulated;      !- Chiller Flow Mode""")

    # --- Pipes ---
    parts.append("""\
Pipe:Adiabatic, CoolSys1_Supply_Bypass, CoolSys1_SBypass_Inlet, CoolSys1_SBypass_Outlet;
Pipe:Adiabatic, CoolSys1_SOutlet_Pipe, CoolSys1_SOutlet_Pipe_In, CoolSys1_Supply_Outlet;
Pipe:Adiabatic, CoolSys1_Demand_Bypass, CoolSys1_DBypass_Inlet, CoolSys1_DBypass_Outlet;
Pipe:Adiabatic, CoolSys1_Demand_Inlet_Pipe, CoolSys1_Demand_Inlet, CoolSys1_DInlet_Pipe_Out;
Pipe:Adiabatic, CoolSys1_Demand_Outlet_Pipe, CoolSys1_DOutlet_Pipe_In, CoolSys1_Demand_Outlet;""")

    # --- Branches ---
    branch_lines = [
        "! Supply Branches",
        "Branch, CoolSys1_Pump_Branch, , Pump:VariableSpeed, CoolSys1_Pump, CoolSys1_Supply_Inlet, CoolSys1_Pump_Outlet;",
    ]
    for i in range(1, n_chiller + 1):
        branch_lines.append(
            f"Branch, CoolSys1_Chiller{i}_Branch, , Chiller:Electric:EIR, CoolSys1 Chiller{i}, CoolSys1_Chiller{i}_Inlet, CoolSys1_Chiller{i}_Outlet;"
        )
    branch_lines.extend(
        [
            "Branch, CoolSys1_SBypass_Branch, , Pipe:Adiabatic, CoolSys1_Supply_Bypass, CoolSys1_SBypass_Inlet, CoolSys1_SBypass_Outlet;",
            "Branch, CoolSys1_SOutlet_Branch, , Pipe:Adiabatic, CoolSys1_SOutlet_Pipe, CoolSys1_SOutlet_Pipe_In, CoolSys1_Supply_Outlet;",
            "",
            "! Demand Branches",
            "Branch, CoolSys1_DInlet_Branch, , Pipe:Adiabatic, CoolSys1_Demand_Inlet_Pipe, CoolSys1_Demand_Inlet, CoolSys1_DInlet_Pipe_Out;",
            "Branch, CoolSys1_CoolCoil_Branch, , Coil:Cooling:Water, VAV_1_CoolCoil, VAV_1_CoolCoil_CW_Inlet, VAV_1_CoolCoil_CW_Outlet;",
            "Branch, CoolSys1_DBypass_Branch, , Pipe:Adiabatic, CoolSys1_Demand_Bypass, CoolSys1_DBypass_Inlet, CoolSys1_DBypass_Outlet;",
            "Branch, CoolSys1_DOutlet_Branch, , Pipe:Adiabatic, CoolSys1_Demand_Outlet_Pipe, CoolSys1_DOutlet_Pipe_In, CoolSys1_Demand_Outlet;",
        ]
    )
    parts.append("\n".join(branch_lines))

    # --- Supply BranchList ---
    sb = ["CoolSys1_Pump_Branch"]
    for i in range(1, n_chiller + 1):
        sb.append(f"CoolSys1_Chiller{i}_Branch")
    sb.extend(["CoolSys1_SBypass_Branch", "CoolSys1_SOutlet_Branch"])
    parts.append("BranchList, CoolSys1_Supply_Branches,\n" + ",\n".join(f"  {b}" for b in sb) + ";")

    # --- Demand BranchList ---
    parts.append(
        "BranchList, CoolSys1_Demand_Branches,\n"
        "  CoolSys1_DInlet_Branch,\n"
        "  CoolSys1_CoolCoil_Branch,\n"
        "  CoolSys1_DBypass_Branch,\n"
        "  CoolSys1_DOutlet_Branch;"
    )

    # --- Supply Connectors ---
    parallel_supply = [f"CoolSys1_Chiller{i}_Branch" for i in range(1, n_chiller + 1)]
    parallel_supply.append("CoolSys1_SBypass_Branch")
    par_str = ",\n".join(f"  {b}" for b in parallel_supply)

    parts.append(
        "ConnectorList, CoolSys1_Supply_Connectors,\n"
        "  Connector:Splitter, CoolSys1_Supply_Splitter,\n"
        "  Connector:Mixer, CoolSys1_Supply_Mixer;"
    )
    parts.append(f"Connector:Splitter, CoolSys1_Supply_Splitter, CoolSys1_Pump_Branch,\n{par_str};")
    parts.append(f"Connector:Mixer, CoolSys1_Supply_Mixer, CoolSys1_SOutlet_Branch,\n{par_str};")

    # --- Demand Connectors ---
    parts.append(
        "ConnectorList, CoolSys1_Demand_Connectors,\n"
        "  Connector:Splitter, CoolSys1_Demand_Splitter,\n"
        "  Connector:Mixer, CoolSys1_Demand_Mixer;"
    )
    parts.append(
        "Connector:Splitter, CoolSys1_Demand_Splitter, CoolSys1_DInlet_Branch,\n"
        "  CoolSys1_CoolCoil_Branch,\n"
        "  CoolSys1_DBypass_Branch;"
    )
    parts.append(
        "Connector:Mixer, CoolSys1_Demand_Mixer, CoolSys1_DOutlet_Branch,\n"
        "  CoolSys1_CoolCoil_Branch,\n"
        "  CoolSys1_DBypass_Branch;"
    )

    # --- Equipment Operation Scheme ---
    equip_items = [f"  Chiller:Electric:EIR, CoolSys1 Chiller{i}" for i in range(1, n_chiller + 1)]
    parts.append(
        "PlantEquipmentOperationSchemes, CoolSys1_OpScheme,\n"
        "  PlantEquipmentOperation:CoolingLoad, CoolSys1_CoolingOp, Always On;"
    )
    parts.append("PlantEquipmentOperation:CoolingLoad, CoolSys1_CoolingOp, 0, 100000000, CoolSys1_Equip;")
    parts.append("PlantEquipmentList, CoolSys1_Equip,\n" + ",\n".join(equip_items) + ";")

    # --- PlantLoop ---
    parts.append("""\
PlantLoop,
  CoolSys1,                      !- Name
  Water,                         !- Fluid Type
  ,                              !- User Fluid Type
  CoolSys1_OpScheme,             !- Plant Equipment Operation Scheme Name
  CoolSys1_Supply_Outlet,        !- Loop Temperature Setpoint Node Name
  98,                            !- Maximum Loop Temperature {C}
  1,                             !- Minimum Loop Temperature {C}
  autosize,                      !- Maximum Loop Flow Rate {m3/s}
  0,                             !- Minimum Loop Flow Rate {m3/s}
  autocalculate,                 !- Plant Loop Volume {m3}
  CoolSys1_Supply_Inlet,         !- Plant Side Inlet Node Name
  CoolSys1_Supply_Outlet,        !- Plant Side Outlet Node Name
  CoolSys1_Supply_Branches,      !- Plant Side Branch List Name
  CoolSys1_Supply_Connectors,    !- Plant Side Connector List Name
  CoolSys1_Demand_Inlet,         !- Demand Side Inlet Node Name
  CoolSys1_Demand_Outlet,        !- Demand Side Outlet Node Name
  CoolSys1_Demand_Branches,      !- Demand Side Branch List Name
  CoolSys1_Demand_Connectors,    !- Demand Side Connector List Name
  Optimal,                       !- Load Distribution Scheme
  ,                              !- Availability Manager List Name
  SingleSetpoint;                !- Plant Loop Demand Calculation Scheme""")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Hot Water Plant Loop
# ---------------------------------------------------------------------------


def _hot_water_loop(n_boiler: int, eff: float) -> str:
    """Generate hot water plant loop with boilers."""
    parts: list[str] = []

    # --- Sizing + SPM + Pump ---
    parts.append("""\
! --- Hot Water Plant Loop ---

Sizing:Plant,
  HeatSys1,                      !- Plant or Condenser Loop Name
  Heating,                       !- Loop Type
  82.0,                          !- Design Loop Exit Temperature {C}
  11.0;                          !- Loop Design Temperature Difference {deltaC}

SetpointManager:Scheduled,
  HeatSys1_SPM,                  !- Name
  Temperature,                   !- Control Variable
  HeatSys1_HW_Temp_Sch,          !- Schedule Name
  HeatSys1_Supply_Outlet;        !- Setpoint Node or NodeList Name

Schedule:Constant,
  HeatSys1_HW_Temp_Sch,          !- Name
  Temperature,                   !- Schedule Type Limits Name
  82.0;                          !- Hourly Value {C}

Pump:VariableSpeed,
  HeatSys1_Pump,                 !- Name
  HeatSys1_Supply_Inlet,         !- Inlet Node Name
  HeatSys1_Pump_Outlet,          !- Outlet Node Name
  autosize,                      !- Design Maximum Flow Rate {m3/s}
  179352,                        !- Design Pump Head {Pa}
  autosize,                      !- Design Power Consumption {W}
  0.9,                           !- Motor Efficiency
  0.0,                           !- Fraction of Motor Inefficiencies to Fluid Stream
  0,                             !- Coefficient 1 of the Part Load Performance Curve
  1,                             !- Coefficient 2 of the Part Load Performance Curve
  0,                             !- Coefficient 3 of the Part Load Performance Curve
  0,                             !- Coefficient 4 of the Part Load Performance Curve
  0,                             !- Design Minimum Flow Rate {m3/s}
  Intermittent;                  !- Pump Control Type""")

    # --- Boilers ---
    for i in range(1, n_boiler + 1):
        parts.append(f"""\
Boiler:HotWater,
  HeatSys1 Boiler{i},             !- Name
  NaturalGas,                    !- Fuel Type
  autosize,                      !- Nominal Capacity {{W}}
  {eff},                          !- Nominal Thermal Efficiency
  LeavingBoiler,                 !- Efficiency Curve Temperature Evaluation Variable
  ,                              !- Normalized Boiler Efficiency Curve Name
  autosize,                      !- Design Water Flow Rate {{m3/s}}
  0,                             !- Minimum Part Load Ratio
  1.0,                           !- Maximum Part Load Ratio
  1.0,                           !- Optimum Part Load Ratio
  HeatSys1_Boiler{i}_Inlet,      !- Boiler Water Inlet Node Name
  HeatSys1_Boiler{i}_Outlet,     !- Boiler Water Outlet Node Name
  99,                            !- Water Outlet Upper Temperature Limit {{C}}
  LeavingSetpointModulated;      !- Boiler Flow Mode""")

    # --- Pipes ---
    parts.append("""\
Pipe:Adiabatic, HeatSys1_Supply_Bypass, HeatSys1_SBypass_Inlet, HeatSys1_SBypass_Outlet;
Pipe:Adiabatic, HeatSys1_SOutlet_Pipe, HeatSys1_SOutlet_Pipe_In, HeatSys1_Supply_Outlet;
Pipe:Adiabatic, HeatSys1_Demand_Bypass, HeatSys1_DBypass_Inlet, HeatSys1_DBypass_Outlet;
Pipe:Adiabatic, HeatSys1_Demand_Inlet_Pipe, HeatSys1_Demand_Inlet, HeatSys1_DInlet_Pipe_Out;
Pipe:Adiabatic, HeatSys1_Demand_Outlet_Pipe, HeatSys1_DOutlet_Pipe_In, HeatSys1_Demand_Outlet;""")

    # --- Branches ---
    branch_lines = [
        "! Supply Branches",
        "Branch, HeatSys1_Pump_Branch, , Pump:VariableSpeed, HeatSys1_Pump, HeatSys1_Supply_Inlet, HeatSys1_Pump_Outlet;",
    ]
    for i in range(1, n_boiler + 1):
        branch_lines.append(
            f"Branch, HeatSys1_Boiler{i}_Branch, , Boiler:HotWater, HeatSys1 Boiler{i}, HeatSys1_Boiler{i}_Inlet, HeatSys1_Boiler{i}_Outlet;"
        )
    branch_lines.extend(
        [
            "Branch, HeatSys1_SBypass_Branch, , Pipe:Adiabatic, HeatSys1_Supply_Bypass, HeatSys1_SBypass_Inlet, HeatSys1_SBypass_Outlet;",
            "Branch, HeatSys1_SOutlet_Branch, , Pipe:Adiabatic, HeatSys1_SOutlet_Pipe, HeatSys1_SOutlet_Pipe_In, HeatSys1_Supply_Outlet;",
            "",
            "! Demand Branches",
            "Branch, HeatSys1_DInlet_Branch, , Pipe:Adiabatic, HeatSys1_Demand_Inlet_Pipe, HeatSys1_Demand_Inlet, HeatSys1_DInlet_Pipe_Out;",
            "Branch, HeatSys1_HeatCoil_Branch, , Coil:Heating:Water, VAV_1_HeatCoil, VAV_1_HeatCoil_HW_Inlet, VAV_1_HeatCoil_HW_Outlet;",
            "Branch, HeatSys1_DBypass_Branch, , Pipe:Adiabatic, HeatSys1_Demand_Bypass, HeatSys1_DBypass_Inlet, HeatSys1_DBypass_Outlet;",
            "Branch, HeatSys1_DOutlet_Branch, , Pipe:Adiabatic, HeatSys1_Demand_Outlet_Pipe, HeatSys1_DOutlet_Pipe_In, HeatSys1_Demand_Outlet;",
        ]
    )
    parts.append("\n".join(branch_lines))

    # --- Supply BranchList ---
    sb = ["HeatSys1_Pump_Branch"]
    for i in range(1, n_boiler + 1):
        sb.append(f"HeatSys1_Boiler{i}_Branch")
    sb.extend(["HeatSys1_SBypass_Branch", "HeatSys1_SOutlet_Branch"])
    parts.append("BranchList, HeatSys1_Supply_Branches,\n" + ",\n".join(f"  {b}" for b in sb) + ";")

    # --- Demand BranchList ---
    parts.append(
        "BranchList, HeatSys1_Demand_Branches,\n"
        "  HeatSys1_DInlet_Branch,\n"
        "  HeatSys1_HeatCoil_Branch,\n"
        "  HeatSys1_DBypass_Branch,\n"
        "  HeatSys1_DOutlet_Branch;"
    )

    # --- Supply Connectors ---
    par_supply = [f"HeatSys1_Boiler{i}_Branch" for i in range(1, n_boiler + 1)]
    par_supply.append("HeatSys1_SBypass_Branch")
    par_str = ",\n".join(f"  {b}" for b in par_supply)

    parts.append(
        "ConnectorList, HeatSys1_Supply_Connectors,\n"
        "  Connector:Splitter, HeatSys1_Supply_Splitter,\n"
        "  Connector:Mixer, HeatSys1_Supply_Mixer;"
    )
    parts.append(f"Connector:Splitter, HeatSys1_Supply_Splitter, HeatSys1_Pump_Branch,\n{par_str};")
    parts.append(f"Connector:Mixer, HeatSys1_Supply_Mixer, HeatSys1_SOutlet_Branch,\n{par_str};")

    # --- Demand Connectors ---
    parts.append(
        "ConnectorList, HeatSys1_Demand_Connectors,\n"
        "  Connector:Splitter, HeatSys1_Demand_Splitter,\n"
        "  Connector:Mixer, HeatSys1_Demand_Mixer;"
    )
    parts.append(
        "Connector:Splitter, HeatSys1_Demand_Splitter, HeatSys1_DInlet_Branch,\n"
        "  HeatSys1_HeatCoil_Branch,\n"
        "  HeatSys1_DBypass_Branch;"
    )
    parts.append(
        "Connector:Mixer, HeatSys1_Demand_Mixer, HeatSys1_DOutlet_Branch,\n"
        "  HeatSys1_HeatCoil_Branch,\n"
        "  HeatSys1_DBypass_Branch;"
    )

    # --- Equipment Operation Scheme ---
    equip_items = [f"  Boiler:HotWater, HeatSys1 Boiler{i}" for i in range(1, n_boiler + 1)]
    parts.append(
        "PlantEquipmentOperationSchemes, HeatSys1_OpScheme,\n"
        "  PlantEquipmentOperation:HeatingLoad, HeatSys1_HeatingOp, Always On;"
    )
    parts.append("PlantEquipmentOperation:HeatingLoad, HeatSys1_HeatingOp, 0, 100000000, HeatSys1_Equip;")
    parts.append("PlantEquipmentList, HeatSys1_Equip,\n" + ",\n".join(equip_items) + ";")

    # --- PlantLoop ---
    parts.append("""\
PlantLoop,
  HeatSys1,                      !- Name
  Water,                         !- Fluid Type
  ,                              !- User Fluid Type
  HeatSys1_OpScheme,             !- Plant Equipment Operation Scheme Name
  HeatSys1_Supply_Outlet,        !- Loop Temperature Setpoint Node Name
  100,                           !- Maximum Loop Temperature {C}
  10,                            !- Minimum Loop Temperature {C}
  autosize,                      !- Maximum Loop Flow Rate {m3/s}
  0,                             !- Minimum Loop Flow Rate {m3/s}
  autocalculate,                 !- Plant Loop Volume {m3}
  HeatSys1_Supply_Inlet,         !- Plant Side Inlet Node Name
  HeatSys1_Supply_Outlet,        !- Plant Side Outlet Node Name
  HeatSys1_Supply_Branches,      !- Plant Side Branch List Name
  HeatSys1_Supply_Connectors,    !- Plant Side Connector List Name
  HeatSys1_Demand_Inlet,         !- Demand Side Inlet Node Name
  HeatSys1_Demand_Outlet,        !- Demand Side Outlet Node Name
  HeatSys1_Demand_Branches,      !- Demand Side Branch List Name
  HeatSys1_Demand_Connectors,    !- Demand Side Connector List Name
  Optimal,                       !- Load Distribution Scheme
  ,                              !- Availability Manager List Name
  SingleSetpoint;                !- Plant Loop Demand Calculation Scheme""")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Air Loop HVAC
# ---------------------------------------------------------------------------


def _air_loop(zone_names: list[str], has_eco: bool, eco_type: str) -> str:
    """Generate AirLoopHVAC with OA system, coils, and fan."""
    parts: list[str] = []

    eco_setting = eco_type if has_eco else "NoEconomizer"

    # --- Sizing:System ---
    parts.append("""\
! --- Air Loop HVAC ---

Sizing:System,
  VAV_1,                         !- AirLoop Name
  Sensible,                      !- Type of Load to Size On
  autosize,                      !- Design Outdoor Air Flow Rate {m3/s}
  0.3,                           !- Central Heating Maximum System Air Flow Ratio
  7.0,                           !- Preheat Design Temperature {C}
  0.008,                         !- Preheat Design Humidity Ratio {kgWater/kgDryAir}
  12.8,                          !- Precool Design Temperature {C}
  0.008,                         !- Precool Design Humidity Ratio {kgWater/kgDryAir}
  12.8,                          !- Central Cooling Design Supply Air Temperature {C}
  16.7,                          !- Central Heating Design Supply Air Temperature {C}
  NonCoincident,                 !- Type of Zone Sum to Use
  No,                            !- 100% Outdoor Air in Cooling
  No,                            !- 100% Outdoor Air in Heating
  0.0085,                        !- Central Cooling Design Supply Air Humidity Ratio {kgWater/kgDryAir}
  0.008,                         !- Central Heating Design Supply Air Humidity Ratio {kgWater/kgDryAir}
  DesignDay,                     !- Cooling Supply Air Flow Rate Method
  0,                             !- Cooling Supply Air Flow Rate {m3/s}
  ,                              !- Cooling Supply Air Flow Rate Per Floor Area {m3/s-m2}
  ,                              !- Cooling Fraction of Autosized Cooling Supply Air Flow Rate
  ,                              !- Cooling Supply Air Flow Rate Per Unit Cooling Capacity {m3/s-W}
  DesignDay,                     !- Heating Supply Air Flow Rate Method
  0,                             !- Heating Supply Air Flow Rate {m3/s}
  ,                              !- Heating Supply Air Flow Rate Per Floor Area {m3/s-m2}
  ,                              !- Heating Fraction of Autosized Heating Supply Air Flow Rate
  ,                              !- Heating Fraction of Autosized Cooling Supply Air Flow Rate
  ,                              !- Heating Supply Air Flow Rate Per Unit Heating Capacity {m3/s-W}
  ,                              !- System Outdoor Air Method
  ,                              !- Zone Maximum Outdoor Air Fraction {dimensionless}
  CoolingDesignCapacity,         !- Cooling Design Capacity Method
  autosize,                      !- Cooling Design Capacity {W}
  ,                              !- Cooling Design Capacity Per Floor Area {W/m2}
  ,                              !- Fraction of Autosized Cooling Design Capacity
  HeatingDesignCapacity,         !- Heating Design Capacity Method
  autosize,                      !- Heating Design Capacity {W}
  ,                              !- Heating Design Capacity Per Floor Area {W/m2}
  ;                              !- Fraction of Autosized Heating Design Capacity""")

    # --- Cooling Coil ---
    parts.append("""\
Coil:Cooling:Water,
  VAV_1_CoolCoil,                !- Name
  Always On,                     !- Availability Schedule Name
  autosize,                      !- Design Water Flow Rate {m3/s}
  autosize,                      !- Design Air Flow Rate {m3/s}
  autosize,                      !- Design Inlet Water Temperature {C}
  autosize,                      !- Design Inlet Air Temperature {C}
  autosize,                      !- Design Outlet Air Temperature {C}
  autosize,                      !- Design Inlet Air Humidity Ratio {kgWater/kgDryAir}
  autosize,                      !- Design Outlet Air Humidity Ratio {kgWater/kgDryAir}
  VAV_1_CoolCoil_CW_Inlet,      !- Water Inlet Node Name
  VAV_1_CoolCoil_CW_Outlet,     !- Water Outlet Node Name
  VAV_1_MixedAir,                !- Air Inlet Node Name
  VAV_1_CoolCoil_Outlet,         !- Air Outlet Node Name
  SimpleAnalysis,                !- Type of Analysis
  CrossFlow;                     !- Heat Exchanger Configuration""")

    # --- Heating Coil (preheat) ---
    parts.append("""\
Coil:Heating:Water,
  VAV_1_HeatCoil,                !- Name
  Always On,                     !- Availability Schedule Name
  autosize,                      !- U-Factor Times Area Value {W/K}
  autosize,                      !- Maximum Water Flow Rate {m3/s}
  VAV_1_HeatCoil_HW_Inlet,      !- Water Inlet Node Name
  VAV_1_HeatCoil_HW_Outlet,     !- Water Outlet Node Name
  VAV_1_CoolCoil_Outlet,         !- Air Inlet Node Name
  VAV_1_HeatCoil_Outlet,         !- Air Outlet Node Name
  UFactorTimesAreaAndDesignWaterFlowRate, !- Performance Input Method
  autosize,                      !- Rated Capacity {W}
  82.0,                          !- Rated Inlet Water Temperature {C}
  16.7,                          !- Rated Inlet Air Temperature {C}
  71.0,                          !- Rated Outlet Water Temperature {C}
  32.2,                          !- Rated Outlet Air Temperature {C}
  0.5;                           !- Rated Ratio for Air and Water Convection""")

    # --- Fan ---
    parts.append("""\
Fan:VariableVolume,
  VAV_1_Fan,                     !- Name
  Always On,                     !- Availability Schedule Name
  0.7,                           !- Fan Total Efficiency
  1000,                          !- Pressure Rise {Pa}
  autosize,                      !- Maximum Flow Rate {m3/s}
  FixedFlowRate,                 !- Fan Power Minimum Flow Rate Input Method
  ,                              !- Fan Power Minimum Flow Fraction
  0.0,                           !- Fan Power Minimum Air Flow Rate {m3/s}
  0.9,                           !- Motor Efficiency
  1.0,                           !- Motor In Airstream Fraction
  0.0407598940,                  !- Fan Power Coefficient 1
  0.08804497,                    !- Fan Power Coefficient 2
  -0.0729926,                    !- Fan Power Coefficient 3
  0.9437398,                     !- Fan Power Coefficient 4
  0,                             !- Fan Power Coefficient 5
  VAV_1_HeatCoil_Outlet,         !- Air Inlet Node Name
  VAV_1_Fan_Outlet;              !- Air Outlet Node Name""")

    # --- Supply Air Setpoint Manager ---
    parts.append("""\
SetpointManager:Scheduled,
  VAV_1_SAT_SPM,                 !- Name
  Temperature,                   !- Control Variable
  VAV_1_SAT_Schedule,            !- Schedule Name
  VAV_1_Fan_Outlet;              !- Setpoint Node or NodeList Name

Schedule:Constant,
  VAV_1_SAT_Schedule,            !- Name
  Temperature,                   !- Schedule Type Limits Name
  12.8;                          !- Hourly Value {C}

SetpointManager:MixedAir,
  VAV_1_CoolC_SPM,              !- Name
  Temperature,                   !- Control Variable
  VAV_1_Fan_Outlet,              !- Reference Setpoint Node Name
  VAV_1_HeatCoil_Outlet,         !- Fan Inlet Node Name
  VAV_1_Fan_Outlet,              !- Fan Outlet Node Name
  VAV_1_CoolCoil_Outlet;         !- Setpoint Node or NodeList Name

SetpointManager:MixedAir,
  VAV_1_HeatC_SPM,              !- Name
  Temperature,                   !- Control Variable
  VAV_1_Fan_Outlet,              !- Reference Setpoint Node Name
  VAV_1_HeatCoil_Outlet,         !- Fan Inlet Node Name
  VAV_1_Fan_Outlet,              !- Fan Outlet Node Name
  VAV_1_HeatCoil_Outlet;         !- Setpoint Node or NodeList Name

SetpointManager:MixedAir,
  VAV_1_OA_SPM,                  !- Name
  Temperature,                   !- Control Variable
  VAV_1_Fan_Outlet,              !- Reference Setpoint Node Name
  VAV_1_HeatCoil_Outlet,         !- Fan Inlet Node Name
  VAV_1_Fan_Outlet,              !- Fan Outlet Node Name
  VAV_1_MixedAir;                !- Setpoint Node or NodeList Name""")

    # --- OA System ---
    parts.append(f"""\
AirLoopHVAC:OutdoorAirSystem,
  VAV_1_OA_System,               !- Name
  VAV_1_OA_Controllers,          !- Controller List Name
  VAV_1_OA_Equipment;            !- Outdoor Air Equipment List Name

AirLoopHVAC:ControllerList,
  VAV_1_OA_Controllers,          !- Name
  Controller:OutdoorAir,         !- Controller 1 Object Type
  VAV_1_OA_Controller;           !- Controller 1 Name

Controller:OutdoorAir,
  VAV_1_OA_Controller,           !- Name
  VAV_1_Relief_Node,             !- Relief Air Outlet Node Name
  VAV_1_Supply_Inlet,            !- Return Air Node Name
  VAV_1_MixedAir,                !- Mixed Air Node Name
  VAV_1_OA_Inlet,                !- Actuator Node Name
  autosize,                      !- Minimum Outdoor Air Flow Rate {{m3/s}}
  autosize,                      !- Maximum Outdoor Air Flow Rate {{m3/s}}
  {eco_setting},                 !- Economizer Control Type
  ModulateFlow,                  !- Economizer Control Action Type
  28.0,                          !- Economizer Maximum Limit Dry-Bulb Temperature {{C}}
  64000,                         !- Economizer Maximum Limit Enthalpy {{J/kg}}
  ,                              !- Economizer Maximum Limit Dewpoint Temperature {{C}}
  ,                              !- Electronic Enthalpy Limit Curve Name
  -100,                          !- Economizer Minimum Limit Dry-Bulb Temperature {{C}}
  NoLockout,                     !- Lockout Type
  FixedMinimum;                  !- Minimum Limit Type

OutdoorAir:NodeList,
  VAV_1_OA_Inlet;                !- Node or NodeList Name 1

AirLoopHVAC:OutdoorAirSystem:EquipmentList,
  VAV_1_OA_Equipment,            !- Name
  OutdoorAir:Mixer,              !- Component 1 Object Type
  VAV_1_OA_Mixer;                !- Component 1 Name

OutdoorAir:Mixer,
  VAV_1_OA_Mixer,                !- Name
  VAV_1_MixedAir,                !- Mixed Air Node Name
  VAV_1_OA_Inlet,                !- Outdoor Air Stream Node Name
  VAV_1_Relief_Node,             !- Relief Air Stream Node Name
  VAV_1_Supply_Inlet;            !- Return Air Stream Node Name""")

    # --- AirLoop Branch (supply side: OA → CoolCoil → HeatCoil → Fan) ---
    parts.append("""\
Branch, VAV_1_Main_Branch, ,
  AirLoopHVAC:OutdoorAirSystem, VAV_1_OA_System, VAV_1_Supply_Inlet, VAV_1_MixedAir,
  Coil:Cooling:Water, VAV_1_CoolCoil, VAV_1_MixedAir, VAV_1_CoolCoil_Outlet,
  Coil:Heating:Water, VAV_1_HeatCoil, VAV_1_CoolCoil_Outlet, VAV_1_HeatCoil_Outlet,
  Fan:VariableVolume, VAV_1_Fan, VAV_1_HeatCoil_Outlet, VAV_1_Fan_Outlet;

BranchList, VAV_1_BranchList, VAV_1_Main_Branch;""")

    # --- Water Coil Controllers ---
    parts.append("""\
AirLoopHVAC:ControllerList,
  VAV_1_Controllers,             !- Name
  Controller:WaterCoil,          !- Controller 1 Object Type
  VAV_1_CoolCoil_Controller,     !- Controller 1 Name
  Controller:WaterCoil,          !- Controller 2 Object Type
  VAV_1_HeatCoil_Controller;     !- Controller 2 Name

Controller:WaterCoil,
  VAV_1_CoolCoil_Controller,     !- Name
  Temperature,                   !- Control Variable
  Reverse,                       !- Action
  Flow,                          !- Actuator Variable
  VAV_1_CoolCoil_Outlet,         !- Sensor Node Name
  VAV_1_CoolCoil_CW_Inlet,      !- Actuator Node Name
  autosize,                      !- Controller Convergence Tolerance {deltaC}
  autosize,                      !- Maximum Actuated Flow {m3/s}
  0.0;                           !- Minimum Actuated Flow {m3/s}

Controller:WaterCoil,
  VAV_1_HeatCoil_Controller,     !- Name
  Temperature,                   !- Control Variable
  Normal,                        !- Action
  Flow,                          !- Actuator Variable
  VAV_1_HeatCoil_Outlet,         !- Sensor Node Name
  VAV_1_HeatCoil_HW_Inlet,      !- Actuator Node Name
  autosize,                      !- Controller Convergence Tolerance {deltaC}
  autosize,                      !- Maximum Actuated Flow {m3/s}
  0.0;                           !- Minimum Actuated Flow {m3/s}""")

    # --- Node Lists + AirLoopHVAC ---
    parts.append("""\
NodeList, VAV_1_Supply_Outlet_Nodes, VAV_1_Fan_Outlet;
NodeList, VAV_1_Demand_Inlet_Nodes, VAV_1_Demand_Inlet;

AirLoopHVAC,
  VAV_1,                         !- Name
  VAV_1_Controllers,             !- Controller List Name
  ,                              !- Availability Manager List Name
  autosize,                      !- Design Supply Air Flow Rate {m3/s}
  VAV_1_BranchList,              !- Branch List Name
  ,                              !- Connector List Name
  VAV_1_Supply_Inlet,            !- Supply Side Inlet Node Name
  VAV_1_Demand_Outlet,           !- Demand Side Outlet Node Name
  VAV_1_Demand_Inlet_Nodes,      !- Demand Side Inlet Node Names
  VAV_1_Supply_Outlet_Nodes;     !- Supply Side Outlet Node Names""")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Zone Equipment (VAV terminals + thermostats)
# ---------------------------------------------------------------------------


def _zone_equipment(zone_names: list[str], min_airflow: float) -> str:
    """Generate per-zone HVAC equipment: sizing, VAV terminals, thermostats."""
    parts = ["! --- Zone HVAC Equipment ---"]

    for zn in zone_names:
        zone_parts = []

        # Sizing:Zone
        zone_parts.append(f"""\
Sizing:Zone,
  {zn},                          !- Zone or ZoneList Name
  SupplyAirTemperature,          !- Zone Cooling Design Supply Air Temperature Input Method
  12.8,                          !- Zone Cooling Design Supply Air Temperature {{C}}
  ,                              !- Zone Cooling Design Supply Air Temperature Difference {{deltaC}}
  SupplyAirTemperature,          !- Zone Heating Design Supply Air Temperature Input Method
  50.0,                          !- Zone Heating Design Supply Air Temperature {{C}}
  ,                              !- Zone Heating Design Supply Air Temperature Difference {{deltaC}}
  0.0085,                        !- Zone Cooling Design Supply Air Humidity Ratio {{kgWater/kgDryAir}}
  0.008,                         !- Zone Heating Design Supply Air Humidity Ratio {{kgWater/kgDryAir}}
  SZ_DSOA_{zn},                  !- Design Specification Outdoor Air Object Name
  ,                              !- Zone Heating Sizing Factor
  ,                              !- Zone Cooling Sizing Factor
  DesignDay,                     !- Cooling Design Air Flow Method
  0,                             !- Cooling Design Air Flow Rate {{m3/s}}
  ,                              !- Cooling Minimum Air Flow per Zone Floor Area {{m3/s-m2}}
  ,                              !- Cooling Minimum Air Flow {{m3/s}}
  0.0,                           !- Cooling Minimum Air Flow Fraction
  DesignDay,                     !- Heating Design Air Flow Method
  0,                             !- Heating Design Air Flow Rate {{m3/s}}
  ,                              !- Heating Maximum Air Flow per Zone Floor Area {{m3/s-m2}}
  ,                              !- Heating Maximum Air Flow {{m3/s}}
  0.3;                           !- Heating Maximum Air Flow Fraction""")

        # DesignSpecification:OutdoorAir
        zone_parts.append(f"""\
DesignSpecification:OutdoorAir,
  SZ_DSOA_{zn},                  !- Name
  Flow/Person,                   !- Outdoor Air Method
  0.006,                         !- Outdoor Air Flow per Person {{m3/s-person}}
  0.0,                           !- Outdoor Air Flow per Zone Floor Area {{m3/s-m2}}
  0.0,                           !- Outdoor Air Flow per Zone {{m3/s}}
  0.0;                           !- Outdoor Air Flow Air Changes per Hour {{1/hr}}""")

        # Electric reheat coil
        zone_parts.append(f"""\
Coil:Heating:Electric,
  {zn}_Reheat,                   !- Name
  Always On,                     !- Availability Schedule Name
  1.0,                           !- Efficiency
  autosize,                      !- Nominal Capacity {{W}}
  {zn}_Damper_Outlet,            !- Air Inlet Node Name
  {zn}_ATU_Outlet;               !- Air Outlet Node Name""")

        # VAV Terminal
        zone_parts.append(f"""\
AirTerminal:SingleDuct:VAV:Reheat,
  {zn}_VAV,                      !- Name
  Always On,                     !- Availability Schedule Name
  {zn}_Damper_Outlet,            !- Damper Air Outlet Node Name
  {zn}_ATU_Inlet,                !- Air Inlet Node Name
  autosize,                      !- Maximum Air Flow Rate {{m3/s}}
  Constant,                      !- Zone Minimum Air Flow Input Method
  {min_airflow},                 !- Constant Minimum Air Flow Fraction
  ,                              !- Fixed Minimum Air Flow Rate {{m3/s}}
  ,                              !- Minimum Air Flow Fraction Schedule Name
  Coil:Heating:Electric,         !- Reheat Coil Object Type
  {zn}_Reheat,                   !- Reheat Coil Name
  autosize,                      !- Maximum Hot Water or Steam Flow Rate {{m3/s}}
  0.0,                           !- Minimum Hot Water or Steam Flow Rate {{m3/s}}
  {zn}_ATU_Outlet,               !- Air Outlet Node Name
  0.001,                         !- Convergence Tolerance
  Normal,                        !- Damper Heating Action
  autosize,                      !- Maximum Flow per Zone Floor Area During Reheat {{m3/s-m2}}
  autosize;                      !- Maximum Flow Fraction During Reheat""")

        # Air Distribution Unit
        zone_parts.append(f"""\
ZoneHVAC:AirDistributionUnit,
  {zn}_ADU,                      !- Name
  {zn}_ATU_Outlet,               !- Air Distribution Unit Outlet Node Name
  AirTerminal:SingleDuct:VAV:Reheat, !- Air Terminal Object Type
  {zn}_VAV;                      !- Air Terminal Name""")

        # Equipment List
        zone_parts.append(f"""\
ZoneHVAC:EquipmentList,
  {zn}_EquipmentList,            !- Name
  SequentialLoad,                !- Load Distribution Scheme
  ZoneHVAC:AirDistributionUnit,  !- Zone Equipment Object Type 1
  {zn}_ADU,                      !- Zone Equipment Name 1
  1,                             !- Zone Equipment Cooling Sequence 1
  1,                             !- Zone Equipment Heating or No-Load Sequence 1
  ,                              !- Zone Equipment Sequential Cooling Fraction Schedule Name 1
  ;                              !- Zone Equipment Sequential Heating Fraction Schedule Name 1""")

        # Equipment Connections
        zone_parts.append(f"""\
ZoneHVAC:EquipmentConnections,
  {zn},                          !- Zone Name
  {zn}_EquipmentList,            !- Zone Conditioning Equipment List Name
  {zn}_ATU_Outlet,               !- Zone Air Inlet Node or NodeList Name
  ,                              !- Zone Air Exhaust Node or NodeList Name
  {zn}_AirNode,                  !- Zone Air Node Name
  {zn}_ReturnAirNode;            !- Zone Return Air Node or NodeList Name""")

        # Thermostat
        zone_parts.append(f"""\
ZoneControl:Thermostat,
  {zn}_Thermostat,               !- Name
  {zn},                          !- Zone Name
  DualSetpointControlType,       !- Control Type Schedule Name
  ThermostatSetpoint:DualSetpoint, !- Control Object Type 1
  {zn}_DualSetpoint;             !- Control Name 1

ThermostatSetpoint:DualSetpoint,
  {zn}_DualSetpoint,             !- Name
  HeatingSetpoint,               !- Heating Setpoint Temperature Schedule Name
  CoolingSetpoint;               !- Cooling Setpoint Temperature Schedule Name""")

        parts.append("\n\n".join(zone_parts))

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Supply/Return Paths
# ---------------------------------------------------------------------------


def _supply_return_paths(zone_names: list[str]) -> str:
    """Generate air loop supply/return paths for zone connections."""
    parts = ["! --- Air Loop Supply/Return Paths ---"]

    # Supply Path (zone splitter)
    splitter_outlets = ",\n".join(f"  {zn}_ATU_Inlet" for zn in zone_names)
    parts.append(f"""\
AirLoopHVAC:SupplyPath,
  VAV_1_SupplyPath,              !- Name
  VAV_1_Demand_Inlet,            !- Supply Air Path Inlet Node Name
  AirLoopHVAC:ZoneSplitter,     !- Component 1 Object Type
  VAV_1_ZoneSplitter;            !- Component 1 Name

AirLoopHVAC:ZoneSplitter,
  VAV_1_ZoneSplitter,            !- Name
  VAV_1_Demand_Inlet,            !- Inlet Node Name
{splitter_outlets};""")

    # Return Path (zone mixer)
    mixer_inlets = ",\n".join(f"  {zn}_ReturnAirNode" for zn in zone_names)
    parts.append(f"""\
AirLoopHVAC:ReturnPath,
  VAV_1_ReturnPath,              !- Name
  VAV_1_Demand_Outlet,           !- Return Air Path Outlet Node Name
  AirLoopHVAC:ZoneMixer,        !- Component 1 Object Type
  VAV_1_ZoneMixer;               !- Component 1 Name

AirLoopHVAC:ZoneMixer,
  VAV_1_ZoneMixer,               !- Name
  VAV_1_Demand_Outlet,           !- Outlet Node Name
{mixer_inlets};""")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Output Variables for Detailed HVAC
# ---------------------------------------------------------------------------


def output_variables_detailed(strategy: str) -> str:
    """Output variables appropriate for detailed HVAC systems."""
    return """\
! === Output Variables ===
Output:Variable,*,Facility Total Electric Demand Power,Hourly;
Output:Variable,*,Zone Mean Air Temperature,Hourly;

Output:Meter,Electricity:Facility,Hourly;
Output:Meter,NaturalGas:Facility,Hourly;
Output:Meter,Cooling:Electricity,Hourly;
Output:Meter,Heating:NaturalGas,Hourly;
Output:Meter,Heating:Electricity,Hourly;
Output:Meter,Fans:Electricity,Hourly;
Output:Meter,Pumps:Electricity,Hourly;

OutputControl:Table:Style,CommaAndHTML;

Output:Table:SummaryReports,
  AllSummary;
"""
