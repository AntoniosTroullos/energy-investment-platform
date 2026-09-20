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

# Greece's 13 administrative regions ("Περιφέρειες") are OSM admin_level=5 relations.
# Keyed by ISO 3166-2 code, not name: admin_level=4 is the 7 coarser Decentralized
# Administrations, admin_level=6 is ~74 finer Regional Units, and OSM's own name/
# name:en tags are inconsistent across sources -- the ISO code is the only stable
# join key. This must match pypsa-greece's data/static/buses.csv exactly.
ISO_TO_BUS = {
    "GR-A": "Eastern_Macedonia_Thrace",
    "GR-B": "Central_Macedonia",
    "GR-C": "Western_Macedonia",
    "GR-D": "Epirus",
    "GR-E": "Thessaly",
    "GR-F": "Ionian_Islands",
    "GR-G": "Western_Greece",
    "GR-H": "Central_Greece",
    "GR-I": "Attica",
    "GR-J": "Peloponnese",
    "GR-K": "North_Aegean",
    "GR-L": "South_Aegean",
    "GR-M": "Crete",
}


def main():
    elements = fetch_overpass(build_region_query())
    regions_geojson = build_regions_geojson(elements)

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    write_geojson(SOURCE_DIR / "admin_regions.geojson", regions_geojson)

    print(
        f"Fetched {len(regions_geojson['features'])} of "
        f"{len(ISO_TO_BUS)} expected Greek administrative regions."
    )


def build_region_query() -> str:
    return """
[out:json][timeout:180];
area["ISO3166-1"="GR"][admin_level=2]->.greece;
relation["boundary"="administrative"]["admin_level"="5"](area.greece);
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


def build_regions_geojson(elements: list[dict]) -> dict:
    raw_geojson = osm2geojson.json2geojson({"elements": elements})
    relation_features = [
        feature
        for feature in raw_geojson["features"]
        if feature.get("properties", {}).get("type") == "relation"
    ]

    features = []
    seen_buses = set()

    for feature in relation_features:
        tags = feature["properties"].get("tags", {})
        iso_code = tags.get("ISO3166-2")
        bus_name = ISO_TO_BUS.get(iso_code)

        if bus_name is None:
            continue

        geometry = shape(feature["geometry"])
        if not geometry.is_valid or geometry.is_empty:
            raise ValueError(f"Invalid or empty geometry for {bus_name} ({iso_code})")

        if bus_name in seen_buses:
            raise ValueError(f"Duplicate region match for bus: {bus_name}")
        seen_buses.add(bus_name)

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": bus_name,
                    "name": tags.get("name:en") or bus_name,
                    "name_el": tags.get("name"),
                    "iso3166_2": iso_code,
                    "osm_relation_id": feature["properties"].get("id"),
                },
                "geometry": feature["geometry"],
            }
        )

    missing_buses = sorted(set(ISO_TO_BUS.values()) - seen_buses)
    if missing_buses:
        raise ValueError(f"Missing boundary polygons for buses: {missing_buses}")

    features.sort(key=lambda f: f["properties"]["id"])

    return {"type": "FeatureCollection", "features": features}


def write_geojson(path: Path, feature_collection: dict):
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(feature_collection, output_file, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
