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

from app.generators import (
    capacities_within_tolerance,
    get_distance_km,
    get_file_timestamp,
    names_match_loose,
    normalize_text,
    text_or_none,
)


SOURCE_DIR = BASE_DIR / "data" / "source"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
DEFAULT_INPUT_PATH = Path(
    r"C:\Users\megas\Downloads\gis-raaey-wms-rae_status-v_sdi_r_hydrogen_all-azl5cazf.zip"
)
OUTPUT_PATH = SOURCE_DIR / "hydrogen_projects.geojson"
REPORT_PATH = PROCESSED_DIR / "hydrogen_projects_import_report.json"

PRIMARY_SOURCE = "RAAEY Hydrogen Registry"
SOURCE_NAME = "RAAEY hydrogen production units registry"
PROJECT_TYPE = "Production"
HYDROGEN_ROLE = "Hydrogen Production Unit"
HYDROGEN_TYPE = "Hydrogen"

GRS80_A = 6378137.0
GRS80_INV_F = 298.257222101
GREEK_GRID_E0 = 500000.0
GREEK_GRID_N0 = 0.0
GREEK_GRID_K0 = 0.9996
GREEK_GRID_LON0_RAD = math.radians(24.0)

STATUS_MAPPINGS = {
    "ΑΔΕΙΑ ΛΕΙΤΟΥΡΓΙΑΣ": {
        "status": "Operating",
        "status_category": "Operating",
    },
    "ΑΔΕΙΑ ΕΓΚΑΤΑΣΤΑΣΗΣ": {
        "status": "Under Construction",
        "status_category": "Under Construction",
    },
    "ΑΔΕΙΑ ΠΑΡΑΓΩΓΗΣ": {
        "status": "Production License",
        "status_category": "Planned",
    },
    "ΑΙΤΗΣΗ ΣΕ ΑΞΙΟΛΟΓΗΣΗ": {
        "status": "Under Evaluation",
        "status_category": "Announced",
    },
}


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT_PATH
    if not input_path.exists():
        raise FileNotFoundError(f"Hydrogen source zip not found: {input_path}")

    input_timestamp = get_file_timestamp(input_path)
    official_features = load_official_features(input_path, input_timestamp)
    existing_feature_collection = load_existing_features()
    merged_features, report = merge_with_existing_features(
        official_features,
        existing_feature_collection.get("features", []),
        input_path,
    )

    feature_collection = {
        "type": "FeatureCollection",
        "features": merged_features,
    }

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(feature_collection, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"Wrote {len(merged_features)} hydrogen project features to {OUTPUT_PATH} "
        f"from {len(official_features)} official RAAEY records"
    )


def load_official_features(input_path: Path, input_timestamp: str) -> list[dict]:
    feature_collection = load_feature_collection_from_zip(input_path)
    official_features: list[dict] = []
    seen_keys: set[str] = set()

    for feature in feature_collection.get("features", []):
        official_feature = build_official_feature(feature, input_path, input_timestamp)
        dedupe_key = build_official_dedupe_key(official_feature)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        official_features.append(official_feature)

    return official_features


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


def load_existing_features() -> dict:
    if not OUTPUT_PATH.exists():
        return {"type": "FeatureCollection", "features": []}

    with OUTPUT_PATH.open("r", encoding="utf-8") as data_file:
        return json.load(data_file)


