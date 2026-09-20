from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import xlrd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed" / "biomass_phase1"
VALIDATION_DIR = PROCESSED_DIR / "validation"
MANUAL_DIR = DATA_DIR / "manual"

RAAEY_RAW_DIRS = {
    "res_certificates": RAW_DIR / "raaey" / "res_certificates",
    "res_applications": RAW_DIR / "raaey" / "res_applications",
    "ceased_or_revoked": RAW_DIR / "raaey" / "ceased_or_revoked",
}
DEDDIE_RAW_DIR = RAW_DIR / "deddie"
ADMIE_RAW_DIR = RAW_DIR / "admie"
DAPEEP_RAW_DIR = RAW_DIR / "dapeep"

MANUAL_DAPEEP_TEMPLATE_PATH = MANUAL_DIR / "dapeep_biomass_totals_template.csv"
MANUAL_BIOMASS_POINTS_PATH = MANUAL_DIR / "biomass_manual_points.json"
QUALITY_REPORT_PATH = PROCESSED_DIR / "biomass_phase1_quality_report.json"
SUMMARY_TECHNOLOGY_PATH = PROCESSED_DIR / "biomass_phase1_summary_by_technology.csv"
SUMMARY_REGION_PATH = PROCESSED_DIR / "biomass_phase1_summary_by_region.csv"
CANDIDATES_CSV_PATH = PROCESSED_DIR / "raaey_biomass_candidates.csv"
CANDIDATES_JSON_PATH = PROCESSED_DIR / "raaey_biomass_candidates.json"
REVIEW_JSON_PATH = PROCESSED_DIR / "biomass_candidates_for_review.json"
README_PATH = PROCESSED_DIR / "README_biomass_phase1.md"

EGSA87_FALSE_EASTING = 500000.0
EGSA87_SCALE_FACTOR = 0.9996
EGSA87_CENTRAL_MERIDIAN_DEGREES = 24.0
GRS80_SEMI_MAJOR_AXIS = 6378137.0
GRS80_FLATTENING = 1 / 298.257222101
GRS80_ECCENTRICITY_SQUARED = (
    2 * GRS80_FLATTENING - GRS80_FLATTENING * GRS80_FLATTENING
)

XLSX_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

NULL_TEXT_VALUES = {"", "-", "unknown", "n/a", "na", "none", "null"}
BIOMASS_TERM_HINTS = [
    "βιομάζα",
    "βιομαζα",
    "βιοαέριο",
    "βιοαεριο",
    "βιορευστά",
    "βιορευστα",
    "βιοαποδομήσιμο",
    "βιοαποδομησιμο",
    "χυτα",
    "χυτυ",
    "σηθυα",
    "biomass",
    "biogas",
    "biofuel",
    "bio-liquid",
    "bioliquid",
    "landfill gas",
    "waste gas",
    "cogeneration",
    "chp",
]
HEADER_ALIASES = {
    "license_id": [
        "αριθμος βεβαιωσης",
        "αρ βεβαιωσης",
        "αριθμος αδειας",
        "αρ αδειας",
        "κωδικος",
        "αδα",
        "αρ μητρωου αδειων ραε",
        "αριθμος μητρωου αδειων",
        "aριθμος μητρωου αδειων",
        "αρ ειδικου πρωτοκολλου αιτησης",
        "αιτηση",
    ],
    "owner": [
        "κατοχος",
        "εταιρεια",
        "φορεας",
        "αιτων",
        "δικαιουχος",
        "επωνυμια",
        "επωνυμια εταιρειας",
    ],
    "project_name": [
        "εργο",
        "ονομασια εργου",
        "θεση",
        "τοποθεσια",
        "περιοχη",
        "ονομασια σταθμου",
    ],
    "technology": [
        "τεχνολογια",
        "μορφη απε",
        "καυσιμο",
        "ειδος σταθμου",
        "κατηγορια",
        "πηγη ενεργειας",
        "τεχνολογια απε",
        "τεχνολογια σταθμου",
    ],
    "capacity": [
        "ισχυς",
        "ισχυς mw",
        "εγκατεστημενη ισχυς",
        "εγκατεστημενη ισχυς mw",
        "μεγιστη ισχυς παραγωγης",
        "μεγιστη ισχυς",
        "μεγ ισχυς mw",
        "μεγιστη ισχυς απε mw",
        "εγκ ισχυς mw",
        "mw",
        "ισχυς παραγωγης",
    ],
    "municipality": ["δημος", "δήμος"],
    "regional_unit": ["περιφερειακη ενοτητα", "πε", "περιφερειακη ενοτητα πε"],
    "region": ["περιφερεια"],
    "status": ["κατασταση"],
    "issue_date": ["ημερομηνια εκδοσης", "ημερομηνια εκδ αδ παραγωγης"],
    "decision_date": ["ημερομηνια αποφασης", "ημερομηνια εκδ αποφασης ανακλησης παυσης αδ παραγωγης"],
    "cease_date": ["ημερομηνια παυσης"],
    "revoke_date": ["ημερομηνια ανακλησης"],
}
STAGING_FIELD_ORDER = [
    "id",
    "source_record_id",
    "source",
    "source_file",
    "source_sheet",
    "source_row_number",
    "license_id",
    "name",
    "normalized_name",
    "project_name",
    "owner",
    "operator",
    "developer",
    "raw_technology",
    "technology",
    "technology_category",
    "carrier",
    "fuel",
    "is_chp",
    "nominal_capacity_mw",
    "capacity_type",
    "status",
    "license_status",
    "derived_status",
    "region",
    "regional_unit",
    "municipality",
    "latitude",
    "longitude",
    "geometry",
    "primary_source",
    "source_confidence",
    "source_refs",
    "raw_record",
    "data_quality_flags",
    "last_seen",
]
COMPANY_SUFFIX_PATTERNS = [
    r"\bα\.?ε\.?\b",
    r"\bμον\s+ικε\b",
    r"\bικε\b",
    r"\bεπε\b",
    r"\bοε\b",
    r"\bεε\b",
    r"\bsa\b",
    r"\bs\.a\.?\b",
    r"\bltd\b",
]
CHP_HINTS = ["σηθυα", "σηθ", "chp", "cogeneration", "co generation"]
LAND_FILL_HINTS = ["χυτα", "χυτυ", "landfill gas"]


