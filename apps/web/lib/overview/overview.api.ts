import { apiUrl } from "../config";
import type { MarketSignal, OverviewResponse } from "./overview.types";

// The dashboard's two feeds are fetched separately on purpose. /overview is
// assembled from files the API has already cached and answers in milliseconds;
// /market/greece calls IPTO and a price API live and can take seconds. Keeping
// them apart means the page paints its numbers immediately and fills in the
// live strip when it arrives, instead of holding everything for the slowest
// upstream.

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export function getOverview(caseName?: string, signal?: AbortSignal): Promise<OverviewResponse> {
  const query = caseName ? `?case_name=${encodeURIComponent(caseName)}` : "";
  return getJson<OverviewResponse>(apiUrl(`/overview${query}`), signal);
}

export function getMarketSignal(signal?: AbortSignal): Promise<MarketSignal> {
  return getJson<MarketSignal>(apiUrl("/market/greece"), signal);
}

export function getRegionGeometry(caseName: string, signal?: AbortSignal): Promise<GeoJSON.FeatureCollection> {
  return getJson<GeoJSON.FeatureCollection>(
    apiUrl(`/scenarios/${encodeURIComponent(caseName)}/map/regions`),
    signal,
  );
}

export function getCorridors(signal?: AbortSignal): Promise<GeoJSON.FeatureCollection> {
  return getJson<GeoJSON.FeatureCollection>(apiUrl("/scenarios/network-topology"), signal);
}

// --- formatting shared across the dashboard's panels ----------------------

export function formatMw(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return "—";
  if (Math.abs(value) >= 1000) {
    return `${(value / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 })} GW`;
  }
  return `${value.toLocaleString(undefined, { maximumFractionDigits: digits })} MW`;
}

export function formatGwh(mwh: number | null | undefined): string {
  if (mwh === null || mwh === undefined) return "—";
  if (Math.abs(mwh) >= 1_000_000) {
    return `${(mwh / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 1 })} TWh`;
  }
  return `${(mwh / 1000).toLocaleString(undefined, { maximumFractionDigits: 0 })} GWh`;
}

export function formatEur(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—";
  return `€${value.toLocaleString(undefined, { maximumFractionDigits: digits })}`;
}

export function formatMoney(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000_000) return `€${(value / 1_000_000_000).toFixed(2)}bn`;
  if (absolute >= 1_000_000) return `€${(value / 1_000_000).toFixed(1)}m`;
  if (absolute >= 1_000) return `€${(value / 1_000).toFixed(0)}k`;
  return `€${value.toFixed(0)}`;
}

export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(digits)}%`;
}

export function regionLabel(regionId: string | null | undefined): string {
  return (regionId ?? "").replace(/_/g, " ");
}

// Carrier colours, shared by every chart on the page so one technology is one
// colour everywhere. Keyed to the app's emerald-led palette rather than a
// default categorical scale.
export const CARRIER_COLORS: Record<string, string> = {
  solar: "#f5c451",
  wind: "#45d2aa",
  hydro: "#4aa8e0",
  gas: "#c97e63",
  lignite: "#8a7f72",
  oil: "#9a6b8f",
  biomass: "#7fae5c",
  battery: "#a78bfa",
  unknown: "#5b6471",
};

export function carrierColor(carrier: string): string {
  return CARRIER_COLORS[carrier.toLowerCase()] ?? CARRIER_COLORS.unknown;
}
