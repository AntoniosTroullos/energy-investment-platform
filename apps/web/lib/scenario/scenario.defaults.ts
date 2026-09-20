import type { Scenario } from "./scenario.types";

export const defaultScenario: Scenario = {
  budgetTier: "medium",
  preferredTechnology: "all",
  maxConnectionDistanceKm: 15,
  excludeLandConstrained: false,
  minInvestmentScore: 50,
};

export const customScenarioStorageKey =
  "energy-investment-platform-custom-scenario";
