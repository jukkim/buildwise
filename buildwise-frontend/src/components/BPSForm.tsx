import { useState, useEffect, useCallback, useRef } from "react";
import clsx from "clsx";

interface BPSFormProps {
  bps: Record<string, Record<string, unknown>>;
  onSave: (patch: Record<string, unknown>) => void;
  saving?: boolean;
  error?: string | null;
}

// --- Validation rules ---
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

  // Geometry
  if ((g.num_floors_above as number) < 1) errors.push({ section: "geometry", field: "num_floors_above", message: "At least 1 floor required" });
  if ((g.total_floor_area_m2 as number) < 100) errors.push({ section: "geometry", field: "total_floor_area_m2", message: "Area must be >= 100 m2" });
  if ((g.wwr as number) > 0.95) errors.push({ section: "geometry", field: "wwr", message: "WWR cannot exceed 0.95" });
  if ((g.wwr as number) < 0) errors.push({ section: "geometry", field: "wwr", message: "WWR cannot be negative" });

  // Envelope
  if ((e.window_shgc as number) > 0.9 || (e.window_shgc as number) < 0.1)
    errors.push({ section: "envelope", field: "window_shgc", message: "SHGC must be between 0.1 and 0.9" });

  // Setpoints - cooling must be higher than heating
  const coolOcc = s.cooling_occupied as number;
  const heatOcc = s.heating_occupied as number;
  if (coolOcc != null && heatOcc != null && coolOcc <= heatOcc)
    errors.push({ section: "setpoints", field: "cooling_occupied", message: "Cooling setpoint must be higher than heating" });

  const coolUnocc = s.cooling_unoccupied as number;
  const heatUnocc = s.heating_unoccupied as number;
  if (coolUnocc != null && heatUnocc != null && coolUnocc <= heatUnocc)
    errors.push({ section: "setpoints", field: "cooling_unoccupied", message: "Cooling setpoint must be higher than heating" });

  // Internal loads
  if ((il.people_density as number) > 1) errors.push({ section: "internal_loads", field: "people_density", message: "People density seems too high (>1 ppl/m2)" });

  return errors;
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
const OCCUPANCY_TYPES = [
  { value: "office_standard", label: "Office (Standard)" },
  { value: "retail", label: "Retail" },
  { value: "school", label: "School" },
  { value: "hospital_24h", label: "Hospital (24h)" },
];

type SectionKey = "geometry" | "location" | "envelope" | "hvac" | "setpoints" | "internal_loads" | "schedules";

