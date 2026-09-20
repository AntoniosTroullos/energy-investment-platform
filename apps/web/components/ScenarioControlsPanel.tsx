"use client";

import type { Scenario } from "../lib/scenario/scenario.types";

type ScenarioControlsPanelProps = {
  scenario: Scenario;
  onUpdateScenario: (updates: Partial<Scenario>) => void;
};

export default function ScenarioControlsPanel({
  scenario,
  onUpdateScenario,
}: ScenarioControlsPanelProps) {
  return (
    <section className="mt-8">
      <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
        Scenario Controls
      </h2>
      <div className="mt-4 space-y-4">
        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <label
            htmlFor="budget-tier"
            className="text-sm font-medium text-zinc-100"
          >
            Budget Tier
          </label>
          <select
            id="budget-tier"
            value={scenario.budgetTier}
            onChange={(event) =>
              onUpdateScenario({
                budgetTier: event.target.value as Scenario["budgetTier"],
              })
            }
            className="mt-3 w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-3 text-sm text-zinc-100 outline-none focus:border-emerald-400"
          >
            <option value="small">Small</option>
            <option value="medium">Medium</option>
            <option value="large">Large</option>
          </select>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <label
            htmlFor="preferred-technology"
            className="text-sm font-medium text-zinc-100"
          >
            Preferred Technology
          </label>
          <select
            id="preferred-technology"
            value={scenario.preferredTechnology}
            onChange={(event) =>
              onUpdateScenario({
                preferredTechnology:
                  event.target.value as Scenario["preferredTechnology"],
              })
            }
            className="mt-3 w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-3 text-sm text-zinc-100 outline-none focus:border-emerald-400"
          >
            <option value="all">All</option>
            <option value="solar">Solar</option>
            <option value="wind">Wind</option>
          </select>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <div className="flex items-center justify-between">
            <label
              htmlFor="max-connection-distance"
              className="text-sm font-medium text-zinc-100"
            >
              Max Connection Distance
            </label>
            <span className="text-sm text-emerald-300">
              {scenario.maxConnectionDistanceKm} km
            </span>
          </div>
          <input
            id="max-connection-distance"
            type="range"
            min="5"
            max="25"
            step="1"
            value={scenario.maxConnectionDistanceKm}
            onChange={(event) =>
              onUpdateScenario({
                maxConnectionDistanceKm: Number(event.target.value),
              })
            }
            className="mt-3 w-full accent-emerald-400"
          />
        </div>

        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <div className="flex items-center justify-between">
            <label
              htmlFor="minimum-investment-score"
              className="text-sm font-medium text-zinc-100"
            >
              Minimum Investment Score
            </label>
            <span className="text-sm text-emerald-300">
              {scenario.minInvestmentScore}
            </span>
          </div>
          <input
            id="minimum-investment-score"
            type="range"
            min="0"
            max="100"
            step="1"
            value={scenario.minInvestmentScore}
            onChange={(event) =>
              onUpdateScenario({
                minInvestmentScore: Number(event.target.value),
              })
            }
            className="mt-3 w-full accent-emerald-400"
          />
        </div>

        <label className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 px-4 py-4 text-sm text-zinc-100">
          <input
            type="checkbox"
            checked={scenario.excludeLandConstrained}
            onChange={(event) =>
              onUpdateScenario({
                excludeLandConstrained: event.target.checked,
              })
            }
            className="h-4 w-4 rounded border-white/20 bg-zinc-800 text-emerald-400 focus:ring-emerald-400"
          />
          <span>Exclude land-constrained cells</span>
        </label>

        <div className="rounded-xl border border-white/10 bg-zinc-950/90 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
            Current Scenario
          </p>
          <div className="mt-4 space-y-2 text-sm text-zinc-100">
            <p>Budget: {capitalizeWord(scenario.budgetTier)}</p>
            <p>
              Preferred technology:{" "}
              {scenario.preferredTechnology === "all"
                ? "All"
                : capitalizeWord(scenario.preferredTechnology)}
            </p>
            <p>
              Max connection distance: {scenario.maxConnectionDistanceKm} km
            </p>
            <p>Minimum investment score: {scenario.minInvestmentScore}</p>
            <p>
              Land constrained:{" "}
              {scenario.excludeLandConstrained ? "Excluded" : "Included"}
            </p>
          </div>
        </div>

        <details className="rounded-xl border border-white/10 bg-white/5 p-4">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
            Scenario Debug
          </summary>
          <pre className="mt-4 overflow-x-auto whitespace-pre-wrap break-words rounded-lg border border-white/10 bg-zinc-950/90 p-4 font-mono text-[11px] leading-5 text-zinc-300">
            {JSON.stringify(scenario, null, 2)}
          </pre>
        </details>
      </div>
    </section>
  );
}

function capitalizeWord(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
