"use client";

import { useId } from "react";
import { motion } from "motion/react";
import { Leaf, MapPin } from "lucide-react";

import type { Scenario } from "../lib/scenario/scenario.types";
import { BUDGET_META, BudgetBars, TECHNOLOGY_META } from "./scenario-visuals";

type ScenarioControlsPanelProps = {
  scenario: Scenario;
  onUpdateScenario: (updates: Partial<Scenario>) => void;
};

const BUDGET_TIERS = ["small", "medium", "large"] as const;
const TECHNOLOGIES = ["solar", "wind", "all"] as const;

function qualityLabel(score: number) {
  if (score <= 20) return "Show everything";
  if (score <= 45) return "Show most sites";
  if (score <= 70) return "Only solid sites";
  return "Only the very best";
}

function distanceLabel(km: number) {
  if (km <= 10) return "Close to the grid";
  if (km <= 18) return "Moderate distance";
  return "Far from the grid";
}

export default function ScenarioControlsPanel({
  scenario,
  onUpdateScenario,
}: ScenarioControlsPanelProps) {
  const distanceId = useId();
  const scoreId = useId();
  const scorePercent = scenario.minInvestmentScore;
  const distancePercent = ((scenario.maxConnectionDistanceKm - 5) / (25 - 5)) * 100;

  return (
    <section className="mt-8">
      <h2 className="font-display text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
        Build Your Scenario
      </h2>
      <p className="mt-2 text-xs leading-5 text-zinc-500">
        Four simple choices. Everything below updates the map immediately.
      </p>

      <div className="mt-5 space-y-5">
        {/* 1. Technology */}
        <div>
          <p className="text-sm font-medium text-zinc-200">What do you want to build?</p>
          <div className="mt-2.5 grid grid-cols-3 gap-2.5">
            {TECHNOLOGIES.map((tech) => {
              const meta = TECHNOLOGY_META[tech];
              const isActive = scenario.preferredTechnology === tech;
              return (
                <button
                  key={tech}
                  type="button"
                  onClick={() => onUpdateScenario({ preferredTechnology: tech })}
                  className="relative overflow-hidden rounded-xl border px-3 py-4 text-center transition-colors"
                  style={{
                    borderColor: isActive ? `${meta.color}66` : "rgba(255,255,255,0.1)",
                    background: isActive ? `${meta.color}14` : "rgba(255,255,255,0.03)",
                  }}
                >
                  {isActive ? (
                    <motion.span
                      layoutId="tech-glow"
                      className="pointer-events-none absolute inset-0"
                      style={{
                        boxShadow: `inset 0 0 0 1px ${meta.color}55, 0 8px 24px -8px ${meta.color}66`,
                      }}
                      transition={{ type: "spring", stiffness: 400, damping: 32 }}
                    />
                  ) : null}
                  <meta.Icon
                    className="mx-auto h-6 w-6"
                    style={{ color: isActive ? meta.color : "#9ca3af" }}
                    strokeWidth={1.75}
                  />
                  <p
                    className={`mt-2 text-sm font-medium ${isActive ? "text-zinc-50" : "text-zinc-300"}`}
                  >
                    {meta.label}
                  </p>
                  <p className="mt-0.5 text-[11px] text-zinc-500">{meta.blurb}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* 2. Budget */}
        <div>
          <p className="text-sm font-medium text-zinc-200">How big is the investment?</p>
          <div className="mt-2.5 grid grid-cols-3 gap-2.5">
            {BUDGET_TIERS.map((tier) => {
              const meta = BUDGET_META[tier];
              const isActive = scenario.budgetTier === tier;
              return (
                <button
                  key={tier}
                  type="button"
                  onClick={() => onUpdateScenario({ budgetTier: tier })}
                  className={`rounded-xl border px-3 py-4 text-center transition-colors ${
                    isActive
                      ? "border-emerald-500/40 bg-emerald-500/10"
                      : "border-white/10 bg-white/[0.03] hover:border-white/20"
                  }`}
                >
                  <div className="flex justify-center">
                    <BudgetBars tier={tier} active={isActive} />
                  </div>
                  <p
                    className={`mt-2 text-sm font-medium ${isActive ? "text-emerald-300" : "text-zinc-300"}`}
                  >
                    {meta.label}
                  </p>
                  <p className="mt-0.5 text-[11px] text-zinc-500">{meta.blurb}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* 3. Grid distance */}
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
          <div className="flex items-center justify-between">
            <label htmlFor={distanceId} className="flex items-center gap-2 text-sm font-medium text-zinc-200">
              <MapPin className="h-4 w-4 text-zinc-500" strokeWidth={1.75} />
              How close to the power grid?
            </label>
            <span className="text-xs text-zinc-500">{scenario.maxConnectionDistanceKm} km</span>
          </div>
          <p className="mt-1 text-[11px] text-zinc-500">
            Closer sites are cheaper to connect; farther opens up more land.
          </p>
          <div className="relative mt-4">
            <input
              id={distanceId}
              type="range"
              min="5"
              max="25"
              step="1"
              value={scenario.maxConnectionDistanceKm}
              onChange={(event) =>
                onUpdateScenario({ maxConnectionDistanceKm: Number(event.target.value) })
              }
              className="w-full accent-emerald-400"
            />
            <motion.div
              className="pointer-events-none absolute -top-7 -translate-x-1/2 rounded-md bg-zinc-800 px-2 py-0.5 text-[10px] font-medium text-emerald-300 shadow"
              animate={{ left: `${distancePercent}%` }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
            >
              {distanceLabel(scenario.maxConnectionDistanceKm)}
            </motion.div>
          </div>
          <div className="mt-1 flex justify-between text-[10px] uppercase tracking-wide text-zinc-600">
            <span>Close</span>
            <span>Medium</span>
            <span>Far</span>
          </div>
        </div>

        {/* 4. Quality bar */}
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
          <div className="flex items-center justify-between">
            <label htmlFor={scoreId} className="text-sm font-medium text-zinc-200">
              How strict should the screen be?
            </label>
            <span className="text-xs text-zinc-500">{scenario.minInvestmentScore}/100</span>
          </div>
          <p className="mt-1 text-[11px] text-zinc-500">
            Stricter means fewer, stronger candidates; looser shows more options.
          </p>
          <div className="relative mt-4">
            <div
              className="h-2 w-full rounded-full"
              style={{
                background: "linear-gradient(90deg,#64748b 0%,#f5b942 50%,#22b891 100%)",
              }}
            />
            <input
              id={scoreId}
              type="range"
              min="0"
              max="100"
              step="1"
              value={scenario.minInvestmentScore}
              onChange={(event) =>
                onUpdateScenario({ minInvestmentScore: Number(event.target.value) })
              }
              className="absolute inset-0 top-1/2 h-2 w-full -translate-y-1/2 cursor-pointer appearance-none bg-transparent accent-white [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-zinc-900 [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow"
            />
            <motion.div
              className="pointer-events-none absolute -top-7 -translate-x-1/2 whitespace-nowrap rounded-md bg-zinc-800 px-2 py-0.5 text-[10px] font-medium text-zinc-100 shadow"
              animate={{ left: `${scorePercent}%` }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
            >
              {qualityLabel(scenario.minInvestmentScore)}
            </motion.div>
          </div>
        </div>

        {/* 5. Land toggle */}
        <button
          type="button"
          onClick={() =>
            onUpdateScenario({ excludeLandConstrained: !scenario.excludeLandConstrained })
          }
          className="flex w-full items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-4 text-left transition-colors hover:border-white/20"
        >
          <span className="flex items-center gap-3">
            <Leaf className="h-4 w-4 shrink-0 text-emerald-400" strokeWidth={1.75} />
            <span>
              <span className="block text-sm font-medium text-zinc-200">
                Skip protected &amp; restricted land
              </span>
              <span className="block text-[11px] text-zinc-500">
                Keeps the screen realistic by excluding sites that likely can&rsquo;t be built on
              </span>
            </span>
          </span>
          <span
            className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
              scenario.excludeLandConstrained ? "bg-emerald-500" : "bg-zinc-700"
            }`}
          >
            <motion.span
              className="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow"
              animate={{ left: scenario.excludeLandConstrained ? "22px" : "2px" }}
              transition={{ type: "spring", stiffness: 500, damping: 32 }}
            />
          </span>
        </button>

        {/* Summary */}
        <div className="rounded-xl border border-white/10 bg-zinc-950/60 p-4">
          <p className="font-display text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
            Your Scenario, At A Glance
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <SummaryChip>
              {(() => {
                const meta = TECHNOLOGY_META[scenario.preferredTechnology];
                return (
                  <>
                    <meta.Icon className="h-3.5 w-3.5" style={{ color: meta.color }} strokeWidth={1.75} />
                    {meta.label}
                  </>
                );
              })()}
            </SummaryChip>
            <SummaryChip>{BUDGET_META[scenario.budgetTier].label} budget</SummaryChip>
            <SummaryChip>Within {scenario.maxConnectionDistanceKm} km of the grid</SummaryChip>
            <SummaryChip>{qualityLabel(scenario.minInvestmentScore)}</SummaryChip>
            {scenario.excludeLandConstrained ? (
              <SummaryChip>
                <Leaf className="h-3.5 w-3.5 text-emerald-400" strokeWidth={1.75} />
                Protected land excluded
              </SummaryChip>
            ) : null}
          </div>
        </div>

        <details className="rounded-xl border border-white/10 bg-white/5 p-4">
          <summary className="font-display cursor-pointer text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
            Advanced: Raw Scenario JSON
          </summary>
          <pre className="mt-4 overflow-x-auto whitespace-pre-wrap break-words rounded-lg border border-white/10 bg-zinc-950/90 p-4 font-mono text-[11px] leading-5 text-zinc-300">
            {JSON.stringify(scenario, null, 2)}
          </pre>
        </details>
      </div>
    </section>
  );
}

function SummaryChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-zinc-200">
      {children}
    </span>
  );
}
