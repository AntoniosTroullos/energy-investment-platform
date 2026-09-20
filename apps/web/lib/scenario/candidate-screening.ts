import type { AssetSelection } from "../../types/asset";
import type { Scenario } from "./scenario.types";

export function matchesCandidateScenario(
  asset: AssetSelection,
  scenario: Scenario,
) {
  if (asset.assetType !== "cell") {
    return true;
  }

  const investmentScore = Number(asset.properties.investment_score ?? 0);
  const technology = String(asset.properties.technology ?? "").toLowerCase();
  const landExcluded = asset.properties.land_excluded === true;
  const distanceToSubstation = Number(
    asset.properties.distance_to_substation_km ?? 0,
  );
  const distanceToLine = Number(asset.properties.distance_to_line_km ?? 0);

  if (investmentScore < scenario.minInvestmentScore) {
    return false;
  }

  if (
    scenario.preferredTechnology === "solar" &&
    !technology.includes("solar")
  ) {
    return false;
  }

  if (
    scenario.preferredTechnology === "wind" &&
    !technology.includes("wind")
  ) {
    return false;
  }

  if (
    distanceToSubstation > scenario.maxConnectionDistanceKm ||
    distanceToLine > scenario.maxConnectionDistanceKm
  ) {
    return false;
  }

  if (scenario.excludeLandConstrained && landExcluded) {
    return false;
  }

  return true;
}

export function getEligibleCandidateCells(
  candidateAssets: AssetSelection[],
  scenario: Scenario,
) {
  return candidateAssets.filter(
    (asset) => asset.assetType === "cell" && matchesCandidateScenario(asset, scenario),
  );
}

export function sortCandidatesByInvestmentScore(assets: AssetSelection[]) {
  return [...assets].sort(
    (left, right) =>
      Number(right.properties.investment_score ?? 0) -
      Number(left.properties.investment_score ?? 0),
  );
}
