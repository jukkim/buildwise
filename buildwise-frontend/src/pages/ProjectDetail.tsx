import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  projectsApi,
  buildingsApi,
  templatesApi,
  simulationsApi,
  type BuildingTemplate,
} from "@/api/client";

export default function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>();
  const queryClient = useQueryClient();
  const [showTemplates, setShowTemplates] = useState(false);

  const { data: project, isLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => projectsApi.get(projectId!).then((r) => r.data),
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
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      setShowTemplates(false);
    },
  });

  if (isLoading || !project) return <div className="text-gray-500">Loading...</div>;

  return (
    <div>
      <div className="mb-6">
        <Link to="/projects" className="text-sm text-blue-600 hover:underline">
          &larr; Projects
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">{project.name}</h1>
        {project.description && (
          <p className="mt-1 text-gray-500">{project.description}</p>
        )}
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-800">Buildings</h2>
        <button
          onClick={() => setShowTemplates(!showTemplates)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Add Building
        </button>
      </div>

      {showTemplates && templates && (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((tmpl: BuildingTemplate) => (
            <button
              key={tmpl.building_type}
              onClick={() => createBuilding.mutate(tmpl)}
              className="rounded-lg border border-gray-200 bg-white p-4 text-left hover:border-blue-400 hover:shadow transition-all"
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

      <div className="rounded-lg border-2 border-dashed border-gray-300 p-12 text-center">
        <p className="text-gray-500">
          Building list and simulation controls will appear here.
        </p>
      </div>
    </div>
  );
}
