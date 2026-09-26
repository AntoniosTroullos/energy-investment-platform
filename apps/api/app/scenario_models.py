from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .staleness import Staleness

RunState = Literal["not_found", "running", "crashed", "done"]

# Limits and default of the electricity run request. Defined once because both
# the request validation below and GET /scenarios/options (which the frontend
# builds its pickers from) must agree on them.
TARGET_YEAR_MIN = 2026
TARGET_YEAR_MAX = 2060
GROWTH_RATE_MIN = -0.05
GROWTH_RATE_MAX = 0.10
GROWTH_RATE_DEFAULT = 0.01


class ElectricityScenarioRunRequest(BaseModel):
    target_year: int = Field(ge=TARGET_YEAR_MIN, le=TARGET_YEAR_MAX)
    annual_growth_rate: float = Field(default=GROWTH_RATE_DEFAULT, ge=GROWTH_RATE_MIN, le=GROWTH_RATE_MAX)
    # Refetch demand data from ENTSO-E instead of using the cached copy --
    # run_multiyear_electricity.py's own --force-fetch flag, previously never
    # forwarded by this bridge at all.
    force_fetch: bool = False


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


class ElectricityScenarioParameters(BaseModel):
    """The inputs a case was solved with, echoed back so a result is never
    shown without the parameters that produced it. A deliberate whitelist of
    the upstream result's `request` block (no extra="allow" here, unlike this
    file's other upstream-mirroring models): that block also carries absolute
    local file paths (base_config_path, regional_features_path, ...), which
    must not leak into an API response. Unlisted keys are silently dropped."""

    annual_growth_rate: float | None = None
    snapshot_strategy: str | None = None
    forecast_model: str | None = None
    scenario_multiplier: float | None = None
    force_fetch: bool | None = None


class ElectricityScenarioResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    case_name: str
    target_year: int
    solved: bool
    message: str
    objective_eur: float | None = None
    metrics: ScenarioMetrics
    parameters: ElectricityScenarioParameters | None = None
    solved_at_utc: str | None = None


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
    # What this case was solved with (None until it has a result).
    annual_growth_rate: float | None = None
    solved_at_utc: str | None = None
    # Coupled gas/hydrogen/heat solve layered on this electricity case, if one
    # has been run (state "not_found" when it hasn't). Only headline numbers --
    # the full result lives at GET /scenarios/{case}/coupled/result.
    coupled_state: RunState = "not_found"
    coupled_objective_eur_per_year: float | None = None
    coupled_annual_heat_twh: float | None = None
    coupled_h2_electrolysis_output_mwh: float | None = None
    # Whether model code/inputs (or, for coupled, the parent electricity case)
    # changed after each result was solved. None when there is no result.
    electricity_staleness: Staleness | None = None
    coupled_staleness: Staleness | None = None


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
    # Which (year, scenario) pairs are valid is defined by pypsa-greece/data/
    # static/h2_market_scenarios.csv, not by this file. They used to be frozen
    # here as Literals (today: one scenario, 3 years) and had to be edited in
    # three places whenever that CSV grew. Now the combination is checked
    # against the CSV at request time (scenario_options.validate_coupled_request
    # -> a clean 422 instead of a crashed subprocess), so a new row there is
    # picked up with no code change.
    target_year: int = Field(default=2030, ge=TARGET_YEAR_MIN, le=TARGET_YEAR_MAX)
    h2_market_scenario: str = "baseline_no_trade"
    # Two alternate storage-modeling methods build_and_solve_coupled_year.py
    # supports in place of its default representative-days snapshots -- see
    # that script's own mutual-exclusion check (run_coupled_year, top of
    # function), mirrored here so a bad combination is a clean 422 rather
    # than a subprocess that launches and then raises.
    chronological_storage: bool = False
    linked_representative_periods: bool = False

    @model_validator(mode="after")
    def _check_storage_methods_are_exclusive(self) -> "CoupledScenarioRunRequest":
        if self.chronological_storage and self.linked_representative_periods:
            raise ValueError(
                "chronological_storage and linked_representative_periods are mutually "
                "exclusive -- choose at most one alternate storage-modeling method."
            )
        return self


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