def run_biomass_phase1(raw_root: Path | None = None) -> dict:
    effective_raw_root = raw_root or RAW_DIR
    ensure_output_directories()
    raaey_result = extract_raaey_biomass_candidates(effective_raw_root)
    records = raaey_result["records"]
    manual_location_evidence = apply_manual_location_evidence(records)
    duplicates = find_possible_duplicates(records)

    deddie_validation = run_deddie_validation(records, effective_raw_root)
    admie_validation = run_admie_validation(records, effective_raw_root)
    dapeep_validation = run_dapeep_validation(records, effective_raw_root)
    validation_sources = {
        "deddie": deddie_validation["status"],
        "admie": admie_validation["status"],
        "dapeep": dapeep_validation["status"],
    }

    write_records_csv(CANDIDATES_CSV_PATH, records)
    write_json(CANDIDATES_JSON_PATH, records)
    write_json(REVIEW_JSON_PATH, records)
    write_summary_csv(SUMMARY_TECHNOLOGY_PATH, build_summary_by_technology(records))
    write_summary_csv(SUMMARY_REGION_PATH, build_summary_by_region(records))
    write_json(VALIDATION_DIR / "deddie_biomass_validation.json", deddie_validation)
    write_json(VALIDATION_DIR / "admie_biomass_validation.json", admie_validation)
    write_json(VALIDATION_DIR / "dapeep_biomass_validation.json", dapeep_validation)

    quality_report = build_quality_report(
        raaey_result=raaey_result,
        records=records,
        duplicates=duplicates,
        manual_location_evidence=manual_location_evidence,
        validation_sources=validation_sources,
        deddie_validation=deddie_validation,
        admie_validation=admie_validation,
        dapeep_validation=dapeep_validation,
    )
    write_json(QUALITY_REPORT_PATH, quality_report)
    write_readme(records, quality_report)

    return {
        "records": records,
        "quality_report": quality_report,
        "validation": {
            "deddie": deddie_validation,
            "admie": admie_validation,
            "dapeep": dapeep_validation,
        },
    }


def get_biomass_phase1_quality_report() -> dict:
    if not QUALITY_REPORT_PATH.exists():
        return {
            "status": "not_generated",
            "message": "Run pipeline/run_biomass_phase1.py first.",
        }

    with QUALITY_REPORT_PATH.open("r", encoding="utf-8") as report_file:
        return json.load(report_file)


def get_biomass_phase1_candidates() -> dict:
    if not CANDIDATES_JSON_PATH.exists():
        return {
            "status": "not_generated",
            "message": "Run pipeline/run_biomass_phase1.py first.",
        }

    with CANDIDATES_JSON_PATH.open("r", encoding="utf-8") as candidates_file:
        records = json.load(candidates_file)

    return {"status": "ok", "total_records": len(records), "candidates": records}


def get_biomass_phase1_summary() -> dict:
    if not REVIEW_JSON_PATH.exists():
        return {
            "status": "not_generated",
            "message": "Run pipeline/run_biomass_phase1.py first.",
        }

    with REVIEW_JSON_PATH.open("r", encoding="utf-8") as review_file:
        records = json.load(review_file)

    return {
        "status": "ok",
        "total_records": len(records),
        "summary_by_technology": build_summary_by_technology(records),
        "summary_by_region": build_summary_by_region(records),
    }


def ensure_output_directories():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    MANUAL_DIR.mkdir(parents=True, exist_ok=True)


def extract_raaey_biomass_candidates(raw_root: Path) -> dict:
    file_groups = [
        ("res_certificates", raw_root / "raaey" / "res_certificates"),
        ("res_applications", raw_root / "raaey" / "res_applications"),
        ("ceased_or_revoked", raw_root / "raaey" / "ceased_or_revoked"),
    ]

    all_records: list[dict] = []
    total_rows_read = 0
    raw_files_read: list[str] = []
    warnings: list[str] = []

    for source_group, folder_path in file_groups:
        if not folder_path.exists():
            warnings.append(f"missing_folder:{folder_path}")
            continue

        for workbook_path in sorted(iter_excel_files(folder_path)):
            raw_files_read.append(str(workbook_path))
            workbook_rows = read_workbook_rows(workbook_path)

            for sheet in workbook_rows:
                header_row_index = detect_header_row_index(sheet["rows"])
                if header_row_index is None:
                    warnings.append(
                        f"header_not_detected:{workbook_path.name}:{sheet['sheet_name']}"
                    )
                    continue

                headers = sheet["rows"][header_row_index]
                column_bindings = detect_column_bindings(headers)

                for relative_index, row in enumerate(
                    sheet["rows"][header_row_index + 1 :],
                    start=header_row_index + 2,
                ):
                    total_rows_read += 1
                    if is_empty_row(row):
                        continue

                    raw_record = build_raw_record(headers, row)
                    if not row_is_biomass_related(raw_record):
                        continue

                    candidate_record = build_candidate_record(
                        raw_record=raw_record,
                        source_file=workbook_path.name,
                        source_sheet=sheet["sheet_name"],
                        source_row_number=relative_index,
                        source_group=source_group,
                        column_bindings=column_bindings,
                        workbook_path=workbook_path,
                    )
                    all_records.append(candidate_record)

    return {
        "records": all_records,
        "raw_files_read": raw_files_read,
        "total_raw_rows_read": total_rows_read,
        "warnings": warnings,
    }


