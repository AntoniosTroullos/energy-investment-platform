"use client";

import { getComparisonRecommendation } from "../lib/compare-recommendation";
import { getScoreExplanation } from "../lib/score-explanation";
import type { Scenario } from "../lib/scenario/scenario.types";
import type { AssetSelection } from "../types/asset";

type ComparePanelProps = {
  comparedAssets: AssetSelection[];
  scenario: Scenario;
  onFocusAsset: (asset: AssetSelection) => void;
  onRemoveAsset: (assetId: string) => void;
  onClearAll: () => void;
};

export default function ComparePanel({
  comparedAssets,
  scenario,
  onFocusAsset,
  onRemoveAsset,
  onClearAll,
}: ComparePanelProps) {
  const recommendation = getComparisonRecommendation(comparedAssets, scenario);

  return (
    <section className="mt-8">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
          Compare
        </h2>
        {comparedAssets.length > 0 ? (
          <button
            type="button"
            onClick={onClearAll}
            className="text-xs text-zinc-400 transition hover:text-zinc-200"
          >
            Clear all
          </button>
        ) : null}
      </div>

      {recommendation ? (
        <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
            Recommendation Summary
          </p>
          <div className="mt-4 space-y-3 text-sm text-zinc-100">
            {recommendation.bestOverall ? <p>{recommendation.bestOverall}</p> : null}
            {recommendation.bestSolar ? <p>{recommendation.bestSolar}</p> : null}
            {recommendation.bestWind ? <p>{recommendation.bestWind}</p> : null}
            {recommendation.bestLowConnectionCost ? (
              <p>{recommendation.bestLowConnectionCost}</p>
            ) : null}
            {recommendation.avoid ? <p>{recommendation.avoid}</p> : null}
            {recommendation.scenarioFit ? <p>{recommendation.scenarioFit}</p> : null}
          </div>
        </div>
      ) : null}

      <div className="mt-4 space-y-3">
        {comparedAssets.length > 0 ? (
          comparedAssets.map((asset) => {
            const explanation = getScoreExplanation(asset);

            return (
              <div
                key={asset.id}
                className="rounded-xl border border-white/10 bg-white/5 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <button
                    type="button"
                    onClick={() => onFocusAsset(asset)}
                    className="min-w-0 text-left"
                  >
                    <p className="truncate text-sm font-medium text-zinc-100">
                      {asset.name}
                    </p>
                    <p className="mt-1 text-xs text-zinc-400">{asset.id}</p>
                  </button>

                  <button
                    type="button"
                    onClick={() => onRemoveAsset(asset.id)}
                    className="rounded-lg border border-white/10 px-2 py-1 text-xs text-zinc-300 transition hover:bg-white/5"
                  >
                    Remove
                  </button>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-zinc-400">
                  <Metric label="Technology" value={String(asset.properties.technology)} />
                  <Metric
                    label="Score"
                    value={String(asset.properties.investment_score)}
                  />
                  <Metric label="Solar" value={String(asset.properties.solar_score)} />
                  <Metric label="Wind" value={String(asset.properties.wind_score)} />
                  <Metric
                    label="Substation"
                    value={`${String(asset.properties.distance_to_substation_km)} km`}
                  />
                  <Metric
                    label="Line"
                    value={`${String(asset.properties.distance_to_line_km)} km`}
                  />
                  <Metric
                    label="Connection"
                    value={String(asset.properties.connection_cost_level)}
                  />
                  <Metric
                    label="Land Excluded"
                    value={String(asset.properties.land_excluded)}
                  />
                </div>

                <p className="mt-4 text-sm text-zinc-200">
                  {explanation?.summary ?? "No comparison summary available."}
                </p>
              </div>
            );
          })
        ) : (
          <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-4">
            <p className="text-sm text-zinc-400">
              Add up to 3 candidate cells to compare side by side.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p>{label}</p>
      <p className="mt-1 text-sm text-zinc-100">{value}</p>
    </div>
  );
}
