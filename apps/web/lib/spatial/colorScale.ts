// Color for the spatial results choropleth, built per the dataviz skill's
// color formula: magnitude gets one sequential hue, polarity (a value that is
// meaningfully positive or negative -- net position, or any A-vs-B delta)
// gets a two-hue diverging pair with a neutral midpoint. Every hex below is
// from the skill's documented palette, not eyeballed -- see references/palette.md.
// A sequential/diverging ramp is checked for lightness monotonicity, not
// adjacency CVD (that check is for categorical palettes and fails a good
// sequential ramp by design), so there is no separate validator run for these.

export type ColorStop = { value: number; color: string };

// The skill's sequential "blue" ramp (steps 100->700), reversed for a dark
// surface: "flips anchor in dark" -- the near-zero end should recede into the
// dark background (a dark step) and the high end should pop (a light step),
// the opposite of the light-surface ordering.
const SEQUENTIAL_DARK_STOPS: readonly string[] = [
  "#0d366b", // step 700 -- low value, recedes into the dark surface
  "#1c5cab", // step 550
  "#2a78d6", // step 450
  "#6da7ec", // step 300
  "#cde2fb", // step 100 -- high value, pops
];

// The skill's diverging pair (blue <-> red) with its neutral gray midpoint,
// dark-surface steps. Convention used throughout this view: negative (a
// deficit, or B lower than A) = red; positive (a surplus, or B higher than A)
// = blue. Always labelled in the legend, since hue alone should never carry
// that meaning for a colorblind reader.
const DIVERGING_NEGATIVE = "#e66767";
const DIVERGING_NEUTRAL = "#383835";
const DIVERGING_POSITIVE = "#3987e5";

