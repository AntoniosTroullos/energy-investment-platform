import json
from pathlib import Path
import re
from urllib import error
from urllib import parse, request

from app.generators import (
    get_generator_carrier,
    get_generator_fuel,
    get_source_confidence,
    map_technology_category,
    normalize_generator_technology,
    parse_capacity_to_mw,
)

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = BASE_DIR / "data" / "source"
OVERPASS_URLS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Greece-wide bounding box for the first honest national infrastructure MVP.
GREECE_BBOX = {
    "south": 34.6,
    "west": 19.0,
    "north": 41.9,
    "east": 29.8,
}


def main():
    substation_elements = fetch_overpass(build_substation_query())
    line_elements = fetch_overpass(build_line_query())
    plant_elements = fetch_overpass(build_plant_query())

    substations_geojson = build_feature_collection(
        convert_substation_elements(substation_elements)
    )
    lines_geojson = build_feature_collection(convert_line_elements(line_elements))
    plants_geojson = build_feature_collection(convert_plant_elements(plant_elements))

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    write_geojson(SOURCE_DIR / "substations.geojson", substations_geojson)
    write_geojson(SOURCE_DIR / "transmission_lines.geojson", lines_geojson)
    write_geojson(SOURCE_DIR / "power_plants.geojson", plants_geojson)

    print(
        "Fetched "
        f"{len(substations_geojson['features'])} substations and "
        f"{len(lines_geojson['features'])} transmission lines and "
        f"{len(plants_geojson['features'])} power plants "
        f"for the Greece-wide baseline."
    )


def build_substation_query() -> str:
    bbox = format_bbox()
    return f"""
[out:json][timeout:180];
(
  node["power"="substation"]({bbox});
  way["power"="substation"]({bbox});
  relation["power"="substation"]({bbox});
);
out center tags;
""".strip()


def build_line_query() -> str:
    bbox = format_bbox()
    return f"""
[out:json][timeout:240];
(
  way["power"="line"]["voltage"~"150000|220000|400000"]({bbox});
  way["power"="cable"]["location"="underwater"]["voltage"~"150000|220000|400000"]({bbox});
  way["power"="cable"]["location"="submarine"]["voltage"~"150000|220000|400000"]({bbox});
  way["power"="line"]["location"="underwater"]["voltage"~"150000|220000|400000"]({bbox});
  way["power"="line"]["location"="submarine"]["voltage"~"150000|220000|400000"]({bbox});
);
out geom tags;
""".strip()


def build_plant_query() -> str:
    bbox = format_bbox()
    return f"""
[out:json][timeout:240];
(
  node["power"="plant"]({bbox});
  way["power"="plant"]({bbox});
  relation["power"="plant"]({bbox});
);
out center tags;
""".strip()


def format_bbox() -> str:
    return (
        f"{GREECE_BBOX['south']},"
        f"{GREECE_BBOX['west']},"
        f"{GREECE_BBOX['north']},"
        f"{GREECE_BBOX['east']}"
    )


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


def convert_substation_elements(elements: list[dict]) -> list[dict]:
    features = []

    for element in elements:
        coordinates = get_substation_coordinates(element)

        if coordinates is None:
            continue

        feature_id = f"osm-substation-{element['type']}-{element['id']}"
        tags = element.get("tags", {})

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": feature_id,
                    "name": get_name(tags, feature_id),
                    "voltage_kv": parse_voltage_kv(tags.get("voltage")),
                    "osm_type": element["type"],
                    "osm_id": element["id"],
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": coordinates,
                },
            }
        )

    return features


def convert_line_elements(elements: list[dict]) -> list[dict]:
    features = []

    for element in elements:
        if should_skip_line_element(element):
            continue

        coordinates = [
            [round(point["lon"], 6), round(point["lat"], 6)]
            for point in element.get("geometry", [])
        ]

        if len(coordinates) < 2:
            continue

        feature_id = f"osm-line-way-{element['id']}"
        tags = element.get("tags", {})

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": feature_id,
                    "name": get_name(tags, feature_id),
                    "voltage_kv": parse_voltage_kv(tags.get("voltage")),
                    "power_type": tags.get("power") or "line",
                    "location": tags.get("location") or "overhead",
                    "is_submarine": is_submarine_line(tags),
                    "osm_type": element["type"],
                    "osm_id": element["id"],
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates,
                },
            }
        )

    return features