export default function BPSForm({ bps, onSave, saving, error }: BPSFormProps) {
  const [activeSection, setActiveSection] = useState<SectionKey>("geometry");
  const [jsonView, setJsonView] = useState(false);
  const [draft, setDraft] = useState<Record<string, Record<string, unknown>>>({
    location: { ...(bps.location ?? {}) },
    geometry: { ...(bps.geometry ?? {}) },
    envelope: { ...(bps.envelope ?? {}) },
    hvac: { ...(bps.hvac ?? {}) },
    setpoints: { ...(bps.setpoints ?? {}) },
    internal_loads: { ...(bps.internal_loads ?? {}) },
    schedules: { ...(bps.schedules ?? {}) },
  });
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [showErrors, setShowErrors] = useState(false);

  // Validate on draft change
  useEffect(() => {
    setValidationErrors(validateBPS(draft));
  }, [draft]);

  const getFieldError = useCallback(
    (section: string, field: string) =>
      showErrors ? validationErrors.find((e) => e.section === section && e.field === field)?.message : undefined,
    [validationErrors, showErrors],
  );

  const sectionHasErrors = useCallback(
    (section: string) => showErrors && validationErrors.some((e) => e.section === section),
    [validationErrors, showErrors],
  );

  const update = (section: SectionKey, field: string, value: unknown) => {
    setDraft((prev) => ({
      ...prev,
      [section]: { ...prev[section], [field]: value },
    }));
  };

  const isSectionDirty = useCallback((section: SectionKey) => {
    const original = bps[section] ?? {};
    const current = draft[section];
    return Object.keys(current).some(
      (f) => JSON.stringify(current[f]) !== JSON.stringify(original[f]),
    );
  }, [bps, draft]);

  const isDirty = Object.keys(draft).some((key) => isSectionDirty(key as SectionKey));

  const handleDiscard = () => {
    setDraft({
      location: { ...(bps.location ?? {}) },
      geometry: { ...(bps.geometry ?? {}) },
      envelope: { ...(bps.envelope ?? {}) },
      hvac: { ...(bps.hvac ?? {}) },
      setpoints: { ...(bps.setpoints ?? {}) },
      internal_loads: { ...(bps.internal_loads ?? {}) },
      schedules: { ...(bps.schedules ?? {}) },
    });
    setShowErrors(false);
  };

  const handleSave = () => {
    const errors = validateBPS(draft);
    setValidationErrors(errors);
    setShowErrors(true);
    if (errors.length > 0) return;

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

  // Ctrl+S shortcut
  const saveRef = useRef(handleSave);
  saveRef.current = handleSave;
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        saveRef.current();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Warn on unsaved changes before page unload
  useEffect(() => {
    if (!isDirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  const sections: { key: SectionKey; label: string }[] = [
    { key: "geometry", label: "Geometry" },
    { key: "location", label: "Location" },
    { key: "envelope", label: "Envelope" },
    { key: "hvac", label: "HVAC" },
    { key: "internal_loads", label: "Loads" },
    { key: "schedules", label: "Schedules" },
    { key: "setpoints", label: "Setpoints" },
  ];

  const hvacType = draft.hvac.system_type as string | undefined;
  const isVAV = hvacType?.startsWith("vav_");
  const isVRF = hvacType === "vrf";

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      {/* Unsaved changes banner */}
      {isDirty && (
        <div className="flex items-center justify-between bg-amber-50 border-b border-amber-200 px-4 py-2 text-sm">
          <span className="text-amber-700">Unsaved changes</span>
          <div className="flex gap-2">
            <button onClick={handleDiscard} className="text-xs text-amber-600 hover:text-amber-800">
              Discard
            </button>
            <button onClick={handleSave} className="text-xs font-medium text-amber-800 hover:text-amber-900">
              Save
            </button>
          </div>
        </div>
      )}
      {/* Section tabs */}
      <div
        className="flex border-b border-gray-200 overflow-x-auto"
        role="tablist"
        onKeyDown={(e) => {
          if (jsonView) return;
          const idx = sections.findIndex((s) => s.key === activeSection);
          if (e.key === "ArrowRight" && idx < sections.length - 1) {
            e.preventDefault();
            setActiveSection(sections[idx + 1].key);
            (e.currentTarget.children[idx + 1] as HTMLElement)?.focus();
          } else if (e.key === "ArrowLeft" && idx > 0) {
            e.preventDefault();
            setActiveSection(sections[idx - 1].key);
            (e.currentTarget.children[idx - 1] as HTMLElement)?.focus();
          }
        }}
      >
        {sections.map((s) => (
          <button
            key={s.key}
            role="tab"
            aria-selected={!jsonView && activeSection === s.key}
            tabIndex={!jsonView && activeSection === s.key ? 0 : -1}
            onClick={() => { setActiveSection(s.key); setJsonView(false); }}
            className={clsx(
              "whitespace-nowrap px-3 py-3 text-sm font-medium transition-colors",
              !jsonView && activeSection === s.key
                ? "border-b-2 border-blue-600 text-blue-600"
                : "text-gray-500 hover:text-gray-700",
              sectionHasErrors(s.key) && "text-red-500",
            )}
          >
            {s.label}
            {sectionHasErrors(s.key) ? (
              <span className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-red-500" />
            ) : isSectionDirty(s.key) ? (
              <>
                <span className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-blue-500" />
                {(() => {
                  const orig = bps[s.key] ?? {};
                  const cur = draft[s.key];
                  const count = Object.keys(cur).filter(
                    (f) => JSON.stringify(cur[f]) !== JSON.stringify(orig[f]),
                  ).length;
                  return count > 0 ? (
                    <span className="ml-0.5 text-[10px] text-blue-400">{count}</span>
                  ) : null;
                })()}
              </>
            ) : null}
          </button>
        ))}
        <button
          onClick={() => setJsonView(!jsonView)}
          className={clsx(
            "ml-auto whitespace-nowrap px-3 py-3 text-xs font-mono transition-colors",
            jsonView ? "border-b-2 border-blue-600 text-blue-600" : "text-gray-400 hover:text-gray-600",
          )}
        >
          JSON
        </button>
      </div>

      <div className="p-5 space-y-4">
        {jsonView ? (
          <div className="relative">
            <button
              onClick={() => {
                navigator.clipboard.writeText(JSON.stringify(draft, null, 2));
              }}
              className="absolute right-2 top-2 rounded bg-gray-200 px-2 py-1 text-xs text-gray-600 hover:bg-gray-300"
              title="Copy JSON to clipboard"
            >
              Copy
            </button>
            <pre className="max-h-96 overflow-auto rounded bg-gray-50 p-3 text-xs text-gray-700 font-mono leading-relaxed">
              {JSON.stringify(draft, null, 2)}
            </pre>
          </div>
        ) : (
        <>
        {activeSection === "geometry" && (
          <>
            <NumField label="Floors Above" value={draft.geometry.num_floors_above as number} min={1} max={100}
              onChange={(v) => update("geometry", "num_floors_above", v)} error={getFieldError("geometry", "num_floors_above")}
              hint="Number of above-ground floors" />
            <NumField label="Total Floor Area (m2)" value={draft.geometry.total_floor_area_m2 as number} min={100} max={500000}
              onChange={(v) => update("geometry", "total_floor_area_m2", v)} error={getFieldError("geometry", "total_floor_area_m2")}
              hint="Gross floor area including all floors" />
            <NumField label="Floor-to-Floor Height (m)" value={draft.geometry.floor_to_floor_height_m as number} min={2.5} max={10} step={0.1}
              onChange={(v) => update("geometry", "floor_to_floor_height_m", v)}
              hint="Typical: 3.5-4.0m for offices" />
            <NumField label="Aspect Ratio" value={draft.geometry.aspect_ratio as number} min={0.5} max={5} step={0.1}
              onChange={(v) => update("geometry", "aspect_ratio", v)}
              hint="Length/width ratio of building footprint" />
            <NumField label="WWR" value={draft.geometry.wwr as number} min={0} max={0.95} step={0.01}
              onChange={(v) => update("geometry", "wwr", v)} error={getFieldError("geometry", "wwr")}
              hint="Window-to-Wall Ratio (0.0-0.95)" />
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
              onChange={(v) => update("envelope", "window_shgc", v)} error={getFieldError("envelope", "window_shgc")}
              hint="Solar Heat Gain Coefficient (lower = less solar heat)" />
            <NumField label="Infiltration (ACH)" value={draft.envelope.infiltration_ach as number} min={0} max={2} step={0.1}
              onChange={(v) => update("envelope", "infiltration_ach", v)}
              hint="Air changes per hour through envelope leaks" />
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

        {activeSection === "internal_loads" && (
          <>
            <NumField label="People Density (ppl/m2)" value={(draft.internal_loads.people_density as number) ?? 0.0565} min={0.01} max={1} step={0.001}
              onChange={(v) => update("internal_loads", "people_density", v)} error={getFieldError("internal_loads", "people_density")} />
            <NumField label="Lighting Power (W/m2)" value={(draft.internal_loads.lighting_power_density as number) ?? 10.76} min={1} max={50} step={0.1}
              onChange={(v) => update("internal_loads", "lighting_power_density", v)} />
            <NumField label="Equipment Power (W/m2)" value={(draft.internal_loads.equipment_power_density as number) ?? 10.76} min={1} max={50} step={0.1}
              onChange={(v) => update("internal_loads", "equipment_power_density", v)} />
          </>
        )}

        {activeSection === "schedules" && (
          <SelectField label="Occupancy Type" value={(draft.schedules.occupancy_type as string) ?? "office_standard"} options={OCCUPANCY_TYPES}
            onChange={(v) => update("schedules", "occupancy_type", v)} />
        )}

        {activeSection === "setpoints" && (
          <>
            <NumField label="Cooling (Occupied)" value={draft.setpoints.cooling_occupied as number} min={18} max={30} step={0.5}
              onChange={(v) => update("setpoints", "cooling_occupied", v)} unit="°C" error={getFieldError("setpoints", "cooling_occupied")}
              hint="Typical office: 24-26°C" />
            <NumField label="Heating (Occupied)" value={draft.setpoints.heating_occupied as number} min={15} max={25} step={0.5}
              onChange={(v) => update("setpoints", "heating_occupied", v)} unit="°C"
              hint="Typical office: 20-22°C" />
            <NumField label="Cooling (Unoccupied)" value={draft.setpoints.cooling_unoccupied as number} min={25} max={35} step={0.5}
              onChange={(v) => update("setpoints", "cooling_unoccupied", v)} unit="°C" error={getFieldError("setpoints", "cooling_unoccupied")}
              hint="Setback during unoccupied hours" />
            <NumField label="Heating (Unoccupied)" value={draft.setpoints.heating_unoccupied as number} min={10} max={20} step={0.5}
              onChange={(v) => update("setpoints", "heating_unoccupied", v)} unit="°C"
              hint="Setback during unoccupied hours" />
          </>
        )}
        </>
        )}
      </div>

      {/* Section navigation */}
      {(() => {
        const idx = sections.findIndex((s) => s.key === activeSection);
        return (
          <div className="flex items-center justify-between border-t border-gray-200 px-5 py-2">
            <button
              onClick={() => idx > 0 && setActiveSection(sections[idx - 1].key)}
              disabled={idx === 0}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              {idx > 0 ? sections[idx - 1].label : ""}
            </button>
            <div className="flex items-center gap-2">
              {isSectionDirty(activeSection) && (
                <button
                  onClick={() => {
                    setDraft((prev) => ({
                      ...prev,
                      [activeSection]: { ...(bps[activeSection] ?? {}) },
                    }));
                  }}
                  className="text-xs text-gray-400 hover:text-red-500"
                  title={`Reset ${sections[idx].label} to saved values`}
                >
                  Reset
                </button>
              )}
              <span className="text-xs text-gray-400">{idx + 1} / {sections.length}</span>
            </div>
            <button
              onClick={() => idx < sections.length - 1 && setActiveSection(sections[idx + 1].key)}
              disabled={idx === sections.length - 1}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {idx < sections.length - 1 ? sections[idx + 1].label : ""}
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        );
      })()}

      {/* Save / Discard buttons */}
      <div className="border-t border-gray-200 px-5 py-3 flex items-center justify-between">
        <div className="text-sm">
          {error && <p className="text-red-600">{error}</p>}
          {showErrors && validationErrors.length > 0 && (
            <p className="text-red-500">{validationErrors.length} validation error{validationErrors.length > 1 ? "s" : ""}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isDirty && (
            <button
              onClick={handleDiscard}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50"
            >
              Discard
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            title="Ctrl+S"
          >
            {saving ? "Saving..." : "Save Changes"}
            <kbd className="ml-2 hidden sm:inline rounded bg-blue-500 px-1 py-0.5 text-xs font-mono">Ctrl+S</kbd>
          </button>
        </div>
      </div>
    </div>
  );
}

// --- Field components ---

function NumField({
  label, value, min, max, step = 1, unit, onChange, error, hint,
}: {
  label: string; value: number; min: number; max: number; step?: number; unit?: string;
  onChange: (v: number) => void; error?: string; hint?: string;
}) {
  return (
    <div>
      <div className="flex items-center justify-between gap-4">
        <label className="text-sm text-gray-600 min-w-[160px]" title={hint}>{label}
          {hint && (
            <span className="ml-1 inline-block text-gray-300 cursor-help" title={hint}>?</span>
          )}
        </label>
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={value ?? ""}
            min={min} max={max} step={step}
            onChange={(e) => onChange(Number(e.target.value))}
            className={clsx(
              "w-28 rounded border px-2 py-1.5 text-sm text-right",
              error ? "border-red-400 bg-red-50" : "border-gray-300",
            )}
          />
          {unit && <span className="text-xs text-gray-400">{unit}</span>}
        </div>
      </div>
      {error && <p className="mt-0.5 text-right text-xs text-red-500">{error}</p>}
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
