import json
from pathlib import Path

from .models import (
    CandidateCell,
    Scenario,
    ScenarioEvaluationResponse,
    ScoreStats,
    TechnologyBreakdown,
    TopCandidateSummary,
)


GENERATED_DATA_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "generated" / "candidate_cells.geojson"
)
SOURCE_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "source"


def load_candidate_feature_collection() -> dict:
    with GENERATED_DATA_PATH.open("r", encoding="utf-8") as data_file:
        return json.load(data_file)


def load_candidate_cells() -> list[CandidateCell]:
    feature_collection = load_candidate_feature_collection()

    return [
        CandidateCell.model_validate(
            {
                **feature["properties"],
                "geometry": feature["geometry"],
            }
        )
        for feature in feature_collection["features"]
    ]


def get_candidate_feature_collection() -> dict:
    return load_candidate_feature_collection()


def get_source_layer_feature_collection(filename: str) -> dict:
    source_path = SOURCE_DATA_DIR / filename

    with source_path.open("r", encoding="utf-8") as data_file:
        return json.load(data_file)


def evaluate_scenario(scenario: Scenario) -> ScenarioEvaluationResponse:
    eligible_cells = get_eligible_candidate_cells(scenario)
    sorted_cells = sort_candidates_by_score(eligible_cells)
    top_candidates = [build_top_candidate_summary(cell) for cell in sorted_cells[:3]]
    top_candidate_ids = [candidate.id for candidate in top_candidates]

    return ScenarioEvaluationResponse(
        eligibleCount=len(eligible_cells),
        topCandidateIds=top_candidate_ids,
        summary=build_summary(scenario, len(eligible_cells), top_candidate_ids),
        topCandidates=top_candidates,
        scoreStats=build_score_stats(eligible_cells),
        technologyBreakdown=build_technology_breakdown(eligible_cells),
    )


def get_eligible_candidate_cells(scenario: Scenario) -> list[CandidateCell]:
    return [
        cell
        for cell in load_candidate_cells()
        if matches_scenario_rules(cell, scenario)
    ]


def matches_scenario_rules(cell: CandidateCell, scenario: Scenario) -> bool:
    technology = cell.technology.lower()

    if cell.investment_score < scenario.minInvestmentScore:
        return False

    if scenario.preferredTechnology == "solar" and "solar" not in technology:
        return False

    if scenario.preferredTechnology == "wind" and "wind" not in technology:
        return False

    if (
        cell.distance_to_substation_km > scenario.maxConnectionDistanceKm
        or cell.distance_to_line_km > scenario.maxConnectionDistanceKm
    ):
        return False

    if scenario.excludeLandConstrained and cell.land_excluded:
        return False

    return True


def sort_candidates_by_score(cells: list[CandidateCell]) -> list[CandidateCell]:
    return sorted(cells, key=lambda cell: cell.investment_score, reverse=True)


def build_top_candidate_summary(cell: CandidateCell) -> TopCandidateSummary:
    return TopCandidateSummary(
        id=cell.id,
        technology=cell.technology,
        investmentScore=cell.investment_score,
        distanceToSubstationKm=cell.distance_to_substation_km,
        distanceToLineKm=cell.distance_to_line_km,
        connectionCostLevel=cell.connection_cost_level,
        landExcluded=cell.land_excluded,
    )


def build_score_stats(cells: list[CandidateCell]) -> ScoreStats:
    if not cells:
        return ScoreStats(min=0, max=0, average=0)

    scores = [cell.investment_score for cell in cells]

    return ScoreStats(
        min=min(scores),
        max=max(scores),
        average=round(sum(scores) / len(scores), 1),
    )


def build_technology_breakdown(cells: list[CandidateCell]) -> TechnologyBreakdown:
    solar_count = 0
    wind_count = 0

    for cell in cells:
        technology = cell.technology.lower()

        if "solar" in technology:
            solar_count += 1

        if "wind" in technology:
            wind_count += 1

    return TechnologyBreakdown(solar=solar_count, wind=wind_count)


def build_summary(
    scenario: Scenario,
    eligible_count: int,
    top_candidate_ids: list[str],
) -> str:
    if eligible_count == 0:
        return "No candidate cells meet the current scenario thresholds."

    technology_focus = (
        "mixed-technology"
        if scenario.preferredTechnology == "all"
        else f"{scenario.preferredTechnology}-focused"
    )
    top_candidate_text = (
        f"Top candidates: {', '.join(top_candidate_ids)}."
        if top_candidate_ids
        else "No top candidates were identified."
    )

    return (
        f"{eligible_count} {technology_focus} candidate cells are eligible under "
        f"the current scenario. {top_candidate_text}"
    )
