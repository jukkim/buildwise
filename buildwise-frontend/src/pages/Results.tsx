import { useState, useEffect, useRef, Fragment } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  Cell,
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
  LineChart,
  Line,
} from "recharts";
import { simulationsApi, type EnergyResult } from "@/api/client";
import { Skeleton } from "@/components/Skeleton";
import { showToast } from "@/components/Toast";
import useDocumentTitle from "@/hooks/useDocumentTitle";
import { STRATEGY_LABELS, STRATEGY_DESCRIPTIONS } from "@/constants/strategies";
import Breadcrumb from "@/components/Breadcrumb";
import { PdfChartRenderer } from "@/features/pdf-report";

type SortKey = "strategy" | "eui" | "total" | "hvac" | "savings" | "cost" | "cost_savings";
type SortDir = "asc" | "desc";

const PERIOD_LABELS: Record<string, string> = {
  "1year": "Full Year",
  "1month_summer": "Summer (Aug)",
  "1month_winter": "Winter (Jan)",
};

export default function Results() {
  const { configId } = useParams<{ configId: string }>();
  const navigate = useNavigate();
  const [sortKey, setSortKey] = useState<SortKey>("strategy");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [selectedRow, setSelectedRow] = useState<string | null>(null);
  const [allExpanded, setAllExpanded] = useState(true);
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);
  const [showPdfCharts, setShowPdfCharts] = useState(false);
  const pdfChartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = () => setShowScrollTop(window.scrollY > 400);
    window.addEventListener("scroll", handler, { passive: true });
    return () => window.removeEventListener("scroll", handler);
  }, []);

  const { data: comparison, isLoading, isError, refetch } = useQuery({
    queryKey: ["results", configId],
    queryFn: () => simulationsApi.results(configId!).then((r) => r.data),
    enabled: !!configId,
  });

  useDocumentTitle(comparison ? `Results: ${comparison.building_name}` : "Results");

  const rerunMutation = useMutation({
    mutationFn: () =>
      simulationsApi.start(
        comparison!.building_id,
        comparison!.climate_city,
        comparison!.period_type ?? "1year",
      ),
    onSuccess: (res) => {
      showToast("Simulation started", "success");
      navigate(`/simulations/${res.data.config_id}/progress`);
    },
    onError: () => showToast("Failed to start simulation"),
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

  if (allStrategies.length === 0) {
    return (
      <div className="rounded-xl bg-white shadow-sm p-12 text-center">
        <svg className="mx-auto h-12 w-12 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <h3 className="mt-3 text-sm font-medium text-gray-900">No results available</h3>
        <p className="mt-1 text-sm text-gray-500">The simulation didn't produce any strategy results.</p>
        <Link
          to={`/simulations/${configId}/progress`}
          className="mt-4 inline-block rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Check Progress
        </Link>
      </div>
    );
  }

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

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sortKey !== col) return <span className="ml-1 inline-block w-3" />;
    return (
      <svg className="ml-1 inline-block h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        {sortDir === "asc"
          ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
          : <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />}
      </svg>
    );
  };

  const STRATEGY_COLORS: Record<string, string> = {
    baseline: "#6B7280",
    M0: "#3B82F6", M1: "#10B981", M2: "#F59E0B", M3: "#EF4444",
    M4: "#8B5CF6", M5: "#EC4899", M6: "#14B8A6", M7: "#F97316", M8: "#6366F1",
  };

  const euiChartData = allStrategies.map((s) => ({
    strategy: STRATEGY_LABELS[s.strategy] ?? s.strategy,
    strategyKey: s.strategy,
    "EUI (kWh/m2)": Number(s.eui_kwh_m2.toFixed(1)),
    fill: s.strategy === comparison.recommended_strategy
      ? "#059669"
      : STRATEGY_COLORS[s.strategy] ?? "#3B82F6",
  }));

  const breakdownChartData = allStrategies
    .filter((s) => s.cooling_energy_kwh != null || s.heating_energy_kwh != null)
    .map((s) => ({
      strategy: STRATEGY_LABELS[s.strategy] ?? s.strategy,
      Cooling: s.cooling_energy_kwh ? Number((s.cooling_energy_kwh / 1000).toFixed(1)) : 0,
      Heating: s.heating_energy_kwh ? Number((s.heating_energy_kwh / 1000).toFixed(1)) : 0,
      Fan: s.fan_energy_kwh ? Number((s.fan_energy_kwh / 1000).toFixed(1)) : 0,
      Pump: s.pump_energy_kwh ? Number((s.pump_energy_kwh / 1000).toFixed(1)) : 0,
      Lighting: s.lighting_energy_kwh ? Number((s.lighting_energy_kwh / 1000).toFixed(1)) : 0,
      Equipment: s.equipment_energy_kwh ? Number((s.equipment_energy_kwh / 1000).toFixed(1)) : 0,
    }));

  const costChartData = allStrategies
    .filter((s) => s.annual_cost_krw != null)
    .map((s) => ({
      strategy: STRATEGY_LABELS[s.strategy] ?? s.strategy,
      strategyKey: s.strategy,
      "Cost (만원)": Number((s.annual_cost_krw! / 10000).toFixed(0)),
      fill: s.strategy === comparison.recommended_strategy
        ? "#059669"
        : STRATEGY_COLORS[s.strategy] ?? "#3B82F6",
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
    const filename = `buildwise-results-${configId}.csv`;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    showToast(`Downloaded ${filename}`, "success");
  };

  const copyTable = () => {
    const headers = ["Strategy", "EUI (kWh/m2)", "Total (kWh)", "HVAC (kWh)", "Savings (%)", "Cost (KRW)", "Savings (KRW)"];
    const rows = allStrategies.map((s) => [
      STRATEGY_LABELS[s.strategy] ?? s.strategy,
      s.eui_kwh_m2.toFixed(1),
      s.total_energy_kwh.toFixed(0),
      s.hvac_energy_kwh?.toFixed(0) ?? "",
      s.savings_pct?.toFixed(1) ?? "",
      s.annual_cost_krw?.toString() ?? "",
      s.annual_savings_krw?.toString() ?? "",
    ]);
    const tsv = [headers, ...rows].map((r) => r.join("\t")).join("\n");
    navigator.clipboard.writeText(tsv).then(
      () => showToast("Table copied to clipboard", "success"),
      () => showToast("Failed to copy to clipboard"),
    );
  };

  const copySummary = () => {
    const best = comparison.recommended_strategy
      ? allStrategies.find((s) => s.strategy === comparison.recommended_strategy)
      : null;
    const lines = [
      `BuildWise Results: ${comparison.building_name}`,
      `Building: ${comparison.building_type.replace(/_/g, " ")} | City: ${comparison.climate_city}`,
      `Strategies compared: ${allStrategies.length}`,
      best
        ? `Recommended: ${STRATEGY_LABELS[best.strategy] ?? best.strategy} (EUI ${best.eui_kwh_m2.toFixed(1)} kWh/m², ${best.savings_pct?.toFixed(1) ?? 0}% savings)`
        : "",
      comparison.baseline
        ? `Baseline EUI: ${comparison.baseline.eui_kwh_m2.toFixed(1)} kWh/m²`
        : "",
    ].filter(Boolean);
    navigator.clipboard.writeText(lines.join("\n")).then(
      () => showToast("Summary copied", "success"),
      () => showToast("Failed to copy summary"),
    );
  };

  const downloadPdf = async () => {
    setIsGeneratingPdf(true);
    setShowPdfCharts(true);
    try {
      // Wait for Recharts to render in the hidden container
      await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 600)));
      const { generateReport } = await import("@/features/pdf-report");
      await generateReport({
        comparison,
        allStrategies,
        chartContainer: pdfChartRef.current!,
      });
      showToast("PDF report downloaded", "success");
    } catch (err) {
      console.error("PDF generation failed:", err);
      showToast("Failed to generate PDF report");
    } finally {
      setShowPdfCharts(false);
      setIsGeneratingPdf(false);
    }
  };

  return (
    <div>
      <Breadcrumb items={[
        { label: "Projects", to: "/projects" },
        { label: comparison.building_name, to: `/projects/${comparison.project_id}/buildings/${comparison.building_id}` },
        { label: "Results" },
      ]} />

      {/* Print-only header */}
      <div className="hidden print:block mb-4 border-b border-gray-300 pb-3">
        <h1 className="text-xl font-bold">BuildWise Energy Report</h1>
        <p className="text-sm text-gray-600">
          {comparison.building_name} &middot; {comparison.building_type.replace(/_/g, " ")} &middot; {comparison.climate_city}
          &middot; {allStrategies.length} strategies &middot; Generated {new Date().toLocaleDateString()}
        </p>
        {comparison.recommended_strategy && (
          <p className="text-sm text-gray-600 mt-1">
            Recommended: {STRATEGY_LABELS[comparison.recommended_strategy] ?? comparison.recommended_strategy}
          </p>
        )}
      </div>

      <div className="mt-2 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">
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
            {comparison.period_type && (
              <> &middot; {PERIOD_LABELS[comparison.period_type] ?? comparison.period_type}</>
            )}
          </p>
          <div className="mt-1 flex items-center gap-2">
            <span className={`inline-block rounded px-2 py-0.5 text-xs ${
              {
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
              }[comparison.building_type] ?? "bg-gray-100 text-gray-700"
            }`}>
              {comparison.building_type.replace(/_/g, " ")}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 print:hidden">
          <button
            onClick={copySummary}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 sm:px-4 sm:py-2"
            title="Copy text summary of results"
          >
            Summary
          </button>
          <button
            onClick={() => {
              navigator.clipboard.writeText(window.location.href).then(
                () => showToast("Link copied", "success"),
                () => showToast("Failed to copy link"),
              );
            }}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 sm:px-4 sm:py-2"
            title="Copy shareable link"
          >
            <span className="hidden sm:inline">Copy </span>Link
          </button>
          <button
            onClick={copyTable}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 sm:px-4 sm:py-2"
            title="Copy table data for spreadsheet"
          >
            <span className="hidden sm:inline">Copy </span>Table
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
          <button
            onClick={downloadPdf}
            disabled={isGeneratingPdf}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 sm:px-4 sm:py-2"
          >
            {isGeneratingPdf ? (
              <span className="flex items-center gap-1.5">
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                PDF...
              </span>
            ) : (
              <><span className="hidden sm:inline">Download </span>PDF</>
            )}
          </button>
          <button
            onClick={() => rerunMutation.mutate()}
            disabled={rerunMutation.isPending}
            className="rounded-lg bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 sm:px-4 sm:py-2"
          >
            {rerunMutation.isPending ? "Starting..." : "Re-run"}
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
          <div className="mt-4 grid gap-3 sm:grid-cols-4">
            <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-emerald-500 via-green-500 to-teal-600 p-5 text-center text-white shadow-xl shadow-green-500/25">
              <div className="absolute -right-3 -top-3 h-16 w-16 rounded-full bg-white/10" />
              <p className="text-xs font-medium text-white/70">Recommended</p>
              <p className="mt-1 text-lg font-bold">
                {STRATEGY_LABELS[comparison.recommended_strategy] ?? comparison.recommended_strategy}
              </p>
            </div>
            <div className="rounded-xl bg-gradient-to-br from-blue-50 to-blue-100/50 p-4 text-center shadow-sm ring-1 ring-blue-100">
              <p className="text-xs font-medium text-gray-400">Energy Savings</p>
              <p className={`mt-1 text-2xl font-bold ${savingsPct > 0 ? "text-blue-600" : "text-red-500"}`}>
                {savingsPct > 0 ? "-" : "+"}{Math.abs(savingsPct).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-400">{baselineEui.toFixed(0)} → {bestEui.toFixed(0)} kWh/m²</p>
            </div>
            <div className="rounded-xl bg-gradient-to-br from-emerald-50 to-emerald-100/50 p-4 text-center shadow-sm ring-1 ring-emerald-100">
              <p className="text-xs font-medium text-gray-400">Annual Cost Savings</p>
              <p className="mt-1 text-2xl font-bold text-emerald-600">
                {costSavings > 0 ? `${(costSavings / 10000).toFixed(0)}만원` : "-"}
              </p>
              <p className="text-xs text-gray-400">
                {baseCost > 0 ? `Base: ${(baseCost / 10000).toFixed(0)}만원/yr` : ""}
              </p>
            </div>
            <div className="rounded-xl bg-gradient-to-br from-gray-50 to-slate-100/50 p-4 text-center shadow-sm ring-1 ring-gray-200">
              <p className="text-xs font-medium text-gray-400">Strategies Compared</p>
              <p className="mt-1 text-2xl font-bold text-gray-800">{allStrategies.length}</p>
              <p className="text-xs text-gray-400">baseline + M0~M8</p>
            </div>
          </div>
        );
      })()}

      {/* Mock mode disclaimer */}
      {allStrategies.some((s) => s.is_mock) && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <svg className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <div>
            <p className="text-sm font-medium text-amber-800">Demo Mode Results</p>
            <p className="text-xs text-amber-600">
              These results are statistical approximations based on reference simulation data,
              not actual EnergyPlus outputs. Values are calibrated against 100+ validated
              simulations but may differ from real building performance.
            </p>
          </div>
        </div>
      )}

      {/* Recommendation reason */}
      {comparison.recommendation_reason && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-green-100 bg-green-50/50 px-4 py-3">
          <svg className="mt-0.5 h-4 w-4 shrink-0 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-green-700">{comparison.recommendation_reason}</p>
        </div>
      )}

      {/* Expand/Collapse All */}
      <div className="mt-6 flex justify-end print:hidden">
        <button
          onClick={() => {
            const next = !allExpanded;
            setAllExpanded(next);
            setCollapsed(next ? {} : { eui: true, radar: true, breakdown: true });
          }}
          className="text-xs text-gray-400 hover:text-gray-600"
        >
          {allExpanded ? "Collapse All Charts" : "Expand All Charts"}
        </button>
      </div>

      {/* EUI Chart */}
      <div className="mt-2 rounded-xl bg-white shadow-sm">
        <button
          onClick={() => setCollapsed((c) => ({ ...c, eui: !c.eui }))}
          className="flex w-full items-center justify-between p-5 text-left"
        >
          <h3 className="font-semibold text-gray-800">
            Energy Use Intensity (EUI)
            {comparison.recommended_strategy && (
              <span className="ml-2 text-xs font-normal text-green-600">
                ★ {STRATEGY_LABELS[comparison.recommended_strategy] ?? comparison.recommended_strategy} recommended
              </span>
            )}
          </h3>
          <svg className={`h-5 w-5 text-gray-400 transition-transform ${collapsed.eui ? "" : "rotate-180"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {!collapsed.eui && (
          <div className="px-5 pb-5">
            {euiChartData.length === 0 ? (
              <div className="flex h-[300px] items-center justify-center text-sm text-gray-400">
                No EUI data available
              </div>
            ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={euiChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="strategy" tick={{ fontSize: 11 }} />
                <YAxis unit=" kWh/m2" tick={{ fontSize: 11 }} />
                <Tooltip content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload;
                  const desc = STRATEGY_DESCRIPTIONS[d.strategyKey];
                  return (
                    <div className="rounded-xl bg-white shadow-sm px-3 py-2 shadow-lg text-xs">
                      <p className="font-medium text-gray-900">{d.strategy}</p>
                      <p className="text-gray-600">{d["EUI (kWh/m2)"]} kWh/m²</p>
                      {desc && <p className="mt-1 text-gray-400 max-w-[200px]">{desc}</p>}
                    </div>
                  );
                }} />
                <Legend />
                <Bar dataKey="EUI (kWh/m2)" radius={[4, 4, 0, 0]}>
                  {euiChartData.map((entry, index) => (
                    <Cell key={index} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            )}
          </div>
        )}
      </div>

      {/* Strategy Radar Chart */}
      {comparison.baseline && allStrategies.length > 2 && (() => {
        const baseEui = comparison.baseline!.eui_kwh_m2;
        const baseCool = comparison.baseline!.cooling_energy_kwh || 1;
        const baseHeat = comparison.baseline!.heating_energy_kwh || 1;
        const baseFan = comparison.baseline!.fan_energy_kwh || 1;
        const basePeak = comparison.baseline!.peak_demand_kw || 1;

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
          <div className="mt-6 rounded-xl bg-white shadow-sm">
            <button
              onClick={() => setCollapsed((c) => ({ ...c, radar: !c.radar }))}
              className="flex w-full items-center justify-between p-5 text-left"
            >
              <h3 className="font-semibold text-gray-800">Strategy Profile (% of Baseline)</h3>
              <svg className={`h-5 w-5 text-gray-400 transition-transform ${collapsed.radar ? "" : "rotate-180"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {!collapsed.radar && (
              <div className="px-5 pb-5">
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
            )}
          </div>
        );
      })()}

      {/* Energy Breakdown Chart */}
      {breakdownChartData.length > 0 && (
        <div className="mt-6 rounded-xl bg-white shadow-sm">
          <button
            onClick={() => setCollapsed((c) => ({ ...c, breakdown: !c.breakdown }))}
            className="flex w-full items-center justify-between p-5 text-left"
          >
            <h3 className="font-semibold text-gray-800">Energy Breakdown (MWh)</h3>
            <svg className={`h-5 w-5 text-gray-400 transition-transform ${collapsed.breakdown ? "" : "rotate-180"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {!collapsed.breakdown && (
            <div className="px-5 pb-5">
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
                  <Bar dataKey="Pump" stackId="a" fill="#34D399" />
                  <Bar dataKey="Lighting" stackId="a" fill="#FBBF24" />
                  <Bar dataKey="Equipment" stackId="a" fill="#FB923C" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Cost comparison chart */}
      {costChartData.length > 1 && (
        <div className="mt-6 rounded-xl bg-white shadow-sm">
          <button
            onClick={() => setCollapsed((c) => ({ ...c, cost: !c.cost }))}
            className="flex w-full items-center justify-between p-5 text-left"
          >
            <h3 className="font-semibold text-gray-800">
              Annual Energy Cost (만원/yr)
              {comparison.baseline?.annual_cost_krw && (
                <span className="ml-2 text-xs font-normal text-gray-400">
                  baseline: {(comparison.baseline.annual_cost_krw / 10000).toFixed(0)}만원
                </span>
              )}
            </h3>
            <svg className={`h-5 w-5 text-gray-400 transition-transform ${collapsed.cost ? "" : "rotate-180"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {!collapsed.cost && (
            <div className="px-5 pb-5">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={costChartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="strategy" tick={{ fontSize: 11 }} />
                  <YAxis unit=" 만원" tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="Cost (만원)" radius={[4, 4, 0, 0]}>
                    {costChartData.map((entry, index) => (
                      <Cell key={index} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Monthly Energy Profile */}
      {(() => {
        const recommended = comparison.recommended_strategy
          ? allStrategies.find((s) => s.strategy === comparison.recommended_strategy)
          : null;
        const profileSource = recommended ?? comparison.baseline ?? allStrategies[0];
        const monthlyData = profileSource?.monthly_profile;
        if (!monthlyData || monthlyData.length === 0) return null;
        return (
          <div className="mt-6 rounded-xl bg-white shadow-sm">
            <button
              onClick={() => setCollapsed((c) => ({ ...c, monthly: !c.monthly }))}
              className="flex w-full items-center justify-between p-5 text-left"
            >
              <h3 className="font-semibold text-gray-800">
                Monthly Energy Profile
                <span className="ml-2 text-xs font-normal text-gray-400">
                  {STRATEGY_LABELS[profileSource.strategy] ?? profileSource.strategy}
                </span>
              </h3>
              <svg className={`h-5 w-5 text-gray-400 transition-transform ${collapsed.monthly ? "" : "rotate-180"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {!collapsed.monthly && (
              <div className="px-5 pb-5">
                <ResponsiveContainer width="100%" height={320}>
                  <LineChart data={monthlyData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis unit=" kWh" tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="total" stroke="#374151" strokeWidth={2} name="Total" />
                    <Line type="monotone" dataKey="cooling" stroke="#60A5FA" name="Cooling" />
                    <Line type="monotone" dataKey="heating" stroke="#F87171" name="Heating" />
                    <Line type="monotone" dataKey="lighting" stroke="#FBBF24" name="Lighting" />
                    <Line type="monotone" dataKey="equipment" stroke="#FB923C" name="Equipment" />
                    <Line type="monotone" dataKey="fan" stroke="#A78BFA" name="Fan" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        );
      })()}

      {/* Detail table */}
      <div className="mt-6 overflow-x-auto overflow-y-auto max-h-[70vh] rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 sticky top-0 z-10">
            <tr>
              {([
                ["strategy", "Strategy", "text-left", ""],
                ["eui", "EUI (kWh/m\u00B2)", "text-right", ""],
                ["total", "Total (kWh)", "text-right", "hidden sm:table-cell"],
                ["hvac", "HVAC (kWh)", "text-right", "hidden md:table-cell"],
                ["savings", "Savings (%)", "text-right", ""],
                ["cost", "Cost (KRW)", "text-right", "hidden lg:table-cell"],
                ["cost_savings", "Savings (KRW)", "text-right", "hidden sm:table-cell"],
              ] as [SortKey, string, string, string][]).map(([key, label, align, responsive]) => (
                <th
                  key={key}
                  onClick={() => toggleSort(key)}
                  className={`${key === "strategy" ? "sticky left-0 bg-gray-50 " : ""}${responsive ? responsive + " " : ""}px-4 py-3 ${align} font-medium text-gray-600 cursor-pointer select-none hover:text-gray-900`}
                >
                  {label}<SortIcon col={key} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {(() => {
              const nonBaseline = allStrategies.filter((s) => s.strategy !== "baseline");
              const worstStrategy = nonBaseline.length > 1
                ? nonBaseline.reduce((worst, s) => s.eui_kwh_m2 > worst.eui_kwh_m2 ? s : worst).strategy
                : null;
              return sortedStrategies.map((s, rowIdx) => {
              const isRecommended = s.strategy === comparison.recommended_strategy;
              const isWorst = s.strategy === worstStrategy && s.strategy !== comparison.recommended_strategy;
              const baselineEui = comparison.baseline?.eui_kwh_m2;
              const euiDelta = baselineEui && s.strategy !== "baseline"
                ? s.eui_kwh_m2 - baselineEui
                : null;
              const isSelected = selectedRow === s.strategy;
              return (
                <Fragment key={s.strategy}>
                <tr
                  onClick={() => setSelectedRow(isSelected ? null : s.strategy)}
                  onDoubleClick={() => {
                    const text = `${STRATEGY_LABELS[s.strategy] ?? s.strategy}: EUI ${s.eui_kwh_m2.toFixed(1)} kWh/m², ${s.savings_pct != null ? `${s.savings_pct.toFixed(1)}% savings` : "baseline"}${s.annual_cost_krw ? `, ${(s.annual_cost_krw / 10000).toFixed(0)}만원/yr` : ""}`;
                    navigator.clipboard.writeText(text).then(
                      () => showToast("Strategy result copied", "success"),
                      () => showToast("Failed to copy"),
                    );
                  }}
                  title="Click to expand, double-click to copy"
                  className={`cursor-pointer transition-colors ${isSelected ? "ring-2 ring-blue-400 ring-inset" : ""} ${isRecommended ? "bg-green-50 border-l-4 border-l-green-500" : isWorst ? "bg-red-50/50 border-l-4 border-l-red-300" : s.strategy === "baseline" ? "bg-gray-50/70 border-l-4 border-l-gray-300" : "hover:bg-gray-50 border-l-4 border-l-transparent"}`}
                >
                  <td className={`sticky left-0 px-4 py-3 font-medium text-gray-900 ${isRecommended ? "bg-green-50" : isWorst ? "bg-red-50/50" : s.strategy === "baseline" ? "bg-gray-50" : "bg-white group-hover:bg-gray-50"}`}>
                    <span className="mr-2 text-xs text-gray-400">#{rowIdx + 1}</span>
                    <span title={STRATEGY_DESCRIPTIONS[s.strategy] ?? ""}>{STRATEGY_LABELS[s.strategy] ?? s.strategy}</span>
                    {isRecommended && (
                      <span className="ml-2 rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-700">
                        Best
                      </span>
                    )}
                    {isWorst && (
                      <span className="ml-2 rounded bg-red-100 px-1.5 py-0.5 text-xs text-red-600">
                        Highest
                      </span>
                    )}
                    {s.strategy === "baseline" && !isRecommended && (
                      <span className="ml-2 rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">
                        Reference
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600">
                    <div className="flex items-center justify-end gap-2">
                      {(() => {
                        const maxEui = Math.max(...allStrategies.map((st) => st.eui_kwh_m2));
                        const pct = maxEui > 0 ? (s.eui_kwh_m2 / maxEui) * 100 : 0;
                        return (
                          <span className="hidden sm:inline-block w-12 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                            <span
                              className={`block h-full rounded-full ${isRecommended ? "bg-green-400" : "bg-blue-300"}`}
                              style={{ width: `${pct}%` }}
                            />
                          </span>
                        );
                      })()}
                      <span>
                        {s.eui_kwh_m2.toFixed(1)}
                        {euiDelta != null && (
                          <span className={`ml-1 text-xs ${euiDelta < 0 ? "text-green-500" : euiDelta > 0 ? "text-red-400" : "text-gray-400"}`}>
                            ({euiDelta > 0 ? "+" : ""}{euiDelta.toFixed(1)})
                          </span>
                        )}
                      </span>
                    </div>
                  </td>
                  <td className="hidden sm:table-cell px-4 py-3 text-right text-gray-600">
                    {s.total_energy_kwh.toLocaleString()}
                  </td>
                  <td className="hidden md:table-cell px-4 py-3 text-right text-gray-600">
                    {s.hvac_energy_kwh != null ? s.hvac_energy_kwh.toLocaleString() : "-"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {s.savings_pct != null ? (
                      <div className="flex items-center justify-end gap-2">
                        <div className="hidden sm:block w-16 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                          <div
                            className={`h-full rounded-full ${s.savings_pct > 0 ? "bg-green-500" : "bg-gray-300"}`}
                            style={{ width: `${Math.min(100, Math.abs(s.savings_pct) * 2)}%` }}
                          />
                        </div>
                        <span className={s.savings_pct > 0 ? "text-green-600 font-medium" : "text-gray-600"}>
                          {s.savings_pct > 0 ? "-" : ""}{s.savings_pct.toFixed(1)}%
                        </span>
                      </div>
                    ) : "-"}
                  </td>
                  <td className="hidden lg:table-cell px-4 py-3 text-right text-gray-600">
                    {s.annual_cost_krw != null ? `${s.annual_cost_krw.toLocaleString()}` : "-"}
                  </td>
                  <td className="hidden sm:table-cell px-4 py-3 text-right">
                    {s.annual_savings_krw != null && s.annual_savings_krw > 0 ? (
                      <span className="text-green-600 font-medium">
                        {s.annual_savings_krw.toLocaleString()}
                      </span>
                    ) : "-"}
                  </td>
                </tr>
                {isSelected && (
                  <tr className="bg-blue-50/50">
                    <td colSpan={7} className="px-6 py-3">
                      <div className="flex flex-wrap gap-6 text-xs text-gray-600">
                        {s.cooling_energy_kwh != null && (
                          <div>
                            <span className="text-gray-400">Cooling</span>
                            <p className="font-medium">{(s.cooling_energy_kwh / 1000).toFixed(1)} MWh</p>
                          </div>
                        )}
                        {s.heating_energy_kwh != null && (
                          <div>
                            <span className="text-gray-400">Heating</span>
                            <p className="font-medium">{(s.heating_energy_kwh / 1000).toFixed(1)} MWh</p>
                          </div>
                        )}
                        {s.fan_energy_kwh != null && (
                          <div>
                            <span className="text-gray-400">Fan</span>
                            <p className="font-medium">{(s.fan_energy_kwh / 1000).toFixed(1)} MWh</p>
                          </div>
                        )}
                        {s.peak_demand_kw != null && (
                          <div>
                            <span className="text-gray-400">Peak Demand</span>
                            <p className="font-medium">{s.peak_demand_kw.toFixed(1)} kW</p>
                          </div>
                        )}
                        {s.total_energy_kwh != null && (
                          <div>
                            <span className="text-gray-400">Total</span>
                            <p className="font-medium">{(s.total_energy_kwh / 1000).toFixed(1)} MWh</p>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
                </Fragment>
              );
            });
            })()}
          </tbody>
          <tfoot className="bg-gray-50 border-t border-gray-200">
            {(() => {
              const nonBaseline = allStrategies.filter((s) => s.strategy !== "baseline");
              if (nonBaseline.length === 0) return null;
              const avgEui = nonBaseline.reduce((sum, s) => sum + s.eui_kwh_m2, 0) / nonBaseline.length;
              const avgSavings = nonBaseline.filter((s) => s.savings_pct != null).reduce((sum, s) => sum + (s.savings_pct ?? 0), 0) / (nonBaseline.filter((s) => s.savings_pct != null).length || 1);
              return (
                <tr className="text-xs text-gray-500">
                  <td className="sticky left-0 bg-gray-50 px-4 py-2 font-medium">Average (strategies)</td>
                  <td className="px-4 py-2 text-right">{avgEui.toFixed(1)}</td>
                  <td className="hidden sm:table-cell px-4 py-2 text-right">-</td>
                  <td className="hidden md:table-cell px-4 py-2 text-right">-</td>
                  <td className="px-4 py-2 text-right">{avgSavings > 0 ? `-${avgSavings.toFixed(1)}%` : `${avgSavings.toFixed(1)}%`}</td>
                  <td className="hidden lg:table-cell px-4 py-2 text-right">-</td>
                  <td className="hidden sm:table-cell px-4 py-2 text-right">-</td>
                </tr>
              );
            })()}
          </tfoot>
        </table>
      </div>

      {/* Table summary */}
      {comparison.baseline && comparison.recommended_strategy && (() => {
        const best = allStrategies.find((s) => s.strategy === comparison.recommended_strategy);
        if (!best || !best.savings_pct) return null;
        return (
          <p className="mt-3 text-sm text-gray-500 text-center">
            <span className="font-medium text-green-600">{STRATEGY_LABELS[best.strategy] ?? best.strategy}</span>
            {" "}saves {best.savings_pct.toFixed(1)}% energy vs baseline
            {best.annual_savings_krw ? ` (${(best.annual_savings_krw / 10000).toFixed(0)}만원/yr)` : ""}
          </p>
        );
      })()}

      {/* Hidden PDF chart renderer */}
      {showPdfCharts && (
        <PdfChartRenderer ref={pdfChartRef} comparison={comparison} allStrategies={allStrategies} />
      )}

      {/* Scroll to top */}
      {showScrollTop && (
        <button
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="fixed bottom-6 right-6 z-40 rounded-full bg-blue-600 p-3 text-white shadow-lg hover:bg-blue-700 print:hidden transition-opacity"
          title="Scroll to top"
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
          </svg>
        </button>
      )}
    </div>
  );
}
