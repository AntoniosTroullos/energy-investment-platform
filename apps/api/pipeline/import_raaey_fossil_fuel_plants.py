from __future__ import annotations

import json
import math
import re
import sys
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.generators import get_file_timestamp, text_or_none


SOURCE_DIR = BASE_DIR / "data" / "source"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
DEFAULT_INPUT_PATH = Path(
    r"C:\Users\megas\Downloads\gis-raaey-wms-rae_status-v_sdi_r_orykta_all-hn5879de.zip"
)
OUTPUT_PATH = SOURCE_DIR / "raaey_fossil_fuel_plants.geojson"
REPORT_PATH = PROCESSED_DIR / "raaey_fossil_fuel_plants_import_report.json"

PRIMARY_SOURCE = "RAAEY Fossil Fuel Registry"
SOURCE_NAME = "RAAEY fossil fuel power stations registry"
SOURCE_DATASET = "gis-raaey-wms-rae_status-v_sdi_r_orykta_all"

GRS80_A = 6378137.0
GRS80_INV_F = 298.257222101
GREEK_GRID_E0 = 500000.0
GREEK_GRID_N0 = 0.0
GREEK_GRID_K0 = 0.9996
GREEK_GRID_LON0_RAD = math.radians(24.0)

STATUS_MAPPINGS = {
    "ΑΔΕΙΑ ΛΕΙΤΟΥΡΓΙΑΣ": {
        "status": "operating",
        "status_category": "Operating",
    },
    "ΑΔΕΙΑ ΕΓΚΑΤΑΣΤΑΣΗΣ": {
        "status": "installation_license",
        "status_category": "Under Construction",
    },
    "ΑΔΕΙΑ ΠΑΡΑΓΩΓΗΣ": {
        "status": "production_license",
        "status_category": "Planned",
    },
    "ΑΙΤΗΣΗ ΣΕ ΑΞΙΟΛΟΓΗΣΗ": {
        "status": "application_under_evaluation",
        "status_category": "Announced",
    },
}


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT_PATH
    if not input_path.exists():
        raise FileNotFoundError(f"Fossil-fuel source zip not found: {input_path}")

    input_timestamp = get_file_timestamp(input_path)
    feature_collection = load_feature_collection_from_zip(input_path)
    official_features = [
        build_official_feature(feature, input_path, input_timestamp)
        for feature in feature_collection.get("features", [])
    ]

    report = {
        "source_zip": str(input_path),
        "official_source_name": SOURCE_NAME,
        "official_features_loaded": len(official_features),
        "output_features_written": len(official_features),
        "source_was_empty": len(official_features) == 0,
        "notes": build_report_notes(official_features),
    }

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({"type": "FeatureCollection", "features": official_features}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"Wrote {len(official_features)} official fossil-fuel plant features to {OUTPUT_PATH}"
    )


def load_feature_collection_from_zip(input_path: Path) -> dict:
    with zipfile.ZipFile(input_path) as archive:
        for zip_info in archive.infolist():
            if zip_info.is_dir():
                continue

            try:
                candidate_text = archive.read(zip_info).decode("utf-8")
            except UnicodeDecodeError:
                continue

            try:
                payload = json.loads(candidate_text)
            except json.JSONDecodeError:
                continue

            if payload.get("type") == "FeatureCollection" and isinstance(
                payload.get("features"), list
            ):
                return payload

    raise ValueError(f"No GeoJSON FeatureCollection found in {input_path}")


