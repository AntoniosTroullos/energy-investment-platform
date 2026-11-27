from datetime import timedelta
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from .biomass_phase1 import (
    get_biomass_phase1_candidates,
    get_biomass_phase1_quality_report,
    get_biomass_phase1_summary,
)
from .climate import get_asset_climate
from .hourly_market import HourlyMarket, available_cases, get_hourly_market
from .evaluation import (
    evaluate_scenario,
    get_candidate_feature_collection,
    get_source_layer_feature_collection,
    load_candidate_cells,
)
from . import investment_analysis
from .generators import (
    filter_feature_collection,
    get_generators_duplicates,
    get_generators_feature_collection,
    get_generators_missing_capacity,
    get_generators_missing_coordinates,
    get_generators_missing_technology,
    get_generators_pypsa_export,
    get_generators_quality_pumped_hydro,
    get_generators_quality_report,
    get_generators_quality_storage,
    get_generators_sources_coverage,
    get_generators_summary_by_region,
    get_generators_summary_by_technology,
    get_generators_summary_storage,
    is_line_feature_in_greece,
    is_point_feature_in_greece,
)
from . import market_feeds
from .live_market import build_live_market
from .market import get_greece_market_signal
from .market_api import FeedStateOut, LiveMarketResponse
from .overview import DEFAULT_OVERVIEW_CASE, build_overview
from . import asset_simulation, demand_response, hourly_series, storage_physics
from .simulation_api import (
    ActivationEventOut,
    AssetSimulationResponse,
    DemandResponseRequest,
    DemandResponseResponse,
    GenerationSimulationRequest,
    HOURS_PER_WEEK,
    HourlyWindow,
    PriceYearSummary,
    SimulatedYearOut,
    SettlementComparison,
    StorageSimulationRequest,
    StorageYearOut,
)
from .network_topology import (
    corridor_provenance,
    get_candidate_region_ids,
    get_network_topology_geojson,
)
from .models import (
    CandidateInvestmentAnalysisResponse,
    ClimateAssetResponse,
    GreeceMarketSignalResponse,
    PortfolioAnalysisRequest,
    PortfolioAnalysisResponse,
    PortfolioCandidateSummary,
    RegionalDemandAllocationResponse,
    ScenarioEvaluationRequest,
    ScenarioEvaluationResponse,
)
from .regional_demand import get_regional_demand_allocation
from .scenario_models import (
    CoupledScenarioResult,
    CoupledScenarioRunRequest,
    CoupledScenarioRunResponse,
    ElectricityScenarioResult,
    ElectricityScenarioRunRequest,
    ElectricityScenarioRunResponse,
    ScenarioListResponse,
    ScenarioStatusResponse,
)
from .scenario_options import InvalidCoupledScenarioError, ScenarioOptionsResponse, get_scenario_options
from .scenario_runner import ScenarioPreconditionError, ScenarioRunError
from .settings import settings
from .system_status import SystemStatusResponse, get_system_status
from .scenarios import (
    get_coupled_scenario_result,
    get_coupled_scenario_status,
    get_generator_clusters_geojson,
    get_scenario_regions_delta_geojson,
    get_scenario_regions_geojson,
    get_scenario_result,
    get_scenario_status,
    list_electricity_scenarios,
    start_coupled_scenario,
    start_electricity_scenario,
)


