"use client";

import Link from "next/link";

import { formatMoney, formatMw, formatPct, regionLabel } from "../../lib/overview/overview.api";
import type { OverviewOpportunities } from "../../lib/overview/overview.types";

// The ranked build list. One row per region and technology, because candidate
// cells inside a region share a price and a capacity factor and so produce
// identical economics -- eight copies of the same number would be noise.

type OpportunitiesTableProps = {
  opportunities: OverviewOpportunities;
};

export default function OpportunitiesTable({ opportunities }: OpportunitiesTableProps) {
  if (opportunities.top.length === 0) {
    return <p className="py-6 text-center text-xs text-zinc-500">No priced candidates in this scenario.</p>;
  }

  return (
    <div className="flex h-full flex-col">
      <div className="-mx-1 overflow-x-auto">
        <table className="w-full min-w-[460px] border-collapse text-left text-[11px]">
          <thead>
            <tr className="text-[10px] uppercase tracking-[0.12em] text-zinc-500">
              <th className="px-1 pb-2 font-medium">Region</th>
              <th className="px-1 pb-2 font-medium">Tech</th>
              <th className="px-1 pb-2 text-right font-medium">Size</th>
              <th className="px-1 pb-2 text-right font-medium">Capture</th>
              <th className="px-1 pb-2 text-right font-medium">IRR</th>
              <th className="px-1 pb-2 text-right font-medium">NPV</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {opportunities.top.map((row) => (
              <tr key={row.candidate_id} className="text-zinc-300">
                <td className="px-1 py-1.5">{regionLabel(row.region_id)}</td>
                <td className="px-1 py-1.5 text-zinc-400">{row.technology}</td>
                <td className="px-1 py-1.5 text-right font-mono text-zinc-400">{formatMw(row.capacity_mw)}</td>
                <td className="px-1 py-1.5 text-right font-mono text-zinc-400">
                  {formatPct(row.capture_rate_pct, 0)}
                </td>
                <td className="px-1 py-1.5 text-right font-mono font-semibold text-emerald-300">
                  {formatPct(row.irr_pct)}
                </td>
                <td className="px-1 py-1.5 text-right font-mono text-zinc-200">{formatMoney(row.npv_eur)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-auto flex items-center justify-between gap-2 pt-3">
        <p className="text-[10px] text-zinc-600">
          {opportunities.priced_count.toLocaleString()} of {opportunities.screened_count.toLocaleString()} screened
          sites priced
        </p>
        <Link
          href="/map"
          className="rounded-lg px-2.5 py-1 text-[11px] font-medium text-emerald-300 transition-colors hover:bg-emerald-500/10"
        >
          Open on the map →
        </Link>
      </div>
    </div>
  );
}
