"use client";

import Link from "next/link";

type AnalysisFiltersPanelProps = {
  excludeNatura2000: boolean;
  onExcludeNatura2000Change: (checked: boolean) => void;
};

export default function AnalysisFiltersPanel({
  excludeNatura2000,
  onExcludeNatura2000Change,
}: AnalysisFiltersPanelProps) {
  return (
    <section className="mt-8">
      <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
        Analysis Filters
      </h2>
      <div className="mt-4 space-y-4">
        <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3">
          <p className="text-xs leading-5 text-zinc-400">
            Screening controls are configured in{" "}
            <Link href="/scenarios" className="text-emerald-300 hover:text-emerald-200">
              Scenario Studio
            </Link>
            .
          </p>
        </div>
        <label className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 px-4 py-4 text-sm text-zinc-100">
          <input
            type="checkbox"
            checked={excludeNatura2000}
            onChange={(event) => onExcludeNatura2000Change(event.target.checked)}
            className="h-4 w-4 rounded border-white/20 bg-zinc-800 text-emerald-400 focus:ring-emerald-400"
          />
          <span>Exclude Natura 2000 areas from candidate screening</span>
        </label>
        <div className="rounded-xl border border-white/10 bg-zinc-950/90 px-4 py-3">
          <p className="text-xs leading-5 text-zinc-400">
            Natura 2000 is available as a context layer in the sidebar. When this option is enabled, candidate cells whose centroids fall inside protected areas are removed from the visible analysis results.
          </p>
        </div>
        <button
          type="button"
          className="w-full rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm font-medium text-emerald-300 transition hover:bg-emerald-500/20"
        >
          Run Analysis
        </button>
      </div>
    </section>
  );
}
