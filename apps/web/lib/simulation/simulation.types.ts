// Mirrors apps/api/app/simulation_api.py -- the hour-by-hour simulation
// endpoints. These answer what screening cannot: what one asset earns against
// the hours the market actually had, for its whole life.

export type PriceYearSummary = {
  year: number;
  source: string;
  redistribution_allowed: boolean;
  hours: number;
  missing_hours: number;
  mean_eur_per_mwh: number;
  min_eur_per_mwh: number;
  max_eur_per_mwh: number;
  negative_hours: number;
  zero_or_negative_hours: number;
};

export type HourlyWindow = {
  start_hour: number;
  label: string;
  timestamps: string[];
  price_eur_per_mwh: number[];
  output_mw: number[];
  state_of_charge_mwh: number[];
};

export type SimulatedYear = {
  year_index: number;
  generation_mwh: number;
  curtailed_mwh: number;
  revenue_eur: number;
  capture_price_eur_per_mwh: number | null;
  capacity_factor_pct: number;
  hours_producing: number;
  hours_curtailed: number;
  output_retention_pct: number;
};

export type StorageYear = {
  year_index: number;
  capacity_retention_pct: number;
  usable_energy_mwh: number;
  energy_charged_mwh: number;
  energy_discharged_mwh: number;
  charging_cost_eur: number;
  discharge_revenue_eur: number;
  cycle_cost_eur: number;
  gross_margin_eur: number;
  equivalent_full_cycles: number;
  hours_charging: number;
  hours_discharging: number;
  negative_price_hours_charged: number;
  average_charge_price_eur_per_mwh: number | null;
  average_discharge_price_eur_per_mwh: number | null;
};

export type SettlementBasis = "day_ahead" | "balancing";

/** The same asset, same physics, valued in the other market. The gap is the
 *  finding: a battery priced on day-ahead alone is valued in a market it does
 *  not physically operate in. */
export type SettlementComparison = {
  settlement: SettlementBasis;
  price_window: string;
  mean_price_eur_per_mwh: number;
  negative_hours: number;
  lifetime_revenue_eur: number;
  npv_eur: number | null;
  irr_pct: number | null;
  first_year_margin_eur: number | null;
  first_year_cycles: number | null;
};

export type AssetSimulation = {
  kind: "generation" | "storage";
  carrier: string;
  capacity_mw: number;
  price_year: number;
  price_source: string;
  lifetime_years: number;
  settlement: SettlementBasis;
  /** The window the prices cover, e.g. "settled balancing, 2025-11-22 to 2026-11-22". */
  price_window: string;
  years: SimulatedYear[];
  storage_years: StorageYear[];
  capex_eur: number | null;
  npv_eur: number | null;
  irr_pct: number | null;
  payback_years: number | null;
  lifetime_revenue_eur: number;
  price_summary: PriceYearSummary | null;
  window: HourlyWindow | null;
  comparison: SettlementComparison | null;
  notes: string[];
};

export type GenerationRequest = {
  latitude: number;
  longitude: number;
  carrier: "solar" | "wind";
  capacity_mw: number;
  price_year?: number;
  lifetime_years?: number;
  capex_eur_per_kw?: number | null;
  discount_rate_pct?: number;
  curtail_at_negative_prices?: boolean;
};

export type StorageRequest = {
  power_mw: number;
  energy_capacity_mwh: number;
  round_trip_efficiency?: number;
  cycle_cost_eur_per_mwh?: number;
  grid_charge_eur_per_mwh?: number;
  max_cycles_per_day?: number;
  price_year?: number;
  lifetime_years?: number;
  capex_eur_per_kwh?: number | null;
  discount_rate_pct?: number;
  /** "balancing" settles against a trailing year of IPTO's settled imbalance
   *  prices -- the market that actually dispatches storage in Greece. */
  settlement?: SettlementBasis;
  compare_settlements?: boolean;
};

export type InterruptibilityContract = {
  product: "type_1" | "type_2";
  contracted_mw: number;
  availability_price_eur_per_mw_year?: number | null;
  activation_price_eur_per_mwh?: number;
  max_activations_per_year?: number;
  max_duration_hours?: number;
};

export type DemandResponseRequest = {
  name: string;
  profile: "continuous" | "two_shift";
  average_load_mw: number;
  base_load_mw?: number;
  interruptible_fraction: number;
  production_loss_eur_per_mwh: number;
  rebound_fraction?: number;
  shiftable_fraction?: number;
  price_year?: number;
  contracts: InterruptibilityContract[];
};

export type ActivationEvent = {
  start_hour: number;
  duration_hours: number;
  energy_not_consumed_mwh: number;
  payment_eur: number;
  avoided_energy_cost_eur: number;
  production_loss_eur: number;
  price_at_activation_eur_per_mwh: number;
};

export type DemandResponseResult = {
  site_name: string;
  year: number;
  price_source: string;
  annual_consumption_mwh: number;
  baseline_energy_cost_eur: number;
  availability_revenue_eur: number;
  activation_revenue_eur: number;
  avoided_energy_cost_eur: number;
  load_shifting_saving_eur: number;
  production_loss_eur: number;
  rebound_cost_eur: number;
  net_benefit_eur: number;
  net_benefit_pct_of_energy_bill: number | null;
  activation_count: number;
  activation_hours: number;
  energy_not_consumed_mwh: number;
  events: ActivationEvent[];
  notes: string[];
};