def apply_manual_location_evidence(records: list[dict]) -> dict:
    manual_entries = load_manual_biomass_points()
    if not manual_entries["file_exists"]:
        return {
            "file_exists": False,
            "source_file": str(MANUAL_BIOMASS_POINTS_PATH),
            "total_entries": 0,
            "matched_records": 0,
            "geometry_applied_count": 0,
            "ambiguous_entries": [],
            "unmatched_entries": [],
            "warnings": [],
        }

    by_license_id: defaultdict[str, list[dict]] = defaultdict(list)
    by_license_id_digits: defaultdict[str, list[dict]] = defaultdict(list)
    by_name: defaultdict[str, list[dict]] = defaultdict(list)
    for record in records:
        license_id = text_or_none(record.get("license_id"))
        if license_id:
            by_license_id[license_id] = by_license_id[license_id] + [record]
            license_id_digits = normalize_license_id_digits(license_id)
            if license_id_digits:
                by_license_id_digits[license_id_digits] = by_license_id_digits[license_id_digits] + [record]

        normalized_name = normalize_name(
            record.get("project_name") or record.get("name") or record.get("owner")
        )
        if normalized_name:
            by_name[normalized_name] = by_name[normalized_name] + [record]

    geometry_applied_count = 0
    matched_records = 0
    ambiguous_entries: list[dict] = []
    unmatched_entries: list[dict] = []
    warnings = list(manual_entries["warnings"])

    for entry in manual_entries["entries"]:
        matched_candidates: list[dict] = []
        license_id = text_or_none(entry.get("license_id"))
        if license_id:
            matched_candidates = by_license_id.get(license_id, [])
            if not matched_candidates:
                license_id_digits = normalize_license_id_digits(license_id)
                if license_id_digits:
                    matched_candidates = by_license_id_digits.get(license_id_digits, [])

        if not matched_candidates:
            normalized_name = text_or_none(entry.get("normalized_name"))
            if normalized_name:
                matched_candidates = by_name.get(normalized_name, [])

        if not matched_candidates:
            unmatched_entries.append(summarize_manual_location_entry(entry))
            continue

        if len(matched_candidates) > 1:
            ambiguous_entries.append(
                {
                    "manual_entry": summarize_manual_location_entry(entry),
                    "candidate_asset_ids": [candidate["id"] for candidate in matched_candidates],
                }
            )
            continue

        record = matched_candidates[0]
        applied_geometry = apply_manual_entry_to_record(record, entry)
        matched_records += 1
        if applied_geometry:
            geometry_applied_count += 1

    return {
        "file_exists": True,
        "source_file": str(MANUAL_BIOMASS_POINTS_PATH),
        "total_entries": len(manual_entries["entries"]),
        "matched_records": matched_records,
        "geometry_applied_count": geometry_applied_count,
        "ambiguous_entries": ambiguous_entries,
        "unmatched_entries": unmatched_entries,
        "warnings": warnings,
    }


def load_manual_biomass_points() -> dict:
    if not MANUAL_BIOMASS_POINTS_PATH.exists():
        return {"file_exists": False, "entries": [], "warnings": []}

    with MANUAL_BIOMASS_POINTS_PATH.open("r", encoding="utf-8") as manual_file:
        raw_payload = json.load(manual_file)

    raw_entries = (
        raw_payload.get("points", [])
        if isinstance(raw_payload, dict)
        else raw_payload
    )
    entries: list[dict] = []
    warnings: list[str] = []

    if not isinstance(raw_entries, list):
        return {
            "file_exists": True,
            "entries": [],
            "warnings": ["invalid_manual_biomass_points_payload"],
        }

    for index, raw_entry in enumerate(raw_entries, start=1):
        if not isinstance(raw_entry, dict):
            warnings.append(f"invalid_manual_biomass_point_entry:{index}")
            continue
        entries.append(normalize_manual_location_entry(raw_entry, index))

    return {"file_exists": True, "entries": entries, "warnings": warnings}


def normalize_license_id_digits(raw_value: object) -> str | None:
    text_value = text_or_none(raw_value)
    if not text_value:
        return None

    digits_only = "".join(character for character in text_value if character.isdigit())
    return digits_only or None


def derive_wgs84_coordinates_from_manual_entry(
    latitude: float | None,
    longitude: float | None,
    x_egsa87: float | None,
    y_egsa87: float | None,
    coordinate_system: str | None,
) -> tuple[float | None, float | None]:
    if latitude is not None and longitude is not None:
        return latitude, longitude

    normalized_coordinate_system = (coordinate_system or "").strip().upper()
    if normalized_coordinate_system not in {"EGSA87", "EPSG:2100", "EPSG2100", "ΕΓΣΑ87", "ΕΓΣΑ 87"}:
        return latitude, longitude

    if x_egsa87 is None or y_egsa87 is None:
        return latitude, longitude

    derived_latitude, derived_longitude = egsa87_to_wgs84(x_egsa87, y_egsa87)
    return derived_latitude, derived_longitude


def egsa87_to_wgs84(
    x_egsa87: float,
    y_egsa87: float,
) -> tuple[float | None, float | None]:
    x = x_egsa87 - EGSA87_FALSE_EASTING
    y = y_egsa87
    a = GRS80_SEMI_MAJOR_AXIS
    e_sq = GRS80_ECCENTRICITY_SQUARED
    e_prime_sq = e_sq / (1 - e_sq)
    e1 = (1 - math.sqrt(1 - e_sq)) / (1 + math.sqrt(1 - e_sq))

    meridional_arc = y / EGSA87_SCALE_FACTOR
    mu = meridional_arc / (
        a
        * (
            1
            - e_sq / 4
            - 3 * e_sq * e_sq / 64
            - 5 * e_sq * e_sq * e_sq / 256
        )
    )

    phi1_rad = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )

    sin_phi1 = math.sin(phi1_rad)
    cos_phi1 = math.cos(phi1_rad)
    tan_phi1 = math.tan(phi1_rad)

    n1 = a / math.sqrt(1 - e_sq * sin_phi1**2)
    t1 = tan_phi1**2
    c1 = e_prime_sq * cos_phi1**2
    r1 = a * (1 - e_sq) / (1 - e_sq * sin_phi1**2) ** 1.5
    d = x / (n1 * EGSA87_SCALE_FACTOR)

    latitude_rad = phi1_rad - (
        n1
        * tan_phi1
        / r1
        * (
            d**2 / 2
            - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * e_prime_sq) * d**4 / 24
            + (
                61
                + 90 * t1
                + 298 * c1
                + 45 * t1**2
                - 252 * e_prime_sq
                - 3 * c1**2
            )
            * d**6
            / 720
        )
    )

    longitude_rad = math.radians(EGSA87_CENTRAL_MERIDIAN_DEGREES) + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * e_prime_sq + 24 * t1**2)
        * d**5
        / 120
    ) / cos_phi1

    latitude = math.degrees(latitude_rad)
    longitude = math.degrees(longitude_rad)

    if not (19 <= longitude <= 30 and 34 <= latitude <= 43):
        return None, None

    return round(latitude, 7), round(longitude, 7)


