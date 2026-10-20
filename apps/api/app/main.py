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
from .market import get_greece_market_signal
from .network_topology import get_candidate_region_ids, get_network_topology_geojson
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
    analyses = [
        investment_analysis.evaluate_candidate_investment(cell, region_ids.get(cell.id), result.metrics, costs)
        for cell in load_candidate_cells()
    ]
    return CandidateInvestmentAnalysisResponse(
        case_name=case_name,
        target_year=result.target_year,
        analyses=analyses,
        assumptions=investment_analysis.ASSUMPTIONS_NOTE,
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
            cell, region_id, result.metrics, costs
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
            **investment_analysis.ASSUMPTIONS_NOTE,
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
