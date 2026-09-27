"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import CandidateInvestmentPanel from "../../components/CandidateInvestmentPanel";
import ScenarioComparisonPanel from "../../components/ScenarioComparisonPanel";
import ScenarioControlsPanel from "../../components/ScenarioControlsPanel";
import ScenarioPresetsPanel from "../../components/ScenarioPresetsPanel";
import ScenarioWizardPanel from "../../components/ScenarioWizardPanel";
import SpatialResultsPanel from "../../components/SpatialResultsPanel";
import { apiUrl } from "../../lib/config";
import { useScenarioConfig } from "../../lib/scenario/ScenarioConfigContext";
import { customScenarioStorageKey, defaultScenario } from "../../lib/scenario/scenario.defaults";
import type { ScenarioEvaluationResponse } from "../../lib/scenario/scenario.api";
import type { Scenario } from "../../lib/scenario/scenario.types";
import {
  formatScenarioJson,
  getActivePresetName,
  isScenario,
  sanitizeScenario,
} from "../../lib/scenario/scenario.utils";

const SCENARIO_EVALUATION_API_URL = apiUrl("/scenario/evaluate");

type EvaluationRequestState = "idle" | "loading" | "success" | "error";
type PypsaTab = "build" | "spatial" | "compare";

const PYPSA_TABS: { id: PypsaTab; label: string }[] = [
  { id: "build", label: "Build & Solve" },
  { id: "spatial", label: "Spatial Results" },
  { id: "compare", label: "Compare Scenarios" },
];

