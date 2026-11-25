"use client";

import { useMemo, useState } from "react";

import { buildProjector, computeBounds, lineToSvgPath, polygonToSvgPath } from "../../lib/spatial/geoSvg";
import { formatEur, formatMw, formatPct, regionLabel } from "../../lib/overview/overview.api";
import type { OverviewCorridor, OverviewRegion } from "../../lib/overview/overview.types";

// The national picture in one frame: the thirteen modelled regions tinted by a
// chosen metric, and the transmission corridors between them drawn with width
// by rating and colour by how hard they are worked.
//
// Inline SVG rather than MapLibre: this is a schematic of a thirteen-bus model,
// not a geographic map, and it has to paint instantly inside a dashboard that
// already carries several other panels. The projection helpers are the ones the
// Spatial Results view already uses, so both views sit in the same frame.

const VIEW_WIDTH = 560;
const VIEW_HEIGHT = 620;
const MAP_PADDING = 16;

export type GridMapMetric = "price" | "solar_capture" | "wind_capture" | "best_irr";

const METRICS: { id: GridMapMetric; label: string; unit: string }[] = [
  { id: "price", label: "System price", unit: "€/MWh" },
  { id: "solar_capture", label: "Solar capture", unit: "€/MWh" },
  { id: "wind_capture", label: "Wind capture", unit: "€/MWh" },
  { id: "best_irr", label: "Best project IRR", unit: "%" },
];

function metricValue(region: OverviewRegion, metric: GridMapMetric): number | null {
  switch (metric) {
    case "price":
      return region.price_eur_per_mwh;
    case "solar_capture":
      return region.solar_capture_eur_per_mwh;
    case "wind_capture":
      return region.wind_capture_eur_per_mwh;
    case "best_irr":
      return region.best_candidate_irr_pct;
  }
}

// A single-hue ramp from the page's own deep slate to its emerald accent.
// One hue, not a rainbow: the quantity is ordered, and a diverging or
// categorical scale would imply a midpoint or a grouping that is not there.
function rampColor(fraction: number): string {
  const clamped = Math.min(1, Math.max(0, fraction));
  const from = [27, 30, 36];
  const to = [69, 210, 170];
  const channel = (index: number) => Math.round(from[index] + (to[index] - from[index]) * clamped);
  return `rgb(${channel(0)}, ${channel(1)}, ${channel(2)})`;
}

function corridorColor(utilisation: number | null): string {
  if (utilisation === null) return "rgba(244,244,245,0.35)";
  if (utilisation >= 60) return "#f59e0b";
  if (utilisation >= 35) return "#45d2aa";
  return "rgba(244,244,245,0.45)";
}

type NationalGridMapProps = {
  regionGeometry: GeoJSON.FeatureCollection | null;
  corridorGeometry: GeoJSON.FeatureCollection | null;
  regions: OverviewRegion[];
  corridors: OverviewCorridor[];
  metric: GridMapMetric;
  onMetricChange: (metric: GridMapMetric) => void;
};

