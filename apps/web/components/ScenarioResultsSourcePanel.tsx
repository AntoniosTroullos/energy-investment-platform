"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getScenarioList } from "../lib/pypsaScenario/pypsaScenario.api";
import type { ScenarioListItem } from "../lib/pypsaScenario/pypsaScenario.types";
import { REGION_METRICS, type RegionMetricId } from "../lib/spatial/colorScale";
import StaleBadge from "./StaleBadge";

type ScenarioResultsSourcePanelProps = {
  selectedCaseName: string | null;
  onSelectCaseName: (caseName: string | null) => void;
  metricId: RegionMetricId;
  onSelectMetric: (metricId: RegionMetricId) => void;
};

// Replaces the old in-session "just solved this" wiring: this panel is
// self-sufficient, listing every solved PyPSA scenario (GET /scenarios,
// already built) regardless of which page or session solved it, and lets
// the map choropleth show any of them. The actual solve-and-configure UI
// lives on the Scenario Studio page (/scenarios) -- this panel only picks
// which already-solved result the map should display.
export default function ScenarioResultsSourcePanel({
  selectedCaseName,
  onSelectCaseName,
  metricId,
  onSelectMetric,
}: ScenarioResultsSourcePanelProps) {
  const [scenarios, setScenarios] = useState<ScenarioListItem[]>([]);
  const [errorMessage, setErrorMessage] = useState("");
  // Bumped by the Refresh button -- gives the effect below a real dependency
  // to react to, so "load on mount" and "load on refresh" share one path.
  const [refreshToken, setRefreshToken] = useState(0);

  async function loadScenarios() {
    try {
      const response = await getScenarioList();
      setScenarios(response.scenarios.filter((item) => item.state === "done" && item.solved));
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load solved scenarios.");
    }
  }

  useEffect(() => {
    // Fetching from an API on mount/refresh is one of React's own
    // documented valid effect use cases (syncing with an external system --
    // here, the scenario-solve backend). loadScenarios() only calls
    // setState after its internal `await`, never synchronously -- the
    // react-hooks/set-state-in-effect false-positive here is specifically
    // about this effect's dependency being local state (refreshToken)
    // rather than a prop, which its heuristic treats more strictly.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadScenarios();
  }, [refreshToken]);

  const selectedItem = scenarios.find((item) => item.case_name === selectedCaseName) ?? null;

  return (
    <section className="mt-8">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
          Scenario Results
        </h2>
        <button
          type="button"
          onClick={() => setRefreshToken((token) => token + 1)}
          className="text-xs text-emerald-300 hover:text-emerald-200"
        >
          Refresh
        </button>
      </div>

      <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-4">
        <label htmlFor="scenario-results-source" className="text-sm font-medium text-zinc-100">
          Show solved scenario on map
        </label>
        <select
          id="scenario-results-source"
          value={selectedCaseName ?? ""}
          onChange={(event) => onSelectCaseName(event.target.value || null)}
          className="mt-3 w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-3 text-sm text-zinc-100 outline-none focus:border-emerald-400"
        >
          <option value="">None</option>
          {scenarios.map((item) => (
            <option key={item.case_name} value={item.case_name}>
              {`${item.target_year} — ${item.case_name}${item.electricity_staleness?.is_stale ? " (outdated)" : ""}`}
            </option>
          ))}
        </select>

        {selectedCaseName && (
          <div className="mt-3">
            <label htmlFor="scenario-results-metric" className="text-xs font-medium text-zinc-100">
              Shade regions by
            </label>
            <select
              id="scenario-results-metric"
              value={metricId}
              onChange={(event) => onSelectMetric(event.target.value as RegionMetricId)}
              className="mt-2 w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-emerald-400"
            >
              {REGION_METRICS.map((metric) => (
                <option key={metric.id} value={metric.id}>
                  {metric.label}
                </option>
              ))}
            </select>
          </div>
        )}

        {selectedItem?.electricity_staleness?.is_stale && (
          <div className="mt-3 flex items-start gap-2">
            <StaleBadge staleness={selectedItem.electricity_staleness} />
            <p className="text-xs text-zinc-400">
              Solved before the model last changed — hover the badge for details, and re-solve in
              Scenario Studio to refresh.
            </p>
          </div>
        )}

        {errorMessage && <p className="mt-3 text-xs text-rose-300">{errorMessage}</p>}

        {scenarios.length === 0 && !errorMessage && (
          <p className="mt-3 text-xs text-zinc-500">
            No solved scenarios yet.
          </p>
        )}

        <Link
          href="/scenarios"
          className="mt-3 block text-xs text-emerald-300 hover:text-emerald-200"
        >
          Configure &amp; solve in Scenario Studio →
        </Link>
      </div>
    </section>
  );
}
