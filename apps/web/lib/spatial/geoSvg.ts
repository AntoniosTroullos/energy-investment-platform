// Projects GeoJSON (lon/lat) geometry into an SVG viewBox, for a schematic
// results map that renders as plain inline SVG -- no tile server, no MapLibre
// instance, exportable as a static image. Deliberately not a general-purpose
// map projection: an equirectangular projection with a single cos(latitude)
// aspect correction is accurate enough at Greece's ~5-degree latitude span
// (the error a proper conic projection would remove is invisible at the
// schematic scale this view renders at) and needs no new dependency.

export type LonLat = [number, number];

export type GeoBounds = {
  west: number;
  south: number;
  east: number;
  north: number;
};

export type Projector = (lonLat: LonLat) => [number, number];

/** Bounding box across every coordinate in a set of feature collections
 * (regions + corridors together, so both project into the same frame). */
export function computeBounds(featureCollections: readonly GeoJSON.FeatureCollection[]): GeoBounds {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;

  for (const collection of featureCollections) {
    for (const feature of collection.features) {
      for (const [longitude, latitude] of iterateCoordinates(feature.geometry)) {
        west = Math.min(west, longitude);
        south = Math.min(south, latitude);
        east = Math.max(east, longitude);
        north = Math.max(north, latitude);
      }
    }
  }

  if (!Number.isFinite(west)) {
    // No coordinates at all -- fall back to a Greece-sized box so callers
    // always get a usable projector rather than one built on Infinity.
    return { west: 19, south: 34.5, east: 30, north: 42 };
  }

  return { west, south, east, north };
}

/** A projector mapping GeoBounds into [0, width] x [0, height], preserving
 * aspect ratio (letterboxed, not stretched) with padding on every side. */
export function buildProjector(
  bounds: GeoBounds,
  width: number,
  height: number,
  padding: number,
): Projector {
  const meanLatitudeRadians = ((bounds.north + bounds.south) / 2) * (Math.PI / 180);
  const cosLatitude = Math.cos(meanLatitudeRadians);

  const lonSpan = Math.max(bounds.east - bounds.west, 1e-6);
  const latSpan = Math.max(bounds.north - bounds.south, 1e-6);

  // Longitude degrees are narrower than latitude degrees away from the
  // equator -- scale x by cos(latitude) so a degree of each covers
  // proportionally the same ground distance instead of stretching the map.
  const projectedWidth = lonSpan * cosLatitude;
  const projectedHeight = latSpan;

  const availableWidth = width - padding * 2;
  const availableHeight = height - padding * 2;
  const scale = Math.min(availableWidth / projectedWidth, availableHeight / projectedHeight);

  const drawnWidth = projectedWidth * scale;
  const drawnHeight = projectedHeight * scale;
  const offsetX = padding + (availableWidth - drawnWidth) / 2;
  const offsetY = padding + (availableHeight - drawnHeight) / 2;

  return ([longitude, latitude]) => {
    const x = offsetX + (longitude - bounds.west) * cosLatitude * scale;
    // SVG y grows downward; latitude grows northward -- flip it.
    const y = offsetY + (bounds.north - latitude) * scale;
    return [x, y];
  };
}

function* iterateCoordinates(geometry: GeoJSON.Geometry | null): Generator<LonLat> {
  if (!geometry) {
    return;
  }

  switch (geometry.type) {
    case "Point":
      yield geometry.coordinates as LonLat;
      return;
    case "MultiPoint":
    case "LineString":
      yield* geometry.coordinates as LonLat[];
      return;
    case "MultiLineString":
    case "Polygon":
      for (const ring of geometry.coordinates as LonLat[][]) {
        yield* ring;
      }
      return;
    case "MultiPolygon":
      for (const polygon of geometry.coordinates as LonLat[][][]) {
        for (const ring of polygon) {
          yield* ring;
        }
      }
      return;
    case "GeometryCollection":
      for (const sub of geometry.geometries) {
        yield* iterateCoordinates(sub);
      }
  }
}

/** An SVG path `d` string for a Polygon/MultiPolygon. Rings are drawn as
 * separate closed subpaths under fill-rule="evenodd", the standard technique
 * for holes to render as holes without any special-casing here. */
export function polygonToSvgPath(geometry: GeoJSON.Geometry, project: Projector): string {
  const polygons: LonLat[][][] =
    geometry.type === "Polygon"
      ? [geometry.coordinates as LonLat[][]]
      : geometry.type === "MultiPolygon"
        ? (geometry.coordinates as LonLat[][][])
        : [];

  return polygons
    .flatMap((polygon) =>
      polygon.map((ring) => {
        const points = ring.map(project);
        const [first, ...rest] = points;
        if (!first) {
          return "";
        }
        const lineTo = rest.map(([x, y]) => `L${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
        return `M${first[0].toFixed(2)},${first[1].toFixed(2)} ${lineTo} Z`;
      }),
    )
    .join(" ");
}

/** An SVG path `d` string for a LineString (a transmission corridor). */
export function lineToSvgPath(geometry: GeoJSON.Geometry, project: Projector): string {
  if (geometry.type !== "LineString") {
    return "";
  }
  const points = (geometry.coordinates as LonLat[]).map(project);
  const [first, ...rest] = points;
  if (!first) {
    return "";
  }
  const lineTo = rest.map(([x, y]) => `L${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
  return `M${first[0].toFixed(2)},${first[1].toFixed(2)} ${lineTo}`;
}
