"use client";

import { useState } from "react";

import {
  buildScaleForValues,
  getRegionMetric,
  type ColorScale,
  type RegionMetricId,
} from "../lib/spatial/colorScale";
import { buildProjector, computeBounds, lineToSvgPath, polygonToSvgPath } from "../lib/spatial/geoSvg";
import RegionMetricLegend from "./RegionMetricLegend";

export type SpatialResultsMapMode = "single" | "delta";

type SpatialResultsMapProps = {
  regions: GeoJSON.FeatureCollection;
  corridors: GeoJSON.FeatureCollection;
  metricId: RegionMetricId;
  mode: SpatialResultsMapMode;
};

type RegionRow = {
  id: string;
  name: string;
  value: number | null;
  valueA: number | null;
  valueB: number | null;
};

const VIEW_WIDTH = 720;
const VIEW_HEIGHT = 720;
const MAP_PADDING = 24;
const REGION_STROKE_COLOR = "#09090b"; // zinc-950, this app's chart/page surface
const REGION_HOVER_STROKE_COLOR = "#f4f4f5"; // zinc-100 -- the hovered region "lifts"
const CORRIDOR_COLOR = "rgba(244, 244, 245, 0.55)"; // zinc-100 at reduced opacity -- infrastructure overlay, not a data color
const MIN_CORRIDOR_WIDTH = 1.5;
const MAX_CORRIDOR_WIDTH = 6;

