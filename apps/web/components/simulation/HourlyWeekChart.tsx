"use client";

import {
  Area,
  Bar,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { HourlyWindow } from "../../lib/simulation/simulation.types";

// One week, hour by hour: the price the market set, and what the asset did
// about it. This is the view that makes the physics legible -- a battery's
// state of charge sawtoothing against the daily spread, or a solar plant
// flatlining through the hours price went below zero.

type HourlyWeekChartProps = {
  window: HourlyWindow;
  mode: "generation" | "storage";
  capacityMw: number;
};

function hourLabel(timestamp: string): string {
  const moment = new Date(timestamp);
  return Number.isNaN(moment.getTime())
    ? ""
    : moment.toLocaleString([], { weekday: "short", hour: "2-digit" });
}

export default function HourlyWeekChart({ window: hourly, mode, capacityMw }: HourlyWeekChartProps) {
  const data = hourly.timestamps.map((timestamp, index) => ({
    t: hourLabel(timestamp),
    price: hourly.price_eur_per_mwh[index] ?? 0,
    output: hourly.output_mw[index] ?? 0,
    soc: hourly.state_of_charge_mwh[index] ?? 0,
  }));

  if (data.length === 0) {
    return <p className="py-8 text-center text-xs text-zinc-500">No hourly detail for this run.</p>;
  }

  const hasNegative = data.some((row) => row.price < 0);

  return (
    <div className="flex h-full flex-col">
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: -18 }}>
            <defs>
              <linearGradient id="simPriceFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#45d2aa" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#45d2aa" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <XAxis dataKey="t" tick={{ fontSize: 9, fill: "#5b6471" }} interval={23} minTickGap={16} />
            <YAxis
              yAxisId="price"
              tick={{ fontSize: 9, fill: "#5b6471" }}
              width={44}
              label={undefined}
            />
            <YAxis yAxisId="asset" orientation="right" tick={{ fontSize: 9, fill: "#5b6471" }} width={44} />
            {/* Zero matters here: below it a generator stops and a battery is
                paid to charge. */}
            {hasNegative ? <ReferenceLine yAxisId="price" y={0} stroke="#f59e0b" strokeDasharray="3 3" /> : null}
            <Tooltip
              contentStyle={{
                background: "#08090b",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 8,
                fontSize: 11,
              }}
              labelStyle={{ color: "#aab1ba" }}
              formatter={(value, name) => {
                const numeric = Number(value);
                if (name === "price") return [`€${numeric.toFixed(2)}/MWh`, "Price"];
                if (name === "soc") return [`${numeric.toFixed(1)} MWh`, "State of charge"];
                return [`${numeric.toFixed(1)} MW`, mode === "storage" ? "Net to grid" : "Output"];
              }}
            />
            <Area
              yAxisId="price"
              type="monotone"
              dataKey="price"
              stroke="#45d2aa"
              strokeWidth={1.4}
              fill="url(#simPriceFill)"
            />
            {mode === "storage" ? (
              <>
                <Bar yAxisId="asset" dataKey="output" fill="#a78bfa" fillOpacity={0.75} />
                <Line
                  yAxisId="asset"
                  type="monotone"
                  dataKey="soc"
                  stroke="#f5c451"
                  strokeWidth={1.2}
                  dot={false}
                />
              </>
            ) : (
              <Bar yAxisId="asset" dataKey="output" fill="#f5c451" fillOpacity={0.6} />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-zinc-500">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-emerald-400" /> Day-ahead price
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="h-2 w-2 rounded-full"
            style={{ background: mode === "storage" ? "#a78bfa" : "#f5c451" }}
          />
          {mode === "storage" ? "Net to grid (MW)" : `Output (MW of ${capacityMw})`}
        </span>
        {mode === "storage" ? (
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-[#f5c451]" /> State of charge (MWh)
          </span>
        ) : null}
        <span className="ml-auto">{hourly.label}</span>
      </div>
    </div>
  );
}
