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
  // A candidate cell's geometry may now be a MultiPolygon: land_constraints.py
  // (apps/api/pipeline) clips real exclusion zones (Natura 2000 for solar,
  // banned regions/islands for wind) out of the raw grid square, and the
  // remainder isn't always a single simply-connected shape. Averaged across
  // every ring of every part -- an approximation (the true area centroid
  // would weight larger parts more), but this centroid only feeds a coarse
  // "is this roughly in a Natura area" screening check, not the map's own
  // rendering of the (already-correct) geometry itself.
  const rings =
    geometry.type === "Polygon"
      ? geometry.coordinates
      : geometry.type === "MultiPolygon"
        ? geometry.coordinates.flat()
        : null;

  if (!rings || rings.length === 0) {
    return null;
  }

  let sumLongitude = 0;
  let sumLatitude = 0;
  let pointCount = 0;

  for (const ring of rings) {
    for (const [longitude, latitude] of ring) {
      sumLongitude += longitude;
      sumLatitude += latitude;
      pointCount += 1;
    }
  }

  if (pointCount === 0) {
    return null;
  }

  return [sumLongitude / pointCount, sumLatitude / pointCount] as [number, number];
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
