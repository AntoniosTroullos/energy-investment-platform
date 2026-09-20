import type { AssetSelection } from "../types/asset";

export const emptyFeatureCollection: GeoJSON.FeatureCollection = {
  type: "FeatureCollection",
  features: [],
};

export function assetSelectionsToFeatureCollection(
  assets: AssetSelection[],
): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: assets.map((asset) => ({
      ...asset.feature,
      properties: {
        ...asset.properties,
      },
    })),
  };
}
