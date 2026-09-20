from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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
)
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
from .models import (
    ClimateAssetResponse,
    GreeceMarketSignalResponse,
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
from .scenario_runner import ScenarioPreconditionError, ScenarioRunError
from .settings import settings
from .system_status import SystemStatusResponse, get_system_status
from .scenarios import (
    get_coupled_scenario_result,
    get_coupled_scenario_status,
    get_generator_clusters_geojson,
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
    except ScenarioPreconditionError as exc:
        # Checked before the broader ScenarioRunError (its own superclass) --
        # 428 lets the frontend render a distinct "solve electricity first"
        # state instead of a generic run-conflict error.
        raise HTTPException(status_code=428, detail=str(exc)) from exc
    except ScenarioRunError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/scenarios/{case_name}/coupled/status", response_model=ScenarioStatusResponse)
def scenarios_coupled_status(case_name: str) -> ScenarioStatusResponse:
    return get_coupled_scenario_status(case_name)


@app.get("/scenarios/{case_name}/coupled/result", response_model=CoupledScenarioResult)
def scenarios_coupled_result(case_name: str) -> CoupledScenarioResult:
    try:
        return get_coupled_scenario_result(case_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/generator-clusters")
def generator_clusters():
    try:
        return get_generator_clusters_geojson()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
