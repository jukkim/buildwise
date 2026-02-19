import { useState, useRef, useEffect, lazy, Suspense } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  buildingsApi,
  simulationsApi,
  type SimulationHistoryItem,
} from "@/api/client";
import { showToast } from "@/components/Toast";
import useDocumentTitle from "@/hooks/useDocumentTitle";
import BPSForm from "@/components/BPSForm";
import { type BuildingViewerProps } from "@/components/BuildingViewer3D";
import { Skeleton } from "@/components/Skeleton";
import timeAgo from "@/utils/timeAgo";

const BuildingViewer3D = lazy(() => import("@/components/BuildingViewer3D"));

const CITIES = [
  "Seoul", "Busan", "Daegu", "Daejeon", "Gwangju",
  "Incheon", "Gangneung", "Jeju", "Cheongju", "Ulsan",
];

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
  const [summaryCollapsed, setSummaryCollapsed] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const simDialogRef = useRef<HTMLDivElement>(null);

  const { data: building, isLoading } = useQuery({
    queryKey: ["building", buildingId],
    queryFn: () =>
      buildingsApi.get(projectId!, buildingId!).then((r) => r.data),
    enabled: !!projectId && !!buildingId,
  });

  useDocumentTitle(building?.name ?? "Building");

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

  return (
    <div>
      <Link
        to={`/projects/${projectId}`}
        className="text-sm text-blue-600 hover:underline"
      >
        &larr; Back to Project
      </Link>

      <div className="mt-2 flex items-center justify-between flex-wrap gap-2">
        <div>
          {editingName ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={nameValue}
                onChange={(e) => setNameValue(e.target.value)}
                className="rounded border border-blue-300 px-2 py-1 text-2xl font-bold"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter" && nameValue.trim()) renameMutation.mutate(nameValue);
                  if (e.key === "Escape") setEditingName(false);
                }}
              />
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
              <h1 className="text-2xl font-bold text-gray-900">{building.name}</h1>
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
            className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 sm:px-5 sm:py-2.5"
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

              <div className="rounded-lg bg-gray-50 p-3 text-xs text-gray-500">
                All available strategies (baseline + M0~M8) will be simulated in parallel.
              </div>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setShowSimDialog(false)}
                className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => simMutation.mutate()}
                disabled={simMutation.isPending}
                className="rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
              >
                {simMutation.isPending ? "Starting..." : "Start Simulation"}
              </button>
            </div>
          </div>
        </SimDialogPortal>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {/* BPS Edit Form */}
        <BPSForm
          bps={bps}
          onSave={(patch) => patchMutation.mutate(patch)}
          saving={patchMutation.isPending}
          error={saveError}
        />

        {/* Right column */}
        <div className="space-y-6">
          {/* Quick summary */}
          <div className="rounded-lg border border-gray-200 bg-white">
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
              </dl>
            )}
          </div>

          {/* Simulation history */}
          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <h3 className="mb-3 font-semibold text-gray-800">Simulation History</h3>
            {!history || history.length === 0 ? (
              <p className="text-sm text-gray-400">No simulations yet.</p>
            ) : (
              <div className="space-y-2">
                {history.map((item: SimulationHistoryItem) => {
                  const done = item.completed + item.failed >= item.total;
                  const hasFailed = item.failed > 0;
                  const isRunning = !done;
                  return (
                    <div
                      key={item.config_id}
                      className="flex items-center justify-between rounded border border-gray-100 px-3 py-2"
                    >
                      <div className="text-sm flex items-center gap-2">
                        <span className={`inline-block h-2 w-2 rounded-full shrink-0 ${
                          hasFailed && done ? "bg-yellow-400" :
                          done ? "bg-green-400" :
                          "bg-blue-400 animate-pulse"
                        }`} />
                        <span className="font-medium text-gray-800">
                          {item.climate_city}
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
              </div>
            )}
          </div>

          {/* 3D Building Viewer */}
          <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
              <h3 className="font-semibold text-gray-800">3D Preview</h3>
              <span className="text-xs text-gray-400">Drag to rotate</span>
            </div>
            <div className="h-[320px]">
              <Suspense fallback={<div className="flex h-full items-center justify-center text-gray-400">Loading 3D...</div>}>
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
