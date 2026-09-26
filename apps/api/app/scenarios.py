from __future__ import annotations

import csv
import re
from datetime import datetime, timezone
from pathlib import Path

from . import network_topology, scenario_options, scenario_runner, staleness
from .pypsa_bridge.normalize import normalize_coupled_result, normalize_electricity_result
from .scenario_models import (
    CoupledScenarioResult,
    CoupledScenarioRunRequest,
    CoupledScenarioRunResponse,
    ElectricityScenarioResult,
    ElectricityScenarioRunRequest,
    ElectricityScenarioRunResponse,
    ScenarioListItem,
    ScenarioListResponse,
    ScenarioMetrics,
    ScenarioStatusResponse,
)

GENERATOR_CLUSTERS_PATH = (
    scenario_runner.PYPSA_GREECE_ROOT / "data" / "processed" / "generator_clusters.csv"
)

# Only case directories this bridge itself creates (scenario_runner.electricity_case_name)
# match this pattern. Other case types under the same pypsa_scenarios/ root --
# built directly via the upstream CLI (clustered_*, orchestrator_*, mid_2026_*,
# etc.) -- use a different, incompatible result schema (confirmed directly: no
# "request" key, "objective" instead of "objective_eur") and are excluded
# rather than mis-normalized.
ELECTRICITY_CASE_PATTERN = re.compile(r"^future_electricity_(\d{4})$")


async def start_electricity_scenario(request: ElectricityScenarioRunRequest) -> ElectricityScenarioRunResponse:
    case_name = await scenario_runner.run_electricity_scenario(
        request.target_year, request.annual_growth_rate, request.force_fetch
    )
    status = scenario_runner.poll_status(case_name)
    return ElectricityScenarioRunResponse(case_name=case_name, state=status.state)


def get_scenario_status(case_name: str) -> ScenarioStatusResponse:
    status = scenario_runner.poll_status(case_name)
    return ScenarioStatusResponse(
        case_name=case_name, state=status.state, pid=status.pid, message=status.message
    )


async def start_coupled_scenario(request: CoupledScenarioRunRequest) -> CoupledScenarioRunResponse:
    # Checked before scenario_runner even builds a case name: an undefined
    # (year, scenario) pair is a malformed request, not an unmet precondition
    # (that check -- is the electricity case solved -- happens inside
    # run_coupled_scenario, once we know the pair itself is valid).
    scenario_options.validate_coupled_request(request.target_year, request.h2_market_scenario)

    case_name = await scenario_runner.run_coupled_scenario(
        request.target_year,
        request.h2_market_scenario,
        request.chronological_storage,
        request.linked_representative_periods,
    )
    status = scenario_runner.poll_coupled_status(
        case_name, request.chronological_storage, request.linked_representative_periods
    )
    return CoupledScenarioRunResponse(case_name=case_name, state=status.state)


def get_coupled_scenario_status(
    case_name: str,
    chronological_storage: bool = False,
    linked_representative_periods: bool = False,
) -> ScenarioStatusResponse:
    status = scenario_runner.poll_coupled_status(case_name, chronological_storage, linked_representative_periods)
    return ScenarioStatusResponse(
        case_name=case_name, state=status.state, pid=status.pid, message=status.message
    )


def get_coupled_scenario_result(
    case_name: str,
    chronological_storage: bool = False,
    linked_representative_periods: bool = False,
) -> CoupledScenarioResult:
    raw = scenario_runner.get_coupled_result(case_name, chronological_storage, linked_representative_periods)
    return normalize_coupled_result(case_name, raw)


def get_scenario_result(case_name: str) -> ElectricityScenarioResult:
    raw = scenario_runner.get_result(case_name)
    result_path = scenario_runner.case_dir(case_name) / "scenario_result.json"
    return normalize_electricity_result(case_name, raw, solved_at_utc=_file_mtime_iso(result_path))


