"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { getScenarioList } from "../lib/pypsaScenario/pypsaScenario.api";
import type { ScenarioListItem } from "../lib/pypsaScenario/pypsaScenario.types";

type ScenarioComparisonPanelProps = {
  // Re-fetches the scenario library whenever this value changes -- pass the
  // latest solved result so a fresh solve makes the comparison view refresh
  // itself without a manual click.
  refreshSignal?: unknown;
};

const CARRIER_COLORS: Record<string, string> = {
  solar: "#facc15",
  wind: "#38bdf8",
  hydro: "#22d3ee",
  gas: "#f97316",
  lignite: "#78716c",
};

const AXIS_COLOR = "#71717a"; // zinc-500, matches the rest of this panel's charts
const GRID_COLOR = "rgba(255,255,255,0.08)";

export default function ScenarioComparisonPanel({ refreshSignal }: ScenarioComparisonPanelProps) {
  const [scenarios, setScenarios] = useState<ScenarioListItem[]>([]);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  // No setState call happens before the first `await` here -- every update
  // below runs inside the resolved/rejected promise callback, not
  // synchronously when the effect fires, which is what the React Compiler
  // lint (react-hooks/set-state-in-effect) requires.
  async function loadScenarios() {
    try {
      const response = await getScenarioList();
      setScenarios(response.scenarios);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load the scenario library.");
    } finally {
      setHasLoadedOnce(true);
    }
  }

  useEffect(() => {
    // refreshSignal is intentionally in the dependency list purely to
    // trigger a re-fetch after a new solve -- its identity, not its shape,
    // is what matters here.
    void loadScenarios();
  }, [refreshSignal]);

  const solvedScenarios = scenarios.filter(
    (scenario) => scenario.state === "done" && scenario.solved,
  );
  const carriers = Array.from(
    new Set(solvedScenarios.flatMap((scenario) => Object.keys(scenario.generation_by_carrier_mwh))),
  );

  const hasCoupled = solvedScenarios.some((scenario) => scenario.coupled_objective_eur_per_year !== null);

  const costRows = solvedScenarios.map((scenario) => ({
    year: String(scenario.target_year),
    objectiveBillionEur: (scenario.objective_eur ?? 0) / 1_000_000_000,
    // null (not 0) when no coupled solve exists, so recharts draws no bar
    // rather than a misleading zero-height one.
    coupledObjectiveBillionEur:
      scenario.coupled_objective_eur_per_year !== null
        ? scenario.coupled_objective_eur_per_year / 1_000_000_000
        : null,
  }));

  const generationRows = solvedScenarios.map((scenario) => {
    const row: Record<string, number | string> = { year: String(scenario.target_year) };
    for (const carrier of carriers) {
      row[carrier] = (scenario.generation_by_carrier_mwh[carrier] ?? 0) / 1000; // MWh -> GWh
    }
    return row;
  });

  return (
    <section className="mt-8">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
          Scenario Comparison
        </h2>
        <button
          type="button"
          onClick={() => void loadScenarios()}
          className="text-xs text-emerald-300 hover:text-emerald-200"
        >
          Refresh
        </button>
      </div>
      <p className="mt-2 text-xs text-zinc-500">
        Every solved electricity scenario, compared side by side, with the coupled gas / hydrogen / heat solve alongside it where one has been run.
      </p>

      {errorMessage && (
        <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          {errorMessage}
        </div>
      )}

      {hasLoadedOnce && !errorMessage && solvedScenarios.length === 0 && (
        <p className="mt-4 text-xs text-zinc-500">
          No solved scenarios yet — solve one in the Electricity tab to see it here.
        </p>
      )}

      {solvedScenarios.length > 0 && (
        <div className="mt-4 space-y-4">
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-baseline justify-between">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
                Objective Cost
              </p>
              <p className="text-[10px] text-zinc-600">Billion € / year</p>
            </div>
            <div className="mt-3 h-40">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={costRows} margin={{ left: 0, right: 8, top: 4, bottom: 4 }}>
                  <CartesianGrid vertical={false} stroke={GRID_COLOR} />
                  <XAxis dataKey="year" tick={{ fill: AXIS_COLOR, fontSize: 10 }} stroke={GRID_COLOR} />
                  <YAxis tick={{ fill: AXIS_COLOR, fontSize: 10 }} stroke={GRID_COLOR} />
                  <Tooltip
                    contentStyle={{ background: "#09090b", border: "1px solid rgba(255,255,255,0.1)", fontSize: 11 }}
                    formatter={(value) => [`€${Number(value).toFixed(2)}B`, ""]}
                  />
                  {hasCoupled && <Legend wrapperStyle={{ fontSize: 10 }} />}
                  <Bar
                    dataKey="objectiveBillionEur"
                    name="Electricity system"
                    radius={[3, 3, 0, 0]}
                    fill="#a78bfa"
                  />
                  {hasCoupled && (
                    <Bar
                      dataKey="coupledObjectiveBillionEur"
                      name="Coupled system (elec + gas + H2 + heat)"
                      radius={[3, 3, 0, 0]}
                      fill="#22d3ee"
                    />
                  )}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-baseline justify-between">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
                Generation Mix
              </p>
              <p className="text-[10px] text-zinc-600">GWh / year</p>
            </div>
            <div className="mt-3 h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={generationRows} margin={{ left: 0, right: 8, top: 4, bottom: 4 }}>
                  <CartesianGrid vertical={false} stroke={GRID_COLOR} />
                  <XAxis dataKey="year" tick={{ fill: AXIS_COLOR, fontSize: 10 }} stroke={GRID_COLOR} />
                  <YAxis tick={{ fill: AXIS_COLOR, fontSize: 10 }} stroke={GRID_COLOR} />
                  <Tooltip
                    contentStyle={{ background: "#09090b", border: "1px solid rgba(255,255,255,0.1)", fontSize: 11 }}
                    formatter={(value, name) => [
                      `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })} GWh`,
                      name,
                    ]}
                  />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  {carriers.map((carrier) => (
                    <Bar
                      key={carrier}
                      dataKey={carrier}
                      stackId="generation"
                      fill={CARRIER_COLORS[carrier] ?? "#a1a1aa"}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-white/10 bg-white/5">
            <table className="w-full text-left text-xs">
              <thead className="text-zinc-500">
                <tr>
                  <th className="px-3 py-2 font-medium">Year</th>
                  <th className="px-3 py-2 font-medium">Case</th>
                  <th className="px-3 py-2 font-medium">Objective (€/yr)</th>
                  {hasCoupled && (
                    <>
                      <th className="px-3 py-2 font-medium">Coupled objective (€/yr)</th>
                      <th className="px-3 py-2 font-medium">Heat demand (TWh)</th>
                      <th className="px-3 py-2 font-medium">Electrolysis (GWh)</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody className="text-zinc-200">
                {solvedScenarios.map((scenario) => (
                  <tr key={scenario.case_name} className="border-t border-white/10">
                    <td className="px-3 py-2">{scenario.target_year}</td>
                    <td className="px-3 py-2 font-mono text-zinc-400">{scenario.case_name}</td>
                    <td className="px-3 py-2">
                      {scenario.objective_eur?.toLocaleString(undefined, { maximumFractionDigits: 0 }) ?? "—"}
                    </td>
                    {hasCoupled && (
                      <>
                        <td className="px-3 py-2">
                          {scenario.coupled_objective_eur_per_year?.toLocaleString(undefined, {
                            maximumFractionDigits: 0,
                          }) ?? "—"}
                        </td>
                        <td className="px-3 py-2">
                          {scenario.coupled_annual_heat_twh?.toFixed(1) ?? "—"}
                        </td>
                        <td className="px-3 py-2">
                          {scenario.coupled_h2_electrolysis_output_mwh !== null
                            ? (scenario.coupled_h2_electrolysis_output_mwh / 1000).toLocaleString(undefined, {
                                maximumFractionDigits: 0,
                              })
                            : "—"}
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
