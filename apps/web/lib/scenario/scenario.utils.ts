import { defaultScenario } from "./scenario.defaults";
import { scenarioPresets } from "./scenario.presets";
import type { BudgetTier, PreferredTechnology, Scenario } from "./scenario.types";

const MIN_CONNECTION_DISTANCE_KM = 5;
const MAX_CONNECTION_DISTANCE_KM = 25;
const MIN_INVESTMENT_SCORE = 0;
const MAX_INVESTMENT_SCORE = 100;

export function sanitizeScenario(input: Scenario): Scenario {
  return {
    budgetTier: isBudgetTier(input.budgetTier)
      ? input.budgetTier
      : defaultScenario.budgetTier,
    preferredTechnology: isPreferredTechnology(input.preferredTechnology)
      ? input.preferredTechnology
      : defaultScenario.preferredTechnology,
    maxConnectionDistanceKm: clampNumber(
      input.maxConnectionDistanceKm,
      MIN_CONNECTION_DISTANCE_KM,
      MAX_CONNECTION_DISTANCE_KM,
      defaultScenario.maxConnectionDistanceKm,
    ),
    excludeLandConstrained:
      typeof input.excludeLandConstrained === "boolean"
        ? input.excludeLandConstrained
        : defaultScenario.excludeLandConstrained,
    minInvestmentScore: clampNumber(
      input.minInvestmentScore,
      MIN_INVESTMENT_SCORE,
      MAX_INVESTMENT_SCORE,
      defaultScenario.minInvestmentScore,
    ),
  };
}

export function isScenario(value: unknown): value is Scenario {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return (
    isBudgetTier(candidate.budgetTier) &&
    isPreferredTechnology(candidate.preferredTechnology) &&
    typeof candidate.maxConnectionDistanceKm === "number" &&
    typeof candidate.excludeLandConstrained === "boolean" &&
    typeof candidate.minInvestmentScore === "number"
  );
}

export function areScenariosEqual(left: Scenario, right: Scenario) {
  return (
    left.budgetTier === right.budgetTier &&
    left.preferredTechnology === right.preferredTechnology &&
    left.maxConnectionDistanceKm === right.maxConnectionDistanceKm &&
    left.excludeLandConstrained === right.excludeLandConstrained &&
    left.minInvestmentScore === right.minInvestmentScore
  );
}

export function getActivePresetName(currentScenario: Scenario) {
  const activePreset = scenarioPresets.find((preset) =>
    areScenariosEqual(preset.scenario, currentScenario),
  );

  return activePreset?.name ?? null;
}

export function formatScenarioJson(scenario: Scenario) {
  return JSON.stringify(sanitizeScenario(scenario), null, 2);
}

export function isBudgetTier(value: unknown): value is BudgetTier {
  return value === "small" || value === "medium" || value === "large";
}

export function isPreferredTechnology(
  value: unknown,
): value is PreferredTechnology {
  return value === "all" || value === "solar" || value === "wind";
}

function clampNumber(
  value: unknown,
  minimum: number,
  maximum: number,
  fallback: number,
) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return fallback;
  }

  return Math.min(Math.max(value, minimum), maximum);
}