def _file_mtime_iso(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return None


def list_electricity_scenarios() -> ScenarioListResponse:
    """The live scenario library (GET /scenarios) -- real case directories
    under pypsa_scenarios/ that this bridge created, each with its current
    status and (once solved) the headline numbers a comparison view needs.
    Deliberately not the hand-curated, already-stale scenario_comparison.csv."""
    if not scenario_runner.SCENARIO_ROOT.exists():
        return ScenarioListResponse(scenarios=[])

    # Globbed once per listing, not per case -- the same few dozen upstream
    # files are checked against every result's mtime.
    project_root = scenario_runner.PYTHON_PROJECT_ROOT
    electricity_watch = staleness.electricity_watchlist(project_root)
    coupled_watch = staleness.coupled_watchlist(project_root)

    items: list[ScenarioListItem] = []
    for entry in sorted(scenario_runner.SCENARIO_ROOT.iterdir()):
        if not entry.is_dir():
            continue

        match = ELECTRICITY_CASE_PATTERN.match(entry.name)
        if not match:
            continue

        case_name = entry.name
        target_year = int(match.group(1))
        status = scenario_runner.poll_status(case_name)

        solved: bool | None = None
        message: str | None = status.message
        objective_eur: float | None = None
        generation_by_carrier_mwh: dict[str, float] = {}
        annual_growth_rate: float | None = None
        solved_at_utc: str | None = None

        if status.state == "done":
            try:
                result = get_scenario_result(case_name)
                solved = result.solved
                message = result.message
                objective_eur = result.objective_eur
                generation_by_carrier_mwh = result.metrics.generation_by_carrier_mwh
                annual_growth_rate = result.parameters.annual_growth_rate if result.parameters else None
                solved_at_utc = result.solved_at_utc
            except FileNotFoundError:
                pass

        coupled_status = scenario_runner.poll_coupled_status(case_name)
        coupled_objective: float | None = None
        coupled_heat_twh: float | None = None
        coupled_h2_output: float | None = None
        if coupled_status.state == "done":
            try:
                coupled = get_coupled_scenario_result(case_name)
                if coupled.solved:
                    coupled_objective = coupled.objective_eur_per_year
                    coupled_heat_twh = coupled.annual_heat_twh
                    if coupled.h2_balance_mwh is not None:
                        coupled_h2_output = coupled.h2_balance_mwh.electrolysis_output
            except Exception:
                # A malformed/partial coupled result must not break the whole
                # library listing -- the electricity row still stands on its own.
                pass

        electricity_result_file = scenario_runner.case_dir(case_name) / "scenario_result.json"
        coupled_result_file = scenario_runner.coupled_result_dir(case_name) / "scenario_result.json"
        electricity_staleness = staleness.assess(electricity_result_file, electricity_watch, project_root)
        coupled_staleness = staleness.assess(
            coupled_result_file,
            coupled_watch,
            project_root,
            parent_result_path=electricity_result_file,
        )

        items.append(
            ScenarioListItem(
                case_name=case_name,
                target_year=target_year,
                state=status.state,
                solved=solved,
                message=message,
                objective_eur=objective_eur,
                generation_by_carrier_mwh=generation_by_carrier_mwh,
                annual_growth_rate=annual_growth_rate,
                solved_at_utc=solved_at_utc,
                coupled_state=coupled_status.state,
                coupled_objective_eur_per_year=coupled_objective,
                coupled_annual_heat_twh=coupled_heat_twh,
                coupled_h2_electrolysis_output_mwh=coupled_h2_output,
                electricity_staleness=electricity_staleness,
                coupled_staleness=coupled_staleness,
            )
        )

    items.sort(key=lambda item: item.target_year)
    return ScenarioListResponse(scenarios=items)


# The pickable per-region metrics for both the single-scenario map and the
# delta-between-cases map -- one shared list so the two views can never end up
# offering different metric choices for what is meant to be the same concept.
REGION_METRIC_KEYS = (
    "generation_mwh",
    "total_load_mwh",
    "net_position_mwh",
    "average_marginal_price_eur_per_mwh",
    "peak_load_mw",
)


def _region_metric_values(bus_id: str, metrics: ScenarioMetrics) -> dict[str, float | None]:
    generation_mwh = metrics.generation_by_bus_mwh.get(bus_id)
    total_load_mwh = metrics.total_load_by_bus_mwh.get(bus_id)
    return {
        "generation_mwh": generation_mwh,
        "total_load_mwh": total_load_mwh,
        # Generation minus load for the year: positive means this region is a
        # net exporter to the rest of the network, negative a net importer.
        # Not one of the upstream metrics.py fields -- both operands it needs
        # already are, so it is derived here rather than requested upstream.
        "net_position_mwh": (
            generation_mwh - total_load_mwh
            if generation_mwh is not None and total_load_mwh is not None
            else None
        ),
        "average_marginal_price_eur_per_mwh": metrics.average_marginal_price_by_bus.get(bus_id),
        "peak_load_mw": metrics.peak_load_by_bus_mw.get(bus_id),
    }


def get_scenario_regions_geojson(case_name: str) -> dict:
    """Joins a solved scenario's per-bus metrics onto the real admin-region
    polygons (/admin-regions) for map choropleth use. This scenario type
    solves pypsa-greece's simple 13-region baseline (data/static/buses.csv,
    generators.csv) -- confirmed directly, not the clustered real-generator-
    fleet network -- so region-level is the real resolution its output
    supports; joining to anything finer would imply precision that isn't
    there. Geometry is network_topology's simplified copy of the polygons
    (~95% smaller than the raw file with no visible loss at map scale)."""
    result = get_scenario_result(case_name)
    regions = network_topology.get_simplified_admin_regions()

    enriched_features = []
    for feature in regions["features"]:
        bus_id = feature.get("properties", {}).get("id")
        properties = {
            **feature.get("properties", {}),
            "scenario_case_name": case_name,
            **_region_metric_values(bus_id, result.metrics),
        }
        enriched_features.append({**feature, "properties": properties})

    return {"type": "FeatureCollection", "features": enriched_features}


def get_scenario_regions_delta_geojson(case_name_a: str, case_name_b: str) -> dict:
    """Per-region (b - a) difference for every REGION_METRIC_KEYS metric, for
    a solved-vs-solved comparison map -- e.g. "how did net position shift
    between the 2030 and 2050 cases". Each metric's own value under both
    cases is included too (<key>_a, <key>_b), not just the delta, so a hover
    tooltip can show "62,000 -> 58,500 MWh (-3,500)" rather than the
    difference alone."""
    result_a = get_scenario_result(case_name_a)
    result_b = get_scenario_result(case_name_b)
    regions = network_topology.get_simplified_admin_regions()

    enriched_features = []
    for feature in regions["features"]:
        bus_id = feature.get("properties", {}).get("id")
        values_a = _region_metric_values(bus_id, result_a.metrics)
        values_b = _region_metric_values(bus_id, result_b.metrics)

        properties = {
            **feature.get("properties", {}),
            "scenario_case_name_a": case_name_a,
            "scenario_case_name_b": case_name_b,
        }
        for key in REGION_METRIC_KEYS:
            value_a, value_b = values_a[key], values_b[key]
            properties[f"{key}_a"] = value_a
            properties[f"{key}_b"] = value_b
            properties[f"{key}_delta"] = (
                value_b - value_a if value_a is not None and value_b is not None else None
            )

        enriched_features.append({**feature, "properties": properties})

    return {"type": "FeatureCollection", "features": enriched_features}


def get_generator_clusters_geojson() -> dict:
    """Real per-project generator cluster locations and capacity
    (pypsa-greece's own generator_clusters.csv, built from RAAEY/DAPEEP/Greek
    Energy Map real data -- see pypsa-greece/KNOWLEDGE_TRANSFER.md sections
    18-21). NOT tied to any solved scenario -- this scenario-builder's
    solves run the simple 13-region baseline, which has no per-cluster
    granularity to join against. This is real installed/calibrated capacity
    at real locations, useful as its own "asset location and capacity" map
    layer regardless of which scenario (if any) is currently solved."""
    if not GENERATOR_CLUSTERS_PATH.exists():
        raise FileNotFoundError(f"No generator cluster data found at {GENERATOR_CLUSTERS_PATH}.")

    features = []
    with GENERATOR_CLUSTERS_PATH.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                longitude = float(row["centroid_longitude"])
                latitude = float(row["centroid_latitude"])
            except (KeyError, ValueError):
                continue

            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "id": f"{row.get('bus')}_{row.get('carrier')}_cluster_{row.get('cluster_index')}",
                        "bus": row.get("bus"),
                        "carrier": row.get("carrier"),
                        "cluster_index": row.get("cluster_index"),
                        "asset_count": row.get("asset_count"),
                        "p_nom_mw": _to_float(row.get("p_nom_mw")),
                        "p_nom_calibrated_mw": _to_float(row.get("p_nom_calibrated_mw")),
                        # Alias for MapView.tsx's existing generic circle-radius
                        # expression (addClusteredPointLayers), which keys off
                        # "capacity_mw"/"nominal_capacity_mw" -- avoids touching
                        # that shared, actively-edited component just to read a
                        # differently-named field.
                        "capacity_mw": _to_float(row.get("p_nom_calibrated_mw")),
                        "capacity_classification": row.get("capacity_classification"),
                        "distance_to_substation_km": _to_float(row.get("distance_to_substation_km")),
                        "distance_to_line_km": _to_float(row.get("distance_to_line_km")),
                    },
                    "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
                }
            )

    return {"type": "FeatureCollection", "features": features}


def _to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None
