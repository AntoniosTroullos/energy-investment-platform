"use client";

import { carrierColor, formatEur, formatPct } from "../../lib/overview/overview.api";
import type { CaptureRow } from "../../lib/overview/overview.types";

// Capture rate is the number that decides a renewable investment and the one
// a flat average price hides. Each row shows what the technology is paid
// against what the average hour is worth: a bar that stops short of the 100%
// mark is revenue the technology does not get, because it produces when its
// own kind is abundant.

type CapturePanelProps = {
  rows: CaptureRow[];
  systemPrice: number | null | undefined;
};

export default function CapturePanel({ rows, systemPrice }: CapturePanelProps) {
  if (rows.length === 0) {
    return <p className="py-6 text-center text-xs text-zinc-500">No capture data for this scenario.</p>;
  }

  const widest = Math.max(100, ...rows.map((row) => row.capture_rate_pct ?? 0));

  return (
    <div className="flex h-full flex-col gap-3">
      {rows.map((row) => {
        const rate = row.capture_rate_pct ?? 0;
        return (
          <div key={row.carrier}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="flex items-center gap-2 text-xs capitalize text-zinc-200">
                <span className="h-2 w-2 rounded-full" style={{ background: carrierColor(row.carrier) }} />
                {row.carrier}
              </span>
              <span className="font-mono text-xs text-zinc-100">
                {formatEur(row.capture_price_eur_per_mwh, 0)}
                <span className="ml-1.5 text-zinc-500">{formatPct(row.capture_rate_pct, 0)}</span>
              </span>
            </div>
            <div className="relative mt-1.5 h-2.5 overflow-hidden rounded-full bg-white/5">
              <div
                className="h-full rounded-full"
                style={{ width: `${(rate / widest) * 100}%`, background: carrierColor(row.carrier), opacity: 0.75 }}
              />
              {/* The 100% mark: paid exactly what the average hour is worth. */}
              <span
                className="absolute top-0 h-full w-px bg-zinc-300/60"
                style={{ left: `${(100 / widest) * 100}%` }}
              />
            </div>
            <p className="mt-1 text-[11px] text-zinc-500">
              {formatPct(row.capacity_factor_pct, 0)} capacity factor
              {row.curtailment_pct ? ` · ${formatPct(row.curtailment_pct, 1)} curtailed` : ""}
            </p>
          </div>
        );
      })}
      <p className="mt-auto text-[10px] leading-relaxed text-zinc-600">
        Against a {formatEur(systemPrice, 0)}/MWh system average. The marker is 100% — paid exactly the
        average hour&apos;s worth.
      </p>
    </div>
  );
}
