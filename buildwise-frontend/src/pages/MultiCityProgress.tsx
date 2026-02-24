import { useEffect, useRef, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { simulationsApi, type SimulationProgress } from "@/api/client";
import { Skeleton } from "@/components/Skeleton";
import useDocumentTitle from "@/hooks/useDocumentTitle";
import clsx from "clsx";
import Breadcrumb from "@/components/Breadcrumb";

export default function MultiCityProgress() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const hasAutoNavigated = useRef(false);
  const [elapsed, setElapsed] = useState(0);

  const configIds = (searchParams.get("configs") ?? "").split(",").filter(Boolean);

  const queries = useQueries({
    queries: configIds.map((id) => ({
      queryKey: ["simulation-progress", id],
      queryFn: () => simulationsApi.progress(id).then((r) => r.data),
      refetchInterval: (query: { state: { data?: SimulationProgress } }) => {
        const d = query.state.data;
        if (!d) return 5000;
        return d.completed + d.failed >= d.total_strategies ? false : 5000;
      },
    })),
  });

  const allData = queries.map((q) => q.data).filter(Boolean) as SimulationProgress[];
  const isLoading = queries.some((q) => q.isLoading);

  const totalStrategies = allData.reduce((s, p) => s + p.total_strategies, 0);
  const totalCompleted = allData.reduce((s, p) => s + p.completed, 0);
  const totalFailed = allData.reduce((s, p) => s + p.failed, 0);
  const totalRunning = allData.reduce((s, p) => s + p.running, 0);
  const allDone = allData.length === configIds.length && allData.every((p) => p.completed + p.failed >= p.total_strategies);
  const pct = totalStrategies > 0 ? Math.round(((totalCompleted + totalFailed) / totalStrategies) * 100) : 0;

  const progressTitle = allDone
    ? `Complete! ${allData.length} cities`
    : `${pct}% Simulating ${allData.length} cities...`;
  useDocumentTitle(progressTitle);

  // Auto-navigate to compare when all done
  useEffect(() => {
    if (!allDone || hasAutoNavigated.current || allData.length === 0) return;
    if (totalFailed === 0) {
      hasAutoNavigated.current = true;
      const timer = setTimeout(() => {
        navigate(`/compare?configs=${configIds.join(",")}`, { replace: true });
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [allDone, allData.length, totalFailed, configIds, navigate]);

  // Elapsed timer
  useEffect(() => {
    if (allDone || allData.length === 0) return;
    const starts = allData
      .flatMap((p) => p.runs)
      .filter((r) => r.started_at)
      .map((r) => new Date(r.started_at!).getTime());
    if (starts.length === 0) return;
    const earliest = Math.min(...starts);
    setElapsed(Math.floor((Date.now() - earliest) / 1000));
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - earliest) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [allDone, allData]);

  if (configIds.length === 0) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-center">
        <p className="text-red-600 font-medium">No simulation configs specified</p>
        <Link to="/projects" className="mt-3 inline-block rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700">
          Back to Projects
        </Link>
      </div>
    );
  }

  if (isLoading || allData.length === 0) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-full rounded-full" />
        {Array.from({ length: configIds.length }).map((_, i) => (
          <Skeleton key={i} className="h-24 rounded-lg" />
        ))}
      </div>
    );
  }

  const firstData = allData[0];

  return (
    <div>
      <Breadcrumb items={[
        { label: "Projects", to: "/projects" },
        ...(firstData.building_name && firstData.project_id && firstData.building_id
          ? [{ label: firstData.building_name, to: `/projects/${firstData.project_id}/buildings/${firstData.building_id}` }]
          : []),
        { label: "Multi-City Simulation" },
      ]} />

      <h1 className="mt-2 text-3xl font-extrabold text-gray-900 tracking-tight">
        Multi-City Simulation
      </h1>
      <p className="text-sm text-gray-500 mb-4">
        {firstData.building_name ?? "Building"} &middot; {allData.length} cities
      </p>

      {/* Overall progress bar */}
      <div className="mb-6">
        <div className="flex items-center justify-between text-sm text-gray-600 mb-1">
          <span>
            {totalCompleted} of {totalStrategies} strategies completed
            {totalFailed > 0 && <span className="text-red-500"> ({totalFailed} failed)</span>}
            {totalRunning > 0 && <span className="text-blue-500"> &middot; {totalRunning} running</span>}
          </span>
          <span className={pct >= 100 ? "text-green-600 font-medium" : "text-gray-600"}>{pct}%</span>
        </div>
        <div className="h-4 rounded-full bg-gray-200/70 overflow-hidden shadow-inner">
          <div
            className={clsx(
              "h-full rounded-full transition-all duration-700 ease-out",
              allDone && totalFailed === 0
                ? "bg-gradient-to-r from-green-500 to-emerald-400"
                : allDone && totalFailed > 0
                ? "bg-gradient-to-r from-yellow-500 to-amber-400"
                : "bg-gradient-to-r from-blue-600 to-indigo-500",
              !allDone && "progress-bar-active",
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="mt-2 flex items-center gap-3 text-sm text-gray-500">
          {!allDone && elapsed > 0 && (
            <span>Elapsed: {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}</span>
          )}
        </div>
      </div>

      {/* Completion banner */}
      {allDone && totalFailed === 0 && (
        <div className="mb-6 rounded-2xl bg-gradient-to-br from-green-50 via-emerald-50 to-teal-50 border border-green-200 px-6 py-6 text-center animate-slide-up">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-green-500 to-emerald-400 shadow-lg shadow-green-500/30">
            <svg className="h-7 w-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <p className="mt-3 text-base font-bold text-green-800">
            All {allData.length} cities completed!
          </p>
          <p className="mt-1 text-sm text-green-600/80">Redirecting to comparison...</p>
        </div>
      )}

      {/* Action buttons */}
      {allDone && (
        <div className="mb-6">
          <Link
            to={`/compare?configs=${configIds.join(",")}`}
            className="inline-block rounded-lg bg-green-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-green-700"
          >
            View Comparison
          </Link>
        </div>
      )}

      {/* Per-city cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {allData.map((prog) => {
          const cityDone = prog.completed + prog.failed >= prog.total_strategies;
          const cityPct = prog.total_strategies > 0
            ? Math.round(((prog.completed + prog.failed) / prog.total_strategies) * 100)
            : 0;
          return (
            <div
              key={prog.config_id}
              className={clsx(
                "rounded-xl border p-4 transition-colors",
                cityDone && prog.failed === 0
                  ? "border-green-200 bg-green-50/50"
                  : cityDone && prog.failed > 0
                  ? "border-yellow-200 bg-yellow-50/50"
                  : "border-gray-200 bg-white",
              )}
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-semibold text-gray-800">{prog.climate_city}</h4>
                {cityDone && prog.failed === 0 && (
                  <svg className="h-5 w-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                )}
                {cityDone && prog.failed > 0 && (
                  <span className="text-xs text-yellow-600">{prog.failed} failed</span>
                )}
                {!cityDone && (
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
                  </span>
                )}
              </div>
              <div className="h-2 rounded-full bg-gray-200 overflow-hidden mb-1">
                <div
                  className={clsx(
                    "h-full rounded-full transition-all duration-500",
                    cityDone && prog.failed === 0 ? "bg-green-500" :
                    cityDone ? "bg-yellow-500" : "bg-blue-500",
                  )}
                  style={{ width: `${cityPct}%` }}
                />
              </div>
              <p className="text-xs text-gray-500">
                {prog.completed}/{prog.total_strategies} strategies
                {prog.running > 0 && <span className="text-blue-500"> &middot; {prog.running} running</span>}
              </p>
              {cityDone && (
                <Link
                  to={`/simulations/${prog.config_id}/results`}
                  className="mt-2 inline-block text-xs text-green-600 hover:underline"
                >
                  View individual results
                </Link>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
