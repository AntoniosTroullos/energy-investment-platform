"use client";

import { formatMw, formatPct, regionLabel } from "../../lib/overview/overview.api";
import type { OverviewNetwork } from "../../lib/overview/overview.types";

// Where the grid actually binds. A corridor sitting at 100% for hundreds of
// hours is the constraint that splits prices between regions, and it is the
// reason one side is a better place to build than the other.

type NetworkStressPanelProps = {
  network: OverviewNetwork;
};

function utilisationTone(value: number | null): string {
  if (value === null) return "bg-zinc-700";
  if (value >= 60) return "bg-amber-500";
  if (value >= 35) return "bg-emerald-500";
  return "bg-zinc-600";
}

export default function NetworkStressPanel({ network }: NetworkStressPanelProps) {
  return (
    <div className="flex h-full flex-col gap-3">
      <div className="grid grid-cols-3 gap-2">
        <div>
          <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">Transfer capacity</p>
          <p className="font-display text-base text-zinc-50">{formatMw(network.total_transfer_capacity_mw)}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">Mean loading</p>
          <p className="font-display text-base text-zinc-50">{formatPct(network.mean_utilisation_pct, 0)}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">Price spread</p>
          <p className="font-display text-base text-zinc-50">
            €{(network.mean_region_price_spread_eur_per_mwh ?? 0).toFixed(1)}
          </p>
        </div>
      </div>

      <ul className="flex flex-col gap-2">
        {network.corridors.map((corridor) => (
          <li key={`${corridor.from}-${corridor.to}`}>
            <div className="flex items-baseline justify-between gap-2 text-[11px]">
              <span className="truncate text-zinc-300">
                {regionLabel(corridor.from)} → {regionLabel(corridor.to)}
              </span>
              <span className="shrink-0 font-mono text-zinc-400">
                {formatPct(corridor.mean_utilisation_pct, 0)} · {formatMw(corridor.rating_mw)}
              </span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/5">
              <div
                className={`h-full rounded-full ${utilisationTone(corridor.mean_utilisation_pct)}`}
                style={{ width: `${Math.min(100, corridor.mean_utilisation_pct ?? 0)}%` }}
              />
            </div>
            {corridor.congested_hours && corridor.congested_hours > 0 ? (
              <p className="mt-0.5 text-[10px] text-amber-300/80">
                {Math.round(corridor.congested_hours).toLocaleString()} h at 90%+ of its rating
              </p>
            ) : null}
          </li>
        ))}
      </ul>

      <p className="mt-auto text-[10px] leading-relaxed text-zinc-600">
        {network.verified_corridor_count} of {network.corridor_count} corridors confirmed against real
        transmission circuits.
      </p>
    </div>
  );
}
