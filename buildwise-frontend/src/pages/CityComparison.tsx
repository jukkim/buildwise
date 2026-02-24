import { useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from "recharts";
import { simulationsApi, type StrategyComparison, type EnergyResult } from "@/api/client";
import { Skeleton } from "@/components/Skeleton";
import { showToast } from "@/components/Toast";
import useDocumentTitle from "@/hooks/useDocumentTitle";
import { STRATEGY_LABELS } from "@/constants/strategies";
import { CITY_COLORS } from "@/constants/cities";
import Breadcrumb from "@/components/Breadcrumb";

export default function CityComparison() {
  const [searchParams] = useSearchParams();
  const [filterCity, setFilterCity] = useState<string | null>(null);

  const configIds = (searchParams.get("configs") ?? "").split(",").filter(Boolean);

  const queries = useQueries({
    queries: configIds.map((id) => ({
      queryKey: ["results", id],
      queryFn: () => simulationsApi.results(id).then((r) => r.data),
    })),
  });

  const isLoading = queries.some((q) => q.isLoading);
  const isError = queries.some((q) => q.isError);
  const comparisons = queries
    .map((q) => q.data)
    .filter(Boolean) as StrategyComparison[];

  useDocumentTitle(
    comparisons.length > 0
      ? `Compare: ${comparisons.map((c) => c.climate_city).join(" vs ")}`
      : "City Comparison",
  );

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

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 sm:grid-cols-3">
          {configIds.map((_, i) => <Skeleton key={i} className="h-28 rounded-lg" />)}
        </div>
        <Skeleton className="h-80 rounded-lg" />
        <Skeleton className="h-80 rounded-lg" />
      </div>
    );
  }

  if (isError || comparisons.length === 0) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-center">
        <p className="text-red-600 font-medium">Failed to load comparison results</p>
        <p className="mt-1 text-sm text-red-400">Some simulations may still be running.</p>
      </div>
    );
  }

  const firstComparison = comparisons[0];

  // Collect all strategy keys across all cities
  const allStrategyKeys = Array.from(
    new Set(
      comparisons.flatMap((c) => [
        ...(c.baseline ? [c.baseline.strategy] : []),
        ...c.strategies.map((s) => s.strategy),
      ]),
    ),
  );

  // Helper to find a strategy result in a comparison
  const findStrategy = (comp: StrategyComparison, strat: string): EnergyResult | null => {
    if (comp.baseline?.strategy === strat) return comp.baseline;
    return comp.strategies.find((s) => s.strategy === strat) ?? null;
  };

  // Filter comparisons
  const displayed = filterCity
    ? comparisons.filter((c) => c.climate_city === filterCity)
    : comparisons;

  // -- Chart Data: EUI grouped bar --
  const euiChartData = allStrategyKeys.map((strat) => ({
    strategy: STRATEGY_LABELS[strat] ?? strat,
    ...Object.fromEntries(
      displayed.map((c) => [
        c.climate_city,
        findStrategy(c, strat)?.eui_kwh_m2 ?? null,
      ]),
    ),
  }));

  // -- Chart Data: Cost grouped bar --
  const costChartData = allStrategyKeys
    .map((strat) => ({
      strategy: STRATEGY_LABELS[strat] ?? strat,
      ...Object.fromEntries(
        displayed.map((c) => {
          const r = findStrategy(c, strat);
          return [c.climate_city, r?.annual_cost_krw ? Math.round(r.annual_cost_krw / 10000) : null];
        }),
      ),
    }))
    .filter((row) => Object.values(row).some((v) => typeof v === "number" && v > 0));

  // -- Heatmap data: savings % --
  const heatmapData = allStrategyKeys.filter((s) => s !== "baseline").map((strat) => ({
    strategy: STRATEGY_LABELS[strat] ?? strat,
    ...Object.fromEntries(
      displayed.map((c) => {
        const r = findStrategy(c, strat);
        return [c.climate_city, r?.savings_pct ?? null];
      }),
    ),
  })) as Array<{ strategy: string; [city: string]: string | number | null }>;

  const maxSavings = Math.max(
    ...heatmapData.flatMap((row) =>
      Object.entries(row)
        .filter(([k]) => k !== "strategy")
        .map(([, v]) => Math.abs((v as unknown as number) ?? 0)),
    ),
    1,
  );

  const getCellColor = (val: number | null): string => {
    if (val == null) return "bg-gray-100 text-gray-400";
    if (val > 0) {
      const intensity = Math.min(val / maxSavings, 1);
      if (intensity > 0.6) return "bg-green-200 text-green-900";
      if (intensity > 0.3) return "bg-green-100 text-green-800";
      return "bg-green-50 text-green-700";
    }
    return "bg-red-50 text-red-600";
  };

  // CSV download
  const downloadCsv = () => {
    const cities = displayed.map((c) => c.climate_city);
    const headers = ["Strategy", ...cities.flatMap((city) => [`${city} EUI`, `${city} Savings%`, `${city} Cost`])];
    const rows = allStrategyKeys.map((strat) => [
      STRATEGY_LABELS[strat] ?? strat,
      ...displayed.flatMap((c) => {
        const r = findStrategy(c, strat);
        return [
          r?.eui_kwh_m2?.toFixed(1) ?? "",
          r?.savings_pct?.toFixed(1) ?? "",
          r?.annual_cost_krw?.toString() ?? "",
        ];
      }),
    ]);
    const csv = [headers, ...rows].map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `buildwise-city-comparison-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("CSV downloaded", "success");
  };

  return (
    <div>
      <Breadcrumb items={[
        { label: "Projects", to: "/projects" },
        { label: firstComparison.building_name, to: `/projects/${firstComparison.project_id}/buildings/${firstComparison.building_id}` },
        { label: "City Comparison" },
      ]} />

      <div className="mt-2 flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">
            City Comparison
          </h1>
          <p className="text-sm text-gray-500">
            {firstComparison.building_name} &middot;{" "}
            {firstComparison.building_type.replace(/_/g, " ")} &middot;{" "}
            {comparisons.length} cities
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {comparisons.length > 2 && (
            <select
              value={filterCity ?? ""}
              onChange={(e) => setFilterCity(e.target.value || null)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="">All Cities ({comparisons.length})</option>
              {comparisons.map((c) => (
                <option key={c.climate_city} value={c.climate_city}>{c.climate_city}</option>
              ))}
            </select>
          )}
          <button
            onClick={downloadCsv}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 sm:px-4 sm:py-2"
          >
            <span className="hidden sm:inline">Download </span>CSV
          </button>
        </div>
      </div>

      {/* City summary cards */}
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {displayed.map((comp) => {
          const baseline = comp.baseline;
          const best = comp.recommended_strategy
            ? [...(comp.baseline ? [comp.baseline] : []), ...comp.strategies]
                .find((s) => s.strategy === comp.recommended_strategy)
            : null;
          return (
            <div
              key={comp.climate_city}
              className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
            >
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="inline-block h-3 w-3 rounded-full"
                  style={{ backgroundColor: CITY_COLORS[comp.climate_city] ?? "#6B7280" }}
                />
                <h4 className="font-semibold text-gray-800">{comp.climate_city}</h4>
              </div>
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-400">Baseline EUI</dt>
                  <dd className="font-medium text-gray-700">{baseline?.eui_kwh_m2.toFixed(1) ?? "-"}</dd>
                </div>
                {best && (
                  <>
                    <div className="flex justify-between">
                      <dt className="text-gray-400">Best</dt>
                      <dd className="font-medium text-green-600">
                        {STRATEGY_LABELS[best.strategy] ?? best.strategy}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-gray-400">Savings</dt>
                      <dd className="font-medium text-green-600">
                        {best.savings_pct != null ? `${best.savings_pct.toFixed(1)}%` : "-"}
                      </dd>
                    </div>
                  </>
                )}
              </dl>
            </div>
          );
        })}
      </div>

      {/* EUI grouped bar chart */}
      <div className="mt-6 rounded-xl bg-white shadow-sm p-5">
        <h3 className="font-semibold text-gray-800 mb-4">
          EUI by Strategy (kWh/m²)
        </h3>
        {euiChartData.length === 0 ? (
          <div className="flex h-[300px] items-center justify-center text-sm text-gray-400">
            No EUI data available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={euiChartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="strategy" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" height={60} />
              <YAxis unit=" kWh/m²" tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              {displayed.map((c) => (
                <Bar
                  key={c.climate_city}
                  dataKey={c.climate_city}
                  fill={CITY_COLORS[c.climate_city] ?? "#6B7280"}
                  radius={[2, 2, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Cost grouped bar chart */}
      {costChartData.length > 0 && (
        <div className="mt-6 rounded-xl bg-white shadow-sm p-5">
          <h3 className="font-semibold text-gray-800 mb-4">
            Annual Cost by Strategy (만원/yr)
          </h3>
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={costChartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="strategy" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" height={60} />
              <YAxis unit=" 만원" tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              {displayed.map((c) => (
                <Bar
                  key={c.climate_city}
                  dataKey={c.climate_city}
                  fill={CITY_COLORS[c.climate_city] ?? "#6B7280"}
                  radius={[2, 2, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Savings heatmap table */}
      <div className="mt-6 rounded-xl bg-white shadow-sm p-5">
        <h3 className="font-semibold text-gray-800 mb-4">
          Savings Heatmap (% vs Baseline)
        </h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Strategy</th>
                {displayed.map((c) => (
                  <th key={c.climate_city} className="px-3 py-2 text-center font-medium text-gray-600">
                    <div className="flex items-center justify-center gap-1">
                      <span
                        className="inline-block h-2 w-2 rounded-full"
                        style={{ backgroundColor: CITY_COLORS[c.climate_city] ?? "#6B7280" }}
                      />
                      {c.climate_city}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {heatmapData.map((row) => (
                <tr key={row.strategy}>
                  <td className="px-3 py-2 font-medium text-gray-800">{row.strategy}</td>
                  {displayed.map((c) => {
                    const val = row[c.climate_city] as number | null;
                    return (
                      <td key={c.climate_city} className="px-3 py-2 text-center">
                        <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${getCellColor(val)}`}>
                          {val != null ? `${val > 0 ? "-" : "+"}${Math.abs(val).toFixed(1)}%` : "N/A"}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail table */}
      <div className="mt-6 overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Strategy</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">City</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">EUI (kWh/m²)</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">Total (kWh)</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">Savings (%)</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">Cost (KRW)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {allStrategyKeys.flatMap((strat) =>
              displayed.map((comp) => {
                const r = findStrategy(comp, strat);
                if (!r) return null;
                const isRecommended = strat === comp.recommended_strategy;
                return (
                  <tr
                    key={`${strat}-${comp.climate_city}`}
                    className={isRecommended ? "bg-green-50/50" : ""}
                  >
                    <td className="px-4 py-2 font-medium text-gray-800">
                      {STRATEGY_LABELS[strat] ?? strat}
                      {isRecommended && (
                        <span className="ml-1.5 rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-700">Best</span>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-1.5">
                        <span
                          className="inline-block h-2 w-2 rounded-full"
                          style={{ backgroundColor: CITY_COLORS[comp.climate_city] ?? "#6B7280" }}
                        />
                        {comp.climate_city}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-right text-gray-600">{r.eui_kwh_m2.toFixed(1)}</td>
                    <td className="px-4 py-2 text-right text-gray-600">{r.total_energy_kwh.toLocaleString()}</td>
                    <td className="px-4 py-2 text-right">
                      {r.savings_pct != null ? (
                        <span className={r.savings_pct > 0 ? "text-green-600 font-medium" : "text-gray-600"}>
                          {r.savings_pct > 0 ? "-" : ""}{r.savings_pct.toFixed(1)}%
                        </span>
                      ) : "-"}
                    </td>
                    <td className="px-4 py-2 text-right text-gray-600">
                      {r.annual_cost_krw != null ? r.annual_cost_krw.toLocaleString() : "-"}
                    </td>
                  </tr>
                );
              }),
            ).filter(Boolean)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
