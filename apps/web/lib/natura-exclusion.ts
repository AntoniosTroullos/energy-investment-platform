import type { AssetSelection } from "../types/asset";

export function isCandidateExcludedByNatura(
  asset: AssetSelection,
  natura2000Data: GeoJSON.FeatureCollection,
  excludeNatura2000: boolean,
) {
  if (!excludeNatura2000 || asset.assetType !== "cell") {
    return false;
  }

  const centroid = getPolygonCentroid(asset.feature.geometry);
  if (!centroid) {
    return false;
  }

  return natura2000Data.features.some((feature) =>
    geometryContainsPoint(feature.geometry, centroid),
  );
}

function getPolygonCentroid(geometry: GeoJSON.Geometry) {
  if (geometry.type !== "Polygon") {
    return null;
  }

  const ring = geometry.coordinates[0];
  if (!ring || ring.length === 0) {
    return null;
  }

  const [sumLongitude, sumLatitude] = ring.reduce(
    ([longitudeTotal, latitudeTotal], [longitude, latitude]) => [
      longitudeTotal + longitude,
      latitudeTotal + latitude,
    ],
    [0, 0],
  );

  return [sumLongitude / ring.length, sumLatitude / ring.length] as [number, number];
}

function geometryContainsPoint(
  geometry: GeoJSON.Geometry | null | undefined,
  point: [number, number],
) {
  if (!geometry) {
    return false;
  }

  if (geometry.type === "Polygon") {
    return polygonContainsPoint(geometry.coordinates, point);
  }

  if (geometry.type === "MultiPolygon") {
    return geometry.coordinates.some((polygon) =>
      polygonContainsPoint(polygon, point),
    );
  }

  return false;
}

function polygonContainsPoint(
  polygon: GeoJSON.Position[][],
  point: [number, number],
) {
  const outerRing = polygon[0];

  if (!outerRing || !ringContainsPoint(outerRing, point)) {
    return false;
  }

  return !polygon.slice(1).some((holeRing) => ringContainsPoint(holeRing, point));
}

function ringContainsPoint(
  ring: GeoJSON.Position[],
  point: [number, number],
) {
  let inside = false;
  const [targetLongitude, targetLatitude] = point;

  for (let currentIndex = 0, previousIndex = ring.length - 1; currentIndex < ring.length; previousIndex = currentIndex++) {
    const [currentLongitude, currentLatitude] = ring[currentIndex];
    const [previousLongitude, previousLatitude] = ring[previousIndex];

    const intersects =
      currentLatitude > targetLatitude !== previousLatitude > targetLatitude &&
      targetLongitude <
        ((previousLongitude - currentLongitude) * (targetLatitude - currentLatitude)) /
          (previousLatitude - currentLatitude) +
          currentLongitude;

    if (intersects) {
      inside = !inside;
    }
  }

  return inside;
}
