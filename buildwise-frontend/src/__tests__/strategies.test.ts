import { describe, it, expect } from "vitest";
import { STRATEGY_LABELS } from "@/constants/strategies";

describe("STRATEGY_LABELS", () => {
  it("includes baseline and all M0-M8 strategies", () => {
    expect(STRATEGY_LABELS.baseline).toBe("Baseline");
    for (let i = 0; i <= 8; i++) {
      expect(STRATEGY_LABELS[`m${i}`]).toBeDefined();
      expect(STRATEGY_LABELS[`m${i}`]).toContain(`M${i}`);
    }
  });

  it("has exactly 10 entries", () => {
    expect(Object.keys(STRATEGY_LABELS)).toHaveLength(10);
  });
});

describe("Results sort logic", () => {
  type SortKey = "strategy" | "eui" | "total" | "hvac" | "savings" | "cost" | "cost_savings";

  interface MockResult {
    strategy: string;
    eui_kwh_m2: number;
    total_energy_kwh: number;
    hvac_energy_kwh: number | null;
    savings_pct: number | null;
    annual_cost_krw: number | null;
    annual_savings_krw: number | null;
  }

  const mockData: MockResult[] = [
    { strategy: "baseline", eui_kwh_m2: 150, total_energy_kwh: 600000, hvac_energy_kwh: 400000, savings_pct: null, annual_cost_krw: 5000000, annual_savings_krw: null },
    { strategy: "m0", eui_kwh_m2: 140, total_energy_kwh: 560000, hvac_energy_kwh: 370000, savings_pct: 6.7, annual_cost_krw: 4650000, annual_savings_krw: 350000 },
    { strategy: "m7", eui_kwh_m2: 110, total_energy_kwh: 440000, hvac_energy_kwh: 280000, savings_pct: 26.7, annual_cost_krw: 3650000, annual_savings_krw: 1350000 },
    { strategy: "m3", eui_kwh_m2: 130, total_energy_kwh: 520000, hvac_energy_kwh: 340000, savings_pct: 13.3, annual_cost_krw: 4320000, annual_savings_krw: 680000 },
  ];

  function getValue(s: MockResult, key: SortKey): number | string {
    switch (key) {
      case "strategy": return STRATEGY_LABELS[s.strategy] ?? s.strategy;
      case "eui": return s.eui_kwh_m2;
      case "total": return s.total_energy_kwh;
      case "hvac": return s.hvac_energy_kwh ?? 0;
      case "savings": return s.savings_pct ?? 0;
      case "cost": return s.annual_cost_krw ?? 0;
      case "cost_savings": return s.annual_savings_krw ?? 0;
    }
  }

  function sortData(data: MockResult[], key: SortKey, dir: "asc" | "desc") {
    return [...data].sort((a, b) => {
      const va = getValue(a, key);
      const vb = getValue(b, key);
      const cmp = typeof va === "string" ? va.localeCompare(vb as string) : (va as number) - (vb as number);
      return dir === "asc" ? cmp : -cmp;
    });
  }

  it("sorts by EUI ascending", () => {
    const sorted = sortData(mockData, "eui", "asc");
    expect(sorted[0].strategy).toBe("m7");
    expect(sorted[sorted.length - 1].strategy).toBe("baseline");
  });

  it("sorts by EUI descending", () => {
    const sorted = sortData(mockData, "eui", "desc");
    expect(sorted[0].strategy).toBe("baseline");
    expect(sorted[sorted.length - 1].strategy).toBe("m7");
  });

  it("sorts by savings descending (highest first)", () => {
    const sorted = sortData(mockData, "savings", "desc");
    expect(sorted[0].strategy).toBe("m7");
    expect(sorted[0].savings_pct).toBe(26.7);
  });

  it("sorts by strategy name alphabetically", () => {
    const sorted = sortData(mockData, "strategy", "asc");
    expect(sorted[0].strategy).toBe("baseline");
  });

  it("handles null values as 0", () => {
    const sorted = sortData(mockData, "savings", "asc");
    expect(sorted[0].strategy).toBe("baseline");
    expect(sorted[0].savings_pct).toBeNull();
  });
});
