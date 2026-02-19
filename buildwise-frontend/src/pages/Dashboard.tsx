import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { projectsApi, type Project } from "@/api/client";
import { CardSkeleton } from "@/components/Skeleton";
import ConfirmDialog from "@/components/ConfirmDialog";
import { showToast } from "@/components/Toast";
import useDocumentTitle from "@/hooks/useDocumentTitle";
import useDebounce from "@/hooks/useDebounce";
import timeAgo from "@/utils/timeAgo";

export default function Dashboard() {
  useDocumentTitle("Projects");
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"newest" | "oldest" | "name">("newest");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [bannerDismissed, setBannerDismissed] = useState(() => localStorage.getItem("buildwise_banner_dismissed") === "1");
  const showCreateRef = useRef(setShowCreate);
  showCreateRef.current = setShowCreate;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "n" && !e.ctrlKey && !e.metaKey && !e.altKey
        && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) {
        showCreateRef.current(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const { data, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list().then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (params: { name: string; description?: string }) =>
      projectsApi.create(params.name, params.description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setShowCreate(false);
      setNewName("");
      setNewDesc("");
      showToast("Project created", "success");
    },
    onError: () => showToast("Failed to create project"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      projectsApi.update(id, { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setEditingId(null);
      showToast("Project renamed", "success");
    },
    onError: () => showToast("Failed to rename project"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => projectsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setDeletingId(null);
      showToast("Project deleted", "success");
    },
    onError: () => showToast("Failed to delete project"),
  });

  const allProjects = data?.data ?? [];
  const totalBuildings = allProjects.reduce((sum: number, p: Project) => sum + p.buildings_count, 0);
  const debouncedSearch = useDebounce(search);
  const filtered = debouncedSearch
    ? allProjects.filter((p) => p.name.toLowerCase().includes(debouncedSearch.toLowerCase()))
    : allProjects;
  const projects = [...filtered].sort((a, b) => {
    if (sortBy === "name") return a.name.localeCompare(b.name);
    if (sortBy === "oldest") return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });
  const userName = localStorage.getItem("buildwise_user_name") ?? "User";

  return (
    <div>
      {/* Welcome banner */}
      {!bannerDismissed && (
        <div className="relative mb-6 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 p-6 text-white">
          <button
            onClick={() => {
              setBannerDismissed(true);
              localStorage.setItem("buildwise_banner_dismissed", "1");
            }}
            className="absolute right-3 top-3 rounded p-1 text-blue-200 hover:bg-blue-500 hover:text-white"
            title="Dismiss"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <h1 className="text-2xl font-bold">Welcome back, {userName}</h1>
          <p className="mt-1 text-blue-100">Manage your building energy simulation projects</p>
          <div className="mt-4 flex gap-6">
            <div>
              <p className="text-2xl font-bold">{allProjects.length}</p>
              <p className="text-xs text-blue-200">Projects</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{totalBuildings}</p>
              <p className="text-xs text-blue-200">Buildings</p>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold text-gray-800">Projects</h2>
          {bannerDismissed && allProjects.length > 0 && (
            <div className="flex items-center gap-3 text-sm text-gray-500">
              <span>{allProjects.length} project{allProjects.length !== 1 ? "s" : ""}</span>
              <span className="text-gray-300">|</span>
              <span>{totalBuildings} building{totalBuildings !== 1 ? "s" : ""}</span>
            </div>
          )}
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          title="Press N to quick-create"
        >
          New Project
          <kbd className="ml-2 hidden sm:inline rounded bg-blue-500 px-1 py-0.5 text-xs font-mono">N</kbd>
        </button>
      </div>

      {/* Search + Sort */}
      {allProjects.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <input
            type="text"
            placeholder="Search projects..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full max-w-xs rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as "newest" | "oldest" | "name")}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-600"
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="name">Name A-Z</option>
          </select>
          <div className="ml-auto flex rounded-lg border border-gray-300 overflow-hidden">
            <button
              onClick={() => setViewMode("grid")}
              className={`px-2.5 py-2 ${viewMode === "grid" ? "bg-gray-100 text-gray-900" : "text-gray-400 hover:text-gray-600"}`}
              title="Grid view"
              aria-label="Grid view"
              aria-pressed={viewMode === "grid"}
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={`px-2.5 py-2 ${viewMode === "list" ? "bg-gray-100 text-gray-900" : "text-gray-400 hover:text-gray-600"}`}
              title="List view"
              aria-label="List view"
              aria-pressed={viewMode === "list"}
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4">
          <input
            type="text"
            placeholder="Project name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter" && newName.trim()) {
                createMutation.mutate({ name: newName, description: newDesc || undefined });
              }
            }}
          />
          <input
            type="text"
            placeholder="Description (optional)"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            className="mt-2 w-full rounded border border-gray-300 px-3 py-2 text-sm"
          />
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => createMutation.mutate({ name: newName, description: newDesc || undefined })}
              disabled={!newName.trim() || createMutation.isPending}
              className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {createMutation.isPending ? "Creating..." : "Create"}
            </button>
            <button
              onClick={() => { setShowCreate(false); setNewName(""); setNewDesc(""); }}
              className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      {deletingId && (
        <ConfirmDialog
          title="Delete Project"
          message="Are you sure? This will remove the project and all its buildings."
          confirmLabel="Delete"
          destructive
          pending={deleteMutation.isPending}
          onConfirm={() => deleteMutation.mutate(deletingId)}
          onCancel={() => setDeletingId(null)}
        />
      )}

      {/* Loading skeleton */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : debouncedSearch && projects.length > 0 ? (
        <>
          <p className="mb-3 text-xs text-gray-400">
            Showing {projects.length} of {allProjects.length} project{allProjects.length !== 1 ? "s" : ""}
          </p>
          <div className={viewMode === "grid" ? "grid gap-4 sm:grid-cols-2 lg:grid-cols-3" : "space-y-2"}>
            {projects.map((p: Project) => (
              <div
                key={p.id}
                className={`group relative rounded-lg border border-gray-200 bg-white hover:shadow-md hover:border-blue-300 transition-all ${
                  viewMode === "list" ? "flex items-center justify-between px-5 py-3" : "p-5"
                }`}
              >
                {/* Action buttons */}
                <div className={`${viewMode === "list" ? "flex" : "absolute right-3 top-3 hidden group-hover:flex group-focus-within:flex"} gap-1 ${viewMode === "grid" ? "" : "shrink-0 ml-3"}`}>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      setEditingId(p.id);
                      setEditName(p.name);
                    }}
                    className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                    title="Rename"
                    aria-label={`Rename ${p.name}`}
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      setDeletingId(p.id);
                    }}
                    className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500"
                    title="Delete"
                    aria-label={`Delete ${p.name}`}
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>

                {editingId === p.id ? (
                  <div className={viewMode === "list" ? "flex-1" : ""}>
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      className="w-full rounded border border-blue-300 px-2 py-1 text-sm font-semibold"
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && editName.trim()) {
                          updateMutation.mutate({ id: p.id, name: editName });
                        }
                        if (e.key === "Escape") setEditingId(null);
                      }}
                    />
                    <div className="mt-2 flex gap-1">
                      <button
                        onClick={() => updateMutation.mutate({ id: p.id, name: editName })}
                        disabled={!editName.trim() || updateMutation.isPending}
                        className="rounded bg-blue-600 px-2 py-1 text-xs text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-600"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <Link to={`/projects/${p.id}`} className={`rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${viewMode === "list" ? "flex-1 flex items-center gap-4 min-w-0" : ""}`}>
                    <h3 className={`font-semibold text-gray-900 ${viewMode === "list" ? "truncate" : ""}`}>{p.name}</h3>
                    {p.description && (
                      <p className={`text-sm text-gray-500 ${viewMode === "grid" ? "mt-1 line-clamp-2" : "hidden sm:block truncate max-w-xs"}`}>
                        {p.description}
                      </p>
                    )}
                    <div className={`flex items-center gap-3 text-xs text-gray-400 ${viewMode === "grid" ? "mt-3" : ""}`}>
                      <span className="flex items-center gap-1">
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                        </svg>
                        {p.buildings_count} building{p.buildings_count !== 1 ? "s" : ""}
                      </span>
                      <span title={new Date(p.updated_at).toLocaleString()}>
                        Updated {timeAgo(p.updated_at)}
                      </span>
                    </div>
                  </Link>
                )}
              </div>
            ))}
          </div>
        </>
      ) : projects.length === 0 && debouncedSearch ? (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
          <p className="text-sm text-gray-500">No projects matching "{debouncedSearch}"</p>
          <button
            onClick={() => setSearch("")}
            className="mt-3 text-sm text-blue-600 hover:underline"
          >
            Clear search
          </button>
        </div>
      ) : projects.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-gray-300 p-12 text-center">
          <svg className="mx-auto h-12 w-12 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
          <h3 className="mt-3 text-sm font-medium text-gray-900">Welcome to BuildWise</h3>
          <p className="mt-1 text-sm text-gray-500">Create a project to start comparing energy strategies.</p>
          <ol className="mt-4 inline-block text-left text-sm text-gray-500 space-y-1.5">
            <li className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-100 text-xs font-medium text-blue-700">1</span>
              Create a project
            </li>
            <li className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-100 text-xs font-medium text-blue-700">2</span>
              Add buildings from templates
            </li>
            <li className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-100 text-xs font-medium text-blue-700">3</span>
              Run simulations &amp; analyze results
            </li>
          </ol>
          <div className="mt-4">
            <button
              onClick={() => setShowCreate(true)}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Create First Project
            </button>
          </div>
        </div>
      ) : (
        <div className={viewMode === "grid" ? "grid gap-4 sm:grid-cols-2 lg:grid-cols-3" : "space-y-2"}>
          {projects.map((p: Project) => (
            <div
              key={p.id}
              className={`group relative rounded-lg border border-gray-200 bg-white hover:shadow-md hover:border-blue-300 transition-all ${
                viewMode === "list" ? "flex items-center justify-between px-5 py-3" : "p-5"
              }`}
            >
              {/* Action buttons */}
              <div className={`${viewMode === "list" ? "flex" : "absolute right-3 top-3 hidden group-hover:flex group-focus-within:flex"} gap-1 ${viewMode === "grid" ? "" : "shrink-0 ml-3"}`}>
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    setEditingId(p.id);
                    setEditName(p.name);
                  }}
                  className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                  title="Rename"
                  aria-label={`Rename ${p.name}`}
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    setDeletingId(p.id);
                  }}
                  className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500"
                  title="Delete"
                  aria-label={`Delete ${p.name}`}
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>

              {editingId === p.id ? (
                <div className={viewMode === "list" ? "flex-1" : ""}>
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="w-full rounded border border-blue-300 px-2 py-1 text-sm font-semibold"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && editName.trim()) {
                        updateMutation.mutate({ id: p.id, name: editName });
                      }
                      if (e.key === "Escape") setEditingId(null);
                    }}
                  />
                  <div className="mt-2 flex gap-1">
                    <button
                      onClick={() => updateMutation.mutate({ id: p.id, name: editName })}
                      disabled={!editName.trim() || updateMutation.isPending}
                      className="rounded bg-blue-600 px-2 py-1 text-xs text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-600"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <Link to={`/projects/${p.id}`} className={`rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${viewMode === "list" ? "flex-1 flex items-center gap-4 min-w-0" : ""}`}>
                  <h3 className={`font-semibold text-gray-900 ${viewMode === "list" ? "truncate" : ""}`}>
                    {p.name}
                    {Date.now() - new Date(p.updated_at).getTime() < 86400000 && (
                      <span className="ml-2 rounded bg-green-100 px-1.5 py-0.5 text-[10px] font-medium text-green-700">Active</span>
                    )}
                  </h3>
                  {p.description && (
                    <p className={`text-sm text-gray-500 ${viewMode === "grid" ? "mt-1 line-clamp-2" : "hidden sm:block truncate max-w-xs"}`}>
                      {p.description}
                    </p>
                  )}
                  <div className={`flex items-center gap-3 text-xs text-gray-400 ${viewMode === "grid" ? "mt-3" : ""}`}>
                    <span className="flex items-center gap-1">
                      <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                      </svg>
                      {p.buildings_count} building{p.buildings_count !== 1 ? "s" : ""}
                    </span>
                    <span title={new Date(p.updated_at).toLocaleString()}>
                      Updated {timeAgo(p.updated_at)}
                    </span>
                  </div>
                </Link>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
