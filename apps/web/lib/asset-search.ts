import { getPlantTechnologyCategory } from "./plant-categories";
import { getVoltageDisplayValue } from "./voltage";
import type { AssetSelection } from "../types/asset";

export function getSearchResultTitle(asset: AssetSelection) {
  const assetTypeLabel =
    asset.assetType === "plant"
      ? "Plant"
      : asset.assetType === "substation"
        ? "Substation"
      : asset.assetType === "line"
          ? "Line"
          : asset.assetType === "gasPipeline"
            ? "Gas Pipeline"
            : asset.assetType === "gasImportPoint"
              ? "Gas Import"
              : asset.assetType === "hydrogenPipeline"
                ? "Hydrogen Pipeline"
              : asset.assetType === "hydrogenProject"
                ? "Hydrogen Project"
                : "Cell";

  const secondaryLabel =
    asset.assetType === "plant"
      ? getPlantTechnologyCategory(asset)
      : asset.assetType === "gasPipeline"
        ? String(asset.properties.pipeline_role ?? "Gas network")
        : asset.assetType === "gasImportPoint"
          ? String(asset.properties.import_type ?? "Import point")
          : asset.assetType === "hydrogenPipeline"
            ? String(asset.properties.development_stage ?? "Hydrogen pipeline")
          : asset.assetType === "hydrogenProject"
            ? String(asset.properties.project_type ?? "Hydrogen project")
            : getVoltageDisplayValue(asset.properties.voltage_kv);

  return `${assetTypeLabel} - ${secondaryLabel} - ${asset.name}`;
}

export function getSearchResultSubtitle(asset: AssetSelection) {
  const subtitleParts = [asset.id];
  const operator = asset.properties.operator;
  const connectedSystem = asset.properties.connected_system;
  const hydrogenRole = asset.properties.hydrogen_role;

  if (operator !== undefined && operator !== null && String(operator).trim().length > 0) {
    subtitleParts.push(`Operator: ${String(operator)}`);
  }

  if (
    connectedSystem !== undefined &&
    connectedSystem !== null &&
    String(connectedSystem).trim().length > 0
  ) {
    subtitleParts.push(`System: ${String(connectedSystem)}`);
  }

  if (
    hydrogenRole !== undefined &&
    hydrogenRole !== null &&
    String(hydrogenRole).trim().length > 0
  ) {
    subtitleParts.push(`Role: ${String(hydrogenRole)}`);
  }

  return subtitleParts.join(" - ");
}