def build_official_feature(
    source_feature: dict,
    input_path: Path,
    input_timestamp: str,
) -> dict:
    properties = source_feature.get("properties", {})
    registry_id = clean_text(properties.get("id1"))
    application_code = clean_text(properties.get("aa"))
    license_id = clean_text(properties.get("a_m"))
    company = clean_text(properties.get("company"))
    site_name = clean_text(properties.get("thesh"))
    status_text = clean_text(properties.get("katastash_descr"))
    status_mapping = map_status(status_text)
    nominal_capacity_mw = parse_number(properties.get("power_mw"))
    maximum_capacity_mw = parse_number(properties.get("max_power"))
    technology = normalize_fossil_technology(
        properties.get("notes"),
        site_name,
        company,
    )
    point = get_geometry_point(source_feature.get("geometry"))

    longitude = None
    latitude = None
    geometry = None
    if point is not None:
        longitude, latitude = egsa87_to_wgs84(point[0], point[1])
        geometry = {
            "type": "Point",
            "coordinates": [longitude, latitude],
        }

    project_name = build_project_name(company, site_name)

    official_properties = {
        "id": build_feature_id(registry_id, application_code, license_id),
        "source_record_id": registry_id,
        "government_registry_id": registry_id,
        "application_code": application_code,
        "license_id": license_id,
        "name": project_name,
        "project_name": site_name or project_name,
        "site_name": site_name,
        "technology": technology,
        "operator": company,
        "owner": company,
        "developer": company,
        "capacity_mw": nominal_capacity_mw,
        "nominal_capacity_mw": nominal_capacity_mw,
        "maximum_capacity_mw": maximum_capacity_mw,
        "capacity_unit": "MW" if nominal_capacity_mw is not None else None,
        "capacity_type": "nominal" if nominal_capacity_mw is not None else None,
        "status": status_mapping["status"],
        "status_category": status_mapping["status_category"],
        "license_status": status_text,
        "license_status_code": clean_text(properties.get("katastash_code")),
        "primary_source": PRIMARY_SOURCE,
        "source": PRIMARY_SOURCE,
        "source_dataset": SOURCE_DATASET,
        "source_confidence": 5,
        "source_refs": [
            {
                "source_name": SOURCE_NAME,
                "source_file": input_path.name,
                "source_record_id": registry_id,
                "application_code": application_code,
                "license_id": license_id,
                "fields_supported": [
                    "name",
                    "operator",
                    "technology",
                    "status",
                    "nominal_capacity_mw",
                    "region",
                    "regional_unit",
                    "municipality",
                ],
            }
        ],
        "latitude": latitude,
        "longitude": longitude,
        "location_accuracy": (
            "official_polygon_centroid_egsa87" if geometry is not None else "missing_geometry"
        ),
        "municipal_unit": clean_text(properties.get("kal_dhm_enothta")),
        "municipality": clean_text(properties.get("kal_dhmos")),
        "regional_unit": clean_text(properties.get("kal_perif_enothta")),
        "region": clean_text(properties.get("kal_perifereia")),
        "country": "Greece",
        "country_role": "domestic",
        "count_in_summary": True,
        "display_on_map": geometry is not None,
        "last_seen": input_timestamp,
        "last_updated": input_timestamp,
        "notes": build_notes(properties, geometry is not None),
        "raw_source_properties": properties,
    }

    return {
        "type": "Feature",
        "properties": official_properties,
        "geometry": geometry,
    }


def build_report_notes(official_features: list[dict]) -> list[str]:
    if official_features:
        return [
            "Official RAAEY fossil-fuel export contained records and was converted into a backend-owned supplemental source layer."
        ]

    return [
        "Official RAAEY fossil-fuel export currently returned no records, so the importer wrote an honest empty supplemental source layer.",
        "Existing fossil-fuel coverage in the app therefore still comes from the previously loaded generator sources, such as OpenStreetMap.",
    ]


def map_status(status_text: str | None) -> dict[str, str]:
    if status_text is None:
        return {"status": "unknown", "status_category": "Unknown"}

    if status_text in STATUS_MAPPINGS:
        return STATUS_MAPPINGS[status_text]

    return {"status": "unknown", "status_category": "Unknown"}


def normalize_fossil_technology(*raw_values: object) -> str:
    haystack = " ".join(value for value in (clean_text(raw_value) or "" for raw_value in raw_values)).lower()

    if contains_any_phrase(haystack, ["φυσικ", "natural gas", "ccgt", "ocgt", "lng"]) or contains_any_word(haystack, ["gas"]):
        return "gas"
    if contains_any_phrase(haystack, ["λιγν", "lignite", "brown coal"]):
        return "lignite"
    if contains_any_phrase(haystack, ["πετρελ", "mazut", "diesel", "ντίζελ"]) or contains_any_word(haystack, ["oil"]):
        return "oil"
    if contains_any_phrase(haystack, ["άνθρακ"]) or contains_any_word(haystack, ["coal"]):
        return "coal"

    return "unknown"


def contains_any_phrase(haystack: str, phrases: list[str]) -> bool:
    return any(phrase in haystack for phrase in phrases)


def contains_any_word(haystack: str, words: list[str]) -> bool:
    for word in words:
        if re.search(rf"\b{re.escape(word)}\b", haystack):
            return True

    return False


def build_project_name(company: str | None, site_name: str | None) -> str:
    if company and site_name:
        return f"{company} - {site_name}"
    if site_name:
        return site_name
    if company:
        return company
    return "RAAEY fossil-fuel power station"


def build_feature_id(
    registry_id: str | None,
    application_code: str | None,
    license_id: str | None,
) -> str:
    slug_source = registry_id or application_code or license_id or "unknown"
    slug = re.sub(r"[^a-z0-9]+", "-", normalize_identifier(slug_source))
    return f"raaey-fossil-{slug.strip('-') or 'unknown'}"


def normalize_identifier(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value)


def build_notes(properties: dict, has_geometry: bool) -> list[str]:
    notes: list[str] = []
    raw_notes = clean_text(properties.get("notes"))
    if raw_notes is not None:
        notes.append(raw_notes)

    if has_geometry:
        notes.append("geometry_from_official_polygon_centroid_egsa87")
    else:
        notes.append("missing_official_geometry")

    return notes


def clean_text(value: object) -> str | None:
    return text_or_none(value)


def parse_number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(float(value), 6)

    text_value = clean_text(value)
    if text_value is None:
        return None

    normalized = text_value.replace(" ", "").replace(",", ".")
    try:
        return round(float(normalized), 6)
    except ValueError:
        return None


