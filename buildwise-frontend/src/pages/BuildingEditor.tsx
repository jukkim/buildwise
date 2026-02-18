import { useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { buildingsApi, simulationsApi } from "@/api/client";
import BPSForm from "@/components/BPSForm";

export default function BuildingEditor() {
  const { projectId, buildingId } = useParams<{
    projectId: string;
    buildingId: string;
  }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [saveError, setSaveError] = useState<string | null>(null);

  const { data: building, isLoading } = useQuery({
    queryKey: ["building", buildingId],
    queryFn: () =>
      buildingsApi.get(projectId!, buildingId!).then((r) => r.data),
    enabled: !!projectId && !!buildingId,
  });

  const patchMutation = useMutation({
    mutationFn: (patch: Record<string, unknown>) =>
      buildingsApi.updateBps(projectId!, buildingId!, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["building", buildingId] });
      setSaveError(null);
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: { errors?: string[] } } } })
          ?.response?.data?.detail?.errors?.join("; ") ?? "Save failed";
      setSaveError(msg);
    },
  });

  const simMutation = useMutation({
    mutationFn: () => simulationsApi.start(buildingId!),
    onSuccess: (res) => {
      navigate(`/simulations/${res.data.config_id}/progress`);
    },
  });

  if (isLoading || !building) return <div className="text-gray-500">Loading...</div>;

  const bps = building.bps as Record<string, Record<string, unknown>>;

  return (
    <div>
      <Link
        to={`/projects/${projectId}`}
        className="text-sm text-blue-600 hover:underline"
      >
        &larr; Back to Project
      </Link>

      <div className="mt-2 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{building.name}</h1>
          <p className="text-sm text-gray-500">
            {building.building_type} &middot; v{building.bps_version}
          </p>
        </div>
        <button
          onClick={() => simMutation.mutate()}
          disabled={simMutation.isPending}
          className="rounded-lg bg-green-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
        >
          {simMutation.isPending ? "Starting..." : "Run Simulation"}
        </button>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {/* BPS Edit Form */}
        <BPSForm
          bps={bps}
          onSave={(patch) => patchMutation.mutate(patch)}
          saving={patchMutation.isPending}
          error={saveError}
        />

        {/* Right column: summary + 3D placeholder */}
        <div className="space-y-6">
          {/* Quick summary */}
          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <h3 className="mb-3 font-semibold text-gray-800">Summary</h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Location</dt>
                <dd className="text-gray-900">
                  {(bps.location?.city as string) ?? "-"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Floors</dt>
                <dd className="text-gray-900">
                  {(bps.geometry?.num_floors_above as number) ?? "-"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Total Area</dt>
                <dd className="text-gray-900">
                  {bps.geometry?.total_floor_area_m2
                    ? `${Number(bps.geometry.total_floor_area_m2).toLocaleString()} m2`
                    : "-"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">HVAC System</dt>
                <dd className="text-gray-900">
                  {(bps.hvac?.system_type as string) ?? "-"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">WWR</dt>
                <dd className="text-gray-900">
                  {bps.geometry?.wwr != null ? String(bps.geometry.wwr) : "-"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Cooling Setpoint</dt>
                <dd className="text-gray-900">
                  {(bps.setpoints?.cooling_occupied as number) ?? 24}°C
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Heating Setpoint</dt>
                <dd className="text-gray-900">
                  {(bps.setpoints?.heating_occupied as number) ?? 20}°C
                </dd>
              </div>
            </dl>
          </div>

          {/* 3D Viewer placeholder */}
          <div className="flex items-center justify-center rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 p-16">
            <p className="text-gray-400">3D Building Viewer (Phase 2)</p>
          </div>
        </div>
      </div>
    </div>
  );
}
