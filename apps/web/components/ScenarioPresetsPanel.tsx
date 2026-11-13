"use client";

import { motion, AnimatePresence } from "motion/react";
import { ChevronDown, Search, RotateCcw, Bookmark, Download, Upload, Copy } from "lucide-react";

import { getEvaluationCandidateBadge } from "../lib/evaluation-badges";
import { scenarioPresets } from "../lib/scenario/scenario.presets";
import type {
  ScenarioEvaluationResponse,
} from "../lib/scenario/scenario.api";
import type { Scenario } from "../lib/scenario/scenario.types";
import { DEFAULT_PRESET_META, PRESET_META } from "./scenario-visuals";

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
      <h2 className="font-display text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
        Quick Start
      </h2>
      <p className="mt-2 text-xs leading-5 text-zinc-500">
        Pick a starting point — tweak it below, or use it as-is.
      </p>

      <div className="mt-4 grid grid-cols-2 gap-2.5">
        {scenarioPresets.map((preset, index) => {
          const isActive = activePresetName === preset.name;
          const meta = PRESET_META[preset.name] ?? DEFAULT_PRESET_META;

          return (
            <motion.button
              key={preset.name}
              type="button"
              onClick={() => onSelectPreset(preset.scenario)}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              whileTap={{ scale: 0.97 }}
              className="relative overflow-hidden rounded-xl border px-3.5 py-3.5 text-left transition-colors"
              style={{
                borderColor: isActive ? `${meta.color}66` : "rgba(255,255,255,0.1)",
                background: isActive ? `${meta.color}14` : "rgba(255,255,255,0.03)",
              }}
            >
              <meta.Icon className="h-5 w-5" style={{ color: meta.color }} strokeWidth={1.75} />
              <p className="mt-2 text-sm font-medium text-zinc-100">{preset.name}</p>
              <p className="mt-1 text-[11px] leading-4 text-zinc-500">{preset.description}</p>
              {isActive ? (
                <motion.span
                  layoutId="preset-active-dot"
                  className="absolute right-3 top-3 h-2 w-2 rounded-full"
                  style={{ background: meta.color }}
                />
              ) : null}
            </motion.button>
          );
        })}
      </div>

      <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-4">
        <button
          type="button"
          onClick={onEvaluateScenario}
          disabled={evaluationRequestState === "loading"}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm font-medium text-emerald-300 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-zinc-500"
        >
          <Search className="h-4 w-4" strokeWidth={1.75} />
          {evaluationRequestState === "loading" ? "Searching..." : "Find Matching Sites"}
        </button>

        <button
          type="button"
          onClick={onResetScenario}
          className="mt-2.5 flex w-full items-center justify-center gap-2 rounded-lg border border-white/10 bg-zinc-950 px-4 py-2.5 text-xs text-zinc-400 transition hover:bg-zinc-900 hover:text-zinc-200"
        >
          <RotateCcw className="h-3.5 w-3.5" strokeWidth={1.75} />
          Reset to Default
        </button>

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

        <AnimatePresence>
          {scenarioEvaluation || evaluationRequestState === "loading" || evaluationRequestState === "error" ? (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <div className="mt-4 rounded-lg border border-white/10 bg-zinc-950/90 p-4">
                {evaluationRequestState === "loading" ? (
                  <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-3">
                    <p className="text-sm text-emerald-300">Searching for matching sites...</p>
                  </div>
                ) : null}

                {evaluationRequestState === "error" ? (
                  <div className="rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-3">
                    <p className="text-sm text-rose-300">{evaluationErrorMessage}</p>
                  </div>
                ) : null}

                {scenarioEvaluation ? (
                  <>
                    <div className="flex items-baseline gap-2">
                      <motion.span
                        key={scenarioEvaluation.eligibleCount}
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="text-3xl font-semibold text-emerald-300"
                      >
                        {scenarioEvaluation.eligibleCount}
                      </motion.span>
                      <span className="text-sm text-zinc-400">matching sites found</span>
                    </div>

                    <div className="mt-3 flex items-center gap-4 text-xs text-zinc-400">
                      <span className="inline-flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full bg-[#f5b942]" />
                        Solar: {scenarioEvaluation.technologyBreakdown.solar}
                      </span>
                      <span className="inline-flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full bg-[#45d2aa]" />
                        Wind: {scenarioEvaluation.technologyBreakdown.wind}
                      </span>
                    </div>

                    <p className="mt-3 text-xs leading-5 text-zinc-400">{scenarioEvaluation.summary}</p>

                    {scenarioEvaluation.topCandidates.length > 0 ? (
                      <div className="mt-4 space-y-2.5">
                        <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                          Top candidates
                        </p>
                        {scenarioEvaluation.topCandidates.map((candidate, index) => {
                          const badge = getEvaluationCandidateBadge(
                            candidate,
                            scenarioEvaluation.topCandidates,
                          );

                          return (
                            <motion.button
                              key={candidate.id}
                              type="button"
                              onClick={() => onEvaluationCandidateFocus(candidate.id)}
                              initial={{ opacity: 0, x: -6 }}
                              animate={{ opacity: 1, x: 0 }}
                              transition={{ delay: index * 0.06 }}
                              whileTap={{ scale: 0.98 }}
                              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2.5 text-left transition hover:bg-white/10"
                            >
                              <div className="flex items-center justify-between gap-3">
                                <div className="min-w-0">
                                  <p className="truncate text-sm font-medium text-zinc-100">
                                    {candidate.id}
                                  </p>
                                  <p className="mt-0.5 text-xs capitalize text-zinc-400">
                                    {candidate.technology} · {candidate.distanceToSubstationKm} km to
                                    substation
                                  </p>
                                </div>
                                <div className="flex shrink-0 items-center gap-2">
                                  {badge ? (
                                    <span
                                      className={`inline-flex rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.15em] ${badge.className}`}
                                    >
                                      {badge.label}
                                    </span>
                                  ) : null}
                                  <span className="text-sm font-semibold text-emerald-300">
                                    {candidate.investmentScore}
                                  </span>
                                </div>
                              </div>
                            </motion.button>
                          );
                        })}
                      </div>
                    ) : null}
                  </>
                ) : null}
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>

      <details className="mt-4 rounded-xl border border-white/10 bg-white/5 p-4">
        <summary className="flex cursor-pointer list-none items-center justify-between font-display text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
          Advanced
          <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" strokeWidth={1.75} />
        </summary>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onSaveCustomPreset}
            className="flex items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-zinc-950 px-3 py-2.5 text-xs text-zinc-200 transition hover:bg-zinc-900"
          >
            <Bookmark className="h-3.5 w-3.5" strokeWidth={1.75} />
            Save Preset
          </button>

          {savedCustomScenario ? (
            <button
              type="button"
              onClick={onLoadCustomPreset}
              className="flex items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-zinc-950 px-3 py-2.5 text-xs text-zinc-200 transition hover:bg-zinc-900"
            >
              <Bookmark className="h-3.5 w-3.5" strokeWidth={1.75} />
              Load Saved
            </button>
          ) : null}

          <button
            type="button"
            onClick={onCopyScenario}
            className="flex items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-zinc-950 px-3 py-2.5 text-xs text-zinc-200 transition hover:bg-zinc-900"
          >
            <Copy className="h-3.5 w-3.5" strokeWidth={1.75} />
            Copy JSON
          </button>

          <button
            type="button"
            onClick={onDownloadScenario}
            className="flex items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-zinc-950 px-3 py-2.5 text-xs text-zinc-200 transition hover:bg-zinc-900"
          >
            <Download className="h-3.5 w-3.5" strokeWidth={1.75} />
            Download
          </button>

          <button
            type="button"
            onClick={onOpenImportScenario}
            className="col-span-2 flex items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-zinc-950 px-3 py-2.5 text-xs text-zinc-200 transition hover:bg-zinc-900"
          >
            <Upload className="h-3.5 w-3.5" strokeWidth={1.75} />
            Import Scenario JSON
          </button>
        </div>

        {isImportOpen ? (
          <div className="mt-3 rounded-lg border border-white/10 bg-zinc-950/90 p-4">
            <label
              htmlFor="scenario-import"
              className="font-display text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500"
            >
              Paste Scenario JSON
            </label>
            <textarea
              id="scenario-import"
              value={importText}
              onChange={(event) => onImportTextChange(event.target.value)}
              placeholder='{\n  "budgetTier": "medium",\n  "preferredTechnology": "all"\n}'
              rows={8}
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
      </details>
    </section>
  );
}
