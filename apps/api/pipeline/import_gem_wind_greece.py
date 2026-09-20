from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = BASE_DIR / "data" / "source"
DEFAULT_INPUT_PATH = Path(
    r"C:\Users\megas\Downloads\Global-Wind-Power-Tracker-February-2026.xlsx"
)
OUTPUT_PATH = SOURCE_DIR / "gem_wind_greece.geojson"
XML_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
SHEET_CONFIG = [
    ("xl/worksheets/sheet2.xml", "above_threshold"),
    ("xl/worksheets/sheet3.xml", "below_threshold"),
]
GEM_STATUS_CATEGORY_PREFIXES = [
    ("operating", "Operating"),
    ("construction", "Under Construction"),
    ("pre-construction", "Pre-Construction"),
    ("announced", "Announced"),
    ("shelved", "Shelved"),
    ("cancelled", "Cancelled"),
    ("retired", "Retired"),
    ("mothballed", "Mothballed"),
]


def main():
    workbook_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT_PATH

    if not workbook_path.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook_path}")

    records = read_greece_records_from_workbook(workbook_path)
    feature_collection = {
        "type": "FeatureCollection",
        "features": [build_feature(record) for record in records],
    }

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as output_file:
        json.dump(feature_collection, output_file, ensure_ascii=False, indent=2)

    print(
        f"Wrote {len(feature_collection['features'])} Greece wind features "
        f"to {OUTPUT_PATH}"
    )


def read_greece_records_from_workbook(workbook_path: Path) -> list[dict]:
    records: list[dict] = []

    with zipfile.ZipFile(workbook_path) as workbook_zip:
        shared_strings = read_shared_strings(workbook_zip)

        for sheet_path, threshold_bucket in SHEET_CONFIG:
            sheet_root = ET.fromstring(workbook_zip.read(sheet_path))
            rows = sheet_root.find("main:sheetData", XML_NS).findall("main:row", XML_NS)

            if not rows:
                continue

            headers = read_row_values(rows[0], shared_strings)

            for row in rows[1:]:
                row_values = read_row_values(row, shared_strings)
                record = build_record(headers, row_values)

                if record.get("Country/Area") != "Greece":
                    continue

                record["threshold_bucket"] = threshold_bucket
                records.append(record)

    return records