def normalize_manual_location_entry(raw_entry: dict[str, object], index: int) -> dict:
    name = text_or_none(raw_entry.get("name"))
    normalized_name = text_or_none(
        normalize_name(raw_entry.get("normalized_name") or name or raw_entry.get("license_id"))
    )
    latitude = parse_optional_float(raw_entry.get("latitude"))
    longitude = parse_optional_float(raw_entry.get("longitude"))
    x_egsa87 = parse_optional_float(raw_entry.get("x_egsa87"))
    y_egsa87 = parse_optional_float(raw_entry.get("y_egsa87"))
    coordinate_system = text_or_none(raw_entry.get("coordinate_system")) or "EGSA87"
    latitude, longitude = derive_wgs84_coordinates_from_manual_entry(
        latitude,
        longitude,
        x_egsa87,
        y_egsa87,
        coordinate_system,
    )

    return {
        "id": text_or_none(raw_entry.get("id")) or f"manual-biomass-point-{index:03d}",
        "license_id": text_or_none(raw_entry.get("license_id")),
        "name": name,
        "normalized_name": normalized_name,
        "latitude": latitude,
        "longitude": longitude,
        "x_egsa87": x_egsa87,
        "y_egsa87": y_egsa87,
        "coordinate_system": coordinate_system,
        "evidence_type": text_or_none(raw_entry.get("evidence_type")) or "manual_geolocation",
        "notes": text_or_none(raw_entry.get("notes")),
    }


def summarize_manual_location_entry(entry: dict[str, object]) -> dict:
    return {
        "id": entry.get("id"),
        "license_id": entry.get("license_id"),
        "name": entry.get("name"),
        "normalized_name": entry.get("normalized_name"),
        "coordinate_system": entry.get("coordinate_system"),
        "latitude": entry.get("latitude"),
        "longitude": entry.get("longitude"),
        "x_egsa87": entry.get("x_egsa87"),
        "y_egsa87": entry.get("y_egsa87"),
        "notes": entry.get("notes"),
    }


def apply_manual_entry_to_record(record: dict, entry: dict[str, object]) -> bool:
    record["source_refs"] = list(record.get("source_refs") or [])
    record["source_refs"].append(
        {
            "source_name": "Manual biomass location evidence",
            "source_file": MANUAL_BIOMASS_POINTS_PATH.name,
            "source_sheet": None,
            "source_row_number": None,
            "fields_extracted": [
                field_name
                for field_name in [
                    "license_id",
                    "name",
                    "latitude",
                    "longitude",
                    "x_egsa87",
                    "y_egsa87",
                    "coordinate_system",
                    "notes",
                ]
                if entry.get(field_name) is not None
            ],
            "evidence_type": entry.get("evidence_type"),
            "coordinate_system": entry.get("coordinate_system"),
            "notes": entry.get("notes"),
        }
    )

    record["data_quality_flags"] = unique_preserve_order(
        list(record.get("data_quality_flags") or [])
        + (
            ["manual_geolocation_applied"]
            if has_wgs84_geometry(entry)
            else ["manual_geolocation_recorded_without_wgs84"]
        )
    )

    if not has_wgs84_geometry(entry):
        return False

    record["latitude"] = entry["latitude"]
    record["longitude"] = entry["longitude"]
    record["geometry"] = {
        "type": "Point",
        "coordinates": [entry["longitude"], entry["latitude"]],
    }
    return True


def has_wgs84_geometry(entry: dict[str, object]) -> bool:
    return isinstance(entry.get("latitude"), (int, float)) and isinstance(
        entry.get("longitude"), (int, float)
    )


def parse_optional_float(raw_value: object) -> float | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)

    normalized_value = text_or_none(raw_value)
    if normalized_value is None:
        return None

    try:
        return float(normalized_value.replace(",", "."))
    except ValueError:
        return None


def build_candidate_record(
    raw_record: dict[str, object],
    source_file: str,
    source_sheet: str,
    source_row_number: int,
    source_group: str,
    column_bindings: dict[str, list[str]],
    workbook_path: Path,
) -> dict:
    license_id = first_value(raw_record, column_bindings.get("license_id", []))
    owner = first_value(raw_record, column_bindings.get("owner", []))
    project_name = first_value(raw_record, column_bindings.get("project_name", []))
    raw_technology = first_value(raw_record, column_bindings.get("technology", []))
    municipality = first_value(raw_record, column_bindings.get("municipality", []))
    regional_unit = first_value(raw_record, column_bindings.get("regional_unit", []))
    region = first_value(raw_record, column_bindings.get("region", []))
    raw_capacity = first_value(raw_record, column_bindings.get("capacity", []))

    technology_result = normalize_biomass_technology(raw_record)
    capacity_result = parse_biomass_capacity_to_mw(raw_capacity)
    status = infer_raaey_status(source_group, raw_record, source_file)
    normalized_name = normalize_name(project_name or owner or license_id or "unknown")
    source_record_id = f"{source_file}:{source_sheet}:{source_row_number}"
    digest = hashlib.sha1(source_record_id.encode("utf-8")).hexdigest()[:12]
    notes = list(technology_result["flags"]) + list(capacity_result["warnings"])
    notes.append("raaey_not_operating_evidence")

    data_quality_flags: list[str] = []
    if not text_or_none(license_id):
        data_quality_flags.append("missing_license_id")
    if not text_or_none(owner):
        data_quality_flags.append("missing_owner")
    if not text_or_none(project_name):
        data_quality_flags.append("missing_project_name")
    if not text_or_none(raw_technology):
        data_quality_flags.append("missing_technology")
    if technology_result["technology"] == "unknown_biomass_related":
        data_quality_flags.append("unknown_biomass_related_technology")
        data_quality_flags.append("needs_manual_review")
    if capacity_result["value_mw"] is None:
        data_quality_flags.append("missing_capacity")
    if "invalid_capacity" in capacity_result["warnings"]:
        data_quality_flags.append("invalid_capacity")
    if not any(text_or_none(value) for value in [municipality, regional_unit, region]):
        data_quality_flags.append("missing_location")
    if status in {"ceased", "revoked"}:
        data_quality_flags.append("ceased_or_revoked")
    if technology_result["is_chp"]:
        data_quality_flags.append("possible_chp_record")
    data_quality_flags.extend(flag for flag in notes if flag == "needs_manual_review")

    extracted_fields = [
        field_name
        for field_name, headers in column_bindings.items()
        if first_value(raw_record, headers) is not None
    ]
    source_ref = {
        "source_name": "RAAEY",
        "source_file": source_file,
        "source_sheet": source_sheet,
        "source_row_number": source_row_number,
        "fields_extracted": extracted_fields,
    }
    last_seen = datetime.fromtimestamp(
        workbook_path.stat().st_mtime,
        tz=timezone.utc,
    ).isoformat()

    return {
        "id": f"raaey-biomass-{digest}",
        "source_record_id": source_record_id,
        "source": "RAAEY",
        "source_file": source_file,
        "source_sheet": source_sheet,
        "source_row_number": source_row_number,
        "license_id": text_or_none(license_id),
        "name": text_or_none(project_name) or text_or_none(owner) or text_or_none(license_id),
        "normalized_name": normalized_name,
        "project_name": text_or_none(project_name),
        "owner": text_or_none(owner),
        "operator": None,
        "developer": None,
        "raw_technology": text_or_none(raw_technology),
        "technology": technology_result["technology"],
        "technology_category": technology_result["technology_category"],
        "carrier": technology_result["carrier"],
        "fuel": technology_result["fuel"],
        "is_chp": technology_result["is_chp"],
        "nominal_capacity_mw": capacity_result["value_mw"],
        "capacity_type": "licensed",
        "status": status,
        "license_status": status,
        "derived_status": technology_result.get("derived_status"),
        "region": text_or_none(region),
        "regional_unit": text_or_none(regional_unit),
        "municipality": text_or_none(municipality),
        "latitude": None,
        "longitude": None,
        "geometry": None,
        "primary_source": "RAAEY",
        "source_confidence": 3,
        "source_refs": [source_ref],
        "raw_record": raw_record,
        "data_quality_flags": unique_preserve_order(
            data_quality_flags + ["raaey_not_operating_evidence"]
        ),
        "last_seen": last_seen,
    }


