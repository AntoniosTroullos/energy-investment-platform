"use client";

import { ArrowLeftRight } from "lucide-react";

import type { AssetSimulation } from "../../lib/simulation/simulation.types";
import { formatEur, formatPct } from "./SimulationControls";

// The same battery, same physics, in the other market. Shown side by side
// because the gap is usually larger than anything in the battery's own spec --
// a unit that looks uninvestable on day-ahead prices can be strongly
// investable on the prices it is really settled at, and the reverse of that
// claim is what a day-ahead-only tool quietly tells you.

const BASIS_LABEL = {
  day_ahead: "Day-ahead",
  balancing: "Settled balancing",
} as const;

export default function SettlementComparisonCard({ result }: { result: AssetSimulation }) {
  const other = result.comparison;
  if (!other) return null;

  const npv = result.npv_eur ?? 0;
  const otherNpv = other.npv_eur ?? 0;
  const better = npv >= otherNpv;

  return (
    <div className="flex flex-col gap-2.5">
      <div className="grid grid-cols-2 gap-2">
        <BasisColumn
          label={BASIS_LABEL[result.settlement] ?? result.settlement}
          window={result.price_window}
          meanPrice={result.price_summary?.mean_eur_per_mwh ?? null}
          negativeHours={result.price_summary?.negative_hours ?? null}
          npv={result.npv_eur}
          irr={result.irr_pct}
          margin={result.storage_years[0]?.gross_margin_eur ?? null}
          selected
          winning={better}
        />
        <BasisColumn
          label={BASIS_LABEL[other.settlement] ?? other.settlement}
          window={other.price_window}
          meanPrice={other.mean_price_eur_per_mwh}
          negativeHours={other.negative_hours}
          npv={other.npv_eur}
          irr={other.irr_pct}
          margin={other.first_year_margin_eur}
          selected={false}
          winning={!better}
        />
      </div>

      <p className="flex items-start gap-2 text-[10px] leading-4 text-zinc-500">
        <ArrowLeftRight className="mt-0.5 h-3 w-3 shrink-0 text-zinc-600" aria-hidden="true" />
        <span>
          Identical physics and spec on both sides — only the price series differs. In Greece the
          balancing market does the physical dispatch, so it is the basis a storage case should be
          argued on; day-ahead is the right basis for a purely financial arbitrage strategy.
        </span>
      </p>
    </div>
  );
}

function BasisColumn({
  label,
  window: priceWindow,
  meanPrice,
  negativeHours,
  npv,
  irr,
  margin,
  selected,
  winning,
}: {
  label: string;
  window: string;
  meanPrice: number | null;
  negativeHours: number | null;
  npv: number | null;
  irr: number | null;
  margin: number | null;
  selected: boolean;
  winning: boolean;
}) {
  const positive = (npv ?? 0) > 0;
  return (
    <div
      className={`flex min-w-0 flex-col gap-1 rounded-xl px-3 py-2.5 ring-1 ring-inset ${
        selected ? "bg-emerald-500/5 ring-emerald-500/30" : "bg-white/[0.02] ring-white/10"
      }`}
    >
      <div className="flex items-center gap-1.5">
        <p className="truncate text-[10px] uppercase tracking-[0.14em] text-zinc-500">{label}</p>
        {selected ? (
          <span className="shrink-0 rounded bg-emerald-500/15 px-1 text-[9px] text-emerald-300">shown</span>
        ) : null}
      </div>
      <p
        className={`font-display text-xl font-semibold tracking-tight ${
          positive ? "text-emerald-300" : "text-rose-300"
        }`}
      >
        {formatEur(npv)}
        <span className="ml-1 text-[10px] font-normal text-zinc-500">NPV</span>
      </p>
      <p className="text-[11px] text-zinc-400">
        IRR <span className="font-mono text-zinc-200">{formatPct(irr)}</span>
        {winning ? <span className="ml-1 text-emerald-400">▲</span> : null}
      </p>
      <p className="truncate text-[10px] text-zinc-500">
        year 1 margin {formatEur(margin)}
      </p>
      <p className="truncate text-[10px] text-zinc-500">
        €{meanPrice?.toFixed(2) ?? "—"} mean · {negativeHours ?? "—"} h below zero
      </p>
      <p className="truncate text-[10px] text-zinc-600" title={priceWindow}>
        {priceWindow}
      </p>
    </div>
  );
}
