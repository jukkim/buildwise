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
import useDebounce from "@/hooks/useDebounce";
import timeAgo from "@/utils/timeAgo";
import Breadcrumb from "@/components/Breadcrumb";

const HVAC_LABELS: Record<string, string> = {
  vav_chiller_boiler: "VAV + Chiller/Boiler",
  vrf: "VRF Heat Recovery",
  psz_hp: "PSZ Heat Pump",
  psz_ac: "PSZ AC",
  vav_chiller_boiler_school: "VAV (School)",
};

const BUILDING_TYPE_COLORS: Record<string, string> = {
  medium_office: "bg-blue-100 text-blue-700",
  large_office: "bg-indigo-100 text-indigo-700",
  small_office: "bg-sky-100 text-sky-700",
  primary_school: "bg-green-100 text-green-700",
  secondary_school: "bg-emerald-100 text-emerald-700",
  hospital: "bg-red-100 text-red-700",
  retail: "bg-amber-100 text-amber-700",
  hotel: "bg-purple-100 text-purple-700",
  warehouse: "bg-gray-200 text-gray-700",
  apartment: "bg-teal-100 text-teal-700",
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
  const [buildingSearch, setBuildingSearch] = useState("");
  const [editingDesc, setEditingDesc] = useState(false);
  const [descValue, setDescValue] = useState("");
  const [cloningBuildingId, setCloningBuildingId] = useState<string | null>(null);
  const [buildingSort, setBuildingSort] = useState<"newest" | "oldest" | "name">("newest");

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
    mutationFn: (data: { name?: string; description?: string }) =>
      projectsApi.update(projectId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setEditingName(false);
      setEditingDesc(false);
      showToast("Project updated", "success");
    },
    onError: () => showToast("Failed to update project"),
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

  const debouncedBuildingSearch = useDebounce(buildingSearch);
  const filteredBuildings = buildings
    ? (() => {
        const filtered = debouncedBuildingSearch
          ? buildings.filter((b) => b.name.toLowerCase().includes(debouncedBuildingSearch.toLowerCase()))
          : buildings;
        return [...filtered].sort((a, b) => {
          if (buildingSort === "name") return a.name.localeCompare(b.name);
          if (buildingSort === "oldest") return new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime();
          return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
        });
      })()
    : [];

  if (projectLoading || !project) return <ListSkeleton rows={3} />;

  return (
    <div>
      <div className="mb-6">
        <Breadcrumb items={[
          { label: "Projects", to: "/projects" },
          { label: project.name },
        ]} />

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
                  if (e.key === "Enter" && nameValue.trim()) updateProject.mutate({ name: nameValue });
                  if (e.key === "Escape") setEditingName(false);
                }}
              />
              <button
                onClick={() => updateProject.mutate({ name: nameValue })}
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

        {editingDesc ? (
          <div className="mt-2">
            <input
              type="text"
              value={descValue}
              onChange={(e) => setDescValue(e.target.value)}
              className="w-full rounded border border-blue-300 px-2 py-1 text-sm text-gray-600"
              placeholder="Project description"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter") updateProject.mutate({ description: descValue });
                if (e.key === "Escape") setEditingDesc(false);
              }}
            />
            <div className="mt-1 flex gap-1">
              <button
                onClick={() => updateProject.mutate({ description: descValue })}
                disabled={updateProject.isPending}
                className="rounded bg-blue-600 px-2 py-1 text-xs text-white hover:bg-blue-700 disabled:opacity-50"
              >
                Save
              </button>
              <button
                onClick={() => setEditingDesc(false)}
                className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-600"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <p
            className="mt-1 text-gray-500 cursor-pointer hover:text-gray-700"
            onClick={() => { setEditingDesc(true); setDescValue(project.description ?? ""); }}
            title="Click to edit description"
          >
            {project.description || <span className="text-gray-300 italic">Add description...</span>}
          </p>
        )}
      </div>

      {/* Project stats */}
      {buildings && buildings.length > 0 && (
        <div className="mb-4 flex gap-4 text-sm">
          <div className="flex items-center gap-1.5 text-gray-500">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
            <span>{buildings.length} building{buildings.length !== 1 ? "s" : ""}</span>
          </div>
          <div className="flex items-center gap-1.5 text-gray-500">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span title={new Date(project.created_at).toLocaleString()}>Created {timeAgo(project.created_at)}</span>
          </div>
          <div className="flex items-center gap-1.5 text-gray-500">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span title={new Date(project.updated_at).toLocaleString()}>Updated {timeAgo(project.updated_at)}</span>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-800">
          Buildings {buildings && (
            debouncedBuildingSearch
              ? <span className="text-sm font-normal text-gray-400">({filteredBuildings.length} of {buildings.length})</span>
              : <span className="text-sm font-normal text-gray-400">({buildings.length})</span>
          )}
        </h2>
        <button
          onClick={() => setShowTemplates(!showTemplates)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {showTemplates ? "Cancel" : "Add Building"}
        </button>
      </div>

      {/* Building search + sort */}
      {buildings && buildings.length > 3 && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <input
            type="text"
            placeholder="Search buildings..."
            value={buildingSearch}
            onChange={(e) => setBuildingSearch(e.target.value)}
            className="w-full max-w-xs rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <select
            value={buildingSort}
            onChange={(e) => setBuildingSort(e.target.value as "newest" | "oldest" | "name")}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-600"
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="name">Name A-Z</option>
          </select>
        </div>
      )}

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

      {/* Clone building confirmation */}
      {cloningBuildingId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900">Clone Building</h3>
            <p className="mt-1 text-sm text-gray-500">
              Enter a name for the cloned building.
            </p>
            <input
              type="text"
              placeholder="Building name (leave empty for default)"
              className="mt-3 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  cloneBuilding.mutate(cloningBuildingId);
                  setCloningBuildingId(null);
                }
                if (e.key === "Escape") setCloningBuildingId(null);
              }}
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setCloningBuildingId(null)}
                className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  cloneBuilding.mutate(cloningBuildingId);
                  setCloningBuildingId(null);
                }}
                disabled={cloneBuilding.isPending}
                className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {cloneBuilding.isPending ? "Cloning..." : "Clone"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Building list */}
      {buildingsLoading ? (
        <ListSkeleton rows={2} />
      ) : filteredBuildings.length === 0 && debouncedBuildingSearch ? (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
          <p className="text-sm text-gray-500">No buildings matching "{debouncedBuildingSearch}"</p>
          <button
            onClick={() => setBuildingSearch("")}
            className="mt-3 text-sm text-blue-600 hover:underline"
          >
            Clear search
          </button>
        </div>
      ) : !buildings || buildings.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-gray-300 p-12 text-center">
          <svg className="mx-auto h-12 w-12 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
          <h3 className="mt-3 text-sm font-medium text-gray-900">No buildings yet</h3>
          <p className="mt-1 text-sm text-gray-500">Get started in 3 easy steps:</p>
          <ol className="mt-3 inline-block text-left text-sm text-gray-500 space-y-1">
            <li className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-100 text-xs font-medium text-blue-700">1</span>
              Choose a building template
            </li>
            <li className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-100 text-xs font-medium text-blue-700">2</span>
              Customize BPS parameters
            </li>
            <li className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-100 text-xs font-medium text-blue-700">3</span>
              Run simulation &amp; compare strategies
            </li>
          </ol>
          <div className="mt-4">
            <button
              onClick={() => setShowTemplates(true)}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Add Building
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredBuildings.map((b: Building) => {
            const bps = b.bps as Record<string, Record<string, unknown>>;
            const area = bps?.geometry?.total_floor_area_m2;
            const floors = bps?.geometry?.num_floors_above;
            const hvac = bps?.hvac?.system_type as string;

            return (
              <div
                key={b.id}
                className="rounded-lg border border-gray-200 bg-white p-5 hover:shadow-md transition-shadow"
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
                      <span className={`rounded px-2 py-0.5 ${BUILDING_TYPE_COLORS[b.building_type] ?? "bg-gray-100 text-gray-700"}`}>
                        {b.building_type.replace(/_/g, " ")}
                      </span>
                      {floors != null && <span>{String(floors)}F</span>}
                      {area != null && <span>{Number(area).toLocaleString()} m2</span>}
                      {hvac && (
                        <span>{HVAC_LABELS[hvac] ?? hvac}</span>
                      )}
                      <span>v{b.bps_version}</span>
                      <span title={new Date(b.updated_at).toLocaleString()}>{timeAgo(b.updated_at)}</span>
                      {area != null && (() => {
                        const maxArea = Math.max(...(buildings ?? []).map((bb) => Number((bb.bps as Record<string, Record<string, unknown>>)?.geometry?.total_floor_area_m2 ?? 0)));
                        const pct = maxArea > 0 ? (Number(area) / maxArea) * 100 : 0;
                        return (
                          <span className="inline-flex items-center gap-1" title={`${Number(area).toLocaleString()} m²`}>
                            <span className="inline-block h-1.5 w-8 rounded-full bg-gray-200 overflow-hidden">
                              <span className="block h-full rounded-full bg-blue-400" style={{ width: `${pct}%` }} />
                            </span>
                          </span>
                        );
                      })()}
                      {Date.now() - new Date(b.created_at).getTime() < 86400000 && (
                        <span className="rounded bg-blue-100 px-1.5 py-0.5 text-blue-700 font-medium">New</span>
                      )}
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
                      onClick={() => setCloningBuildingId(b.id)}
                      className="rounded border border-gray-300 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50"
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
