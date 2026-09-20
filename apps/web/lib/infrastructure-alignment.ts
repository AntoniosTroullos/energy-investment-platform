const NNGTS_MAIN_TRUNK_ID = "gas-pipeline-main-trunk";
const H2DRIA_GREEK_ROUTE_TEST_ID = "hydrogen-pipeline-h2dria-greek-part-test";

// Keep the backend source untouched and only align the displayed NNGTS trunk
// to the newer H2dria test route when that frontend-loaded route is available.
export function alignGasPipelineRoutes(
  gasFeatureCollection: GeoJSON.FeatureCollection,
  hydrogenFeatureCollection: GeoJSON.FeatureCollection,
): GeoJSON.FeatureCollection {
  const h2driaTestFeature = getFeatureById(
    hydrogenFeatureCollection,
    H2DRIA_GREEK_ROUTE_TEST_ID,
  );

  if (
    !h2driaTestFeature ||
    !h2driaTestFeature.geometry ||
    h2driaTestFeature.geometry.type !== "LineString"
  ) {
    return gasFeatureCollection;
  }

  // Captured after the guard: TypeScript drops the LineString narrowing of
  // h2driaTestFeature.geometry inside the .map() closure below.
  const trunkCoordinates = h2driaTestFeature.geometry.coordinates.map(
    (coordinate): GeoJSON.Position => [coordinate[0], coordinate[1]],
  );

  return {
    ...gasFeatureCollection,
    features: gasFeatureCollection.features.map((feature) => {
      if (feature.properties?.id !== NNGTS_MAIN_TRUNK_ID) {
        return feature;
      }

      return {
        ...feature,
        geometry: {
          type: "LineString" as const,
          coordinates: trunkCoordinates,
        },
      };
    }),
  };
}

function getFeatureById(
  featureCollection: GeoJSON.FeatureCollection,
  featureId: string,
) {
  return (
    featureCollection.features.find(
      (feature) => feature.properties?.id === featureId,
    ) ?? null
  );
}
