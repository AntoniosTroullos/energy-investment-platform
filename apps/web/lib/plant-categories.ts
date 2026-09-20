import type { AssetSelection } from "../types/asset";

export type PlantTechnologyCategory =
  | "Solar"
  | "Wind"
  | "Hydro"
  | "Storage"
  | "Gas"
  | "Lignite"
  | "Oil"
  | "Biomass/Biogas"
  | "CHP"
  | "Geothermal"
  | "Other/Unknown";

export type PlantStatusCategory =
  | "Operating"
  | "Under Construction"
  | "Pre-Construction"
  | "Announced"
  | "Planned"
  | "Shelved"
  | "Retired"
  | "Cancelled"
  | "Mothballed"
  | "Unknown";

export const PLANT_TECHNOLOGY_CATEGORIES: PlantTechnologyCategory[] = [
  "Solar",
  "Wind",
  "Hydro",
  "Storage",
  "Gas",
  "Lignite",
  "Oil",
  "Biomass/Biogas",
  "CHP",
  "Geothermal",
  "Other/Unknown",
];

export const PLANT_STATUS_CATEGORIES: PlantStatusCategory[] = [
  "Operating",
  "Under Construction",
  "Pre-Construction",
  "Announced",
  "Planned",
  "Shelved",
  "Retired",
  "Cancelled",
  "Mothballed",
  "Unknown",
];

export function filterPlantAssets(
  assets: AssetSelection[],
  enabledTechnologies: PlantTechnologyCategory[],
  enabledStatuses: PlantStatusCategory[],
) {
  return assets.filter(
    (asset) =>
      matchesPlantTechnology(asset, enabledTechnologies) &&
      matchesPlantStatus(asset, enabledStatuses),
  );
}

export function matchesPlantTechnology(
  asset: AssetSelection,
  enabledTechnologies: PlantTechnologyCategory[],
) {
  const category = getPlantTechnologyCategory(asset);
  return enabledTechnologies.includes(category);
}

export function matchesPlantStatus(
  asset: AssetSelection,
  enabledStatuses: PlantStatusCategory[],
) {
  const status = getPlantStatusCategory(asset);
  return enabledStatuses.includes(status);
}

export function getPlantTechnologyCategory(
  asset: AssetSelection,
): PlantTechnologyCategory {
  const propertyValue = asset.properties.technology_category;

  if (typeof propertyValue === "string") {
    return propertyValue as PlantTechnologyCategory;
  }

  return normalizePlantTechnologyCategory(asset.properties.technology);
}

export function getPlantStatusCategory(
  asset: AssetSelection,
): PlantStatusCategory {
  const propertyValue = asset.properties.status_category;

  if (typeof propertyValue === "string") {
    return propertyValue as PlantStatusCategory;
  }

  return normalizePlantStatusCategory(asset.properties.status);
}

export function normalizePlantTechnologyCategory(
  value: unknown,
): PlantTechnologyCategory {
  const normalizedValue = String(value ?? "").trim().toLowerCase();

  if (!normalizedValue) {
    return "Other/Unknown";
  }

  if (normalizedValue === "solar" || normalizedValue.includes("solar") || normalizedValue.includes("pv")) {
    return "Solar";
  }

  if (
    normalizedValue === "wind" ||
    normalizedValue.includes("wind")
  ) {
    return "Wind";
  }

  if (normalizedValue === "hydro" || normalizedValue.includes("hydro")) {
    return "Hydro";
  }

  if (
    normalizedValue === "storage" ||
    normalizedValue.includes("storage") ||
    normalizedValue.includes("battery") ||
    normalizedValue.includes("pumped")
  ) {
    return "Storage";
  }

  if (
    normalizedValue === "gas" ||
    normalizedValue.includes("natural gas") ||
    normalizedValue === "gas" ||
    normalizedValue.includes("ccgt") ||
    normalizedValue.includes("ocgt") ||
    normalizedValue.includes("chp")
  ) {
    if (normalizedValue.includes("chp")) {
      return "CHP";
    }

    return "Gas";
  }

  if (normalizedValue === "lignite" || normalizedValue.includes("lignite")) {
    return "Lignite";
  }

  if (
    normalizedValue === "oil" ||
    normalizedValue.includes("diesel") ||
    normalizedValue.includes("oil") ||
    normalizedValue.includes("mazut")
  ) {
    return "Oil";
  }

  if (normalizedValue === "geothermal" || normalizedValue.includes("geothermal")) {
    return "Geothermal";
  }

  if (
    normalizedValue === "biomass/biogas" ||
    normalizedValue.includes("biomass") ||
    normalizedValue.includes("biogas")
  ) {
    return "Biomass/Biogas";
  }

  if (normalizedValue === "chp") {
    return "CHP";
  }

  return "Other/Unknown";
}