def read_shared_strings(workbook_zip: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook_zip.namelist():
        return []

    shared_strings_root = ET.fromstring(workbook_zip.read("xl/sharedStrings.xml"))
    values = []

    for shared_string in shared_strings_root.findall("main:si", XML_NS):
        text_value = "".join(
            node.text or "" for node in shared_string.iter() if node.tag.endswith("}t")
        )
        values.append(text_value)

    return values


def read_row_values(row: ET.Element, shared_strings: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}

    for cell in row.findall("main:c", XML_NS):
        reference = cell.attrib.get("r", "")
        column_name = get_column_letters(reference)
        cell_type = cell.attrib.get("t")
        value_node = cell.find("main:v", XML_NS)
        text_value = ""

        if value_node is not None:
            raw_value = value_node.text or ""
            text_value = shared_strings[int(raw_value)] if cell_type == "s" else raw_value
        else:
            inline_string = cell.find("main:is", XML_NS)
            if inline_string is not None:
                text_value = "".join(
                    node.text or ""
                    for node in inline_string.iter()
                    if node.tag.endswith("}t")
                )

        values[column_name] = text_value

    return values


def build_record(headers: dict[str, str], row_values: dict[str, str]) -> dict:
    return {
        headers[column_name]: value
        for column_name, value in row_values.items()
        if column_name in headers
    }


def build_feature(record: dict) -> dict:
    gem_phase_id = record.get("GEM phase ID") or "unknown-phase"
    project_name = clean_text(record.get("Project Name")) or "Unknown wind project"
    phase_name = clean_text(record.get("Phase Name"))
    location_name = build_display_name(project_name, phase_name)
    raw_installation_type = clean_text(record.get("Installation Type")) or "Onshore"
    technology = "offshore wind" if "offshore" in raw_installation_type.lower() else "onshore wind"
    operator = clean_text(record.get("Operator")) or clean_text(record.get("Owner"))

    return {
        "type": "Feature",
        "properties": {
            "id": f"gem-wind-{gem_phase_id}",
            "name": location_name,
            "project_name": project_name,
            "phase_name": phase_name,
            "technology": technology,
            "operator": operator,
            "owner": clean_text(record.get("Owner")),
            "capacity_mw": parse_optional_float(record.get("Capacity (MW)")),
            "nominal_capacity_mw": parse_optional_float(record.get("Capacity (MW)")),
            "capacity_unit": "MW",
            "capacity_type": "nominal",
            "status": clean_text(record.get("Status")),
            "status_category": map_gem_status_category(record.get("Status")),
            "installation_type": raw_installation_type,
            "primary_source": "Global Energy Monitor",
            "source": "Global Energy Monitor",
            "source_dataset": "Global Wind Power Tracker, February 2026 release",
            "source_license": "CC BY 4.0",
            "source_refs": build_source_refs(record),
            "latitude": parse_optional_float(record.get("Latitude")),
            "longitude": parse_optional_float(record.get("Longitude")),
            "location_accuracy": clean_text(record.get("Location accuracy")),
            "municipality": clean_text(record.get("City")),
            "regional_unit": clean_text(record.get("Local area (taluk, county)")),
            "region": clean_text(record.get("State/Province")),
            "major_area": clean_text(record.get("Major area (prefecture, district)")),
            "subregion": clean_text(record.get("Subregion")),
            "global_region": clean_text(record.get("Region")),
            "country": clean_text(record.get("Country/Area")),
            "gem_location_id": clean_text(record.get("GEM location ID")),
            "gem_phase_id": clean_text(record.get("GEM phase ID")),
            "other_ids_location": clean_text(record.get("Other IDs (location)")),
            "other_ids_phase": clean_text(record.get("Other IDs (unit/phase)")),
            "wiki_url": clean_text(record.get("Wiki URL")),
            "threshold_bucket": record.get("threshold_bucket"),
            "commissioning_year": parse_optional_year(record.get("Start year")),
            "decommissioning_year": parse_optional_year(record.get("Retired year")),
            "last_seen": normalize_date_text(record.get("Date Last Researched")),
            "last_updated": normalize_date_text(record.get("Date Last Researched")),
        },
        "geometry": {
            "type": "Point",
            "coordinates": [
                parse_optional_float(record.get("Longitude")),
                parse_optional_float(record.get("Latitude")),
            ],
        },
    }


def build_source_refs(record: dict) -> list[str]:
    references: list[str] = []

    gem_location_id = clean_text(record.get("GEM location ID"))
    gem_phase_id = clean_text(record.get("GEM phase ID"))
    wiki_url = clean_text(record.get("Wiki URL"))

    if gem_location_id:
        references.append(f"gem:location/{gem_location_id}")

    if gem_phase_id:
        references.append(f"gem:phase/{gem_phase_id}")

    if wiki_url:
        references.append(wiki_url)

    for other_ids_key in ["Other IDs (location)", "Other IDs (unit/phase)"]:
        other_ids = clean_text(record.get(other_ids_key))
        if not other_ids:
            continue

        for value in other_ids.split(","):
            normalized_value = value.strip()
            if normalized_value:
                references.append(normalized_value)

    return references


def build_display_name(project_name: str, phase_name: str | None) -> str:
    if not phase_name or phase_name == "--":
        return project_name

    return f"{project_name} - Phase {phase_name}"


def parse_optional_float(value: str | None) -> float | None:
    cleaned = clean_text(value)
    if not cleaned:
        return None

    try:
        return round(float(cleaned), 6)
    except ValueError:
        return None


def parse_optional_year(value: str | None) -> int | None:
    numeric_value = parse_optional_float(value)
    if numeric_value is None:
        return None

    return int(numeric_value)


def normalize_date_text(value: str | None) -> str | None:
    cleaned = clean_text(value)
    if not cleaned:
        return None

    return cleaned.replace("/", "-")


def map_gem_status_category(raw_status: str | None) -> str:
    cleaned = clean_text(raw_status)
    if not cleaned:
        return "Unknown"

    normalized = cleaned.casefold()
    for prefix, category in GEM_STATUS_CATEGORY_PREFIXES:
        if normalized.startswith(prefix):
            return category

    return "Unknown"


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = str(value).strip()
    if cleaned in {"", "--"}:
        return None

    return cleaned


def get_column_letters(cell_reference: str) -> str:
    letters = ""

    for character in cell_reference:
        if character.isalpha():
            letters += character
        else:
            break

    return letters


if __name__ == "__main__":
    main()
