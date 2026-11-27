"use client";

import { BatteryCharging } from "lucide-react";

import { eurPerMwh } from "../../lib/liveMarket/liveMarket.api";
import type { ReserveRequirement, StorageFleetBehaviour } from "../../lib/liveMarket/liveMarket.types";
import DashboardCard from "../overview/DashboardCard";

// Two things a storage investor needs that no model can supply: what the
// batteries already on the system actually did, and how big the market they
// would be bidding into is.
//
// The fleet's revealed round-trip spread is the platform's only real-world
// check on its own storage model -- a simulated battery that charges and
// discharges at prices nothing like these is modelling something else.

type StorageFleetPanelProps = {
  fleet: StorageFleetBehaviour | null;
  reserves: ReserveRequirement[];
};

export default function StorageFleetPanel({ fleet, reserves }: StorageFleetPanelProps) {
  const procured = reserves.filter((reserve) => reserve.mean_mw > 0);
  const largest = procured.reduce((most, reserve) => Math.max(most, reserve.max_mw), 1);

  return (
    <DashboardCard
      title="What the fleet did, and the market it bid into"
      subtitle={fleet ? `${fleet.units} scheduled storage units` : "Operator schedule unavailable"}
    >
      <div className="flex flex-col gap-3.5">
        {fleet ? (
          <>
            <div className="flex items-stretch gap-2">
              <PriceBlock
                label="Charged at"
                value={eurPerMwh(fleet.average_charge_price_eur_per_mwh)}
                detail={`${fleet.charged_mwh.toLocaleString()} MWh over ${fleet.periods_charging} periods`}
                accent="sky"
              />
              <div className="flex shrink-0 flex-col items-center justify-center px-1">
                <BatteryCharging className="h-4 w-4 text-emerald-400" aria-hidden="true" />
                <p className="mt-1 font-display text-sm text-emerald-300">
                  {eurPerMwh(fleet.round_trip_spread_eur_per_mwh, 0)}
                </p>
                <p className="text-[9px] uppercase tracking-wider text-zinc-500">spread</p>
              </div>
              <PriceBlock
                label="Discharged at"
                value={eurPerMwh(fleet.average_discharge_price_eur_per_mwh)}
                detail={`${fleet.discharged_mwh.toLocaleString()} MWh over ${fleet.periods_discharging} periods`}
                accent="rose"
              />
            </div>
            <p className="text-[11px] leading-5 text-zinc-500">
              Scheduled dispatch valued at the balancing prices of the same quarter-hours — a valuation of
              the operator&apos;s schedule, not settled revenue. It is the closest available check on the
              simulator&apos;s own storage physics.
            </p>
          </>
        ) : (
          <p className="text-[11px] text-zinc-500">
            Today&apos;s operator schedule could not be read, so the fleet&apos;s behaviour is unavailable.
          </p>
        )}

        {procured.length > 0 ? (
          <div className="border-t border-white/5 pt-3">
            <p className="mb-2 text-[11px] uppercase tracking-[0.14em] text-zinc-500">
              Reserve procured today
            </p>
            <ul className="flex flex-col gap-1.5">
              {procured.map((reserve) => (
                <li key={reserve.product} className="flex items-center gap-2.5">
                  <span className="w-20 shrink-0 truncate text-[11px] text-zinc-300">
                    {reserve.product}
                  </span>
                  <span className="h-2 flex-1 overflow-hidden rounded-full bg-white/5">
                    <span
                      className="block h-full rounded-full bg-emerald-500/60"
                      style={{ width: `${(reserve.mean_mw / largest) * 100}%` }}
                    />
                  </span>
                  <span className="w-28 shrink-0 text-right font-mono text-[11px] text-zinc-400">
                    {reserve.mean_mw.toFixed(0)}
                    <span className="text-zinc-600"> / {reserve.max_mw.toFixed(0)} MW</span>
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[11px] leading-5 text-zinc-500">
              Mean and peak requirement across the day. This is the size of the market a new battery would
              be competing for, and it is why a fleet of them compresses the spread above.
            </p>
          </div>
        ) : null}
      </div>
    </DashboardCard>
  );
}

function PriceBlock({
  label,
  value,
  detail,
  accent,
}: {
  label: string;
  value: string;
  detail: string;
  accent: "sky" | "rose";
}) {
  const textClass = accent === "rose" ? "text-rose-300" : "text-sky-300";
  const ringClass = accent === "rose" ? "ring-rose-400/20 bg-rose-400/5" : "ring-sky-400/20 bg-sky-400/5";
  return (
    <div className={`flex min-w-0 flex-1 flex-col gap-1 rounded-xl px-3 py-2.5 ring-1 ring-inset ${ringClass}`}>
      <p className="truncate text-[10px] uppercase tracking-[0.14em] text-zinc-500">{label}</p>
      <p className={`font-display text-xl font-semibold tracking-tight ${textClass}`}>{value}</p>
      <p className="truncate text-[10px] text-zinc-500">{detail}</p>
    </div>
  );
}
