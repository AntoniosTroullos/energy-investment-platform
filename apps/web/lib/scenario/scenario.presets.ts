import type { ScenarioPreset } from "./scenario.types";

// Built-in scenario presets for quick planning workflows.
export const scenarioPresets: ScenarioPreset[] = [
  {
    name: "Solar-first",
    description:
      "Prioritizes higher-scoring solar candidates with moderate grid reach.",
    scenario: {
      budgetTier: "medium",
      preferredTechnology: "solar",
      maxConnectionDistanceKm: 16,
      excludeLandConstrained: true,
      minInvestmentScore: 62,
    },
  },
  {
    name: "Wind-first",
    description:
      "Focuses the screen on stronger wind candidates with room for grid access.",
    scenario: {
      budgetTier: "large",
      preferredTechnology: "wind",
      maxConnectionDistanceKm: 18,
      excludeLandConstrained: true,
      minInvestmentScore: 58,
    },
  },
  {
    name: "Conservative Grid Distance",
    description:
      "Keeps only candidates with tighter connection distances and cleaner constraints.",
    scenario: {
      budgetTier: "small",
      preferredTechnology: "all",
      maxConnectionDistanceKm: 10,
      excludeLandConstrained: true,
      minInvestmentScore: 60,
    },
  },
  {
    name: "Aggressive Expansion",
    description:
      "Allows broader buildout conditions to surface more expansion candidates.",
    scenario: {
      budgetTier: "large",
      preferredTechnology: "all",
      maxConnectionDistanceKm: 22,
      excludeLandConstrained: false,
      minInvestmentScore: 40,
    },
  },
];
