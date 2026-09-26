// Starting points for the scenario wizard's Parameters step -- each just
// pre-fills the form with a bundle of real, already-solver-supported values
// (nothing invented). The user can still change anything after picking one,
// and target year / H2 market scenario are deliberately left out of every
// preset (those are picked in their own control, constrained by what's
// actually solvable for the chosen year -- see GET /scenarios/options).

export type ScenarioType = "electricity" | "coupled";

export type ScenarioPreset = {
  id: string;
  label: string;
  description: string;
  scenarioType: ScenarioType;
  annualGrowthRate: number;
  chronologicalStorage?: boolean;
  linkedRepresentativePeriods?: boolean;
};

export const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    id: "business-as-usual",
    label: "Business as usual",
    description: "1%/yr demand growth, standard representative-day modeling.",
    scenarioType: "electricity",
    annualGrowthRate: 0.01,
  },
  {
    id: "high-growth",
    label: "High demand growth",
    description: "5%/yr demand growth -- stress-tests capacity and prices.",
    scenarioType: "electricity",
    annualGrowthRate: 0.05,
  },
  {
    id: "low-growth",
    label: "Low / declining demand",
    description: "-2%/yr demand growth -- efficiency gains or demographic decline.",
    scenarioType: "electricity",
    annualGrowthRate: -0.02,
  },
  {
    id: "detailed-storage",
    label: "Detailed seasonal storage",
    description:
      "Coupled electricity + gas/hydrogen/heat system, solved with exact chronological " +
      "seasonal-storage tracking instead of representative days -- slower, more accurate " +
      "for storage-heavy years.",
    scenarioType: "coupled",
    annualGrowthRate: 0.01,
    chronologicalStorage: true,
  },
];
