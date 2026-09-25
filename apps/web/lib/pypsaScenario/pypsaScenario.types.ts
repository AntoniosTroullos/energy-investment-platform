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

// What a case was actually solved with -- present once it has a result.
// Mirrors apps/api's ElectricityScenarioParameters.
export type ElectricityScenarioParameters = {
  annual_growth_rate: number | null;
  snapshot_strategy: string | null;
  forecast_model: string | null;
  scenario_multiplier: number | null;
};

export type ElectricityScenarioResult = {
  case_name: string;
  target_year: number;
  solved: boolean;
  message: string;
  objective_eur: number | null;
  metrics: ScenarioMetrics;
  parameters: ElectricityScenarioParameters | null;
  solved_at_utc: string | null;
};

// Whether anything a result depends on changed after it was solved (model
// code, model input tables, or -- for coupled -- the parent electricity
// case). Mirrors apps/api's app/staleness.py.
export type StaleReasonCode = "model_code_changed" | "model_inputs_changed" | "parent_resolved";

export type StaleReason = {
  code: StaleReasonCode;
  detail: string;
  changed_at: string;
};

export type Staleness = {
  solved_at: string | null;
  is_stale: boolean;
  reasons: StaleReason[];
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
  electricity_staleness: Staleness | null;
  coupled_staleness: Staleness | null;
  annual_growth_rate: number | null;
  solved_at_utc: string | null;
};

// ---------------------------------------------------------------------------
// GET /scenarios/options -- valid parameter choices, read from the real
// upstream source (h2_market_scenarios.csv for the coupled combinations) so
// the pickers below never hard-code a list that can drift from it. Mirrors
// apps/api's app/scenario_options.py.
// ---------------------------------------------------------------------------

export type ElectricityYearOption = {
  year: number;
  solved: boolean;
};

export type CoupledScenarioOption = {
  target_year: number;
  h2_market_scenario: string;
  label: string;
  // Whether run_coupled_scenario's own precondition (electricity case solved
  // for this year) is met right now.
  electricity_solved: boolean;
};

export type ScenarioOptions = {
  target_year_min: number;
  target_year_max: number;
  annual_growth_rate_min: number;
  annual_growth_rate_max: number;
  annual_growth_rate_default: number;
  electricity_years: ElectricityYearOption[];
  coupled_options: CoupledScenarioOption[];
};

export type ScenarioListResponse = {
  scenarios: ScenarioListItem[];
};

// ---------------------------------------------------------------------------
// Spatial results -- GET /scenarios/{case}/map/regions,
// GET /scenarios/compare/map/regions, and GET /scenarios/network-topology.
// Both region endpoints return a plain GeoJSON FeatureCollection; these types
// name only the properties the spatial view reads (the real payload also
// carries admin boundary fields -- name, name_el, iso3166_2, ... -- read
// straight off the feature for display, not worth typing here).
// ---------------------------------------------------------------------------

// The metrics both a single-scenario region and a delta region carry, before
// the "_a" / "_b" / "_delta" suffixing the delta endpoint applies to each.
export type RegionMetricId =
  | "generation_mwh"
  | "total_load_mwh"
  | "net_position_mwh"
  | "average_marginal_price_eur_per_mwh"
  | "peak_load_mw";

export type ScenarioRegionProperties = {
  id: string;
  name: string;
  scenario_case_name: string;
} & Record<RegionMetricId, number | null>;

// One row per REGION_METRIC_KEYS entry, each as <key>_a / <key>_b / <key>_delta
// -- see apps/api's get_scenario_regions_delta_geojson.
export type ScenarioRegionDeltaProperties = {
  id: string;
  name: string;
  scenario_case_name_a: string;
  scenario_case_name_b: string;
} & {
  [K in RegionMetricId as `${K}_a` | `${K}_b` | `${K}_delta`]: number | null;
};

export type TransmissionCorridorProperties = {
  id: string;
  bus0: string;
  bus1: string;
  s_nom_mw: number | null;
};

// ---------------------------------------------------------------------------
// Coupled gas/hydrogen/heat scenario (Phase 5). Layers onto an already-solved
// electricity case for the same year -- see CoupledScenarioPanel.tsx. Mirrors
// apps/api's CoupledScenarioResult (app/scenario_models.py), which itself
// mirrors pythonProject1's build_and_solve_coupled_year.py -- a script
// confirmed to be under active, uncommitted development upstream, hence the
// optional/nullable fields throughout.
// ---------------------------------------------------------------------------

// Which (year, scenario) pairs are valid comes from GET /scenarios/options
// (CoupledScenarioOption, above) -- reading h2_market_scenarios.csv directly
// -- rather than being frozen here as a small literal union.
export type CoupledScenarioParams = {
  targetYear: number;
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
