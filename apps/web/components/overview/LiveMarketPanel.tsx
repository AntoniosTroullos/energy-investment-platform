"use client";

import { Area, AreaChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatEur, formatMw, formatPct } from "../../lib/overview/overview.api";
import type { MarketSignal } from "../../lib/overview/overview.types";

// The live side of the dashboard: the real Greek day-ahead curve, and what
// each technology would earn against it. The capture figures are the same
// quantity the modelled scenario reports, computed here on real prices, so the
// two can be read side by side.

type LiveMarketPanelProps = {
  signal: MarketSignal | null;
  loading: boolean;
};

function hourLabel(timestamp: string): string {
  const moment = new Date(timestamp);
  return Number.isNaN(moment.getTime())
    ? ""
    : moment.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function LiveMarketPanel({ signal, loading }: LiveMarketPanelProps) {
  if (loading) {
    return <p className="py-8 text-center text-xs text-zinc-500">Fetching the live market…</p>;
  }
  if (!signal || signal.status !== "success") {
    return (
      <p className="py-8 text-center text-xs text-zinc-500">
        The live market feed is unavailable right now. Everything else on this page is unaffected.
      </p>
    );
  }

  const curve = signal.dayAheadCurve;
  const chartData =
    curve?.points.map((point) => ({
      t: hourLabel(point.timestamp),
      price: point.priceEurMwh,
    })) ?? [];

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="grid grid-cols-3 gap-2">
        <div>
          <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">Mean</p>
          <p className="font-display text-lg text-zinc-50">{formatEur(curve?.meanEurMwh, 0)}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">Range</p>
          <p className="font-display text-lg text-zinc-50">
            {formatEur(curve?.minEurMwh, 0)}–{formatEur(curve?.maxEurMwh, 0)}
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">Net flow</p>
          <p className="font-display text-lg text-zinc-50">
            {signal.netImportMw >= 0 ? "+" : ""}
            {formatMw(signal.netImportMw)}
          </p>
        </div>
      </div>

      <div className="h-32 w-full">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -18 }}>
              <defs>
                <linearGradient id="dayAheadFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#45d2aa" stopOpacity={0.45} />
                  <stop offset="100%" stopColor="#45d2aa" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <XAxis dataKey="t" tick={{ fontSize: 9, fill: "#5b6471" }} interval="preserveStartEnd" minTickGap={48} />
              <YAxis tick={{ fontSize: 9, fill: "#5b6471" }} width={38} />
              {/* Negative prices are the hours a renewable project earns
                  nothing -- worth marking, not smoothing away. */}
              <ReferenceLine y={0} stroke="#434b56" strokeDasharray="3 3" />
              <Tooltip
                contentStyle={{
                  background: "#08090b",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: 8,
                  fontSize: 11,
                }}
                labelStyle={{ color: "#aab1ba" }}
                formatter={(value) => [`€${Number(value).toFixed(2)}/MWh`, "Day-ahead"]}
              />
              <Area type="monotone" dataKey="price" stroke="#45d2aa" strokeWidth={1.6} fill="url(#dayAheadFill)" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-zinc-500">No curve available.</div>
        )}
      </div>

      {curve && curve.capture.length > 0 ? (
        <div className="grid grid-cols-2 gap-2">
          {curve.capture.map((entry) => (
            <div key={entry.carrier} className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">{entry.carrier} capture</p>
              <p className="font-display text-base text-zinc-50">{formatEur(entry.capturePriceEurMwh, 0)}</p>
              <p className="text-[11px] text-zinc-500">
                {formatPct(entry.captureRatePct, 0)} of the flat mean
              </p>
            </div>
          ))}
        </div>
      ) : null}

      <p className="mt-auto text-[10px] leading-relaxed text-zinc-600">
        {curve ? `${curve.pointCount} points · ${curve.source}` : signal.summary}
        {curve && curve.negativePricePoints > 0 ? ` · ${curve.negativePricePoints} negative` : ""}
      </p>
    </div>
  );
}
