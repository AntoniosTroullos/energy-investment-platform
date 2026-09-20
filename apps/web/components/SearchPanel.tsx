"use client";

import { getSearchResultSubtitle, getSearchResultTitle } from "../lib/asset-search";
import type { AssetSelection } from "../types/asset";

type SearchPanelProps = {
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  limitResultsToViewport: boolean;
  searchResults: AssetSelection[];
  onAssetFocus: (asset: AssetSelection) => void;
};

export default function SearchPanel({
  searchQuery,
  onSearchQueryChange,
  limitResultsToViewport,
  searchResults,
  onAssetFocus,
}: SearchPanelProps) {
  return (
    <section className="mt-8">
      <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
        Search
      </h2>
      <div className="mt-4 space-y-4">
        <p className="text-xs leading-5 text-zinc-400">
          Search Greece-wide infrastructure by name, id, technology, voltage, operator, hydrogen role, or connected system.
        </p>
        {limitResultsToViewport ? (
          <p className="text-xs leading-5 text-emerald-300">
            Search is currently limited to infrastructure visible in the map view.
          </p>
        ) : null}
        <input
          type="search"
          placeholder="Search plants, substations, power lines, gas assets, hydrogen pipelines, and hydrogen projects..."
          value={searchQuery}
          onChange={(event) => onSearchQueryChange(event.target.value)}
          className="w-full rounded-lg border border-white/10 bg-zinc-950 px-4 py-3 text-sm text-zinc-100 outline-none placeholder:text-zinc-500 focus:border-emerald-400"
        />
        {searchQuery.trim() ? (
          <div className="rounded-xl border border-white/10 bg-zinc-950/90 p-2">
            {searchResults.length > 0 ? (
              <div className="max-h-64 space-y-2 overflow-y-auto">
                {searchResults.map((asset) => (
                  <button
                    key={asset.id}
                    type="button"
                    onClick={() => onAssetFocus(asset)}
                    className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-3 text-left transition hover:bg-white/10"
                  >
                    <p className="text-sm font-medium text-zinc-100">
                      {getSearchResultTitle(asset)}
                    </p>
                    <p className="mt-1 text-xs text-zinc-400">
                      {getSearchResultSubtitle(asset)}
                    </p>
                  </button>
                ))}
              </div>
            ) : (
              <p className="px-2 py-3 text-sm text-zinc-400">
                No matching assets found.
              </p>
            )}
          </div>
        ) : null}
      </div>
    </section>
  );
}
