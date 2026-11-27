"use client";

import { ArrowRight } from "lucide-react";

import { eurPerMwh, utcDate } from "../../lib/liveMarket/liveMarket.api";
import type { BalancingYearSummary, DayAheadComparison } from "../../lib/liveMarket/liveMarket.types";
import DashboardCard from "../overview/DashboardCard";

// The finding the whole live-market layer exists to show. Day-ahead and
// balancing are not two views of one price: the negative-hour counts differ by
// an order of magnitude, and in Greece it is the balancing market that
// physically dispatches storage. A battery valued on day-ahead alone is valued
// in a market it does not operate in.

type BalancingVsDayAheadPanelProps = {
  comparison: DayAheadComparison;
  trailingYear: BalancingYearSummary | null;
};

export default function BalancingVsDayAheadPanel({
  comparison,
  trailingYear,
}: BalancingVsDayAheadPanelProps) {
  const dayAheadNegative = comparison.day_ahead_negative_hours;
  const balancingNegative = comparison.balancing_negative_hours;
  const maxNegative = Math.max(dayAheadNegative ?? 0, balancingNegative ?? 0, 1);

  return (
    <DashboardCard
      title="Balancing against day-ahead"
      subtitle={
        trailingYear
          ? `Trailing year · ${utcDate(trailingYear.from_utc)} to ${utcDate(trailingYear.to_utc)} · ${
              trailingYear.files_used
            } settlement files`
          : undefined
      }
    >
      <div className="flex flex-col gap-3.5">
        <div className="grid gap-2 sm:grid-cols-2">
          <MarketColumn
            name={`Day-ahead ${comparison.day_ahead_year ?? ""}`.trim()}
            mean={comparison.day_ahead_mean_eur_per_mwh}
            negativeHours={dayAheadNegative}
            maxNegative={maxNegative}
            accent="sky"
            note="What a generator earns."
          />
          <MarketColumn
            name="Settled balancing"
            mean={comparison.balancing_mean_eur_per_mwh}
            negativeHours={balancingNegative}
            maxNegative={maxNegative}
            accent="emerald"
            note="What actually dispatches storage."
          />
        </div>

        {comparison.negative_hour_ratio ? (
          <p className="flex items-start gap-2 rounded-xl bg-emerald-500/5 px-3 py-2.5 text-[11px] leading-5 text-zinc-300 ring-1 ring-inset ring-emerald-500/20">
            <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" aria-hidden="true" />
            <span>
              Settled balancing had{" "}
              <strong className="font-semibold text-emerald-300">
                {comparison.negative_hour_ratio}×
              </strong>{" "}
              as many hours below zero as day-ahead. A battery is paid to charge in every one of them —
              which is why the same asset can be uninvestable on day-ahead prices and strongly
              investable on the prices it is really settled at.
            </span>
          </p>
        ) : null}

        {trailingYear ? (
          <dl className="grid grid-cols-2 gap-2 border-t border-white/5 pt-3 sm:grid-cols-4">
            <Figure label="Hours" value={`${trailingYear.hours.toLocaleString()}`} hint={
              trailingYear.missing_hours > 0 ? `${trailingYear.missing_hours} carried forward` : "complete"
            } />
            <Figure label="Median" value={eurPerMwh(trailingYear.median_eur_per_mwh)} />
            <Figure
              label="Range"
              value={`${eurPerMwh(trailingYear.min_eur_per_mwh, 0)} – ${eurPerMwh(
                trailingYear.max_eur_per_mwh,
                0,
              )}`}
            />
            <Figure
              label="Within-hour spread"
              value={eurPerMwh(trailingYear.mean_intra_hour_spread_eur_per_mwh)}
              hint="not captured by hourly simulation"
            />
          </dl>
        ) : null}

        {trailingYear ? (
          <p className="text-[11px] leading-5 text-zinc-500">
            The simulator averages the settled quarter-hours into hours, so the{" "}
            {eurPerMwh(trailingYear.mean_intra_hour_spread_eur_per_mwh)} of mean within-hour spread is
            revenue it cannot see. Its storage figures are conservative on that count.
          </p>
        ) : null}
      </div>
    </DashboardCard>
  );
}

function MarketColumn({
  name,
  mean,
  negativeHours,
  maxNegative,
  accent,
  note,
}: {
  name: string;
  mean: number | null;
  negativeHours: number | null;
  maxNegative: number;
  accent: "sky" | "emerald";
  note: string;
}) {
  const barClass = accent === "emerald" ? "bg-emerald-500/70" : "bg-sky-500/60";
  const textClass = accent === "emerald" ? "text-emerald-300" : "text-sky-300";
  const fraction = negativeHours === null ? 0 : negativeHours / maxNegative;

  return (
    <div className="flex min-w-0 flex-col gap-1.5 rounded-xl border border-white/10 bg-white/[0.02] px-3 py-2.5">
      <p className="truncate text-[10px] uppercase tracking-[0.14em] text-zinc-500">{name}</p>
      <p className={`font-display text-2xl font-semibold tracking-tight ${textClass}`}>
        {eurPerMwh(mean)}
        <span className="ml-1 text-[11px] font-normal text-zinc-500">/MWh mean</span>
      </p>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
        <div className={`h-full rounded-full ${barClass}`} style={{ width: `${fraction * 100}%` }} />
      </div>
      <p className="text-[11px] text-zinc-400">
        <span className="font-mono text-zinc-200">{negativeHours ?? "—"}</span> hours below zero
      </p>
      <p className="truncate text-[10px] text-zinc-500">{note}</p>
    </div>
  );
}

function Figure({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="min-w-0">
      <dt className="truncate text-[10px] uppercase tracking-[0.14em] text-zinc-500">{label}</dt>
      <dd className="font-display text-base text-zinc-50">{value}</dd>
      {hint ? <p className="truncate text-[10px] text-zinc-500">{hint}</p> : null}
    </div>
  );
}
