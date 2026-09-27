"use client";

import { useEffect, useRef, useState } from "react";

import { getCandidateInvestmentAnalysis, getPortfolioAnalysis } from "../lib/candidateInvestment/candidateInvestment.api";
import type {
  CandidateInvestmentAnalysis,
  CandidateInvestmentAnalysisResponse,
  PortfolioAnalysisResponse,
} from "../lib/candidateInvestment/candidateInvestment.types";
import { apiUrl } from "../lib/config";
import { getScenarioList } from "../lib/pypsaScenario/pypsaScenario.api";
import type { ScenarioListItem } from "../lib/pypsaScenario/pypsaScenario.types";
import { matchesCandidateScenario } from "../lib/scenario/candidate-screening";
import type { Scenario } from "../lib/scenario/scenario.types";
import type { AssetSelection } from "../types/asset";
import PortfolioSummary from "./PortfolioSummary";

type CandidateInvestmentPanelProps = {
  scenario: Scenario;
};

type ScenariosState = "loading" | "ready" | "error";
type AnalysisState = "idle" | "loading" | "ready" | "error";

const CANDIDATES_API_URL = apiUrl("/candidates");
const PORTFOLIO_STORAGE_KEY = "energy-investment-platform-candidate-portfolio";

type RankedCandidate = CandidateInvestmentAnalysis & { name: string };

function toCandidateAsset(feature: GeoJSON.Feature): AssetSelection {
  const properties = (feature.properties ?? {}) as AssetSelection["properties"];
  return {
    id: String(properties.id ?? ""),
    name: String(properties.name ?? properties.id ?? ""),
    assetType: "cell",
    properties,
    feature,
  };
}

