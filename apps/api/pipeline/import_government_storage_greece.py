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
DEFAULT_INSTALLATION_INPUT_PATH = Path(
    r"C:\Users\megas\Downloads\v_sdi_r_storage12.csv"
)
DEFAULT_OPERATION_INPUT_PATH = Path(
    r"C:\Users\megas\Downloads\v_sdi_r_storage13.csv"
)
OUTPUT_PATH = SOURCE_DIR / "government_storage_greece.geojson"
REPORT_PATH = PROCESSED_DIR / "government_storage_import_report.json"

PRIMARY_SOURCE = "Greek Government Storage Registry"
INSTALLATION_SOURCE_DATASET = "v_sdi_r_storage12.csv"
OPERATION_SOURCE_DATASET = "v_sdi_r_storage13.csv"

STATUS_RULES = {
    "ΑΔΕΙΑ ΛΕΙΤΟΥΡΓΙΑΣ": ("operating", "Operating"),
    "ΑΔΕΙΑ ΕΓΚΑΤΑΣΤΑΣΗΣ": ("installation_license", "Under Construction"),
}
STATUS_PREFERENCE = {
    "Operating": 2,
    "Under Construction": 1,
    "Unknown": 0,
}

GRS80_A = 6378137.0
GRS80_INV_F = 298.257222101
GREEK_GRID_E0 = 500000.0
GREEK_GRID_N0 = 0.0
GREEK_GRID_K0 = 0.9996
GREEK_GRID_LON0_RAD = math.radians(24.0)


def main() -> None:
    installation_path = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INSTALLATION_INPUT_PATH
    )
    operation_path = (
        Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OPERATION_INPUT_PATH
    )

    if not installation_path.exists():
        raise FileNotFoundError(f"Installation storage CSV not found: {installation_path}")

    if not operation_path.exists():
        raise FileNotFoundError(f"Operation storage CSV not found: {operation_path}")

    installation_rows = read_rows(installation_path)
    operation_rows = read_rows(operation_path)
    comparison_features = load_comparison_features()
    comparison_index = build_comparison_index(comparison_features)

    candidate_features = build_candidate_features(
        installation_rows,
        operation_rows,
        installation_path,
        operation_path,
    )

    kept_features: list[dict] = []
    skipped_duplicates: list[dict] = []
    seen_candidate_keys: set[str] = set()

    for feature in candidate_features:
        candidate_key = build_candidate_identity_key(feature)
        if candidate_key in seen_candidate_keys:
            continue
        seen_candidate_keys.add(candidate_key)

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

    feature_collection = {
        "type": "FeatureCollection",
        "features": kept_features,
    }
    report = {
        "installation_source_file": str(installation_path),
        "operation_source_file": str(operation_path),
        "installation_rows_read": len(installation_rows),
        "operation_rows_read": len(operation_rows),
        "candidate_features_built": len(candidate_features),
        "kept_features": len(kept_features),
        "skipped_due_to_duplicates": len(skipped_duplicates),
        "technology_breakdown": summarize_breakdown(
            kept_features, "technology_category"
        ),
        "status_breakdown": summarize_breakdown(
            kept_features, "status_category"
        ),
        "empty_operation_source": len(operation_rows) == 0,
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
        f"Wrote {len(kept_features)} government storage features to {OUTPUT_PATH} "
        f"and {len(skipped_duplicates)} duplicate candidates to {REPORT_PATH}"
    )


def read_rows(csv_path: Path) -> list[dict[str, str]]:
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
        SOURCE_DIR / "government_photovoltaics_greece.geojson",
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


def build_candidate_features(
    installation_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    installation_path: Path,
    operation_path: Path,
) -> list[dict]:
    features: list[dict] = []
    grouped_rows: defaultdict[str, list[tuple[dict[str, str], str, Path]]] = defaultdict(list)

    for row in installation_rows:
        grouped_rows[get_row_group_key(row)].append(
            (row, "installation", installation_path)
        )

    for row in operation_rows:
        grouped_rows[get_row_group_key(row)].append(
            (row, "operation", operation_path)
        )

    for grouped_entries in grouped_rows.values():
        preferred_row, source_kind, source_path = choose_preferred_row(grouped_entries)
        features.append(
            build_storage_feature(
                preferred_row,
                source_kind,
                source_path,
                grouped_entries,
            )
        )

    return features


def get_row_group_key(row: dict[str, str]) -> str:
    for key_name in ["a_m", "aa", "id1", "FID"]:
        key_value = clean_text(row.get(key_name))
        if key_value:
            return f"{key_name}:{key_value}"

    name = normalize_text(build_project_name(clean_text(row.get("company")), clean_text(row.get("thesh"))))
    municipality = normalize_text(row.get("kal_dhmos")) or "unknown"
    return f"name:{name}|municipality:{municipality}"


