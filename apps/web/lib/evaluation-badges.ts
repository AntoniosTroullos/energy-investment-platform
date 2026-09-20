import type { ScenarioTopCandidateSummary } from "./scenario/scenario.api";

export function getEvaluationCandidateBadge(
  candidate: ScenarioTopCandidateSummary,
  candidates: ScenarioTopCandidateSummary[],
) {
  if (candidates.length === 0) {
    return null;
  }

  if (candidate.id === candidates[0]?.id) {
    return {
      label: "Best overall",
      className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    };
  }

  if (isAvoidCandidate(candidate)) {
    return {
      label: "Avoid",
      className: "border-rose-500/30 bg-rose-500/10 text-rose-300",
    };
  }

  if (isBestSolarCandidate(candidate, candidates)) {
    return {
      label: "Best solar",
      className: "border-amber-500/30 bg-amber-500/10 text-amber-300",
    };
  }

  if (isBestWindCandidate(candidate, candidates)) {
    return {
      label: "Best wind",
      className: "border-sky-500/30 bg-sky-500/10 text-sky-300",
    };
  }

  if (isLowestConnectionCostCandidate(candidate, candidates)) {
    return {
      label: "Lowest connection cost",
      className: "border-cyan-500/30 bg-cyan-500/10 text-cyan-300",
    };
  }

  if (isWatchlistCandidate(candidate)) {
    return {
      label: "Watchlist",
      className: "border-zinc-400/20 bg-zinc-500/10 text-zinc-300",
    };
  }

  return null;
}

function isBestSolarCandidate(
  candidate: ScenarioTopCandidateSummary,
  candidates: ScenarioTopCandidateSummary[],
) {
  if (!candidate.technology.toLowerCase().includes("solar")) {
    return false;
  }

  const solarCandidates = candidates.filter((item) =>
    item.technology.toLowerCase().includes("solar"),
  );

  return candidate.id === solarCandidates[0]?.id;
}

function isBestWindCandidate(
  candidate: ScenarioTopCandidateSummary,
  candidates: ScenarioTopCandidateSummary[],
) {
  if (!candidate.technology.toLowerCase().includes("wind")) {
    return false;
  }

  const windCandidates = candidates.filter((item) =>
    item.technology.toLowerCase().includes("wind"),
  );

  return candidate.id === windCandidates[0]?.id;
}

function isLowestConnectionCostCandidate(
  candidate: ScenarioTopCandidateSummary,
  candidates: ScenarioTopCandidateSummary[],
) {
  const sortedByConnection = [...candidates].sort((left, right) => {
    const leftRank = getConnectionCostRank(left.connectionCostLevel);
    const rightRank = getConnectionCostRank(right.connectionCostLevel);

    if (leftRank !== rightRank) {
      return leftRank - rightRank;
    }

    const leftDistance =
      left.distanceToSubstationKm + left.distanceToLineKm;
    const rightDistance =
      right.distanceToSubstationKm + right.distanceToLineKm;

    return leftDistance - rightDistance;
  });

  return candidate.id === sortedByConnection[0]?.id;
}

function isAvoidCandidate(candidate: ScenarioTopCandidateSummary) {
  return (
    candidate.landExcluded &&
    candidate.connectionCostLevel === "High"
  );
}

function isWatchlistCandidate(candidate: ScenarioTopCandidateSummary) {
  return (
    candidate.landExcluded ||
    candidate.connectionCostLevel === "High" ||
    candidate.investmentScore < 50
  );
}

function getConnectionCostRank(connectionCostLevel: string) {
  if (connectionCostLevel === "Low") {
    return 0;
  }

  if (connectionCostLevel === "Medium") {
    return 1;
  }

  return 2;
}
