import { useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  projectsApi,
  buildingsApi,
  templatesApi,
  simulationsApi,
  type Building,
  type BuildingTemplate,
} from "@/api/client";

const HVAC_LABELS: Record<string, string> = {
  vav_chiller_boiler: "VAV + Chiller/Boiler",
  vrf: "VRF Heat Recovery",
  psz_hp: "PSZ Heat Pump",
  psz_ac: "PSZ AC",
  vav_chiller_boiler_school: "VAV (School)",
};

export default function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showTemplates, setShowTemplates] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [deletingBuildingId, setDeletingBuildingId] = useState<string | null>(null);

  const { data: project, isLoading: projectLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => projectsApi.get(projectId!).then((r) => r.data),
    enabled: !!projectId,
  });

  const { data: buildings, isLoading: buildingsLoading } = useQuery({
    queryKey: ["buildings", projectId],
    queryFn: () => buildingsApi.list(projectId!).then((r) => r.data),
    enabled: !!projectId,
  });

  const { data: templates } = useQuery({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then((r) => r.data),
    enabled: showTemplates,
  });

  const createBuilding = useMutation({
    mutationFn: (tmpl: BuildingTemplate) =>
      buildingsApi.create(projectId!, tmpl.name, tmpl.default_bps),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["buildings", projectId] });
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      setShowTemplates(false);
    },
  });

  const startSim = useMutation({
    mutationFn: (buildingId: string) => simulationsApi.start(buildingId),
    onSuccess: (res) => {
      navigate(`/simulations/${res.data.config_id}/progress`);
    },
  });

  const updateProject = useMutation({
    mutationFn: (name: string) => projectsApi.update(projectId!, { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setEditingName(false);
    },
  });

  const deleteProject = useMutation({
    mutationFn: () => projectsApi.delete(projectId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate("/projects");
    },
  });

  const deleteBuilding = useMutation({
    mutationFn: (buildingId: string) =>
      buildingsApi.delete(projectId!, buildingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["buildings", projectId] });
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      setDeletingBuildingId(null);
    },
  });

  if (projectLoading || !project) return <div className="text-gray-500">Loading...</div>;

  return (
    <div>
      <div className="mb-6">
        <Link to="/projects" className="text-sm text-blue-600 hover:underline">
          &larr; Projects
        </Link>

        <div className="mt-2 flex items-center gap-3">
          {editingName ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={nameValue}
                onChange={(e) => setNameValue(e.target.value)}
                className="rounded border border-blue-300 px-2 py-1 text-2xl font-bold"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter" && nameValue.trim()) updateProject.mutate(nameValue);
                  if (e.key === "Escape") setEditingName(false);
                }}
              />
              <button
                onClick={() => updateProject.mutate(nameValue)}
                disabled={!nameValue.trim() || updateProject.isPending}
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
            <>
              <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
              <button
                onClick={() => { setEditingName(true); setNameValue(project.name); }}
                className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                title="Rename project"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </button>
              <button
                onClick={() => {
                  if (confirm("Delete this project and all its buildings?")) {
                    deleteProject.mutate();
                  }
                }}
                className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500"
                title="Delete project"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </>
          )}
        </div>

        {project.description && (
          <p className="mt-1 text-gray-500">{project.description}</p>
        )}
      </div>

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-800">
          Buildings {buildings && `(${buildings.length})`}
        </h2>
        <button
          onClick={() => setShowTemplates(!showTemplates)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {showTemplates ? "Cancel" : "Add Building"}
        </button>
      </div>

      {/* Template selection */}
      {showTemplates && templates && (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((tmpl: BuildingTemplate) => (
            <button
              key={tmpl.building_type}
              onClick={() => createBuilding.mutate(tmpl)}
              disabled={createBuilding.isPending}
              className="rounded-lg border border-gray-200 bg-white p-4 text-left hover:border-blue-400 hover:shadow transition-all disabled:opacity-50"
            >
              <h4 className="font-medium text-gray-900">{tmpl.name}</h4>
              <p className="mt-1 text-xs text-gray-500">{tmpl.description}</p>
              {tmpl.baseline_eui_kwh_m2 && (
                <p className="mt-2 text-xs text-gray-400">
                  Baseline EUI: {tmpl.baseline_eui_kwh_m2} kWh/m2
                </p>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Delete building confirmation */}
      {deletingBuildingId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900">Delete Building</h3>
            <p className="mt-2 text-sm text-gray-500">
              Are you sure? This will permanently delete this building and all its simulation data.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setDeletingBuildingId(null)}
                className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteBuilding.mutate(deletingBuildingId)}
                disabled={deleteBuilding.isPending}
                className="rounded bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleteBuilding.isPending ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Building list */}
      {buildingsLoading ? (
        <div className="text-gray-500">Loading buildings...</div>
      ) : !buildings || buildings.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-gray-300 p-12 text-center">
          <p className="text-gray-500">
            No buildings yet. Click "Add Building" to create one from a template.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {buildings.map((b: Building) => {
            const bps = b.bps as Record<string, Record<string, unknown>>;
            const area = bps?.geometry?.total_floor_area_m2;
            const floors = bps?.geometry?.num_floors_above;
            const hvac = bps?.hvac?.system_type as string;

            return (
              <div
                key={b.id}
                className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-5"
              >
                <div className="flex-1">
                  <Link
                    to={`/projects/${projectId}/buildings/${b.id}`}
                    className="text-base font-semibold text-gray-900 hover:text-blue-600"
                  >
                    {b.name}
                  </Link>
                  <div className="mt-1 flex flex-wrap gap-3 text-xs text-gray-500">
                    <span className="rounded bg-gray-100 px-2 py-0.5">
                      {b.building_type.replace(/_/g, " ")}
                    </span>
                    {floors && <span>{floors}F</span>}
                    {area && <span>{Number(area).toLocaleString()} m2</span>}
                    {hvac && (
                      <span>{HVAC_LABELS[hvac] ?? hvac}</span>
                    )}
                    <span>v{b.bps_version}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 ml-4">
                  <Link
                    to={`/projects/${projectId}/buildings/${b.id}`}
                    className="rounded border border-gray-300 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50"
                  >
                    Edit
                  </Link>
                  <button
                    onClick={() => startSim.mutate(b.id)}
                    disabled={startSim.isPending}
                    className="rounded bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
                  >
                    Simulate
                  </button>
                  <button
                    onClick={() => setDeletingBuildingId(b.id)}
                    className="rounded border border-red-200 px-3 py-1.5 text-xs text-red-500 hover:bg-red-50"
                  >
                    Delete
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
