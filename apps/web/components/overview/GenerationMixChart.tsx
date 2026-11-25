"use client";

import { useMemo } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { carrierColor } from "../../lib/overview/overview.api";
import type { OverviewSeries } from "../../lib/overview/overview.types";

// How the system is actually served through the day, stacked by technology.
// The solved snapshots are representative days scaled to a year, so this is
// the shape of a typical day rather than a particular date -- which is the
// useful read anyway: where the renewables sit, and what fills the evening.

type GenerationMixChartProps = {
  series: OverviewSeries;
};

// Dispatchable carriers at the bottom, weather-driven on top, so the stack
// reads the way the merit order does.
const STACK_ORDER = ["lignite", "gas", "hydro", "biomass", "battery", "wind", "solar"];

export default function GenerationMixChart({ series }: GenerationMixChartProps) {
  const { data, carriers } = useMemo(() => {
    const generation = series.generation_mw_by_carrier ?? {};
    const timestamps = series.timestamps ?? [];
    const present = STACK_ORDER.filter((carrier) => (generation[carrier] ?? []).length > 0);

    // One representative day: the first 24 snapshots, which in these solves is
    // one monthly representative day at hourly resolution.
    const length = Math.min(24, timestamps.length);
    const rows = Array.from({ length }, (_, index) => {
      const row: Record<string, number | string> = {
        hour: new Date(timestamps[index]).getUTCHours().toString().padStart(2, "0"),
      };
      for (const carrier of present) {
        row[carrier] = generation[carrier]?.[index] ?? 0;
      }
      return row;
    });
    return { data: rows, carriers: present };
  }, [series]);

  if (data.length === 0) {
    return <p className="py-6 text-center text-xs text-zinc-500">No hourly series for this scenario.</p>;
  }

  return (
    <div className="flex h-full flex-col">
      <div className="h-44 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
            <XAxis dataKey="hour" tick={{ fontSize: 9, fill: "#5b6471" }} interval={3} />
            <YAxis tick={{ fontSize: 9, fill: "#5b6471" }} width={42} />
            <Tooltip
              contentStyle={{
                background: "#08090b",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 8,
                fontSize: 11,
              }}
              labelStyle={{ color: "#aab1ba" }}
              formatter={(value, name) => [`${Math.round(Number(value)).toLocaleString()} MW`, String(name)]}
            />
            {carriers.map((carrier) => (
              <Area
                key={carrier}
                type="monotone"
                dataKey={carrier}
                stackId="mix"
                stroke={carrierColor(carrier)}
                strokeWidth={0.8}
                fill={carrierColor(carrier)}
                fillOpacity={0.55}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
        {carriers.map((carrier) => (
          <span key={carrier} className="flex items-center gap-1.5 text-[11px] capitalize text-zinc-400">
            <span className="h-2 w-2 rounded-full" style={{ background: carrierColor(carrier) }} />
            {carrier}
          </span>
        ))}
      </div>
    </div>
  );
}
