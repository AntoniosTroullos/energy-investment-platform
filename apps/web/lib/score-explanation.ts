import type { AssetSelection } from "../types/asset";

export type ScoreExplanation = {
  strengths: string[];
  penalties: string[];
  summary: string;
};

export function getScoreExplanation(asset: AssetSelection): ScoreExplanation | null {
  if (asset.assetType !== "cell") {
    return null;
  }

  const technology = String(asset.properties.technology ?? "Unknown");
  const solarScore = Number(asset.properties.solar_score ?? 0);
  const windScore = Number(asset.properties.wind_score ?? 0);
  const distanceToSubstation = Number(
    asset.properties.distance_to_substation_km ?? 0,
  );
  const distanceToLine = Number(asset.properties.distance_to_line_km ?? 0);
  const landExcluded = asset.properties.land_excluded === true;
  const connectionCostLevel = String(
    asset.properties.connection_cost_level ?? "Unknown",
  );
  const investmentScore = Number(asset.properties.investment_score ?? 0);

  const strengths: string[] = [];
  const penalties: string[] = [];

  if (technology.toLowerCase().includes("solar") && solarScore >= 80) {
    strengths.push(`Strong solar resource score (${solarScore}).`);
  }

  if (technology.toLowerCase().includes("wind") && windScore >= 80) {
    strengths.push(`Strong wind resource score (${windScore}).`);
  }

  if (distanceToSubstation <= 7) {
    strengths.push(
      `Close to an existing substation (${distanceToSubstation.toFixed(1)} km).`,
    );
  } else if (distanceToSubstation >= 12) {
    penalties.push(
      `Far from the nearest substation (${distanceToSubstation.toFixed(1)} km).`,
    );
  }

  if (distanceToLine <= 7) {
    strengths.push(
      `Reasonably close to transmission infrastructure (${distanceToLine.toFixed(1)} km).`,
    );
  } else if (distanceToLine >= 12) {
    penalties.push(
      `Far from the nearest transmission line (${distanceToLine.toFixed(1)} km).`,
    );
  }

  if (connectionCostLevel === "Low") {
    strengths.push("Low connection cost level supports project economics.");
  }

  if (connectionCostLevel === "Medium") {
    penalties.push("Medium connection cost level adds moderate grid cost pressure.");
  }

  if (connectionCostLevel === "High") {
    penalties.push("High connection cost level materially reduces attractiveness.");
  }

  if (landExcluded) {
    penalties.push("Land exclusion is a major constraint for development.");
  }

  if (strengths.length === 0) {
    strengths.push(`Technology fit is led by the ${technology} resource profile.`);
  }

  if (penalties.length === 0) {
    penalties.push("No major screening penalties stand out at this stage.");
  }

  return {
    strengths,
    penalties,
    summary: getScoreSummary({
      technology,
      investmentScore,
      connectionCostLevel,
      landExcluded,
    }),
  };
}

function getScoreSummary(input: {
  technology: string;
  investmentScore: number;
  connectionCostLevel: string;
  landExcluded: boolean;
}) {
  const technology = input.technology.toLowerCase().includes("wind")
    ? "wind"
    : "solar";

  if (input.landExcluded) {
    return `This is a constrained ${technology} candidate. Despite some resource potential, land exclusions and connection conditions significantly reduce its investment outlook.`;
  }

  if (input.investmentScore >= 80) {
    return `This is a strong ${technology} candidate with supportive resource quality and relatively manageable grid connection difficulty.`;
  }

  if (input.investmentScore >= 60) {
    return `This is a workable ${technology} candidate, but it carries some connection or distance penalties that should be reviewed before prioritization.`;
  }

  if (input.connectionCostLevel === "High") {
    return `This ${technology} candidate is currently weakened by high expected connection costs and should be treated as a lower-priority opportunity.`;
  }

  return `This ${technology} candidate is currently less attractive than the top-ranked options and likely needs further review or constraint mitigation.`;
}
