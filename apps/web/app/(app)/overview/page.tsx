"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  BatteryCharging,
  Gauge,
  Leaf,
  TrendingUp,
  Zap,
} from "lucide-react";

import CapturePanel from "../../../components/overview/CapturePanel";
import DashboardCard from "../../../components/overview/DashboardCard";
import GenerationMixChart from "../../../components/overview/GenerationMixChart";
import KpiTile from "../../../components/overview/KpiTile";
import LiveMarketPanel from "../../../components/overview/LiveMarketPanel";
import NationalGridMap, { type GridMapMetric } from "../../../components/overview/NationalGridMap";
import NetworkStressPanel from "../../../components/overview/NetworkStressPanel";
import OpportunitiesTable from "../../../components/overview/OpportunitiesTable";
import PipelinePanel from "../../../components/overview/PipelinePanel";
import {
  formatEur,
  formatGwh,
  formatMw,
  formatPct,
  getCorridors,
  getMarketSignal,
  getOverview,
  getRegionGeometry,
  regionLabel,
} from "../../../lib/overview/overview.api";
import type { MarketSignal, OverviewResponse } from "../../../lib/overview/overview.types";

// The national picture, on one screen: what is on the system, what it is worth
// hour by hour, where the network binds, and where the next project should go.
//
// Four feeds, fetched independently so the page fills in rather than blocking:
// /overview answers from cached files in milliseconds, the geometry is static,
// and the live market calls two third-party APIs and is allowed to be slow.

