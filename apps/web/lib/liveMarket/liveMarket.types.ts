// Mirrors apps/api/app/market_api.py -- the live balancing market layer.
//
// The reason this exists alongside the day-ahead market signal: day-ahead and
// balancing are not two views of one price. Over the trailing year the API
// measures, day-ahead ran about 115 hours below zero and settled balancing
// over 1,400, and in Greece it is the balancing market that physically
// dispatches storage. So a battery valued on day-ahead alone is valued in a
// market it does not operate in.

export type FeedStatus = "live" | "stale" | "unavailable";

export type FeedState = {
  key: string;
  label: string;
  source: string;
  status: FeedStatus;
  what_it_is_for: string;
  cadence_minutes: number;
  expected_lag_minutes: number;
  refreshed_at_utc: string | null;
  age_minutes: number | null;
  covers_to_utc: string | null;
  /** Negative for a feed that publishes ahead of real time, as day-ahead does. */
  lag_minutes: number | null;
  detail: string | null;
};

export type ReserveRequirement = {
  product: string;
  mean_mw: number;
  max_mw: number;
  min_mw: number;
};

export type StorageFleetBehaviour = {
  units: number;
  periods_charging: number;
  periods_discharging: number;
  charged_mwh: number;
  discharged_mwh: number;
  average_charge_price_eur_per_mwh: number | null;
  average_discharge_price_eur_per_mwh: number | null;
  round_trip_spread_eur_per_mwh: number | null;
};

export type ImbalanceStatistics = {
  periods: number;
  from_utc: string | null;
  to_utc: string | null;
  mean_eur_per_mwh: number;
  median_eur_per_mwh: number;
  p10_eur_per_mwh: number;
  p90_eur_per_mwh: number;
  min_eur_per_mwh: number;
  max_eur_per_mwh: number;
  negative_periods: number;
  system_short_periods: number;
  system_long_periods: number;
  mean_price_when_short_eur_per_mwh: number | null;
  mean_price_when_long_eur_per_mwh: number | null;
  short_long_spread_eur_per_mwh: number | null;
  activated_up_mwh: number | null;
  activated_down_mwh: number | null;
};

export type MfrrStatistics = {
  mean_up_eur_per_mwh: number;
  mean_down_eur_per_mwh: number;
  median_up_eur_per_mwh: number;
  median_down_eur_per_mwh: number;
  max_up_eur_per_mwh: number;
  min_down_eur_per_mwh: number;
  mean_spread_eur_per_mwh: number;
  negative_down_periods: number;
};

export type PricingAttribution = {
  periods: number;
  set_by_mfrr_up: number;
  set_by_mfrr_down: number;
  set_by_neither: number;
  set_by_mfrr_up_pct: number;
  set_by_mfrr_down_pct: number;
  set_by_neither_pct: number;
};

export type BalancingDay = {
  file_name: string;
  periods: number;
  from_utc: string;
  to_utc: string;
  timestamps_utc: string[];
  price_up_eur_per_mwh: (number | null)[];
  price_down_eur_per_mwh: (number | null)[];
  system_load_mw: (number | null)[];
  renewables_mw: (number | null)[];
  storage_mw: (number | null)[];
  mean_price_up_eur_per_mwh: number | null;
  mean_price_down_eur_per_mwh: number | null;
  reserve_requirements: ReserveRequirement[];
  storage_fleet: StorageFleetBehaviour | null;
};

export type BalancingYearSummary = {
  from_utc: string;
  to_utc: string;
  hours: number;
  missing_hours: number;
  files_used: number;
  mean_eur_per_mwh: number;
  median_eur_per_mwh: number;
  p10_eur_per_mwh: number;
  p90_eur_per_mwh: number;
  min_eur_per_mwh: number;
  max_eur_per_mwh: number;
  negative_hours: number;
  /** What hourly averaging of the settled quarter-hours discards. */
  mean_intra_hour_spread_eur_per_mwh: number;
  source: string;
};

export type DayAheadComparison = {
  day_ahead_year: number | null;
  day_ahead_mean_eur_per_mwh: number | null;
  day_ahead_negative_hours: number | null;
  balancing_mean_eur_per_mwh: number | null;
  balancing_negative_hours: number | null;
  negative_hour_ratio: number | null;
  mean_premium_eur_per_mwh: number | null;
};

export type LiveMarketResponse = {
  generated_at_utc: string;
  feeds: FeedState[];
  imbalance: ImbalanceStatistics | null;
  mfrr: MfrrStatistics | null;
  pricing_attribution: PricingAttribution | null;
  settlement_file: string | null;
  day: BalancingDay | null;
  trailing_year: BalancingYearSummary | null;
  comparison: DayAheadComparison | null;
  notes: string[];
};
