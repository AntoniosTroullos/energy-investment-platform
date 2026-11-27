"use client";

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { BalancingDay } from "../../lib/liveMarket/liveMarket.types";

// The operator's own schedule for the market day, quarter-hour by
// quarter-hour: the price to be given energy, the price to absorb it, and what
// the storage fleet was told to do about it.
//
// The gap between the two price lines IS a battery's margin, so they are drawn
// on one axis and the storage bars beneath them share the chart rather than
// sitting in a separate panel -- the point is that the bars line up with the
// gap.

type BalancingDayChartProps = {
  day: BalancingDay;
};

function quarterLabel(timestamp: string): string {
  const moment = new Date(timestamp);
  return Number.isNaN(moment.getTime())
    ? ""
    : moment.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function BalancingDayChart({ day }: BalancingDayChartProps) {
  const data = day.timestamps_utc.map((timestamp, index) => ({
    t: quarterLabel(timestamp),
    up: day.price_up_eur_per_mwh[index] ?? null,
    down: day.price_down_eur_per_mwh[index] ?? null,
    storage: day.storage_mw[index] ?? 0,
  }));

  if (data.length === 0) {
    return <p className="py-8 text-center text-xs text-zinc-500">No schedule published for today yet.</p>;
  }

  const hasNegativeStorage = data.some((row) => row.storage < 0);

  return (
    <div className="flex h-full flex-col">
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 6, right: 4, bottom: 0, left: -20 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis
              dataKey="t"
              tick={{ fontSize: 9, fill: "#5b6471" }}
              interval={Math.max(3, Math.floor(data.length / 8))}
              minTickGap={12}
            />
            <YAxis yAxisId="price" tick={{ fontSize: 9, fill: "#5b6471" }} width={44} />
            <YAxis
              yAxisId="storage"
              orientation="right"
              tick={{ fontSize: 9, fill: "#5b6471" }}
              width={44}
            />
            {hasNegativeStorage ? (
              <ReferenceLine yAxisId="storage" y={0} stroke="rgba(255,255,255,0.12)" />
            ) : null}
            <Tooltip
              contentStyle={{
                background: "#08090b",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 8,
                fontSize: 11,
              }}
              labelStyle={{ color: "#aab1ba" }}
              formatter={(value, name) => {
                if (value === null || value === undefined) return ["—", String(name)];
                const numeric = Number(value);
                if (name === "storage") {
                  return [
                    `${Math.abs(numeric).toFixed(0)} MW ${numeric < 0 ? "charging" : "discharging"}`,
                    "Storage fleet",
                  ];
                }
                return [
                  `€${numeric.toFixed(2)}/MWh`,
                  name === "up" ? "Paid for energy (up)" : "Paid to absorb (down)",
                ];
              }}
            />
            <Bar yAxisId="storage" dataKey="storage" fill="#a78bfa" fillOpacity={0.5} />
            <Line
              yAxisId="price"
              type="stepAfter"
              dataKey="up"
              stroke="#f87171"
              strokeWidth={1.5}
              dot={false}
              connectNulls
            />
            <Line
              yAxisId="price"
              type="stepAfter"
              dataKey="down"
              stroke="#38bdf8"
              strokeWidth={1.5}
              dot={false}
              connectNulls
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-zinc-500">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-rose-400" /> Balancing price up
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-sky-400" /> Balancing price down
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-violet-400" /> Storage fleet (MW)
        </span>
        <span className="ml-auto font-mono text-[10px]">{day.file_name}</span>
      </div>
    </div>
  );
}
