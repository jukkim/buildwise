import { forwardRef } from "react";
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  LineChart,
  Line,
} from "recharts";
import type { StrategyComparison, EnergyResult } from "@/api/client";
import { STRATEGY_LABELS } from "@/constants/strategies";

const STRATEGY_COLORS: Record<string, string> = {
  baseline: "#6B7280",
  M0: "#3B82F6", M1: "#10B981", M2: "#F59E0B", M3: "#EF4444",
  M4: "#8B5CF6", M5: "#EC4899", M6: "#14B8A6", M7: "#F97316", M8: "#6366F1",
};

const RADAR_COLORS = ["#6B7280", "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#14B8A6", "#F97316", "#6366F1"];

interface Props {
  comparison: StrategyComparison;
  allStrategies: EnergyResult[];
}

const PdfChartRenderer = forwardRef<HTMLDivElement, Props>(
  ({ comparison, allStrategies }, ref) => {
    const W = 700;
    const H = 300;

    /* ── EUI chart data ── */
    const euiData = allStrategies.map((s) => ({
      strategy: STRATEGY_LABELS[s.strategy] ?? s.strategy,
      strategyKey: s.strategy,
      "EUI (kWh/m²)": Number(s.eui_kwh_m2.toFixed(1)),
      fill:
        s.strategy === comparison.recommended_strategy
          ? "#059669"
          : STRATEGY_COLORS[s.strategy] ?? "#3B82F6",
    }));

    /* ── Breakdown chart data ── */
    const breakdownData = allStrategies
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

    /* ── Cost chart data ── */
    const costData = allStrategies
      .filter((s) => s.annual_cost_krw != null)
      .map((s) => ({
        strategy: STRATEGY_LABELS[s.strategy] ?? s.strategy,
        strategyKey: s.strategy,
        "Cost (만원)": Number((s.annual_cost_krw! / 10000).toFixed(0)),
        fill:
          s.strategy === comparison.recommended_strategy
            ? "#059669"
            : STRATEGY_COLORS[s.strategy] ?? "#3B82F6",
      }));

    /* ── Radar chart data ── */
    const hasRadar = comparison.baseline && allStrategies.length > 2;
    let radarData: Record<string, unknown>[] = [];
    let radarTop: EnergyResult[] = [];
    if (hasRadar) {
      const b = comparison.baseline!;
      const baseEui = b.eui_kwh_m2;
      const baseCool = b.cooling_energy_kwh || 1;
      const baseHeat = b.heating_energy_kwh || 1;
      const baseFan = b.fan_energy_kwh || 1;
      const basePeak = b.peak_demand_kw || 1;

      radarData = [
        { metric: "EUI", ...Object.fromEntries(allStrategies.map((s) => [s.strategy, Math.round((s.eui_kwh_m2 / baseEui) * 100)])) },
        { metric: "Cooling", ...Object.fromEntries(allStrategies.map((s) => [s.strategy, Math.round(((s.cooling_energy_kwh ?? baseCool) / baseCool) * 100)])) },
        { metric: "Heating", ...Object.fromEntries(allStrategies.map((s) => [s.strategy, Math.round(((s.heating_energy_kwh ?? baseHeat) / baseHeat) * 100)])) },
        { metric: "Fan", ...Object.fromEntries(allStrategies.map((s) => [s.strategy, Math.round(((s.fan_energy_kwh ?? baseFan) / baseFan) * 100)])) },
        { metric: "Peak", ...Object.fromEntries(allStrategies.map((s) => [s.strategy, Math.round(((s.peak_demand_kw ?? basePeak) / basePeak) * 100)])) },
      ];

      radarTop = comparison.recommended_strategy
        ? [
            allStrategies.find((s) => s.strategy === "baseline")!,
            allStrategies.find((s) => s.strategy === comparison.recommended_strategy)!,
          ].filter(Boolean)
        : allStrategies.slice(0, 3);
    }

    /* ── Monthly profile data ── */
    const recommended = comparison.recommended_strategy
      ? allStrategies.find((s) => s.strategy === comparison.recommended_strategy)
      : null;
    const profileSource = recommended ?? comparison.baseline ?? allStrategies[0];
    const monthlyData = profileSource?.monthly_profile;

    return (
      <div
        ref={ref}
        style={{
          position: "absolute",
          left: -9999,
          top: 0,
          width: W,
          background: "white",
          fontFamily: "Arial, Helvetica, sans-serif",
        }}
      >
        {/* EUI Comparison */}
        <div data-chart="eui" style={{ width: W, height: H, background: "white" }}>
          <BarChart width={W} height={H} data={euiData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="strategy" tick={{ fontSize: 11 }} />
            <YAxis unit=" kWh/m²" tick={{ fontSize: 11 }} />
            <Legend />
            <Bar dataKey="EUI (kWh/m²)" radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {euiData.map((entry, i) => (
                <Cell key={i} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </div>

        {/* Energy Breakdown */}
        {breakdownData.length > 0 && (
          <div data-chart="breakdown" style={{ width: W, height: H, background: "white" }}>
            <BarChart width={W} height={H} data={breakdownData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="strategy" tick={{ fontSize: 11 }} />
              <YAxis unit=" MWh" tick={{ fontSize: 11 }} />
              <Legend />
              <Bar dataKey="Cooling" stackId="a" fill="#60A5FA" isAnimationActive={false} />
              <Bar dataKey="Heating" stackId="a" fill="#F87171" isAnimationActive={false} />
              <Bar dataKey="Fan" stackId="a" fill="#A78BFA" isAnimationActive={false} />
              <Bar dataKey="Pump" stackId="a" fill="#34D399" isAnimationActive={false} />
              <Bar dataKey="Lighting" stackId="a" fill="#FBBF24" isAnimationActive={false} />
              <Bar dataKey="Equipment" stackId="a" fill="#FB923C" isAnimationActive={false} />
            </BarChart>
          </div>
        )}

        {/* Cost Comparison */}
        {costData.length > 1 && (
          <div data-chart="cost" style={{ width: W, height: H, background: "white" }}>
            <BarChart width={W} height={H} data={costData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="strategy" tick={{ fontSize: 11 }} />
              <YAxis unit=" 만원" tick={{ fontSize: 11 }} />
              <Legend />
              <Bar dataKey="Cost (만원)" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                {costData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </div>
        )}

        {/* Radar */}
        {hasRadar && (
          <div data-chart="radar" style={{ width: W, height: 320, background: "white" }}>
            <RadarChart width={W} height={320} data={radarData} cx="50%" cy="50%" outerRadius="70%">
              <PolarGrid />
              <PolarAngleAxis dataKey="metric" tick={{ fontSize: 12 }} />
              <PolarRadiusAxis angle={90} domain={[0, 110]} tick={{ fontSize: 10 }} />
              {radarTop.map((s, i) => (
                <Radar
                  key={s.strategy}
                  name={STRATEGY_LABELS[s.strategy] ?? s.strategy}
                  dataKey={s.strategy}
                  stroke={RADAR_COLORS[i % RADAR_COLORS.length]}
                  fill={RADAR_COLORS[i % RADAR_COLORS.length]}
                  fillOpacity={0.15}
                  isAnimationActive={false}
                />
              ))}
              <Legend />
            </RadarChart>
          </div>
        )}

        {/* Monthly Profile */}
        {monthlyData && monthlyData.length > 0 && (
          <div data-chart="monthly" style={{ width: W, height: 320, background: "white" }}>
            <LineChart width={W} height={320} data={monthlyData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis unit=" kWh" tick={{ fontSize: 11 }} />
              <Legend />
              <Line type="monotone" dataKey="total" stroke="#374151" strokeWidth={2} name="Total" isAnimationActive={false} />
              <Line type="monotone" dataKey="cooling" stroke="#60A5FA" name="Cooling" isAnimationActive={false} />
              <Line type="monotone" dataKey="heating" stroke="#F87171" name="Heating" isAnimationActive={false} />
              <Line type="monotone" dataKey="lighting" stroke="#FBBF24" name="Lighting" isAnimationActive={false} />
              <Line type="monotone" dataKey="equipment" stroke="#FB923C" name="Equipment" isAnimationActive={false} />
              <Line type="monotone" dataKey="fan" stroke="#A78BFA" name="Fan" dot={false} isAnimationActive={false} />
            </LineChart>
          </div>
        )}
      </div>
    );
  },
);

PdfChartRenderer.displayName = "PdfChartRenderer";
export default PdfChartRenderer;
