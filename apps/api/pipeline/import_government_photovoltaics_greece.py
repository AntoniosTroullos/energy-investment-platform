from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.generators import (
    build_canonical_generator_feature,
    capacities_within_tolerance,
    get_distance_km,
    get_file_timestamp,
    get_neighbor_bucket_keys,
    load_source_feature_collection,
    merge_generator_features,
    names_match_loose,
    normalize_text,
    text_or_none,
)


SOURCE_DIR = BASE_DIR / "data" / "source"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
DEFAULT_INPUT_PATH = Path(
    r"C:\Users\megas\Downloads\V_SDI_R_PHOTOVOLTAICS_ALL.csv"
)
OUTPUT_PATH = SOURCE_DIR / "government_photovoltaics_greece.geojson"
REPORT_PATH = PROCESSED_DIR / "government_photovoltaics_import_report.json"

PRIMARY_SOURCE = "Greek Government PV Registry"
SOURCE_DATASET = "V_SDI_R_PHOTOVOLTAICS_ALL.csv"
ACTIVE_STATUS_RULES = {
    "ΑΔΕΙΑ ΛΕΙΤΟΥΡΓΙΑΣ": ("operating", "Operating"),
    "ΑΔΕΙΑ ΕΓΚΑΤΑΣΤΑΣΗΣ": ("installation_license", "Under Construction"),
    "ΑΔΕΙΑ ΠΑΡΑΓΩΓΗΣ": ("production_license", "Planned"),
    "ΑΔΕΙΕΣ ΑΠΑΛΛΑΣΣΟΜΕΝΕΣ": ("exempted_license", "Planned"),
    "ΔΙΑΒΙΒΑΣΗ ΣΤΟ ΔΕΔΔΗΕ": ("submitted_to_deddie", "Pre-Construction"),
    "ΑΙΤΗΣΗ ΣΕ ΑΞΙΟΛΟΓΗΣΗ": ("application_under_evaluation", "Announced"),
}
EXCLUDED_STATUS_KEYWORDS = [
    "ΑΠΟΡΡΙΠ",
    "ΑΝΑΚΛ",
    "ΠΑΥΣ",
    "ΕΛΛΙΠΗΣ",
    "ΑΡΝΗΤΙΚ",
    "ΜΗ ΕΓΚΡΙΣΗ",
]
GRS80_A = 6378137.0
GRS80_INV_F = 298.257222101
GREEK_GRID_E0 = 500000.0
GREEK_GRID_N0 = 0.0
GREEK_GRID_K0 = 0.9996
GREEK_GRID_LON0_RAD = math.radians(24.0)


def main() -> None:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT_PATH

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    rows = read_photovoltaic_rows(csv_path)
    comparison_features = load_comparison_features()
    comparison_index = build_comparison_index(comparison_features)
    kept_features: list[dict] = []
    skipped_duplicates: list[dict] = []
    skipped_status_counts: Counter[str] = Counter()
    kept_status_counts: Counter[str] = Counter()

    for row in rows:
        status_descriptor = normalize_status_descriptor(row.get("katastash_descr"))
        status_mapping = map_government_status(status_descriptor)

        if status_mapping is None:
            skipped_status_counts[status_descriptor or "UNKNOWN"] += 1
            continue

        feature = build_government_feature(row, status_mapping, get_file_timestamp(csv_path))
        duplicate_match = find_existing_duplicate(
            feature,
            comparison_features,
            comparison_index,
        )
        if duplicate_match is not None:
            skipped_duplicates.append(
                {
                    "government_id": feature["properties"]["id"],
                    "government_name": feature["properties"]["name"],
                    "matched_existing_id": duplicate_match["id"],
                    "matched_existing_name": duplicate_match["name"],
                    "reason": duplicate_match["reason"],
                }
            )
            continue

        kept_features.append(feature)
        kept_status_counts[status_descriptor or "UNKNOWN"] += 1

    feature_collection = {
        "type": "FeatureCollection",
        "features": kept_features,
    }
    report = {
        "source_file": str(csv_path),
        "total_rows_read": len(rows),
        "kept_features": len(kept_features),
        "skipped_due_to_status": sum(skipped_status_counts.values()),
        "skipped_due_to_duplicates": len(skipped_duplicates),
        "kept_status_breakdown": dict(sorted(kept_status_counts.items())),
        "skipped_status_breakdown": dict(sorted(skipped_status_counts.items())),
        "top_duplicate_matches": skipped_duplicates[:100],
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
        f"Wrote {len(kept_features)} new government PV features to {OUTPUT_PATH} "
        f"and {len(skipped_duplicates)} duplicate candidates to {REPORT_PATH}"
    )


def read_photovoltaic_rows(csv_path: Path) -> list[dict[str, str]]:
    csv.field_size_limit(sys.maxsize)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return [dict(row) for row in reader]


