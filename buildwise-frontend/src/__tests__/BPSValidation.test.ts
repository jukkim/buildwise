import { describe, it, expect } from "vitest";

// Re-implement validation logic for testing (mirrors BPSForm.tsx validateBPS)
interface ValidationError {
  section: string;
  field: string;
  message: string;
}

function validateBPS(draft: Record<string, Record<string, unknown>>): ValidationError[] {
  const errors: ValidationError[] = [];
  const g = draft.geometry ?? {};
  const e = draft.envelope ?? {};
  const s = draft.setpoints ?? {};
  const il = draft.internal_loads ?? {};

  if ((g.num_floors_above as number) < 1)
    errors.push({ section: "geometry", field: "num_floors_above", message: "At least 1 floor required" });
  if ((g.total_floor_area_m2 as number) < 100)
    errors.push({ section: "geometry", field: "total_floor_area_m2", message: "Area must be >= 100 m2" });
  if ((g.wwr as number) > 0.95)
    errors.push({ section: "geometry", field: "wwr", message: "WWR cannot exceed 0.95" });
  if ((g.wwr as number) < 0)
    errors.push({ section: "geometry", field: "wwr", message: "WWR cannot be negative" });

  if ((e.window_shgc as number) > 0.9 || (e.window_shgc as number) < 0.1)
    errors.push({ section: "envelope", field: "window_shgc", message: "SHGC must be between 0.1 and 0.9" });

  const coolOcc = s.cooling_occupied as number;
  const heatOcc = s.heating_occupied as number;
  if (coolOcc != null && heatOcc != null && coolOcc <= heatOcc)
    errors.push({ section: "setpoints", field: "cooling_occupied", message: "Cooling setpoint must be higher than heating" });

  const coolUnocc = s.cooling_unoccupied as number;
  const heatUnocc = s.heating_unoccupied as number;
  if (coolUnocc != null && heatUnocc != null && coolUnocc <= heatUnocc)
    errors.push({ section: "setpoints", field: "cooling_unoccupied", message: "Cooling setpoint must be higher than heating" });

  if ((il.people_density as number) > 1)
    errors.push({ section: "internal_loads", field: "people_density", message: "People density seems too high (>1 ppl/m2)" });

  return errors;
}

describe("BPS Validation", () => {
  const validBPS: Record<string, Record<string, unknown>> = {
    geometry: {
      num_floors_above: 12,
      total_floor_area_m2: 46320,
      wwr: 0.38,
    },
    envelope: { window_shgc: 0.25 },
    setpoints: {
      cooling_occupied: 24,
      heating_occupied: 20,
      cooling_unoccupied: 29,
      heating_unoccupied: 15,
    },
    internal_loads: { people_density: 0.0565 },
  };

  it("returns no errors for valid BPS", () => {
    expect(validateBPS(validBPS)).toHaveLength(0);
  });

  it("rejects floors < 1", () => {
    const bps = { ...validBPS, geometry: { ...validBPS.geometry, num_floors_above: 0 } };
    const errors = validateBPS(bps);
    expect(errors.some((e) => e.field === "num_floors_above")).toBe(true);
  });

  it("rejects area < 100", () => {
    const bps = { ...validBPS, geometry: { ...validBPS.geometry, total_floor_area_m2: 50 } };
    const errors = validateBPS(bps);
    expect(errors.some((e) => e.field === "total_floor_area_m2")).toBe(true);
  });

  it("rejects WWR > 0.95", () => {
    const bps = { ...validBPS, geometry: { ...validBPS.geometry, wwr: 0.99 } };
    const errors = validateBPS(bps);
    expect(errors.some((e) => e.field === "wwr")).toBe(true);
  });

  it("rejects negative WWR", () => {
    const bps = { ...validBPS, geometry: { ...validBPS.geometry, wwr: -0.1 } };
    const errors = validateBPS(bps);
    expect(errors.some((e) => e.field === "wwr")).toBe(true);
  });

  it("rejects SHGC out of range", () => {
    const bps = { ...validBPS, envelope: { window_shgc: 0.95 } };
    const errors = validateBPS(bps);
    expect(errors.some((e) => e.field === "window_shgc")).toBe(true);
  });

  it("rejects cooling <= heating setpoint", () => {
    const bps = {
      ...validBPS,
      setpoints: { ...validBPS.setpoints, cooling_occupied: 20, heating_occupied: 24 },
    };
    const errors = validateBPS(bps);
    expect(errors.some((e) => e.field === "cooling_occupied")).toBe(true);
  });

  it("rejects people_density > 1", () => {
    const bps = { ...validBPS, internal_loads: { people_density: 1.5 } };
    const errors = validateBPS(bps);
    expect(errors.some((e) => e.field === "people_density")).toBe(true);
  });

  it("allows equal cooling and heating unoccupied to fail", () => {
    const bps = {
      ...validBPS,
      setpoints: { ...validBPS.setpoints, cooling_unoccupied: 20, heating_unoccupied: 20 },
    };
    const errors = validateBPS(bps);
    expect(errors.some((e) => e.field === "cooling_unoccupied")).toBe(true);
  });
});
