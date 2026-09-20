from __future__ import annotations

import json
import math
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.generators import get_file_timestamp, normalize_text, text_or_none


SOURCE_DIR = BASE_DIR / "data" / "source"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
DEFAULT_INPUT_PATH = Path(
    r"C:\Users\megas\Downloads\gis-raaey-wms-rae_status-v_sdi_r_aiolika1237_count_ag-fy5j57_9.zip"
)
OUTPUT_PATH = SOURCE_DIR / "government_wind_greece.geojson"
REPORT_PATH = PROCESSED_DIR / "government_wind_import_report.json"

PRIMARY_SOURCE = "Greek Government Wind Registry"
SOURCE_NAME = "Greek government wind registry"
SOURCE_DATASET = "gis-raaey-wms-rae_status-v_sdi_r_aiolika1237_count_ag"

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
    "ΒΕΒΑΙΩΣΗ ΚΑΤΑΧΩΡΙΣΗΣ ΠΟΛΥΓΩΝΟΥ": {
        "status": "polygon_registration",
        "status_category": "Announced",
    },
}

GRS80_A = 6378137.0
GRS80_INV_F = 298.257222101
GREEK_GRID_E0 = 500000.0
GREEK_GRID_N0 = 0.0
GREEK_GRID_K0 = 0.9996
GREEK_GRID_LON0_RAD = math.radians(24.0)


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT_PATH
    if not input_path.exists():
        raise FileNotFoundError(f"Wind source zip not found: {input_path}")

    input_timestamp = get_file_timestamp(input_path)
    raw_feature_collection = load_feature_collection_from_zip(input_path)

    seen_keys: set[str] = set()
    official_features: list[dict] = []
    for raw_feature in raw_feature_collection.get("features", []):
        feature = build_official_feature(raw_feature, input_path, input_timestamp)
        dedupe_key = build_feature_dedupe_key(feature)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        official_features.append(feature)

    report = build_import_report(input_path, official_features)

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
        f"Wrote {len(official_features)} government wind features to {OUTPUT_PATH}"
    )


def load_feature_collection_from_zip(input_path: Path) -> dict:
    with zipfile.ZipFile(input_path) as archive:
        for zip_info in archive.infolist():
            if zip_info.is_dir() or zip_info.file_size == 0:
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
    raw_feature: dict,
    input_path: Path,
    input_timestamp: str,
) -> dict:
    properties = raw_feature.get("properties", {})
    registry_id = clean_text(properties.get("id1"))
    application_code = clean_text(properties.get("aa"))
    license_id = clean_text(properties.get("a_m"))
    company = clean_text(properties.get("company"))
    site_name = clean_text(properties.get("thesh"))
    project_name = build_project_name(company, site_name)
    status_mapping = map_status(properties.get("katastash_descr"))
    technology = normalize_wind_technology(site_name, properties.get("notes"))
    point = get_geometry_point(raw_feature.get("geometry"))

    longitude = None
    latitude = None
    geometry = None
    if point is not None:
        longitude, latitude = egsa87_to_wgs84(point[0], point[1])
        geometry = {
            "type": "Point",
            "coordinates": [longitude, latitude],
        }

    nominal_capacity_mw = parse_decimal_value(properties.get("power_mw"))
    maximum_capacity_mw = parse_decimal_value(properties.get("max_power"))
    turbine_count_total = parse_total_integer_count(properties.get("count_ag"))
    equivalent_typical_turbines = parse_total_decimal_count(
        properties.get("arithmos_typikon_ag")
    )

    official_properties = {
        "id": build_feature_id(registry_id, application_code, license_id),
        "source_record_id": registry_id,
        "government_registry_id": registry_id,
        "license_id": license_id,
        "application_code": application_code,
        "name": project_name,
        "project_name": site_name or project_name,
        "site_name": site_name,
        "technology": technology,
        "technology_type": "Wind",
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
        "license_status": status_mapping["raw_status"],
        "license_status_code": clean_text(properties.get("katastash_code")),
        "wind_turbine_count_total": turbine_count_total,
        "wind_turbine_count_raw": clean_text(properties.get("count_ag")),
        "turbine_diameter_summary": clean_text(properties.get("count_grby_diam_agg")),
        "equivalent_typical_turbines": equivalent_typical_turbines,
        "environmental_terms_approved": normalize_yes_no(properties.get("epo")),
        "area_m2": parse_decimal_value(properties.get("area_m2")),
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
                    "wind_turbine_count_total",
                    "equivalent_typical_turbines",
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
        "municipality": clean_text(properties.get("kal_dhmos")),
        "municipal_unit": clean_text(properties.get("kal_dhmotikh_enothta")),
        "regional_unit": clean_text(properties.get("kal_perifereiakh_enothta")),
        "region": clean_text(properties.get("kal_perifereia")),
        "country": "Greece",
        "country_role": "domestic",
        "count_in_summary": True,
        "display_on_map": geometry is not None,
        "last_seen": input_timestamp,
        "last_updated": input_timestamp,
        "notes": build_notes(properties, geometry is not None),
    }

    return {
        "type": "Feature",
        "properties": official_properties,
        "geometry": geometry,
    }


