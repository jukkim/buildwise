import { useState } from "react";
import clsx from "clsx";

interface BPSFormProps {
  bps: Record<string, Record<string, unknown>>;
  onSave: (patch: Record<string, unknown>) => void;
  saving?: boolean;
  error?: string | null;
}

const CITIES = [
  "Seoul", "Busan", "Daegu", "Daejeon", "Gwangju",
  "Incheon", "Gangneung", "Jeju", "Cheongju", "Ulsan",
];

const HVAC_TYPES = [
  { value: "vav_chiller_boiler", label: "VAV + Chiller/Boiler" },
  { value: "vrf", label: "VRF Heat Recovery" },
  { value: "psz_hp", label: "PSZ Heat Pump" },
  { value: "psz_ac", label: "PSZ AC" },
  { value: "vav_chiller_boiler_school", label: "VAV + Chiller/Boiler (School)" },
];

const WALL_TYPES = ["curtain_wall", "masonry", "metal_panel", "concrete", "wood_frame"];
const WINDOW_TYPES = ["single_clear", "double_clear", "double_low_e", "triple_low_e"];

type SectionKey = "geometry" | "location" | "envelope" | "hvac" | "setpoints";

export default function BPSForm({ bps, onSave, saving, error }: BPSFormProps) {
  const [activeSection, setActiveSection] = useState<SectionKey>("geometry");
  const [draft, setDraft] = useState<Record<string, Record<string, unknown>>>({
    location: { ...(bps.location ?? {}) },
    geometry: { ...(bps.geometry ?? {}) },
    envelope: { ...(bps.envelope ?? {}) },
    hvac: { ...(bps.hvac ?? {}) },
    setpoints: { ...(bps.setpoints ?? {}) },
  });

  const update = (section: SectionKey, field: string, value: unknown) => {
    setDraft((prev) => ({
      ...prev,
      [section]: { ...prev[section], [field]: value },
    }));
  };

  const handleSave = () => {
    const patch: Record<string, unknown> = {};
    for (const key of Object.keys(draft) as SectionKey[]) {
      const original = bps[key] ?? {};
      const current = draft[key];
      const changed = Object.keys(current).some(
        (f) => JSON.stringify(current[f]) !== JSON.stringify(original[f]),
      );
      if (changed) patch[key] = current;
    }
    if (Object.keys(patch).length > 0) onSave(patch);
  };

  const sections: { key: SectionKey; label: string }[] = [
    { key: "geometry", label: "Geometry" },
    { key: "location", label: "Location" },
    { key: "envelope", label: "Envelope" },
    { key: "hvac", label: "HVAC" },
    { key: "setpoints", label: "Setpoints" },
  ];

  const hvacType = draft.hvac.system_type as string | undefined;
  const isVAV = hvacType?.startsWith("vav_");
  const isVRF = hvacType === "vrf";

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      {/* Section tabs */}
      <div className="flex border-b border-gray-200 overflow-x-auto">
        {sections.map((s) => (
          <button
            key={s.key}
            onClick={() => setActiveSection(s.key)}
            className={clsx(
              "whitespace-nowrap px-4 py-3 text-sm font-medium transition-colors",
              activeSection === s.key
                ? "border-b-2 border-blue-600 text-blue-600"
                : "text-gray-500 hover:text-gray-700",
            )}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="p-5 space-y-4">
        {activeSection === "geometry" && (
          <>
            <NumField label="Floors Above" value={draft.geometry.num_floors_above as number} min={1} max={100}
              onChange={(v) => update("geometry", "num_floors_above", v)} />
            <NumField label="Total Floor Area (m2)" value={draft.geometry.total_floor_area_m2 as number} min={100} max={500000}
              onChange={(v) => update("geometry", "total_floor_area_m2", v)} />
            <NumField label="Floor-to-Floor Height (m)" value={draft.geometry.floor_to_floor_height_m as number} min={2.5} max={10} step={0.1}
              onChange={(v) => update("geometry", "floor_to_floor_height_m", v)} />
            <NumField label="Aspect Ratio" value={draft.geometry.aspect_ratio as number} min={0.5} max={5} step={0.1}
              onChange={(v) => update("geometry", "aspect_ratio", v)} />
            <NumField label="WWR" value={draft.geometry.wwr as number} min={0} max={0.95} step={0.01}
              onChange={(v) => update("geometry", "wwr", v)} />
            <NumField label="Orientation (deg)" value={draft.geometry.orientation_deg as number} min={0} max={360}
              onChange={(v) => update("geometry", "orientation_deg", v)} />
          </>
        )}

        {activeSection === "location" && (
          <SelectField label="City" value={draft.location.city as string} options={CITIES}
            onChange={(v) => update("location", "city", v)} />
        )}

        {activeSection === "envelope" && (
          <>
            <SelectField label="Wall Type" value={draft.envelope.wall_type as string} options={WALL_TYPES}
              onChange={(v) => update("envelope", "wall_type", v)} />
            <SelectField label="Window Type" value={draft.envelope.window_type as string} options={WINDOW_TYPES}
              onChange={(v) => update("envelope", "window_type", v)} />
            <NumField label="Window SHGC" value={draft.envelope.window_shgc as number} min={0.1} max={0.9} step={0.01}
              onChange={(v) => update("envelope", "window_shgc", v)} />
            <NumField label="Infiltration (ACH)" value={draft.envelope.infiltration_ach as number} min={0} max={2} step={0.1}
              onChange={(v) => update("envelope", "infiltration_ach", v)} />
          </>
        )}

        {activeSection === "hvac" && (
          <>
            <SelectField label="System Type" value={hvacType ?? ""} options={HVAC_TYPES}
              onChange={(v) => update("hvac", "system_type", v)} />
            {isVAV && (
              <>
                <NumField label="Chiller COP" value={(draft.hvac.chiller_cop as number) ?? 5.5} min={2} max={10} step={0.1}
                  onChange={(v) => update("hvac", "chiller_cop", v)} />
                <NumField label="Boiler Efficiency" value={(draft.hvac.boiler_efficiency as number) ?? 0.85} min={0.5} max={1.0} step={0.01}
                  onChange={(v) => update("hvac", "boiler_efficiency", v)} />
                <NumField label="Fan Pressure (Pa)" value={(draft.hvac.fan_total_pressure_pa as number) ?? 1000} min={200} max={3000}
                  onChange={(v) => update("hvac", "fan_total_pressure_pa", v)} />
              </>
            )}
            {isVRF && (
              <>
                <NumField label="Cooling COP" value={(draft.hvac.cooling_cop as number) ?? 4.0} min={2} max={8} step={0.1}
                  onChange={(v) => update("hvac", "cooling_cop", v)} />
                <NumField label="Heating COP" value={(draft.hvac.heating_cop as number) ?? 4.5} min={2} max={8} step={0.1}
                  onChange={(v) => update("hvac", "heating_cop", v)} />
                <NumField label="Heat Recovery Eff" value={(draft.hvac.heat_recovery_efficiency as number) ?? 0.3} min={0} max={1} step={0.05}
                  onChange={(v) => update("hvac", "heat_recovery_efficiency", v)} />
              </>
            )}
            {!isVAV && !isVRF && hvacType && (
              <>
                <NumField label="Cooling COP/EER" value={(draft.hvac.cooling_cop as number) ?? 3.5} min={2} max={8} step={0.1}
                  onChange={(v) => update("hvac", "cooling_cop", v)} />
                <NumField label="Heating COP" value={(draft.hvac.heating_cop as number) ?? 3.0} min={1} max={6} step={0.1}
                  onChange={(v) => update("hvac", "heating_cop", v)} />
              </>
            )}
          </>
        )}

        {activeSection === "setpoints" && (
          <>
            <NumField label="Cooling (Occupied)" value={draft.setpoints.cooling_occupied as number} min={18} max={30} step={0.5}
              onChange={(v) => update("setpoints", "cooling_occupied", v)} unit="°C" />
            <NumField label="Heating (Occupied)" value={draft.setpoints.heating_occupied as number} min={15} max={25} step={0.5}
              onChange={(v) => update("setpoints", "heating_occupied", v)} unit="°C" />
            <NumField label="Cooling (Unoccupied)" value={draft.setpoints.cooling_unoccupied as number} min={25} max={35} step={0.5}
              onChange={(v) => update("setpoints", "cooling_unoccupied", v)} unit="°C" />
            <NumField label="Heating (Unoccupied)" value={draft.setpoints.heating_unoccupied as number} min={10} max={20} step={0.5}
              onChange={(v) => update("setpoints", "heating_unoccupied", v)} unit="°C" />
          </>
        )}
      </div>

      {/* Save button */}
      <div className="border-t border-gray-200 px-5 py-3 flex items-center justify-between">
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          onClick={handleSave}
          disabled={saving}
          className="ml-auto rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save Changes"}
        </button>
      </div>
    </div>
  );
}

// --- Field components ---

function NumField({
  label, value, min, max, step = 1, unit, onChange,
}: {
  label: string; value: number; min: number; max: number; step?: number; unit?: string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <label className="text-sm text-gray-600 min-w-[160px]">{label}</label>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={value ?? ""}
          min={min} max={max} step={step}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-28 rounded border border-gray-300 px-2 py-1.5 text-sm text-right"
        />
        {unit && <span className="text-xs text-gray-400">{unit}</span>}
      </div>
    </div>
  );
}

function SelectField({
  label, value, options, onChange,
}: {
  label: string; value: string; options: string[] | { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <label className="text-sm text-gray-600 min-w-[160px]">{label}</label>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-gray-300 px-2 py-1.5 text-sm"
      >
        {options.map((opt) => {
          const v = typeof opt === "string" ? opt : opt.value;
          const l = typeof opt === "string" ? opt : opt.label;
          return <option key={v} value={v}>{l}</option>;
        })}
      </select>
    </div>
  );
}