app = FastAPI(title="Energy Investment Platform API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Several GeoJSON endpoints (natura-2000, plants, etc.) serve large payloads;
# compression keeps them under the deployed platform's response size limit.
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/system/status", response_model=SystemStatusResponse)
def system_status(deep: bool = False) -> SystemStatusResponse:
    # deep=true imports the whole solver stack in the solver interpreter --
    # several seconds -- so it is opt-in; the default is a cheap file check.
    return get_system_status(deep=deep)


@app.get("/candidates")
def candidates():
    return get_candidate_feature_collection()


@app.get("/candidates/investment-analysis", response_model=CandidateInvestmentAnalysisResponse)
def candidates_investment_analysis(case_name: str) -> CandidateInvestmentAnalysisResponse:
    # Bridges the static candidate-screening cells to a real solved PyPSA
    # scenario's regional prices/generation -- see app/investment_analysis.py.
    try:
        result = get_scenario_result(case_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    region_ids = get_candidate_region_ids()
    costs = investment_analysis.load_technology_costs()
    # The hourly layer is optional by design: a case solved since the last
    # extraction run has none, and the analysis degrades to annual averages
    # rather than failing (each candidate's price_basis records which it got).
    hourly = get_hourly_market(case_name)
    analyses = [
        investment_analysis.evaluate_candidate_investment(
            cell, region_ids.get(cell.id), result.metrics, costs, hourly
        )
        for cell in load_candidate_cells()
    ]
    return CandidateInvestmentAnalysisResponse(
        case_name=case_name,
        target_year=result.target_year,
        analyses=analyses,
        assumptions=investment_analysis.assumptions_note(),
    )


@app.post("/candidates/portfolio-analysis", response_model=PortfolioAnalysisResponse)
def candidates_portfolio_analysis(request: PortfolioAnalysisRequest) -> PortfolioAnalysisResponse:
    # Combines several candidates' real cash flows into portfolio-level
    # metrics -- see app/investment_analysis.py's combine_cash_flows for why
    # portfolio IRR is NOT a weighted average of each candidate's own IRR.
    try:
        result = get_scenario_result(request.case_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    region_ids = get_candidate_region_ids()
    costs = investment_analysis.load_technology_costs()
    hourly = get_hourly_market(request.case_name)
    cells_by_id = {cell.id: cell for cell in load_candidate_cells()}

    summaries: list[PortfolioCandidateSummary] = []
    included = []
    included_flows: list[list[float]] = []

    for candidate_id in request.candidate_ids:
        cell = cells_by_id.get(candidate_id)
        if cell is None:
            summaries.append(
                PortfolioCandidateSummary(candidate_id=candidate_id, technology="unknown", message="Unknown candidate id.")
            )
            continue

        region_id = region_ids.get(candidate_id)
        analysis, flows = investment_analysis.evaluate_candidate_with_cash_flows(
            cell, region_id, result.metrics, costs, hourly
        )
        summaries.append(
            PortfolioCandidateSummary(
                candidate_id=candidate_id,
                technology=analysis.technology,
                carrier=analysis.carrier,
                region_id=analysis.region_id,
                assumed_capacity_mw=analysis.assumed_capacity_mw,
                capex_eur=analysis.capex_eur,
                npv_eur=analysis.npv_eur,
                irr_pct=analysis.irr_pct,
                message=analysis.message,
            )
        )
        if analysis.message is None:
            included.append(analysis)
            if flows is not None:
                included_flows.append(flows)

    total_capex = sum(a.capex_eur or 0.0 for a in included) if included else None
    total_capacity = sum(a.assumed_capacity_mw or 0.0 for a in included) if included else None
    total_npv = sum(a.npv_eur or 0.0 for a in included) if included else None

    combined_flows = investment_analysis.combine_cash_flows(included_flows)
    portfolio_irr = investment_analysis.irr(combined_flows) if combined_flows else None
    portfolio_payback = investment_analysis.payback_period_years(combined_flows) if combined_flows else None

    technology_breakdown = investment_analysis.build_breakdown(included, lambda a: a.carrier)
    region_breakdown = investment_analysis.build_breakdown(included, lambda a: a.region_id)
    flags = investment_analysis.concentration_flags([technology_breakdown, region_breakdown])

    return PortfolioAnalysisResponse(
        case_name=request.case_name,
        target_year=result.target_year,
        candidates=summaries,
        included_count=len(included),
        excluded_count=len(request.candidate_ids) - len(included),
        total_capex_eur=round(total_capex, 0) if total_capex is not None else None,
        total_assumed_capacity_mw=round(total_capacity, 2) if total_capacity is not None else None,
        total_npv_eur=round(total_npv, 0) if total_npv is not None else None,
        portfolio_irr_pct=round(portfolio_irr * 100, 2) if portfolio_irr is not None else None,
        portfolio_payback_years=round(portfolio_payback, 1) if portfolio_payback is not None else None,
        technology_breakdown=technology_breakdown,
        region_breakdown=region_breakdown,
        concentration_flags=flags,
        assumptions={
            **investment_analysis.assumptions_note(),
            "portfolio_combination": (
                "Portfolio IRR/payback are computed from each included candidate's own annual cash flows "
                "summed together (zero-padded to the longest lifetime), NOT an average of individual IRRs -- "
                "averaging IRRs across investments is not mathematically valid. Assumes no repowering/"
                "reinvestment after a technology's modeled lifetime ends. Portfolio NPV is the sum of each "
                "candidate's own NPV (valid regardless of differing lifetimes/discount rates)."
            ),
        },
    )


@lru_cache(maxsize=1)
def get_greek_substations() -> dict:
    feature_collection = get_source_layer_feature_collection("substations.geojson")
    return filter_feature_collection(feature_collection, is_point_feature_in_greece)


@lru_cache(maxsize=1)
def get_greek_transmission_lines() -> dict:
    feature_collection = get_source_layer_feature_collection(
        "transmission_lines.geojson"
    )
    return filter_feature_collection(feature_collection, is_line_feature_in_greece)


@app.get("/substations")
def substations():
    return get_greek_substations()


@app.get("/transmission-lines")
def transmission_lines():
    return get_greek_transmission_lines()


@app.get("/gas-pipelines")
def gas_pipelines():
    return get_source_layer_feature_collection("gas_pipelines.geojson")


@app.get("/gas-import-points")
def gas_import_points():
    return get_source_layer_feature_collection("gas_import_points.geojson")


@app.get("/hydrogen-projects")
def hydrogen_projects():
    return get_source_layer_feature_collection("hydrogen_projects.geojson")


@app.get("/hydrogen-pipelines")
def hydrogen_pipelines():
    return get_source_layer_feature_collection("hydrogen_pipelines.geojson")


@app.get("/plants")
def plants():
    return get_generators_feature_collection()


@app.get("/generators")
def generators():
    return get_generators_feature_collection()


@app.get("/generators/summary/by-technology")
def generators_summary_by_technology():
    return get_generators_summary_by_technology()


@app.get("/generators/summary/by-region")
def generators_summary_by_region():
    return get_generators_summary_by_region()


@app.get("/generators/summary/storage")
def generators_summary_storage():
    return get_generators_summary_storage()


@app.get("/generators/quality/missing-capacity")
def generators_quality_missing_capacity():
    return get_generators_missing_capacity()


@app.get("/generators/quality/missing-technology")
def generators_quality_missing_technology():
    return get_generators_missing_technology()


@app.get("/generators/quality/missing-coordinates")
def generators_quality_missing_coordinates():
    return get_generators_missing_coordinates()


@app.get("/generators/quality/duplicates")
def generators_quality_duplicates():
    return get_generators_duplicates()


@app.get("/generators/quality/report")
def generators_quality_report():
    return get_generators_quality_report()


@app.get("/generators/quality/storage")
def generators_quality_storage():
    return get_generators_quality_storage()


@app.get("/generators/quality/pumped-hydro")
def generators_quality_pumped_hydro():
    return get_generators_quality_pumped_hydro()


@app.get("/generators/quality/biomass-phase1")
def generators_quality_biomass_phase1():
    return get_biomass_phase1_quality_report()


@app.get("/generators/summary/biomass-phase1")
def generators_summary_biomass_phase1():
    return get_biomass_phase1_summary()


@app.get("/generators/candidates/biomass-phase1")
def generators_candidates_biomass_phase1():
    return get_biomass_phase1_candidates()


@app.get("/generators/sources/coverage")
def generators_sources_coverage():
    return get_generators_sources_coverage()


@app.get("/generators/export/pypsa")
def generators_export_pypsa():
    return get_generators_pypsa_export()


@app.get("/natura-2000")
def natura_2000():
    return get_source_layer_feature_collection("natura_2000.geojson")


@app.get("/admin-regions")
def admin_regions():
    return get_source_layer_feature_collection("admin_regions.geojson")


@app.get("/raaey-operating-wind")
def raaey_operating_wind():
    return get_source_layer_feature_collection("raaey_operating_wind.geojson")


@app.get("/raaey-operating-solar")
def raaey_operating_solar():
    return get_source_layer_feature_collection("raaey_operating_solar.geojson")


@app.get("/greek-energy-map-projects")
def greek_energy_map_projects():
    return get_source_layer_feature_collection("greek_energy_map_projects.geojson")


@app.get("/regional-units")
def regional_units():
    return get_source_layer_feature_collection("regional_units.geojson")


@app.get("/greek-islands")
def greek_islands():
    return get_source_layer_feature_collection("greek_islands.geojson")


@app.get("/unesco-sites")
def unesco_sites():
    return get_source_layer_feature_collection("unesco_sites_greece.geojson")


@app.get("/climate/asset", response_model=ClimateAssetResponse)
def climate_asset(
    latitude: float,
    longitude: float,
    technology: str = "Unknown",
) -> ClimateAssetResponse:
    return get_asset_climate(latitude, longitude, technology)


@app.get("/market/greece", response_model=GreeceMarketSignalResponse)
def market_greece() -> GreeceMarketSignalResponse:
    return get_greece_market_signal()


@app.get("/market/live", response_model=LiveMarketResponse)
def market_live() -> LiveMarketResponse:
    """The Greek market as it stands: settled imbalance prices, the operator's
    own schedule for today, the reserve requirements a battery would bid into,
    and how each of those compares with day-ahead.

    Each feed refreshes on its own cadence (app/market_feeds.py), so repeated
    calls are cheap and every number carries the age of the data behind it."""
    return build_live_market()


@app.get("/market/feeds", response_model=list[FeedStateOut])
def market_feed_states(refresh: bool = False) -> list[FeedStateOut]:
    """Just the freshness of each source -- for a status strip, or to check
    whether a cold number is a bug or a publication lag."""
    if refresh:
        market_feeds.reset()
    return [FeedStateOut(**vars(state)) for state in market_feeds.all_states()]


@app.get("/market/greece-boundary")
def market_greece_boundary():
    return get_source_layer_feature_collection("greece_boundary.geojson")


@app.get("/regional-demand/allocation", response_model=RegionalDemandAllocationResponse)
def regional_demand_allocation(
    timestamp_utc: str | None = None,
    national_load_mw: float | None = None,
) -> RegionalDemandAllocationResponse:
    return get_regional_demand_allocation(
        timestamp_utc=timestamp_utc,
        national_load_mw=national_load_mw,
    )


@app.post("/scenario/evaluate", response_model=ScenarioEvaluationResponse)
def evaluate_scenario_endpoint(
    request: ScenarioEvaluationRequest,
) -> ScenarioEvaluationResponse:
    return evaluate_scenario(request.scenario)


# ---------------------------------------------------------------------------
# PyPSA scenario builder -- bridges to the real solve/forecast infrastructure
# in the sibling pythonProject1 project via subprocess (see app/scenario_runner.py
# for why: apps/api's own environment is deliberately kept free of
# pandas/pypsa/linopy/highspy/xgboost). Electricity-only endpoints first,
# coupled gas/hydrogen/heat endpoints below (Phase 5 -- layers onto an
# already-solved electricity case for the same year).
# ---------------------------------------------------------------------------


@app.post("/scenarios/electricity/run", response_model=ElectricityScenarioRunResponse)
async def scenarios_electricity_run(
    request: ElectricityScenarioRunRequest,
) -> ElectricityScenarioRunResponse:
    try:
        return await start_electricity_scenario(request)
    except ScenarioRunError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/scenarios", response_model=ScenarioListResponse)
def scenarios_list() -> ScenarioListResponse:
    return list_electricity_scenarios()


@app.get("/scenarios/options", response_model=ScenarioOptionsResponse)
def scenarios_options() -> ScenarioOptionsResponse:
    # Must be declared before the /scenarios/{case_name}/... routes below --
    # FastAPI matches path routes in declaration order, and "options" would
    # otherwise be captured as a case_name by the first of those.
    return get_scenario_options()


@app.get("/scenarios/network-topology")
def scenarios_network_topology():
    # Static (region centroids + the 14 fixed corridors) -- not tied to any
    # particular case, so it lives outside the /scenarios/{case_name}/...
    # group even though it is under /scenarios.
    return get_network_topology_geojson()


@app.get("/scenarios/compare/map/regions")
def scenarios_compare_map_regions(case_a: str, case_b: str):
    # Declared before /scenarios/{case_name}/map/regions below for the same
    # reason as /scenarios/options above: "compare" would otherwise be
    # captured as a case_name by that route, which is registered first-match.
    try:
        return get_scenario_regions_delta_geojson(case_a, case_b)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/scenarios/{case_name}/status", response_model=ScenarioStatusResponse)
def scenarios_status(case_name: str) -> ScenarioStatusResponse:
    return get_scenario_status(case_name)


@app.get("/scenarios/{case_name}/result", response_model=ElectricityScenarioResult)
def scenarios_result(case_name: str) -> ElectricityScenarioResult:
    try:
        return get_scenario_result(case_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@lru_cache(maxsize=4)
def _cached_overview(case_name: str) -> dict:
    """Assembling the overview reads the whole generator registry and prices
    every candidate cell -- tens of seconds cold, milliseconds after. Cached
    per case, like the other derived layers in this module."""
    return build_overview(get_scenario_result(case_name), case_name=case_name)


# ---------------------------------------------------------------------------
# Hour-by-hour simulation (app/asset_simulation.py, storage_physics.py,
# demand_response.py). These answer the question screening cannot: what does
# THIS asset earn against the hours the market actually had?
# ---------------------------------------------------------------------------


def _price_summary(price_year: hourly_series.PriceYear) -> PriceYearSummary:
    prices = price_year.prices_eur_per_mwh
    return PriceYearSummary(
        year=price_year.year,
        source=price_year.source,
        redistribution_allowed=price_year.redistribution_allowed,
        hours=len(prices),
        missing_hours=price_year.missing_hours,
        mean_eur_per_mwh=round(price_year.mean_eur_per_mwh, 2),
        min_eur_per_mwh=round(min(prices), 2) if prices else 0.0,
        max_eur_per_mwh=round(max(prices), 2) if prices else 0.0,
        negative_hours=price_year.negative_hours,
        zero_or_negative_hours=price_year.zero_or_negative_hours,
    )


def _build_window(
    price_year: hourly_series.PriceYear,
    prices: list[float],
    output_mw: list[float],
    soc_mwh: list[float],
    requested_start: int | None,
) -> HourlyWindow:
    """One week of hourly detail. Defaults to the week containing the year's
    highest price -- where a battery makes its money and a flexible site earns
    its contract -- because a full year of traces is unusable in a browser."""
    if requested_start is None and prices:
        peak = max(range(len(prices)), key=lambda hour: prices[hour])
        start = max(0, min(peak - HOURS_PER_WEEK // 2, len(prices) - HOURS_PER_WEEK))
        label = "the week of the year's highest price"
    else:
        start = requested_start or 0
        label = f"hours {start} to {start + HOURS_PER_WEEK}"

    stop = start + HOURS_PER_WEEK
    # A balancing window is a trailing twelve months, so hour 0 is not
    # 1 January and the timestamps have to come from the series' own start.
    timestamps = hourly_series.hour_timestamps_from(
        price_year.window_start + timedelta(hours=start), min(HOURS_PER_WEEK, max(0, len(prices) - start))
    )
    return HourlyWindow(
        start_hour=start,
        label=label,
        timestamps=timestamps,
        price_eur_per_mwh=prices[start:stop],
        output_mw=output_mw[start:stop],
        state_of_charge_mwh=soc_mwh[start:stop],
    )


@app.get("/simulation/price-year/{year}", response_model=PriceYearSummary)
def simulation_price_year(year: int) -> PriceYearSummary:
    """What a calendar year of real Greek day-ahead prices looked like."""
    price_year = hourly_series.get_price_year(year)
    if price_year is None:
        raise HTTPException(status_code=404, detail=f"No price series available for {year}.")
    return _price_summary(price_year)


@app.post("/simulation/generation", response_model=AssetSimulationResponse)
def simulation_generation(request: GenerationSimulationRequest) -> AssetSimulationResponse:
    """A solar or wind plant, hour by hour, for its whole life."""
    price_year, weather = asset_simulation.load_inputs(
        request.latitude, request.longitude, request.price_year
    )
    if price_year is None:
        raise HTTPException(status_code=503, detail=f"No price series available for {request.price_year}.")
    if weather is None:
        raise HTTPException(status_code=503, detail="Could not reach the weather archive for this site.")

    simulation = asset_simulation.simulate_generation_asset(
        latitude=request.latitude,
        longitude=request.longitude,
        carrier=request.carrier,
        capacity_mw=request.capacity_mw,
        price_year=price_year,
        weather=weather,
        lifetime_years=request.lifetime_years,
        capex_eur_per_kw=request.capex_eur_per_kw,
        fixed_opex_pct_of_capex=request.fixed_opex_pct_of_capex,
        discount_rate_pct=request.discount_rate_pct,
        price_escalation_pct_per_year=request.price_escalation_pct_per_year,
        curtail_at_negative_prices=request.curtail_at_negative_prices,
        dc_ac_ratio=request.dc_ac_ratio,
    )
    return _to_response(simulation, price_year, request.window_start_hour)


@app.post("/simulation/storage", response_model=AssetSimulationResponse)
def simulation_storage(request: StorageSimulationRequest) -> AssetSimulationResponse:
    """A battery, hour by hour, with state of charge and degradation carried
    across the whole of its life."""
    price_year = _storage_price_series(request)
    spec = storage_physics.BatterySpec(
        power_mw=request.power_mw,
        energy_capacity_mwh=request.energy_capacity_mwh,
        round_trip_efficiency=request.round_trip_efficiency,
        min_soc_fraction=request.min_soc_fraction,
        max_soc_fraction=request.max_soc_fraction,
        cycle_cost_eur_per_mwh=request.cycle_cost_eur_per_mwh,
        grid_charge_eur_per_mwh=request.grid_charge_eur_per_mwh,
        max_cycles_per_day=request.max_cycles_per_day,
        calendar_fade_pct_per_year=request.calendar_fade_pct_per_year,
        cycle_fade_pct_per_equivalent_cycle=request.cycle_fade_pct_per_equivalent_cycle,
    )
    if spec.max_soc_fraction <= spec.min_soc_fraction:
        raise HTTPException(status_code=422, detail="max_soc_fraction must exceed min_soc_fraction.")

    simulation = asset_simulation.simulate_storage_asset(
        spec=spec,
        price_year=price_year,
        lifetime_years=request.lifetime_years,
        capex_eur_per_kwh=request.capex_eur_per_kwh,
        fixed_opex_pct_of_capex=request.fixed_opex_pct_of_capex,
        discount_rate_pct=request.discount_rate_pct,
        price_escalation_pct_per_year=request.price_escalation_pct_per_year,
        settlement=request.settlement,
    )
    response = _to_response(simulation, price_year, request.window_start_hour)
    if request.compare_settlements:
        response.comparison = _settlement_comparison(request, spec)
    return response


def _storage_price_series(request: StorageSimulationRequest) -> hourly_series.PriceYear:
    """The hourly series to settle the battery against.

    Balancing is offered because it is the market that physically dispatches
    storage in Greece; day-ahead remains available because a merchant battery
    trading only the day-ahead spread is a real strategy, just a different
    one."""
    if request.settlement == asset_simulation.SETTLEMENT_BALANCING:
        year = market_feeds.payload("balancing_year")
        if year is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "No settled balancing prices are available. IPTO's settlement files could not be "
                    "reached and nothing is cached."
                ),
            )
        return asset_simulation.balancing_price_series(year)

    price_year = hourly_series.get_price_year(request.price_year)
    if price_year is None:
        raise HTTPException(status_code=503, detail=f"No price series available for {request.price_year}.")
    return price_year


def _settlement_comparison(
    request: StorageSimulationRequest, spec: storage_physics.BatterySpec
) -> SettlementComparison | None:
    """The same battery, same physics, in the other market.

    Run with traces off and economics only, because this is a sanity check
    beside the headline result, not a second full result."""
    other = (
        asset_simulation.SETTLEMENT_DAY_AHEAD
        if request.settlement == asset_simulation.SETTLEMENT_BALANCING
        else asset_simulation.SETTLEMENT_BALANCING
    )
    try:
        series = _storage_price_series(request.model_copy(update={"settlement": other}))
    except HTTPException:
        return None  # The other basis is unavailable; the headline result stands alone.

    simulation = asset_simulation.simulate_storage_asset(
        spec=spec,
        price_year=series,
        lifetime_years=request.lifetime_years,
        capex_eur_per_kwh=request.capex_eur_per_kwh,
        fixed_opex_pct_of_capex=request.fixed_opex_pct_of_capex,
        discount_rate_pct=request.discount_rate_pct,
        price_escalation_pct_per_year=request.price_escalation_pct_per_year,
        settlement=other,
        keep_traces=False,
    )
    first = simulation.storage_years[0] if simulation.storage_years else None
    return SettlementComparison(
        settlement=other,
        price_window=series.window_label,
        mean_price_eur_per_mwh=round(series.mean_eur_per_mwh, 2),
        negative_hours=series.negative_hours,
        lifetime_revenue_eur=simulation.lifetime_revenue_eur,
        npv_eur=simulation.npv_eur,
        irr_pct=simulation.irr_pct,
        first_year_margin_eur=round(first.gross_margin_eur, 2) if first else None,
        first_year_cycles=first.equivalent_full_cycles if first else None,
    )


def _to_response(
    simulation: asset_simulation.AssetSimulation,
    price_year: hourly_series.PriceYear,
    window_start: int | None,
) -> AssetSimulationResponse:
    return AssetSimulationResponse(
        kind=simulation.kind,
        carrier=simulation.carrier,
        capacity_mw=simulation.capacity_mw,
        price_year=simulation.price_year,
        price_source=simulation.price_source,
        lifetime_years=simulation.lifetime_years,
        settlement=simulation.settlement,
        price_window=simulation.price_window or price_year.window_label,
        years=[SimulatedYearOut(**vars(year)) for year in simulation.years],
        storage_years=[
            StorageYearOut(
                year_index=year.year_index,
                capacity_retention_pct=year.capacity_retention_pct,
                usable_energy_mwh=year.usable_energy_mwh,
                energy_charged_mwh=year.energy_charged_mwh,
                energy_discharged_mwh=year.energy_discharged_mwh,
                charging_cost_eur=year.charging_cost_eur,
                discharge_revenue_eur=year.discharge_revenue_eur,
                cycle_cost_eur=year.cycle_cost_eur,
                gross_margin_eur=round(year.gross_margin_eur, 2),
                equivalent_full_cycles=year.equivalent_full_cycles,
                hours_charging=year.hours_charging,
                hours_discharging=year.hours_discharging,
                negative_price_hours_charged=year.negative_price_hours_charged,
                average_charge_price_eur_per_mwh=(
                    round(year.average_charge_price_eur_per_mwh, 2)
                    if year.average_charge_price_eur_per_mwh is not None
                    else None
                ),
                average_discharge_price_eur_per_mwh=(
                    round(year.average_discharge_price_eur_per_mwh, 2)
                    if year.average_discharge_price_eur_per_mwh is not None
                    else None
                ),
            )
            for year in simulation.storage_years
        ],
        capex_eur=simulation.capex_eur,
        npv_eur=simulation.npv_eur,
        irr_pct=simulation.irr_pct,
        payback_years=simulation.payback_years,
        lifetime_revenue_eur=simulation.lifetime_revenue_eur,
        price_summary=_price_summary(price_year),
        window=_build_window(
            price_year,
            price_year.prices_eur_per_mwh,
            simulation.first_year_output_mw,
            simulation.first_year_soc_mwh,
            window_start,
        ),
        notes=simulation.notes,
    )


@app.post("/simulation/demand-response", response_model=DemandResponseResponse)
def simulation_demand_response(request: DemandResponseRequest) -> DemandResponseResponse:
    """What an industrial site's flexibility is worth: the availability fee for
    standing ready, the payment when the operator calls, and the saving from
    simply not running the expensive hours -- less what stopping costs."""
    price_year = hourly_series.get_price_year(request.price_year)
    if price_year is None:
        raise HTTPException(status_code=503, detail=f"No price series available for {request.price_year}.")

    if request.profile == "custom":
        if not request.custom_load_mw:
            raise HTTPException(status_code=422, detail="A custom profile needs custom_load_mw.")
        load = request.custom_load_mw
    elif request.profile == "two_shift":
        load = demand_response.two_shift_load(request.average_load_mw, request.base_load_mw)
    else:
        load = demand_response.continuous_process_load(request.average_load_mw)

    site = demand_response.IndustrialSite(
        name=request.name,
        baseline_load_mw=load,
        interruptible_fraction=request.interruptible_fraction,
        production_loss_eur_per_mwh=request.production_loss_eur_per_mwh,
        rebound_fraction=request.rebound_fraction,
        shiftable_fraction=request.shiftable_fraction,
    )
    contracts = [
        demand_response.InterruptibilityContract(
            product=demand_response.InterruptibilityProduct(contract.product),
            contracted_mw=contract.contracted_mw,
            availability_price_eur_per_mw_year=contract.availability_price_eur_per_mw_year,
            activation_price_eur_per_mwh=contract.activation_price_eur_per_mwh,
            max_activation_hours_per_year=contract.max_activation_hours_per_year,
            max_activations_per_year=contract.max_activations_per_year,
            max_duration_hours=contract.max_duration_hours,
            min_hours_between_activations=contract.min_hours_between_activations,
        )
        for contract in request.contracts
    ]

    result = demand_response.simulate_demand_response(
        site, price_year.prices_eur_per_mwh, contracts, year=price_year.year
    )
    return DemandResponseResponse(
        site_name=result.site_name,
        year=result.year,
        price_source=price_year.source,
        annual_consumption_mwh=round(site.annual_consumption_mwh, 1),
        baseline_energy_cost_eur=result.baseline_energy_cost_eur,
        availability_revenue_eur=result.availability_revenue_eur,
        activation_revenue_eur=result.activation_revenue_eur,
        avoided_energy_cost_eur=result.avoided_energy_cost_eur,
        load_shifting_saving_eur=result.load_shifting_saving_eur,
        production_loss_eur=result.production_loss_eur,
        rebound_cost_eur=result.rebound_cost_eur,
        net_benefit_eur=round(result.net_benefit_eur, 2),
        net_benefit_pct_of_energy_bill=(
            round(result.net_benefit_pct_of_energy_bill, 2)
            if result.net_benefit_pct_of_energy_bill is not None
            else None
        ),
        activation_count=result.activation_count,
        activation_hours=result.activation_hours,
        energy_not_consumed_mwh=result.energy_not_consumed_mwh,
        events=[ActivationEventOut(**vars(event)) for event in result.events[:50]],
        notes=result.notes,
    )


@app.get("/overview")
def overview(case_name: str = DEFAULT_OVERVIEW_CASE) -> dict:
    """Everything the national overview dashboard renders, in one call: the
    operating fleet, modelled prices and capture rates, network stress and
    verification, the project pipeline, and the ranked investment
    opportunities. No live third-party calls -- the market feed is its own
    endpoint so a slow upstream never delays this one."""
    try:
        return _cached_overview(case_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/scenarios/network-topology/provenance")
def scenarios_network_topology_provenance() -> dict:
    """What the modelled 13-region network is made of, and how much of it the
    real transmission layer corroborates -- corridor by corridor, so "stylised"
    is a measurement a reader can check rather than a disclaimer in prose."""
    return corridor_provenance()


@app.get("/scenarios/hourly-market/cases")
def scenarios_hourly_market_cases() -> dict:
    """Which cases have an extracted hourly layer. The frontend asks this once
    so it can tell a user why a case shows capture prices and another does not,
    instead of silently showing two different kinds of number side by side."""
    return {"cases": available_cases()}


@app.get("/scenarios/{case_name}/hourly-market", response_model=HourlyMarket)
def scenarios_hourly_market(case_name: str) -> HourlyMarket:
    """The hour-by-hour market position of a solved case: capture prices per
    technology per region, the price-duration shape, and corridor utilisation.
    See app/hourly_market.py for why an annual average cannot answer the same
    questions."""
    market = get_hourly_market(case_name)
    if market is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No hourly market layer for '{case_name}'. Extract it with "
                "pipeline/extract_hourly_market.py (needs the solver environment)."
            ),
        )
    return market


@app.get("/scenarios/{case_name}/map/regions")
def scenarios_map_regions(case_name: str):
    try:
        return get_scenario_regions_geojson(case_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/scenarios/coupled/run", response_model=CoupledScenarioRunResponse)
async def scenarios_coupled_run(
    request: CoupledScenarioRunRequest,
) -> CoupledScenarioRunResponse:
    try:
        return await start_coupled_scenario(request)
    except InvalidCoupledScenarioError as exc:
        # The (year, scenario) pair itself isn't one the CSV defines -- a
        # malformed request (422), distinct from the 428/409 cases below
        # (a well-formed request whose precondition isn't met yet, or that
        # collides with a run already in progress).
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ScenarioPreconditionError as exc:
        # Checked before the broader ScenarioRunError (its own superclass) --
        # 428 lets the frontend render a distinct "solve electricity first"
        # state instead of a generic run-conflict error.
        raise HTTPException(status_code=428, detail=str(exc)) from exc
    except ScenarioRunError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/scenarios/{case_name}/coupled/status", response_model=ScenarioStatusResponse)
def scenarios_coupled_status(
    case_name: str,
    chronological_storage: bool = False,
    linked_representative_periods: bool = False,
) -> ScenarioStatusResponse:
    return get_coupled_scenario_status(case_name, chronological_storage, linked_representative_periods)


@app.get("/scenarios/{case_name}/coupled/result", response_model=CoupledScenarioResult)
def scenarios_coupled_result(
    case_name: str,
    chronological_storage: bool = False,
    linked_representative_periods: bool = False,
) -> CoupledScenarioResult:
    try:
        return get_coupled_scenario_result(case_name, chronological_storage, linked_representative_periods)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/generator-clusters")
def generator_clusters():
    try:
        return get_generator_clusters_geojson()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