def convert_plant_elements(elements: list[dict]) -> list[dict]:
    features = []

    for element in elements:
        coordinates = get_substation_coordinates(element)

        if coordinates is None:
            continue

        feature_id = f"osm-plant-{element['type']}-{element['id']}"
        tags = element.get("tags", {})

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": feature_id,
                    "name": get_name(tags, feature_id),
                    "technology": get_plant_technology(tags),
                    "technology_category": get_plant_technology_category(tags),
                    "carrier": get_plant_carrier(tags),
                    "fuel": get_plant_fuel(tags),
                    "operator": get_operator(tags),
                    "capacity_mw": get_plant_capacity_mw(tags),
                    "nominal_capacity_mw": get_plant_capacity_mw(tags),
                    "capacity_unit": "MW"
                    if get_plant_capacity_mw(tags) is not None
                    else None,
                    "capacity_type": "nominal"
                    if get_plant_capacity_mw(tags) is not None
                    else None,
                    "status": tags.get("plant:status") or tags.get("status") or "Unknown",
                    "source": "OpenStreetMap",
                    "primary_source": "OpenStreetMap",
                    "source_refs": [f"osm:{element['type']}/{element['id']}"],
                    "source_confidence": get_plant_source_confidence(tags, coordinates),
                    "confidence_score": get_plant_source_confidence(tags, coordinates),
                    "latitude": coordinates[1],
                    "longitude": coordinates[0],
                    "osm_type": element["type"],
                    "osm_id": element["id"],
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": coordinates,
                },
            }
        )

    return features


def should_skip_line_element(element: dict) -> bool:
    tags = element.get("tags", {})
    line_kind = tags.get("line", "").lower()

    if line_kind in {"bay", "busbar"}:
        return True

    return False


def is_submarine_line(tags: dict) -> bool:
    location = tags.get("location", "").lower()
    return location in {"underwater", "submarine"}


def get_substation_coordinates(element: dict) -> list[float] | None:
    if "lon" in element and "lat" in element:
        return [round(element["lon"], 6), round(element["lat"], 6)]

    center = element.get("center")

    if center is None:
        return None

    return [round(center["lon"], 6), round(center["lat"], 6)]


def get_name(tags: dict, fallback_id: str) -> str:
    return tags.get("name") or tags.get("ref") or fallback_id


def get_plant_technology(tags: dict) -> str:
    raw_technology = (
        tags.get("plant:source")
        or tags.get("generator:source")
        or tags.get("source")
        or "Unknown"
    )
    return normalize_generator_technology(raw_technology)


def get_plant_technology_category(tags: dict) -> str:
    return map_technology_category(get_plant_technology(tags))


def get_plant_carrier(tags: dict) -> str:
    return get_generator_carrier(get_plant_technology(tags))


def get_plant_fuel(tags: dict) -> str | None:
    return get_generator_fuel({"fuel": tags.get("fuel")}, get_plant_technology(tags))


def get_operator(tags: dict) -> str:
    return (
        tags.get("operator")
        or tags.get("plant:operator")
        or tags.get("operator:wikidata")
        or "Unknown"
    )


def get_plant_capacity_mw(tags: dict) -> float | None:
    raw_capacity = (
        tags.get("plant:output:electricity")
        or tags.get("generator:output:electricity")
        or tags.get("output:electricity")
    )

    return parse_capacity_to_mw(raw_capacity)["value_mw"]

def get_plant_source_confidence(tags: dict, coordinates: list[float]) -> float:
    technology = get_plant_technology(tags)
    capacity_mw = get_plant_capacity_mw(tags)
    return get_source_confidence(
        {"name": tags.get("name"), "operator": get_operator(tags), "osm_id": tags.get("id")},
        technology,
        capacity_mw,
        coordinates[0],
        coordinates[1],
        [],
    )


def parse_voltage_kv(raw_voltage: str | None) -> int | None:
    if not raw_voltage:
        return None

    # OSM's voltage tag convention is ";"-separated multi-circuit values, but
    # some contributors use "/" or "," instead. Splitting on ";" alone left
    # those un-split, so stripping non-digit characters below concatenated
    # the separate values into one digit string before the kV conversion
    # (e.g. "400000/150000" volts became the nonsense reading "400000150" kV).
    first_value = re.split(r"[;,/]", raw_voltage)[0].strip()
    digits_only = "".join(character for character in first_value if character.isdigit())

    if not digits_only:
        return None

    voltage_value = int(digits_only)

    if voltage_value >= 1000:
        return round(voltage_value / 1000)

    return voltage_value


def build_feature_collection(features: list[dict]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": features,
    }


def write_geojson(path: Path, feature_collection: dict):
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(feature_collection, output_file, indent=2)


if __name__ == "__main__":
    main()
