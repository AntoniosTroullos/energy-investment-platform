"use client";

import { getEvaluationCandidateBadge } from "../lib/evaluation-badges";
import { scenarioPresets } from "../lib/scenario/scenario.presets";
import type {
  ScenarioEvaluationResponse,
} from "../lib/scenario/scenario.api";
import type { Scenario } from "../lib/scenario/scenario.types";

type RequestState = "idle" | "loading" | "success" | "error";

type ScenarioPresetsPanelProps = {
  activePresetName: string | null;
  onSelectPreset: (scenario: Scenario) => void;
  savedCustomScenario: Scenario | null;
  onResetScenario: () => void;
  onSaveCustomPreset: () => void;
  onLoadCustomPreset: () => void;
  onCopyScenario: () => void;
  onDownloadScenario: () => void;
  scenarioStatus: string;
  candidateLoadState: RequestState;
  candidateLoadErrorMessage: string;
  infrastructureLoadState: RequestState;
  infrastructureLoadErrorMessage: string;
  isImportOpen: boolean;
  importText: string;
  onImportTextChange: (value: string) => void;
  onOpenImportScenario: () => void;
  onCancelImportScenario: () => void;
  onImportScenario: () => void;
  evaluationRequestState: RequestState;
  evaluationErrorMessage: string;
  onEvaluateScenario: () => void;
  scenarioEvaluation: ScenarioEvaluationResponse | null;
  onEvaluationCandidateFocus: (candidateId: string) => void;
};

