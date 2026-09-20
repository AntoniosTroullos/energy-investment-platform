"use client";

import { useState } from "react";

import {
  getScenarioResult,
  pollScenarioUntilTerminal,
  runElectricityScenario,
} from "../lib/pypsaScenario/pypsaScenario.api";
import type {
  ElectricityScenarioResult,
  RunState,
} from "../lib/pypsaScenario/pypsaScenario.types";
import ScenarioResultsCharts from "./ScenarioResultsCharts";

type SolveState = "idle" | "starting" | "running" | "success" | "crashed" | "error";

const YEAR_OPTIONS = [2030, 2035, 2040, 2045, 2050];

export default function ScenarioBuilderPanel() {
  const [targetYear, setTargetYear] = useState(2030);
  const [annualGrowthRate, setAnnualGrowthRate] = useState(0.01);
  const [solveState, setSolveState] = useState<SolveState>("idle");
  const [caseName, setCaseName] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<ElectricityScenarioResult | null>(null);

  const isBusy = solveState === "starting" || solveState === "running";

  async function handleSolve() {
    setSolveState("starting");
    setErrorMessage(null);
    setStatusMessage("Starting the solve...");

    try {
      const started = await runElectricityScenario({ targetYear, annualGrowthRate });
      setCaseName(started.case_name);
      setSolveState("running");
      setStatusMessage(`Solving '${started.case_name}'...`);

      const terminalStatus = await pollScenarioUntilTerminal(started.case_name, (status: { state: RunState }) => {
        if (status.state === "running") {
          setStatusMessage(`Solving '${started.case_name}'...`);
        }
      });

      if (terminalStatus.state === "crashed") {
        setSolveState("crashed");
        setErrorMessage(
          terminalStatus.message ?? "The solver process stopped without producing a result.",
        );
        return;
      }

      const result = await getScenarioResult(started.case_name);
      setLastResult(result);
      setSolveState("success");
      setStatusMessage(
        result.solved
          ? `Solved. Objective cost: €${(result.objective_eur ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}/year.`
          : `Solve completed but did not find an optimal solution: ${result.message}`,
      );
    } catch (error) {
      setSolveState("error");
      setErrorMessage(error instanceof Error ? error.message : "Unable to solve this scenario.");
    }
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[360px_1fr]">
      <div className="space-y-4">
        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <label htmlFor="target-year" className="text-sm font-medium text-zinc-100">
            Target Year
          </label>
          <select
            id="target-year"
            value={targetYear}
            disabled={isBusy}
            onChange={(event) => setTargetYear(Number(event.target.value))}
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
          <div className="flex items-center justify-between">
            <label htmlFor="annual-growth-rate" className="text-sm font-medium text-zinc-100">
              Annual Demand Growth
            </label>
            <span className="text-sm text-emerald-300">
              {(annualGrowthRate * 100).toFixed(1)}%/yr
            </span>
          </div>
          <input
            id="annual-growth-rate"
            type="range"
            min="-0.02"
            max="0.05"
            step="0.005"
            value={annualGrowthRate}
            disabled={isBusy}
            onChange={(event) => setAnnualGrowthRate(Number(event.target.value))}
            className="mt-3 w-full accent-emerald-400 disabled:opacity-50"
          />
        </div>

        <button
          type="button"
          onClick={handleSolve}
          disabled={isBusy}
          className="w-full rounded-lg bg-emerald-500 px-4 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-emerald-500/40"
        >
          {isBusy ? "Solving..." : "Solve Scenario"}
        </button>

        {statusMessage && solveState !== "error" && solveState !== "crashed" && (
          <p className="text-xs text-zinc-400">{statusMessage}</p>
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
          <div>
            <div className="rounded-xl border border-white/10 bg-zinc-950/90 p-4 text-sm text-zinc-100">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
                Latest Result — {lastResult.target_year}
              </p>
              <p className="mt-2 text-xs text-zinc-400">
                Objective cost: €
                {(lastResult.objective_eur ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                /year
              </p>
            </div>
            <ScenarioResultsCharts result={lastResult} />
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