function formatEur(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return `€${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatMw(value: number | null): string {
  return value === null ? "—" : `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} MW`;
}

export default function CandidateInvestmentPanel({ scenario }: CandidateInvestmentPanelProps) {
  const [scenarios, setScenarios] = useState<ScenarioListItem[]>([]);
  const [scenariosState, setScenariosState] = useState<ScenariosState>("loading");
  const [selectedCaseName, setSelectedCaseName] = useState<string | null>(null);

  const [candidateAssets, setCandidateAssets] = useState<AssetSelection[]>([]);
  const [candidatesState, setCandidatesState] = useState<ScenariosState>("loading");

  const [analysisResponse, setAnalysisResponse] = useState<CandidateInvestmentAnalysisResponse | null>(null);
  const [analysisState, setAnalysisState] = useState<AnalysisState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [portfolioIds, setPortfolioIds] = useState<string[]>([]);
  const [portfolioResponse, setPortfolioResponse] = useState<PortfolioAnalysisResponse | null>(null);
  const [portfolioState, setPortfolioState] = useState<AnalysisState>("idle");
  const [portfolioErrorMessage, setPortfolioErrorMessage] = useState<string | null>(null);
  // Guards the persistence effect below from firing (with the initial []
  // state) before the load effect has had a chance to read localStorage --
  // without this, the save effect would immediately overwrite a real saved
  // portfolio with an empty array on every mount.
  const hasLoadedPortfolioRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    async function loadScenarios() {
      try {
        const response = await getScenarioList();
        if (cancelled) {
          return;
        }
        const solved = response.scenarios.filter((item) => item.state === "done" && item.solved);
        setScenarios(solved);
        setScenariosState("ready");
        setSelectedCaseName((current) => current ?? solved[0]?.case_name ?? null);
      } catch {
        if (!cancelled) {
          setScenariosState("error");
        }
      }
    }

    async function loadCandidates() {
      try {
        const response = await fetch(CANDIDATES_API_URL);
        if (!response.ok) {
          throw new Error(`status ${response.status}`);
        }
        const geojson = (await response.json()) as GeoJSON.FeatureCollection;
        if (cancelled) {
          return;
        }
        setCandidateAssets(geojson.features.map(toCandidateAsset));
        setCandidatesState("ready");
      } catch {
        if (!cancelled) {
          setCandidatesState("error");
        }
      }
    }

    void loadScenarios();
    void loadCandidates();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedCaseName) {
      return;
    }
    let cancelled = false;
    setAnalysisState("loading");
    setErrorMessage(null);

    getCandidateInvestmentAnalysis(selectedCaseName)
      .then((response) => {
        if (cancelled) {
          return;
        }
        setAnalysisResponse(response);
        setAnalysisState("ready");
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        setAnalysisState("error");
        setErrorMessage(error instanceof Error ? error.message : "Unable to load candidate investment analysis.");
      });

    return () => {
      cancelled = true;
    };
  }, [selectedCaseName]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(PORTFOLIO_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          setPortfolioIds(parsed);
        }
      }
    } catch {
      // Malformed or inaccessible storage -- start with an empty portfolio.
    } finally {
      hasLoadedPortfolioRef.current = true;
    }
  }, []);

  useEffect(() => {
    if (!hasLoadedPortfolioRef.current) {
      return;
    }
    try {
      window.localStorage.setItem(PORTFOLIO_STORAGE_KEY, JSON.stringify(portfolioIds));
    } catch {
      // Private browsing / storage quota -- the portfolio just won't survive a reload.
    }
  }, [portfolioIds]);

  useEffect(() => {
    if (!selectedCaseName || portfolioIds.length === 0) {
      setPortfolioResponse(null);
      setPortfolioState("idle");
      return;
    }
    let cancelled = false;
    setPortfolioState("loading");
    setPortfolioErrorMessage(null);

    getPortfolioAnalysis(selectedCaseName, portfolioIds)
      .then((response) => {
        if (cancelled) {
          return;
        }
        setPortfolioResponse(response);
        setPortfolioState("ready");
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        setPortfolioState("error");
        setPortfolioErrorMessage(error instanceof Error ? error.message : "Unable to compute portfolio analysis.");
      });

    return () => {
      cancelled = true;
    };
  }, [selectedCaseName, portfolioIds]);

  function togglePortfolioMembership(candidateId: string) {
    setPortfolioIds((current) =>
      current.includes(candidateId) ? current.filter((id) => id !== candidateId) : [...current, candidateId],
    );
  }

  const eligibleIds = new Set(
    candidateAssets.filter((asset) => matchesCandidateScenario(asset, scenario)).map((asset) => asset.id),
  );
  const namesById = new Map(candidateAssets.map((asset) => [asset.id, asset.name]));

  const eligibleAnalyses: RankedCandidate[] = (analysisResponse?.analyses ?? [])
    .filter((analysis) => eligibleIds.has(analysis.candidate_id) && analysis.message === null)
    .map((analysis) => ({ ...analysis, name: namesById.get(analysis.candidate_id) ?? analysis.candidate_id }));

  // Ranked by IRR first (the standard "which investment is best" figure);
  // a case where the IRR bisection couldn't bracket a root (irr.ts's irr()
  // returns None for a never-profitable cash flow) falls back to NPV, but
  // always after every candidate that does have a real IRR.
  const byIrr = eligibleAnalyses
    .filter((candidate) => candidate.irr_pct !== null)
    .sort((a, b) => (b.irr_pct as number) - (a.irr_pct as number));
  const byNpvOnly = eligibleAnalyses
    .filter((candidate) => candidate.irr_pct === null && candidate.npv_eur !== null)
    .sort((a, b) => (b.npv_eur as number) - (a.npv_eur as number));
  const top10 = [...byIrr, ...byNpvOnly].slice(0, 10);
  // A candidate already in the portfolio stays visible (with its toggle
  // button) even if it later falls out of the top 10 -- so adding it never
  // makes it seem to vanish.
  const top10Ids = new Set(top10.map((candidate) => candidate.candidate_id));
  const alsoInPortfolio = eligibleAnalyses.filter(
    (candidate) => portfolioIds.includes(candidate.candidate_id) && !top10Ids.has(candidate.candidate_id),
  );
  const rankedCandidates = [...top10, ...alsoInPortfolio];

  return (
    <section className="mt-8 rounded-xl border border-white/10 bg-white/5 p-4">
      <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
        Real Investment Economics
      </h3>
      <p className="mt-2 text-xs text-zinc-500">
        Ranks the current scenario&rsquo;s eligible candidates by projected IRR, grounded in a real
        solved PyPSA scenario&rsquo;s regional prices and capacity factors -- not the heuristic score above.
      </p>

      <div className="mt-4">
        <label htmlFor="candidate-investment-case" className="text-sm font-medium text-zinc-100">
          Solved scenario to analyze against
        </label>
        <select
          id="candidate-investment-case"
          value={selectedCaseName ?? ""}
          onChange={(event) => setSelectedCaseName(event.target.value || null)}
          disabled={scenariosState === "loading"}
          className="mt-3 w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-3 text-sm text-zinc-100 outline-none focus:border-emerald-400 disabled:opacity-50"
        >
          {scenariosState === "loading" && <option>Loading solved scenarios...</option>}
          {scenariosState === "ready" && scenarios.length === 0 && <option value="">No solved scenarios yet</option>}
          {scenarios.map((item) => (
            <option key={item.case_name} value={item.case_name}>
              {item.target_year} — {item.case_name}
            </option>
          ))}
        </select>
        {scenariosState === "error" && (
          <p className="mt-2 text-xs text-amber-300">Could not load the solved-scenario list from the backend.</p>
        )}
        {candidatesState === "error" && (
          <p className="mt-2 text-xs text-amber-300">Could not load candidate cells from the backend.</p>
        )}
      </div>

      {analysisState === "loading" && (
        <p className="mt-4 text-xs text-zinc-400">Computing real investment economics...</p>
      )}

      {analysisState === "error" && (
        <div className="mt-4 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-3">
          <p className="text-sm text-rose-300">{errorMessage}</p>
        </div>
      )}

      {analysisResponse && analysisState === "ready" && (
        <div className="mt-4 space-y-3">
          {rankedCandidates.length === 0 ? (
            <p className="text-xs text-zinc-500">
              No eligible candidate has a complete real-economics result for this scenario -- try loosening the
              current screening thresholds.
            </p>
          ) : (
            rankedCandidates.map((candidate) => (
              <div key={candidate.candidate_id} className="rounded-lg border border-white/10 bg-zinc-950/90 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-zinc-100">{candidate.name}</p>
                    <p className="mt-1 text-xs text-zinc-400">
                      {candidate.technology} · {candidate.region_id ?? "unknown region"}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-zinc-400">IRR</p>
                    <p className="text-sm font-semibold text-emerald-300">
                      {candidate.irr_pct !== null ? `${candidate.irr_pct.toFixed(1)}%` : "n/a"}
                    </p>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-zinc-400 sm:grid-cols-3">
                  <p>Capacity: {formatMw(candidate.assumed_capacity_mw)}</p>
                  <p>CAPEX: {formatEur(candidate.capex_eur)}</p>
                  <p>NPV: {formatEur(candidate.npv_eur)}</p>
                  <p>LCOE: {candidate.lcoe_eur_per_mwh !== null ? `€${candidate.lcoe_eur_per_mwh.toFixed(1)}/MWh` : "—"}</p>
                  <p>
                    Payback: {candidate.payback_years !== null ? `${candidate.payback_years.toFixed(1)} yr` : "—"}
                  </p>
                  <p>
                    Captured price:{" "}
                    {candidate.captured_price_eur_per_mwh !== null
                      ? `€${candidate.captured_price_eur_per_mwh.toFixed(1)}/MWh`
                      : "—"}
                  </p>
                </div>
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    onClick={() => togglePortfolioMembership(candidate.candidate_id)}
                    className={`flex-1 rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                      portfolioIds.includes(candidate.candidate_id)
                        ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20"
                        : "border-white/10 bg-zinc-950 text-zinc-300 hover:bg-zinc-900"
                    }`}
                  >
                    {portfolioIds.includes(candidate.candidate_id) ? "✓ In portfolio — remove" : "Add to portfolio"}
                  </button>
                  {selectedCaseName && (
                    <a
                      href={`/scenarios/memo?type=candidate&case_name=${encodeURIComponent(selectedCaseName)}&id=${encodeURIComponent(candidate.candidate_id)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1 rounded-lg border border-white/10 bg-zinc-950 px-3 py-1.5 text-center text-xs font-medium text-zinc-300 transition hover:bg-zinc-900"
                    >
                      Export memo
                    </a>
                  )}
                </div>
              </div>
            ))
          )}

          {portfolioIds.length > 0 && (
            <div>
              {portfolioState === "loading" && (
                <p className="text-xs text-zinc-400">Computing portfolio economics...</p>
              )}
              {portfolioState === "error" && (
                <div className="rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-3">
                  <p className="text-sm text-rose-300">{portfolioErrorMessage}</p>
                </div>
              )}
              {portfolioResponse && portfolioState === "ready" && (
                <PortfolioSummary response={portfolioResponse} onClear={() => setPortfolioIds([])} />
              )}
            </div>
          )}

          <div className="rounded-lg border border-white/10 bg-white/5 p-3 text-[11px] leading-5 text-zinc-500">
            <p className="font-semibold uppercase tracking-[0.2em] text-zinc-600">Assumptions</p>
            {Object.values(analysisResponse.assumptions).map((note, index) => (
              <p key={index} className="mt-1">
                {note}
              </p>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