def normalize_biomass_technology(raw_record: dict[str, object]) -> dict:
    combined_text = build_combined_search_text(raw_record)
    normalized_text = normalize_text_for_matching(combined_text)
    raw_technology = normalize_text_for_matching(
        str(raw_record.get("ΤΕΧΝΟΛΟΓΙΑ") or raw_record.get("ΤΕΧΝΟΛΟΓΙΑ ΑΠΕ") or raw_record.get("ΤΕΧΝΟΛΟΓΙΑ ΣΤΑΘΜΟΥ") or "")
    )

    is_chp = any(hint in normalized_text for hint in CHP_HINTS)
    flags: list[str] = []

    if any(hint in normalized_text for hint in LAND_FILL_HINTS):
        return {
            "technology": "landfill_gas",
            "technology_category": "Biomass/Biogas",
            "carrier": "landfill_gas",
            "fuel": "landfill_gas",
            "is_chp": is_chp,
            "flags": flags,
        }

    if "βιοαεριο" in normalized_text or "biogas" in normalized_text:
        return {
            "technology": "biogas",
            "technology_category": "Biomass/Biogas",
            "carrier": "biogas",
            "fuel": "biogas",
            "is_chp": is_chp,
            "flags": flags,
        }

    if "βιομαζα" in normalized_text or "biomass" in normalized_text:
        return {
            "technology": "biomass",
            "technology_category": "Biomass/Biogas",
            "carrier": "biomass",
            "fuel": "biomass",
            "is_chp": is_chp,
            "flags": flags,
        }

    if "βιορευστα" in normalized_text or "bioliquid" in normalized_text or "bio liquid" in normalized_text or "biofuel" in normalized_text:
        return {
            "technology": "bioliquid",
            "technology_category": "Biomass/Biogas",
            "carrier": "bioliquid",
            "fuel": "bioliquid",
            "is_chp": is_chp,
            "flags": flags,
        }

    if "βιοαποδομησιμο" in normalized_text or "waste gas" in normalized_text or "waste to energy" in normalized_text:
        return {
            "technology": "waste_to_energy",
            "technology_category": "Biomass/Biogas",
            "carrier": "waste",
            "fuel": "waste",
            "is_chp": is_chp,
            "flags": flags,
        }

    if is_chp:
        flags.append("possible_chp_record")
        return {
            "technology": "chp",
            "technology_category": "CHP",
            "carrier": "chp",
            "fuel": None,
            "is_chp": True,
            "flags": flags,
        }

    flags.extend(["unknown_biomass_related_technology", "needs_manual_review"])
    return {
        "technology": "unknown_biomass_related",
        "technology_category": "Biomass/Biogas",
        "carrier": "unknown",
        "fuel": None,
        "is_chp": False,
        "flags": flags,
    }


def infer_raaey_status(source_group: str, raw_record: dict[str, object], source_file: str) -> str:
    normalized_text = normalize_text_for_matching(
        " ".join(str(value) for value in raw_record.values() if value is not None)
        + f" {source_file}"
    )

    if source_group == "res_applications":
        return "application"

    if source_group == "ceased_or_revoked":
        if "ανακλη" in normalized_text or text_or_none(raw_record.get("ΑΡΙΘΜΟΣ ΑΝΑΚΛΗΣΗΣ")):
            return "revoked"
        if "παυ" in normalized_text or "επαυσαν" in normalized_text or "ληξ" in normalized_text:
            return "ceased"
        return "unknown"

    if source_group == "res_certificates":
        return "licensed"

    return "unknown"


def parse_biomass_capacity_to_mw(raw_value: object) -> dict:
    warnings: list[str] = []
    if raw_value is None:
        return {"value_mw": None, "warnings": warnings}

    if isinstance(raw_value, (int, float)):
        numeric_value = float(raw_value)
        if numeric_value < 0:
            return {"value_mw": None, "warnings": ["invalid_capacity"]}
        return {"value_mw": round(numeric_value, 6), "warnings": warnings}

    text_value = str(raw_value).strip()
    if normalize_text_for_matching(text_value) in NULL_TEXT_VALUES:
        return {"value_mw": None, "warnings": warnings}

    unit_match = re.search(r"(gw|mw|kw)\b", text_value.casefold())
    unit = unit_match.group(1) if unit_match else "mw"
    number_match = re.search(r"-?\d[\d.,\s]*", text_value)
    if not number_match:
        return {"value_mw": None, "warnings": ["invalid_capacity"]}

    numeric_value = parse_localized_number(number_match.group(0), unit=unit)
    if numeric_value is None or numeric_value < 0:
        return {"value_mw": None, "warnings": ["invalid_capacity"]}

    if unit == "gw":
        value_mw = numeric_value * 1000
    elif unit == "kw":
        value_mw = numeric_value / 1000
    else:
        value_mw = numeric_value

    return {"value_mw": round(value_mw, 6), "warnings": warnings}