def get_geometry_point(geometry: dict | None) -> tuple[float, float] | None:
    if not geometry:
        return None

    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if geometry_type == "Point" and is_valid_point(coordinates):
        return float(coordinates[0]), float(coordinates[1])

    if geometry_type == "Polygon":
        return get_polygon_group_centroid(coordinates)

    if geometry_type == "MultiPolygon":
        polygon_points: list[tuple[float, float, float]] = []
        for polygon in coordinates or []:
            centroid = get_polygon_group_centroid(polygon)
            area = get_polygon_group_area(polygon)
            if centroid is not None and area > 0:
                polygon_points.append((centroid[0], centroid[1], area))

        if polygon_points:
            total_area = sum(area for _, _, area in polygon_points)
            return (
                sum(x * area for x, _, area in polygon_points) / total_area,
                sum(y * area for _, y, area in polygon_points) / total_area,
            )

        for polygon in coordinates or []:
            centroid = get_polygon_group_centroid(polygon)
            if centroid is not None:
                return centroid

    return None


def get_polygon_group_centroid(polygon_coordinates: list | None) -> tuple[float, float] | None:
    if not polygon_coordinates:
        return None

    outer_ring = polygon_coordinates[0]
    centroid, _ = get_ring_centroid_and_area(outer_ring)
    if centroid is not None:
        return centroid

    valid_points = [
        (float(point[0]), float(point[1]))
        for point in outer_ring or []
        if is_valid_point(point)
    ]
    if not valid_points:
        return None

    min_x = min(point[0] for point in valid_points)
    max_x = max(point[0] for point in valid_points)
    min_y = min(point[1] for point in valid_points)
    max_y = max(point[1] for point in valid_points)
    return ((min_x + max_x) / 2, (min_y + max_y) / 2)


def get_polygon_group_area(polygon_coordinates: list | None) -> float:
    if not polygon_coordinates:
        return 0

    _, area = get_ring_centroid_and_area(polygon_coordinates[0])
    return area


def get_ring_centroid_and_area(ring_coordinates: list | None) -> tuple[tuple[float, float] | None, float]:
    if not ring_coordinates:
        return None, 0

    points = [
        (float(point[0]), float(point[1]))
        for point in ring_coordinates
        if is_valid_point(point)
    ]
    if len(points) < 3:
        return None, 0

    if points[0] != points[-1]:
        points.append(points[0])

    twice_area = 0.0
    centroid_x = 0.0
    centroid_y = 0.0

    for index in range(len(points) - 1):
        x1, y1 = points[index]
        x2, y2 = points[index + 1]
        cross = x1 * y2 - x2 * y1
        twice_area += cross
        centroid_x += (x1 + x2) * cross
        centroid_y += (y1 + y2) * cross

    if abs(twice_area) < 1e-9:
        return None, 0

    area = abs(twice_area) / 2
    return ((centroid_x / (3 * twice_area), centroid_y / (3 * twice_area)), area)


def is_valid_point(point: object) -> bool:
    return (
        isinstance(point, (list, tuple))
        and len(point) >= 2
        and isinstance(point[0], (int, float))
        and isinstance(point[1], (int, float))
    )


def egsa87_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    flattening = 1 / GRS80_INV_F
    eccentricity_squared = 2 * flattening - flattening**2
    eccentricity_prime_squared = eccentricity_squared / (1 - eccentricity_squared)
    meridional_arc = (northing - GREEK_GRID_N0) / GREEK_GRID_K0
    mu = meridional_arc / (
        GRS80_A
        * (
            1
            - eccentricity_squared / 4
            - 3 * eccentricity_squared**2 / 64
            - 5 * eccentricity_squared**3 / 256
        )
    )
    e1 = (1 - math.sqrt(1 - eccentricity_squared)) / (
        1 + math.sqrt(1 - eccentricity_squared)
    )

    phi1 = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )

    sin_phi1 = math.sin(phi1)
    cos_phi1 = math.cos(phi1)
    tan_phi1 = math.tan(phi1)
    radius_n = GRS80_A / math.sqrt(1 - eccentricity_squared * sin_phi1**2)
    radius_r = (
        GRS80_A
        * (1 - eccentricity_squared)
        / (1 - eccentricity_squared * sin_phi1**2) ** 1.5
    )
    t1 = tan_phi1**2
    c1 = eccentricity_prime_squared * cos_phi1**2
    d = (easting - GREEK_GRID_E0) / (radius_n * GREEK_GRID_K0)

    latitude = phi1 - (
        radius_n
        * tan_phi1
        / radius_r
        * (
            d**2 / 2
            - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * eccentricity_prime_squared)
            * d**4
            / 24
            + (
                61
                + 90 * t1
                + 298 * c1
                + 45 * t1**2
                - 252 * eccentricity_prime_squared
                - 3 * c1**2
            )
            * d**6
            / 720
        )
    )
    longitude = GREEK_GRID_LON0_RAD + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (
            5
            - 2 * c1
            + 28 * t1
            - 3 * c1**2
            + 8 * eccentricity_prime_squared
            + 24 * t1**2
        )
        * d**5
        / 120
    ) / cos_phi1

    return (round(math.degrees(longitude), 6), round(math.degrees(latitude), 6))


if __name__ == "__main__":
    main()