export default function OverviewPage() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [regionGeometry, setRegionGeometry] = useState<GeoJSON.FeatureCollection | null>(null);
  const [corridorGeometry, setCorridorGeometry] = useState<GeoJSON.FeatureCollection | null>(null);
  const [market, setMarket] = useState<MarketSignal | null>(null);
  const [marketLoading, setMarketLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mapMetric, setMapMetric] = useState<GridMapMetric>("solar_capture");

  useEffect(() => {
    const controller = new AbortController();

    getOverview(undefined, controller.signal)
      .then((response) => {
        setOverview(response);
        return getRegionGeometry(response.case_name, controller.signal);
      })
      .then((geometry) => setRegionGeometry(geometry))
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : "Could not load the overview.");
        }
      });

    getCorridors(controller.signal)
      .then(setCorridorGeometry)
      .catch(() => undefined);

    getMarketSignal(controller.signal)
      .then(setMarket)
      .catch(() => undefined)
      .finally(() => {
        if (!controller.signal.aborted) setMarketLoading(false);
      });

    return () => controller.abort();
  }, []);

  const headline = useMemo(() => buildHeadlines(overview), [overview]);

  const refreshMarket = useCallback(() => {
    setMarketLoading(true);
    getMarketSignal()
      .then(setMarket)
      .catch(() => undefined)
      .finally(() => setMarketLoading(false));
  }, []);

  if (error) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-20 text-center">
        <h1 className="font-display text-lg text-zinc-100">The overview could not load</h1>
        <p className="mt-2 text-sm text-zinc-400">{error}</p>
        <p className="mt-6 text-xs text-zinc-500">
          The API may still be warming its data layers — assembling this view reads the whole generator
          registry the first time. Try again in a moment.
        </p>
      </main>
    );
  }

  if (!overview) {
    return (
      <main className="mx-auto max-w-7xl px-6 py-20">
        <p className="animate-pulse text-center text-sm text-zinc-500">Loading the national picture…</p>
      </main>
    );
  }

  const { fleet, market: modelled, network, opportunities, pipeline, regions, series } = overview;
  const best = opportunities.top[0];

  return (
    <main className="mx-auto w-full max-w-[1600px] px-4 py-5 sm:px-6">
      <header className="flex flex-wrap items-end justify-between gap-3 pb-4">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight text-zinc-50">
            National Grid Overview
          </h1>
          <p className="mt-1 text-xs text-zinc-500">
            Greece · {overview.case_name.replace(/_/g, " ")} · solved for {overview.target_year}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/map"
            className="rounded-lg border border-white/10 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:bg-white/5 hover:text-zinc-100"
          >
            Explore the map
          </Link>
          <Link
            href="/scenarios"
            className="rounded-lg bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-300 ring-1 ring-inset ring-emerald-500/30 transition-colors hover:bg-emerald-500/20"
          >
            Run a scenario
          </Link>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <KpiTile
          label="Operating fleet"
          value={formatMw(fleet.total_capacity_mw)}
          hint={`${formatGwh(fleet.total_generation_mwh)} generated`}
          icon={Zap}
        />
        <KpiTile
          label="Renewable share"
          value={formatPct(fleet.renewable_share_of_generation_pct, 0)}
          hint={`${formatPct(fleet.renewable_share_of_capacity_pct, 0)} of capacity`}
          icon={Leaf}
          tone="positive"
          bar={{ fraction: (fleet.renewable_share_of_generation_pct ?? 0) / 100 }}
        />
        <KpiTile
          label="Peak demand"
          value={formatMw(fleet.peak_load_mw)}
          hint={`${formatGwh(fleet.total_demand_mwh)} a year`}
          icon={Activity}
        />
        <KpiTile
          label="System price"
          value={formatEur(modelled.time_weighted_price_eur_per_mwh, 0)}
          hint={`${formatEur(modelled.load_weighted_price_eur_per_mwh, 0)} load-weighted`}
          icon={Gauge}
        />
        <KpiTile
          label="Solar capture"
          value={formatPct(headline.solarCaptureRate, 0)}
          hint={`${formatEur(headline.solarCapturePrice, 0)} of the average hour`}
          icon={BatteryCharging}
          tone={headline.solarCaptureRate !== null && headline.solarCaptureRate < 70 ? "warning" : "default"}
          bar={{ fraction: (headline.solarCaptureRate ?? 0) / 100 }}
        />
        <KpiTile
          label="Best project IRR"
          value={formatPct(best?.irr_pct)}
          hint={best ? `${best.technology} · ${regionLabel(best.region_id)}` : undefined}
          icon={TrendingUp}
          tone="positive"
        />
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-12">
        <DashboardCard
          title="Grid & opportunity map"
          subtitle="Regions by metric · corridors by loading"
          className="lg:col-span-5 lg:row-span-2"
          bodyClassName="min-h-[520px]"
        >
          <NationalGridMap
            regionGeometry={regionGeometry}
            corridorGeometry={corridorGeometry}
            regions={regions}
            corridors={network.corridors}
            metric={mapMetric}
            onMetricChange={setMapMetric}
          />
        </DashboardCard>

        <DashboardCard
          title="Live day-ahead market"
          subtitle="Real Greek wholesale prices"
          className="lg:col-span-4"
          action={
            <button
              type="button"
              onClick={refreshMarket}
              className="rounded-lg px-2 py-1 text-[11px] text-zinc-400 transition-colors hover:bg-white/5 hover:text-zinc-100"
            >
              Refresh
            </button>
          }
        >
          <LiveMarketPanel signal={market} loading={marketLoading} />
        </DashboardCard>

        <DashboardCard
          title="Capture & cannibalisation"
          subtitle="What each technology is actually paid"
          className="lg:col-span-3"
        >
          <CapturePanel rows={modelled.capture ?? []} systemPrice={modelled.time_weighted_price_eur_per_mwh} />
        </DashboardCard>

        <DashboardCard
          title="Generation through the day"
          subtitle="Representative day, stacked by technology"
          className="lg:col-span-4"
        >
          <GenerationMixChart series={series} />
        </DashboardCard>

        <DashboardCard
          title="Network stress"
          subtitle="Corridor loading and price separation"
          className="lg:col-span-3"
        >
          <NetworkStressPanel network={network} />
        </DashboardCard>

        <DashboardCard
          title="Where to build next"
          subtitle="Ranked by IRR, best site per region"
          className="lg:col-span-7"
        >
          <OpportunitiesTable opportunities={opportunities} />
        </DashboardCard>

        <DashboardCard
          title="Project pipeline"
          subtitle="Licensing registries against the built fleet"
          className="lg:col-span-5"
        >
          <PipelinePanel pipeline={pipeline} fleet={fleet} />
        </DashboardCard>
      </div>

      <section className="mt-3 rounded-2xl border border-white/10 bg-zinc-950/70 px-5 py-4">
        <h2 className="font-display text-[13px] font-semibold tracking-tight text-zinc-100">What this says</h2>
        <ul className="mt-2 grid gap-2 text-xs text-zinc-400 sm:grid-cols-3">
          {headline.takeaways.map((takeaway) => (
            <li key={takeaway} className="flex gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
              <span>{takeaway}</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}

// The takeaways are derived from the same figures the panels show, so the
// summary can never drift from the data above it.
function buildHeadlines(overview: OverviewResponse | null) {
  if (!overview) {
    return { solarCaptureRate: null, solarCapturePrice: null, takeaways: [] as string[] };
  }

  const capture = overview.market.capture ?? [];
  const solar = capture.find((row) => row.carrier === "solar");
  const wind = capture.find((row) => row.carrier === "wind");
  const best = overview.opportunities.top[0];
  const busiest = overview.network.corridors[0];

  const takeaways: string[] = [];

  if (solar?.capture_rate_pct != null) {
    takeaways.push(
      `Solar earns ${formatEur(solar.capture_price_eur_per_mwh, 0)}/MWh — ${formatPct(
        solar.capture_rate_pct,
        0,
      )} of the average hour. Pricing new solar at the system average overstates its revenue by about ${Math.round(
        100 / (solar.capture_rate_pct / 100) - 100,
      )}%.`,
    );
  }
  if (wind?.capture_rate_pct != null) {
    takeaways.push(
      `Wind holds ${formatPct(wind.capture_rate_pct, 0)} of the average price${
        wind.curtailment_pct ? ` with ${formatPct(wind.curtailment_pct, 1)} curtailed` : ""
      } — it is not cannibalised the way solar is, so the siting question for wind is resource, not timing.`,
    );
  }
  if (busiest) {
    takeaways.push(
      `${regionLabel(busiest.from)} → ${regionLabel(busiest.to)} runs at ${formatPct(
        busiest.mean_utilisation_pct,
        0,
      )} of its ${formatMw(busiest.rating_mw)}, the corridor most likely to separate regional prices.`,
    );
  }
  if (best) {
    takeaways.push(
      `Best screened project: ${best.technology} in ${regionLabel(best.region_id)} at ${formatPct(
        best.irr_pct,
      )} IRR.`,
    );
  }

  return {
    solarCaptureRate: solar?.capture_rate_pct ?? null,
    solarCapturePrice: solar?.capture_price_eur_per_mwh ?? null,
    takeaways: takeaways.slice(0, 3),
  };
}
