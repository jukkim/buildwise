import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { simulationsApi, type SimulationRun } from "@/api/client";
import clsx from "clsx";

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

  const { data: progress, isLoading } = useQuery({
    queryKey: ["simulation-progress", configId],
    queryFn: () => simulationsApi.progress(configId!).then((r) => r.data),
    enabled: !!configId,
    refetchInterval: (query) => {
      const d = query.state.data;
      if (!d) return 5000;
      return d.completed + d.failed >= d.total_strategies ? false : 5000;
    },
  });

  if (isLoading || !progress) return <div className="text-gray-500">Loading...</div>;

  const pct =
    progress.total_strategies > 0
      ? Math.round(
          ((progress.completed + progress.failed) / progress.total_strategies) * 100,
        )
      : 0;

  const allDone = progress.completed + progress.failed >= progress.total_strategies;

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">
        Simulation Progress
      </h1>

      {/* Progress bar */}
      <div className="mb-6">
        <div className="flex items-center justify-between text-sm text-gray-600 mb-1">
          <span>
            {progress.completed}/{progress.total_strategies} strategies
          </span>
          <span>{pct}%</span>
        </div>
        <div className="h-3 rounded-full bg-gray-200 overflow-hidden">
          <div
            className="h-full rounded-full bg-blue-600 transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {allDone && (
        <Link
          to={`/simulations/${configId}/results`}
          className="mb-6 inline-block rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
        >
          View Results
        </Link>
      )}

      {/* Run list */}
      <div className="space-y-2">
        {progress.runs.map((run: SimulationRun) => (
          <div
            key={run.id}
            className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3"
          >
            <span className="font-medium text-gray-900">{run.strategy}</span>
            <span
              className={clsx(
                "rounded-full px-2.5 py-0.5 text-xs font-medium",
                STATUS_COLORS[run.status] ?? STATUS_COLORS.pending,
              )}
            >
              {run.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
