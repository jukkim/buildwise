import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { buildingsApi } from "@/api/client";

export default function BuildingEditor() {
  const { projectId, buildingId } = useParams<{
    projectId: string;
    buildingId: string;
  }>();

  const { data: building, isLoading } = useQuery({
    queryKey: ["building", buildingId],
    queryFn: () =>
      buildingsApi.get(projectId!, buildingId!).then((r) => r.data),
    enabled: !!projectId && !!buildingId,
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

      <h1 className="mt-2 text-2xl font-bold text-gray-900">{building.name}</h1>
      <p className="text-sm text-gray-500">
        {building.building_type} &middot; v{building.bps_version}
      </p>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {/* BPS Summary */}
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <h3 className="mb-3 font-semibold text-gray-800">Building Parameters</h3>
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
          </dl>
        </div>

        {/* 3D Viewer placeholder */}
        <div className="flex items-center justify-center rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 p-12">
          <p className="text-gray-400">3D Building Viewer (Phase 2)</p>
        </div>
      </div>
    </div>
  );
}
