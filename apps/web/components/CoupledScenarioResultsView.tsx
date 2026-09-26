"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { CoupledScenarioResult } from "../lib/pypsaScenario/pypsaScenario.types";

type CoupledScenarioResultsViewProps = {
  result: CoupledScenarioResult;
};

const AXIS_COLOR = "#71717a";
const GRID_COLOR = "rgba(255,255,255,0.08)";

// Only these three link suffixes get charted -- everything else in
// link_capacity_mw (gas-to-power links, per-project electrolyzer links) is
// left to the raw-JSON block below rather than guessed at.
const HEAT_TECH_SUFFIXES = ["_heat_pump", "_gas_boiler", "_hydrogen_boiler"] as const;
const HEAT_TECH_LABELS: Record<(typeof HEAT_TECH_SUFFIXES)[number], string> = {
  _heat_pump: "Heat pump",
  _gas_boiler: "Gas boiler",
  _hydrogen_boiler: "Hydrogen boiler",
};

function parseHeatTechnologyCapacity(linkCapacityMw: Record<string, number>) {
  const rows: { region: string; technology: string; value: number }[] = [];
  for (const [key, value] of Object.entries(linkCapacityMw)) {
    const suffix = HEAT_TECH_SUFFIXES.find((candidate) => key.endsWith(candidate));
    if (!suffix) {
      continue;
    }
    const region = key.slice(0, -suffix.length).replace(/_/g, " ");
    rows.push({ region, technology: HEAT_TECH_LABELS[suffix], value });
  }
  return rows;
}

function h2BalanceRows(result: CoupledScenarioResult) {
  const balance = result.h2_balance_mwh;
  if (!balance) {
    return [];
  }
  return [
    { name: "Domestic non-heat load", value: balance.domestic_non_heat_load / 1000 },
    { name: "Electrolysis output", value: balance.electrolysis_output / 1000 },
    { name: "Imports", value: balance.imports / 1000 },
    { name: "Exports", value: balance.exports / 1000 },
    { name: "Hydrogen boiler input", value: balance.hydrogen_boiler_input / 1000 },
  ];
}

// The coupled solve's result rendering -- extracted out of the old
// CoupledScenarioPanel so both the scenario wizard and any future caller can
// reuse it without duplicating ~150 lines of chart/card markup.
export default function CoupledScenarioResultsView({ result }: CoupledScenarioResultsViewProps) {
  const heatTechRows = parseHeatTechnologyCapacity(result.link_capacity_mw);
  const balanceRows = h2BalanceRows(result);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-white/10 bg-zinc-950/90 p-3">
          <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Objective Cost</p>
          <p className="mt-1 text-sm text-zinc-100">
            €{(result.objective_eur_per_year ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}/yr
          </p>
        </div>
        <div className="rounded-xl border border-white/10 bg-zinc-950/90 p-3">
          <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Annual Heat Demand</p>
          <p className="mt-1 text-sm text-zinc-100">{result.annual_heat_twh?.toFixed(1) ?? "—"} TWh</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-zinc-950/90 p-3">
          <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Annual H2 Target</p>
          <p className="mt-1 text-sm text-zinc-100">
            {result.annual_h2_final_energy_target_twh?.toFixed(2) ?? "—"} TWh
          </p>
        </div>
        <div className="rounded-xl border border-white/10 bg-zinc-950/90 p-3">
          <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">H2DRIA</p>
          <p className="mt-1 text-sm text-zinc-100">
            {result.h2dria_available ? "Available" : "Not yet available"}
            {result.h2dria_commissioning_year ? ` (from ${result.h2dria_commissioning_year})` : ""}
          </p>
        </div>
      </div>

      {balanceRows.length > 0 && (
        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <div className="flex items-baseline justify-between">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Hydrogen Balance</p>
            <p className="text-[10px] text-zinc-600">GWh / year</p>
          </div>
          <div className="mt-3 h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={balanceRows} margin={{ left: 0, right: 8, top: 4, bottom: 24 }}>
                <CartesianGrid vertical={false} stroke={GRID_COLOR} />
                <XAxis
                  dataKey="name"
                  tick={{ fill: AXIS_COLOR, fontSize: 9 }}
                  stroke={GRID_COLOR}
                  angle={-20}
                  textAnchor="end"
                  interval={0}
                />
                <YAxis tick={{ fill: AXIS_COLOR, fontSize: 10 }} stroke={GRID_COLOR} />
                <Tooltip
                  contentStyle={{ background: "#09090b", border: "1px solid rgba(255,255,255,0.1)", fontSize: 11 }}
                  formatter={(value) => [`${Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })} GWh`, ""]}
                />
                <Bar dataKey="value" radius={[3, 3, 0, 0]} fill="#22d3ee" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {heatTechRows.length > 0 && (
        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <div className="flex items-baseline justify-between">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
              Heat Technology Capacity
            </p>
            <p className="text-[10px] text-zinc-600">MW, by region</p>
          </div>
          <div className="mt-3 max-h-64 space-y-1 overflow-y-auto text-xs text-zinc-300">
            {heatTechRows
              .sort((a, b) => b.value - a.value)
              .map((row) => (
                <div key={`${row.region}-${row.technology}`} className="flex items-center justify-between gap-2">
                  <span className="truncate">
                    {row.region} · {row.technology}
                  </span>
                  <span className="font-mono text-zinc-500">{row.value.toFixed(1)} MW</span>
                </div>
              ))}
          </div>
        </div>
      )}

      <details className="rounded-xl border border-white/10 bg-white/5 p-4 text-xs text-zinc-400">
        <summary className="cursor-pointer text-zinc-300">Full result JSON</summary>
        <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words text-[10px] text-zinc-500">
          {JSON.stringify(result, null, 2)}
        </pre>
      </details>
    </div>
  );
}