def choose_preferred_row(
    grouped_entries: list[tuple[dict[str, str], str, Path]]
) -> tuple[dict[str, str], str, Path]:
    best_entry = grouped_entries[0]
    best_priority = -1

    for row, source_kind, source_path in grouped_entries:
        status_mapping = map_storage_status(row.get("katastash_descr"), source_kind)
        priority = STATUS_PREFERENCE.get(status_mapping["status_category"], 0)
        if priority > best_priority:
            best_entry = (row, source_kind, source_path)
            best_priority = priority

    return best_entry


def build_storage_feature(
    row: dict[str, str],
    source_kind: str,
    source_path: Path,
    grouped_entries: list[tuple[dict[str, str], str, Path]],
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

    company = clean_text(row.get("company"))
    site_name = clean_text(row.get("thesh"))
    project_name = build_project_name(company, site_name)
    status_mapping = map_storage_status(row.get("katastash_descr"), source_kind)
    technology = normalize_storage_technology(row.get("texnologia"))
    source_dataset = (
        OPERATION_SOURCE_DATASET if source_kind == "operation" else INSTALLATION_SOURCE_DATASET
    )

    generation_capacity_mw = parse_decimal_value(row.get("max_pwr_eg"))
    pumping_capacity_mw = parse_decimal_value(row.get("max_pwr_ap"))
    energy_capacity_mwh = parse_decimal_value(row.get("egk_capac"))
    guaranteed_capacity_mwh = parse_decimal_value(row.get("guar_capac"))
    environmental_terms_approved = normalize_yes_no(row.get("epo"))

    source_refs = [
        {
            "source_name": PRIMARY_SOURCE,
            "source_file": source_path.name,
            "fields_supported": [
                "name",
                "technology",
                "status",
                "generation_capacity_mw",
                "pumping_capacity_mw",
                "energy_capacity_mwh",
                "guaranteed_capacity_mwh",
                "region",
                "regional_unit",
                "municipality",
            ],
            "source_record_id": clean_text(row.get("FID")) or clean_text(row.get("id1")),
            "application_code": clean_text(row.get("aa")),
            "license_id": clean_text(row.get("a_m")),
        }
    ]

    if len(grouped_entries) > 1:
        source_refs[0]["merged_status_files"] = [
            entry_source_path.name for _, _, entry_source_path in grouped_entries
        ]

    properties = {
        "id": build_storage_id(row),
        "source_record_id": clean_text(row.get("FID")) or clean_text(row.get("id1")),
        "government_registry_id": clean_text(row.get("id1")),
        "license_id": clean_text(row.get("a_m")),
        "application_code": clean_text(row.get("aa")),
        "name": project_name,
        "project_name": site_name or project_name,
        "site_name": site_name,
        "technology": technology,
        "technology_category": "Storage",
        "carrier": "pumped_hydro" if technology == "pumped_hydro" else "battery",
        "fuel": "water" if technology == "pumped_hydro" else "electricity",
        "operator": company,
        "owner": company,
        "developer": company,
        "capacity_mw": generation_capacity_mw,
        "nominal_capacity_mw": generation_capacity_mw,
        "generation_capacity_mw": generation_capacity_mw,
        "pumping_capacity_mw": pumping_capacity_mw,
        "energy_capacity_mwh": energy_capacity_mwh,
        "guaranteed_capacity_mwh": guaranteed_capacity_mwh,
        "capacity_unit": "MW" if generation_capacity_mw is not None else None,
        "capacity_type": "nominal" if generation_capacity_mw is not None else None,
        "status": status_mapping["status"],
        "status_category": status_mapping["status_category"],
        "license_status": status_mapping["raw_status"],
        "raw_technology": clean_text(row.get("texnologia")),
        "primary_source": PRIMARY_SOURCE,
        "source": PRIMARY_SOURCE,
        "source_dataset": source_dataset,
        "source_confidence": 5,
        "source_refs": source_refs,
        "latitude": latitude,
        "longitude": longitude,
        "location_accuracy": "egsa87_polygon_bbox_center" if geometry else "missing_geometry",
        "municipality": clean_text(row.get("kal_dhmos")),
        "municipal_unit": clean_text(row.get("kal_dhm_enothta")),
        "regional_unit": clean_text(row.get("kal_perif_enothta")),
        "region": clean_text(row.get("kal_perifereia")),
        "country": "Greece",
        "country_role": "domestic",
        "environmental_terms_approved": environmental_terms_approved,
        "count_in_summary": True,
        "display_on_map": geometry is not None,
        "last_seen": get_file_timestamp(source_path),
        "last_updated": get_file_timestamp(source_path),
        "notes": build_notes(row, status_mapping, point, source_kind, grouped_entries),
    }

    return {
        "type": "Feature",
        "properties": properties,
        "geometry": geometry,
    }


def summarize_breakdown(features: list[dict], field_name: str) -> dict[str, int]:
    counts: Counter[str] = Counter()

    for feature in features:
        value = feature.get("properties", {}).get(field_name) or "Unknown"
        counts[str(value)] += 1

    return dict(sorted(counts.items()))


def build_storage_id(row: dict[str, str]) -> str:
    for key_name in ["id1", "aa", "a_m"]:
        key_value = clean_text(row.get(key_name))
        if key_value:
            normalized = normalize_text(key_value) or key_value.lower()
            return f"gov-storage-{normalized}"

    fallback = normalize_text(
        build_project_name(clean_text(row.get("company")), clean_text(row.get("thesh")))
    ) or "unknown"
    return f"gov-storage-{fallback}"


def map_storage_status(value: object, source_kind: str) -> dict[str, str]:
    raw_status = clean_text(value)
    if raw_status is not None and raw_status in STATUS_RULES:
        status_value, status_category = STATUS_RULES[raw_status]
        return {
            "status": status_value,
            "status_category": status_category,
            "raw_status": raw_status,
        }

    if source_kind == "operation":
        return {
            "status": "operating",
            "status_category": "Operating",
            "raw_status": raw_status or "ΑΔΕΙΑ ΛΕΙΤΟΥΡΓΙΑΣ",
        }

    return {
        "status": "installation_license",
        "status_category": "Under Construction",
        "raw_status": raw_status or "ΑΔΕΙΑ ΕΓΚΑΤΑΣΤΑΣΗΣ",
    }


def normalize_storage_technology(value: object) -> str:
    text_value = clean_text(value)
    if text_value is None:
        return "battery_storage"

    normalized = text_value.upper()
    if "ΑΝΤΛΗΣΙΟΤΑΜΙΕΥΣ" in normalized:
        return "pumped_hydro"
    if "ΣΥΣΣΩΡΕΥ" in normalized:
        return "battery_storage"

    return "battery_storage"


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


def build_project_name(company: str | None, site_name: str | None) -> str:
    if company and site_name:
        return f"{company} - {site_name}"
    if site_name:
        return site_name
    if company:
        return company
    return "Government storage asset"


def build_notes(
    row: dict[str, str],
    status_mapping: dict[str, str],
    point: tuple[float, float] | None,
    source_kind: str,
    grouped_entries: list[tuple[dict[str, str], str, Path]],
) -> list[str]:
    notes: list[str] = []

    raw_notes = clean_text(row.get("notes"))
    if raw_notes:
        notes.append(raw_notes)

    notes.append(f"raw_status:{status_mapping['raw_status']}")
    notes.append(f"source_kind:{source_kind}")

    if len(grouped_entries) > 1:
        notes.append("merged_across_storage_status_files")

    if point is not None:
        notes.append("geometry_from_government_polygon_bbox_center_egsa87")
    else:
        notes.append("missing_government_geometry")

    if normalize_yes_no(row.get("epo")) is True:
        notes.append("environmental_terms_approved")

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


def build_candidate_identity_key(feature: dict) -> str:
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
    candidate_technology = candidate_properties.get("technology")

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
        existing_technology = properties.get("technology")
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
        technologies_match = (
            candidate_technology == existing_technology
            or (
                candidate_technology == "pumped_hydro"
                and existing_technology == "pumped_hydro"
            )
        )

        if (
            distance_km is not None
            and distance_km <= 0.35
            and capacities_match
            and technologies_match
        ):
            return {
                "id": existing_id,
                "name": str(properties.get("name") or existing_id),
                "reason": "nearby_coordinates_capacity_and_technology",
            }

        if names_match and capacities_match and technologies_match:
            return {
                "id": existing_id,
                "name": str(properties.get("name") or existing_id),
                "reason": "matching_name_capacity_and_technology",
            }

        if (
            distance_km is not None
            and distance_km <= 1.2
            and capacities_match
            and operators_match
            and technologies_match
        ):
            return {
                "id": existing_id,
                "name": str(properties.get("name") or existing_id),
                "reason": "nearby_coordinates_with_operator_match",
            }

    return None


def normalize_company_name(value: object) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None

    cleaned = normalized
    for token in [
        "ανωνυμηεταιρεια",
        "αε",
        "μονοπροσωπη",
        "ικε",
        "επε",
        "οε",
        "εε",
        "sa",
        "ltd",
    ]:
        cleaned = cleaned.replace(token, " ")

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


if __name__ == "__main__":
    main()