function readNumber(properties: GeoJSON.GeoJsonProperties, key: string): number | null {
  const value = properties?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function regionRowsFor(regions: GeoJSON.FeatureCollection, metricId: RegionMetricId, mode: SpatialResultsMapMode): RegionRow[] {
  return regions.features.map((feature) => {
    const properties = feature.properties;
    const id = String(properties?.id ?? "");
    const name = String(properties?.name ?? id);

    if (mode === "delta") {
      return {
        id,
        name,
        value: readNumber(properties, `${metricId}_delta`),
        valueA: readNumber(properties, `${metricId}_a`),
        valueB: readNumber(properties, `${metricId}_b`),
      };
    }

    const value = readNumber(properties, metricId);
    return { id, name, value, valueA: null, valueB: null };
  });
}

function corridorWidthScale(corridors: GeoJSON.FeatureCollection): (capacityMw: number | null) => number {
  const capacities = corridors.features
    .map((feature) => readNumber(feature.properties, "s_nom_mw"))
    .filter((value): value is number => value !== null);

  if (capacities.length === 0) {
    return () => MIN_CORRIDOR_WIDTH;
  }

  const min = Math.min(...capacities);
  const max = Math.max(...capacities);
  const span = max - min;

  return (capacityMw) => {
    if (capacityMw === null) {
      return MIN_CORRIDOR_WIDTH;
    }
    const t = span === 0 ? 1 : (capacityMw - min) / span;
    return MIN_CORRIDOR_WIDTH + t * (MAX_CORRIDOR_WIDTH - MIN_CORRIDOR_WIDTH);
  };
}

function formatValue(scaleValueFormatter: (value: number) => string, value: number | null): string {
  return value === null ? "No data" : scaleValueFormatter(value);
}

export default function SpatialResultsMap({ regions, corridors, metricId, mode }: SpatialResultsMapProps) {
  const [hoveredRegionId, setHoveredRegionId] = useState<string | null>(null);
  const [showTable, setShowTable] = useState(false);

  // No manual useMemo below: this project runs the React Compiler (see
  // eslint's react-hooks/preserve-manual-memoization), which auto-memoizes
  // plain derived values -- hand-written useMemo here only risks the
  // compiler being unable to reconcile it and skipping optimization instead.
  const metric = getRegionMetric(metricId);
  const rows = regionRowsFor(regions, metricId, mode);
  const valueFormatter = mode === "delta" ? metric.formatDelta : metric.format;
  const isDivergingView = mode === "delta" || metric.diverging;

  const scale: ColorScale = buildScaleForValues(
    rows.map((row) => row.value),
    isDivergingView,
  );

  const projector = buildProjector(computeBounds([regions, corridors]), VIEW_WIDTH, VIEW_HEIGHT, MAP_PADDING);
  const getCorridorWidth = corridorWidthScale(corridors);
  const hoveredRow = rows.find((row) => row.id === hoveredRegionId) ?? null;

  const rowsSortedByMagnitude = [...rows].sort(
    (a, b) => Math.abs(b.value ?? 0) - Math.abs(a.value ?? 0),
  );

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
          {metric.label}
          {mode === "delta" ? " — change" : ""}
        </p>
        <button
          type="button"
          onClick={() => setShowTable((current) => !current)}
          className="text-xs text-emerald-300 hover:text-emerald-200"
        >
          {showTable ? "View as map" : "View as table"}
        </button>
      </div>

      {showTable ? (
        <div className="mt-4 max-h-[560px] overflow-y-auto rounded-lg border border-white/10">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-zinc-950 text-zinc-500">
              <tr>
                <th className="px-3 py-2 font-medium">Region</th>
                {mode === "delta" ? (
                  <>
                    <th className="px-3 py-2 font-medium">Before</th>
                    <th className="px-3 py-2 font-medium">After</th>
                    <th className="px-3 py-2 font-medium">Change</th>
                  </>
                ) : (
                  <th className="px-3 py-2 font-medium">{metric.label}</th>
                )}
              </tr>
            </thead>
            <tbody className="text-zinc-200">
              {rowsSortedByMagnitude.map((row) => (
                <tr key={row.id} className="border-t border-white/10">
                  <td className="px-3 py-2">{row.name}</td>
                  {mode === "delta" ? (
                    <>
                      <td className="px-3 py-2 font-mono text-zinc-400">{formatValue(metric.format, row.valueA)}</td>
                      <td className="px-3 py-2 font-mono text-zinc-400">{formatValue(metric.format, row.valueB)}</td>
                      <td className="px-3 py-2 font-mono">{formatValue(metric.formatDelta, row.value)}</td>
                    </>
                  ) : (
                    <td className="px-3 py-2 font-mono">{formatValue(metric.format, row.value)}</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <>
          <div className="relative mt-4">
            <svg
              viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
              role="img"
              aria-label={`Map of Greece's 13 regions shaded by ${metric.label.toLowerCase()}`}
              className="h-auto w-full"
            >
              <g>
                {regions.features.map((feature, index) => {
                  const row = rows[index];
                  const d = feature.geometry ? polygonToSvgPath(feature.geometry, projector) : "";
                  if (!d) {
                    return null;
                  }
                  const isHovered = row.id === hoveredRegionId;

                  return (
                    <path
                      key={row.id}
                      d={d}
                      fillRule="evenodd"
                      fill={scale.colorFor(row.value)}
                      stroke={isHovered ? REGION_HOVER_STROKE_COLOR : REGION_STROKE_COLOR}
                      strokeWidth={isHovered ? 2 : 1}
                      tabIndex={0}
                      role="img"
                      aria-label={`${row.name}: ${formatValue(valueFormatter, row.value)}`}
                      onPointerEnter={() => setHoveredRegionId(row.id)}
                      onPointerLeave={() => setHoveredRegionId((current) => (current === row.id ? null : current))}
                      onFocus={() => setHoveredRegionId(row.id)}
                      onBlur={() => setHoveredRegionId((current) => (current === row.id ? null : current))}
                      style={{ cursor: "pointer", outline: "none" }}
                    />
                  );
                })}
              </g>

              <g>
                {corridors.features.map((feature) => {
                  const d = feature.geometry ? lineToSvgPath(feature.geometry, projector) : "";
                  if (!d) {
                    return null;
                  }
                  const capacityMw = readNumber(feature.properties, "s_nom_mw");
                  const id = String(feature.properties?.id ?? "");

                  return (
                    <path
                      key={id}
                      d={d}
                      fill="none"
                      stroke={CORRIDOR_COLOR}
                      strokeWidth={getCorridorWidth(capacityMw)}
                      strokeLinecap="round"
                    >
                      <title>
                        {String(feature.properties?.bus0)} ↔ {String(feature.properties?.bus1)}
                        {capacityMw !== null ? ` — ${Math.round(capacityMw).toLocaleString()} MW capacity` : ""}
                      </title>
                    </path>
                  );
                })}
              </g>
            </svg>

            {hoveredRow && (
              <div className="pointer-events-none absolute left-3 top-3 max-w-[220px] rounded-lg border border-white/10 bg-zinc-950/95 px-3 py-2 text-xs shadow-xl">
                <p className="font-medium text-zinc-100">{hoveredRow.name}</p>
                {mode === "delta" ? (
                  <div className="mt-1 space-y-0.5 text-zinc-400">
                    <p>Before: {formatValue(metric.format, hoveredRow.valueA)}</p>
                    <p>After: {formatValue(metric.format, hoveredRow.valueB)}</p>
                    <p className="text-zinc-100">Change: {formatValue(metric.formatDelta, hoveredRow.value)}</p>
                  </div>
                ) : (
                  <p className="mt-1 text-emerald-300">{formatValue(metric.format, hoveredRow.value)}</p>
                )}
              </div>
            )}
          </div>

          <div className="mt-4">
            <RegionMetricLegend scale={scale} formatValue={valueFormatter} diverging={isDivergingView} />
          </div>

          <p className="mt-3 text-[10px] leading-4 text-zinc-600">
            Corridors are schematic (drawn centroid-to-centroid, not the real physical route) and their thickness
            shows rated transmission capacity, not this metric.
          </p>
        </>
      )}
    </div>
  );
}