def load_comparison_features() -> list[dict]:
    source_paths = [
        SOURCE_DIR / "power_plants.geojson",
        SOURCE_DIR / "gem_wind_greece.geojson",
        SOURCE_DIR / "gem_solar_greece.geojson",
        SOURCE_DIR / "gem_hydro_greece.geojson",
        SOURCE_DIR / "pumped_hydro_seed.geojson",
    ]

    canonical_features: list[dict] = []
    for source_path in source_paths:
        if not source_path.exists():
            continue

        feature_collection = load_source_feature_collection(source_path)
        last_seen = get_file_timestamp(source_path)
        canonical_features.extend(
            build_canonical_generator_feature(feature, last_seen)
            for feature in feature_collection.get("features", [])
        )

    biomass_review_path = (
        BASE_DIR / "data" / "processed" / "biomass_phase1" / "raaey_biomass_candidates.json"
    )
    if biomass_review_path.exists():
        feature_collection = load_source_feature_collection(biomass_review_path)
        last_seen = get_file_timestamp(biomass_review_path)
        canonical_features.extend(
            build_canonical_generator_feature(feature, last_seen)
            for feature in feature_collection.get("features", [])
        )

    return merge_generator_features(canonical_features)


def build_comparison_index(features: list[dict]) -> dict[str, dict[str, list[dict]]]:
    by_bucket: defaultdict[str, list[dict]] = defaultdict(list)
    by_name: defaultdict[str, list[dict]] = defaultdict(list)

    for feature in features:
        properties = feature.get("properties", {})
        latitude = properties.get("latitude")
        longitude = properties.get("longitude")
        for bucket_key in get_neighbor_bucket_keys(latitude, longitude):
            by_bucket[bucket_key].append(feature)

        normalized_name = normalize_text(properties.get("name"))
        if normalized_name:
            by_name[normalized_name].append(feature)

    return {
        "by_bucket": by_bucket,
        "by_name": by_name,
    }


def normalize_status_descriptor(value: object) -> str | None:
    text_value = text_or_none(value)
    if text_value is None:
        return None

    return text_value.strip().upper()


def map_government_status(status_descriptor: str | None) -> dict[str, str] | None:
    if status_descriptor is None:
        return None

    if status_descriptor in ACTIVE_STATUS_RULES:
        status_value, status_category = ACTIVE_STATUS_RULES[status_descriptor]
        return {
            "status": status_value,
            "status_category": status_category,
            "raw_status": status_descriptor,
        }

    if any(keyword in status_descriptor for keyword in EXCLUDED_STATUS_KEYWORDS):
        return None

    return None


def build_government_feature(
    row: dict[str, str],
    status_mapping: dict[str, str],
    last_seen: str,
) -> dict:
    point = get_government_point(row.get("geometry"))
    longitude = None
    latitude = None
    geometry = None

    if point is not None:
        longitude, latitude = egsa87_to_wgs84(point[0], point[1])
        geometry = {
            "type": "Point",
            "coordinates": [longitude, latitude],
        }

    registry_id = clean_text(row.get("id1"))
    application_code = clean_text(row.get("aa"))
    license_id = clean_text(row.get("a_m"))
    company = clean_text(row.get("company"))
    site_name = clean_text(row.get("thesh"))
    project_name = build_project_name(company, site_name)
    nominal_capacity_mw = parse_decimal_value(row.get("power_mw"))
    maximum_capacity_mw = parse_decimal_value(row.get("max_power"))

    source_refs = [
        ref
        for ref in [
            f"gov-pv:fid/{clean_text(row.get('FID'))}" if clean_text(row.get("FID")) else None,
            f"gov-pv:id1/{registry_id}" if registry_id else None,
            f"gov-pv:aa/{application_code}" if application_code else None,
            f"gov-pv:am/{license_id}" if license_id else None,
        ]
        if ref is not None
    ]

    properties = {
        "id": f"gov-pv-{registry_id or application_code or license_id or 'unknown'}",
        "source_record_id": clean_text(row.get("FID")) or registry_id,
        "government_registry_id": registry_id,
        "license_id": license_id,
        "application_code": application_code,
        "name": project_name,
        "project_name": site_name or project_name,
        "site_name": site_name,
        "technology": "solar pv",
        "technology_type": "PV",
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
        "primary_source": PRIMARY_SOURCE,
        "source": PRIMARY_SOURCE,
        "source_dataset": SOURCE_DATASET,
        "source_license": None,
        "source_confidence": 5,
        "source_refs": source_refs,
        "latitude": latitude,
        "longitude": longitude,
        "location_accuracy": "egsa87_polygon_bbox_center" if geometry else "missing_geometry",
        "municipality": clean_text(row.get("kal_dhmos")),
        "regional_unit": clean_text(row.get("kal_perif_enothta")),
        "region": clean_text(row.get("kal_perifereia")),
        "connection_level": None,
        "voltage_kv": None,
        "grid_operator": None,
        "country": "Greece",
        "country_role": "domestic",
        "count_in_summary": True,
        "display_on_map": geometry is not None,
        "last_seen": last_seen,
        "last_updated": last_seen,
        "notes": build_notes(row, status_mapping, point),
    }

    return {
        "type": "Feature",
        "properties": properties,
        "geometry": geometry,
    }


