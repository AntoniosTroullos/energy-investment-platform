"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Info } from "lucide-react";

import BalancingDayChart from "../../../components/market/BalancingDayChart";
import BalancingSpreadPanel from "../../../components/market/BalancingSpreadPanel";
import BalancingVsDayAheadPanel from "../../../components/market/BalancingVsDayAheadPanel";
import FeedHealthStrip from "../../../components/market/FeedHealthStrip";
import StorageFleetPanel from "../../../components/market/StorageFleetPanel";
import DashboardCard from "../../../components/overview/DashboardCard";
import { eurPerMwh, getLiveMarket } from "../../../lib/liveMarket/liveMarket.api";
import type { LiveMarketResponse } from "../../../lib/liveMarket/liveMarket.types";

// The live balancing market: settled imbalance prices, the operator's own
// schedule for today, the reserve it is procuring, and how all of that
// compares with day-ahead.
//
// This page exists separately from the national overview because it answers a
// different question. The overview asks what is on the system and where the
// next project should go, from a solved scenario. This asks what the market is
// paying right now, from feeds that update on their own clocks -- and in
// particular whether a storage business case is being priced in the right
// market at all.

export default function MarketPage() {
  const [market, setMarket] = useState<LiveMarketResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback((signal?: AbortSignal) => {
    return getLiveMarket(signal)
      .then((response) => {
        setMarket(response);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (signal?.aborted) return;
        setError(caught instanceof Error ? caught.message : "Could not load the market.");
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const refresh = useCallback(() => {
    setRefreshing(true);
    load().finally(() => setRefreshing(false));
  }, [load]);

  if (error && !market) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-20 text-center">
        <h1 className="font-display text-lg text-zinc-100">The market layer could not load</h1>
        <p className="mt-2 text-sm text-zinc-400">{error}</p>
        <p className="mt-6 text-xs text-zinc-500">
          Assembling a trailing year of settled prices reads about fifty weekly files from IPTO the first
          time. After that it is cached on disk. Try again in a moment.
        </p>
      </main>
    );
  }

  if (!market) {
    return (
      <main className="mx-auto max-w-7xl px-6 py-20">
        <p className="animate-pulse text-center text-sm text-zinc-500">Reading the market…</p>
      </main>
    );
  }

  const { comparison, day, imbalance, mfrr, notes, pricing_attribution, trailing_year } = market;

  return (
    <main className="mx-auto w-full max-w-[1600px] px-4 py-5 sm:px-6">
      <header className="flex flex-wrap items-end justify-between gap-3 pb-4">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight text-zinc-50">
            Balancing Market
          </h1>
          <p className="mt-1 text-xs text-zinc-500">
            Greece · IPTO/ADMIE settlement and scheduling · assembled{" "}
            {new Date(market.generated_at_utc).toLocaleString([], {
              day: "2-digit",
              month: "short",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/overview"
            className="rounded-lg border border-white/10 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:bg-white/5 hover:text-zinc-100"
          >
            National overview
          </Link>
          <Link
            href="/simulate"
            className="rounded-lg bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-300 ring-1 ring-inset ring-emerald-500/30 transition-colors hover:bg-emerald-500/20"
          >
            Simulate a battery on these prices
          </Link>
        </div>
      </header>

      <div className="flex flex-col gap-3">
        <FeedHealthStrip feeds={market.feeds} onRefresh={refresh} refreshing={refreshing} />

        <div className="grid gap-3 xl:grid-cols-2">
          {imbalance ? (
            <BalancingSpreadPanel
              imbalance={imbalance}
              mfrr={mfrr}
              attribution={pricing_attribution}
              settlementFile={market.settlement_file}
            />
          ) : (
            <DashboardCard title="Settled imbalance prices">
              <p className="text-[11px] text-zinc-500">
                IPTO&apos;s settlement files could not be read, so settled prices are unavailable.
              </p>
            </DashboardCard>
          )}

          {comparison ? (
            <BalancingVsDayAheadPanel comparison={comparison} trailingYear={trailing_year} />
          ) : null}
        </div>

        <div className="grid gap-3 xl:grid-cols-[1.4fr_1fr]">
          <DashboardCard
            title="Today, as the operator is running it"
            subtitle={
              day
                ? `${day.periods} quarter-hours · up ${eurPerMwh(
                    day.mean_price_up_eur_per_mwh,
                    0,
                  )} / down ${eurPerMwh(day.mean_price_down_eur_per_mwh, 0)} mean`
                : undefined
            }
          >
            {day ? (
              <BalancingDayChart day={day} />
            ) : (
              <p className="py-8 text-center text-[11px] text-zinc-500">
                Today&apos;s scheduling results are not available.
              </p>
            )}
          </DashboardCard>

          <StorageFleetPanel
            fleet={day?.storage_fleet ?? null}
            reserves={day?.reserve_requirements ?? []}
          />
        </div>

        {notes.length > 0 ? (
          <DashboardCard title="What this says" subtitle="Derived from the feeds above, not asserted">
            <ul className="flex flex-col gap-2">
              {notes.map((note) => (
                <li key={note} className="flex items-start gap-2 text-[11px] leading-5 text-zinc-400">
                  <Info className="mt-0.5 h-3 w-3 shrink-0 text-zinc-600" aria-hidden="true" />
                  <span>{note}</span>
                </li>
              ))}
            </ul>
          </DashboardCard>
        ) : null}
      </div>
    </main>
  );
}
