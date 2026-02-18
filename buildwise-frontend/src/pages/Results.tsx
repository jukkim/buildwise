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
} from "recharts";
import { simulationsApi, type EnergyResult } from "@/api/client";

const STRATEGY_LABELS: Record<string, string> = {
  baseline: "Baseline",
  m0: "M0 Night Stop",
  m1: "M1 Smart Start",
  m2: "M2 Economizer",
  m3: "M3 Setpoint",
  m4: "M4 Chiller",
  m5: "M5 DCV",
  m6: "M6 Integrated",
  m7: "M7 Full Normal",
  m8: "M8 Full Savings",
};

export default function Results() {
  const { configId } = useParams<{ configId: string }>();

  const { data: comparison, isLoading } = useQuery({
    queryKey: ["results", configId],
    queryFn: () => simulationsApi.results(configId!).then((r) => r.data),
    enabled: !!configId,
  });

  if (isLoading || !comparison) return <div className="text-gray-500">Loading...</div>;

  const allStrategies: EnergyResult[] = [
    ...(comparison.baseline ? [comparison.baseline] : []),
    ...comparison.strategies,
  ];

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
        <button
          onClick={downloadCsv}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Download CSV
        </button>
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
              <th className="px-4 py-3 text-left font-medium text-gray-600">Strategy</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">EUI (kWh/m2)</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">Total (kWh)</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">HVAC (kWh)</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">Savings (%)</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">Cost (KRW)</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">Savings (KRW)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {allStrategies.map((s) => {
              const isRecommended = s.strategy === comparison.recommended_strategy;
              return (
                <tr
                  key={s.strategy}
                  className={isRecommended ? "bg-green-50" : ""}
                >
                  <td className="px-4 py-3 font-medium text-gray-900">
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
