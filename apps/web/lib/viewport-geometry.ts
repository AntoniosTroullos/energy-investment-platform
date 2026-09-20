import type { AssetSelection, ViewportBounds } from "../types/asset";

export function getAssetsInViewCount(
  assets: AssetSelection[],
  viewportBounds: ViewportBounds | null,
) {
  return assets.filter((asset) => isAssetInViewport(asset, viewportBounds)).length;
}

export function isAssetInViewport(
  asset: AssetSelection,
  viewportBounds: ViewportBounds | null,
) {
  if (!viewportBounds) {
    return true;
  }

  const geometry = asset.feature.geometry;

  if (geometry.type === "Point") {
    return isPointInViewport(
      geometry.coordinates as [number, number],
      viewportBounds,
    );
  }

  const geometryBounds = getFeatureGeometryBounds(geometry);
  if (!geometryBounds) {
    return false;
  }

  return doBoundsOverlap(geometryBounds, viewportBounds);
}

function isPointInViewport(
  coordinates: [number, number],
  viewportBounds: ViewportBounds,
) {
  const [longitude, latitude] = coordinates;

  return (
    longitude >= viewportBounds.west &&
    longitude <= viewportBounds.east &&
    latitude >= viewportBounds.south &&
    latitude <= viewportBounds.north
  );
}

function getFeatureGeometryBounds(geometry: GeoJSON.Geometry) {
  // A GeometryCollection has no .coordinates of its own; the map layers here
  // only ever carry Point/Line/Polygon features, so treat it as empty rather
  // than recursing.
  if (geometry.type === "GeometryCollection") {
    return null;
  }

  const coordinates = collectGeometryCoordinates(geometry.coordinates);
  if (coordinates.length === 0) {
    return null;
  }

  let west = coordinates[0][0];
  let south = coordinates[0][1];
  let east = coordinates[0][0];
  let north = coordinates[0][1];

  for (const [longitude, latitude] of coordinates) {
    west = Math.min(west, longitude);
    south = Math.min(south, latitude);
    east = Math.max(east, longitude);
    north = Math.max(north, latitude);
  }

  return { west, south, east, north };
}

function doBoundsOverlap(
  left: ViewportBounds,
  right: ViewportBounds,
) {
  return !(
    left.east < right.west ||
    left.west > right.east ||
    left.north < right.south ||
    left.south > right.north
  );
}

function collectGeometryCoordinates(
  value:
    | GeoJSON.Position
    | GeoJSON.Position[]
    | GeoJSON.Position[][]
    | GeoJSON.Position[][][],
): [number, number][] {
  if (typeof value[0] === "number") {
    return [value as [number, number]];
  }

  return (
    value as Array<GeoJSON.Position | GeoJSON.Position[] | GeoJSON.Position[][]>
  ).flatMap((entry) => collectGeometryCoordinates(entry));
}
