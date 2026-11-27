"""One call that answers "what is the state of the Greek grid, and where is
the money in it" -- the data behind the national overview dashboard.

Everything here is already computed and cached elsewhere: the solved scenario's
metrics, the hourly capture layer, corridor verification, the generator
registry, the candidate economics. What this module adds is the assembly, in
one round trip, in the shape a dashboard actually renders: headline figures,
then the panels, then the per-region rows the map colours.

Two different ideas of "capacity" appear deliberately, because they answer
different questions and conflating them is the usual way an energy dashboard
misleads:

  * the OPERATING FLEET, from the solved scenario -- what is actually on the
    system today and what it generated, and
  * the PROJECT PIPELINE, from the licensing registries -- what has been
    applied for or licensed, which is an order of magnitude larger and is the
    market opportunity, not the grid.

No live network calls: the live market feed is its own endpoint, so a slow
third-party API never delays this one.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache

from .evaluation import load_candidate_cells
from .generators import get_generators_summary_by_technology
from .hourly_market import HourlyMarket, get_hourly_market
from .investment_analysis import (
    evaluate_candidate_investment,
    load_technology_costs,
)
from .network_topology import corridor_provenance, get_candidate_region_ids
from .scenario_models import ElectricityScenarioResult

# The case the overview describes: the clustered 2026 run built on Greece's
# real generator fleet, as opposed to the stylised-fleet cases.
DEFAULT_OVERVIEW_CASE = "clustered_mid_2026_monthly_days"

RENEWABLE_CARRIERS = {"solar", "wind", "hydro", "biomass", "ror"}

# How many investment opportunities the dashboard lists.
TOP_OPPORTUNITY_COUNT = 8


def build_overview(
    result: ElectricityScenarioResult,
    *,
    case_name: str = DEFAULT_OVERVIEW_CASE,
) -> dict:
    market = get_hourly_market(case_name)
    opportunities = _opportunities(result)

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "case_name": case_name,
        "target_year": result.target_year,
        "fleet": _fleet(result, market),
        "market": _market(market),
        "network": _network(market),
        "pipeline": _pipeline(),
        "opportunities": opportunities,
        "regions": _regions(market, opportunities["by_region"]),
        "series": _series(market),
    }


def _fleet(result: ElectricityScenarioResult, market: HourlyMarket | None) -> dict:
    capacity = {
        carrier: value
        for carrier, value in result.metrics.installed_capacity_by_carrier_mw.items()
        if value and value > 0
    }
    generation = {
        carrier: value
        for carrier, value in result.metrics.generation_by_carrier_mwh.items()
        if value and value > 0
    }
    total_capacity = sum(capacity.values())
    total_generation = sum(generation.values())
    renewable_capacity = sum(value for carrier, value in capacity.items() if carrier in RENEWABLE_CARRIERS)
    renewable_generation = sum(value for carrier, value in generation.items() if carrier in RENEWABLE_CARRIERS)

    return {
        "capacity_mw_by_carrier": {carrier: round(value, 1) for carrier, value in sorted(capacity.items())},
        "generation_mwh_by_carrier": {carrier: round(value, 1) for carrier, value in sorted(generation.items())},
        "total_capacity_mw": round(total_capacity, 1),
        "total_generation_mwh": round(total_generation, 1),
        "renewable_share_of_capacity_pct": round(100.0 * renewable_capacity / total_capacity, 1)
        if total_capacity
        else None,
        "renewable_share_of_generation_pct": round(100.0 * renewable_generation / total_generation, 1)
        if total_generation
        else None,
        # The national peak is the peak of the SUM, which the hourly layer
        # measures. Summing each bus's own peak would add up thirteen peaks
        # that never happen in the same hour and overstate the system.
        "peak_load_mw": market.national.peak_load_mw if market else None,
        "total_demand_mwh": round(sum(result.metrics.total_load_by_bus_mwh.values()), 1)
        if result.metrics.total_load_by_bus_mwh
        else None,
    }


def _market(market: HourlyMarket | None) -> dict:
    if market is None:
        return {"available": False}

    capture = []
    for carrier, position in market.national.carriers.items():
        if position.availability_capture_price_eur_per_mwh is None:
            continue
        reference = market.national.time_weighted_price_eur_per_mwh
        capture.append(
            {
                "carrier": carrier,
                "capture_price_eur_per_mwh": position.availability_capture_price_eur_per_mwh,
                "capture_rate_pct": round(
                    100.0 * position.availability_capture_price_eur_per_mwh / reference, 1
                )
                if reference
                else None,
                "capacity_factor_pct": position.availability_capacity_factor_pct,
                "curtailment_pct": position.curtailment_pct,
                "generation_mwh": position.generation_mwh,
            }
        )
    capture.sort(key=lambda row: row["capture_rate_pct"] or 0.0)

    duration = market.national.price_duration_eur_per_mwh
    return {
        "available": True,
        "time_weighted_price_eur_per_mwh": market.national.time_weighted_price_eur_per_mwh,
        "load_weighted_price_eur_per_mwh": market.national.load_weighted_price_eur_per_mwh,
        "price_duration_eur_per_mwh": {
            "p5": duration.p5,
            "p25": duration.p25,
            "p50": duration.p50,
            "p75": duration.p75,
            "p95": duration.p95,
        },
        "near_zero_price_hours": market.national.near_zero_price_hours,
        "capture": capture,
    }


def _network(market: HourlyMarket | None) -> dict:
    provenance = corridor_provenance()
    stress = market.network_stress if market else None

    # Only the region-to-region corridors count as transfer capacity. The
    # clustered network also wires each generator to its bus with a line, and
    # summing those stubs in inflated the figure roughly fivefold.
    corridor_capacity = sum(
        corridor["modelled_rating_mw"] or 0.0 for corridor in provenance["corridors"]
    )

    return {
        "corridor_count": provenance["corridor_count"],
        "verified_corridor_count": provenance["corroborated_count"],
        "verified_corridor_pct": provenance["corroborated_pct"],
        "total_transfer_capacity_mw": round(corridor_capacity, 1) or None,
        "mean_utilisation_pct": stress.mean_utilisation_pct if stress else None,
        "congested_corridor_hours": stress.congested_corridor_hours if stress else None,
        "mean_region_price_spread_eur_per_mwh": stress.mean_region_price_spread_eur_per_mwh if stress else None,
        "max_region_price_spread_eur_per_mwh": stress.max_region_price_spread_eur_per_mwh if stress else None,
        "corridors": [
            {
                "from": corridor.from_bus,
                "to": corridor.to_bus,
                "rating_mw": corridor.rating_mw,
                "mean_utilisation_pct": corridor.mean_utilisation_pct,
                "peak_utilisation_pct": corridor.peak_utilisation_pct,
                "congested_hours": corridor.congested_hours,
            }
            # Region-to-region corridors only: the clustered network also wires
            # each generator to its bus with a line, and those stubs are not
            # transmission.
            for corridor in (stress.corridors if stress else [])
            if "_cluster_" not in corridor.from_bus and "_cluster_" not in corridor.to_bus
        ][:6],
    }


@lru_cache(maxsize=1)
def _pipeline() -> dict:
    """The licensing registries: what has been applied for or licensed, which
    is the market opportunity rather than the operating grid."""
    rows = get_generators_summary_by_technology()
    by_technology = [
        {
            "technology": row.get("technology_category"),
            "asset_count": row.get("count_assets"),
            "capacity_mw": round(row.get("total_nominal_capacity_mw") or 0.0, 1),
        }
        for row in rows
        if row.get("technology_category")
    ]
    by_technology.sort(key=lambda row: row["capacity_mw"], reverse=True)

    return {
        "tracked_asset_count": sum(row["asset_count"] or 0 for row in by_technology),
        "tracked_capacity_mw": round(sum(row["capacity_mw"] for row in by_technology), 1),
        "by_technology": by_technology[:8],
    }


def _opportunities(result: ElectricityScenarioResult) -> dict:
    market = get_hourly_market(result.case_name)
    costs = load_technology_costs()
    region_ids = get_candidate_region_ids()

    priced = []
    for cell in load_candidate_cells():
        analysis = evaluate_candidate_investment(cell, region_ids.get(cell.id), result.metrics, costs, market)
        if analysis.irr_pct is None or analysis.npv_eur is None:
            continue
        priced.append(analysis)

    priced.sort(key=lambda analysis: analysis.irr_pct or 0.0, reverse=True)

    by_region: dict[str, float] = {}
    best_per_region_and_technology = []
    seen: set[tuple[str | None, str | None]] = set()
    for analysis in priced:
        region = analysis.region_id
        if region and (region not in by_region or (analysis.irr_pct or 0) > by_region[region]):
            by_region[region] = analysis.irr_pct or 0.0
        # Candidate cells in one region share a price and a capacity factor, so
        # they produce identical economics. Listing the same number eight times
        # is noise; one entry per region and technology is the signal.
        key = (region, analysis.carrier)
        if key in seen:
            continue
        seen.add(key)
        best_per_region_and_technology.append(analysis)

    return {
        "screened_count": len(region_ids),
        "priced_count": len(priced),
        "top": [
            {
                "candidate_id": analysis.candidate_id,
                "technology": analysis.technology,
                "region_id": analysis.region_id,
                "capacity_mw": analysis.assumed_capacity_mw,
                "irr_pct": analysis.irr_pct,
                "npv_eur": analysis.npv_eur,
                "lcoe_eur_per_mwh": analysis.lcoe_eur_per_mwh,
                "capture_price_eur_per_mwh": analysis.captured_price_eur_per_mwh,
                "capture_rate_pct": analysis.capture_rate_pct,
            }
            for analysis in best_per_region_and_technology[:TOP_OPPORTUNITY_COUNT]
        ],
        "by_region": by_region,
    }


def _regions(market: HourlyMarket | None, best_irr_by_region: dict[str, float]) -> list[dict]:
    if market is None:
        return []
    rows = []
    for region_id, position in sorted(market.by_region.items()):
        solar = position.carriers.get("solar")
        wind = position.carriers.get("wind")
        rows.append(
            {
                "region_id": region_id,
                "price_eur_per_mwh": position.time_weighted_price_eur_per_mwh,
                "load_mwh": position.load_mwh,
                "peak_load_mw": position.peak_load_mw,
                "solar_capture_eur_per_mwh": solar.availability_capture_price_eur_per_mwh if solar else None,
                "solar_capacity_factor_pct": solar.availability_capacity_factor_pct if solar else None,
                "wind_capture_eur_per_mwh": wind.availability_capture_price_eur_per_mwh if wind else None,
                "wind_capacity_factor_pct": wind.availability_capacity_factor_pct if wind else None,
                "best_candidate_irr_pct": best_irr_by_region.get(region_id),
            }
        )
    return rows


def _series(market: HourlyMarket | None) -> dict:
    if market is None or market.series is None:
        return {}
    return {
        "timestamps": market.series.timestamps,
        "national_price_eur_per_mwh": market.series.national_price_eur_per_mwh,
        "national_load_mw": market.series.national_load_mw,
        "generation_mw_by_carrier": market.series.generation_mw_by_carrier,
    }
