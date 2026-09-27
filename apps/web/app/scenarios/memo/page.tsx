"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getCandidateInvestmentAnalysis, getPortfolioAnalysis } from "../../../lib/candidateInvestment/candidateInvestment.api";
import type {
  CandidateInvestmentAnalysis,
  PortfolioAnalysisResponse,
} from "../../../lib/candidateInvestment/candidateInvestment.types";
import { apiUrl } from "../../../lib/config";
import { getScenarioList } from "../../../lib/pypsaScenario/pypsaScenario.api";
import type { ScenarioListItem } from "../../../lib/pypsaScenario/pypsaScenario.types";

// A dedicated, print-styled page rather than a modal -- opened in a new tab
// via a plain <a target="_blank">, so print CSS never has to fight the rest
// of the app's (dark, interactive) layout. Independently re-fetches
// everything it needs from window.location.search, since a new tab shares
// no React state with whichever panel opened it.

type MemoType = "candidate" | "portfolio" | "compare";
type LoadState = "loading" | "ready" | "error";

type CandidateMemoData = {
  analysis: CandidateInvestmentAnalysis;
  name: string;
  caseName: string;
  targetYear: number;
  assumptions: Record<string, string>;
};

function formatEur(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return `€${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatMw(value: number | null): string {
  return value === null ? "—" : `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} MW`;
}

function DisclaimerFooter({ hasAssumptions = false }: { hasAssumptions?: boolean }) {
  return (
    <p className="mt-10 border-t border-zinc-300 pt-4 text-[11px] leading-5 text-zinc-500">
      Generated from real solved PyPSA scenario results
      {hasAssumptions ? ", combined with the named external estimates stated above" : ""} -- for internal
      evaluation purposes, not investment advice.
    </p>
  );
}

function AssumptionsSection({ assumptions }: { assumptions: Record<string, string> }) {
  return (
    <div className="mt-8">
      <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Assumptions &amp; Caveats</h2>
      <ul className="mt-2 list-disc space-y-2 pl-5 text-xs leading-5 text-zinc-700">
        {Object.values(assumptions).map((note, index) => (
          <li key={index}>{note}</li>
        ))}
      </ul>
    </div>
  );
}

function MemoHeader({
  title,
  generatedAt,
  subtitle,
}: {
  title: string;
  generatedAt: Date;
  subtitle: string;
}) {
  return (
    <div className="border-b border-zinc-300 pb-4">
      <p className="text-[11px] uppercase tracking-[0.2em] text-zinc-500">Investment Memo</p>
      <h1 className="mt-1 text-2xl font-semibold text-zinc-900">{title}</h1>
      <p className="mt-2 text-xs text-zinc-500">
        Generated {generatedAt.toLocaleString()} · {subtitle}
      </p>
    </div>
  );
}

function CandidateMemo({ data, generatedAt }: { data: CandidateMemoData; generatedAt: Date }) {
  const { analysis, name } = data;
  return (
    <div>
      <MemoHeader
        title={name}
        generatedAt={generatedAt}
        subtitle={`${data.caseName} (${data.targetYear}) · ${analysis.technology}${analysis.region_id ? ` · ${analysis.region_id}` : ""}`}
      />

      {analysis.message ? (
        <p className="mt-6 text-sm text-red-700">{analysis.message}</p>
      ) : (
        <table className="mt-6 w-full text-left text-sm">
          <tbody>
            {[
              ["Assumed capacity", formatMw(analysis.assumed_capacity_mw)],
              ["Capital expenditure (CAPEX)", formatEur(analysis.capex_eur)],
              [
                "Annual generation (year 1)",
                analysis.annual_generation_year0_mwh !== null
                  ? `${analysis.annual_generation_year0_mwh.toLocaleString(undefined, { maximumFractionDigits: 0 })} MWh`
                  : "—",
              ],
              [
                "Captured price",
                analysis.captured_price_eur_per_mwh !== null ? `€${analysis.captured_price_eur_per_mwh.toFixed(1)}/MWh` : "—",
              ],
              ["LCOE", analysis.lcoe_eur_per_mwh !== null ? `€${analysis.lcoe_eur_per_mwh.toFixed(1)}/MWh` : "—"],
              ["Net present value (NPV)", formatEur(analysis.npv_eur)],
              ["Internal rate of return (IRR)", analysis.irr_pct !== null ? `${analysis.irr_pct.toFixed(1)}%` : "n/a"],
              ["Payback period", analysis.payback_years !== null ? `${analysis.payback_years.toFixed(1)} years` : "—"],
            ].map(([label, value]) => (
              <tr key={label} className="border-b border-zinc-200">
                <td className="py-2 pr-4 font-medium text-zinc-600">{label}</td>
                <td className="py-2 font-mono text-zinc-900">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <AssumptionsSection assumptions={data.assumptions} />
      <DisclaimerFooter hasAssumptions />
    </div>
  );
}

function PortfolioMemo({ response, generatedAt }: { response: PortfolioAnalysisResponse; generatedAt: Date }) {
  const excluded = response.candidates.filter((candidate) => candidate.message !== null);

  return (
    <div>
      <MemoHeader
        title={`Portfolio of ${response.included_count} candidate${response.included_count === 1 ? "" : "s"}`}
        generatedAt={generatedAt}
        subtitle={`${response.case_name} (${response.target_year})`}
      />

      <table className="mt-6 w-full text-left text-sm">
        <tbody>
          {[
            ["Total assumed capacity", formatMw(response.total_assumed_capacity_mw)],
            ["Total CAPEX", formatEur(response.total_capex_eur)],
            ["Total NPV", formatEur(response.total_npv_eur)],
            ["Portfolio IRR", response.portfolio_irr_pct !== null ? `${response.portfolio_irr_pct.toFixed(1)}%` : "n/a"],
            [
              "Portfolio payback period",
              response.portfolio_payback_years !== null ? `${response.portfolio_payback_years.toFixed(1)} years` : "—",
            ],
          ].map(([label, value]) => (
            <tr key={label} className="border-b border-zinc-200">
              <td className="py-2 pr-4 font-medium text-zinc-600">{label}</td>
              <td className="py-2 font-mono text-zinc-900">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-8 grid grid-cols-2 gap-8">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">By Technology</h2>
          <table className="mt-2 w-full text-left text-xs">
            <thead className="text-zinc-500">
              <tr>
                <th className="py-1 font-medium">Technology</th>
                <th className="py-1 font-medium">CAPEX</th>
                <th className="py-1 font-medium">Share</th>
              </tr>
            </thead>
            <tbody>
              {response.technology_breakdown.map((entry) => (
                <tr key={entry.label} className="border-t border-zinc-200">
                  <td className="py-1">{entry.label}</td>
                  <td className="py-1 font-mono">{formatEur(entry.capex_eur)}</td>
                  <td className="py-1 font-mono">{entry.capex_share_pct.toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">By Region</h2>
          <table className="mt-2 w-full text-left text-xs">
            <thead className="text-zinc-500">
              <tr>
                <th className="py-1 font-medium">Region</th>
                <th className="py-1 font-medium">CAPEX</th>
                <th className="py-1 font-medium">Share</th>
              </tr>
            </thead>
            <tbody>
              {response.region_breakdown.map((entry) => (
                <tr key={entry.label} className="border-t border-zinc-200">
                  <td className="py-1">{entry.label}</td>
                  <td className="py-1 font-mono">{formatEur(entry.capex_eur)}</td>
                  <td className="py-1 font-mono">{entry.capex_share_pct.toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {response.concentration_flags.length > 0 && (
        <ul className="mt-6 list-disc space-y-1 pl-5 text-xs text-amber-700">
          {response.concentration_flags.map((flag, index) => (
            <li key={index}>{flag}</li>
          ))}
        </ul>
      )}

      <div className="mt-8">
        <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Candidates</h2>
        <table className="mt-2 w-full text-left text-xs">
          <thead className="text-zinc-500">
            <tr>
              <th className="py-1 pr-3 font-medium">ID</th>
              <th className="py-1 pr-3 font-medium">Technology</th>
              <th className="py-1 pr-3 font-medium">Region</th>
              <th className="py-1 pr-3 font-medium">CAPEX</th>
              <th className="py-1 pr-3 font-medium">NPV</th>
              <th className="py-1 pr-3 font-medium">IRR</th>
              <th className="py-1 font-medium">Notes</th>
            </tr>
          </thead>
          <tbody>
            {response.candidates.map((candidate) => (
              <tr key={candidate.candidate_id} className="border-t border-zinc-200">
                <td className="py-1 pr-3 font-mono">{candidate.candidate_id}</td>
                <td className="py-1 pr-3">{candidate.technology}</td>
                <td className="py-1 pr-3">{candidate.region_id ?? "—"}</td>
                <td className="py-1 pr-3 font-mono">{formatEur(candidate.capex_eur)}</td>
                <td className="py-1 pr-3 font-mono">{formatEur(candidate.npv_eur)}</td>
                <td className="py-1 pr-3 font-mono">{candidate.irr_pct !== null ? `${candidate.irr_pct.toFixed(1)}%` : "—"}</td>
                <td className="py-1 text-zinc-500">{candidate.message ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {excluded.length > 0 && (
        <p className="mt-3 text-[11px] text-zinc-500">
          {excluded.length} candidate{excluded.length === 1 ? "" : "s"} excluded from the totals above (see Notes).
        </p>
      )}

      <AssumptionsSection assumptions={response.assumptions} />
      <DisclaimerFooter hasAssumptions />
    </div>
  );
}

function CompareMemo({ scenarios, generatedAt }: { scenarios: ScenarioListItem[]; generatedAt: Date }) {
  const hasCoupled = scenarios.some((scenario) => scenario.coupled_objective_eur_per_year !== null);

  return (
    <div>
      <MemoHeader
        title="Scenario Comparison"
        generatedAt={generatedAt}
        subtitle={`${scenarios.length} solved scenario${scenarios.length === 1 ? "" : "s"}`}
      />

      <table className="mt-6 w-full text-left text-xs">
        <thead className="text-zinc-500">
          <tr>
            <th className="py-1 pr-3 font-medium">Year</th>
            <th className="py-1 pr-3 font-medium">Case</th>
            <th className="py-1 pr-3 font-medium">Objective (€/yr)</th>
            {hasCoupled && (
              <>
                <th className="py-1 pr-3 font-medium">Coupled objective (€/yr)</th>
                <th className="py-1 pr-3 font-medium">Heat demand (TWh)</th>
                <th className="py-1 font-medium">Electrolysis (GWh)</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {scenarios.map((scenario) => (
            <tr key={scenario.case_name} className="border-t border-zinc-200">
              <td className="py-1 pr-3">{scenario.target_year}</td>
              <td className="py-1 pr-3 font-mono">{scenario.case_name}</td>
              <td className="py-1 pr-3 font-mono">
                {scenario.objective_eur?.toLocaleString(undefined, { maximumFractionDigits: 0 }) ?? "—"}
              </td>
              {hasCoupled && (
                <>
                  <td className="py-1 pr-3 font-mono">
                    {scenario.coupled_objective_eur_per_year?.toLocaleString(undefined, { maximumFractionDigits: 0 }) ?? "—"}
                  </td>
                  <td className="py-1 pr-3 font-mono">{scenario.coupled_annual_heat_twh?.toFixed(1) ?? "—"}</td>
                  <td className="py-1 font-mono">
                    {scenario.coupled_h2_electrolysis_output_mwh !== null
                      ? (scenario.coupled_h2_electrolysis_output_mwh / 1000).toLocaleString(undefined, {
                          maximumFractionDigits: 0,
                        })
                      : "—"}
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-8">
        <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Generation Mix (GWh/yr)</h2>
        <table className="mt-2 w-full text-left text-xs">
          <thead className="text-zinc-500">
            <tr>
              <th className="py-1 pr-3 font-medium">Year</th>
              {Array.from(new Set(scenarios.flatMap((s) => Object.keys(s.generation_by_carrier_mwh)))).map((carrier) => (
                <th key={carrier} className="py-1 pr-3 font-medium capitalize">
                  {carrier}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {scenarios.map((scenario) => (
              <tr key={scenario.case_name} className="border-t border-zinc-200">
                <td className="py-1 pr-3">{scenario.target_year}</td>
                {Array.from(new Set(scenarios.flatMap((s) => Object.keys(s.generation_by_carrier_mwh)))).map((carrier) => (
                  <td key={carrier} className="py-1 pr-3 font-mono">
                    {((scenario.generation_by_carrier_mwh[carrier] ?? 0) / 1000).toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <DisclaimerFooter />
    </div>
  );
}

export default function InvestmentMemoPage() {
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [memoType, setMemoType] = useState<MemoType | null>(null);
  const [generatedAt, setGeneratedAt] = useState<Date | null>(null);

  const [candidateData, setCandidateData] = useState<CandidateMemoData | null>(null);
  const [portfolioData, setPortfolioData] = useState<PortfolioAnalysisResponse | null>(null);
  const [compareData, setCompareData] = useState<ScenarioListItem[] | null>(null);

  useEffect(() => {
    async function load() {
      const params = new URLSearchParams(window.location.search);
      const type = params.get("type");
      const caseName = params.get("case_name");

      try {
        if (type === "candidate") {
          const id = params.get("id");
          if (!caseName || !id) {
            throw new Error("Missing case_name or id in the memo link.");
          }
          const [analysisResponse, candidatesResponse] = await Promise.all([
            getCandidateInvestmentAnalysis(caseName),
            fetch(apiUrl("/candidates")),
          ]);
          const analysis = analysisResponse.analyses.find((candidate) => candidate.candidate_id === id);
          if (!analysis) {
            throw new Error(`Candidate '${id}' was not found in '${caseName}''s analysis.`);
          }
          const candidatesGeojson = (await candidatesResponse.json()) as GeoJSON.FeatureCollection;
          const feature = candidatesGeojson.features.find((f) => String(f.properties?.id ?? "") === id);
          setCandidateData({
            analysis,
            name: String(feature?.properties?.name ?? id),
            caseName,
            targetYear: analysisResponse.target_year,
            assumptions: analysisResponse.assumptions,
          });
          setMemoType("candidate");
        } else if (type === "portfolio") {
          const ids = (params.get("ids") ?? "").split(",").filter(Boolean);
          if (!caseName || ids.length === 0) {
            throw new Error("Missing case_name or ids in the memo link.");
          }
          setPortfolioData(await getPortfolioAnalysis(caseName, ids));
          setMemoType("portfolio");
        } else if (type === "compare") {
          const response = await getScenarioList();
          setCompareData(response.scenarios.filter((scenario) => scenario.state === "done" && scenario.solved));
          setMemoType("compare");
        } else {
          throw new Error("This memo link is missing a valid 'type' (candidate, portfolio, or compare).");
        }
        setGeneratedAt(new Date());
        setLoadState("ready");
      } catch (error) {
        setLoadState("error");
        setErrorMessage(error instanceof Error ? error.message : "Unable to load this memo.");
      }
    }

    void load();
  }, []);

  return (
    <main className="min-h-screen bg-white px-8 py-10 text-zinc-900 print:px-0 print:py-6">
      <div className="mb-6 flex items-center justify-between print:hidden">
        <Link href="/scenarios" className="text-sm text-zinc-600 hover:text-zinc-900">
          ← Back to Scenario Studio
        </Link>
        {loadState === "ready" && (
          <button
            type="button"
            onClick={() => window.print()}
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-700"
          >
            Print / Save as PDF
          </button>
        )}
      </div>

      <div className="mx-auto max-w-3xl">
        {loadState === "loading" && <p className="text-sm text-zinc-500">Loading memo...</p>}
        {loadState === "error" && <p className="text-sm text-red-700">{errorMessage}</p>}
        {loadState === "ready" && generatedAt && memoType === "candidate" && candidateData && (
          <CandidateMemo data={candidateData} generatedAt={generatedAt} />
        )}
        {loadState === "ready" && generatedAt && memoType === "portfolio" && portfolioData && (
          <PortfolioMemo response={portfolioData} generatedAt={generatedAt} />
        )}
        {loadState === "ready" && generatedAt && memoType === "compare" && compareData && (
          <CompareMemo scenarios={compareData} generatedAt={generatedAt} />
        )}
      </div>
    </main>
  );
}
