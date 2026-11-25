"use client";

import { carrierColor, formatMw } from "../../lib/overview/overview.api";
import type { OverviewFleet, OverviewPipeline } from "../../lib/overview/overview.types";

// Operating fleet against licensing pipeline. These are deliberately shown as
// two different quantities: the pipeline is roughly ten times the fleet,
// because it counts everything applied for or licensed rather than built, and
// a dashboard that adds them together is telling the reader the grid is ten
// times its real size.

type PipelinePanelProps = {
  pipeline: OverviewPipeline;
  fleet: OverviewFleet;
};

export default function PipelinePanel({ pipeline, fleet }: PipelinePanelProps) {
  const rows = pipeline.by_technology.filter((row) => row.capacity_mw > 0).slice(0, 6);
  const largest = Math.max(...rows.map((row) => row.capacity_mw), 1);

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
          <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">Operating fleet</p>
          <p className="font-display text-lg text-zinc-50">{formatMw(fleet.total_capacity_mw)}</p>
        </div>
        <div className="rounded-lg border border-emerald-500/15 bg-emerald-500/5 px-3 py-2">
          <p className="text-[10px] uppercase tracking-[0.14em] text-emerald-300/80">Licensed / applied</p>
          <p className="font-display text-lg text-zinc-50">{formatMw(pipeline.tracked_capacity_mw)}</p>
        </div>
      </div>

      <ul className="flex flex-col gap-2">
        {rows.map((row) => (
          <li key={row.technology}>
            <div className="flex items-baseline justify-between gap-2 text-[11px]">
              <span className="truncate text-zinc-300">{row.technology}</span>
              <span className="shrink-0 font-mono text-zinc-400">
                {formatMw(row.capacity_mw)}
                <span className="ml-1.5 text-zinc-600">{(row.asset_count ?? 0).toLocaleString()}</span>
              </span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/5">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(row.capacity_mw / largest) * 100}%`,
                  background: carrierColor(row.technology.split("/")[0]),
                  opacity: 0.7,
                }}
              />
            </div>
          </li>
        ))}
      </ul>

      <p className="mt-auto text-[10px] leading-relaxed text-zinc-600">
        {pipeline.tracked_asset_count.toLocaleString()} assets tracked across the licensing registries — projects
        applied for or permitted, not built.
      </p>
    </div>
  );
}
