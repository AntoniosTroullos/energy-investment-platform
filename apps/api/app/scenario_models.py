from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RunState = Literal["not_found", "running", "crashed", "done"]


class ElectricityScenarioRunRequest(BaseModel):
    target_year: int = Field(ge=2026, le=2060)
    annual_growth_rate: float = Field(default=0.01, ge=-0.05, le=0.10)


class ElectricityScenarioRunResponse(BaseModel):
    case_name: str
    state: RunState


class ScenarioStatusResponse(BaseModel):
    case_name: str
    state: RunState
    pid: int | None = None
    message: str | None = None


class ScenarioMetrics(BaseModel):
    """Mirrors pypsa-greece's real src/metrics.py output. Loosely typed on
    purpose: this schema is owned by actively-evolving upstream code (a
    separate coding agent's work, not this repo). extra="allow" means a
    newly-added upstream metrics key surfaces to API consumers rather than
    causing a validation error the moment that code changes."""

    model_config = ConfigDict(extra="allow")

    installed_capacity_by_carrier_mw: dict[str, float] = Field(default_factory=dict)
    peak_load_by_bus_mw: dict[str, float] = Field(default_factory=dict)
    total_load_by_bus_mwh: dict[str, float] = Field(default_factory=dict)
    optimized_capacity_by_carrier_mw: dict[str, float] = Field(default_factory=dict)
    generation_by_carrier_mwh: dict[str, float] = Field(default_factory=dict)
    generation_by_bus_mwh: dict[str, float] = Field(default_factory=dict)
    average_marginal_price_by_bus: dict[str, float] = Field(default_factory=dict)
    capacity_factor_by_generator: dict[str, float] = Field(default_factory=dict)
    curtailment_by_carrier_mwh: dict[str, float] = Field(default_factory=dict)
    technology_summary: dict[str, dict[str, float]] = Field(default_factory=dict)
    storage_discharge_by_unit_mwh: dict[str, float] = Field(default_factory=dict)
    storage_charge_by_unit_mwh: dict[str, float] = Field(default_factory=dict)
    storage_final_state_of_charge_mwh: dict[str, float] = Field(default_factory=dict)


class ElectricityScenarioResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    case_name: str
    target_year: int
    solved: bool
    message: str
    objective_eur: float | None = None
    metrics: ScenarioMetrics


class ScenarioListItem(BaseModel):
    """One row of the scenario library (GET /scenarios). Deliberately only
    covers case directories this bridge itself created (see scenarios.py's
    ELECTRICITY_CASE_PATTERN) -- other case types sitting in the same
    pypsa_scenarios/ root (built directly via the upstream CLI, not this
    bridge) use a different, incompatible result schema and are left out
    rather than mis-normalized."""

    case_name: str
    target_year: int
    state: RunState
    solved: bool | None = None
    message: str | None = None
    objective_eur: float | None = None
    generation_by_carrier_mwh: dict[str, float] = Field(default_factory=dict)
    # Coupled gas/hydrogen/heat solve layered on this electricity case, if one
    # has been run (state "not_found" when it hasn't). Only headline numbers --
    # the full result lives at GET /scenarios/{case}/coupled/result.
    coupled_state: RunState = "not_found"
    coupled_objective_eur_per_year: float | None = None
    coupled_annual_heat_twh: float | None = None
    coupled_h2_electrolysis_output_mwh: float | None = None


class ScenarioListResponse(BaseModel):
    scenarios: list[ScenarioListItem]


# ---------------------------------------------------------------------------
# Coupled gas/hydrogen/heat scenario (Phase 5). Layers onto an already-solved
# electricity case (see scenario_runner.run_coupled_scenario's precondition
# check) via build_and_solve_coupled_year.py, a script confirmed to be
# mid-edit/uncommitted upstream as of this writing -- see CoupledScenarioResult's
# extra="allow" and the two explicitly-optional electrolyzer-expansion fields.
# ---------------------------------------------------------------------------


class CoupledScenarioRunRequest(BaseModel):
    # Both constraints trace directly to pypsa-greece/data/static/
    # h2_market_scenarios.csv, which today has exactly one named scenario
    # ("baseline_no_trade") defined only for these 3 years. Loosen these
    # Literals the day that CSV gains more rows -- until then they turn an
    # invalid combination into a clean 422 instead of a crashed subprocess
    # (the underlying script raises ValueError for anything else).
    target_year: Literal[2030, 2040, 2050] = 2030
    h2_market_scenario: Literal["baseline_no_trade"] = "baseline_no_trade"


class CoupledScenarioRunResponse(BaseModel):
    case_name: str
    state: RunState


class H2MarketInputs(BaseModel):
    model_config = ConfigDict(extra="allow")

    scenario: str
    import_price_eur_per_mwh: float | None = None
    import_capacity_mw: float | None = None
    export_price_eur_per_mwh: float | None = None
    storage_e_nom_mwh: float | None = None
    storage_capital_cost_eur_per_mwh_year: float | None = None
    storage_standing_loss_per_hour: float | None = None


class H2Balance(BaseModel):
    model_config = ConfigDict(extra="allow")

    domestic_non_heat_load: float = 0.0
    electrolysis_output: float = 0.0
    imports: float = 0.0
    exports: float = 0.0
    hydrogen_boiler_input: float = 0.0


class CoupledScenarioResult(BaseModel):
    """Mirrors build_and_solve_coupled_year.py's real result JSON. extra="allow"
    plus optional/defaulted fields throughout because that script (and
    coupled_energy_system.py, which builds its network) is confirmed to be
    under active, uncommitted development upstream -- in particular
    electrolyzer_expansion_cost/electrolyzer_expansion_capacity_mw are a
    work-in-progress addition absent from older results on disk."""

    model_config = ConfigDict(extra="allow")

    case_name: str
    year: int
    solved: bool
    message: str
    objective_eur_per_year: float | None = None
    annual_heat_twh: float | None = None
    annual_h2_final_energy_target_twh: float | None = None
    annual_h2_assumed_within_heat_twh: float | None = None
    annual_non_heat_h2_load_twh: float | None = None
    h2_market_scenario: str | None = None
    h2_market_inputs: H2MarketInputs | None = None
    h2dria_capacity_mw: float | None = None
    h2dria_commissioning_year: int | None = None
    h2dria_available: bool | None = None
    electrolyzer_projects_included: int | None = None
    electrolyzer_projects_excluded: int | None = None
    electrolyzer_project_source: str | None = None
    electrolyzer_expansion_cost: dict = Field(default_factory=dict)
    electrolyzer_expansion_capacity_mw: dict[str, float] = Field(default_factory=dict)
    link_capacity_mw: dict[str, float] = Field(default_factory=dict)
    link_input_energy_mwh: dict[str, float] = Field(default_factory=dict)
    h2_balance_mwh: H2Balance | None = None
    average_electricity_price_eur_per_mwh: dict[str, float] = Field(default_factory=dict)
