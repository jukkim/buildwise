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

export default function Results() {
  const { configId } = useParams<{ configId: string }>();

  const { data: comparison, isLoading } = useQuery({
    queryKey: ["results", configId],
    queryFn: () => simulationsApi.results(configId!).then((r) => r.data),
    enabled: !!configId,
  });

  if (isLoading || !comparison) return <div className="text-gray-500">Loading...</div>;

  // Merge baseline + strategies for chart data
  const allStrategies: EnergyResult[] = [
    ...(comparison.baseline ? [comparison.baseline] : []),
    ...comparison.strategies,
  ];

  const chartData = allStrategies.map((s) => ({
    strategy: s.strategy,
    "EUI (kWh/m2)": Number(s.eui_kwh_m2.toFixed(1)),
    "Savings (%)": s.savings_pct ? Number(s.savings_pct.toFixed(1)) : 0,
  }));

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">
        Strategy Comparison
      </h1>
      <p className="text-sm text-gray-500 mb-6">
        {comparison.building_name} &middot; {comparison.building_type} &middot;{" "}
        {comparison.climate_city}
      </p>

      {comparison.recommended_strategy && (
        <div className="mb-6 rounded-lg border border-green-200 bg-green-50 p-4">
          <p className="text-sm font-medium text-green-800">
            Recommended: {comparison.recommended_strategy}
          </p>
          <p className="text-xs text-green-600">
            {comparison.recommendation_reason}
          </p>
        </div>
      )}

      {/* EUI Chart */}
      <div className="mb-8 rounded-lg border border-gray-200 bg-white p-5">
        <h3 className="mb-4 font-semibold text-gray-800">
          Energy Use Intensity (EUI)
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="strategy" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="EUI (kWh/m2)" fill="#3B82F6" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Detail table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">
                Strategy
              </th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">
                EUI (kWh/m2)
              </th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">
                Total (kWh)
              </th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">
                Savings (%)
              </th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">
                Cost (KRW)
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {allStrategies.map((s) => (
              <tr key={s.strategy}>
                <td className="px-4 py-3 font-medium text-gray-900">
                  {s.strategy}
                </td>
                <td className="px-4 py-3 text-right text-gray-600">
                  {s.eui_kwh_m2.toFixed(1)}
                </td>
                <td className="px-4 py-3 text-right text-gray-600">
                  {s.total_energy_kwh.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right text-gray-600">
                  {s.savings_pct != null ? `${s.savings_pct.toFixed(1)}%` : "-"}
                </td>
                <td className="px-4 py-3 text-right text-gray-600">
                  {s.annual_cost_krw != null
                    ? `${s.annual_cost_krw.toLocaleString()}`
                    : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-6">
        <Link
          to={`/simulations/${configId}/progress`}
          className="text-sm text-blue-600 hover:underline"
        >
          &larr; Back to Progress
        </Link>
      </div>
    </div>
  );
}