export default function NationalGridMap({
  regionGeometry,
  corridorGeometry,
  regions,
  corridors,
  metric,
  onMetricChange,
}: NationalGridMapProps) {
  const [hovered, setHovered] = useState<string | null>(null);

  const byRegion = useMemo(() => {
    const map = new Map<string, OverviewRegion>();
    for (const region of regions) map.set(region.region_id, region);
    return map;
  }, [regions]);

  const utilisationByPair = useMemo(() => {
    const map = new Map<string, OverviewCorridor>();
    for (const corridor of corridors) {
      map.set([corridor.from, corridor.to].sort().join("|"), corridor);
    }
    return map;
  }, [corridors]);

  const projector = useMemo(() => {
    const collections = [regionGeometry, corridorGeometry].filter(
      (collection): collection is GeoJSON.FeatureCollection => collection !== null,
    );
    if (collections.length === 0) return null;
    return buildProjector(computeBounds(collections), VIEW_WIDTH, VIEW_HEIGHT, MAP_PADDING);
  }, [regionGeometry, corridorGeometry]);

  // A rank scale, not a linear one. These metrics are skewed -- twelve regions
  // clear 58 EUR/MWh of solar capture and one sits at 38 -- so a linear ramp
  // spends its whole range on the outlier and paints the other twelve the same
  // colour. Ranking spreads the colour across the regions that exist, which is
  // what the reader is comparing. The legend still reports the real end values,
  // so the scale is shorthand for order, never for distance.
  const { minimum, maximum, rankOf } = useMemo(() => {
    const values = regions
      .map((region) => metricValue(region, metric))
      .filter((value): value is number => value !== null && Number.isFinite(value))
      .sort((left, right) => left - right);

    if (values.length === 0) {
      return { minimum: 0, maximum: 1, rankOf: () => null as number | null };
    }

    const lookup = (value: number | null): number | null => {
      if (value === null || !Number.isFinite(value)) return null;
      if (values.length === 1) return 1;
      const index = values.findIndex((candidate) => candidate >= value);
      return (index < 0 ? values.length - 1 : index) / (values.length - 1);
    };

    return { minimum: values[0], maximum: values[values.length - 1], rankOf: lookup };
  }, [regions, metric]);

  const active = METRICS.find((entry) => entry.id === metric) ?? METRICS[0];
  const hoveredRegion = hovered ? byRegion.get(hovered) ?? null : null;

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex flex-wrap gap-1.5">
        {METRICS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            onClick={() => onMetricChange(entry.id)}
            className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition-colors ${
              entry.id === metric
                ? "bg-emerald-500/10 text-emerald-300 ring-1 ring-inset ring-emerald-500/30"
                : "text-zinc-400 hover:bg-white/5 hover:text-zinc-100"
            }`}
          >
            {entry.label}
          </button>
        ))}
      </div>

      <div className="relative flex-1">
        {projector === null ? (
          <div className="flex h-full min-h-60 items-center justify-center text-xs text-zinc-500">
            Loading network geometry…
          </div>
        ) : (
          <svg
            viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
            className="h-full w-full"
            role="img"
            aria-label={`Greek grid regions coloured by ${active.label}`}
          >
            {regionGeometry?.features.map((feature, index) => {
              const id = String(feature.properties?.id ?? index);
              const region = byRegion.get(id);
              const value = region ? metricValue(region, metric) : null;
              const fraction = rankOf(value);
              return (
                <path
                  key={id}
                  d={polygonToSvgPath(feature.geometry, projector)}
                  fill={fraction === null ? "#14171c" : rampColor(fraction)}
                  fillOpacity={hovered && hovered !== id ? 0.55 : 0.92}
                  stroke={hovered === id ? "#eceef0" : "#08090b"}
                  strokeWidth={hovered === id ? 1.4 : 0.6}
                  onMouseEnter={() => setHovered(id)}
                  onMouseLeave={() => setHovered(null)}
                />
              );
            })}

            {corridorGeometry?.features.map((feature, index) => {
              const from = String(feature.properties?.bus0 ?? "");
              const to = String(feature.properties?.bus1 ?? "");
              const rating = Number(feature.properties?.s_nom_mw ?? 0);
              const corridor = utilisationByPair.get([from, to].sort().join("|")) ?? null;
              const verified = Number(feature.properties?.real_circuits_found ?? 0) > 0;
              return (
                <path
                  key={`${from}-${to}-${index}`}
                  d={lineToSvgPath(feature.geometry, projector)}
                  fill="none"
                  stroke={corridorColor(corridor?.mean_utilisation_pct ?? null)}
                  strokeWidth={Math.max(1.2, Math.min(5, rating / 600))}
                  strokeLinecap="round"
                  // An unverified corridor is drawn dashed: the model carries
                  // it, the real transmission layer does not show a circuit.
                  strokeDasharray={verified ? undefined : "4 4"}
                />
              );
            })}
          </svg>
        )}

        {hoveredRegion ? (
          <div className="pointer-events-none absolute left-2 top-2 rounded-lg border border-white/10 bg-zinc-950/95 px-3 py-2 text-[11px] shadow-lg">
            <p className="font-display text-xs text-zinc-100">{regionLabel(hoveredRegion.region_id)}</p>
            <dl className="mt-1 space-y-0.5 text-zinc-400">
              <div className="flex gap-3">
                <dt className="w-24">System price</dt>
                <dd className="font-mono text-zinc-200">{formatEur(hoveredRegion.price_eur_per_mwh)}</dd>
              </div>
              <div className="flex gap-3">
                <dt className="w-24">Solar capture</dt>
                <dd className="font-mono text-zinc-200">{formatEur(hoveredRegion.solar_capture_eur_per_mwh)}</dd>
              </div>
              <div className="flex gap-3">
                <dt className="w-24">Wind capture</dt>
                <dd className="font-mono text-zinc-200">{formatEur(hoveredRegion.wind_capture_eur_per_mwh)}</dd>
              </div>
              <div className="flex gap-3">
                <dt className="w-24">Peak demand</dt>
                <dd className="font-mono text-zinc-200">{formatMw(hoveredRegion.peak_load_mw)}</dd>
              </div>
              <div className="flex gap-3">
                <dt className="w-24">Best IRR</dt>
                <dd className="font-mono text-zinc-200">{formatPct(hoveredRegion.best_candidate_irr_pct)}</dd>
              </div>
            </dl>
          </div>
        ) : null}
      </div>

      <div className="flex items-center justify-between gap-4 text-[11px] text-zinc-500">
        <div className="flex items-center gap-2">
          <span className="font-mono">
            {metric === "best_irr" ? formatPct(minimum) : formatEur(minimum, 0)}
          </span>
          <span
            className="h-2 w-24 rounded-full"
            style={{ background: `linear-gradient(to right, ${rampColor(0)}, ${rampColor(1)})` }}
          />
          <span className="font-mono">
            {metric === "best_irr" ? formatPct(maximum) : formatEur(maximum, 0)}
          </span>
          <span className="ml-1">{active.unit}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-5 rounded-full bg-amber-500" /> &gt;60% loaded
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-5 rounded-full border-t border-dashed border-zinc-400" /> unverified
          </span>
        </div>
      </div>
    </div>
  );
}
