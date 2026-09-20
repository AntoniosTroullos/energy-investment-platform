"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ElectricityScenarioResult } from "../lib/pypsaScenario/pypsaScenario.types";

type ScenarioResultsChartsProps = {
  result: ElectricityScenarioResult;
};

const CARRIER_COLORS: Record<string, string> = {
  solar: "#facc15",
  wind: "#38bdf8",
  hydro: "#22d3ee",
  gas: "#f97316",
  lignite: "#78716c",
};

const AXIS_COLOR = "#71717a"; // zinc-500, matches the panel's existing label color
const GRID_COLOR = "rgba(255,255,255,0.08)";

function toChartRows(record: Record<string, number> | undefined, valueDivisor = 1) {
  return Object.entries(record ?? {})
    .map(([name, value]) => ({ name: formatLabel(name), rawName: name, value: value / valueDivisor }))
    .sort((a, b) => b.value - a.value);
}

function formatLabel(name: string): string {
  return name.replace(/_/g, " ");
}

function ChartCard({ title, unit, children }: { title: string; unit: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <div className="flex items-baseline justify-between">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">{title}</p>
        <p className="text-[10px] text-zinc-600">{unit}</p>
      </div>
      <div className="mt-3 h-48">{children}</div>
    </div>
  );
}

export default function ScenarioResultsCharts({ result }: ScenarioResultsChartsProps) {
  const generationRows = toChartRows(result.metrics.generation_by_carrier_mwh, 1000); // -> GWh
  const priceRows = toChartRows(result.metrics.average_marginal_price_by_bus);
  const peakLoadRows = toChartRows(result.metrics.peak_load_by_bus_mw);
  const curtailmentRows = toChartRows(result.metrics.curtailment_by_carrier_mwh, 1000); // -> GWh

  if (!result.solved) {
    return (
      <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-200">
        This scenario did not reach an optimal solution ({result.message}) -- no results to chart.
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-4">
      <ChartCard title="Generation by Carrier" unit="GWh / year">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={generationRows} layout="vertical" margin={{ left: 8, right: 12, top: 4, bottom: 4 }}>
            <CartesianGrid horizontal={false} stroke={GRID_COLOR} />
            <XAxis type="number" tick={{ fill: AXIS_COLOR, fontSize: 10 }} stroke={GRID_COLOR} />
            <YAxis
              type="category"
              dataKey="name"
              width={64}
              tick={{ fill: AXIS_COLOR, fontSize: 10 }}
              stroke={GRID_COLOR}
            />
            <Tooltip
              contentStyle={{ background: "#09090b", border: "1px solid rgba(255,255,255,0.1)", fontSize: 11 }}
              formatter={(value) => [`${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })} GWh`, ""]}
            />
            <Bar dataKey="value" radius={[0, 3, 3, 0]}>
              {generationRows.map((row) => (
                <Cell key={row.rawName} fill={CARRIER_COLORS[row.rawName] ?? "#a1a1aa"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      {curtailmentRows.length > 0 && (
        <ChartCard title="Curtailment by Carrier" unit="GWh / year">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={curtailmentRows} layout="vertical" margin={{ left: 8, right: 12, top: 4, bottom: 4 }}>
              <CartesianGrid horizontal={false} stroke={GRID_COLOR} />
              <XAxis type="number" tick={{ fill: AXIS_COLOR, fontSize: 10 }} stroke={GRID_COLOR} />
              <YAxis
                type="category"
                dataKey="name"
                width={64}
                tick={{ fill: AXIS_COLOR, fontSize: 10 }}
                stroke={GRID_COLOR}
              />
              <Tooltip
                contentStyle={{ background: "#09090b", border: "1px solid rgba(255,255,255,0.1)", fontSize: 11 }}
                formatter={(value) => [`${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })} GWh`, ""]}
              />
              <Bar dataKey="value" radius={[0, 3, 3, 0]} fill="#ef4444" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      )}

      <ChartCard title="Peak Load by Region" unit="MW">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={peakLoadRows} margin={{ left: 0, right: 8, top: 4, bottom: 24 }}>
            <CartesianGrid vertical={false} stroke={GRID_COLOR} />
            <XAxis
              dataKey="name"
              tick={{ fill: AXIS_COLOR, fontSize: 9 }}
              stroke={GRID_COLOR}
              angle={-35}
              textAnchor="end"
              interval={0}
            />
            <YAxis tick={{ fill: AXIS_COLOR, fontSize: 10 }} stroke={GRID_COLOR} />
            <Tooltip
              contentStyle={{ background: "#09090b", border: "1px solid rgba(255,255,255,0.1)", fontSize: 11 }}
              formatter={(value) => [`${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })} MW`, ""]}
            />
            <Bar dataKey="value" radius={[3, 3, 0, 0]} fill="#34d399" />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Average Marginal Price by Region" unit="€/MWh">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={priceRows} margin={{ left: 0, right: 8, top: 4, bottom: 24 }}>
            <CartesianGrid vertical={false} stroke={GRID_COLOR} />
            <XAxis
              dataKey="name"
              tick={{ fill: AXIS_COLOR, fontSize: 9 }}
              stroke={GRID_COLOR}
              angle={-35}
              textAnchor="end"
              interval={0}
            />
            <YAxis tick={{ fill: AXIS_COLOR, fontSize: 10 }} stroke={GRID_COLOR} />
            <Tooltip
              contentStyle={{ background: "#09090b", border: "1px solid rgba(255,255,255,0.1)", fontSize: 11 }}
              formatter={(value) => [`€${Number(value).toFixed(2)}/MWh`, ""]}
            />
            <Bar dataKey="value" radius={[3, 3, 0, 0]} fill="#a78bfa" />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}
