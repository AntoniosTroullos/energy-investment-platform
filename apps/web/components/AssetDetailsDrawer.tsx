"use client";

import { getScoreExplanation } from "../lib/score-explanation";
import type { AssetSelection } from "../types/asset";

type AssetDetailsDrawerProps = {
  asset: AssetSelection;
  onClose: () => void;
  isCompared?: boolean;
  compareLimitReached?: boolean;
  onAddToCompare?: (asset: AssetSelection) => void;
  onRemoveFromCompare?: (assetId: string) => void;
};

export default function AssetDetailsDrawer({
  asset,
  onClose,
  isCompared = false,
  compareLimitReached = false,
  onAddToCompare,
  onRemoveFromCompare,
}: AssetDetailsDrawerProps) {
  const details = Object.entries(asset.properties).filter(
    ([, value]) => value !== undefined && value !== null,
  );
  const summaryFields = getSummaryFields(asset);
  const groupedProperties = getGroupedProperties(details, summaryFields);
  const scoreExplanation = getScoreExplanation(asset);

  return (
    <aside className="flex w-96 shrink-0 flex-col border-l border-white/10 bg-zinc-900 px-6 py-6">
      <div className="flex items-start justify-between border-b border-white/10 pb-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
            Asset Details
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-100">
            {asset.name}
          </h2>
          <p className="mt-2 text-sm text-zinc-400">{formatAssetType(asset.assetType)}</p>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="rounded-lg border border-white/10 px-3 py-2 text-sm text-zinc-300 transition hover:bg-white/5"
        >
          Close
        </button>
      </div>

      {asset.assetType === "cell" ? (
        <div className="mt-4">
          {isCompared ? (
            <button
              type="button"
              onClick={() => onRemoveFromCompare?.(asset.id)}
              className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-zinc-100 transition hover:bg-white/10"
            >
              Remove From Compare
            </button>
          ) : (
            <button
              type="button"
              onClick={() => onAddToCompare?.(asset)}
              disabled={compareLimitReached}
              className="w-full rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm font-medium text-emerald-300 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-zinc-500"
            >
              {compareLimitReached ? "Compare Limit Reached" : "Add To Compare"}
            </button>
          )}
        </div>
      ) : null}

      <div className="mt-6 space-y-4 overflow-y-auto">
        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
            {asset.assetType === "cell" ? "Summary" : "Infrastructure Summary"}
          </p>
          <dl className="mt-4 space-y-3">
            {summaryFields.map((field) => (
              <div key={field.label}>
                <dt className="text-xs text-zinc-500">{field.label}</dt>
                <dd className="mt-1 text-sm text-zinc-100">{field.value}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
            Properties
          </p>
          <dl className="mt-4 space-y-3">
            {groupedProperties.map(([key, value]) => (
              <div key={key}>
                <dt className="text-xs text-zinc-500">{formatLabel(key)}</dt>
                <dd className="mt-1 break-words text-sm text-zinc-100">
                  {formatValue(value)}
                </dd>
              </div>
            ))}
          </dl>
        </div>

        {scoreExplanation ? (
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
              Score Explanation
            </p>

            <div className="mt-4 space-y-4">
              <div>
                <p className="text-xs text-zinc-500">Strengths</p>
                <ul className="mt-2 space-y-2 text-sm text-zinc-100">
                  {scoreExplanation.strengths.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>

              <div>
                <p className="text-xs text-zinc-500">Penalties</p>
                <ul className="mt-2 space-y-2 text-sm text-zinc-100">
                  {scoreExplanation.penalties.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>

              <div>
                <p className="text-xs text-zinc-500">Summary</p>
                <p className="mt-2 text-sm text-zinc-100">
                  {scoreExplanation.summary}
                </p>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </aside>
  );
}

function formatAssetType(assetType: AssetSelection["assetType"]) {
  if (assetType === "plant") {
    return "Power Plant";
  }

  if (assetType === "substation") {
    return "Substation";
  }

  if (assetType === "line") {
    return "Transmission Line";
  }

  if (assetType === "gasPipeline") {
    return "Gas Pipeline";
  }

  if (assetType === "gasImportPoint") {
    return "Gas Import Point";
  }

  if (assetType === "hydrogenPipeline") {
    return "Hydrogen Pipeline";
  }

  if (assetType === "hydrogenProject") {
    return "Hydrogen Project";
  }

  return "Suitability Cell";
}

function getSummaryFields(asset: AssetSelection) {
  const baseFields = [
    { key: "name", label: "Name", value: asset.name },
    { key: "assetType", label: "Asset Type", value: formatAssetType(asset.assetType) },
    { key: "id", label: "Asset ID", value: asset.id },
  ];

  if (asset.assetType === "plant") {
    const pumpedHydroSummaryFields = isPumpedHydroAsset(asset)
      ? [
          {
            key: "generation_capacity_mw",
            label: "Generation Capacity",
            value: formatCapacity(
              asset.properties.generation_capacity_mw ??
                asset.properties.nominal_capacity_mw ??
                asset.properties.capacity_mw,
            ),
          },
          {
            key: "pumping_capacity_mw",
            label: "Pumping Capacity",
            value: formatCapacity(asset.properties.pumping_capacity_mw),
          },
          {
            key: "energy_capacity_mwh",
            label: "Energy Capacity",
            value: formatEnergyCapacity(asset.properties.energy_capacity_mwh),
          },
          {
            key: "storage_duration_hours",
            label: "Storage Duration",
            value: formatStorageDuration(asset.properties.storage_duration_hours),
          },
          {
            key: "upper_reservoir",
            label: "Upper Reservoir",
            value: formatValue(asset.properties.upper_reservoir ?? "Unknown"),
          },
          {
            key: "lower_reservoir",
            label: "Lower Reservoir",
            value: formatValue(asset.properties.lower_reservoir ?? "Unknown"),
          },
          {
            key: "developer",
            label: "Developer",
            value: formatValue(asset.properties.developer ?? "Unknown"),
          },
        ]
      : [];

    return [
      ...baseFields,
      {
        key: "technology",
        label: "Technology",
        value: formatTechnologyLabel(asset.properties),
      },
      {
        key: "technology_category",
        label: "Technology Category",
        value: formatValue(asset.properties.technology_category ?? "Other/Unknown"),
      },
      ...pumpedHydroSummaryFields,
      {
        key: "nominal_capacity_mw",
        label: "Nominal Capacity",
        value: formatCapacity(
          asset.properties.nominal_capacity_mw ?? asset.properties.capacity_mw,
        ),
      },
      {
        key: "operator",
        label: "Operator",
        value: formatValue(asset.properties.operator ?? "Unknown"),
      },
      {
        key: "status",
        label: "Status",
        value: formatValue(asset.properties.status ?? "Unknown"),
      },
      {
        key: "location",
        label: "Location",
        value: formatLocation(asset.properties),
      },
      {
        key: "grid_operator",
        label: "Grid Operator",
        value: formatValue(asset.properties.grid_operator ?? "Unknown"),
      },
      {
        key: "primary_source",
        label: "Primary Source",
        value: formatValue(asset.properties.primary_source ?? "Unknown"),
      },
      {
        key: "source_confidence",
        label: "Source Confidence",
        value: formatConfidence(asset.properties.source_confidence),
      },
      {
        key: "last_seen",
        label: "Last Seen",
        value: formatDateValue(
          asset.properties.last_seen ?? asset.properties.last_updated,
        ),
      },
    ];
  }

  if (asset.assetType === "substation") {
    return [
      ...baseFields,
      {
        key: "voltage_kv",
        label: "Voltage",
        value: formatVoltage(asset.properties.voltage_kv),
      },
      {
        key: "operator",
        label: "Operator",
        value: formatValue(asset.properties.operator ?? "Unknown"),
      },
      {
        key: "status",
        label: "Status",
        value: formatValue(asset.properties.status ?? "Unknown"),
      },
    ];
  }

  if (asset.assetType === "line") {
    return [
      ...baseFields,
      {
        key: "voltage_kv",
        label: "Voltage",
        value: formatVoltage(asset.properties.voltage_kv),
      },
      {
        key: "operator",
        label: "Operator",
        value: formatValue(asset.properties.operator ?? "Unknown"),
      },
      {
        key: "status",
        label: "Status",
        value: formatValue(asset.properties.status ?? "Unknown"),
      },
    ];
  }

  if (asset.assetType === "gasPipeline") {
    return [
      ...baseFields,
      {
        key: "pipeline_role",
        label: "Pipeline Role",
        value: formatValue(asset.properties.pipeline_role ?? "Unknown"),
      },
      {
        key: "diameter_in",
        label: "Diameter",
        value: formatDiameter(asset.properties.diameter_in),
      },
      {
        key: "operator",
        label: "Operator",
        value: formatValue(asset.properties.operator ?? "Unknown"),
      },
      {
        key: "status",
        label: "Status",
        value: formatValue(asset.properties.status ?? "Unknown"),
      },
    ];
  }

  if (asset.assetType === "gasImportPoint") {
    return [
      ...baseFields,
      {
        key: "import_type",
        label: "Import Type",
        value: formatValue(asset.properties.import_type ?? "Unknown"),
      },
      {
        key: "connected_system",
        label: "Connected System",
        value: formatValue(asset.properties.connected_system ?? "Unknown"),
      },
      {
        key: "design_capacity_nm3h",
        label: "Design Capacity",
        value: formatGasCapacity(asset.properties.design_capacity_nm3h),
      },
      {
        key: "operator",
        label: "Operator",
        value: formatValue(asset.properties.operator ?? "Unknown"),
      },
      {
        key: "status",
        label: "Status",
        value: formatValue(asset.properties.status ?? "Unknown"),
      },
    ];
  }

  if (asset.assetType === "hydrogenPipeline") {
    return [
      ...baseFields,
      {
        key: "pipeline_code",
        label: "Pipeline Code",
        value: formatValue(asset.properties.pipeline_code ?? "Unknown"),
      },
      {
        key: "pipeline_category",
        label: "Pipeline Category",
        value: formatValue(asset.properties.pipeline_category ?? "Unspecified"),
      },
      {
        key: "hydrogen_role",
        label: "Hydrogen Role",
        value: formatValue(asset.properties.hydrogen_role ?? "Unknown"),
      },
      {
        key: "development_stage",
        label: "Development Stage",
        value: formatValue(asset.properties.development_stage ?? "Unknown"),
      },
      {
        key: "target_year",
        label: "Target Year",
        value: formatValue(asset.properties.target_year ?? "Unknown"),
      },
      {
        key: "capacity_gwh_per_day",
        label: "Transport Capacity",
        value: formatHydrogenDailyCapacity(asset.properties.capacity_gwh_per_day),
      },
      {
        key: "length_km",
        label: "Length",
        value: formatLengthKm(asset.properties.length_km),
      },
      {
        key: "operator",
        label: "Operator",
        value: formatValue(asset.properties.operator ?? "Unknown"),
      },
      {
        key: "status",
        label: "Status",
        value: formatValue(asset.properties.status ?? "Unknown"),
      },
      {
        key: "estimated_cost_eur",
        label: "Estimated Cost",
        value: formatValue(asset.properties.estimated_cost_eur ?? "Unknown"),
      },
      {
        key: "primary_source",
        label: "Primary Source",
        value: formatValue(asset.properties.primary_source ?? "Unknown"),
      },
      {
        key: "geometry_confidence",
        label: "Geometry Confidence",
        value: formatValue(asset.properties.geometry_confidence ?? "Unknown"),
      },
    ];
  }

  if (asset.assetType === "hydrogenProject") {
    return [
      ...baseFields,
      {
        key: "project_type",
        label: "Project Type",
        value: formatValue(asset.properties.project_type ?? "Unknown"),
      },
      {
        key: "hydrogen_role",
        label: "Hydrogen Role",
        value: formatValue(asset.properties.hydrogen_role ?? "Unknown"),
      },
      {
        key: "hydrogen_type",
        label: "Hydrogen Type",
        value: formatValue(asset.properties.hydrogen_type ?? "Unknown"),
      },
      {
        key: "electrolyzer_capacity_mw",
        label: "Electrolyser Capacity",
        value: formatCapacity(asset.properties.electrolyzer_capacity_mw),
      },
      {
        key: "annual_output_tpa",
        label: "Annual Output",
        value: formatAnnualHydrogenOutput(asset.properties.annual_output_tpa),
      },
      {
        key: "operator",
        label: "Operator",
        value: formatValue(asset.properties.operator ?? "Unknown"),
      },
      {
        key: "status",
        label: "Status",
        value: formatValue(asset.properties.status ?? "Unknown"),
      },
      {
        key: "location",
        label: "Location",
        value: formatLocation(asset.properties),
      },
      {
        key: "primary_source",
        label: "Primary Source",
        value: formatValue(asset.properties.primary_source ?? "Unknown"),
      },
      {
        key: "location_confidence",
        label: "Location Confidence",
        value: formatValue(asset.properties.location_confidence ?? "Unknown"),
      },
    ];
  }

  return [
    ...baseFields,
    {
      key: "technology",
      label: "Technology",
      value: formatValue(asset.properties.technology ?? "Unknown"),
    },
    {
      key: "investment_score",
      label: "Investment Score",
      value: formatValue(asset.properties.investment_score ?? "Unknown"),
    },
  ];
}

function getGroupedProperties(
  details: Array<[string, unknown]>,
  summaryFields: Array<{ key: string; label: string; value: string }>,
) {
  const summaryKeys = new Set(summaryFields.map((field) => field.key));

  return details
    .filter(([key]) => !summaryKeys.has(key))
    .sort(([leftKey], [rightKey]) => {
      const leftPriority = getPropertyPriority(leftKey);
      const rightPriority = getPropertyPriority(rightKey);

      if (leftPriority !== rightPriority) {
        return leftPriority - rightPriority;
      }

      return leftKey.localeCompare(rightKey);
    });
}

function getPropertyPriority(key: string) {
  const priorityKeys = [
    "name",
    "id",
    "technology",
    "technology_label",
    "technology_category",
    "carrier",
    "generation_capacity_mw",
    "pumping_capacity_mw",
    "energy_capacity_mwh",
    "storage_duration_hours",
    "round_trip_efficiency",
    "fuel",
    "capacity_type",
    "capacity_mw",
    "nominal_capacity_mw",
    "capacity_unit",
    "voltage_kv",
    "region",
    "regional_unit",
    "municipality",
    "grid_operator",
    "connection_level",
    "nearest_substation_id",
    "pypsa_bus",
    "primary_source",
    "source",
    "source_confidence",
    "confidence_score",
    "source_refs",
    "raw_sources",
    "upper_reservoir",
    "lower_reservoir",
    "reservoir_system",
    "developer",
    "owner",
    "reversible_units",
    "annual_generation_gwh",
    "last_seen",
    "last_updated",
    "commissioning_year",
    "decommissioning_year",
    "pipeline_role",
    "import_type",
    "connected_system",
    "diameter_in",
    "design_capacity_nm3h",
    "pipeline_code",
    "pipeline_category",
    "development_stage",
    "target_year",
    "country_code",
    "location_type",
    "capacity_gwh_per_day",
    "length_km",
    "estimated_cost_eur",
    "geometry_confidence",
    "project_type",
    "hydrogen_role",
    "hydrogen_type",
    "electrolyzer_capacity_mw",
    "annual_output_tpa",
    "location_confidence",
    "operator",
    "status",
    "osm_type",
    "osm_id",
  ];

  const index = priorityKeys.indexOf(key);
  return index === -1 ? priorityKeys.length : index;
}

function formatLabel(label: string) {
  return label
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_-]/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function formatValue(value: unknown) {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (Array.isArray(value)) {
    if (value.every((item) => typeof item === "string" || typeof item === "number")) {
      return value.join(", ");
    }

    return JSON.stringify(value, null, 2);
  }

  if (value && typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }

  return "Unknown";
}

function formatVoltage(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${value} kV`;
  }

  if (typeof value === "string" && value.trim().length > 0) {
    return value.includes("kV") ? value : `${value} kV`;
  }

  return "Unknown";
}

function formatCapacity(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${new Intl.NumberFormat("en-US", {
      maximumFractionDigits: 3,
    }).format(value)} MW`;
  }

  if (typeof value === "string" && value.trim().length > 0) {
    return value.includes("MW") ? value : `${value} MW`;
  }

  return "Unknown";
}

function formatEnergyCapacity(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${new Intl.NumberFormat("en-US", {
      maximumFractionDigits: 3,
    }).format(value)} MWh`;
  }

  if (typeof value === "string" && value.trim().length > 0) {
    return value.includes("MWh") ? value : `${value} MWh`;
  }

  return "Unknown";
}

function formatStorageDuration(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${new Intl.NumberFormat("en-US", {
      maximumFractionDigits: 3,
    }).format(value)} hours`;
  }

  if (typeof value === "string" && value.trim().length > 0) {
    return value.includes("hour") ? value : `${value} hours`;
  }

  return "Unknown";
}

function formatTechnologyLabel(properties: Record<string, unknown>) {
  if (properties.technology === "pumped_hydro") {
    return "Pumped Hydro Storage";
  }

  const technologyLabel = properties.technology_label;
  if (typeof technologyLabel === "string" && technologyLabel.trim().length > 0) {
    return technologyLabel;
  }

  const technology = properties.technology;
  if (typeof technology !== "string" || technology.trim().length === 0) {
    return "Unknown";
  }

  return technology
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatLocation(properties: Record<string, unknown>) {
  const locationParts = [
    properties.municipality,
    properties.regional_unit,
    properties.region,
  ]
    .map((value) => (typeof value === "string" ? value.trim() : ""))
    .filter((value) => value.length > 0);

  if (locationParts.length === 0) {
    return "Unknown";
  }

  return locationParts.join(", ");
}

function formatConfidence(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toFixed(2);
  }

  if (typeof value === "string" && value.trim().length > 0) {
    return value;
  }

  return "Unknown";
}

function formatDateValue(value: unknown) {
  if (typeof value !== "string" || value.trim().length === 0) {
    return "Unknown";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("en-GB", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

function isPumpedHydroAsset(asset: AssetSelection) {
  return asset.assetType === "plant" && asset.properties.technology === "pumped_hydro";
}

function formatDiameter(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${value}"`;
  }

  if (typeof value === "string" && value.trim().length > 0) {
    return value.includes("\"") ? value : `${value}"`;
  }

  return "Unknown";
}

function formatGasCapacity(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${value.toLocaleString()} Nm3/h`;
  }

  if (typeof value === "string" && value.trim().length > 0) {
    return value.includes("Nm3/h") ? value : `${value} Nm3/h`;
  }

  return "Unknown";
}

function formatAnnualHydrogenOutput(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${value.toLocaleString()} tpa`;
  }

  if (typeof value === "string" && value.trim().length > 0) {
    return value.includes("tpa") ? value : `${value} tpa`;
  }

  return "Unknown";
}

function formatHydrogenDailyCapacity(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${new Intl.NumberFormat("en-US", {
      maximumFractionDigits: 2,
    }).format(value)} GWh/day`;
  }

  if (typeof value === "string" && value.trim().length > 0) {
    return value.includes("GWh") ? value : `${value} GWh/day`;
  }

  return "Unknown";
}

function formatLengthKm(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${new Intl.NumberFormat("en-US", {
      maximumFractionDigits: 1,
    }).format(value)} km`;
  }

  if (typeof value === "string" && value.trim().length > 0) {
    return value.includes("km") ? value : `${value} km`;
  }

  return "Unknown";
}
