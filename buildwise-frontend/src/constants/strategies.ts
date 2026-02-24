export const STRATEGY_LABELS: Record<string, string> = {
  baseline: "Baseline",
  m0: "M0 NightCycle",
  m1: "M1 Preheat/Cool",
  m2: "M2 Economizer",
  m3: "M3 Staging",
  m4: "M4 PMV 0.5",
  m5: "M5 PMV 0.7",
  m6: "M6 Integrated",
  m7: "M7 Full + PMV 0.5",
  m8: "M8 Full + PMV 0.7",
};

export const STRATEGY_DESCRIPTIONS: Record<string, string> = {
  baseline: "No energy management — HVAC runs on fixed schedule",
  m0: "Night shutdown — turns off HVAC after hours, restarts based on demand",
  m1: "Smart pre-conditioning — uses outdoor temperature to start heating/cooling early",
  m2: "Free cooling — uses cool outdoor air instead of mechanical cooling when possible",
  m3: "Chiller staging — optimizes chiller operation based on actual cooling load",
  m4: "Comfort-first setpoint — adjusts temperature dynamically for optimal comfort (PMV 0.5)",
  m5: "Energy-saving setpoint — adjusts temperature for energy savings while maintaining comfort (PMV 0.7)",
  m6: "Combined strategy — economizer + chiller staging together",
  m7: "Full optimization (comfort) — all strategies combined with comfort-priority setpoints",
  m8: "Full optimization (savings) — all strategies combined with energy-saving setpoints",
};

export const STRATEGY_SHORT_DESCRIPTIONS: Record<string, string> = {
  baseline: "Fixed schedule, no optimization",
  m0: "Night shutdown",
  m1: "Smart pre-conditioning",
  m2: "Free cooling with outdoor air",
  m3: "Chiller load optimization",
  m4: "Comfort-priority setpoint",
  m5: "Energy-saving setpoint",
  m6: "Economizer + staging",
  m7: "Full combo (comfort)",
  m8: "Full combo (savings)",
};
