"use client";

import { useEffect, useState } from "react";

import {
  CoupledScenarioPreconditionError,
  getCoupledScenarioResult,
  getScenarioOptions,
  getScenarioResult,
  pollCoupledScenarioUntilTerminal,
  pollScenarioUntilTerminal,
  runCoupledScenario,
  runElectricityScenario,
} from "../lib/pypsaScenario/pypsaScenario.api";
import type {
  CoupledScenarioResult,
  ElectricityScenarioResult,
  RunState,
  ScenarioOptions,
} from "../lib/pypsaScenario/pypsaScenario.types";
import { SCENARIO_PRESETS, type ScenarioPreset, type ScenarioType } from "../lib/pypsaScenario/presets";
import CoupledScenarioResultsView from "./CoupledScenarioResultsView";
import ScenarioResultsCharts from "./ScenarioResultsCharts";

type WizardStep = "type" | "parameters" | "advanced" | "review";
type SolveState = "idle" | "running" | "success" | "crashed" | "precondition-failed" | "error";
type OptionsState = "loading" | "ready" | "error";
type StorageMethod = "representative-days" | "chronological" | "linked";

// Used only until GET /scenarios/options answers (or if it fails) -- the real
// bounds (and which years/H2 scenarios are actually solvable) always come
// from the backend.
const FALLBACK_YEAR = 2030;
const FALLBACK_GROWTH_RATE = 0.01;

const WIZARD_STEPS: { id: WizardStep; label: string }[] = [
  { id: "type", label: "Model" },
  { id: "parameters", label: "Parameters" },
  { id: "advanced", label: "Advanced" },
  { id: "review", label: "Review & Solve" },
];

function defaultYearForType(type: ScenarioType, options: ScenarioOptions | null, fallback: number): number {
  if (!options) {
    return fallback;
  }
  if (type === "electricity") {
    const nextUnsolved = options.electricity_years.find((year) => !year.solved);
    return nextUnsolved?.year ?? options.electricity_years[0]?.year ?? fallback;
  }
  const preferred = options.coupled_options.find((option) => option.electricity_solved);
  return preferred?.target_year ?? options.coupled_options[0]?.target_year ?? fallback;
}

function defaultH2ScenarioForYear(year: number, options: ScenarioOptions | null): string | null {
  const match = options?.coupled_options.find((option) => option.target_year === year);
  return match?.h2_market_scenario ?? null;
}

function coupledYearOptions(options: ScenarioOptions | null): { year: number; solved: boolean }[] {
  if (!options) {
    return [];
  }
  const solvedByYear = new Map<number, boolean>();
  for (const option of options.coupled_options) {
    if (!solvedByYear.has(option.target_year)) {
      solvedByYear.set(option.target_year, option.electricity_solved);
    }
  }
  return Array.from(solvedByYear.entries())
    .map(([year, solved]) => ({ year, solved }))
    .sort((a, b) => a.year - b.year);
}

function isElectricityAlreadySolved(
  scenarioType: ScenarioType,
  targetYear: number,
  options: ScenarioOptions | null,
): boolean {
  if (!options) {
    return false;
  }
  if (scenarioType === "electricity") {
    return options.electricity_years.find((year) => year.year === targetYear)?.solved ?? false;
  }
  return options.coupled_options.find((option) => option.target_year === targetYear)?.electricity_solved ?? false;
}

function formatH2Scenario(h2MarketScenario: string | null): string {
  if (!h2MarketScenario) {
    return "the selected";
  }
  return h2MarketScenario.replace(/_/g, " ");
}

function storageMethodDescription(storageMethod: StorageMethod): string {
  switch (storageMethod) {
    case "chronological":
      return "exact chronological seasonal-storage modeling";
    case "linked":
      return "linked representative-period storage modeling";
    default:
      return "the default representative-day modeling";
  }
}

