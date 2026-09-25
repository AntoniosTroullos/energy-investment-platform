"use client";

import { useEffect, useMemo, useState } from "react";

import {
  getNetworkTopologyGeoJson,
  getScenarioList,
  getScenarioRegionsDeltaGeoJson,
  getScenarioRegionsGeoJson,
} from "../lib/pypsaScenario/pypsaScenario.api";
import type { ScenarioListItem } from "../lib/pypsaScenario/pypsaScenario.types";
import { REGION_METRICS, type RegionMetricId } from "../lib/spatial/colorScale";
import SpatialResultsMap from "./SpatialResultsMap";

type ViewMode = "single" | "delta";
type LoadState = "loading" | "ready" | "error";

const emptyFeatureCollection: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

export default function SpatialResultsPanel() {
  const [scenarios, setScenarios] = useState<ScenarioListItem[]>([]);
  const [scenariosState, setScenariosState] = useState<LoadState>("loading");
  const [scenariosError, setScenariosError] = useState("");

  const [corridors, setCorridors] = useState<GeoJSON.FeatureCollection>(emptyFeatureCollection);

  const [viewMode, setViewMode] = useState<ViewMode>("single");
  const [caseNameA, setCaseNameA] = useState<string | null>(null);
  const [caseNameB, setCaseNameB] = useState<string | null>(null);
  const [metricId, setMetricId] = useState<RegionMetricId>("net_position_mwh");

  const [regions, setRegions] = useState<GeoJSON.FeatureCollection | null>(null);
  const [regionsState, setRegionsState] = useState<LoadState>("loading");
  const [regionsError, setRegionsError] = useState("");

  // Scenario library + the (static, cheap) network topology, once.
  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [scenarioList, topology] = await Promise.all([getScenarioList(), getNetworkTopologyGeoJson()]);
        if (cancelled) {
          return;
        }
        const solved = scenarioList.scenarios.filter((item) => item.state === "done" && item.solved);
        setScenarios(solved);
        setCorridors(topology);
        setScenariosState("ready");
        setCaseNameA((current) => current ?? solved[0]?.case_name ?? null);
        setCaseNameB((current) => current ?? solved[1]?.case_name ?? solved[0]?.case_name ?? null);
      } catch (error) {
        if (!cancelled) {
          setScenariosError(error instanceof Error ? error.message : "Unable to load the scenario library.");
          setScenariosState("error");
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  // The region GeoJSON for whatever the current mode + selection asks for.
  useEffect(() => {
    if (!caseNameA || (viewMode === "delta" && !caseNameB)) {
      return;
    }

    let cancelled = false;
    // Synchronously flipping back to "loading" is the point of this effect --
    // it re-fetches whenever the mode/selection changes, and the previous
    // render's "ready"/"error" state must not be shown while that happens.
    // Same false-positive as ScenarioResultsSourcePanel.tsx's loadScenarios
    // effect: react-hooks/set-state-in-effect's heuristic treats a dependency
    // that is local state (not a prop) more strictly than this case warrants.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setRegionsState("loading");
    setRegionsError("");

    async function load() {
      try {
        const geojson =
          viewMode === "single"
            ? await getScenarioRegionsGeoJson(caseNameA as string)
            : await getScenarioRegionsDeltaGeoJson(caseNameA as string, caseNameB as string);
        if (cancelled) {
          return;
        }
        setRegions(geojson);
        setRegionsState("ready");
      } catch (error) {
        if (!cancelled) {
          setRegionsError(error instanceof Error ? error.message : "Unable to load the spatial results.");
          setRegionsState("error");
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [viewMode, caseNameA, caseNameB]);

  const yearOf = useMemo(() => {
    const byName = new Map(scenarios.map((item) => [item.case_name, item.target_year]));
    return (caseName: string | null) => (caseName ? byName.get(caseName) : undefined);
  }, [scenarios]);

  return (
    <div className="space-y-4">
      <p className="text-xs text-zinc-500">
        A schematic map of the same 13-region network every scenario solves, shaded by a result metric you pick, with
        the real transmission corridors drawn at their rated capacity.
      </p>

      <div className="rounded-xl border border-white/10 bg-white/5 p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-white/10 bg-zinc-950/60 p-2">
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setViewMode("single")}
                className={`rounded-md px-3 py-2 text-xs font-medium transition ${
                  viewMode === "single"
                    ? "border border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                    : "border border-white/10 text-zinc-300 hover:bg-white/5"
                }`}
              >
                Single scenario
              </button>
              <button
                type="button"
                onClick={() => setViewMode("delta")}
                className={`rounded-md px-3 py-2 text-xs font-medium transition ${
                  viewMode === "delta"
                    ? "border border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                    : "border border-white/10 text-zinc-300 hover:bg-white/5"
                }`}
              >
                Compare two
              </button>
            </div>
          </div>

          <div>
            <label htmlFor="spatial-metric" className="text-xs font-medium text-zinc-100">
              Metric
            </label>
            <select
              id="spatial-metric"
              value={metricId}
              onChange={(event) => setMetricId(event.target.value as RegionMetricId)}
              className="mt-2 w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-emerald-400"
            >
              {REGION_METRICS.map((metric) => (
                <option key={metric.id} value={metric.id}>
                  {metric.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="spatial-case-a" className="text-xs font-medium text-zinc-100">
              {viewMode === "single" ? "Scenario" : "Before"}
            </label>
            <select
              id="spatial-case-a"
              value={caseNameA ?? ""}
              disabled={scenariosState !== "ready" || scenarios.length === 0}
              onChange={(event) => setCaseNameA(event.target.value)}
              className="mt-2 w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-emerald-400 disabled:opacity-50"
            >
              {scenarios.map((item) => (
                <option key={item.case_name} value={item.case_name}>
                  {item.target_year} — {item.case_name}
                </option>
              ))}
            </select>
          </div>

          {viewMode === "delta" && (
            <div>
              <label htmlFor="spatial-case-b" className="text-xs font-medium text-zinc-100">
                After
              </label>
              <select
                id="spatial-case-b"
                value={caseNameB ?? ""}
                disabled={scenariosState !== "ready" || scenarios.length === 0}
                onChange={(event) => setCaseNameB(event.target.value)}
                className="mt-2 w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-emerald-400 disabled:opacity-50"
              >
                {scenarios.map((item) => (
                  <option key={item.case_name} value={item.case_name}>
                    {item.target_year} — {item.case_name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {viewMode === "delta" && caseNameA && caseNameB && caseNameA === caseNameB && (
          <p className="mt-3 text-xs text-amber-300">
            Before and after are the same scenario — every change will read as zero.
          </p>
        )}

        {scenariosState === "error" && (
          <p className="mt-3 text-xs text-rose-300">{scenariosError}</p>
        )}

        {scenariosState === "ready" && scenarios.length === 0 && (
          <p className="mt-3 text-xs text-zinc-500">
            No solved scenarios yet — solve one in the Electricity tab to see it here.
          </p>
        )}

        {scenariosState === "ready" && scenarios.length === 1 && viewMode === "delta" && (
          <p className="mt-3 text-xs text-zinc-500">
            Only one solved scenario exists so far — solve a second year to compare.
          </p>
        )}
      </div>

      {regionsState === "error" && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          {regionsError}
        </div>
      )}

      {regionsState === "loading" && (
        <div className="flex min-h-[240px] items-center justify-center rounded-xl border border-dashed border-white/10 p-8 text-center">
          <p className="text-sm text-zinc-500">Loading spatial results...</p>
        </div>
      )}

      {regionsState === "ready" && regions && (
        <SpatialResultsMap
          regions={regions}
          corridors={corridors}
          metricId={metricId}
          mode={viewMode === "delta" ? "delta" : "single"}
        />
      )}

      {viewMode === "delta" && regionsState === "ready" && (
        <p className="text-xs text-zinc-600">
          Comparing {yearOf(caseNameA) ?? caseNameA} → {yearOf(caseNameB) ?? caseNameB}.
        </p>
      )}
    </div>
  );
}
