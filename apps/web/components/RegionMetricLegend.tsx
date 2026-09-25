"use client";

import { useId } from "react";

import type { ColorScale } from "../lib/spatial/colorScale";

type RegionMetricLegendProps = {
  scale: ColorScale;
  formatValue: (value: number) => string;
  diverging: boolean;
};

// The gradient legend for a region-metric color scale -- shared by the
// Scenario Studio's SVG spatial map and the live map's choropleth, so the two
// views can never drift into different-looking legends for the same scale.
// Unstyled beyond its own gradient bar and labels: each caller wraps it in
// whatever container fits its own layout (a bordered panel, a floating card).
export default function RegionMetricLegend({ scale, formatValue, diverging }: RegionMetricLegendProps) {
  // useId, not Math.random(): a stable id generated the same way on server
  // and client render, unlike a random value (which is also an impure call
  // during render -- see eslint's react-hooks/purity).
  const gradientId = useId();
  const first = scale.stops[0];
  const last = scale.stops[scale.stops.length - 1];
  const middle = scale.stops[Math.floor(scale.stops.length / 2)];

  return (
    <div>
      <svg viewBox="0 0 260 14" className="h-3 w-full max-w-[260px]">
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="0">
            {scale.stops.map((stop, index) => (
              <stop
                key={stop.value}
                offset={`${(index / (scale.stops.length - 1)) * 100}%`}
                stopColor={stop.color}
              />
            ))}
          </linearGradient>
        </defs>
        <rect x={0} y={0} width={260} height={14} rx={3} fill={`url(#${gradientId})`} />
      </svg>
      <div className="mt-1 flex max-w-[260px] justify-between text-[10px] text-zinc-500">
        <span>{formatValue(first.value)}</span>
        {diverging && <span>{formatValue(middle.value)}</span>}
        <span>{formatValue(last.value)}</span>
      </div>
    </div>
  );
}
