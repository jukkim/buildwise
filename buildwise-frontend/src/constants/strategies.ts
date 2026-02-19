export const STRATEGY_LABELS: Record<string, string> = {
  baseline: "Baseline",
  m0: "M0 Night Stop",
  m1: "M1 Smart Start",
  m2: "M2 Economizer",
  m3: "M3 Setpoint",
  m4: "M4 Chiller",
  m5: "M5 DCV",
  m6: "M6 Integrated",
  m7: "M7 Full Normal",
  m8: "M8 Full Savings",
};

export const STRATEGY_DESCRIPTIONS: Record<string, string> = {
  baseline: "Standard operation without energy management",
  m0: "Shut off HVAC during unoccupied night hours",
  m1: "Optimize HVAC start time based on building thermal mass",
  m2: "Use outdoor air for free cooling when conditions allow",
  m3: "Dynamic temperature setpoint adjustment by occupancy",
  m4: "Optimize chiller staging and sequencing",
  m5: "Demand-controlled ventilation based on CO2 levels",
  m6: "Combined economizer + setpoint + DCV optimization",
  m7: "All strategies with standard parameters",
  m8: "All strategies with aggressive energy savings targets",
};
