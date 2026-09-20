from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib import error, parse, request

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import osm2geojson
import pyproj
from shapely.geometry import shape
from shapely.ops import transform

SOURCE_DIR = BASE_DIR / "data" / "source"
OVERPASS_URLS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# The May-2026 draft spatial-planning framework bans new wind development on
# islands under 300 km^2. OSM tags named islands with place=island on a node
# (point only, no polygon) or on a way/relation (real outline). Only the
# way/relation features carry a measurable area, so node-only islands are
# dropped here rather than given a fabricated area.
AREA_PROJECTION = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:2100", always_xy=True).transform


def main():
    elements = fetch_overpass(build_islands_query())
    islands_geojson = build_islands_geojson(elements)

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    write_geojson(SOURCE_DIR / "greek_islands.geojson", islands_geojson)

    under_threshold = sum(
        1 for f in islands_geojson["features"] if f["properties"]["area_km2"] < 300
    )
    print(
        f"Fetched {len(islands_geojson['features'])} named Greek islands with real polygons "
        f"({under_threshold} under the 300 km^2 threshold)."
    )


def build_islands_query() -> str:
    # Ways carry their own coordinates under "out geom;" -- no child-node recursion
    # needed (recursing would re-emit every node individually and roughly triple
    # payload size for large islands like Crete/Rhodes/Evia). Relations (a handful
    # of multipolygon islands) still need "(._;>;)" to resolve their member ways.
    return """
[out:json][timeout:180];
area["ISO3166-1"="GR"][admin_level=2]->.greece;
way["place"="island"](area.greece);
out geom;
relation["place"="island"](area.greece);
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


def build_islands_geojson(elements: list[dict]) -> dict:
    raw_geojson = osm2geojson.json2geojson({"elements": elements})

    features = []
    seen_ids = set()

    for feature in raw_geojson["features"]:
        properties = feature.get("properties", {})
        element_type = properties.get("type")
        if element_type not in {"way", "relation"}:
            continue

        tags = properties.get("tags", {})
        name = tags.get("name:en") or tags.get("name")
        element_id = properties.get("id")
        if not name or element_id is None:
            continue

        dedupe_key = (element_type, element_id)
        if dedupe_key in seen_ids:
            continue
        seen_ids.add(dedupe_key)

        geometry = shape(feature["geometry"])
        if not geometry.is_valid or geometry.is_empty:
            continue

        area_km2 = transform(AREA_PROJECTION, geometry).area / 1_000_000.0
        if area_km2 <= 0:
            continue

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "osm_type": element_type,
                    "osm_id": element_id,
                    "name": name,
                    "name_el": tags.get("name"),
                    "area_km2": round(area_km2, 2),
                },
                "geometry": feature["geometry"],
            }
        )

    features.sort(key=lambda f: -f["properties"]["area_km2"])

    return {"type": "FeatureCollection", "features": features}


def write_geojson(path: Path, feature_collection: dict):
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(feature_collection, output_file, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
