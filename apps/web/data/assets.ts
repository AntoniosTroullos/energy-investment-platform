// Builds one shared list of backend-loaded assets so search and selection use the same shape.
import type { AssetSelection, AssetType } from "../types/asset";

export function buildSelections(
  featureCollection: GeoJSON.FeatureCollection,
  assetType: AssetType,
) {
  return featureCollection.features.map((feature, index) => {
    const properties = feature.properties ? { ...feature.properties } : {};
    const fallbackId = `${assetType}-${index + 1}`;
    const id = String(properties.id ?? fallbackId);
    const name =
      typeof properties.name === "string" && properties.name.trim().length > 0
        ? properties.name
        : id;

    return {
      id,
      name,
      assetType,
      properties,
      feature,
    } satisfies AssetSelection;
  });
}