def merge_with_existing_features(
    official_features: list[dict],
    existing_features: list[dict],
    input_path: Path,
) -> tuple[list[dict], dict]:
    merged_features = list(official_features)
    retained_legacy_features: list[dict] = []
    replaced_legacy_duplicates: list[dict] = []
    skipped_old_official_ids: list[str] = []

    for existing_feature in existing_features:
        properties = existing_feature.get("properties", {})
        if properties.get("primary_source") == PRIMARY_SOURCE:
            skipped_old_official_ids.append(str(properties.get("id")))
            continue

        duplicate_match = find_duplicate_official_feature(existing_feature, official_features)
        if duplicate_match is not None:
            replaced_legacy_duplicates.append(
                {
                    "legacy_id": str(properties.get("id")),
                    "legacy_name": properties.get("name"),
                    "official_id": duplicate_match["properties"].get("id"),
                    "official_name": duplicate_match["properties"].get("name"),
                }
            )
            continue

        retained_legacy_features.append(existing_feature)

    merged_features.extend(retained_legacy_features)

    report = {
        "source_zip": str(input_path),
        "official_source_name": SOURCE_NAME,
        "official_features_loaded": len(official_features),
        "retained_legacy_features": len(retained_legacy_features),
        "replaced_legacy_duplicates": replaced_legacy_duplicates,
        "skipped_old_official_ids": skipped_old_official_ids,
        "total_output_features": len(merged_features),
    }

    return merged_features, report


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
    electrolyzer_capacity_mw = parse_number(properties.get("power_mw"))
    maximum_power_mw = parse_number(properties.get("max_power"))
    annual_output_tpa = parse_number(properties.get("hy_prod"))
    area_m2 = parse_number(properties.get("area_m2"))
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
    source_refs = [
        {
            "source_name": SOURCE_NAME,
            "source_file": input_path.name,
            "fields_supported": [
                "name",
                "operator",
                "project_type",
                "hydrogen_role",
                "status",
                "electrolyzer_capacity_mw",
                "annual_output_tpa",
                "region",
                "regional_unit",
                "municipality",
            ],
            "source_record_id": registry_id,
            "application_code": application_code,
            "license_id": license_id,
        }
    ]

    notes = []
    extra_notes = clean_text(properties.get("notes"))
    if extra_notes is not None:
        notes.append(extra_notes)
    if geometry is not None:
        notes.append("geometry_from_official_polygon_centroid_egsa87")
    else:
        notes.append("missing_official_geometry")

    official_properties = {
        "id": build_feature_id(registry_id, application_code, license_id),
        "source_record_id": registry_id,
        "government_registry_id": registry_id,
        "application_code": application_code,
        "license_id": license_id,
        "name": project_name,
        "project_name": site_name or project_name,
        "site_name": site_name,
        "operator": company,
        "owner": company,
        "developer": company,
        "asset_class": "hydrogen_project",
        "project_type": PROJECT_TYPE,
        "hydrogen_role": HYDROGEN_ROLE,
        "hydrogen_type": HYDROGEN_TYPE,
        "status": status_mapping["status"],
        "status_category": status_mapping["status_category"],
        "license_status": status_text,
        "license_status_code": clean_text(properties.get("katastash_code")),
        "electrolyzer_capacity_mw": electrolyzer_capacity_mw,
        "capacity_mw": electrolyzer_capacity_mw,
        "nominal_capacity_mw": electrolyzer_capacity_mw,
        "maximum_power_mw": maximum_power_mw,
        "annual_output_tpa": annual_output_tpa,
        "area_m2": area_m2,
        "primary_source": PRIMARY_SOURCE,
        "source": PRIMARY_SOURCE,
        "source_dataset": input_path.name,
        "source_confidence": 5,
        "source_refs": source_refs,
        "latitude": latitude,
        "longitude": longitude,
        "location_confidence": (
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
        "raw_source_properties": properties,
        "notes": notes,
    }

    return {
        "type": "Feature",
        "properties": official_properties,
        "geometry": geometry,
    }


def build_feature_id(
    registry_id: str | None,
    application_code: str | None,
    license_id: str | None,
) -> str:
    slug_source = registry_id or application_code or license_id or "unknown"
    slug = re.sub(r"[^a-z0-9]+", "-", (normalize_text(slug_source) or slug_source.lower()))
    return f"hydrogen-project-raaey-{slug.strip('-') or 'unknown'}"


def build_project_name(company: str | None, site_name: str | None) -> str:
    if company and site_name:
        return f"{company} - {site_name}"
    if site_name:
        return site_name
    if company:
        return company
    return "RAAEY hydrogen production unit"


def build_official_dedupe_key(feature: dict) -> str:
    properties = feature.get("properties", {})
    for value in [
        properties.get("application_code"),
        properties.get("license_id"),
        properties.get("source_record_id"),
    ]:
        normalized = normalize_text(value)
        if normalized:
            return normalized

    name_key = normalize_text(properties.get("name")) or "unknown"
    municipality_key = normalize_text(properties.get("municipality")) or "unknown"
    capacity = properties.get("electrolyzer_capacity_mw")
    return f"{name_key}:{municipality_key}:{capacity}"


def find_duplicate_official_feature(existing_feature: dict, official_features: list[dict]) -> dict | None:
    existing_properties = existing_feature.get("properties", {})
    existing_geometry = existing_feature.get("geometry") or {}
    existing_name = normalize_text(existing_properties.get("name"))
    existing_operator = normalize_text(existing_properties.get("operator"))
    existing_municipality = normalize_text(existing_properties.get("municipality"))
    existing_capacity = parse_number(
        existing_properties.get("electrolyzer_capacity_mw")
        or existing_properties.get("capacity_mw")
        or existing_properties.get("nominal_capacity_mw")
    )
    existing_longitude = existing_properties.get("longitude")
    existing_latitude = existing_properties.get("latitude")
    if not isinstance(existing_longitude, (int, float)) or not isinstance(
        existing_latitude, (int, float)
    ):
        geometry_coordinates = existing_geometry.get("coordinates")
        if is_valid_point(geometry_coordinates):
            existing_longitude = float(geometry_coordinates[0])
            existing_latitude = float(geometry_coordinates[1])

    for official_feature in official_features:
        official_properties = official_feature.get("properties", {})
        official_name = normalize_text(official_properties.get("name"))
        official_operator = normalize_text(official_properties.get("operator"))
        official_municipality = normalize_text(official_properties.get("municipality"))
        official_capacity = parse_number(official_properties.get("electrolyzer_capacity_mw"))
        official_latitude = official_properties.get("latitude")
        official_longitude = official_properties.get("longitude")

        if existing_name and official_name and names_match_loose(existing_name, official_name):
            return official_feature

        same_operator = (
            existing_operator is not None
            and official_operator is not None
            and existing_operator == official_operator
        )
        same_municipality = (
            existing_municipality is not None
            and official_municipality is not None
            and existing_municipality == official_municipality
        )
        close_capacity = capacities_within_tolerance(existing_capacity, official_capacity)
        distance_km = get_distance_km(
            existing_latitude,
            existing_longitude,
            official_latitude,
            official_longitude,
        )

        if same_operator and same_municipality and close_capacity:
            return official_feature

        if close_capacity and distance_km is not None and distance_km <= 5:
            return official_feature

        if same_operator and close_capacity and distance_km is not None and distance_km <= 12:
            return official_feature

    return None


def map_status(status_text: str | None) -> dict[str, str]:
    if status_text is None:
        return {"status": "Unknown", "status_category": "Unknown"}

    if status_text in STATUS_MAPPINGS:
        return STATUS_MAPPINGS[status_text]

    return {"status": status_text.title(), "status_category": "Unknown"}


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