function hexToRgb(hex: string): [number, number, number] {
  const value = parseInt(hex.slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

function rgbToHex([r, g, b]: [number, number, number]): string {
  const channel = (n: number) => Math.round(Math.min(255, Math.max(0, n))).toString(16).padStart(2, "0");
  return `#${channel(r)}${channel(g)}${channel(b)}`;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function interpolateStops(stops: readonly ColorStop[], value: number): string {
  if (value <= stops[0].value) {
    return stops[0].color;
  }
  const last = stops[stops.length - 1];
  if (value >= last.value) {
    return last.color;
  }

  for (let i = 0; i < stops.length - 1; i += 1) {
    const left = stops[i];
    const right = stops[i + 1];
    if (value >= left.value && value <= right.value) {
      const span = right.value - left.value;
      const t = span === 0 ? 0 : (value - left.value) / span;
      const leftRgb = hexToRgb(left.color);
      const rightRgb = hexToRgb(right.color);
      return rgbToHex([
        lerp(leftRgb[0], rightRgb[0], t),
        lerp(leftRgb[1], rightRgb[1], t),
        lerp(leftRgb[2], rightRgb[2], t),
      ]);
    }
  }
  return last.color;
}

export type ColorScale = {
  stops: readonly ColorStop[];
  colorFor: (value: number | null) => string;
  /** Color used for a region with no value at all (missing data), never part
   * of the value ramp itself so it can't be misread as "zero" or "low". */
  missingColor: string;
};

const MISSING_COLOR = "#2c2c2a"; // one step off the dark surface -- reads as "no data", not a data point

export function buildSequentialScale(min: number, max: number): ColorScale {
  // A flat domain (every region equal) still needs a valid scale -- widen it
  // by a hair so interpolateStops has a real span instead of dividing by zero.
  const safeMax = max > min ? max : min + 1;
  const stops: ColorStop[] = SEQUENTIAL_DARK_STOPS.map((color, index) => ({
    value: min + ((safeMax - min) * index) / (SEQUENTIAL_DARK_STOPS.length - 1),
    color,
  }));

  return {
    stops,
    colorFor: (value) => (value === null ? MISSING_COLOR : interpolateStops(stops, value)),
    missingColor: MISSING_COLOR,
  };
}

export function buildDivergingScale(maxAbsoluteValue: number): ColorScale {
  const domainMax = maxAbsoluteValue > 0 ? maxAbsoluteValue : 1;
  const stops: ColorStop[] = [
    { value: -domainMax, color: DIVERGING_NEGATIVE },
    { value: 0, color: DIVERGING_NEUTRAL },
    { value: domainMax, color: DIVERGING_POSITIVE },
  ];

  return {
    stops,
    colorFor: (value) => (value === null ? MISSING_COLOR : interpolateStops(stops, value)),
    missingColor: MISSING_COLOR,
  };
}

/** Builds the right scale for a set of values: diverging when the values
 * themselves are signed around a meaningful zero (net position, or any A-vs-B
 * delta), sequential otherwise. */
export function buildScaleForValues(values: readonly (number | null)[], diverging: boolean): ColorScale {
  const present = values.filter((value): value is number => value !== null);

  if (diverging) {
    const maxAbsoluteValue = present.reduce((max, value) => Math.max(max, Math.abs(value)), 0);
    return buildDivergingScale(maxAbsoluteValue);
  }

  const min = present.length > 0 ? Math.min(...present) : 0;
  const max = present.length > 0 ? Math.max(...present) : 1;
  return buildSequentialScale(min, max);
}

// ---------------------------------------------------------------------------
// Region metric registry -- one definition per metric so the picker, the
// legend, the tooltip, and the table view all read one shared source instead
// of five copies of the same label/unit/formatter.
// ---------------------------------------------------------------------------

export type RegionMetricId =
  | "generation_mwh"
  | "total_load_mwh"
  | "net_position_mwh"
  | "average_marginal_price_eur_per_mwh"
  | "peak_load_mw";

export type RegionMetricDefinition = {
  id: RegionMetricId;
  label: string;
  /** Whether zero is a meaningful midpoint for this metric on its own (only
   * net position today) -- a delta view always uses a diverging scale
   * regardless of this flag, since any A-vs-B difference is signed. */
  diverging: boolean;
  format: (value: number) => string;
  formatDelta: (value: number) => string;
};

function formatGwhPerYear(mwh: number): string {
  return `${(mwh / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 })} GWh/yr`;
}

function formatSignedGwhPerYear(mwh: number): string {
  const sign = mwh > 0 ? "+" : mwh < 0 ? "−" : "±";
  return `${sign}${Math.abs(mwh / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 })} GWh/yr`;
}

function formatEurPerMwh(value: number): string {
  return `€${value.toFixed(1)}/MWh`;
}

function formatSignedEurPerMwh(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "±";
  return `${sign}€${Math.abs(value).toFixed(1)}/MWh`;
}

function formatMw(value: number): string {
  return `${Math.round(value).toLocaleString()} MW`;
}

function formatSignedMw(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "±";
  return `${sign}${Math.round(Math.abs(value)).toLocaleString()} MW`;
}

export const REGION_METRICS: readonly RegionMetricDefinition[] = [
  {
    id: "net_position_mwh",
    label: "Net position (generation − load)",
    diverging: true,
    format: formatSignedGwhPerYear,
    formatDelta: formatSignedGwhPerYear,
  },
  {
    id: "generation_mwh",
    label: "Generation",
    diverging: false,
    format: formatGwhPerYear,
    formatDelta: formatSignedGwhPerYear,
  },
  {
    id: "total_load_mwh",
    label: "Load",
    diverging: false,
    format: formatGwhPerYear,
    formatDelta: formatSignedGwhPerYear,
  },
  {
    id: "average_marginal_price_eur_per_mwh",
    label: "Average marginal price",
    diverging: false,
    format: formatEurPerMwh,
    formatDelta: formatSignedEurPerMwh,
  },
  {
    id: "peak_load_mw",
    label: "Peak load",
    diverging: false,
    format: formatMw,
    formatDelta: formatSignedMw,
  },
];

export function getRegionMetric(id: RegionMetricId): RegionMetricDefinition {
  const metric = REGION_METRICS.find((candidate) => candidate.id === id);
  if (!metric) {
    throw new Error(`Unknown region metric id: ${id}`);
  }
  return metric;
}