export default function ScenarioStudioPage() {
  const {
    scenario,
    setScenario,
    savedCustomScenario,
    setSavedCustomScenario,
    setPendingMapFocusCandidateId,
  } = useScenarioConfig();
  const router = useRouter();

  const [scenarioStatus, setScenarioStatus] = useState("");
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [importText, setImportText] = useState("");
  const [scenarioEvaluation, setScenarioEvaluation] = useState<ScenarioEvaluationResponse | null>(null);
  const [evaluationRequestState, setEvaluationRequestState] = useState<EvaluationRequestState>("idle");
  const [evaluationErrorMessage, setEvaluationErrorMessage] = useState("");

  const [activeTab, setActiveTab] = useState<PypsaTab>("build");

  const activePresetName = getActivePresetName(scenario);

  return (
    <main className="mx-auto max-w-6xl px-6 py-10 text-zinc-100">
      <div className="border-b border-white/10 pb-6">
        <p className="text-2xl font-semibold tracking-tight">Scenario Studio</p>
        <p className="mt-2 text-sm text-zinc-400">
          Configure and solve Greece&rsquo;s real energy models, and screen candidate investment
          sites — full-size results, away from the map.
        </p>
      </div>

      <section className="mt-10">
        <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
          Investment Screening Scenario
        </h2>
        <p className="mt-2 text-xs text-zinc-500">
          Filters candidate cells shown on the Map page — budget tier, technology, connection
          distance, and investment score. Changes here apply immediately on the map.
        </p>
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <ScenarioPresetsPanel
            activePresetName={activePresetName}
            onSelectPreset={(presetScenario) => setScenario(sanitizeScenario(presetScenario))}
            savedCustomScenario={savedCustomScenario}
            onResetScenario={handleResetScenario}
            onSaveCustomPreset={handleSaveCustomPreset}
            onLoadCustomPreset={handleLoadCustomPreset}
            onCopyScenario={handleCopyScenario}
            onDownloadScenario={handleDownloadScenario}
            scenarioStatus={scenarioStatus}
            candidateLoadState="idle"
            candidateLoadErrorMessage=""
            infrastructureLoadState="idle"
            infrastructureLoadErrorMessage=""
            isImportOpen={isImportOpen}
            importText={importText}
            onImportTextChange={setImportText}
            onOpenImportScenario={handleOpenImportScenario}
            onCancelImportScenario={handleCancelImportScenario}
            onImportScenario={handleImportScenario}
            evaluationRequestState={evaluationRequestState}
            evaluationErrorMessage={evaluationErrorMessage}
            onEvaluateScenario={handleEvaluateScenario}
            scenarioEvaluation={scenarioEvaluation}
            onEvaluationCandidateFocus={handleEvaluationCandidateFocus}
          />
          <ScenarioControlsPanel scenario={scenario} onUpdateScenario={handleUpdateScenario} />
        </div>
        <CandidateInvestmentPanel scenario={scenario} />
      </section>

      <section className="mt-12">
        <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
          PyPSA Model Scenarios
        </h2>
        <p className="mt-2 text-xs text-zinc-500">
          Solves Greece&rsquo;s real electricity, and coupled gas/hydrogen/heat, PyPSA models.
        </p>

        <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-2">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {PYPSA_TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`rounded-lg px-3 py-3 text-sm font-medium transition ${
                  activeTab === tab.id
                    ? "border border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                    : "border border-white/10 bg-zinc-950 text-zinc-300 hover:bg-zinc-900"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-6">
          {activeTab === "build" && <ScenarioWizardPanel />}
          {activeTab === "spatial" && <SpatialResultsPanel />}
          {activeTab === "compare" && (
            // Re-fetches GET /scenarios each time this tab is opened -- a
            // simpler and equally correct trigger than the old cross-panel
            // "just solved" event, and it also works for scenarios solved in
            // an earlier session, not just this one.
            <ScenarioComparisonPanel refreshSignal={activeTab} />
          )}
        </div>
      </section>
    </main>
  );

  // This page has no map, so focusing a candidate means handing it to the Map
  // page: record the id, then navigate there (the map picks it up on arrival).
  function handleEvaluationCandidateFocus(candidateId: string) {
    setPendingMapFocusCandidateId(candidateId);
    router.push("/");
  }

  function handleUpdateScenario(updates: Partial<Scenario>) {
    setScenario(sanitizeScenario({ ...scenario, ...updates }));
  }

  function handleResetScenario() {
    setScenario(sanitizeScenario(defaultScenario));
    setScenarioStatus("Reset to default scenario");
  }

  function handleSaveCustomPreset() {
    const sanitizedScenario = sanitizeScenario(scenario);

    window.localStorage.setItem(customScenarioStorageKey, JSON.stringify(sanitizedScenario));
    setSavedCustomScenario(sanitizedScenario);
    setScenarioStatus("Custom preset saved");
  }

  function handleLoadCustomPreset() {
    if (!savedCustomScenario) {
      return;
    }

    setScenario(sanitizeScenario(savedCustomScenario));
    setScenarioStatus("Loaded custom preset");
  }

  async function handleCopyScenario() {
    const scenarioJson = formatScenarioJson(scenario);

    try {
      await navigator.clipboard.writeText(scenarioJson);
      setScenarioStatus("Scenario copied");
    } catch {
      setScenarioStatus("Clipboard copy unavailable");
    }
  }

  function handleDownloadScenario() {
    const scenarioJson = formatScenarioJson(scenario);
    const fileBlob = new Blob([scenarioJson], { type: "application/json" });
    const downloadUrl = URL.createObjectURL(fileBlob);
    const link = document.createElement("a");

    link.href = downloadUrl;
    link.download = "scenario-export.json";
    link.click();
    URL.revokeObjectURL(downloadUrl);
    setScenarioStatus("Scenario downloaded");
  }

  function handleOpenImportScenario() {
    setImportText(formatScenarioJson(scenario));
    setIsImportOpen(true);
    setScenarioStatus("");
  }

  function handleCancelImportScenario() {
    setIsImportOpen(false);
    setImportText("");
  }

  function handleImportScenario() {
    try {
      const parsedScenario = JSON.parse(importText);

      if (!isScenario(parsedScenario)) {
        setScenarioStatus("Invalid scenario JSON");
        return;
      }

      const sanitizedScenario = sanitizeScenario(parsedScenario);
      setScenario(sanitizedScenario);
      setIsImportOpen(false);
      setImportText("");
      setScenarioStatus("Scenario imported");
    } catch {
      setScenarioStatus("Invalid scenario JSON");
    }
  }

  async function handleEvaluateScenario() {
    setEvaluationRequestState("loading");
    setEvaluationErrorMessage("");

    try {
      const response = await fetch(SCENARIO_EVALUATION_API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          scenario,
        }),
      });

      if (!response.ok) {
        setEvaluationRequestState("error");
        setEvaluationErrorMessage("Scenario evaluation failed. Backend unavailable or returned an error.");
        return;
      }

      const result = (await response.json()) as ScenarioEvaluationResponse;

      setScenarioEvaluation(result);
      setEvaluationRequestState("success");
    } catch {
      setEvaluationRequestState("error");
      setEvaluationErrorMessage("Could not reach evaluation service.");
    }
  }
}
