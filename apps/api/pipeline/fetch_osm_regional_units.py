from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib import error, parse, request

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import osm2geojson
from shapely.geometry import shape

SOURCE_DIR = BASE_DIR / "data" / "source"
OVERPASS_URLS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Greece's ~74 Regional Units ("Περιφερειακές Ενότητες") are OSM admin_level=6
# relations -- the correct tier for the May-2026 draft spatial-planning framework's
# 1.5%-max-solar-coverage-per-regional-unit rule. Unlike the 13 admin_level=5
# Regions (fetch_osm_admin_regions.py), Regional Units carry no ISO 3166-2 code in
# OSM, so osm_relation_id is the only stable join key here.
EXPECTED_MIN_REGIONAL_UNITS = 70


def main():
    elements = fetch_overpass(build_regional_unit_query())
    units_geojson = build_units_geojson(elements)

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    write_geojson(SOURCE_DIR / "regional_units.geojson", units_geojson)

    print(f"Fetched {len(units_geojson['features'])} Greek regional units (admin_level=6).")


def build_regional_unit_query() -> str:
    return """
[out:json][timeout:180];
area["ISO3166-1"="GR"][admin_level=2]->.greece;
relation["boundary"="administrative"]["admin_level"="6"](area.greece);
(._;>;);
out geom;
""".strip()


def fetch_overpass(query: str) -> list[dict]:
    encoded_query = parse.urlencode({"data": query}).encode("utf-8")
    last_error = None

    for overpass_url in OVERPASS_URLS:
        http_request = request.Request(
            overpass_url,
            data=encoded_query,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "energy-investment-platform/0.1",
            },
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=420) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload.get("elements", [])
        except json.JSONDecodeError as request_error:
            last_error = request_error
            continue
        except error.HTTPError as request_error:
            last_error = request_error
            continue
        except error.URLError as request_error:
            last_error = request_error
            continue

    if last_error is not None:
        raise last_error

    raise RuntimeError("No Overpass request could be completed.")


def build_units_geojson(elements: list[dict]) -> dict:
    raw_geojson = osm2geojson.json2geojson({"elements": elements})
    relation_features = [
        feature
        for feature in raw_geojson["features"]
        if feature.get("properties", {}).get("type") == "relation"
    ]

    features = []
    seen_relation_ids = set()

    for feature in relation_features:
        tags = feature["properties"].get("tags", {})
        osm_relation_id = feature["properties"].get("id")
        name = tags.get("name:en") or tags.get("name")

        if not name or osm_relation_id is None:
            continue

        geometry = shape(feature["geometry"])
        if not geometry.is_valid or geometry.is_empty:
            raise ValueError(f"Invalid or empty geometry for regional unit: {name} ({osm_relation_id})")

        if osm_relation_id in seen_relation_ids:
            continue
        seen_relation_ids.add(osm_relation_id)

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "osm_relation_id": osm_relation_id,
                    "name": name,
                    "name_el": tags.get("name"),
                    "area_km2": round(geodesic_area_km2(geometry), 2),
                },
                "geometry": feature["geometry"],
            }
        )

    if len(features) < EXPECTED_MIN_REGIONAL_UNITS:
        raise ValueError(
            f"Only found {len(features)} regional units, expected at least "
            f"{EXPECTED_MIN_REGIONAL_UNITS} -- Overpass response likely incomplete."
        )

    features.sort(key=lambda f: f["properties"]["name"])

    return {"type": "FeatureCollection", "features": features}


def geodesic_area_km2(geometry) -> float:
    # Same equal-area-projection approach as fetch_greek_islands.py's area calc --
    # shapely geometries here are in WGS84 lon/lat degrees, whose raw .area is not
    # a real area. Reproject to Greece's national grid (EGSA87 / EPSG:2100, already
    # a project dependency via pyproj) before measuring.
    import pyproj
    from shapely.ops import transform

    project = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:2100", always_xy=True).transform
    projected = transform(project, geometry)
    return projected.area / 1_000_000.0


def write_geojson(path: Path, feature_collection: dict):
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(feature_collection, output_file, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
