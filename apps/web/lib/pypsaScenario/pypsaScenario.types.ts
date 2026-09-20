// A PyPSA scenario solve is a categorically different concept from the
// existing candidate-cell screening `Scenario` (lib/scenario/scenario.types.ts):
// that one filters a static, pre-generated 42-cell GeoJSON with four
// threshold rules; this one triggers a real linear-programming solve of
// Greece's electricity network and reports back real dispatch/price/capacity
// results. Deliberately kept as a separate module, not a variant of the
// existing one.

export type RunState = "not_found" | "running" | "crashed" | "done";

export type PypsaScenarioParams = {
  targetYear: number;
  annualGrowthRate: number;
};

export type ElectricityScenarioRunResponse = {
  case_name: string;
  state: RunState;
};

export type ScenarioStatusResponse = {
  case_name: string;
  state: RunState;
  pid: number | null;
  message: string | null;
};

// Mirrors apps/api's ScenarioMetrics (app/scenario_models.py), which itself
// mirrors pypsa-greece's real src/metrics.py output. All-optional per key:
// several are only populated when solved=true, and the backend's own
// extra="allow" means the raw payload could carry more keys than listed
// here -- this type only names the ones the UI actually reads from.
export type ScenarioMetrics = {
  installed_capacity_by_carrier_mw: Record<string, number>;
  peak_load_by_bus_mw: Record<string, number>;
  total_load_by_bus_mwh: Record<string, number>;
  optimized_capacity_by_carrier_mw?: Record<string, number>;
  generation_by_carrier_mwh?: Record<string, number>;
  generation_by_bus_mwh?: Record<string, number>;
  average_marginal_price_by_bus?: Record<string, number>;
  capacity_factor_by_generator?: Record<string, number>;
  curtailment_by_carrier_mwh?: Record<string, number>;
  technology_summary?: Record<string, Record<string, number>>;
  storage_discharge_by_unit_mwh?: Record<string, number>;
  storage_charge_by_unit_mwh?: Record<string, number>;
  storage_final_state_of_charge_mwh?: Record<string, number>;
};

export type ElectricityScenarioResult = {
  case_name: string;
  target_year: number;
  solved: boolean;
  message: string;
  objective_eur: number | null;
  metrics: ScenarioMetrics;
};

// One row of the live scenario library (GET /scenarios) -- only case
// directories the scenario builder itself created (future_electricity_*),
// each with its current status and, once solved, the headline numbers a
// comparison view needs.
export type ScenarioListItem = {
  case_name: string;
  target_year: number;
  state: RunState;
  solved: boolean | null;
  message: string | null;
  objective_eur: number | null;
  generation_by_carrier_mwh: Record<string, number>;
  // Headline numbers of the coupled gas/hydrogen/heat solve layered on this
  // electricity case ("not_found" until one has been run).
  coupled_state: RunState;
  coupled_objective_eur_per_year: number | null;
  coupled_annual_heat_twh: number | null;
  coupled_h2_electrolysis_output_mwh: number | null;
};

export type ScenarioListResponse = {
  scenarios: ScenarioListItem[];
};

// ---------------------------------------------------------------------------
// Coupled gas/hydrogen/heat scenario (Phase 5). Layers onto an already-solved
// electricity case for the same year -- see CoupledScenarioPanel.tsx. Mirrors
// apps/api's CoupledScenarioResult (app/scenario_models.py), which itself
// mirrors pythonProject1's build_and_solve_coupled_year.py -- a script
// confirmed to be under active, uncommitted development upstream, hence the
// optional/nullable fields throughout.
// ---------------------------------------------------------------------------

// Both constraints trace to pypsa-greece/data/static/h2_market_scenarios.csv,
// which today has exactly one named scenario defined only for these 3 years.
export type CoupledEligibleYear = 2030 | 2040 | 2050;

export type CoupledScenarioParams = {
  targetYear: CoupledEligibleYear;
  h2MarketScenario: string;
};

export type CoupledScenarioRunResponse = {
  case_name: string;
  state: RunState;
};

export type H2MarketInputs = {
  scenario: string;
  import_price_eur_per_mwh: number | null;
  import_capacity_mw: number | null;
  export_price_eur_per_mwh: number | null;
  storage_e_nom_mwh: number | null;
  storage_capital_cost_eur_per_mwh_year: number | null;
  storage_standing_loss_per_hour: number | null;
};

export type H2Balance = {
  domestic_non_heat_load: number;
  electrolysis_output: number;
  imports: number;
  exports: number;
  hydrogen_boiler_input: number;
};

export type CoupledScenarioResult = {
  case_name: string;
  year: number;
  solved: boolean;
  message: string;
  objective_eur_per_year: number | null;
  annual_heat_twh: number | null;
  annual_h2_final_energy_target_twh: number | null;
  annual_h2_assumed_within_heat_twh: number | null;
  annual_non_heat_h2_load_twh: number | null;
  h2_market_scenario: string | null;
  h2_market_inputs: H2MarketInputs | null;
  h2dria_capacity_mw: number | null;
  h2dria_commissioning_year: number | null;
  h2dria_available: boolean | null;
  electrolyzer_projects_included: number | null;
  electrolyzer_projects_excluded: number | null;
  electrolyzer_expansion_capacity_mw: Record<string, number>;
  link_capacity_mw: Record<string, number>;
  link_input_energy_mwh: Record<string, number>;
  h2_balance_mwh: H2Balance | null;
  average_electricity_price_eur_per_mwh: Record<string, number>;
};
