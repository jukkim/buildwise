import { useEffect, useRef, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { simulationsApi, type SimulationRun } from "@/api/client";
import { Skeleton } from "@/components/Skeleton";
import useDocumentTitle from "@/hooks/useDocumentTitle";
import clsx from "clsx";
import { STRATEGY_LABELS } from "@/constants/strategies";

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-green-100 text-green-800",
  running: "bg-blue-100 text-blue-800",
  pending: "bg-gray-100 text-gray-800",
  queued: "bg-yellow-100 text-yellow-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-500",
};

export default function SimulationProgress() {
  const { configId } = useParams<{ configId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const hasAutoNavigated = useRef(false);
  const [elapsed, setElapsed] = useState(0);

  const { data: progress, isLoading, isError, refetch } = useQuery({
    queryKey: ["simulation-progress", configId],
    queryFn: () => simulationsApi.progress(configId!).then((r) => r.data),
    enabled: !!configId,
    refetchInterval: (query) => {
      const d = query.state.data;
      if (!d) return 5000;
      return d.completed + d.failed >= d.total_strategies ? false : 5000;
    },
  });

  const progressTitle = progress
    ? `${progress.completed}/${progress.total_strategies} Simulating...`
    : "Simulation Progress";
  useDocumentTitle(progressTitle);

  const cancelMutation = useMutation({
    mutationFn: () => simulationsApi.cancel(configId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["simulation-progress", configId] });
    },
  });

  // Auto-navigate to results when all done (with 1.5s delay for UX)
  useEffect(() => {
    if (!progress || hasAutoNavigated.current) return;
    const done = progress.completed + progress.failed >= progress.total_strategies;
    if (done && progress.failed === 0) {
      hasAutoNavigated.current = true;
      const timer = setTimeout(() => {
        navigate(`/simulations/${configId}/results`, { replace: true });
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [progress, configId, navigate]);

  // Elapsed timer — ticks every second while simulation is running
  useEffect(() => {
    if (!progress) return;
    const done = progress.completed + progress.failed >= progress.total_strategies;
    if (done) return;
    const firstRun = progress.runs.find((r) => r.started_at);
    if (!firstRun?.started_at) return;
    const start = new Date(firstRun.started_at).getTime();
    setElapsed(Math.floor((Date.now() - start) / 1000));
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [progress]);

  if (isError) return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-center">
      <p className="text-red-600 font-medium">Failed to load simulation progress</p>
      <button onClick={() => refetch()} className="mt-3 rounded bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700">
        Retry
      </button>
    </div>
  );

  if (isLoading || !progress) return (
    <div className="space-y-4">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-3 w-full rounded-full" />
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-14 rounded-lg" />
        ))}
      </div>
    </div>
  );

  const pct =
    progress.total_strategies > 0
      ? Math.round(
          ((progress.completed + progress.failed) / progress.total_strategies) * 100,
        )
      : 0;

  const allDone = progress.completed + progress.failed >= progress.total_strategies;
  const hasRunning = progress.running > 0 || progress.runs.some((r) => r.status === "pending" || r.status === "queued");

  return (
    <div>
      <div className="flex gap-4 text-sm">
        <Link to="/projects" className="text-blue-600 hover:underline">
          &larr; Projects
        </Link>
        {progress.project_id && progress.building_id && (
          <Link
            to={`/projects/${progress.project_id}/buildings/${progress.building_id}`}
            className="text-blue-600 hover:underline"
          >
            &larr; Building Editor
          </Link>
        )}
      </div>

      <h1 className="mt-2 text-2xl font-bold text-gray-900">
        Simulation Progress
      </h1>
      {(progress.building_name || progress.climate_city) && (
        <p className="text-sm text-gray-500 mb-4">
          {progress.building_name && progress.project_id && progress.building_id ? (
            <Link
              to={`/projects/${progress.project_id}/buildings/${progress.building_id}`}
              className="hover:text-blue-600 hover:underline"
            >
              {progress.building_name}
            </Link>
          ) : (
            progress.building_name
          )}
          {progress.building_name && progress.climate_city && " \u00b7 "}
          {progress.climate_city}
        </p>
      )}
      {!progress.building_name && !progress.climate_city && <div className="mb-6" />}

      {/* Progress bar */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-sm text-gray-600 mb-1">
          <span>
            {progress.completed} completed, {progress.failed > 0 ? `${progress.failed} failed, ` : ""}
            {progress.total_strategies} total
          </span>
          <span>{pct}%</span>
        </div>
        <div className="h-3 rounded-full bg-gray-200 overflow-hidden">
          <div
            className={clsx(
              "h-full rounded-full transition-all duration-500",
              progress.failed > 0 && allDone ? "bg-yellow-500" : "bg-blue-600",
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Status summary */}
      <div className="mb-6 flex items-center gap-3 text-sm">
        {!allDone && elapsed > 0 && (
          <span className="text-gray-500">
            Elapsed: {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}
          </span>
        )}
        {progress.estimated_remaining_seconds && !allDone && (
          <span className="text-gray-500">
            ~{Math.ceil(progress.estimated_remaining_seconds / 60)} min remaining
          </span>
        )}
      </div>

      {/* Action buttons */}
      <div className="mb-6 flex items-center gap-3">
        {allDone && progress.failed === 0 && (
          <span className="text-sm text-green-600 animate-pulse">Redirecting to results...</span>
        )}
        {allDone && (
          <Link
            to={`/simulations/${configId}/results`}
            className="inline-block rounded-lg bg-green-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-green-700"
          >
            View Results
          </Link>
        )}
        {hasRunning && !allDone && (
          <button
            onClick={() => cancelMutation.mutate()}
            disabled={cancelMutation.isPending}
            className="rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
          >
            {cancelMutation.isPending ? "Cancelling..." : "Cancel Simulation"}
          </button>
        )}
      </div>

      {/* Run list */}
      <div className="space-y-2">
        {progress.runs.map((run: SimulationRun) => (
          <div
            key={run.id}
            className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3"
          >
            <div>
              <span className="font-medium text-gray-900">
                {STRATEGY_LABELS[run.strategy] ?? run.strategy}
              </span>
              {run.duration_seconds != null && (
                <span className="ml-3 text-xs text-gray-400">
                  {run.duration_seconds >= 60
                    ? `${Math.floor(run.duration_seconds / 60)}m ${run.duration_seconds % 60}s`
                    : `${run.duration_seconds}s`}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {run.status === "running" && (
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
                </span>
              )}
              <span
                className={clsx(
                  "rounded-full px-2.5 py-0.5 text-xs font-medium",
                  STATUS_COLORS[run.status] ?? STATUS_COLORS.pending,
                )}
              >
                {run.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