def build_project_name(company: str | None, site_name: str | None) -> str:
    if company and site_name:
        return f"{company} - {site_name}"
    if site_name:
        return site_name
    if company:
        return company
    return "Government PV asset"


def build_notes(
    row: dict[str, str],
    status_mapping: dict[str, str],
    point: tuple[float, float] | None,
) -> list[str]:
    notes: list[str] = []

    if clean_text(row.get("notes")):
        notes.append(clean_text(row.get("notes")))

    notes.append(f"raw_status:{status_mapping['raw_status']}")

    if point is not None:
        notes.append("geometry_from_government_polygon_bbox_center_egsa87")
    else:
        notes.append("missing_government_geometry")

    return notes


def clean_text(value: object) -> str | None:
    return text_or_none(value)


def parse_decimal_value(value: object) -> float | None:
    text_value = clean_text(value)
    if text_value is None:
        return None

    normalized = text_value.replace(" ", "")
    try:
        return round(float(normalized), 6)
    except ValueError:
        return None


def get_government_point(wkt_text: str | None) -> tuple[float, float] | None:
    if not wkt_text:
        return None

    coordinate_pairs = [
        (float(match.group(1)), float(match.group(2)))
        for match in re.finditer(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", wkt_text)
    ]
    if not coordinate_pairs:
        return None

    min_x = min(pair[0] for pair in coordinate_pairs)
    max_x = max(pair[0] for pair in coordinate_pairs)
    min_y = min(pair[1] for pair in coordinate_pairs)
    max_y = max(pair[1] for pair in coordinate_pairs)

    return ((min_x + max_x) / 2, (min_y + max_y) / 2)


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


def find_existing_duplicate(
    candidate_feature: dict,
    existing_features: list[dict],
    comparison_index: dict[str, dict[str, list[dict]]],
) -> dict[str, str] | None:
    candidate_properties = candidate_feature.get("properties", {})
    candidate_name = normalize_text(candidate_properties.get("name"))
    candidate_capacity = candidate_properties.get("nominal_capacity_mw")
    candidate_latitude = candidate_properties.get("latitude")
    candidate_longitude = candidate_properties.get("longitude")
    candidate_operator = normalize_company_name(candidate_properties.get("operator"))

    candidate_matches: list[dict] = []
    for bucket_key in get_neighbor_bucket_keys(candidate_latitude, candidate_longitude):
        candidate_matches.extend(comparison_index["by_bucket"].get(bucket_key, []))

    if candidate_name:
        candidate_matches.extend(comparison_index["by_name"].get(candidate_name, []))

    seen_ids: set[str] = set()
    for existing_feature in candidate_matches:
        properties = existing_feature.get("properties", {})
        existing_id = str(properties.get("id"))
        if existing_id in seen_ids:
            continue
        seen_ids.add(existing_id)

        existing_name = normalize_text(properties.get("name"))
        existing_capacity = properties.get("nominal_capacity_mw")
        existing_operator = normalize_company_name(
            properties.get("operator") or properties.get("owner")
        )
        distance_km = get_distance_km(
            candidate_latitude,
            candidate_longitude,
            properties.get("latitude"),
            properties.get("longitude"),
        )
        capacities_match = capacities_within_tolerance(candidate_capacity, existing_capacity)
        operators_match = (
            candidate_operator is not None
            and existing_operator is not None
            and candidate_operator == existing_operator
        )
        names_match = names_match_loose(candidate_name, existing_name)

        if distance_km is not None and distance_km <= 0.35 and capacities_match:
            return {
                "id": existing_id,
                "name": str(properties.get("name") or existing_id),
                "reason": "nearby_coordinates_and_capacity",
            }

        if (
            distance_km is not None
            and distance_km <= 1.2
            and capacities_match
            and (names_match or operators_match)
        ):
            return {
                "id": existing_id,
                "name": str(properties.get("name") or existing_id),
                "reason": "nearby_coordinates_with_name_or_operator_match",
            }

        if names_match and capacities_match:
            return {
                "id": existing_id,
                "name": str(properties.get("name") or existing_id),
                "reason": "matching_name_and_capacity",
            }

    return None


def normalize_company_name(value: object) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None

    cleaned = normalized
    for token in [
        " ανωνυμη εταιρεια",
        " ανωνυμος εταιρια",
        " αε",
        " α ε",
        " μονοπροσωπη",
        " ικε",
        " επε",
        " οε",
        " εε",
        " sa",
        " ltd",
    ]:
        cleaned = cleaned.replace(token, " ")

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


if __name__ == "__main__":
    main()