export default function ScenarioWizardPanel() {
  const [options, setOptions] = useState<ScenarioOptions | null>(null);
  const [optionsState, setOptionsState] = useState<OptionsState>("loading");

  const [step, setStep] = useState<WizardStep>("type");
  const [scenarioType, setScenarioType] = useState<ScenarioType>("electricity");
  const [targetYear, setTargetYear] = useState(FALLBACK_YEAR);
  const [annualGrowthRate, setAnnualGrowthRate] = useState(FALLBACK_GROWTH_RATE);
  const [h2MarketScenario, setH2MarketScenario] = useState<string | null>(null);
  const [forceFetch, setForceFetch] = useState(false);
  const [storageMethod, setStorageMethod] = useState<StorageMethod>("representative-days");
  const [appliedPresetId, setAppliedPresetId] = useState<string | null>(null);

  const [solveState, setSolveState] = useState<SolveState>("idle");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [electricityCaseName, setElectricityCaseName] = useState<string | null>(null);
  const [coupledCaseName, setCoupledCaseName] = useState<string | null>(null);
  const [electricityResult, setElectricityResult] = useState<ElectricityScenarioResult | null>(null);
  const [coupledResult, setCoupledResult] = useState<CoupledScenarioResult | null>(null);

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
        // Initial scenarioType is always "electricity" (its useState default),
        // so the electricity-branch default is the correct one here.
        setTargetYear(defaultYearForType("electricity", loaded, FALLBACK_YEAR));
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

  const isBusy = solveState === "running";
  const chronologicalStorage = storageMethod === "chronological";
  const linkedRepresentativePeriods = storageMethod === "linked";
  const electricityAlreadySolved = isElectricityAlreadySolved(scenarioType, targetYear, options);
  const yearOptions =
    scenarioType === "electricity" ? options?.electricity_years ?? [] : coupledYearOptions(options);
  const h2ScenarioOptionsForYear =
    options?.coupled_options.filter((option) => option.target_year === targetYear) ?? [];

  function handleSelectScenarioType(type: ScenarioType) {
    setScenarioType(type);
    setAppliedPresetId(null);
    const nextYear = defaultYearForType(type, options, FALLBACK_YEAR);
    setTargetYear(nextYear);
    setH2MarketScenario(type === "coupled" ? defaultH2ScenarioForYear(nextYear, options) : null);
  }

  function handleSelectYear(year: number) {
    setTargetYear(year);
    if (scenarioType === "coupled") {
      setH2MarketScenario(defaultH2ScenarioForYear(year, options));
    }
  }

  function handleApplyPreset(preset: ScenarioPreset) {
    setAppliedPresetId(preset.id);
    setScenarioType(preset.scenarioType);
    setAnnualGrowthRate(preset.annualGrowthRate);
    setForceFetch(false);
    setStorageMethod(
      preset.chronologicalStorage ? "chronological" : preset.linkedRepresentativePeriods ? "linked" : "representative-days",
    );
    const nextYear = defaultYearForType(preset.scenarioType, options, targetYear);
    setTargetYear(nextYear);
    setH2MarketScenario(
      preset.scenarioType === "coupled" ? defaultH2ScenarioForYear(nextYear, options) : null,
    );
  }

  function summarySentence(): string {
    const growthText = `${(annualGrowthRate * 100).toFixed(1)}%/yr demand growth`;
    if (scenarioType === "electricity") {
      const fetchText = forceFetch ? "a fresh ENTSO-E demand pull" : "cached demand data";
      return `Solving the electricity system for ${targetYear}, assuming ${growthText}, using ${fetchText}.`;
    }
    const h2Text = formatH2Scenario(h2MarketScenario);
    const storageText = storageMethodDescription(storageMethod);
    const chainNote = electricityAlreadySolved
      ? ""
      : ` The ${targetYear} electricity case hasn't been solved yet -- that will run automatically first.`;
    return (
      `Solving electricity + coupled gas/hydrogen/heat system for ${targetYear} ` +
      `(${h2Text} H2 market scenario), assuming ${growthText}, with ${storageText}.${chainNote}`
    );
  }

  async function handleSolve() {
    setSolveState("running");
    setErrorMessage(null);
    setElectricityResult(null);
    setCoupledResult(null);
    setElectricityCaseName(null);
    setCoupledCaseName(null);

    try {
      const needsElectricitySolve = scenarioType === "electricity" || !electricityAlreadySolved;

      if (needsElectricitySolve) {
        setStatusMessage(`Solving the electricity system for ${targetYear}...`);
        const started = await runElectricityScenario({ targetYear, annualGrowthRate, forceFetch });
        setElectricityCaseName(started.case_name);

        const terminal = await pollScenarioUntilTerminal(started.case_name, (status: { state: RunState }) => {
          if (status.state === "running") {
            setStatusMessage(`Solving the electricity system for ${targetYear}...`);
          }
        });

        if (terminal.state === "crashed") {
          setSolveState("crashed");
          setErrorMessage(terminal.message ?? "The electricity solver stopped without producing a result.");
          return;
        }

        const eResult = await getScenarioResult(started.case_name);
        setElectricityResult(eResult);

        if (scenarioType === "electricity") {
          setSolveState("success");
          setStatusMessage(
            eResult.solved
              ? `Solved. Objective cost: €${(eResult.objective_eur ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}/year.`
              : `Solve completed but did not find an optimal solution: ${eResult.message}`,
          );
          return;
        }
      }

      // scenarioType === "coupled" from here (either already-solved electricity, or just solved above).
      if (!h2MarketScenario) {
        throw new Error("Choose an H2 market scenario before solving.");
      }

      setStatusMessage(`Solving the coupled system for ${targetYear}...`);
      const startedCoupled = await runCoupledScenario({
        targetYear,
        h2MarketScenario,
        chronologicalStorage,
        linkedRepresentativePeriods,
      });
      setCoupledCaseName(startedCoupled.case_name);
      const mode = { chronologicalStorage, linkedRepresentativePeriods };

      const terminalCoupled = await pollCoupledScenarioUntilTerminal(
        startedCoupled.case_name,
        (status: { state: RunState }) => {
          if (status.state === "running") {
            setStatusMessage(`Solving the coupled system for ${targetYear}...`);
          }
        },
        mode,
      );

      if (terminalCoupled.state === "crashed") {
        setSolveState("crashed");
        setErrorMessage(terminalCoupled.message ?? "The coupled solver stopped without producing a result.");
        return;
      }

      const cResult = await getCoupledScenarioResult(startedCoupled.case_name, mode);
      setCoupledResult(cResult);
      setSolveState("success");
      setStatusMessage(
        cResult.solved
          ? `Solved. Objective cost: €${(cResult.objective_eur_per_year ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}/year.`
          : `Solve completed but did not find an optimal solution: ${cResult.message}`,
      );
    } catch (error) {
      if (error instanceof CoupledScenarioPreconditionError) {
        setSolveState("precondition-failed");
        setErrorMessage(error.message);
        return;
      }
      setSolveState("error");
      setErrorMessage(error instanceof Error ? error.message : "Unable to solve this scenario.");
    }
  }

  const stepIndex = WIZARD_STEPS.findIndex((candidate) => candidate.id === step);

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[420px_1fr]">
      <div className="space-y-4">
        <div className="flex gap-1 rounded-xl border border-white/10 bg-white/5 p-1">
          {WIZARD_STEPS.map((wizardStep, index) => (
            <button
              key={wizardStep.id}
              type="button"
              disabled={isBusy}
              onClick={() => setStep(wizardStep.id)}
              className={`flex-1 rounded-lg px-2 py-2 text-[11px] font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${
                step === wizardStep.id
                  ? "bg-emerald-500/10 text-emerald-300"
                  : index < stepIndex
                    ? "text-zinc-400 hover:text-zinc-200"
                    : "text-zinc-600"
              }`}
            >
              {index + 1}. {wizardStep.label}
            </button>
          ))}
        </div>

        {step === "type" && (
          <div className="space-y-3">
            <button
              type="button"
              onClick={() => handleSelectScenarioType("electricity")}
              className={`w-full rounded-xl border p-4 text-left transition ${
                scenarioType === "electricity"
                  ? "border-emerald-500/40 bg-emerald-500/10"
                  : "border-white/10 bg-white/5 hover:bg-white/10"
              }`}
            >
              <p className="text-sm font-semibold text-zinc-100">Electricity only</p>
              <p className="mt-1 text-xs text-zinc-400">
                Solve Greece&rsquo;s electricity dispatch and prices for one future year.
              </p>
            </button>
            <button
              type="button"
              onClick={() => handleSelectScenarioType("coupled")}
              className={`w-full rounded-xl border p-4 text-left transition ${
                scenarioType === "coupled"
                  ? "border-emerald-500/40 bg-emerald-500/10"
                  : "border-white/10 bg-white/5 hover:bg-white/10"
              }`}
            >
              <p className="text-sm font-semibold text-zinc-100">Electricity + Coupled Gas / H2 / Heat</p>
              <p className="mt-1 text-xs text-zinc-400">
                Also layers on gas, hydrogen, and heat demand for that year. Requires the electricity
                case for that year to be solved -- solved automatically first if it isn&rsquo;t yet.
              </p>
            </button>
          </div>
        )}

        {step === "parameters" && (
          <div className="space-y-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Start from a preset</p>
              <div className="mt-2 grid grid-cols-1 gap-2">
                {SCENARIO_PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => handleApplyPreset(preset)}
                    className={`rounded-lg border p-3 text-left transition ${
                      appliedPresetId === preset.id
                        ? "border-emerald-500/40 bg-emerald-500/10"
                        : "border-white/10 bg-white/5 hover:bg-white/10"
                    }`}
                  >
                    <p className="text-xs font-medium text-zinc-100">{preset.label}</p>
                    <p className="mt-0.5 text-[11px] text-zinc-500">{preset.description}</p>
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <label htmlFor="wizard-target-year" className="text-sm font-medium text-zinc-100">
                Target Year
              </label>
              <select
                id="wizard-target-year"
                value={targetYear}
                disabled={isBusy || optionsState === "loading"}
                onChange={(event) => handleSelectYear(Number(event.target.value))}
                className="mt-3 w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-3 text-sm text-zinc-100 outline-none focus:border-emerald-400 disabled:opacity-50"
              >
                {optionsState === "loading" && <option>Loading years...</option>}
                {optionsState === "error" && <option value={FALLBACK_YEAR}>{FALLBACK_YEAR}</option>}
                {yearOptions.map((year) => (
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
              {scenarioType === "coupled" && yearOptions.length === 0 && optionsState === "ready" && (
                <p className="mt-2 text-xs text-amber-300">No coupled scenarios are defined yet.</p>
              )}
            </div>

            {scenarioType === "coupled" && (
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <label htmlFor="wizard-h2-scenario" className="text-sm font-medium text-zinc-100">
                  H2 Market Scenario
                </label>
                <select
                  id="wizard-h2-scenario"
                  value={h2MarketScenario ?? ""}
                  disabled={isBusy || h2ScenarioOptionsForYear.length === 0}
                  onChange={(event) => setH2MarketScenario(event.target.value)}
                  className="mt-3 w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-3 text-sm capitalize text-zinc-100 outline-none focus:border-emerald-400 disabled:opacity-50"
                >
                  {h2ScenarioOptionsForYear.length === 0 && <option>No scenarios defined for this year</option>}
                  {h2ScenarioOptionsForYear.map((option) => (
                    <option key={option.h2_market_scenario} value={option.h2_market_scenario} className="capitalize">
                      {option.h2_market_scenario.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <div className="flex items-center justify-between">
                <label htmlFor="wizard-growth-rate" className="text-sm font-medium text-zinc-100">
                  Annual Demand Growth
                </label>
                <span className="text-sm text-emerald-300">{(annualGrowthRate * 100).toFixed(1)}%/yr</span>
              </div>
              <input
                id="wizard-growth-rate"
                type="range"
                min={options?.annual_growth_rate_min ?? -0.05}
                max={options?.annual_growth_rate_max ?? 0.1}
                step={0.005}
                value={annualGrowthRate}
                disabled={isBusy}
                onChange={(event) => {
                  setAnnualGrowthRate(Number(event.target.value));
                  setAppliedPresetId(null);
                }}
                className="mt-3 w-full accent-emerald-400 disabled:opacity-50"
              />
            </div>
          </div>
        )}

        {step === "advanced" && (
          <div className="space-y-4">
            {scenarioType === "electricity" ? (
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <label className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={forceFetch}
                    disabled={isBusy}
                    onChange={(event) => setForceFetch(event.target.checked)}
                    className="mt-0.5 accent-emerald-400"
                  />
                  <span>
                    <span className="text-sm font-medium text-zinc-100">Refetch demand data from ENTSO-E</span>
                    <span className="mt-1 block text-xs text-zinc-500">
                      Off by default -- uses the cached forecast. Turn this on only if the underlying demand
                      data changed and you need a fresh pull (slower).
                    </span>
                  </span>
                </label>
              </div>
            ) : (
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <p className="text-sm font-medium text-zinc-100">Storage modeling method</p>
                <div className="mt-3 space-y-2">
                  {(
                    [
                      {
                        id: "representative-days" as const,
                        label: "Representative days (default)",
                        description: "Fastest -- the standard method used everywhere else in this app.",
                      },
                      {
                        id: "chronological" as const,
                        label: "Chronological seasonal storage",
                        description:
                          "Exact hour-by-hour seasonal storage tracking across the whole year -- slower, " +
                          "solved as a separate case so you can compare it against the default result.",
                      },
                      {
                        id: "linked" as const,
                        label: "Linked representative periods",
                        description:
                          "A cyclic/linked representative-day method for storage -- a middle ground between " +
                          "speed and seasonal accuracy.",
                      },
                    ]
                  ).map((choice) => (
                    <label key={choice.id} className="flex items-start gap-3">
                      <input
                        type="radio"
                        name="storage-method"
                        checked={storageMethod === choice.id}
                        disabled={isBusy}
                        onChange={() => setStorageMethod(choice.id)}
                        className="mt-0.5 accent-emerald-400"
                      />
                      <span>
                        <span className="text-sm text-zinc-100">{choice.label}</span>
                        <span className="mt-0.5 block text-xs text-zinc-500">{choice.description}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {step === "review" && (
          <div className="space-y-4">
            <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-zinc-200">
              {summarySentence()}
              {electricityAlreadySolved && (
                <p className="mt-2 text-xs text-amber-300">
                  Solving again replaces any existing result for this exact combination.
                </p>
              )}
            </div>

            <button
              type="button"
              onClick={handleSolve}
              disabled={isBusy || (scenarioType === "coupled" && !h2MarketScenario)}
              className="w-full rounded-lg bg-emerald-500 px-4 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-emerald-500/40"
            >
              {isBusy ? "Solving..." : "Solve Scenario"}
            </button>

            {statusMessage && solveState !== "error" && solveState !== "crashed" && solveState !== "precondition-failed" && (
              <p className="text-xs text-zinc-400">{statusMessage}</p>
            )}

            {solveState === "precondition-failed" && (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
                <p className="font-semibold">Electricity case not solved yet</p>
                <p className="mt-1 text-xs">{errorMessage}</p>
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

            {(electricityCaseName || coupledCaseName) && (
              <p className="text-xs text-zinc-600">
                Case: <span className="font-mono text-zinc-400">{coupledCaseName ?? electricityCaseName}</span>
              </p>
            )}
          </div>
        )}

        <div className="flex gap-2">
          {stepIndex > 0 && (
            <button
              type="button"
              disabled={isBusy}
              onClick={() => setStep(WIZARD_STEPS[stepIndex - 1].id)}
              className="flex-1 rounded-lg border border-white/10 bg-zinc-950 px-4 py-2 text-sm text-zinc-300 transition hover:bg-zinc-900 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Back
            </button>
          )}
          {stepIndex < WIZARD_STEPS.length - 1 && (
            <button
              type="button"
              disabled={isBusy}
              onClick={() => setStep(WIZARD_STEPS[stepIndex + 1].id)}
              className="flex-1 rounded-lg bg-zinc-800 px-4 py-2 text-sm text-zinc-100 transition hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          )}
        </div>
      </div>

      <div>
        {solveState === "success" && (electricityResult || coupledResult) ? (
          <div className="space-y-4">
            {coupledResult ? (
              <CoupledScenarioResultsView result={coupledResult} />
            ) : (
              electricityResult && (
                <div>
                  <div className="rounded-xl border border-white/10 bg-zinc-950/90 p-4 text-sm text-zinc-100">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
                      Latest Result — {electricityResult.target_year}
                    </p>
                    <p className="mt-2 text-xs text-zinc-400">
                      Objective cost: €
                      {(electricityResult.objective_eur ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      /year
                      {electricityResult.parameters?.annual_growth_rate != null &&
                        ` · ${(electricityResult.parameters.annual_growth_rate * 100).toFixed(1)}%/yr demand growth`}
                    </p>
                  </div>
                  <ScenarioResultsCharts result={electricityResult} />
                </div>
              )
            )}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-white/10 p-8">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">What will run</p>
            <p className="mt-3 text-sm text-zinc-300">{summarySentence()}</p>
            <p className="mt-6 text-sm text-zinc-500">
              Step through Model → Parameters → Advanced → Review, then hit Solve to see results here.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
