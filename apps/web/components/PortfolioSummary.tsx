"use client";

import type { PortfolioAnalysisResponse, PortfolioBreakdownEntry } from "../lib/candidateInvestment/candidateInvestment.types";

type PortfolioSummaryProps = {
  response: PortfolioAnalysisResponse;
  onClear: () => void;
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

function BreakdownBar({ entry }: { entry: PortfolioBreakdownEntry }) {
  return (
    <div>
      <div className="flex items-center justify-between text-xs text-zinc-300">
        <span>
          {entry.label} <span className="text-zinc-500">({entry.candidate_count})</span>
        </span>
        <span className="font-mono text-zinc-400">{entry.capex_share_pct.toFixed(0)}%</span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-white/5">
        <div
          className="h-full rounded-full bg-emerald-500/60"
          style={{ width: `${Math.min(100, Math.max(0, entry.capex_share_pct))}%` }}
        />
      </div>
    </div>
  );
}

export default function PortfolioSummary({ response, onClear }: PortfolioSummaryProps) {
  const excluded = response.candidates.filter((candidate) => candidate.message !== null);

  return (
    <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300">
            Portfolio ({response.included_count} candidate{response.included_count === 1 ? "" : "s"})
          </p>
          <p className="mt-1 text-[11px] text-zinc-500">
            Against {response.case_name} ({response.target_year})
            {response.excluded_count > 0 && ` · ${response.excluded_count} excluded`}
          </p>
        </div>
        <button
          type="button"
          onClick={onClear}
          className="shrink-0 rounded-lg border border-white/10 bg-zinc-950 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-900"
        >
          Clear portfolio
        </button>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-white/10 bg-zinc-950/90 p-3">
          <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Total Capacity</p>
          <p className="mt-1 text-sm text-zinc-100">{formatMw(response.total_assumed_capacity_mw)}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-zinc-950/90 p-3">
          <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Total CAPEX</p>
          <p className="mt-1 text-sm text-zinc-100">{formatEur(response.total_capex_eur)}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-zinc-950/90 p-3">
          <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Total NPV</p>
          <p className="mt-1 text-sm text-zinc-100">{formatEur(response.total_npv_eur)}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-zinc-950/90 p-3">
          <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Portfolio IRR</p>
          <p className="mt-1 text-sm font-semibold text-emerald-300">
            {response.portfolio_irr_pct !== null ? `${response.portfolio_irr_pct.toFixed(1)}%` : "n/a"}
          </p>
        </div>
        <div className="rounded-lg border border-white/10 bg-zinc-950/90 p-3">
          <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Payback</p>
          <p className="mt-1 text-sm text-zinc-100">
            {response.portfolio_payback_years !== null ? `${response.portfolio_payback_years.toFixed(1)} yr` : "—"}
          </p>
        </div>
      </div>

      {response.technology_breakdown.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">By Technology</p>
          {response.technology_breakdown.map((entry) => (
            <BreakdownBar key={entry.label} entry={entry} />
          ))}
        </div>
      )}

      {response.region_breakdown.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">By Region</p>
          {response.region_breakdown.map((entry) => (
            <BreakdownBar key={entry.label} entry={entry} />
          ))}
        </div>
      )}

      {response.concentration_flags.length > 0 && (
        <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
          {response.concentration_flags.map((flag, index) => (
            <p key={index} className="text-xs text-amber-200">
              {flag}
            </p>
          ))}
        </div>
      )}

      {excluded.length > 0 && (
        <div className="mt-4 rounded-lg border border-white/10 bg-white/5 p-3">
          <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Excluded from portfolio</p>
          {excluded.map((candidate) => (
            <p key={candidate.candidate_id} className="mt-1 text-xs text-zinc-400">
              {candidate.candidate_id}: {candidate.message}
            </p>
          ))}
        </div>
      )}

      <div className="mt-4 rounded-lg border border-white/10 bg-white/5 p-3 text-[11px] leading-5 text-zinc-500">
        <p className="font-semibold uppercase tracking-[0.2em] text-zinc-600">Assumptions</p>
        {Object.values(response.assumptions).map((note, index) => (
          <p key={index} className="mt-1">
            {note}
          </p>
        ))}
      </div>
    </div>
  );
}
