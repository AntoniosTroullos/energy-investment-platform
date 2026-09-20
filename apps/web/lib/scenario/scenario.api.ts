import {
  getEligibleCandidateCells,
  sortCandidatesByInvestmentScore,
} from "./candidate-screening";
import { sanitizeScenario } from "./scenario.utils";
import type { AssetSelection } from "../../types/asset";
import type { Scenario } from "./scenario.types";

export type ScenarioEvaluationRequest = {
  scenario: Scenario;
};

export type ScenarioTopCandidateSummary = {
  id: string;
  technology: string;
  investmentScore: number;
  distanceToSubstationKm: number;
  distanceToLineKm: number;
  connectionCostLevel: string;
  landExcluded: boolean;
};

export type ScenarioScoreStats = {
  min: number;
  max: number;
  average: number;
};

export type ScenarioTechnologyBreakdown = {
  solar: number;
  wind: number;
};

export type ScenarioEvaluationResponse = {
  eligibleCount: number;
  topCandidateIds: string[];
  summary: string;
  topCandidates: ScenarioTopCandidateSummary[];
  scoreStats: ScenarioScoreStats;
  technologyBreakdown: ScenarioTechnologyBreakdown;
};

export function evaluateMockScenario(
  request: ScenarioEvaluationRequest,
): ScenarioEvaluationResponse {
  const scenario = sanitizeScenario(request.scenario);
  // This route has no local candidate dataset to screen (the app now sources
  // candidate cells from the FastAPI backend instead), so it always reports
  // zero eligible candidates rather than crashing on a missing argument.
  const eligibleCells = getEligibleCandidateCells([], scenario);
  const sortedEligibleCells = sortCandidatesByInvestmentScore(eligibleCells);
  const topCandidates = sortedEligibleCells.slice(0, 3).map(buildTopCandidateSummary);
  const topCandidateIds = topCandidates.map((candidate) => candidate.id);

  return {
    eligibleCount: eligibleCells.length,
    topCandidateIds,
    topCandidates,
    scoreStats: buildScoreStats(eligibleCells),
    technologyBreakdown: buildTechnologyBreakdown(eligibleCells),
    summary: buildScenarioSummary(scenario, eligibleCells, topCandidateIds),
  };
}

function buildScenarioSummary(
  scenario: Scenario,
  eligibleCells: AssetSelection[],
  topCandidateIds: string[],
) {
  if (eligibleCells.length === 0) {
    return "No candidate cells meet the current scenario thresholds.";
  }

  const technologyFocus =
    scenario.preferredTechnology === "all"
      ? "mixed-technology"
      : `${scenario.preferredTechnology}-focused`;
  const topCandidateText =
    topCandidateIds.length > 0
      ? `Top candidates: ${topCandidateIds.join(", ")}.`
      : "No top candidates were identified.";

  return `${eligibleCells.length} ${technologyFocus} candidate cells are eligible under the current scenario. ${topCandidateText}`;
}

function buildTopCandidateSummary(
  asset: AssetSelection,
): ScenarioTopCandidateSummary {
  return {
    id: asset.id,
    technology: String(asset.properties.technology ?? "Unknown"),
    investmentScore: Number(asset.properties.investment_score ?? 0),
    distanceToSubstationKm: Number(
      asset.properties.distance_to_substation_km ?? 0,
    ),
    distanceToLineKm: Number(asset.properties.distance_to_line_km ?? 0),
    connectionCostLevel: String(asset.properties.connection_cost_level ?? "Unknown"),
    landExcluded: asset.properties.land_excluded === true,
  };
}

function buildScoreStats(eligibleCells: AssetSelection[]): ScenarioScoreStats {
  if (eligibleCells.length === 0) {
    return {
      min: 0,
      max: 0,
      average: 0,
    };
  }

  const scores = eligibleCells.map((asset) =>
    Number(asset.properties.investment_score ?? 0),
  );
  const totalScore = scores.reduce((sum, score) => sum + score, 0);

  return {
    min: Math.min(...scores),
    max: Math.max(...scores),
    average: Math.round((totalScore / scores.length) * 10) / 10,
  };
}

function buildTechnologyBreakdown(
  eligibleCells: AssetSelection[],
): ScenarioTechnologyBreakdown {
  return eligibleCells.reduce(
    (breakdown, asset) => {
      const technology = String(asset.properties.technology ?? "").toLowerCase();

      if (technology.includes("solar")) {
        breakdown.solar += 1;
      }

      if (technology.includes("wind")) {
        breakdown.wind += 1;
      }

      return breakdown;
    },
    {
      solar: 0,
      wind: 0,
    } satisfies ScenarioTechnologyBreakdown,
  );
}