export function normalizePlantStatusCategory(value: unknown): PlantStatusCategory {
  const normalizedValue = String(value ?? "").trim().toLowerCase();

  if (!normalizedValue || normalizedValue === "unknown") {
    return "Unknown";
  }

  if (normalizedValue.includes("mothball")) {
    return "Mothballed";
  }

  if (normalizedValue.includes("cancel")) {
    return "Cancelled";
  }

  if (
    normalizedValue.includes("retir") ||
    normalizedValue.includes("decommission") ||
    normalizedValue.includes("closed")
  ) {
    return "Retired";
  }

  if (normalizedValue.includes("shelved")) {
    return "Shelved";
  }

  if (
    normalizedValue.includes("under construction") ||
    normalizedValue.includes("in construction") ||
    normalizedValue === "construction" ||
    normalizedValue.includes("construction")
  ) {
    return "Under Construction";
  }

  if (
    normalizedValue.includes("pre-construction") ||
    normalizedValue.includes("pre construction")
  ) {
    return "Pre-Construction";
  }

  if (normalizedValue.includes("announced")) {
    return "Announced";
  }

  if (
    normalizedValue.includes("planned") ||
    normalizedValue.includes("proposed") ||
    normalizedValue.includes("permitted") ||
    normalizedValue.includes("licensed")
  ) {
    return "Planned";
  }

  if (
    normalizedValue.includes("operat") ||
    normalizedValue.includes("active") ||
    normalizedValue.includes("commissioned")
  ) {
    return "Operating";
  }

  return "Unknown";
}

export function getPlantStatusDotClass(status: PlantStatusCategory) {
  if (status === "Operating") {
    return "bg-emerald-400";
  }

  if (status === "Under Construction") {
    return "bg-amber-400";
  }

  if (status === "Pre-Construction") {
    return "bg-sky-400";
  }

  if (status === "Announced") {
    return "bg-fuchsia-400";
  }

  if (status === "Planned") {
    return "bg-indigo-400";
  }

  if (status === "Shelved") {
    return "bg-zinc-400";
  }

  if (status === "Retired") {
    return "bg-rose-400";
  }

  if (status === "Cancelled") {
    return "bg-red-500";
  }

  if (status === "Mothballed") {
    return "bg-orange-500";
  }

  return "bg-slate-400";
}

export function addPlantExplorerProperties(asset: AssetSelection): AssetSelection {
  if (asset.assetType !== "plant") {
    return asset;
  }

  const technologyCategory = normalizePlantTechnologyCategory(
    asset.properties.technology_category ?? asset.properties.technology,
  );
  const statusCategory = normalizePlantStatusCategory(asset.properties.status);

  return {
    ...asset,
    properties: {
      ...asset.properties,
      technology_category: technologyCategory,
      status_category: statusCategory,
    },
    feature: {
      ...asset.feature,
      properties: {
        ...asset.feature.properties,
        technology_category: technologyCategory,
        status_category: statusCategory,
      },
    },
  };
}

export function isDisplayablePlantAsset(asset: AssetSelection) {
  if (asset.assetType !== "plant") {
    return true;
  }

  if (asset.properties.display_on_map === false) {
    return false;
  }

  return asset.feature.geometry !== null;
}
