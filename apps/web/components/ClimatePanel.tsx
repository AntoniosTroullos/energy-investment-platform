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
      <h2 className="font-display text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
        Climate Filter
      </h2>

      <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-4">
        <p className="text-sm font-medium text-zinc-100">Selected asset climate</p>
        <p className="mt-2 text-xs leading-5 text-zinc-400">
          Hourly weather for this location through a solar or wind performance model,
          and what that output would have earned against the live day-ahead price.
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
              <p className="font-display text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
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

            {climate.yieldEstimate ? (
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300">
                  Modelled Output
                </p>
                <dl className="mt-3 grid grid-cols-2 gap-3">
                  <div>
                    <dt className="text-xs text-zinc-400">Capacity factor</dt>
                    <dd className="mt-1 font-display text-xl text-zinc-50">
                      {climate.yieldEstimate.capacityFactorPct.toFixed(1)}%
                    </dd>
                    <dd className="text-[11px] text-zinc-500">
                      over the last {Math.round(climate.yieldEstimate.windowHours / 24)} days of weather
                    </dd>
                  </div>
                  {climate.yieldEstimate.marketCapture ? (
                    <div>
                      <dt className="text-xs text-zinc-400">Earned in the market</dt>
                      <dd className="mt-1 font-display text-xl text-zinc-50">
                        €{climate.yieldEstimate.marketCapture.capturePriceEurMwh.toFixed(0)}
                        <span className="ml-1 text-xs text-zinc-500">/MWh</span>
                      </dd>
                      <dd className="text-[11px] text-zinc-500">
                        {climate.yieldEstimate.marketCapture.captureRatePct?.toFixed(0) ?? "—"}% of the
                        average hour
                      </dd>
                    </div>
                  ) : null}
                </dl>
                {climate.yieldEstimate.dcAcRatio ? (
                  <p className="mt-3 text-[11px] text-zinc-400">
                    DC/AC {climate.yieldEstimate.dcAcRatio.toFixed(2)} —{" "}
                    {(climate.yieldEstimate.clippedPctOfDc ?? 0) > 0 ? (
                      <>
                        the inverter clipped{" "}
                        <span className="text-amber-300">
                          {climate.yieldEstimate.clippedPctOfDc?.toFixed(1)}%
                        </span>{" "}
                        of what the array made, over {climate.yieldEstimate.hoursClipped} hours.
                      </>
                    ) : (
                      <>nothing clipped: cell heat held DC output under the inverter limit.</>
                    )}
                  </p>
                ) : null}
                <div className="mt-3 h-10">
                  <YieldSparkline series={climate.yieldEstimate.series} />
                </div>
                <p className="mt-2 text-[11px] leading-5 text-zinc-400">{climate.yieldEstimate.model}.</p>
              </div>
            ) : (
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300">
                      Current Conditions
                    </p>
                    <p className="mt-2 text-lg font-semibold text-zinc-100">
                      {formatEfficiency(climate.efficiency.estimatedEfficiencyPct)}
                    </p>
                  </div>
                  <span className="rounded-full border border-emerald-500/30 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
                    {climate.efficiency.band}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-zinc-200">{climate.efficiency.summary}</p>
              </div>
            )}
            <p className="text-xs text-zinc-400">Source: {climate.source}</p>
          </div>
        ) : null}
      </div>
    </section>
  );
}

// The production shape behind the capacity factor: a week of hourly output,
// where the gaps are nights for solar and calm spells for wind. It is the part
// a single percentage cannot show, and the part that decides what the site is
// paid.
function YieldSparkline({ series }: { series: { timestamp: string; outputPerUnit: number }[] }) {
  if (series.length === 0) {
    return null;
  }

  const width = 240;
  const height = 40;
  const peak = Math.max(...series.map((point) => point.outputPerUnit), 0.001);
  const step = width / Math.max(1, series.length - 1);
  const line = series
    .map((point, index) => `${index === 0 ? "M" : "L"}${(index * step).toFixed(1)},${(height - (point.outputPerUnit / peak) * height).toFixed(1)}`)
    .join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-full w-full" preserveAspectRatio="none" aria-hidden="true">
      <path d={`${line} L${width},${height} L0,${height} Z`} fill="rgba(69,210,170,0.18)" />
      <path d={line} fill="none" stroke="#45d2aa" strokeWidth={1} vectorEffect="non-scaling-stroke" />
    </svg>
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