export default function ScenarioPresetsPanel({
  activePresetName,
  onSelectPreset,
  savedCustomScenario,
  onResetScenario,
  onSaveCustomPreset,
  onLoadCustomPreset,
  onCopyScenario,
  onDownloadScenario,
  scenarioStatus,
  candidateLoadState,
  candidateLoadErrorMessage,
  infrastructureLoadState,
  infrastructureLoadErrorMessage,
  isImportOpen,
  importText,
  onImportTextChange,
  onOpenImportScenario,
  onCancelImportScenario,
  onImportScenario,
  evaluationRequestState,
  evaluationErrorMessage,
  onEvaluateScenario,
  scenarioEvaluation,
  onEvaluationCandidateFocus,
}: ScenarioPresetsPanelProps) {
  return (
    <section className="mt-8">
      <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
        Scenario Presets
      </h2>
      <div className="mt-4 space-y-3">
        {scenarioPresets.map((preset) => {
          const isActive = activePresetName === preset.name;

          return (
            <button
              key={preset.name}
              type="button"
              onClick={() => onSelectPreset(preset.scenario)}
              className={`w-full rounded-xl border px-4 py-4 text-left transition ${
                isActive
                  ? "border-emerald-500/40 bg-emerald-500/10"
                  : "border-white/10 bg-white/5 hover:bg-white/10"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-zinc-100">
                    {preset.name}
                  </p>
                  <p className="mt-2 text-xs leading-5 text-zinc-400">
                    {preset.description}
                  </p>
                </div>
                {isActive ? (
                  <span className="shrink-0 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
                    Active
                  </span>
                ) : null}
              </div>
            </button>
          );
        })}

        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <div className="flex flex-col gap-3">
            <button
              type="button"
              onClick={onResetScenario}
              className="w-full rounded-lg border border-white/10 bg-zinc-950 px-4 py-3 text-sm text-zinc-100 transition hover:bg-zinc-900"
            >
              Reset to Default
            </button>

            <button
              type="button"
              onClick={onSaveCustomPreset}
              className="w-full rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm font-medium text-emerald-300 transition hover:bg-emerald-500/20"
            >
              Save Custom Preset
            </button>

            {savedCustomScenario ? (
              <button
                type="button"
                onClick={onLoadCustomPreset}
                className="w-full rounded-lg border border-white/10 bg-zinc-950 px-4 py-3 text-sm text-zinc-100 transition hover:bg-zinc-900"
              >
                Load Custom Preset
              </button>
            ) : null}

            <button
              type="button"
              onClick={onCopyScenario}
              className="w-full rounded-lg border border-white/10 bg-zinc-950 px-4 py-3 text-sm text-zinc-100 transition hover:bg-zinc-900"
            >
              Export Scenario
            </button>

            <button
              type="button"
              onClick={onDownloadScenario}
              className="w-full rounded-lg border border-white/10 bg-zinc-950 px-4 py-3 text-sm text-zinc-100 transition hover:bg-zinc-900"
            >
              Download Scenario JSON
            </button>

            <button
              type="button"
              onClick={onOpenImportScenario}
              className="w-full rounded-lg border border-white/10 bg-zinc-950 px-4 py-3 text-sm text-zinc-100 transition hover:bg-zinc-900"
            >
              Import Scenario
            </button>

            <button
              type="button"
              onClick={onEvaluateScenario}
              disabled={evaluationRequestState === "loading"}
              className="w-full rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm font-medium text-emerald-300 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-zinc-500"
            >
              {evaluationRequestState === "loading"
                ? "Evaluating..."
                : "Evaluate Scenario"}
            </button>
          </div>

          {scenarioStatus ? (
            <p className="mt-3 text-xs text-zinc-400">{scenarioStatus}</p>
          ) : null}

          {candidateLoadState === "loading" ? (
            <p className="mt-3 text-xs text-zinc-400">
              Loading candidate cells from backend...
            </p>
          ) : null}

          {candidateLoadState === "error" ? (
            <div className="mt-3 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-3">
              <p className="text-sm text-rose-300">
                {candidateLoadErrorMessage}
              </p>
            </div>
          ) : null}

          {infrastructureLoadState === "loading" ? (
            <p className="mt-3 text-xs text-zinc-400">
              Loading Greece-wide infrastructure from backend...
            </p>
          ) : null}

          {infrastructureLoadState === "error" ? (
            <div className="mt-3 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-3">
              <p className="text-sm text-rose-300">
                {infrastructureLoadErrorMessage}
              </p>
            </div>
          ) : null}

          {isImportOpen ? (
            <div className="mt-4 rounded-lg border border-white/10 bg-zinc-950/90 p-4">
              <label
                htmlFor="scenario-import"
                className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500"
              >
                Paste Scenario JSON
              </label>
              <textarea
                id="scenario-import"
                value={importText}
                onChange={(event) => onImportTextChange(event.target.value)}
                placeholder='{\n  "budgetTier": "medium",\n  "preferredTechnology": "all"\n}'
                rows={10}
                className="mt-3 w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-3 font-mono text-xs leading-5 text-zinc-100 outline-none placeholder:text-zinc-500 focus:border-emerald-400"
              />
              <div className="mt-3 flex gap-3">
                <button
                  type="button"
                  onClick={onImportScenario}
                  className="flex-1 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm font-medium text-emerald-300 transition hover:bg-emerald-500/20"
                >
                  Import
                </button>
                <button
                  type="button"
                  onClick={onCancelImportScenario}
                  className="rounded-lg border border-white/10 bg-zinc-950 px-4 py-3 text-sm text-zinc-100 transition hover:bg-zinc-900"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : null}

          {scenarioEvaluation ? (
            <div className="mt-4 rounded-lg border border-white/10 bg-zinc-950/90 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
                Scenario Evaluation
              </p>

              {evaluationRequestState === "loading" ? (
                <div className="mt-4 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-3">
                  <p className="text-sm text-emerald-300">
                    Evaluating scenario with backend service...
                  </p>
                </div>
              ) : null}

              {evaluationRequestState === "error" ? (
                <div className="mt-4 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-3">
                  <p className="text-sm text-rose-300">
                    {evaluationErrorMessage}
                  </p>
                </div>
              ) : null}

              <div className="mt-4 space-y-2 text-sm text-zinc-100">
                <p>Eligible candidates: {scenarioEvaluation.eligibleCount}</p>
                <p>
                  Score stats: min {scenarioEvaluation.scoreStats.min}, max{" "}
                  {scenarioEvaluation.scoreStats.max}, avg{" "}
                  {scenarioEvaluation.scoreStats.average}
                </p>
                <p>
                  Technology breakdown: solar{" "}
                  {scenarioEvaluation.technologyBreakdown.solar}, wind{" "}
                  {scenarioEvaluation.technologyBreakdown.wind}
                </p>
                <p className="text-zinc-300">{scenarioEvaluation.summary}</p>
              </div>

              {scenarioEvaluation.topCandidates.length > 0 ? (
                <div className="mt-4 space-y-3">
                  {scenarioEvaluation.topCandidates.map((candidate) => {
                    const badge = getEvaluationCandidateBadge(
                      candidate,
                      scenarioEvaluation.topCandidates,
                    );

                    return (
                      <button
                        key={candidate.id}
                        type="button"
                        onClick={() => onEvaluationCandidateFocus(candidate.id)}
                        className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-3 text-left transition hover:bg-white/10"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-zinc-100">
                              {candidate.id}
                            </p>
                            <p className="mt-1 text-xs text-zinc-400">
                              {candidate.technology}
                            </p>
                          </div>
                          <div className="text-right">
                            {badge ? (
                              <span
                                className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] ${badge.className}`}
                              >
                                {badge.label}
                              </span>
                            ) : null}
                            <p className="mt-2 text-xs text-zinc-400">Score</p>
                            <p className="text-sm font-semibold text-emerald-300">
                              {candidate.investmentScore}
                            </p>
                          </div>
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-zinc-400">
                          <p>
                            Substation: {candidate.distanceToSubstationKm} km
                          </p>
                          <p>Line: {candidate.distanceToLineKm} km</p>
                          <p>Connection: {candidate.connectionCostLevel}</p>
                          <p>
                            Land excluded: {String(candidate.landExcluded)}
                          </p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              ) : null}
            </div>
          ) : null}

          {!scenarioEvaluation && evaluationRequestState === "loading" ? (
            <div className="mt-4 rounded-lg border border-white/10 bg-zinc-950/90 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
                Scenario Evaluation
              </p>
              <div className="mt-4 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-3">
                <p className="text-sm text-emerald-300">
                  Evaluating scenario with backend service...
                </p>
              </div>
            </div>
          ) : null}

          {!scenarioEvaluation && evaluationRequestState === "error" ? (
            <div className="mt-4 rounded-lg border border-white/10 bg-zinc-950/90 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
                Scenario Evaluation
              </p>
              <div className="mt-4 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-3">
                <p className="text-sm text-rose-300">
                  {evaluationErrorMessage}
                </p>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
