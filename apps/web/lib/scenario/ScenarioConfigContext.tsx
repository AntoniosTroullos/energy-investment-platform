"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { customScenarioStorageKey, defaultScenario } from "./scenario.defaults";
import type { Scenario } from "./scenario.types";
import { isScenario, sanitizeScenario } from "./scenario.utils";

// The screening scenario (budget tier, preferred technology, connection
// distance, min investment score) is *configured* on the Scenario Studio
// page (/scenarios, ScenarioPresetsPanel + ScenarioControlsPanel) but
// *consumed* on the Map page (/, candidate-cell highlighting, Top
// Opportunities, Compare) -- the one piece of state that genuinely needs to
// be shared across those two routed pages. Everything else those two panels
// use (evaluation results, import/export UI, status messages) stays local
// to wherever they're rendered; only the active scenario + the saved custom
// preset need to survive navigation between the two pages.

type ScenarioConfigContextValue = {
  scenario: Scenario;
  setScenario: (scenario: Scenario) => void;
  savedCustomScenario: Scenario | null;
  setSavedCustomScenario: (scenario: Scenario | null) => void;
  // One-shot handoff from Scenario Studio to the Map page: clicking a
  // candidate in the Evaluate Scenario results stores its id here and
  // navigates to the map, which focuses it and clears the request. Held in
  // context (not the URL) so it survives the client-side route change without
  // needing a Suspense boundary for useSearchParams.
  pendingMapFocusCandidateId: string | null;
  setPendingMapFocusCandidateId: (candidateId: string | null) => void;
};

const ScenarioConfigContext = createContext<ScenarioConfigContextValue | null>(null);

export function ScenarioConfigProvider({ children }: { children: ReactNode }) {
  const [scenario, setScenario] = useState<Scenario>(defaultScenario);
  const [savedCustomScenario, setSavedCustomScenario] = useState<Scenario | null>(null);
  const [pendingMapFocusCandidateId, setPendingMapFocusCandidateId] = useState<string | null>(null);

  useEffect(() => {
    const storedScenario = window.localStorage.getItem(customScenarioStorageKey);

    if (!storedScenario) {
      return;
    }

    try {
      const parsedScenario = JSON.parse(storedScenario);

      if (isScenario(parsedScenario)) {
        // A mount-only effect is the correct, SSR-safe way to restore this
        // from localStorage: window doesn't exist during Next's server
        // render, so this must run client-side only, after hydration --
        // exactly what an effect (and only an effect) guarantees. A lazy
        // useState initializer would read localStorage during the render
        // that also runs on the server and would either crash (no window)
        // or, guarded, produce a hydration mismatch against the server's
        // null-state HTML the moment a preset is actually saved.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setSavedCustomScenario(sanitizeScenario(parsedScenario));
      }
    } catch {
      window.localStorage.removeItem(customScenarioStorageKey);
    }
  }, []);

  return (
    <ScenarioConfigContext.Provider
      value={{
        scenario,
        setScenario,
        savedCustomScenario,
        setSavedCustomScenario,
        pendingMapFocusCandidateId,
        setPendingMapFocusCandidateId,
      }}
    >
      {children}
    </ScenarioConfigContext.Provider>
  );
}

export function useScenarioConfig(): ScenarioConfigContextValue {
  const context = useContext(ScenarioConfigContext);

  if (!context) {
    throw new Error("useScenarioConfig must be used within a ScenarioConfigProvider");
  }

  return context;
}
