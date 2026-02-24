import { useState, useRef, useEffect, lazy, Suspense } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  buildingsApi,
  projectsApi,
  simulationsApi,
  type SimulationHistoryItem,
} from "@/api/client";
import { showToast } from "@/components/Toast";
import useDocumentTitle from "@/hooks/useDocumentTitle";
import BPSForm from "@/components/BPSForm";
import { type BuildingViewerProps } from "@/components/BuildingViewer3D";
import { Skeleton } from "@/components/Skeleton";
import timeAgo from "@/utils/timeAgo";
import Breadcrumb from "@/components/Breadcrumb";
import { CITIES } from "@/constants/cities";

const BuildingViewer3D = lazy(() => import("@/components/BuildingViewer3D"));

const PERIODS = [
  { value: "1year", label: "Full Year" },
  { value: "1month_summer", label: "Summer Month (Aug)" },
  { value: "1month_winter", label: "Winter Month (Jan)" },
];

export default function BuildingEditor() {
  const { projectId, buildingId } = useParams<{
    projectId: string;
    buildingId: string;
  }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [saveError, setSaveError] = useState<string | null>(null);
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [showSimDialog, setShowSimDialog] = useState(false);
  const [simCity, setSimCity] = useState("Seoul");
  const [simPeriod, setSimPeriod] = useState("1year");
  const [multiCityMode, setMultiCityMode] = useState(false);
  const [selectedCities, setSelectedCities] = useState<Set<string>>(new Set());
  const [compareMode, setCompareMode] = useState(false);
  const [compareSelected, setCompareSelected] = useState<Set<string>>(new Set());
  const [summaryCollapsed, setSummaryCollapsed] = useState(false);
  const [viewer3dFullscreen, setViewer3dFullscreen] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const simDialogRef = useRef<HTMLDivElement>(null);

  const { data: building, isLoading } = useQuery({
    queryKey: ["building", buildingId],
    queryFn: () =>
      buildingsApi.get(projectId!, buildingId!).then((r) => r.data),
    enabled: !!projectId && !!buildingId,
  });

  useDocumentTitle(building?.name ?? "Building");

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => projectsApi.get(projectId!).then((r) => r.data),
    enabled: !!projectId,
  });

  const { data: history } = useQuery({
    queryKey: ["building-simulations", buildingId],
    queryFn: () =>
      buildingsApi.simulations(projectId!, buildingId!).then((r) => r.data),
    enabled: !!projectId && !!buildingId,
  });

  const patchMutation = useMutation({
    mutationFn: (patch: Record<string, unknown>) =>
      buildingsApi.updateBps(projectId!, buildingId!, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["building", buildingId] });
      setSaveError(null);
      setLastSavedAt(new Date());
      showToast("BPS saved", "success");
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: { errors?: string[] } } } })
          ?.response?.data?.detail?.errors?.join("; ") ?? "Save failed";
      setSaveError(msg);
      showToast(msg);
    },
  });

  const renameMutation = useMutation({
    mutationFn: (name: string) =>
      buildingsApi.update(projectId!, buildingId!, { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["building", buildingId] });
      queryClient.invalidateQueries({ queryKey: ["buildings", projectId] });
      setEditingName(false);
      showToast("Building renamed", "success");
    },
    onError: () => showToast("Failed to rename building"),
  });

  const simMutation = useMutation({
    mutationFn: () => simulationsApi.start(buildingId!, simCity, simPeriod),
    onSuccess: (res) => {
      setShowSimDialog(false);
      showToast("Simulation started", "success");
      navigate(`/simulations/${res.data.config_id}/progress`);
    },
    onError: () => showToast("Failed to start simulation"),
  });

  const batchMutation = useMutation({
    mutationFn: () =>
      simulationsApi.startBatch(buildingId!, [...selectedCities], simPeriod),
    onSuccess: (res) => {
      setShowSimDialog(false);
      showToast(`${res.data.total_configs} simulations started`, "success");
      const ids = res.data.config_ids.join(",");
      navigate(`/compare/progress?configs=${ids}`);
    },
    onError: () => showToast("Failed to start batch simulation"),
  });

  if (isLoading || !building) return (
    <div className="space-y-4">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-64" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-96 rounded-lg" />
        <div className="space-y-4">
          <Skeleton className="h-48 rounded-lg" />
          <Skeleton className="h-48 rounded-lg" />
        </div>
      </div>
    </div>
  );

  const bps = building.bps as Record<string, Record<string, unknown>>;
  const locationCity = (bps.location?.city as string) ?? "Seoul";

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (!file || !file.name.endsWith(".json")) {
      showToast("Please drop a .json file");
      return;
    }
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const imported = JSON.parse(ev.target?.result as string);
        if (typeof imported !== "object" || !imported) throw new Error("Invalid");
        patchMutation.mutate(imported);
        showToast("BPS imported via drop", "success");
      } catch {
        showToast("Invalid BPS JSON file");
      }
    };
    reader.readAsText(file);
  };

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className={isDragging ? "ring-2 ring-blue-400 ring-inset rounded-lg" : ""}
    >
      {isDragging && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-blue-50/80 pointer-events-none">
          <p className="text-lg font-medium text-blue-600">Drop BPS JSON file to import</p>
        </div>
      )}
      <Breadcrumb items={[
        { label: "Projects", to: "/projects" },
        { label: project?.name ?? "Project", to: `/projects/${projectId}` },
        { label: building.name },
      ]} />

      <div className="mt-2 flex items-center justify-between flex-wrap gap-2">
        <div>
          {editingName ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={nameValue}
                onChange={(e) => setNameValue(e.target.value.slice(0, 50))}
                maxLength={50}
                className="rounded border border-blue-300 px-2 py-1 text-2xl font-bold"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter" && nameValue.trim()) renameMutation.mutate(nameValue);
                  if (e.key === "Escape") setEditingName(false);
                }}
              />
              <span className="text-xs text-gray-400">{nameValue.length}/50</span>
              <button
                onClick={() => renameMutation.mutate(nameValue)}
                disabled={!nameValue.trim() || renameMutation.isPending}
                className="rounded bg-blue-600 px-2 py-1 text-xs text-white hover:bg-blue-700 disabled:opacity-50"
              >
                Save
              </button>
              <button
                onClick={() => setEditingName(false)}
                className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-600"
              >
                Cancel
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">{building.name}</h1>
              <button
                onClick={() => { setEditingName(true); setNameValue(building.name); }}
                className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                title="Rename building"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </button>
            </div>
          )}
          <p className="text-sm text-gray-500">
            {building.building_type.replace(/_/g, " ")} &middot; v{building.bps_version}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              const reader = new FileReader();
              reader.onload = (ev) => {
                try {
                  const imported = JSON.parse(ev.target?.result as string);
                  if (typeof imported !== "object" || !imported) throw new Error("Invalid JSON");
                  patchMutation.mutate(imported);
                  showToast("BPS imported", "success");
                } catch {
                  showToast("Invalid BPS JSON file");
                }
              };
              reader.readAsText(file);
              e.target.value = "";
            }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 sm:px-4 sm:py-2.5"
          >
            <span className="hidden sm:inline">Import </span>BPS
          </button>
          <button
            onClick={() => {
              const blob = new Blob([JSON.stringify(building.bps, null, 2)], { type: "application/json" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `${building.name.replace(/\s+/g, "_")}_bps.json`;
              a.click();
              URL.revokeObjectURL(url);
              showToast("BPS exported", "success");
            }}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 sm:px-4 sm:py-2.5"
          >
            Export<span className="hidden sm:inline"> BPS</span>
          </button>
          <button
            onClick={() => {
              setSimCity(locationCity);
              setShowSimDialog(true);
            }}
            className="rounded-lg bg-gradient-to-r from-green-600 to-emerald-500 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-green-500/25 hover:shadow-lg hover:shadow-green-500/30 hover:from-green-500 hover:to-emerald-400 active:scale-[0.98] sm:px-6 sm:py-3"
          >
            <span className="hidden sm:inline">Run </span>Simulate
          </button>
        </div>
      </div>

      {/* Simulation start dialog */}
      {showSimDialog && (
        <SimDialogPortal
          dialogRef={simDialogRef}
          onClose={() => setShowSimDialog(false)}
        >
          <div ref={simDialogRef} className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h3 id="sim-dialog-title" className="text-lg font-semibold text-gray-900">Start Simulation</h3>
            <p className="mt-1 text-sm text-gray-500">
              Configure simulation parameters for {building.name}
            </p>

            <div className="mt-4 space-y-4">
              {/* Multi-city toggle */}
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-gray-700">Multi-City Compare</label>
                <button
                  type="button"
                  role="switch"
                  aria-checked={multiCityMode}
                  onClick={() => {
                    setMultiCityMode((v) => !v);
                    if (!multiCityMode) setSelectedCities(new Set([locationCity]));
                  }}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${multiCityMode ? "bg-green-600" : "bg-gray-300"}`}
                >
                  <span className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${multiCityMode ? "translate-x-6" : "translate-x-1"}`} />
                </button>
              </div>

              {multiCityMode ? (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-700">
                      Select Cities ({selectedCities.size}/10)
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        setSelectedCities(
                          selectedCities.size === CITIES.length
                            ? new Set([locationCity])
                            : new Set(CITIES),
                        )
                      }
                      className="text-xs text-blue-600 hover:underline"
                    >
                      {selectedCities.size === CITIES.length ? "Deselect All" : "Select All"}
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {CITIES.map((c) => (
                      <label
                        key={c}
                        className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm cursor-pointer transition-colors ${
                          selectedCities.has(c)
                            ? "border-green-300 bg-green-50 text-green-800"
                            : "border-gray-200 hover:bg-gray-50 text-gray-700"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedCities.has(c)}
                          onChange={() => {
                            setSelectedCities((prev) => {
                              const next = new Set(prev);
                              if (next.has(c)) next.delete(c);
                              else next.add(c);
                              return next;
                            });
                          }}
                          className="rounded border-gray-300 text-green-600 focus:ring-green-500"
                        />
                        {c}
                      </label>
                    ))}
                  </div>
                </div>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Climate City</label>
                  <select
                    value={simCity}
                    onChange={(e) => setSimCity(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                  >
                    {CITIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Simulation Period</label>
                <select
                  value={simPeriod}
                  onChange={(e) => setSimPeriod(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                >
                  {PERIODS.map((p) => (
                    <option key={p.value} value={p.value}>{p.label}</option>
                  ))}
                </select>
              </div>

              <div className="rounded-lg bg-gray-50 p-3 text-xs text-gray-500 space-y-1">
                <p>All available strategies (baseline + M0~M8) will be simulated in parallel.</p>
                <p className="text-gray-400">
                  {multiCityMode
                    ? `${selectedCities.size} cities × all strategies. Uses ${selectedCities.size} simulation credits.`
                    : "Estimated time: ~2-5 minutes depending on building complexity."}
                </p>
              </div>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setShowSimDialog(false)}
                className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
              {multiCityMode ? (
                <button
                  onClick={() => batchMutation.mutate()}
                  disabled={batchMutation.isPending || selectedCities.size < 2}
                  className="rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                >
                  {batchMutation.isPending
                    ? "Starting..."
                    : `Start ${selectedCities.size} Simulations`}
                </button>
              ) : (
                <button
                  onClick={() => simMutation.mutate()}
                  disabled={simMutation.isPending}
                  className="rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                >
                  {simMutation.isPending ? "Starting..." : "Start Simulation"}
                </button>
              )}
            </div>
          </div>
        </SimDialogPortal>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {/* BPS Edit Form */}
        <div>
          {(() => {
            const sections = ["location", "geometry", "envelope", "hvac", "setpoints", "internal_loads", "schedules"];
            const filled = sections.filter((s) => {
              const sec = bps[s];
              return sec && Object.keys(sec).length > 0;
            }).length;
            const pct = Math.round((filled / sections.length) * 100);
            return (
              <div className="mb-2 flex items-center gap-2 text-xs text-gray-400">
                <div className="h-1.5 flex-1 rounded-full bg-gray-200 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${pct === 100 ? "bg-green-500" : "bg-blue-500"}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span>{filled}/{sections.length} sections ({pct}%)</span>
              </div>
            );
          })()}
          <BPSForm
            bps={bps}
            onSave={(patch) => patchMutation.mutate(patch)}
            saving={patchMutation.isPending}
            error={saveError}
          />
          {lastSavedAt && (
            <p className="mt-2 text-xs text-gray-400 text-right">
              Last saved {lastSavedAt.toLocaleTimeString()}
            </p>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Quick summary */}
          <div className="rounded-xl bg-white shadow-sm">
            <button
              onClick={() => setSummaryCollapsed((v) => !v)}
              className="flex w-full items-center justify-between p-5 text-left"
            >
              <h3 className="font-semibold text-gray-800">Summary</h3>
              <svg className={`h-5 w-5 text-gray-400 transition-transform ${summaryCollapsed ? "" : "rotate-180"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {!summaryCollapsed && (
              <dl className="space-y-2 px-5 pb-5 text-sm">
                {(() => {
                  const required = ["location", "geometry", "hvac"];
                  const missing = required.filter((s) => !bps[s] || Object.keys(bps[s]).length === 0);
                  return missing.length > 0 ? (
                    <div className="flex items-center gap-1.5 rounded bg-amber-50 px-2 py-1.5 text-xs text-amber-600 mb-2">
                      <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                      </svg>
                      Missing: {missing.join(", ")}
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5 rounded bg-green-50 px-2 py-1.5 text-xs text-green-600 mb-2">
                      <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      Ready to simulate
                    </div>
                  );
                })()}
                <SummaryRow label="Location" value={locationCity} />
                <SummaryRow label="Floors" value={String(bps.geometry?.num_floors_above ?? "-")} />
                <SummaryRow
                  label="Total Area"
                  value={bps.geometry?.total_floor_area_m2
                    ? `${Number(bps.geometry.total_floor_area_m2).toLocaleString()} m2`
                    : "-"}
                />
                <SummaryRow label="HVAC" value={(bps.hvac?.system_type as string)?.replace(/_/g, " ") ?? "-"} />
                <SummaryRow label="WWR" value={bps.geometry?.wwr != null ? String(bps.geometry.wwr) : "-"} />
                <SummaryRow label="Wall" value={(bps.envelope?.wall_type as string)?.replace(/_/g, " ") ?? "-"} />
                <SummaryRow label="Window" value={(bps.envelope?.window_type as string)?.replace(/_/g, " ") ?? "-"} />
                <SummaryRow label="Cooling" value={`${(bps.setpoints?.cooling_occupied as number) ?? 24}°C`} />
                <SummaryRow label="Heating" value={`${(bps.setpoints?.heating_occupied as number) ?? 20}°C`} />
                <SummaryRow label="Lighting" value={bps.internal_loads?.lighting_power_density != null ? `${bps.internal_loads.lighting_power_density} W/m2` : "-"} />
                <SummaryRow label="BPS Version" value={`v${building.bps_version}`} />
                <SummaryRow
                  label="BPS Fields"
                  value={`${Object.values(bps).reduce((sum, sec) => sum + (sec ? Object.keys(sec).length : 0), 0)} parameters`}
                />
              </dl>
            )}
          </div>

          {/* Simulation history */}
          <div className="rounded-xl bg-white shadow-sm p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-800">Simulation History</h3>
              {history && history.filter((h) => h.completed + h.failed >= h.total && h.completed > 0).length >= 2 && (
                <button
                  onClick={() => setCompareMode((v) => { if (!v) setCompareSelected(new Set()); return !v; })}
                  className={`text-xs font-medium px-2.5 py-1 rounded-lg transition-colors ${
                    compareMode
                      ? "bg-blue-100 text-blue-700"
                      : "text-blue-600 hover:bg-blue-50"
                  }`}
                >
                  {compareMode ? "Cancel" : "Compare Cities"}
                </button>
              )}
            </div>
            {compareMode && compareSelected.size >= 2 && (
              <div className="mb-3 flex items-center gap-2">
                <button
                  onClick={() => {
                    const ids = [...compareSelected].join(",");
                    navigate(`/compare?configs=${ids}`);
                  }}
                  className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
                >
                  Compare {compareSelected.size} Cities
                </button>
                <span className="text-xs text-gray-400">Select 2+ completed simulations</span>
              </div>
            )}
            {!history || history.length === 0 ? (
              <div className="text-center py-4">
                <svg className="mx-auto h-8 w-8 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <p className="mt-2 text-sm text-gray-400">No simulations yet</p>
                <button
                  onClick={() => { setSimCity(locationCity); setShowSimDialog(true); }}
                  className="mt-2 rounded bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700"
                >
                  Run First Simulation
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {[...history].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 5).map((item: SimulationHistoryItem) => {
                  const done = item.completed + item.failed >= item.total;
                  const hasFailed = item.failed > 0;
                  const isRunning = !done;
                  const isCompletedOk = done && item.completed > 0;
                  return (
                    <div
                      key={item.config_id}
                      className="flex items-center justify-between rounded border border-gray-100 px-3 py-2"
                    >
                      <div className="text-sm flex items-center gap-2">
                        {compareMode && isCompletedOk ? (
                          <input
                            type="checkbox"
                            checked={compareSelected.has(item.config_id)}
                            onChange={() => {
                              setCompareSelected((prev) => {
                                const next = new Set(prev);
                                if (next.has(item.config_id)) next.delete(item.config_id);
                                else next.add(item.config_id);
                                return next;
                              });
                            }}
                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                          />
                        ) : (
                          <span className={`inline-block h-2 w-2 rounded-full shrink-0 ${
                            hasFailed && done ? "bg-yellow-400" :
                            done ? "bg-green-400" :
                            "bg-blue-400 animate-pulse"
                          }`} />
                        )}
                        <span className="font-medium text-gray-800">
                          {item.climate_city}
                        </span>
                        <span className="text-xs text-gray-400 flex items-center gap-0.5">
                          {item.period_type === "1month_summer" ? (
                            <svg className="h-3 w-3 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5" strokeWidth={2} /><path strokeLinecap="round" strokeWidth={2} d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" /></svg>
                          ) : item.period_type === "1month_winter" ? (
                            <svg className="h-3 w-3 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 2v20M2 12h20M4.93 4.93l14.14 14.14M19.07 4.93L4.93 19.07" /></svg>
                          ) : (
                            <svg className="h-3 w-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                          )}
                          {PERIODS.find((p) => p.value === item.period_type)?.label ?? item.period_type}
                        </span>
                        <span className="text-gray-400">
                          {item.completed}/{item.total}
                        </span>
                        <span className="text-xs text-gray-400" title={new Date(item.created_at).toLocaleString()}>
                          {timeAgo(item.created_at)}
                        </span>
                      </div>
                      <Link
                        to={
                          done
                            ? `/simulations/${item.config_id}/results`
                            : `/simulations/${item.config_id}/progress`
                        }
                        className={`text-xs hover:underline ${
                          isRunning ? "text-blue-600" : "text-green-600"
                        }`}
                      >
                        {done ? "Results" : "In Progress"}
                      </Link>
                    </div>
                  );
                })}
                {history.length > 5 && (
                  <p className="text-center text-xs text-gray-400 pt-1">
                    Showing latest 5 of {history.length} simulations
                  </p>
                )}
              </div>
            )}
          </div>

          {/* 3D Building Viewer */}
          <div className={viewer3dFullscreen
            ? "fixed inset-0 z-50 bg-white flex flex-col"
            : "rounded-xl bg-white shadow-sm overflow-hidden"
          }>
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
              <h3 className="font-semibold text-gray-800">3D Preview</h3>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">Drag to rotate · Scroll to zoom</span>
                <button
                  onClick={() => setViewer3dFullscreen((v) => !v)}
                  className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                  title={viewer3dFullscreen ? "Exit fullscreen" : "Fullscreen"}
                >
                  {viewer3dFullscreen ? (
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  ) : (
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
            <div className={viewer3dFullscreen ? "flex-1" : "h-[320px]"}>
              <Suspense fallback={
                <div className="flex h-full flex-col items-center justify-center gap-2 text-gray-400">
                  <svg className="h-6 w-6 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  <span className="text-xs">Loading 3D viewer...</span>
                </div>
              }>
                <BuildingViewer3D
                  geometry={bps.geometry as BuildingViewerProps["geometry"]}
                  buildingType={building.building_type}
                />
              </Suspense>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-gray-500">{label}</dt>
      <dd className="text-gray-900">{value}</dd>
    </div>
  );
}

function SimDialogPortal({
  dialogRef,
  onClose,
  children,
}: {
  dialogRef: React.RefObject<HTMLDivElement | null>;
  onClose: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), select, input:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [dialogRef, onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-labelledby="sim-dialog-title"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {children}
    </div>
  );
}
