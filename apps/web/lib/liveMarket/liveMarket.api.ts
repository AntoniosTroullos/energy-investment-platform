import { apiUrl } from "../config";
import type { FeedState, LiveMarketResponse } from "./liveMarket.types";

// /market/live assembles every balancing feed behind one call. The API caches
// each feed on its own cadence, so a repeat call costs nothing and a cold one
// costs a couple of seconds -- which is why the page fetches it separately
// from everything else rather than blocking on it.

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") detail = payload.detail;
    } catch {
      // Keep the status-code message.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function getLiveMarket(signal?: AbortSignal): Promise<LiveMarketResponse> {
  return getJson<LiveMarketResponse>(apiUrl("/market/live"), signal);
}

export function getFeedStates(refresh = false, signal?: AbortSignal): Promise<FeedState[]> {
  return getJson<FeedState[]>(apiUrl(`/market/feeds${refresh ? "?refresh=true" : ""}`), signal);
}

// --- formatting -----------------------------------------------------------

export function eurPerMwh(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined ? "—" : `€${value.toFixed(digits)}`;
}

/** Feed lag in words. Negative lag means the feed publishes ahead of now,
 *  which day-ahead does by design, so it reads as "ahead" rather than a
 *  nonsensical negative age. */
export function describeLag(minutes: number | null): string {
  if (minutes === null) return "coverage unknown";
  const absolute = Math.abs(minutes);
  const amount =
    absolute < 90
      ? `${Math.round(absolute)} min`
      : absolute < 2880
        ? `${(absolute / 60).toFixed(1)} h`
        : `${(absolute / 1440).toFixed(1)} days`;
  if (minutes < -5) return `${amount} ahead`;
  if (absolute < 5) return "current";
  return `${amount} behind`;
}

export function describeAge(minutes: number | null): string {
  if (minutes === null) return "never fetched";
  if (minutes < 1) return "just now";
  if (minutes < 90) return `${Math.round(minutes)} min ago`;
  if (minutes < 2880) return `${(minutes / 60).toFixed(1)} h ago`;
  return `${(minutes / 1440).toFixed(1)} days ago`;
}

export function utcDate(value: string | null | undefined): string {
  if (!value) return "—";
  const moment = new Date(value);
  return Number.isNaN(moment.getTime())
    ? "—"
    : moment.toLocaleDateString([], { day: "2-digit", month: "short", year: "numeric" });
}