def parse_localized_number(text_value: str, unit: str = "mw") -> float | None:
    sanitized = text_value.replace(" ", "")
    if not sanitized:
        return None

    if "," in sanitized and "." in sanitized:
        if sanitized.rfind(",") > sanitized.rfind("."):
            sanitized = sanitized.replace(".", "").replace(",", ".")
        else:
            sanitized = sanitized.replace(",", "")
    elif "," in sanitized:
        if sanitized.count(",") == 1:
            sanitized = sanitized.replace(",", ".")
        else:
            sanitized = sanitized.replace(",", "")
    elif "." in sanitized:
        parts = sanitized.split(".")
        if len(parts) > 2:
            sanitized = "".join(parts)
        elif (
            len(parts) == 2
            and len(parts[1]) == 3
            and unit == "kw"
            and parts[0] != "0"
        ):
            sanitized = "".join(parts)

    try:
        return float(sanitized)
    except ValueError:
        return None


def normalize_name(value: object) -> str:
    normalized_text = normalize_text_for_matching(value)
    if not normalized_text:
        return ""

    normalized_text = normalized_text.replace("ς", "σ")
    for suffix_pattern in COMPANY_SUFFIX_PATTERNS:
        normalized_text = re.sub(suffix_pattern, " ", normalized_text)
    normalized_text = re.sub(r"[^a-z0-9α-ω\s]", " ", normalized_text)
    normalized_text = re.sub(r"\s+", " ", normalized_text).strip()
    return normalized_text


def row_is_biomass_related(raw_record: dict[str, object]) -> bool:
    combined_text = normalize_text_for_matching(build_combined_search_text(raw_record))
    return any(term in combined_text for term in BIOMASS_TERM_HINTS)


def build_combined_search_text(raw_record: dict[str, object]) -> str:
    return " ".join(str(value) for value in raw_record.values() if value not in {None, ""})


def normalize_text_for_matching(value: object) -> str:
    if value is None:
        return ""

    text_value = str(value).strip().lower().replace("ς", "σ")
    text_value = unicodedata.normalize("NFD", text_value)
    text_value = "".join(character for character in text_value if not unicodedata.combining(character))
    text_value = re.sub(r"[^\w\s/-]", " ", text_value)
    text_value = re.sub(r"\s+", " ", text_value).strip()
    return text_value


def read_workbook_rows(workbook_path: Path) -> list[dict]:
    if workbook_path.suffix.casefold() == ".xls":
        return read_xls_rows(workbook_path)

    return read_xlsx_rows(workbook_path)


def read_xls_rows(workbook_path: Path) -> list[dict]:
    workbook = xlrd.open_workbook(workbook_path)
    sheets: list[dict] = []

    for sheet_name in workbook.sheet_names():
        sheet = workbook.sheet_by_name(sheet_name)
        rows = []
        for row_index in range(sheet.nrows):
            rows.append(
                [normalize_excel_cell_value(sheet.cell_value(row_index, column_index)) for column_index in range(sheet.ncols)]
            )
        sheets.append({"sheet_name": sheet_name, "rows": rows})

    return sheets


def read_xlsx_rows(workbook_path: Path) -> list[dict]:
    sheets: list[dict] = []
    with zipfile.ZipFile(workbook_path) as workbook_zip:
        shared_strings = read_shared_strings(workbook_zip)
        for sheet_name, sheet_path in iter_xlsx_sheets(workbook_zip):
            root = ET.fromstring(workbook_zip.read(sheet_path))
            sheet_data = root.find("main:sheetData", XLSX_NS)
            rows = []
            if sheet_data is None:
                sheets.append({"sheet_name": sheet_name, "rows": rows})
                continue

            for row in sheet_data.findall("main:row", XLSX_NS):
                row_cells: dict[int, str] = {}
                max_index = -1
                for cell in row.findall("main:c", XLSX_NS):
                    reference = cell.attrib.get("r", "")
                    column_index = get_excel_column_index(reference)
                    max_index = max(max_index, column_index)
                    row_cells[column_index] = read_xlsx_cell_value(cell, shared_strings)
                rows.append(
                    [row_cells.get(index, "") for index in range(max_index + 1)]
                    if max_index >= 0
                    else []
                )

            sheets.append({"sheet_name": sheet_name, "rows": rows})

    return sheets


