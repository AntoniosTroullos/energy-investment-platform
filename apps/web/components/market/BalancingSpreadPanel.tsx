"use client";

import { eurPerMwh, utcDate } from "../../lib/liveMarket/liveMarket.api";
import type {
  ImbalanceStatistics,
  MfrrStatistics,
  PricingAttribution,
} from "../../lib/liveMarket/liveMarket.types";
import DashboardCard from "../overview/DashboardCard";

// The settled week, framed around the one quantity that decides what storage
// and flexibility are worth: what the system pays when it is short of energy
// against what it pays when it is long. An asset that can move energy between
// those two states earns the difference.

type BalancingSpreadPanelProps = {
  imbalance: ImbalanceStatistics;
  mfrr: MfrrStatistics | null;
  attribution: PricingAttribution | null;
  settlementFile: string | null;
};

export default function BalancingSpreadPanel({
  imbalance,
  mfrr,
  attribution,
  settlementFile,
}: BalancingSpreadPanelProps) {
  const shortShare =
    imbalance.periods > 0 ? imbalance.system_short_periods / imbalance.periods : 0;

  return (
    <DashboardCard
      title="Settled imbalance prices"
      subtitle={`${imbalance.periods} quarter-hours · ${utcDate(imbalance.from_utc)} to ${utcDate(
        imbalance.to_utc,
      )}${settlementFile ? ` · ${settlementFile}` : ""}`}
    >
      <div className="flex flex-col gap-3.5">
        {/* The short/long spread, as a bar so the asymmetry is visible rather
            than inferred from two numbers. */}
        <div>
          <div className="mb-1.5 flex items-baseline justify-between gap-2">
            <p className="text-[11px] uppercase tracking-[0.14em] text-zinc-500">
              Price when short vs long
            </p>
            <p className="font-display text-lg text-emerald-300">
              {eurPerMwh(imbalance.short_long_spread_eur_per_mwh)}
              <span className="ml-1 text-[11px] text-zinc-500">spread</span>
            </p>
          </div>

          <div className="flex h-7 overflow-hidden rounded-lg border border-white/10">
            <div
              className="flex items-center justify-start bg-rose-500/20 px-2"
              style={{ width: `${Math.max(12, shortShare * 100)}%` }}
            >
              <span className="truncate font-mono text-[10px] text-rose-200">
                short {Math.round(shortShare * 100)}%
              </span>
            </div>
            <div className="flex flex-1 items-center justify-end bg-sky-500/15 px-2">
              <span className="truncate font-mono text-[10px] text-sky-200">
                long {Math.round((1 - shortShare) * 100)}%
              </span>
            </div>
          </div>

          <div className="mt-1.5 flex justify-between text-[11px]">
            <span className="text-zinc-400">
              <span className="font-mono text-rose-200">
                {eurPerMwh(imbalance.mean_price_when_short_eur_per_mwh)}
              </span>{" "}
              paid for energy
            </span>
            <span className="text-zinc-400">
              <span className="font-mono text-sky-200">
                {eurPerMwh(imbalance.mean_price_when_long_eur_per_mwh)}
              </span>{" "}
              to absorb it
            </span>
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-2 border-t border-white/5 pt-3 sm:grid-cols-4">
          <Figure label="Mean" value={eurPerMwh(imbalance.mean_eur_per_mwh)} />
          <Figure label="Median" value={eurPerMwh(imbalance.median_eur_per_mwh)} />
          <Figure
            label="P10 – P90"
            value={`${eurPerMwh(imbalance.p10_eur_per_mwh, 0)} – ${eurPerMwh(imbalance.p90_eur_per_mwh, 0)}`}
          />
          <Figure
            label="Below zero"
            value={`${imbalance.negative_periods}`}
            hint={`of ${imbalance.periods} periods`}
            tone={imbalance.negative_periods > 0 ? "accent" : "default"}
          />
        </dl>

        {mfrr ? (
          <dl className="grid grid-cols-2 gap-2 border-t border-white/5 pt-3 sm:grid-cols-3">
            <Figure label="mFRR up" value={eurPerMwh(mfrr.mean_up_eur_per_mwh)} hint="mean when called" />
            <Figure label="mFRR down" value={eurPerMwh(mfrr.mean_down_eur_per_mwh)} hint="mean when called" />
            <Figure
              label="mFRR spread"
              value={eurPerMwh(mfrr.mean_spread_eur_per_mwh)}
              hint="per MWh cycled, before losses"
              tone="accent"
            />
          </dl>
        ) : null}

        {attribution ? (
          <div className="border-t border-white/5 pt-3">
            <p className="mb-1.5 text-[11px] uppercase tracking-[0.14em] text-zinc-500">
              Which price set settlement
            </p>
            <div className="flex h-2 overflow-hidden rounded-full bg-white/5">
              <div
                className="bg-rose-400/60"
                style={{ width: `${attribution.set_by_mfrr_up_pct}%` }}
                title={`mFRR up: ${attribution.set_by_mfrr_up_pct}%`}
              />
              <div
                className="bg-sky-400/60"
                style={{ width: `${attribution.set_by_mfrr_down_pct}%` }}
                title={`mFRR down: ${attribution.set_by_mfrr_down_pct}%`}
              />
              <div
                className="bg-zinc-500/50"
                style={{ width: `${attribution.set_by_neither_pct}%` }}
                title={`neither: ${attribution.set_by_neither_pct}%`}
              />
            </div>
            <p className="mt-1.5 text-[11px] leading-5 text-zinc-500">
              <span className="text-rose-200">{attribution.set_by_mfrr_up_pct}%</span> mFRR up ·{" "}
              <span className="text-sky-200">{attribution.set_by_mfrr_down_pct}%</span> mFRR down ·{" "}
              <span className="text-zinc-300">{attribution.set_by_neither_pct}%</span> neither. Measured
              from this week&apos;s settlement rather than assumed from the rulebook, so an amendment
              cannot silently make it wrong.
            </p>
          </div>
        ) : null}
      </div>
    </DashboardCard>
  );
}

function Figure({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "accent";
}) {
  return (
    <div className="min-w-0">
      <dt className="truncate text-[10px] uppercase tracking-[0.14em] text-zinc-500">{label}</dt>
      <dd
        className={`font-display text-base ${tone === "accent" ? "text-emerald-300" : "text-zinc-50"}`}
      >
        {value}
      </dd>
      {hint ? <p className="truncate text-[10px] text-zinc-500">{hint}</p> : null}
    </div>
  );
}
