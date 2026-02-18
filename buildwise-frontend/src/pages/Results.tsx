import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from "recharts";
import { simulationsApi, type EnergyResult } from "@/api/client";
import { Skeleton } from "@/components/Skeleton";
import { showToast } from "@/components/Toast";
import useDocumentTitle from "@/hooks/useDocumentTitle";
import { STRATEGY_LABELS } from "@/constants/strategies";

type SortKey = "strategy" | "eui" | "total" | "hvac" | "savings" | "cost" | "cost_savings";
type SortDir = "asc" | "desc";

export default function Results() {
  const { configId } = useParams<{ configId: string }>();

  useDocumentTitle("Results");

  const { data: comparison, isLoading, isError, refetch } = useQuery({
    queryKey: ["results", configId],
    queryFn: () => simulationsApi.results(configId!).then((r) => r.data),
    enabled: !!configId,
  });

  if (isError) return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-center">
      <p className="text-red-600 font-medium">Failed to load results</p>
      <p className="mt-1 text-sm text-red-400">The simulation may still be running or an error occurred.</p>
      <div className="mt-4 flex justify-center gap-3">
        <button onClick={() => refetch()} className="rounded bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700">
          Retry
        </button>
        <Link to={`/simulations/${configId}/progress`} className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">
          Check Progress
        </Link>
      </div>
    </div>
  );

  if (isLoading || !comparison) return (
    <div className="space-y-6">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-8 w-64" />
      <div className="grid gap-4 sm:grid-cols-4">
        <Skeleton className="h-24 rounded-lg" />
        <Skeleton className="h-24 rounded-lg" />
        <Skeleton className="h-24 rounded-lg" />
        <Skeleton className="h-24 rounded-lg" />
      </div>
      <Skeleton className="h-80 rounded-lg" />
      <Skeleton className="h-80 rounded-lg" />
    </div>
  );

  const [sortKey, setSortKey] = useState<SortKey>("strategy");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "strategy" ? "asc" : "desc");
    }
  };

  const allStrategies: EnergyResult[] = [
    ...(comparison.baseline ? [comparison.baseline] : []),
    ...comparison.strategies,
  ];

  const getValue = (s: EnergyResult, key: SortKey): number | string => {
    switch (key) {
      case "strategy": return STRATEGY_LABELS[s.strategy] ?? s.strategy;
      case "eui": return s.eui_kwh_m2;
      case "total": return s.total_energy_kwh;
      case "hvac": return s.hvac_energy_kwh ?? 0;
      case "savings": return s.savings_pct ?? 0;
      case "cost": return s.annual_cost_krw ?? 0;
      case "cost_savings": return s.annual_savings_krw ?? 0;
    }
  };

  const sortedStrategies = [...allStrategies].sort((a, b) => {
    const va = getValue(a, sortKey);
    const vb = getValue(b, sortKey);
    const cmp = typeof va === "string" ? va.localeCompare(vb as string) : (va as number) - (vb as number);
    return sortDir === "asc" ? cmp : -cmp;
  });

  const sortIcon = (key: SortKey) =>
    sortKey === key ? (sortDir === "asc" ? " \u2191" : " \u2193") : "";

  const euiChartData = allStrategies.map((s) => ({
    strategy: STRATEGY_LABELS[s.strategy] ?? s.strategy,
    "EUI (kWh/m2)": Number(s.eui_kwh_m2.toFixed(1)),
  }));

  const breakdownChartData = allStrategies
    .filter((s) => s.cooling_energy_kwh != null || s.heating_energy_kwh != null)
    .map((s) => ({
      strategy: STRATEGY_LABELS[s.strategy] ?? s.strategy,
      Cooling: s.cooling_energy_kwh ? Number((s.cooling_energy_kwh / 1000).toFixed(1)) : 0,
      Heating: s.heating_energy_kwh ? Number((s.heating_energy_kwh / 1000).toFixed(1)) : 0,
      Fan: s.fan_energy_kwh ? Number((s.fan_energy_kwh / 1000).toFixed(1)) : 0,
    }));

  const downloadCsv = () => {
    const headers = ["Strategy", "EUI (kWh/m2)", "Total (kWh)", "HVAC (kWh)", "Cooling (kWh)", "Heating (kWh)", "Fan (kWh)", "Savings (%)", "Cost (KRW)", "Savings (KRW)"];
    const rows = allStrategies.map((s) => [
      s.strategy,
      s.eui_kwh_m2.toFixed(1),
      s.total_energy_kwh.toFixed(0),
      s.hvac_energy_kwh?.toFixed(0) ?? "",
      s.cooling_energy_kwh?.toFixed(0) ?? "",
      s.heating_energy_kwh?.toFixed(0) ?? "",
      s.fan_energy_kwh?.toFixed(0) ?? "",
      s.savings_pct?.toFixed(1) ?? "",
      s.annual_cost_krw?.toString() ?? "",
      s.annual_savings_krw?.toString() ?? "",
    ]);
    const csv = [headers, ...rows].map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `buildwise-results-${configId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="flex gap-4 text-sm">
        <Link
          to={`/simulations/${configId}/progress`}
          className="text-blue-600 hover:underline"
        >
          &larr; Progress
        </Link>
        <Link
          to={`/projects/${comparison.project_id}/buildings/${comparison.building_id}`}
          className="text-blue-600 hover:underline"
        >
          &larr; Building Editor
        </Link>
      </div>

      <div className="mt-2 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Strategy Comparison
          </h1>
          <p className="text-sm text-gray-500">
            <Link
              to={`/projects/${comparison.project_id}/buildings/${comparison.building_id}`}
              className="hover:text-blue-600 hover:underline"
            >
              {comparison.building_name}
            </Link>
            {" "}&middot; {comparison.building_type.replace(/_/g, " ")} &middot;{" "}
            {comparison.climate_city}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 print:hidden">
          <button
            onClick={() => {
              navigator.clipboard.writeText(window.location.href);
              showToast("Link copied", "success");
            }}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 sm:px-4 sm:py-2"
            title="Copy shareable link"
          >
            <span className="hidden sm:inline">Copy </span>Link
          </button>
          <button
            onClick={() => window.print()}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 sm:px-4 sm:py-2"
          >
            Print
          </button>
          <button
            onClick={downloadCsv}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 sm:px-4 sm:py-2"
          >
            <span className="hidden sm:inline">Download </span>CSV
          </button>
        </div>
      </div>

      {/* Savings Summary Cards */}
      {comparison.baseline && comparison.recommended_strategy && (() => {
        const best = allStrategies.find((s) => s.strategy === comparison.recommended_strategy);
        if (!best) return null;
        const baselineEui = comparison.baseline.eui_kwh_m2;
        const bestEui = best.eui_kwh_m2;
        const savingsPct = best.savings_pct ?? 0;
        const costSavings = best.annual_savings_krw ?? 0;
        const baseCost = comparison.baseline.annual_cost_krw ?? 0;

        return (
          <div className="mt-4 grid gap-4 sm:grid-cols-4">
            <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-center">
              <p className="text-xs text-green-600">Recommended</p>
              <p className="mt-1 text-lg font-bold text-green-800">
                {STRATEGY_LABELS[comparison.recommended_strategy] ?? comparison.recommended_strategy}
              </p>
              <p className="text-xs text-green-500">{comparison.recommendation_reason}</p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4 text-center">
              <p className="text-xs text-gray-500">Energy Savings</p>
              <p className="mt-1 text-2xl font-bold text-blue-600">-{savingsPct.toFixed(1)}%</p>
              <p className="text-xs text-gray-400">{baselineEui.toFixed(0)} → {bestEui.toFixed(0)} kWh/m2</p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4 text-center">
              <p className="text-xs text-gray-500">Annual Cost Savings</p>
              <p className="mt-1 text-2xl font-bold text-green-600">
                {costSavings > 0 ? `${(costSavings / 10000).toFixed(0)}만원` : "-"}
              </p>
              <p className="text-xs text-gray-400">
                {baseCost > 0 ? `Base: ${(baseCost / 10000).toFixed(0)}만원/yr` : ""}
              </p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4 text-center">
              <p className="text-xs text-gray-500">Strategies Compared</p>
              <p className="mt-1 text-2xl font-bold text-gray-800">{allStrategies.length}</p>
              <p className="text-xs text-gray-400">baseline + M0~M8</p>
            </div>
          </div>
        );
      })()}

      {/* EUI Chart */}
      <div className="mt-6 rounded-lg border border-gray-200 bg-white p-5">
        <h3 className="mb-4 font-semibold text-gray-800">
          Energy Use Intensity (EUI)
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={euiChartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="strategy" tick={{ fontSize: 11 }} />
            <YAxis unit=" kWh/m2" tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="EUI (kWh/m2)" fill="#3B82F6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Strategy Radar Chart */}
      {comparison.baseline && allStrategies.length > 2 && (() => {
        const baseEui = comparison.baseline!.eui_kwh_m2;
        const baseCool = comparison.baseline!.cooling_energy_kwh ?? 1;
        const baseHeat = comparison.baseline!.heating_energy_kwh ?? 1;
        const baseFan = comparison.baseline!.fan_energy_kwh ?? 1;
        const basePeak = comparison.baseline!.peak_demand_kw ?? 1;

        // Normalize to 0-100 scale relative to baseline (lower is better)
        const radarData = [
          { metric: "EUI", ...Object.fromEntries(allStrategies.map((s) => [s.strategy, Math.round((s.eui_kwh_m2 / baseEui) * 100)])) },
          { metric: "Cooling", ...Object.fromEntries(allStrategies.map((s) => [s.strategy, Math.round(((s.cooling_energy_kwh ?? baseCool) / baseCool) * 100)])) },
          { metric: "Heating", ...Object.fromEntries(allStrategies.map((s) => [s.strategy, Math.round(((s.heating_energy_kwh ?? baseHeat) / baseHeat) * 100)])) },
          { metric: "Fan", ...Object.fromEntries(allStrategies.map((s) => [s.strategy, Math.round(((s.fan_energy_kwh ?? baseFan) / baseFan) * 100)])) },
          { metric: "Peak", ...Object.fromEntries(allStrategies.map((s) => [s.strategy, Math.round(((s.peak_demand_kw ?? basePeak) / basePeak) * 100)])) },
        ];

        const COLORS = ["#6B7280", "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#14B8A6", "#F97316", "#6366F1"];
        const top = comparison.recommended_strategy
          ? [allStrategies.find((s) => s.strategy === "baseline")!, allStrategies.find((s) => s.strategy === comparison.recommended_strategy)!].filter(Boolean)
          : allStrategies.slice(0, 3);

        return (
          <div className="mt-6 rounded-lg border border-gray-200 bg-white p-5">
            <h3 className="mb-4 font-semibold text-gray-800">
              Strategy Profile (% of Baseline)
            </h3>
            <p className="mb-2 text-xs text-gray-400">Lower values = better performance. 100% = baseline level.</p>
            <ResponsiveContainer width="100%" height={320}>
              <RadarChart data={radarData}>
                <PolarGrid />
                <PolarAngleAxis dataKey="metric" tick={{ fontSize: 12 }} />
                <PolarRadiusAxis angle={90} domain={[0, 110]} tick={{ fontSize: 10 }} />
                {top.map((s, i) => (
                  <Radar
                    key={s.strategy}
                    name={STRATEGY_LABELS[s.strategy] ?? s.strategy}
                    dataKey={s.strategy}
                    stroke={COLORS[i % COLORS.length]}
                    fill={COLORS[i % COLORS.length]}
                    fillOpacity={0.15}
                  />
                ))}
                <Legend />
                <Tooltip />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        );
      })()}

      {/* Energy Breakdown Chart */}
      {breakdownChartData.length > 0 && (
        <div className="mt-6 rounded-lg border border-gray-200 bg-white p-5">
          <h3 className="mb-4 font-semibold text-gray-800">
            Energy Breakdown (MWh)
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={breakdownChartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="strategy" tick={{ fontSize: 11 }} />
              <YAxis unit=" MWh" tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="Cooling" stackId="a" fill="#60A5FA" />
              <Bar dataKey="Heating" stackId="a" fill="#F87171" />
              <Bar dataKey="Fan" stackId="a" fill="#A78BFA" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Detail table */}
      <div className="mt-6 overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              {([
                ["strategy", "Strategy", "text-left"],
                ["eui", "EUI (kWh/m\u00B2)", "text-right"],
                ["total", "Total (kWh)", "text-right"],
                ["hvac", "HVAC (kWh)", "text-right"],
                ["savings", "Savings (%)", "text-right"],
                ["cost", "Cost (KRW)", "text-right"],
                ["cost_savings", "Savings (KRW)", "text-right"],
              ] as [SortKey, string, string][]).map(([key, label, align]) => (
                <th
                  key={key}
                  onClick={() => toggleSort(key)}
                  className={`${key === "strategy" ? "sticky left-0 bg-gray-50 " : ""}px-4 py-3 ${align} font-medium text-gray-600 cursor-pointer select-none hover:text-gray-900`}
                >
                  {label}{sortIcon(key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {sortedStrategies.map((s) => {
              const isRecommended = s.strategy === comparison.recommended_strategy;
              return (
                <tr
                  key={s.strategy}
                  className={isRecommended ? "bg-green-50" : ""}
                >
                  <td className={`sticky left-0 px-4 py-3 font-medium text-gray-900 ${isRecommended ? "bg-green-50" : "bg-white"}`}>
                    {STRATEGY_LABELS[s.strategy] ?? s.strategy}
                    {isRecommended && (
                      <span className="ml-2 rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-700">
                        Best
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600">
                    {s.eui_kwh_m2.toFixed(1)}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600">
                    {s.total_energy_kwh.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600">
                    {s.hvac_energy_kwh != null ? s.hvac_energy_kwh.toLocaleString() : "-"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {s.savings_pct != null ? (
                      <span className={s.savings_pct > 0 ? "text-green-600 font-medium" : "text-gray-600"}>
                        {s.savings_pct > 0 ? "-" : ""}{s.savings_pct.toFixed(1)}%
                      </span>
                    ) : "-"}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600">
                    {s.annual_cost_krw != null ? `${s.annual_cost_krw.toLocaleString()}` : "-"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {s.annual_savings_krw != null && s.annual_savings_krw > 0 ? (
                      <span className="text-green-600 font-medium">
                        {s.annual_savings_krw.toLocaleString()}
                      </span>
                    ) : "-"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
