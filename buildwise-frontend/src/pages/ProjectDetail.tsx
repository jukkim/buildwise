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
import { ListSkeleton } from "@/components/Skeleton";
import ConfirmDialog from "@/components/ConfirmDialog";
import { showToast } from "@/components/Toast";
import useDocumentTitle from "@/hooks/useDocumentTitle";
import timeAgo from "@/utils/timeAgo";

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
  const [showDeleteProject, setShowDeleteProject] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<BuildingTemplate | null>(null);
  const [newBuildingName, setNewBuildingName] = useState("");

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
    mutationFn: ({ name, bps }: { name: string; bps: Record<string, unknown> }) =>
      buildingsApi.create(projectId!, name, bps),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["buildings", projectId] });
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      setShowTemplates(false);
      setSelectedTemplate(null);
      setNewBuildingName("");
      showToast("Building created", "success");
      navigate(`/projects/${projectId}/buildings/${res.data.id}`);
    },
    onError: () => showToast("Failed to create building"),
  });

  const startSim = useMutation({
    mutationFn: (buildingId: string) => simulationsApi.start(buildingId),
    onSuccess: (res) => {
      showToast("Simulation started", "success");
      navigate(`/simulations/${res.data.config_id}/progress`);
    },
    onError: () => showToast("Failed to start simulation"),
  });

  const updateProject = useMutation({
    mutationFn: (name: string) => projectsApi.update(projectId!, { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setEditingName(false);
      showToast("Project renamed", "success");
    },
    onError: () => showToast("Failed to rename project"),
  });

  const deleteProject = useMutation({
    mutationFn: () => projectsApi.delete(projectId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      showToast("Project deleted", "success");
      navigate("/projects");
    },
    onError: () => showToast("Failed to delete project"),
  });

  const cloneBuilding = useMutation({
    mutationFn: (buildingId: string) =>
      buildingsApi.clone(projectId!, buildingId),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["buildings", projectId] });
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      showToast("Building cloned", "success");
      navigate(`/projects/${projectId}/buildings/${res.data.id}`);
    },
    onError: () => showToast("Failed to clone building"),
  });

  const deleteBuilding = useMutation({
    mutationFn: (buildingId: string) =>
      buildingsApi.delete(projectId!, buildingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["buildings", projectId] });
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      setDeletingBuildingId(null);
      showToast("Building deleted", "success");
    },
    onError: () => showToast("Failed to delete building"),
  });

  useDocumentTitle(project?.name ?? "Project");

  if (projectLoading || !project) return <ListSkeleton rows={3} />;

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
                onClick={() => setShowDeleteProject(true)}
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
      {showTemplates && templates && !selectedTemplate && (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((tmpl: BuildingTemplate) => {
            const bps = tmpl.default_bps as Record<string, Record<string, unknown>>;
            const floors = bps?.geometry?.num_floors_above;
            const area = bps?.geometry?.total_floor_area_m2;
            const hvac = bps?.hvac?.system_type as string;
            return (
              <button
                key={tmpl.building_type}
                onClick={() => {
                  setSelectedTemplate(tmpl);
                  setNewBuildingName(tmpl.name);
                }}
                className="rounded-lg border border-gray-200 bg-white p-4 text-left hover:border-blue-400 hover:shadow transition-all"
              >
                <h4 className="font-medium text-gray-900">{tmpl.name}</h4>
                <p className="mt-1 text-xs text-gray-500">{tmpl.description}</p>
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  {floors != null && (
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-600">{String(floors)}F</span>
                  )}
                  {area != null && (
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-600">{Number(area).toLocaleString()} m2</span>
                  )}
                  {hvac && (
                    <span className="rounded bg-blue-50 px-1.5 py-0.5 text-blue-600">{HVAC_LABELS[hvac] ?? hvac}</span>
                  )}
                </div>
                {tmpl.baseline_eui_kwh_m2 && (
                  <p className="mt-2 text-xs text-gray-400">
                    Baseline EUI: {tmpl.baseline_eui_kwh_m2} kWh/m2
                  </p>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Name input after template selection */}
      {selectedTemplate && (
        <div className="mb-6 rounded-lg border border-blue-200 bg-blue-50 p-4">
          <p className="text-sm text-gray-600">
            Template: <span className="font-medium">{selectedTemplate.name}</span>
          </p>
          <div className="mt-3">
            <label className="block text-sm font-medium text-gray-700 mb-1">Building Name</label>
            <input
              type="text"
              value={newBuildingName}
              onChange={(e) => setNewBuildingName(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter" && newBuildingName.trim()) {
                  createBuilding.mutate({ name: newBuildingName, bps: selectedTemplate.default_bps });
                }
              }}
            />
          </div>
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => createBuilding.mutate({ name: newBuildingName, bps: selectedTemplate.default_bps })}
              disabled={!newBuildingName.trim() || createBuilding.isPending}
              className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {createBuilding.isPending ? "Creating..." : "Create Building"}
            </button>
            <button
              onClick={() => { setSelectedTemplate(null); setNewBuildingName(""); }}
              className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
            >
              Back
            </button>
          </div>
        </div>
      )}

      {/* Delete project confirmation */}
      {showDeleteProject && (
        <ConfirmDialog
          title="Delete Project"
          message="Are you sure? This will permanently delete this project and all its buildings."
          confirmLabel="Delete"
          destructive
          pending={deleteProject.isPending}
          onConfirm={() => deleteProject.mutate()}
          onCancel={() => setShowDeleteProject(false)}
        />
      )}

      {/* Delete building confirmation */}
      {deletingBuildingId && (
        <ConfirmDialog
          title="Delete Building"
          message="Are you sure? This will permanently delete this building and all its simulation data."
          confirmLabel="Delete"
          destructive
          pending={deleteBuilding.isPending}
          onConfirm={() => deleteBuilding.mutate(deletingBuildingId)}
          onCancel={() => setDeletingBuildingId(null)}
        />
      )}

      {/* Building list */}
      {buildingsLoading ? (
        <ListSkeleton rows={2} />
      ) : !buildings || buildings.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-gray-300 p-12 text-center">
          <svg className="mx-auto h-12 w-12 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
          <h3 className="mt-3 text-sm font-medium text-gray-900">No buildings yet</h3>
          <p className="mt-1 text-sm text-gray-500">Get started by adding a building from a template.</p>
          <button
            onClick={() => setShowTemplates(true)}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Add Building
          </button>
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
                className="rounded-lg border border-gray-200 bg-white p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <Link
                      to={`/projects/${projectId}/buildings/${b.id}`}
                      className="text-base font-semibold text-gray-900 hover:text-blue-600"
                    >
                      {b.name}
                    </Link>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-500">
                      <span className="rounded bg-gray-100 px-2 py-0.5">
                        {b.building_type.replace(/_/g, " ")}
                      </span>
                      {floors != null && <span>{String(floors)}F</span>}
                      {area != null && <span>{Number(area).toLocaleString()} m2</span>}
                      {hvac && (
                        <span>{HVAC_LABELS[hvac] ?? hvac}</span>
                      )}
                      <span>v{b.bps_version}</span>
                      <span title={new Date(b.updated_at).toLocaleString()}>{timeAgo(b.updated_at)}</span>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 shrink-0">
                    <Link
                      to={`/projects/${projectId}/buildings/${b.id}`}
                      className="rounded border border-gray-300 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50"
                    >
                      Edit
                    </Link>
                    <button
                      onClick={() => cloneBuilding.mutate(b.id)}
                      disabled={cloneBuilding.isPending}
                      className="rounded border border-gray-300 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                      title="Duplicate building"
                    >
                      Clone
                    </button>
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
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
