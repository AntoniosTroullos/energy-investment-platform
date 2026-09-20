import type { AssetSelection } from "../types/asset";
import type { Scenario } from "./scenario/scenario.types";

export type ComparisonRecommendation = {
  bestOverall?: string;
  bestSolar?: string;
  bestWind?: string;
  bestLowConnectionCost?: string;
  avoid?: string;
  scenarioFit?: string;
};

export function getComparisonRecommendation(
  comparedCells: AssetSelection[],
  scenario: Scenario,
): ComparisonRecommendation | null {
  if (comparedCells.length === 0) {
    return null;
  }

  const bestOverall = getHighestScore(comparedCells);
  const solarCandidates = comparedCells.filter((cell) =>
    String(cell.properties.technology ?? "").toLowerCase().includes("solar"),
  );
  const windCandidates = comparedCells.filter((cell) =>
    String(cell.properties.technology ?? "").toLowerCase().includes("wind"),
  );
  const lowConnectionCandidates = comparedCells.filter(
    (cell) => cell.properties.connection_cost_level === "Low",
  );
  const avoidCandidate = getAvoidCandidate(comparedCells);

  return {
    bestOverall: bestOverall
      ? `Best overall: ${bestOverall.id} due to the highest score and manageable grid distance.`
      : undefined,
    bestSolar:
      solarCandidates.length > 0
        ? `Best solar candidate: ${getHighestScore(solarCandidates)?.id} based on the strongest solar-weighted score among the compared options.`
        : undefined,
    bestWind:
      windCandidates.length > 0
        ? `Best wind candidate: ${getHighestScore(windCandidates)?.id} because it leads the compared wind-oriented options.`
        : undefined,
    bestLowConnectionCost:
      lowConnectionCandidates.length > 0
        ? `Best low-connection-cost option: ${getHighestScore(lowConnectionCandidates)?.id} thanks to low connection cost and a strong overall score.`
        : undefined,
    avoid: avoidCandidate
      ? `Avoid ${avoidCandidate.id} because ${getAvoidReason(avoidCandidate)}.`
      : undefined,
    scenarioFit: getScenarioFitMessage(bestOverall, scenario),
  };
}

function getHighestScore(cells: AssetSelection[]) {
  return [...cells].sort(
    (left, right) =>
      Number(right.properties.investment_score ?? 0) -
      Number(left.properties.investment_score ?? 0),
  )[0];
}

function getAvoidCandidate(cells: AssetSelection[]) {
  return [...cells]
    .filter(
      (cell) =>
        cell.properties.land_excluded === true ||
        cell.properties.connection_cost_level === "High" ||
        Number(cell.properties.investment_score ?? 0) < 50,
    )
    .sort((left, right) => {
      const leftRisk = getRiskScore(left);
      const rightRisk = getRiskScore(right);
      return rightRisk - leftRisk;
    })[0];
}

function getRiskScore(cell: AssetSelection) {
  let riskScore = 0;

  if (cell.properties.land_excluded === true) {
    riskScore += 50;
  }

  if (cell.properties.connection_cost_level === "High") {
    riskScore += 25;
  }

  riskScore += Math.max(0, 60 - Number(cell.properties.investment_score ?? 0));

  return riskScore;
}

function getAvoidReason(cell: AssetSelection) {
  if (cell.properties.land_excluded === true) {
    return "land_excluded is true and development constraints are likely to be severe";
  }

  if (cell.properties.connection_cost_level === "High") {
    return "connection cost is high and the economics are less favorable";
  }

  return "its investment score trails the stronger compared candidates";
}

function getScenarioFitMessage(
  bestOverall: AssetSelection | undefined,
  scenario: Scenario,
) {
  if (!bestOverall) {
    return undefined;
  }

  const connectionCost = String(bestOverall.properties.connection_cost_level ?? "");
  const technology = String(bestOverall.properties.technology ?? "").toLowerCase();

  if (scenario.budgetTier === "small" && connectionCost === "High") {
    return "Scenario note: a small budget tier may struggle to support the current top option because connection costs are high.";
  }

  if (scenario.budgetTier === "small" && connectionCost === "Low") {
    return "Scenario note: this comparison fits a small budget tier reasonably well because the leading option has relatively low connection cost.";
  }

  if (scenario.budgetTier === "large" && connectionCost === "High") {
    return "Scenario note: a large budget tier can absorb more connection cost, so the higher-cost leading option may still be practical.";
  }

  if (
    scenario.preferredTechnology === "solar" &&
    !technology.includes("solar")
  ) {
    return "Scenario note: the strongest compared option does not match the preferred solar focus, so the best solar-specific candidate may be more aligned with this scenario.";
  }

  if (
    scenario.preferredTechnology === "wind" &&
    !technology.includes("wind")
  ) {
    return "Scenario note: the strongest compared option does not match the preferred wind focus, so the best wind-specific candidate may be more aligned with this scenario.";
  }

  return "Scenario note: the current comparison is broadly aligned with the active planning scenario.";
}
