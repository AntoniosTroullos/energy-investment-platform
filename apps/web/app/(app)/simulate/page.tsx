"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BatteryCharging, Factory, Sun } from "lucide-react";

import DashboardCard from "../../../components/overview/DashboardCard";
import HourlyWeekChart from "../../../components/simulation/HourlyWeekChart";
import SettlementComparisonCard from "../../../components/simulation/SettlementComparisonCard";
import {
  Choice,
  Field,
  Metric,
  NumberInput,
  Toggle,
  formatEur,
  formatPct,
} from "../../../components/simulation/SimulationControls";
import {
  simulateDemandResponse,
  simulateGeneration,
  simulateStorage,
} from "../../../lib/simulation/simulation.api";
import type {
  AssetSimulation,
  DemandResponseResult,
  SettlementBasis,
} from "../../../lib/simulation/simulation.types";

// Hour by hour, for one asset, against the hours the market actually had.
//
// The screening model values a site from annual averages, which is the right
// resolution for ranking hundreds of them. This page is the other end: one
// asset, 8,760 real prices and 8,760 real weather hours, replayed for every
// year of its life.

type Mode = "generation" | "storage" | "demand";

const MODES: { id: Mode; label: string; icon: typeof Sun }[] = [
  { id: "generation", label: "Generation", icon: Sun },
  { id: "storage", label: "Storage", icon: BatteryCharging },
  { id: "demand", label: "Industrial flexibility", icon: Factory },
];

