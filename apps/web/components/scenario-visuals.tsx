"use client";

// Small, shared visual building blocks for the Scenario Builder: icons and
// mini-widgets standing in for jargon (technology codes, "budget tier",
// "investment score") so the controls read at a glance instead of needing
// domain knowledge to parse.

import { Sun, Wind, Sparkles, Leaf, Rocket, ShieldCheck } from "lucide-react";
import type { BudgetTier, PreferredTechnology } from "../lib/scenario/scenario.types";

export const TECHNOLOGY_META: Record<
  PreferredTechnology,
  { label: string; blurb: string; Icon: typeof Sun; color: string }
> = {
  solar: {
    label: "Solar",
    blurb: "Sun-powered sites",
    Icon: Sun,
    color: "#f5b942",
  },
  wind: {
    label: "Wind",
    blurb: "Turbine sites",
    Icon: Wind,
    color: "#45d2aa",
  },
  all: {
    label: "Either",
    blurb: "Solar or wind",
    Icon: Sparkles,
    color: "#9aa3ff",
  },
};

export const PRESET_META: Record<
  string,
  { Icon: typeof Sun; color: string }
> = {
  "Solar-first": { Icon: Sun, color: "#f5b942" },
  "Wind-first": { Icon: Wind, color: "#45d2aa" },
  "Conservative Grid Distance": { Icon: ShieldCheck, color: "#7fb4ff" },
  "Aggressive Expansion": { Icon: Rocket, color: "#ff8a65" },
};

export const DEFAULT_PRESET_META = { Icon: Sparkles, color: "#9aa3ff" };

/** A WiFi-signal-style "how much budget" indicator: more filled bars = bigger budget. */
export function BudgetBars({ tier, active }: { tier: BudgetTier; active?: boolean }) {
  const filled = tier === "small" ? 1 : tier === "medium" ? 2 : 3;
  return (
    <div className="flex items-end gap-0.5" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={`w-1.5 rounded-sm transition-colors ${
            i < filled
              ? active
                ? "bg-emerald-400"
                : "bg-zinc-400"
              : "bg-zinc-700"
          }`}
          style={{ height: `${6 + i * 5}px` }}
        />
      ))}
    </div>
  );
}

export const BUDGET_META: Record<BudgetTier, { label: string; blurb: string }> = {
  small: { label: "Small", blurb: "A few sites, lower cost" },
  medium: { label: "Medium", blurb: "Balanced size" },
  large: { label: "Large", blurb: "Big, capital-intensive" },
};

export { Leaf };
