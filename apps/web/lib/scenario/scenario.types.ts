export type BudgetTier = "small" | "medium" | "large";
export type PreferredTechnology = "all" | "solar" | "wind";

export type Scenario = {
  budgetTier: BudgetTier;
  preferredTechnology: PreferredTechnology;
  maxConnectionDistanceKm: number;
  excludeLandConstrained: boolean;
  minInvestmentScore: number;
};

export type ScenarioPreset = {
  name: string;
  description: string;
  scenario: Scenario;
};
