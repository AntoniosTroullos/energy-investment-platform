"use client";

import { AlertTriangle, CircleCheck, CircleSlash, RefreshCw } from "lucide-react";

import { describeAge, describeLag } from "../../lib/liveMarket/liveMarket.api";
import type { FeedState } from "../../lib/liveMarket/liveMarket.types";

// Five sources on five different clocks. Nothing useful can be said about "the
// current market" without saying which one a number came from and how old it
// is, so this strip is the first thing on the page rather than a footnote.
//
// The distinction the strip has to carry: a feed can be freshly refreshed and
// still be a fortnight behind, because that is what settlement IS. So lag is
// shown next to the refresh age, and "stale" is judged against each feed's own
// expectation -- settlement is never flagged red for being settlement.

const STATUS_STYLES = {
  live: {
    icon: CircleCheck,
    dot: "bg-emerald-400",
    text: "text-emerald-300",
    ring: "ring-emerald-500/25 bg-emerald-500/5",
  },
  stale: {
    icon: AlertTriangle,
    dot: "bg-amber-400",
    text: "text-amber-300",
    ring: "ring-amber-400/25 bg-amber-400/5",
  },
  unavailable: {
    icon: CircleSlash,
    dot: "bg-rose-400",
    text: "text-rose-300",
    ring: "ring-rose-400/25 bg-rose-400/5",
  },
} as const;

type FeedHealthStripProps = {
  feeds: FeedState[];
  onRefresh?: () => void;
  refreshing?: boolean;
};

export default function FeedHealthStrip({ feeds, onRefresh, refreshing = false }: FeedHealthStripProps) {
  if (feeds.length === 0) return null;

  return (
    <section className="rounded-2xl border border-white/10 bg-zinc-950/70 px-4 py-3 backdrop-blur-sm">
      <div className="mb-2.5 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-display text-[13px] font-semibold tracking-tight text-zinc-100">Feeds</h2>
          <p className="text-[11px] text-zinc-500">
            Each source refreshes on its own cadence. Lag is how far behind now the data reaches, which is
            not the same as how long ago it was fetched.
          </p>
        </div>
        {onRefresh ? (
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            className="flex shrink-0 items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1.5 text-[11px] font-medium text-zinc-300 transition-colors hover:border-emerald-400/40 hover:text-zinc-50 disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 ${refreshing ? "animate-spin" : ""}`} aria-hidden="true" />
            {refreshing ? "Refreshing" : "Refresh all"}
          </button>
        ) : null}
      </div>

      <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {feeds.map((feed) => {
          const style = STATUS_STYLES[feed.status] ?? STATUS_STYLES.unavailable;
          return (
            <li
              key={feed.key}
              className={`flex min-w-0 flex-col gap-1 rounded-xl px-3 py-2.5 ring-1 ring-inset ${style.ring}`}
              title={feed.what_it_is_for}
            >
              <div className="flex items-center gap-2">
                <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${style.dot}`} aria-hidden="true" />
                <p className="truncate text-[11px] font-medium text-zinc-200">{feed.label}</p>
                <span className={`ml-auto shrink-0 text-[10px] uppercase tracking-wider ${style.text}`}>
                  {feed.status}
                </span>
              </div>
              <p className="font-mono text-[11px] text-zinc-300">{describeLag(feed.lag_minutes)}</p>
              <p className="truncate text-[10px] text-zinc-500">
                fetched {describeAge(feed.age_minutes)} · every {formatCadence(feed.cadence_minutes)}
              </p>
              {feed.detail ? <p className="text-[10px] leading-4 text-amber-300/80">{feed.detail}</p> : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function formatCadence(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = minutes / 60;
  return hours < 24 ? `${hours % 1 === 0 ? hours : hours.toFixed(1)} h` : `${(hours / 24).toFixed(0)} d`;
}