def read_shared_strings(workbook_zip: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook_zip.namelist():
        return []

    root = ET.fromstring(workbook_zip.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for shared_string in root.findall("main:si", XLSX_NS):
        values.append(
            "".join(
                node.text or ""
                for node in shared_string.iter()
                if node.tag.endswith("}t")
            )
        )

    return values


def iter_xlsx_sheets(workbook_zip: zipfile.ZipFile) -> Iterable[tuple[str, str]]:
    workbook_root = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
    relationships_root = ET.fromstring(workbook_zip.read("xl/_rels/workbook.xml.rels"))
    relationship_targets = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships_root.findall("pkg:Relationship", XLSX_NS)
    }

    for sheet in workbook_root.findall("main:sheets/main:sheet", XLSX_NS):
        relationship_id = sheet.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        target = relationship_targets.get(relationship_id)
        if target is None:
            continue
        yield sheet.attrib.get("name", "Sheet"), f"xl/{target}"


def read_xlsx_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    value_node = cell.find("main:v", XLSX_NS)
    if value_node is not None:
        raw_value = value_node.text or ""
        return (
            shared_strings[int(raw_value)]
            if cell.attrib.get("t") == "s"
            else normalize_excel_cell_value(raw_value)
        )

    inline_string = cell.find("main:is", XLSX_NS)
    if inline_string is None:
        return ""

    return "".join(
        node.text or ""
        for node in inline_string.iter()
        if node.tag.endswith("}t")
    )


def get_excel_column_index(reference: str) -> int:
    column_letters = "".join(character for character in reference if character.isalpha())
    column_index = 0
    for character in column_letters:
        column_index = column_index * 26 + (ord(character.upper()) - ord("A") + 1)
    return max(column_index - 1, 0)


def normalize_excel_cell_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def detect_header_row_index(rows: list[list[str]]) -> int | None:
    best_index: int | None = None
    best_score = 0
    for row_index, row in enumerate(rows[:15]):
        score = score_header_row(row)
        if score > best_score:
            best_score = score
            best_index = row_index

    return best_index if best_score >= 3 else None


def score_header_row(row: list[str]) -> int:
    score = 0
    normalized_headers = [normalize_text_for_matching(value) for value in row]
    for aliases in HEADER_ALIASES.values():
        if any(any(alias in header for alias in aliases) for header in normalized_headers):
            score += 1
    return score


def detect_column_bindings(headers: list[str]) -> dict[str, list[str]]:
    bindings: dict[str, list[str]] = {}
    normalized_headers = {
        header: normalize_text_for_matching(header)
        for header in headers
        if normalize_text_for_matching(header)
    }

    for field_name, aliases in HEADER_ALIASES.items():
        matched_headers = [
            header
            for header, normalized_header in normalized_headers.items()
            if any(alias in normalized_header for alias in aliases)
        ]
        bindings[field_name] = matched_headers

    return bindings


def build_raw_record(headers: list[str], row: list[str]) -> dict[str, object]:
    width = max(len(headers), len(row))
    record: dict[str, object] = {}

    for index in range(width):
        header = headers[index] if index < len(headers) and headers[index].strip() else f"column_{index + 1}"
        value = row[index] if index < len(row) else ""
        record[header] = normalize_excel_cell_value(value)

    return record


def is_empty_row(row: list[str]) -> bool:
    return not any(str(value).strip() for value in row)


def first_value(raw_record: dict[str, object], headers: list[str]) -> object | None:
    for header in headers:
        value = raw_record.get(header)
        if text_or_none(value):
            return value
    return None


def text_or_none(value: object) -> str | None:
    if value is None:
        return None

    text_value = str(value).strip()
    if not text_value or normalize_text_for_matching(text_value) in NULL_TEXT_VALUES:
        return None
    return text_value


def find_possible_duplicates(records: list[dict]) -> list[dict]:
    duplicates: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()

    for left_index in range(len(records)):
        left = records[left_index]
        for right_index in range(left_index + 1, len(records)):
            right = records[right_index]
            reasons: list[str] = []

            if left["license_id"] and left["license_id"] == right["license_id"]:
                reasons.append("same_license_id")

            if (
                left["normalized_name"]
                and left["normalized_name"] == right["normalized_name"]
                and normalize_name(left.get("municipality")) == normalize_name(right.get("municipality"))
            ):
                reasons.append("same_normalized_name_municipality")

            if (
                normalize_name(left.get("owner")) == normalize_name(right.get("owner"))
                and normalize_name(left.get("municipality")) == normalize_name(right.get("municipality"))
                and capacities_within_tolerance(
                    left.get("nominal_capacity_mw"),
                    right.get("nominal_capacity_mw"),
                )
            ):
                reasons.append("same_owner_municipality_capacity")

            if (
                normalize_name(left.get("project_name")) == normalize_name(right.get("project_name"))
                and normalize_name(left.get("regional_unit")) == normalize_name(right.get("regional_unit"))
            ):
                reasons.append("same_project_regional_unit")

            if not reasons:
                continue

            key = tuple(sorted((left["id"], right["id"])))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            duplicates.append(
                {
                    "asset_ids": list(key),
                    "name_pair": [left.get("name"), right.get("name")],
                    "owner_pair": [left.get("owner"), right.get("owner")],
                    "capacity_pair_mw": [
                        left.get("nominal_capacity_mw"),
                        right.get("nominal_capacity_mw"),
                    ],
                    "reasons": reasons,
                }
            )

    return duplicates


def capacities_within_tolerance(left: object, right: object) -> bool:
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return False

    tolerance = max(abs(float(left)), abs(float(right))) * 0.05
    tolerance = max(tolerance, 0.05)
    return abs(float(left) - float(right)) <= tolerance


def build_summary_by_technology(records: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for record in records:
        technology = record["technology"]
        summary = grouped.setdefault(
            technology,
            {
                "technology": technology,
                "technology_category": record["technology_category"],
                "count_records": 0,
                "total_nominal_capacity_mw": 0.0,
                "count_missing_capacity": 0,
            },
        )
        summary["count_records"] += 1
        if record["nominal_capacity_mw"] is None:
            summary["count_missing_capacity"] += 1
        else:
            summary["total_nominal_capacity_mw"] = round(
                summary["total_nominal_capacity_mw"] + record["nominal_capacity_mw"],
                6,
            )

    return sorted(
        grouped.values(),
        key=lambda item: (-item["total_nominal_capacity_mw"], item["technology"]),
    )


def build_summary_by_region(records: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for record in records:
        region = record["region"] or record["regional_unit"] or record["municipality"] or "Unknown"
        summary = grouped.setdefault(
            region,
            {
                "region": region,
                "count_records": 0,
                "total_nominal_capacity_mw": 0.0,
                "count_missing_capacity": 0,
            },
        )
        summary["count_records"] += 1
        if record["nominal_capacity_mw"] is None:
            summary["count_missing_capacity"] += 1
        else:
            summary["total_nominal_capacity_mw"] = round(
                summary["total_nominal_capacity_mw"] + record["nominal_capacity_mw"],
                6,
            )

    return sorted(
        grouped.values(),
        key=lambda item: (-item["total_nominal_capacity_mw"], item["region"]),
    )


def build_quality_report(
    raaey_result: dict,
    records: list[dict],
    duplicates: list[dict],
    manual_location_evidence: dict,
    validation_sources: dict[str, str],
    deddie_validation: dict,
    admie_validation: dict,
    dapeep_validation: dict,
) -> dict:
    technology_counts = Counter(record["technology"] for record in records)
    capacity_by_technology: defaultdict[str, float] = defaultdict(float)
    for record in records:
        if isinstance(record["nominal_capacity_mw"], (int, float)):
            capacity_by_technology[record["technology"]] += float(record["nominal_capacity_mw"])

    count_missing_capacity = sum(1 for record in records if record["nominal_capacity_mw"] is None)
    count_missing_owner = sum(1 for record in records if not text_or_none(record["owner"]))
    count_missing_location = sum(
        1
        for record in records
        if not any(text_or_none(record[field]) for field in ["region", "regional_unit", "municipality"])
    )
    count_ceased_revoked = sum(
        1 for record in records if record["status"] in {"ceased", "revoked"}
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_raw_files_read": len(raaey_result["raw_files_read"]),
        "total_raw_rows_read": raaey_result["total_raw_rows_read"],
        "total_biomass_related_rows_extracted": len(records),
        "count_by_technology": dict(technology_counts),
        "total_licensed_capacity_by_technology_mw": {
            technology: round(total_capacity, 6)
            for technology, total_capacity in sorted(capacity_by_technology.items())
        },
        "count_missing_capacity": count_missing_capacity,
        "count_missing_owner": count_missing_owner,
        "count_missing_location": count_missing_location,
        "count_ceased_or_revoked": count_ceased_revoked,
        "count_possible_duplicates": len(duplicates),
        "top_20_possible_duplicate_records": duplicates[:20],
        "manual_location_evidence": manual_location_evidence,
        "validation_sources_found": validation_sources,
        "warnings": raaey_result["warnings"],
        "validation_details": {
            "deddie": deddie_validation,
            "admie": admie_validation,
            "dapeep": dapeep_validation,
        },
    }


def run_deddie_validation(records: list[dict], raw_root: Path) -> dict:
    files = list(iter_excel_files(raw_root / "deddie"))
    if not files:
        return {
            "status": "validation_source_not_available",
            "notes": ["No DEDDIE raw files found."],
        }

    return {
        "status": "source_found_but_not_structured_for_asset_validation",
        "notes": [
            "DEDDE source files are present, but the current local file layout is aggregate/non-plant-level.",
            "Regional biomass operating validation was not derived automatically in this phase.",
        ],
        "files": [file.name for file in files],
        "comparisons": [],
    }


def run_admie_validation(records: list[dict], raw_root: Path) -> dict:
    files = list(iter_excel_files(raw_root / "admie"))
    if not files:
        return {
            "status": "validation_source_not_available",
            "notes": ["No ADMIE raw files found."],
            "matched_records": [],
        }

    matched_records: list[dict] = []
    notes = ["ADMIE files found. Parser hooks prepared, but no confirmed biomass matches were derived in this phase."]

    for file_path in files:
        workbook_rows = read_workbook_rows(file_path)
        for sheet in workbook_rows:
            header_row_index = detect_header_row_index(sheet["rows"])
            if header_row_index is None:
                continue

            headers = sheet["rows"][header_row_index]
            for relative_index, row in enumerate(sheet["rows"][header_row_index + 1 :], start=header_row_index + 2):
                raw_record = build_raw_record(headers, row)
                if not row_is_biomass_related(raw_record):
                    continue

                status_value = derive_admie_status(raw_record)
                if status_value == "unknown":
                    continue

                matched_records.append(
                    {
                        "source_file": file_path.name,
                        "source_sheet": sheet["sheet_name"],
                        "source_row_number": relative_index,
                        "admie_status": status_value,
                    }
                )

    status = "source_found" if matched_records else "source_found_but_no_biomass_matches"
    return {
        "status": status,
        "notes": notes,
        "files": [file.name for file in files],
        "matched_records": matched_records,
    }


def derive_admie_status(raw_record: dict[str, object]) -> str:
    raw_values = [str(value).strip() for value in raw_record.values() if value is not None]
    if not raw_values:
        return "unknown"

    last_value = raw_values[-1]
    if last_value == "+":
        return "operating"
    if last_value == "2":
        return "connection_offer"
    return "unknown"


def run_dapeep_validation(records: list[dict], raw_root: Path) -> dict:
    files = list((raw_root / "dapeep").glob("*"))
    build_dapeep_manual_template()

    if not files:
        return {
            "status": "validation_source_not_available",
            "notes": ["No DAPEEP raw files found.", "Manual template created."],
            "manual_template": str(MANUAL_DAPEEP_TEMPLATE_PATH),
        }

    return {
        "status": "manual_template_required",
        "notes": [
            "DAPEEP files were found, but automated ELAPE biomass extraction was not completed in this phase.",
            "Use the manual totals template to capture biomass/biogas aggregate validation.",
        ],
        "files": [file.name for file in files],
        "manual_template": str(MANUAL_DAPEEP_TEMPLATE_PATH),
    }


def build_dapeep_manual_template():
    MANUAL_DIR.mkdir(parents=True, exist_ok=True)
    if MANUAL_DAPEEP_TEMPLATE_PATH.exists():
        return

    rows = [
        ["period", "technology", "installed_capacity_mw", "generation_mwh", "source_file", "notes"],
    ]
    with MANUAL_DAPEEP_TEMPLATE_PATH.open("w", encoding="utf-8", newline="") as template_file:
        writer = csv.writer(template_file)
        writer.writerows(rows)


def write_records_csv(path: Path, records: list[dict]):
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=STAGING_FIELD_ORDER)
        writer.writeheader()
        for record in records:
            writer.writerow({field: serialize_csv_value(record.get(field)) for field in STAGING_FIELD_ORDER})


def write_summary_csv(path: Path, rows: list[dict]):
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as csv_file:
            csv_file.write("")
        return

    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: object):
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, ensure_ascii=False, indent=2)


