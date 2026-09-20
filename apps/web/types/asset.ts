export type AssetType =
  | "plant"
  | "substation"
  | "line"
  | "gasPipeline"
  | "gasImportPoint"
  | "hydrogenPipeline"
  | "hydrogenProject"
  | "cell";

export type SourceReference = {
  source_name?: string;
  source_url?: string;
  fields_supported?: string[];
  retrieved_at?: string;
  [key: string]: unknown;
};

export type AssetProperties = Record<string, unknown> & {
  technology?: string;
  technology_label?: string;
  technology_category?: string;
  carrier?: string;
  operator?: string;
  owner?: string;
  developer?: string;
  status?: string;
  capacity_mw?: number | string | null;
  nominal_capacity_mw?: number | string | null;
  generation_capacity_mw?: number | string | null;
  pumping_capacity_mw?: number | string | null;
  energy_capacity_mwh?: number | string | null;
  storage_duration_hours?: number | string | null;
  round_trip_efficiency?: number | string | null;
  upper_reservoir?: string | null;
  lower_reservoir?: string | null;
  reservoir_system?: string | null;
  source_confidence?: number | string | null;
  source_refs?: Array<string | SourceReference>;
  region?: string | null;
  regional_unit?: string | null;
  municipality?: string | null;
  grid_operator?: string | null;
  connection_level?: string | null;
  primary_source?: string | null;
  last_seen?: string | null;
  last_updated?: string | null;
  project_type?: string | null;
  hydrogen_role?: string | null;
  hydrogen_type?: string | null;
  electrolyzer_capacity_mw?: number | string | null;
  annual_output_tpa?: number | string | null;
  location_confidence?: string | null;
  pipeline_code?: string | null;
  pipeline_category?: string | null;
  development_stage?: string | null;
  target_year?: number | string | null;
  country_code?: string | null;
  location_type?: string | null;
  capacity_gwh_per_day?: number | string | null;
  length_km?: number | string | null;
  estimated_cost_eur?: string | null;
  geometry_confidence?: string | null;
  display_on_map?: boolean;
};

export type AssetSelection = {
  id: string;
  name: string;
  assetType: AssetType;
  properties: AssetProperties;
  feature: GeoJSON.Feature;
};

export type FocusRequest = {
  asset: AssetSelection;
  timestamp: number;
};

export type ViewportBounds = {
  west: number;
  south: number;
  east: number;
  north: number;
};
