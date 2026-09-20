"use client";

import type { AssetSelection } from "../types/asset";

type TopOpportunitiesPanelProps = {
  topOpportunities: AssetSelection[];
  onAssetFocus: (asset: AssetSelection) => void;
};

export default function TopOpportunitiesPanel({
  topOpportunities,
  onAssetFocus,
}: TopOpportunitiesPanelProps) {
  return (
    <section className="mt-8">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
          Top Opportunities
        </h2>
        <span className="text-xs text-zinc-500">
          {topOpportunities.length} shown
        </span>
      </div>

      <div className="mt-4 space-y-3">
        {topOpportunities.length > 0 ? (
          topOpportunities.map((asset, index) => (
            <button
              key={asset.id}
              type="button"
              onClick={() => onAssetFocus(asset)}
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-4 text-left transition hover:bg-white/10"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300">
                    #{index + 1}
                  </p>
                  <p className="mt-2 truncate text-sm font-medium text-zinc-100">
                    {asset.name}
                  </p>
                  <p className="mt-1 text-xs text-zinc-400">
                    {asset.id} - {String(asset.properties.technology ?? "Unknown")}
                  </p>
                </div>
                <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-right">
                  <p className="text-xs text-zinc-400">Score</p>
                  <p className="text-sm font-semibold text-emerald-300">
                    {String(asset.properties.investment_score ?? "-")}
                  </p>
                </div>
              </div>

              <div className="mt-3 flex gap-4 text-xs text-zinc-400">
                <span>
                  Substation:{" "}
                  {String(asset.properties.distance_to_substation_km ?? "-")} km
                </span>
                <span>
                  Connection:{" "}
                  {String(asset.properties.connection_cost_level ?? "-")}
                </span>
              </div>
            </button>
          ))
        ) : (
          <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-4">
            <p className="text-sm text-zinc-400">
              No opportunities match the current filters.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