def build_import_report(input_path: Path, features: list[dict]) -> dict:
    status_counts: Counter[str] = Counter()
    technology_counts: Counter[str] = Counter()
    missing_capacity = 0
    missing_geometry = 0

    for feature in features:
        properties = feature.get("properties", {})
        status_counts[str(properties.get("status_category") or "Unknown")] += 1
        technology_counts[str(properties.get("technology") or "unknown")] += 1
        if properties.get("nominal_capacity_mw") is None:
            missing_capacity += 1
        if feature.get("geometry") is None:
            missing_geometry += 1

    return {
        "source_zip": str(input_path),
        "official_source_name": SOURCE_NAME,
        "official_features_loaded": len(features),
        "status_breakdown": dict(sorted(status_counts.items())),
        "technology_breakdown": dict(sorted(technology_counts.items())),
        "count_missing_capacity": missing_capacity,
        "count_missing_geometry": missing_geometry,
    }


def map_status(value: object) -> dict[str, str]:
    raw_status = clean_text(value)
    if raw_status is not None and raw_status in STATUS_MAPPINGS:
        return {
            "status": STATUS_MAPPINGS[raw_status]["status"],
            "status_category": STATUS_MAPPINGS[raw_status]["status_category"],
            "raw_status": raw_status,
        }

    return {
        "status": "unknown",
        "status_category": "Unknown",
        "raw_status": raw_status,
    }


def normalize_wind_technology(*raw_values: object) -> str:
    haystack = " ".join(
        clean_text(raw_value) or "" for raw_value in raw_values
    ).lower()
    if "offshore" in haystack or "υπεράκτ" in haystack or "θαλάσσ" in haystack:
        return "offshore_wind"

    return "onshore_wind"


def build_project_name(company: str | None, site_name: str | None) -> str:
    if company and site_name:
        return f"{company} - {site_name}"
    if site_name:
        return site_name
    if company:
        return company
    return "Government wind asset"


def build_feature_id(
    registry_id: str | None,
    application_code: str | None,
    license_id: str | None,
) -> str:
    slug_source = registry_id or application_code or license_id or "unknown"
    slug = normalize_text(slug_source) or "unknown"
    return f"gov-wind-{slug}"


def build_feature_dedupe_key(feature: dict) -> str:
    properties = feature.get("properties", {})
    for value in [
        properties.get("license_id"),
        properties.get("application_code"),
        properties.get("government_registry_id"),
    ]:
        normalized = normalize_text(value)
        if normalized:
            return normalized

    name_key = normalize_text(properties.get("name")) or "unknown"
    municipality_key = normalize_text(properties.get("municipality")) or "unknown"
    capacity = properties.get("nominal_capacity_mw")
    return f"{name_key}:{municipality_key}:{capacity}"


def build_notes(properties: dict, has_geometry: bool) -> list[str]:
    notes: list[str] = []
    raw_notes = clean_text(properties.get("notes"))
    if raw_notes:
        notes.append(raw_notes)

    if has_geometry:
        notes.append("geometry_from_official_polygon_centroid_egsa87")
    else:
        notes.append("missing_official_geometry")

    return notes


def clean_text(value: object) -> str | None:
    return text_or_none(value)


def parse_decimal_value(value: object) -> float | None:
    text_value = clean_text(value)
    if text_value is None:
        return None

    normalized = text_value.replace(" ", "").replace(",", ".")
    try:
        return round(float(normalized), 6)
    except ValueError:
        return None


def parse_total_integer_count(value: object) -> int | None:
    text_value = clean_text(value)
    if text_value is None:
        return None

    matches = re.findall(r"\d+", text_value)
    if not matches:
        return None

    return sum(int(match) for match in matches)


def parse_total_decimal_count(value: object) -> float | None:
    text_value = clean_text(value)
    if text_value is None:
        return None

    matches = re.findall(r"\d+(?:[.,]\d+)?", text_value)
    if not matches:
        return None

    total = 0.0
    for match in matches:
        total += float(match.replace(",", "."))

    return round(total, 6)


def normalize_yes_no(value: object) -> bool | None:
    text_value = clean_text(value)
    if text_value is None:
        return None

    normalized = text_value.strip().upper()
    if normalized == "ΝΑΙ":
        return True
    if normalized == "ΟΧΙ":
        return False

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


def get_ring_centroid_and_area(
    ring_coordinates: list | None,
) -> tuple[tuple[float, float] | None, float]:
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