export default function SimulatePage() {
  const [mode, setMode] = useState<Mode>("storage");

  return (
    <main className="mx-auto w-full max-w-[1500px] px-4 py-5 sm:px-6">
      <header className="pb-4">
        <h1 className="font-display text-xl font-semibold tracking-tight text-zinc-50">Asset Simulator</h1>
        <p className="mt-1 max-w-3xl text-xs leading-5 text-zinc-500">
          One asset, hour by hour, against a full year of real Greek day-ahead prices and real weather for
          its location — then replayed for every year of its life with degradation carried through.
        </p>
      </header>

      <div className="flex flex-wrap gap-1.5 pb-4">
        {MODES.map((entry) => {
          const Icon = entry.icon;
          return (
            <button
              key={entry.id}
              type="button"
              onClick={() => setMode(entry.id)}
              className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                entry.id === mode
                  ? "bg-emerald-500/10 text-emerald-300 ring-1 ring-inset ring-emerald-500/30"
                  : "text-zinc-400 hover:bg-white/5 hover:text-zinc-100"
              }`}
            >
              <Icon className="h-3.5 w-3.5" aria-hidden="true" />
              {entry.label}
            </button>
          );
        })}
      </div>

      {mode === "generation" ? <GenerationPanel /> : null}
      {mode === "storage" ? <StoragePanel /> : null}
      {mode === "demand" ? <DemandPanel /> : null}
    </main>
  );
}

function useSimulation<T>(run: () => Promise<T>, deps: unknown[]) {
  const [result, setResult] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const execute = useCallback(() => {
    setBusy(true);
    setError(null);
    run()
      .then((value) => setResult(value))
      .catch((caught: unknown) =>
        setError(caught instanceof Error ? caught.message : "The simulation failed."),
      )
      .finally(() => setBusy(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  // Run once on mount so the page opens with a worked example rather than an
  // empty form.
  useEffect(() => {
    execute();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { result, error, busy, execute };
}

function RunButton({ busy, onClick }: { busy: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className="w-full rounded-lg bg-emerald-500/15 px-3 py-2 text-xs font-semibold text-emerald-300 ring-1 ring-inset ring-emerald-500/30 transition-colors hover:bg-emerald-500/25 disabled:opacity-50"
    >
      {busy ? "Simulating 8,760 hours…" : "Run simulation"}
    </button>
  );
}

function Notes({ notes }: { notes: string[] }) {
  if (notes.length === 0) return null;
  return (
    <ul className="mt-3 flex flex-col gap-1.5">
      {notes.map((note) => (
        <li key={note} className="flex gap-2 text-[11px] leading-5 text-zinc-400">
          <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-emerald-400" />
          <span>{note}</span>
        </li>
      ))}
    </ul>
  );
}

function PriceContext({ simulation }: { simulation: AssetSimulation }) {
  const summary = simulation.price_summary;
  if (!summary) return null;
  return (
    // The window, not the calendar year: a balancing series is a trailing
    // twelve months and straddles two years, so naming one of them would
    // misdescribe it.
    <p className="mt-3 text-[10px] leading-4 text-zinc-600">
      {simulation.price_window || summary.year}: {summary.hours.toLocaleString()} hours, mean €
      {summary.mean_eur_per_mwh}/MWh, range €{summary.min_eur_per_mwh} to €{summary.max_eur_per_mwh},{" "}
      {summary.negative_hours} below zero. {summary.source}.
    </p>
  );
}

// ---------------------------------------------------------------------------
// Generation
// ---------------------------------------------------------------------------

function GenerationPanel() {
  const [carrier, setCarrier] = useState<"solar" | "wind">("solar");
  const [capacity, setCapacity] = useState(100);
  const [latitude, setLatitude] = useState(38.0);
  const [longitude, setLongitude] = useState(23.7);
  const [capex, setCapex] = useState(600);
  const [lifetime, setLifetime] = useState(25);
  const [curtail, setCurtail] = useState(true);

  const { result, error, busy, execute } = useSimulation<AssetSimulation>(
    () =>
      simulateGeneration({
        latitude,
        longitude,
        carrier,
        capacity_mw: capacity,
        capex_eur_per_kw: capex || null,
        lifetime_years: lifetime,
        curtail_at_negative_prices: curtail,
      }),
    [carrier, capacity, latitude, longitude, capex, lifetime, curtail],
  );

  const first = result?.years[0];
  const last = result?.years[result.years.length - 1];

  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
      <DashboardCard title="The plant" subtitle="Site, size and cost" className="lg:col-span-3">
        <div className="flex flex-col gap-3">
          <Field label="Technology">
            <Choice
              value={carrier}
              onChange={setCarrier}
              options={[
                { id: "solar", label: "Solar PV" },
                { id: "wind", label: "Onshore wind" },
              ]}
            />
          </Field>
          <Field label="Capacity"><NumberInput value={capacity} onChange={setCapacity} min={1} suffix="MW" /></Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Latitude"><NumberInput value={latitude} onChange={setLatitude} step={0.1} /></Field>
            <Field label="Longitude"><NumberInput value={longitude} onChange={setLongitude} step={0.1} /></Field>
          </div>
          <Field label="Capex" hint="Overnight cost per kW installed">
            <NumberInput value={capex} onChange={setCapex} min={0} step={25} suffix="€/kW" />
          </Field>
          <Field label="Lifetime"><NumberInput value={lifetime} onChange={setLifetime} min={1} max={40} suffix="yr" /></Field>
          <Toggle
            label="Stop when the price is negative"
            checked={curtail}
            onChange={setCurtail}
            hint="A merchant plant does not pay the market to take its power. One on a contract for difference does — untick to see the difference."
          />
          <RunButton busy={busy} onClick={execute} />
          {error ? <p className="text-[11px] text-rose-300">{error}</p> : null}
        </div>
      </DashboardCard>

      <DashboardCard
        title="A week of operation"
        subtitle="Hourly output against the price that set it"
        className="lg:col-span-9"
      >
        {result?.window ? (
          <HourlyWeekChart window={result.window} mode="generation" capacityMw={result.capacity_mw} />
        ) : (
          <p className="py-10 text-center text-xs text-zinc-500">Run a simulation to see the hours.</p>
        )}
      </DashboardCard>

      {result ? (
        <>
          <DashboardCard title="Lifetime economics" className="lg:col-span-4">
            <div className="grid grid-cols-2 gap-2">
              <Metric label="IRR" value={formatPct(result.irr_pct)} tone={(result.irr_pct ?? 0) > 0 ? "positive" : "negative"} />
              <Metric label="NPV" value={formatEur(result.npv_eur)} tone={(result.npv_eur ?? 0) > 0 ? "positive" : "negative"} />
              <Metric label="Payback" value={result.payback_years ? `${result.payback_years} yr` : "—"} />
              <Metric label="Capex" value={formatEur(result.capex_eur)} />
            </div>
            <Notes notes={result.notes} />
            <PriceContext simulation={result} />
          </DashboardCard>

          <DashboardCard title="Year one" subtitle="What the hours produced" className="lg:col-span-4">
            <div className="grid grid-cols-2 gap-2">
              <Metric label="Generation" value={`${((first?.generation_mwh ?? 0) / 1000).toFixed(1)} GWh`} />
              <Metric label="Capacity factor" value={formatPct(first?.capacity_factor_pct)} />
              <Metric
                label="Capture price"
                value={`€${first?.capture_price_eur_per_mwh?.toFixed(2) ?? "—"}`}
                hint={
                  result.price_summary
                    ? `${formatPct(
                        ((first?.capture_price_eur_per_mwh ?? 0) / result.price_summary.mean_eur_per_mwh) * 100,
                        0,
                      )} of the market mean`
                    : undefined
                }
              />
              <Metric
                label="Curtailed"
                value={`${first?.hours_curtailed ?? 0} h`}
                hint={`${Math.round(first?.curtailed_mwh ?? 0).toLocaleString()} MWh not produced`}
                tone={(first?.hours_curtailed ?? 0) > 0 ? "negative" : "default"}
              />
            </div>
          </DashboardCard>

          <DashboardCard title="Degradation" subtitle="First year against last" className="lg:col-span-4">
            <div className="grid grid-cols-2 gap-2">
              <Metric label="Year 1 output" value={`${((first?.generation_mwh ?? 0) / 1000).toFixed(1)} GWh`} />
              <Metric
                label={`Year ${result.lifetime_years} output`}
                value={`${((last?.generation_mwh ?? 0) / 1000).toFixed(1)} GWh`}
                hint={`${formatPct(last?.output_retention_pct)} retained`}
              />
              <Metric label="Lifetime revenue" value={formatEur(result.lifetime_revenue_eur)} />
              <Metric
                label="Capture price drift"
                value={`€${last?.capture_price_eur_per_mwh?.toFixed(2) ?? "—"}`}
                hint="Output fades evenly across hours, so the price it is paid does not move"
              />
            </div>
          </DashboardCard>
        </>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Storage
// ---------------------------------------------------------------------------

function StoragePanel() {
  const [power, setPower] = useState(50);
  const [energy, setEnergy] = useState(200);
  const [efficiency, setEfficiency] = useState(0.88);
  const [cycleCost, setCycleCost] = useState(6);
  const [gridCharge, setGridCharge] = useState(0);
  const [capex, setCapex] = useState(250);
  const [lifetime, setLifetime] = useState(15);
  // Balancing is the default because it is the market that physically
  // dispatches storage in Greece. Day-ahead remains available for a purely
  // financial arbitrage strategy, which is a real but different business.
  const [settlement, setSettlement] = useState<SettlementBasis>("balancing");

  const { result, error, busy, execute } = useSimulation<AssetSimulation>(
    () =>
      simulateStorage({
        power_mw: power,
        energy_capacity_mwh: energy,
        round_trip_efficiency: efficiency,
        cycle_cost_eur_per_mwh: cycleCost,
        grid_charge_eur_per_mwh: gridCharge,
        capex_eur_per_kwh: capex || null,
        lifetime_years: lifetime,
        settlement,
        compare_settlements: true,
      }),
    [power, energy, efficiency, cycleCost, gridCharge, capex, lifetime, settlement],
  );

  // Numeric fields wait for the Run button -- refiring on every keystroke
  // would be absurd. The settlement toggle does not: it is one click with
  // unambiguous intent, and it changes the answer more than anything else on
  // the form, so leaving the previous market's result beside a flipped toggle
  // would state something false.
  const lastSettlement = useRef(settlement);
  useEffect(() => {
    if (lastSettlement.current === settlement) return;
    lastSettlement.current = settlement;
    execute();
  }, [settlement, execute]);

  const first = result?.storage_years[0];
  const last = result?.storage_years[result.storage_years.length - 1];

  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
      <DashboardCard title="The battery" subtitle="Physics and cost" className="lg:col-span-3">
        <div className="flex flex-col gap-3">
          <Field
            label="Settled against"
            hint="Balancing is where Greek storage is actually dispatched and priced. Day-ahead values a purely financial arbitrage strategy."
          >
            <Choice
              options={[
                { id: "balancing", label: "Balancing" },
                { id: "day_ahead", label: "Day-ahead" },
              ]}
              value={settlement}
              onChange={setSettlement}
            />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Power"><NumberInput value={power} onChange={setPower} min={1} suffix="MW" /></Field>
            <Field label="Energy"><NumberInput value={energy} onChange={setEnergy} min={1} suffix="MWh" /></Field>
          </div>
          <Field label="Round-trip efficiency" hint="Split as the square root each way, so a 0.88 round trip loses about 6% on each leg">
            <NumberInput value={efficiency} onChange={setEfficiency} min={0.3} max={1} step={0.01} />
          </Field>
          <Field label="Cycle cost" hint="What a MWh of throughput costs in wear. Without it a battery chases spreads that earn revenue and destroy value.">
            <NumberInput value={cycleCost} onChange={setCycleCost} min={0} step={0.5} suffix="€/MWh" />
          </Field>
          <Field label="Network charge" hint="Paid on both legs — charging and discharging">
            <NumberInput value={gridCharge} onChange={setGridCharge} min={0} step={1} suffix="€/MWh" />
          </Field>
          <Field label="Capex"><NumberInput value={capex} onChange={setCapex} min={0} step={10} suffix="€/kWh" /></Field>
          <Field label="Lifetime"><NumberInput value={lifetime} onChange={setLifetime} min={1} max={30} suffix="yr" /></Field>
          <RunButton busy={busy} onClick={execute} />
          {error ? <p className="text-[11px] text-rose-300">{error}</p> : null}
        </div>
      </DashboardCard>

      <DashboardCard
        title="A week of trading"
        subtitle="State of charge and grid exchange against the price"
        className="lg:col-span-9"
      >
        {result?.window ? (
          <HourlyWeekChart
            window={result.window}
            mode="storage"
            capacityMw={result.capacity_mw}
            priceLabel={
              result.settlement === "balancing" ? "Settled balancing price" : "Day-ahead price"
            }
          />
        ) : (
          <p className="py-10 text-center text-xs text-zinc-500">Run a simulation to see the hours.</p>
        )}
      </DashboardCard>

      {result && first ? (
        <>
          <DashboardCard title="Lifetime economics" className="lg:col-span-4">
            <div className="grid grid-cols-2 gap-2">
              <Metric label="IRR" value={formatPct(result.irr_pct)} tone={(result.irr_pct ?? 0) > 0 ? "positive" : "negative"} />
              <Metric label="NPV" value={formatEur(result.npv_eur)} tone={(result.npv_eur ?? 0) > 0 ? "positive" : "negative"} />
              <Metric label="Payback" value={result.payback_years ? `${result.payback_years} yr` : "—"} />
              <Metric label="Capex" value={formatEur(result.capex_eur)} />
            </div>
            <Notes notes={result.notes} />
            <PriceContext simulation={result} />
          </DashboardCard>

          <DashboardCard
            title="Which market"
            subtitle="Same battery, both settlement bases"
            className="lg:col-span-4"
          >
            <SettlementComparisonCard result={result} />
          </DashboardCard>

          <DashboardCard title="Year one trading" className="lg:col-span-4">
            <div className="grid grid-cols-2 gap-2">
              <Metric
                label="Bought at"
                value={`€${first.average_charge_price_eur_per_mwh?.toFixed(2) ?? "—"}`}
                hint={`${Math.round(first.energy_charged_mwh).toLocaleString()} MWh`}
              />
              <Metric
                label="Sold at"
                value={`€${first.average_discharge_price_eur_per_mwh?.toFixed(2) ?? "—"}`}
                hint={`${Math.round(first.energy_discharged_mwh).toLocaleString()} MWh`}
                tone="positive"
              />
              <Metric label="Full cycles" value={`${first.equivalent_full_cycles.toFixed(0)}/yr`} />
              <Metric
                label="Gross margin"
                value={formatEur(first.gross_margin_eur)}
                hint={`after €${Math.round(first.cycle_cost_eur).toLocaleString()} of wear`}
              />
            </div>
            <p className="mt-3 text-[10px] leading-4 text-zinc-600">
              Charged in {first.negative_price_hours_charged} hours of negative prices — paid to take energy
              off the system. Round-trip losses{" "}
              {Math.round(first.energy_charged_mwh - first.energy_discharged_mwh).toLocaleString()} MWh.
            </p>
          </DashboardCard>

          <DashboardCard title="Degradation" subtitle="Capacity fade over life" className="lg:col-span-4">
            <div className="grid grid-cols-2 gap-2">
              <Metric label="Year 1 retention" value={formatPct(first.capacity_retention_pct)} />
              <Metric
                label={`Year ${result.lifetime_years} retention`}
                value={formatPct(last?.capacity_retention_pct)}
                tone="negative"
              />
              <Metric label="Year 1 margin" value={formatEur(first.gross_margin_eur)} />
              <Metric label={`Year ${result.lifetime_years} margin`} value={formatEur(last?.gross_margin_eur)} />
            </div>
            <div className="mt-3 flex h-10 items-end gap-0.5">
              {result.storage_years.map((year) => (
                <span
                  key={year.year_index}
                  title={`Year ${year.year_index + 1}: ${year.capacity_retention_pct}%`}
                  className="flex-1 rounded-t bg-emerald-500/50"
                  style={{ height: `${Math.max(4, (year.capacity_retention_pct - 60) * 2.5)}%` }}
                />
              ))}
            </div>
          </DashboardCard>
        </>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Industrial flexibility
// ---------------------------------------------------------------------------

function DemandPanel() {
  const [profile, setProfile] = useState<"continuous" | "two_shift">("continuous");
  const [load, setLoad] = useState(80);
  const [interruptible, setInterruptible] = useState(0.4);
  const [productionLoss, setProductionLoss] = useState(120);
  const [rebound, setRebound] = useState(0.6);
  const [shiftable, setShiftable] = useState(0);
  const [type1Mw, setType1Mw] = useState(30);
  const [type1Activation, setType1Activation] = useState(250);
  const [type2Mw, setType2Mw] = useState(15);
  const [type2Activation, setType2Activation] = useState(400);

  const { result, error, busy, execute } = useSimulation<DemandResponseResult>(
    () =>
      simulateDemandResponse({
        name: "Industrial site",
        profile,
        average_load_mw: load,
        base_load_mw: Math.round(load * 0.25),
        interruptible_fraction: interruptible,
        production_loss_eur_per_mwh: productionLoss,
        rebound_fraction: rebound,
        shiftable_fraction: shiftable,
        contracts: [
          ...(type1Mw > 0
            ? [
                {
                  product: "type_1" as const,
                  contracted_mw: type1Mw,
                  activation_price_eur_per_mwh: type1Activation,
                },
              ]
            : []),
          ...(type2Mw > 0
            ? [
                {
                  product: "type_2" as const,
                  contracted_mw: type2Mw,
                  activation_price_eur_per_mwh: type2Activation,
                },
              ]
            : []),
        ],
      }),
    [profile, load, interruptible, productionLoss, rebound, shiftable, type1Mw, type1Activation, type2Mw, type2Activation],
  );

  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
      <DashboardCard title="The site" subtitle="Load and what it can give up" className="lg:col-span-3">
        <div className="flex flex-col gap-3">
          <Field label="Process">
            <Choice
              value={profile}
              onChange={setProfile}
              options={[
                { id: "continuous", label: "Continuous" },
                { id: "two_shift", label: "Two-shift" },
              ]}
            />
          </Field>
          <Field label="Average load"><NumberInput value={load} onChange={setLoad} min={1} suffix="MW" /></Field>
          <Field label="Interruptible share" hint="What the process can physically drop on a call">
            <NumberInput value={interruptible} onChange={setInterruptible} min={0} max={1} step={0.05} />
          </Field>
          <Field
            label="Production loss"
            hint="Foregone output, scrapped work in progress and restart, per MWh not consumed. The number the whole case turns on."
          >
            <NumberInput value={productionLoss} onChange={setProductionLoss} min={0} step={10} suffix="€/MWh" />
          </Field>
          <Field label="Rebound share" hint="Output made up later, in hours the site does not choose">
            <NumberInput value={rebound} onChange={setRebound} min={0} max={1} step={0.1} />
          </Field>
          <Field label="Shiftable share" hint="Load that can move within the day rather than be lost">
            <NumberInput value={shiftable} onChange={setShiftable} min={0} max={1} step={0.05} />
          </Field>
          <RunButton busy={busy} onClick={execute} />
          {error ? <p className="text-[11px] text-rose-300">{error}</p> : null}
        </div>
      </DashboardCard>

      <DashboardCard title="Interruptibility contracts" subtitle="What ADMIE pays to hold the option" className="lg:col-span-3">
        <div className="flex flex-col gap-3">
          <p className="text-[10px] leading-4 text-zinc-500">
            Availability defaults to the last published auction caps — €70k/MW·yr for Type 1, €50k for
            Type 2, which is capped near 24 hours of calls a year.
          </p>
          <Field label="Type 1 contracted"><NumberInput value={type1Mw} onChange={setType1Mw} min={0} suffix="MW" /></Field>
          <Field label="Type 1 activation price"><NumberInput value={type1Activation} onChange={setType1Activation} min={0} step={10} suffix="€/MWh" /></Field>
          <Field label="Type 2 contracted"><NumberInput value={type2Mw} onChange={setType2Mw} min={0} suffix="MW" /></Field>
          <Field label="Type 2 activation price"><NumberInput value={type2Activation} onChange={setType2Activation} min={0} step={10} suffix="€/MWh" /></Field>
        </div>
      </DashboardCard>

      <DashboardCard title="What flexibility is worth" subtitle="A year on real prices" className="lg:col-span-6">
        {result ? (
          <div className="flex h-full flex-col">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <Metric label="Net benefit" value={formatEur(result.net_benefit_eur)} tone={result.net_benefit_eur > 0 ? "positive" : "negative"} hint={`${formatPct(result.net_benefit_pct_of_energy_bill)} of the energy bill`} />
              <Metric label="Energy bill" value={formatEur(result.baseline_energy_cost_eur)} hint={`${Math.round(result.annual_consumption_mwh).toLocaleString()} MWh`} />
              <Metric label="Calls" value={`${result.activation_count}`} hint={`${result.activation_hours} h, ${Math.round(result.energy_not_consumed_mwh).toLocaleString()} MWh`} />
            </div>

            <div className="mt-3 flex flex-col gap-1.5">
              {[
                { label: "Availability payment", value: result.availability_revenue_eur, sign: 1 },
                { label: "Activation payment", value: result.activation_revenue_eur, sign: 1 },
                { label: "Energy not bought", value: result.avoided_energy_cost_eur, sign: 1 },
                { label: "Load shifting", value: result.load_shifting_saving_eur, sign: 1 },
                { label: "Production loss", value: result.production_loss_eur, sign: -1 },
                { label: "Rebound energy", value: result.rebound_cost_eur, sign: -1 },
              ]
                .filter((row) => row.value !== 0)
                .map((row) => {
                  const magnitude = Math.abs(row.value);
                  const widest = Math.max(
                    result.availability_revenue_eur,
                    result.activation_revenue_eur,
                    result.production_loss_eur,
                    result.load_shifting_saving_eur,
                    1,
                  );
                  return (
                    <div key={row.label}>
                      <div className="flex items-baseline justify-between gap-2 text-[11px]">
                        <span className="text-zinc-300">{row.label}</span>
                        <span className={`font-mono ${row.sign > 0 ? "text-emerald-300" : "text-rose-300"}`}>
                          {row.sign > 0 ? "+" : "−"}
                          {formatEur(magnitude)}
                        </span>
                      </div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/5">
                        <div
                          className={`h-full rounded-full ${row.sign > 0 ? "bg-emerald-500/70" : "bg-rose-500/60"}`}
                          style={{ width: `${Math.min(100, (magnitude / widest) * 100)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>

            <Notes notes={result.notes} />
            <p className="mt-auto pt-3 text-[10px] leading-4 text-zinc-600">
              Calls land in the year&apos;s dearest hours, because system shortage is what a high price is.
              Prices: {result.price_source}.
            </p>
          </div>
        ) : (
          <p className="py-10 text-center text-xs text-zinc-500">Run a simulation to value the flexibility.</p>
        )}
      </DashboardCard>

      {result && result.events.length > 0 ? (
        <DashboardCard title="When the operator called" subtitle="Every activation, in price order" className="lg:col-span-12">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] border-collapse text-left text-[11px]">
              <thead>
                <tr className="text-[10px] uppercase tracking-[0.12em] text-zinc-500">
                  <th className="px-1 pb-2 font-medium">Hour of year</th>
                  <th className="px-1 pb-2 font-medium">Duration</th>
                  <th className="px-1 pb-2 text-right font-medium">Price then</th>
                  <th className="px-1 pb-2 text-right font-medium">Not consumed</th>
                  <th className="px-1 pb-2 text-right font-medium">Paid</th>
                  <th className="px-1 pb-2 text-right font-medium">Energy saved</th>
                  <th className="px-1 pb-2 text-right font-medium">Production loss</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {result.events.slice(0, 12).map((event) => (
                  <tr key={event.start_hour} className="text-zinc-300">
                    <td className="px-1 py-1.5 font-mono text-zinc-400">{event.start_hour}</td>
                    <td className="px-1 py-1.5 text-zinc-400">{event.duration_hours} h</td>
                    <td className="px-1 py-1.5 text-right font-mono">€{event.price_at_activation_eur_per_mwh}</td>
                    <td className="px-1 py-1.5 text-right font-mono text-zinc-400">{Math.round(event.energy_not_consumed_mwh)} MWh</td>
                    <td className="px-1 py-1.5 text-right font-mono text-emerald-300">{formatEur(event.payment_eur)}</td>
                    <td className="px-1 py-1.5 text-right font-mono text-emerald-300">{formatEur(event.avoided_energy_cost_eur)}</td>
                    <td className="px-1 py-1.5 text-right font-mono text-rose-300">{formatEur(event.production_loss_eur)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.events.length > 12 ? (
            <p className="mt-2 text-[10px] text-zinc-600">
              Showing the 12 highest-priced of {result.events.length} activations.
            </p>
          ) : null}
        </DashboardCard>
      ) : null}
    </div>
  );
}
