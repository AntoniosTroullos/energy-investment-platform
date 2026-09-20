"use client";

import type { AssetSelection } from "../types/asset";
import type {
  ClimateAssetResponse,
  ClimateRequestState,
} from "../types/climate";

type ClimatePanelProps = {
  asset: AssetSelection | null;
  climate: ClimateAssetResponse | null;
  requestState: ClimateRequestState;
  errorMessage: string;
};

export default function ClimatePanel({
  asset,
  climate,
  requestState,
  errorMessage,
}: ClimatePanelProps) {
  const isPlant = asset?.assetType === "plant";

  return (
    <section className="mt-8">
      <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
        Climate Filter
      </h2>

      <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-4">
        <p className="text-sm font-medium text-zinc-100">Selected asset climate</p>
        <p className="mt-2 text-xs leading-5 text-zinc-400">
          This first pass uses live climate conditions for the selected asset location
          and a simple solar or wind efficiency estimate.
        </p>

        {!asset ? (
          <p className="mt-4 text-sm text-zinc-400">
            Select a plant on the map to load live climate conditions.
          </p>
        ) : null}

        {asset && !isPlant ? (
          <p className="mt-4 text-sm text-zinc-400">
            Climate efficiency is currently modeled for plants first. Select a power
            plant to view current weather support for renewable output.
          </p>
        ) : null}

        {requestState === "loading" ? (
          <p className="mt-4 text-sm text-zinc-300">
            Loading live climate conditions for {asset?.name}...
          </p>
        ) : null}

        {requestState === "error" ? (
          <div className="mt-4 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-3">
            <p className="text-sm text-rose-300">{errorMessage}</p>
          </div>
        ) : null}

        {isPlant && climate ? (
          <div className="mt-4 space-y-4">
            <div className="rounded-lg border border-white/10 bg-zinc-950/70 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
                Live Conditions
              </p>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <Metric label="Temperature" value={formatMetric(climate.current.temperatureC, "°C")} />
                <Metric label="Cloud Cover" value={formatMetric(climate.current.cloudCoverPct, "%")} />
                <Metric label="Wind 10 m" value={formatMetric(climate.current.windSpeed10mKph, "km/h")} />
                <Metric label="Wind 100 m" value={formatMetric(climate.current.windSpeed100mKph, "km/h")} />
                <Metric
                  label="Shortwave Radiation"
                  value={formatMetric(climate.current.shortwaveRadiationWm2, "W/m2")}
                />
                <Metric
                  label="Direct Normal Irradiance"
                  value={formatMetric(
                    climate.current.directNormalIrradianceWm2,
                    "W/m2",
                  )}
                />
              </dl>
            </div>

            <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300">
                    Renewable Efficiency
                  </p>
                  <p className="mt-2 text-lg font-semibold text-zinc-100">
                    {formatEfficiency(climate.efficiency.estimatedEfficiencyPct)}
                  </p>
                </div>
                <span className="rounded-full border border-emerald-500/30 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
                  {climate.efficiency.band}
                </span>
              </div>

              <p className="mt-3 text-sm leading-6 text-zinc-200">
                {climate.efficiency.summary}
              </p>
              <p className="mt-3 text-xs text-zinc-400">
                Source: {climate.source}
              </p>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-zinc-500">{label}</dt>
      <dd className="mt-1 text-zinc-100">{value}</dd>
    </div>
  );
}

function formatMetric(value: number | null, suffix: string) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "Unknown";
  }

  return `${roundMetric(value)} ${suffix}`;
}

function formatEfficiency(value: number | null) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "Not modeled";
  }

  return `${roundMetric(value)}%`;
}

function roundMetric(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}
