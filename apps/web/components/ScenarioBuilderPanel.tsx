"use client";

import { useEffect, useState } from "react";

import {
  getScenarioOptions,
  getScenarioResult,
  pollScenarioUntilTerminal,
  runElectricityScenario,
} from "../lib/pypsaScenario/pypsaScenario.api";
import type {
  ElectricityScenarioResult,
  RunState,
  ScenarioOptions,
} from "../lib/pypsaScenario/pypsaScenario.types";
import ScenarioResultsCharts from "./ScenarioResultsCharts";

type SolveState = "idle" | "starting" | "running" | "success" | "crashed" | "error";
type OptionsState = "loading" | "ready" | "error";

// Used only until GET /scenarios/options answers (or if it fails) -- picking a
// year to render immediately beats a blank/disabled control on first paint.
// The real bounds (and which years are solved) always come from the backend.
const FALLBACK_YEAR = 2030;
const FALLBACK_GROWTH_RATE = 0.01;

export default function ScenarioBuilderPanel() {
  const [options, setOptions] = useState<ScenarioOptions | null>(null);
  const [optionsState, setOptionsState] = useState<OptionsState>("loading");
  const [targetYear, setTargetYear] = useState(FALLBACK_YEAR);
  const [annualGrowthRate, setAnnualGrowthRate] = useState(FALLBACK_GROWTH_RATE);
  const [solveState, setSolveState] = useState<SolveState>("idle");
  const [caseName, setCaseName] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<ElectricityScenarioResult | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadOptions() {
      try {
        const loaded = await getScenarioOptions();
        if (cancelled) {
          return;
        }
        setOptions(loaded);
        setOptionsState("ready");
        // Default to the first not-yet-solved year (screening a new year is
        // the common case); fall back to the earliest offered year once
        // everything currently listed is solved.
        const nextUnsolved = loaded.electricity_years.find((year) => !year.solved);
        setTargetYear(nextUnsolved?.year ?? loaded.electricity_years[0]?.year ?? FALLBACK_YEAR);
        setAnnualGrowthRate(loaded.annual_growth_rate_default);
      } catch {
        if (!cancelled) {
          setOptionsState("error");
        }
      }
    }

    void loadOptions();
    return () => {
      cancelled = true;
    };
  }, []);

  const isBusy = solveState === "starting" || solveState === "running";
  const selectedYearOption = options?.electricity_years.find((year) => year.year === targetYear);
  const growthPercentStep = 0.5; // percentage points; matches the slider's 0.005 step in fraction form

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
      // This year is now solved (or re-solved) -- refresh the picker's solved
      // flags so a subsequent look at the dropdown reflects it.
      setOptions((current) =>
        current
          ? {
              ...current,
              electricity_years: current.electricity_years.map((year) =>
                year.year === targetYear ? { ...year, solved: true } : year,
              ),
            }
          : current,
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
            disabled={isBusy || optionsState === "loading"}
            onChange={(event) => setTargetYear(Number(event.target.value))}
            className="mt-3 w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-3 text-sm text-zinc-100 outline-none focus:border-emerald-400 disabled:opacity-50"
          >
            {optionsState === "loading" && <option>Loading years...</option>}
            {optionsState === "error" && <option value={FALLBACK_YEAR}>{FALLBACK_YEAR}</option>}
            {options?.electricity_years.map((year) => (
              <option key={year.year} value={year.year}>
                {year.year}
                {year.solved ? " (solved)" : ""}
              </option>
            ))}
          </select>
          {optionsState === "error" && (
            <p className="mt-2 text-xs text-amber-300">
              Could not load the year list from the backend -- showing a fallback default ({FALLBACK_YEAR}).
            </p>
          )}
          {selectedYearOption?.solved && (
            <p className="mt-2 text-xs text-zinc-500">
              Already solved -- solving again replaces that result.
            </p>
          )}
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
            min={options?.annual_growth_rate_min ?? -0.05}
            max={options?.annual_growth_rate_max ?? 0.10}
            step={growthPercentStep / 100}
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
                {lastResult.parameters?.annual_growth_rate != null &&
                  ` · ${(lastResult.parameters.annual_growth_rate * 100).toFixed(1)}%/yr demand growth`}
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