def write_readme(records: list[dict], quality_report: dict):
    manual_location_summary = quality_report.get("manual_location_evidence", {})
    lines = [
        "# Biomass Phase 1",
        "",
        "This folder contains the first staged biomass/biogas/CHP extraction from local RAAEY files.",
        "",
        "## How to run",
        "",
        "```bash",
        "python pipeline/run_biomass_phase1.py",
        "```",
        "",
        "## Outputs",
        "",
        "- `raaey_biomass_candidates.csv`",
        "- `raaey_biomass_candidates.json`",
        "- `biomass_candidates_for_review.json`",
        "- `biomass_phase1_quality_report.json`",
        "- `biomass_phase1_summary_by_technology.csv`",
        "- `biomass_phase1_summary_by_region.csv`",
        "- `validation/*.json`",
        "- `../../manual/biomass_manual_points.json`",
        "",
        "## Meaning",
        "",
        "- RAAEY records represent the licensing/application universe, not proof of operation.",
        "- `derived_status` should only be upgraded by stronger validation sources such as ADMIE.",
        "- `biomass_manual_points.json` can hold manual geolocation evidence for licensed biomass/biogas projects.",
        "- Manual points do not create fake plants. They only enrich a matched record or remain listed as unmatched evidence.",
        f"- Current extracted record count: {len(records)}",
        f"- Current missing capacity count: {quality_report['count_missing_capacity']}",
        f"- Current manual location entries: {manual_location_summary.get('total_entries', 0)}",
        f"- Current manual location matches: {manual_location_summary.get('matched_records', 0)}",
        "",
    ]
    README_PATH.write_text("\n".join(lines), encoding="utf-8")


def serialize_csv_value(value: object) -> object:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def iter_excel_files(folder_path: Path) -> Iterable[Path]:
    if not folder_path.exists():
        return []

    return [
        path
        for path in sorted(folder_path.iterdir())
        if path.is_file() and path.suffix.casefold() in {".xls", ".xlsx"}
    ]


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
