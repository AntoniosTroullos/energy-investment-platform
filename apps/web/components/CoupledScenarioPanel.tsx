"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  CoupledScenarioPreconditionError,
  getCoupledScenarioResult,
  pollCoupledScenarioUntilTerminal,
  runCoupledScenario,
} from "../lib/pypsaScenario/pypsaScenario.api";
import type {
  CoupledEligibleYear,
  CoupledScenarioResult,
  RunState,
} from "../lib/pypsaScenario/pypsaScenario.types";

type SolveState = "idle" | "starting" | "running" | "success" | "crashed" | "precondition-failed" | "error";

// Both constraints trace to pypsa-greece/data/static/h2_market_scenarios.csv,
// which today has exactly one named scenario, defined only for these 3
// years. Extend both lists the day that CSV gains more rows.
const YEAR_OPTIONS: CoupledEligibleYear[] = [2030, 2040, 2050];
const H2_MARKET_SCENARIO_OPTIONS = [
  { value: "baseline_no_trade", label: "Baseline (no H2 import/export, no storage)" },
];

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

export default function CoupledScenarioPanel() {
  const [targetYear, setTargetYear] = useState<CoupledEligibleYear>(2030);
  const [h2MarketScenario, setH2MarketScenario] = useState(H2_MARKET_SCENARIO_OPTIONS[0].value);
  const [solveState, setSolveState] = useState<SolveState>("idle");
  const [caseName, setCaseName] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<CoupledScenarioResult | null>(null);

  const isBusy = solveState === "starting" || solveState === "running";

  async function handleSolve() {
    setSolveState("starting");
    setErrorMessage(null);
    setStatusMessage("Starting the coupled solve...");

    try {
      const started = await runCoupledScenario({ targetYear, h2MarketScenario });
      setCaseName(started.case_name);
      setSolveState("running");
      setStatusMessage(`Solving the coupled system for ${targetYear}...`);

      const terminalStatus = await pollCoupledScenarioUntilTerminal(
        started.case_name,
        (status: { state: RunState }) => {
          if (status.state === "running") {
            setStatusMessage(`Solving the coupled system for ${targetYear}...`);
          }
        },
      );

      if (terminalStatus.state === "crashed") {
        setSolveState("crashed");
        setErrorMessage(
          terminalStatus.message ?? "The coupled solver process stopped without producing a result.",
        );
        return;
      }

      const result = await getCoupledScenarioResult(started.case_name);
      setLastResult(result);
      setSolveState("success");
      setStatusMessage(
        result.solved
          ? `Solved. Objective cost: €${(result.objective_eur_per_year ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}/year.`
          : `Solve completed but did not find an optimal solution: ${result.message}`,
      );
    } catch (error) {
      if (error instanceof CoupledScenarioPreconditionError) {
        setSolveState("precondition-failed");
        setErrorMessage(error.message);
        return;
      }
      setSolveState("error");
      setErrorMessage(error instanceof Error ? error.message : "Unable to solve the coupled system.");
    }
  }

  const heatTechRows = lastResult ? parseHeatTechnologyCapacity(lastResult.link_capacity_mw) : [];
  const balanceRows = lastResult ? h2BalanceRows(lastResult) : [];

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[360px_1fr]">
      <div className="space-y-4">
        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <label htmlFor="coupled-target-year" className="text-sm font-medium text-zinc-100">
            Target Year
          </label>
          <select
            id="coupled-target-year"
            value={targetYear}
            disabled={isBusy}
            onChange={(event) => setTargetYear(Number(event.target.value) as CoupledEligibleYear)}
            className="mt-3 w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-3 text-sm text-zinc-100 outline-none focus:border-emerald-400 disabled:opacity-50"
          >
            {YEAR_OPTIONS.map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <label htmlFor="coupled-h2-market-scenario" className="text-sm font-medium text-zinc-100">
            H2 Market Scenario
          </label>
          <select
            id="coupled-h2-market-scenario"
            value={h2MarketScenario}
            disabled={isBusy}
            onChange={(event) => setH2MarketScenario(event.target.value)}
            className="mt-3 w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-3 text-sm text-zinc-100 outline-none focus:border-emerald-400 disabled:opacity-50"
          >
            {H2_MARKET_SCENARIO_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          onClick={handleSolve}
          disabled={isBusy}
          className="w-full rounded-lg bg-cyan-500 px-4 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:bg-cyan-500/40"
        >
          {isBusy ? "Solving..." : "Solve Coupled System"}
        </button>

        {statusMessage &&
          solveState !== "error" &&
          solveState !== "crashed" &&
          solveState !== "precondition-failed" && (
            <p className="text-xs text-zinc-400">{statusMessage}</p>
          )}

        {solveState === "precondition-failed" && (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
            <p className="font-semibold">Electricity case not solved yet</p>
            <p className="mt-1 text-xs">
              {errorMessage ?? `Electricity scenario for ${targetYear} hasn't been solved yet -- solve it in the Electricity tab first, then try again.`}
            </p>
          </div>
        )}

        {solveState === "crashed" && (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
            <p className="font-semibold">Solve did not complete</p>
            <p className="mt-1 text-xs">{errorMessage}</p>
          </div>
        )}

        {solveState === "error" && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
            <p className="font-semibold">Something went wrong</p>
            <p className="mt-1 text-xs">{errorMessage}</p>
          </div>
        )}

        {caseName && (
          <p className="text-xs text-zinc-600">
            Case: <span className="font-mono text-zinc-400">{caseName}</span>
          </p>
        )}
      </div>

      <div>
        {lastResult && solveState === "success" ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-white/10 bg-zinc-950/90 p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Objective Cost</p>
                <p className="mt-1 text-sm text-zinc-100">
                  €{(lastResult.objective_eur_per_year ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}/yr
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-zinc-950/90 p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Annual Heat Demand</p>
                <p className="mt-1 text-sm text-zinc-100">
                  {lastResult.annual_heat_twh?.toFixed(1) ?? "—"} TWh
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-zinc-950/90 p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Annual H2 Target</p>
                <p className="mt-1 text-sm text-zinc-100">
                  {lastResult.annual_h2_final_energy_target_twh?.toFixed(2) ?? "—"} TWh
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-zinc-950/90 p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">H2DRIA</p>
                <p className="mt-1 text-sm text-zinc-100">
                  {lastResult.h2dria_available ? "Available" : "Not yet available"}
                  {lastResult.h2dria_commissioning_year ? ` (from ${lastResult.h2dria_commissioning_year})` : ""}
                </p>
              </div>
            </div>

            {balanceRows.length > 0 && (
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <div className="flex items-baseline justify-between">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
                    Hydrogen Balance
                  </p>
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
                {JSON.stringify(lastResult, null, 2)}
              </pre>
            </details>
          </div>
        ) : (
          <div className="flex h-full min-h-[240px] items-center justify-center rounded-xl border border-dashed border-white/10 p-8 text-center">
            <p className="text-sm text-zinc-500">
              Choose a year and hit Solve to see results here.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
