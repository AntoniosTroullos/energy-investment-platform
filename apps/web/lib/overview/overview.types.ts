// The shape of GET /overview (apps/api/app/overview.py) -- everything the
// national dashboard renders, in one call.
//
// Two different ideas of capacity appear here on purpose: `fleet` is what is
// operating on the system today, `pipeline` is what has been applied for or
// licensed. The second is roughly ten times the first, and showing them as one
// number is the usual way an energy dashboard misleads.

export type OverviewFleet = {
  capacity_mw_by_carrier: Record<string, number>;
  generation_mwh_by_carrier: Record<string, number>;
  total_capacity_mw: number;
  total_generation_mwh: number;
  renewable_share_of_capacity_pct: number | null;
  renewable_share_of_generation_pct: number | null;
  peak_load_mw: number | null;
  total_demand_mwh: number | null;
};

export type CaptureRow = {
  carrier: string;
  capture_price_eur_per_mwh: number;
  capture_rate_pct: number | null;
  capacity_factor_pct: number | null;
  curtailment_pct: number | null;
  generation_mwh: number | null;
};

export type OverviewMarket = {
  available: boolean;
  time_weighted_price_eur_per_mwh?: number | null;
  load_weighted_price_eur_per_mwh?: number | null;
  price_duration_eur_per_mwh?: {
    p5: number | null;
    p25: number | null;
    p50: number | null;
    p75: number | null;
    p95: number | null;
  };
  near_zero_price_hours?: number | null;
  capture?: CaptureRow[];
};

export type OverviewCorridor = {
  from: string;
  to: string;
  rating_mw: number | null;
  mean_utilisation_pct: number | null;
  peak_utilisation_pct: number | null;
  congested_hours: number | null;
};

export type OverviewNetwork = {
  corridor_count: number;
  verified_corridor_count: number;
  verified_corridor_pct: number | null;
  total_transfer_capacity_mw: number | null;
  mean_utilisation_pct: number | null;
  congested_corridor_hours: number | null;
  mean_region_price_spread_eur_per_mwh: number | null;
  max_region_price_spread_eur_per_mwh: number | null;
  corridors: OverviewCorridor[];
};

export type PipelineRow = {
  technology: string;
  asset_count: number | null;
  capacity_mw: number;
};

export type OverviewPipeline = {
  tracked_asset_count: number;
  tracked_capacity_mw: number;
  by_technology: PipelineRow[];
};

export type OpportunityRow = {
  candidate_id: string;
  technology: string;
  region_id: string | null;
  capacity_mw: number | null;
  irr_pct: number | null;
  npv_eur: number | null;
  lcoe_eur_per_mwh: number | null;
  capture_price_eur_per_mwh: number | null;
  capture_rate_pct: number | null;
};

export type OverviewOpportunities = {
  screened_count: number;
  priced_count: number;
  top: OpportunityRow[];
  by_region: Record<string, number>;
};

export type OverviewRegion = {
  region_id: string;
  price_eur_per_mwh: number | null;
  load_mwh: number | null;
  peak_load_mw: number | null;
  solar_capture_eur_per_mwh: number | null;
  solar_capacity_factor_pct: number | null;
  wind_capture_eur_per_mwh: number | null;
  wind_capacity_factor_pct: number | null;
  best_candidate_irr_pct: number | null;
};

export type OverviewSeries = {
  timestamps?: string[];
  national_price_eur_per_mwh?: number[];
  national_load_mw?: number[];
  generation_mw_by_carrier?: Record<string, number[]>;
};

export type OverviewResponse = {
  generated_at_utc: string;
  case_name: string;
  target_year: number;
  fleet: OverviewFleet;
  market: OverviewMarket;
  network: OverviewNetwork;
  pipeline: OverviewPipeline;
  opportunities: OverviewOpportunities;
  regions: OverviewRegion[];
  series: OverviewSeries;
};

// --- the live market feed (GET /market/greece), fetched separately so a slow
// third-party API never delays the dashboard ------------------------------

export type DayAheadPoint = { timestamp: string; priceEurMwh: number };

export type DayAheadCapture = {
  carrier: string;
  capturePriceEurMwh: number;
  flatMeanEurMwh: number;
  captureRatePct: number | null;
  basis: string;
};

export type DayAheadCurve = {
  source: string;
  redistributionAllowed: boolean;
  licenseNote: string | null;
  unit: string;
  pointCount: number;
  fromUtc: string;
  toUtc: string;
  meanEurMwh: number;
  minEurMwh: number;
  maxEurMwh: number;
  medianEurMwh: number;
  spreadEurMwh: number;
  negativePricePoints: number;
  points: DayAheadPoint[];
  capture: DayAheadCapture[];
};

export type MarketSignal = {
  status: string;
  summary: string;
  totalImportMw: number;
  totalExportMw: number;
  netImportMw: number;
  currentPrice: { valueEurMwh: number | null; label: string };
  dayAheadCurve: DayAheadCurve | null;
};
