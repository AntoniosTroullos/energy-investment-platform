from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = BASE_DIR / "data" / "source"
DEFAULT_INPUT_PATH = Path(
    r"C:\Users\megas\Downloads\Global-Hydropower-Tracker-March-2026.xlsx"
)
OUTPUT_PATH = SOURCE_DIR / "gem_hydro_greece.geojson"
XML_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}
SHEET_CONFIG = {
    "Data": "main_tracker",
    "Below Threshold": "below_threshold",
}
EXCEL_EPOCH = datetime(1899, 12, 30)
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
    features = [build_hydropower_feature(record) for record in records]

    feature_collection = {
        "type": "FeatureCollection",
        "features": features,
    }

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as output_file:
        json.dump(feature_collection, output_file, ensure_ascii=False, indent=2)

    print(
        f"Wrote {len(feature_collection['features'])} Greece hydropower features "
        f"to {OUTPUT_PATH}"
    )


def read_greece_records_from_workbook(workbook_path: Path) -> list[dict]:
    records: list[dict] = []

    with zipfile.ZipFile(workbook_path) as workbook_zip:
        shared_strings = read_shared_strings(workbook_zip)
        sheet_targets = get_sheet_targets(workbook_zip)

        for sheet_name, threshold_bucket in SHEET_CONFIG.items():
            sheet_path = sheet_targets.get(sheet_name)
            if not sheet_path:
                continue

            sheet_root = ET.fromstring(workbook_zip.read(sheet_path))
            rows = sheet_root.find("main:sheetData", XML_NS).findall("main:row", XML_NS)
            if not rows:
                continue

            headers = read_row_values(rows[0], shared_strings)

            for row in rows[1:]:
                row_values = read_row_values(row, shared_strings)
                record = build_record(headers, row_values)
                record = normalize_hydropower_record(record)

                if not is_greece_record(record):
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


def get_sheet_targets(workbook_zip: zipfile.ZipFile) -> dict[str, str]:
    workbook_root = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
    relationships_root = ET.fromstring(workbook_zip.read("xl/_rels/workbook.xml.rels"))
    relationship_targets = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships_root.findall("pkg:Relationship", REL_NS)
    }
    sheet_targets: dict[str, str] = {}

    for sheet in workbook_root.findall("main:sheets/main:sheet", REL_NS):
        sheet_name = sheet.attrib.get("name")
        relationship_id = sheet.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        target = relationship_targets.get(relationship_id)

        if sheet_name and target:
            sheet_targets[sheet_name] = f"xl/{target}"

    return sheet_targets


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


def normalize_hydropower_record(record: dict) -> dict:
    country_1 = clean_text(record.get("Country/Area 1"))
    country_2 = clean_text(record.get("Country/Area 2"))
    greece_is_country_1 = normalize_country(country_1) == "greece"
    greece_is_country_2 = normalize_country(country_2) == "greece"

    if greece_is_country_1:
        country_capacity = parse_optional_float(record.get("Country/Area 1 Capacity (MW)"))
        municipality = clean_text(record.get("City 1"))
        regional_unit = clean_text(record.get("Local Area 1"))
        major_area = clean_text(record.get("Major Area 1"))
        region = clean_text(record.get("State/Province 1"))
        subregion = clean_text(record.get("Subregion 1"))
        global_region = clean_text(record.get("Region 1"))
        country_role = "country_1"
    elif greece_is_country_2:
        country_capacity = parse_optional_float(record.get("Country/Area 2 Capacity (MW)"))
        municipality = clean_text(record.get("City 2"))
        regional_unit = clean_text(record.get("Local Area 2"))
        major_area = clean_text(record.get("Major Area 2"))
        region = clean_text(record.get("State/Province 2"))
        subregion = clean_text(record.get("Subregion 2"))
        global_region = clean_text(record.get("Region 2"))
        country_role = "country_2"
    else:
        country_capacity = None
        municipality = None
        regional_unit = None
        major_area = None
        region = None
        subregion = None
        global_region = None
        country_role = None

    normalized_record = dict(record)
    normalized_record["country"] = "Greece"
    normalized_record["country_role"] = country_role
    normalized_record["capacity_mw_greece_share"] = country_capacity
    normalized_record["municipality"] = municipality
    normalized_record["regional_unit"] = regional_unit
    normalized_record["major_area"] = major_area
    normalized_record["region"] = region
    normalized_record["subregion"] = subregion
    normalized_record["global_region"] = global_region
    return normalized_record


def is_greece_record(record: dict) -> bool:
    return normalize_country(record.get("Country/Area 1")) == "greece" or normalize_country(
        record.get("Country/Area 2")
    ) == "greece"


def build_hydropower_feature(record: dict) -> dict:
    gem_unit_id = clean_text(record.get("GEM unit ID")) or "unknown-unit"
    project_name = clean_text(record.get("Project Name")) or "Unknown hydropower project"
    local_name = clean_text(record.get("Project Name (local lang/script)"))
    other_names = clean_text(record.get("Other name(s)"))
    technology_type = clean_text(record.get("Technology Type")) or "conventional storage"
    technology = map_hydropower_technology(technology_type)
    capacity_mw = (
        parse_optional_float(record.get("capacity_mw_greece_share"))
        or parse_optional_float(record.get("Capacity (MW)"))
    )
    operator = clean_text(record.get("Operator")) or clean_text(record.get("Owner"))
    latitude = parse_optional_float(record.get("Latitude"))
    longitude = parse_optional_float(record.get("Longitude"))
    is_amfilochia_subasset = is_amfilochia_subasset_name(project_name)

    return {
        "type": "Feature",
        "properties": {
            "id": f"gem-hydro-{gem_unit_id}",
            "name": project_name,
            "project_name": project_name,
            "local_name": local_name,
            "other_names": other_names,
            "technology": technology,
            "operator": operator,
            "owner": clean_text(record.get("Owner")),
            "capacity_mw": capacity_mw,
            "nominal_capacity_mw": capacity_mw,
            "capacity_unit": "MW" if capacity_mw is not None else None,
            "capacity_type": "nominal" if capacity_mw is not None else None,
            "status": clean_text(record.get("Status")),
            "status_category": map_gem_status_category(record.get("Status")),
            "technology_type": technology_type,
            "primary_source": "Global Energy Monitor",
            "source": "Global Energy Monitor",
            "source_dataset": "Global Hydropower Tracker, March 2026 release",
            "source_license": "CC BY 4.0",
            "source_refs": build_source_refs(record),
            "latitude": latitude,
            "longitude": longitude,
            "location_accuracy": clean_text(record.get("Location Accuracy")),
            "municipality": clean_text(record.get("municipality")),
            "regional_unit": clean_text(record.get("regional_unit")),
            "major_area": clean_text(record.get("major_area")),
            "region": clean_text(record.get("region")),
            "subregion": clean_text(record.get("subregion")),
            "global_region": clean_text(record.get("global_region")),
            "country": "Greece",
            "country_role": clean_text(record.get("country_role")),
            "binational": normalize_boolean(record.get("Binational")),
            "complex": clean_text(record.get("Complex")),
            "turbines": parse_optional_int(record.get("Turbines")),
            "river_watercourse": clean_text(record.get("River / Watercourse")),
            "country_1": clean_text(record.get("Country/Area 1")),
            "country_2": clean_text(record.get("Country/Area 2")),
            "country_1_capacity_mw": parse_optional_float(record.get("Country/Area 1 Capacity (MW)")),
            "country_2_capacity_mw": parse_optional_float(record.get("Country/Area 2 Capacity (MW)")),
            "total_project_capacity_mw": parse_optional_float(record.get("Capacity (MW)")),
            "gem_location_id": clean_text(record.get("GEM location ID")),
            "gem_phase_id": clean_text(record.get("GEM unit ID")),
            "wiki_url": clean_text(record.get("Wiki URL")),
            "threshold_bucket": clean_text(record.get("threshold_bucket")),
            "commissioning_year": parse_optional_year(record.get("Start Year")),
            "decommissioning_year": parse_optional_year(record.get("Retired Year")),
            "last_seen": normalize_date_text(record.get("Date Last Researched")),
            "last_updated": normalize_date_text(record.get("Date Last Researched")),
            "parent_project_name": (
                "Amfilochia Pumped Storage" if is_amfilochia_subasset else None
            ),
            "display_on_map": True,
            "count_in_summary": not is_amfilochia_subasset,
        },
        "geometry": {
            "type": "Point",
            "coordinates": [longitude, latitude],
        },
    }


def build_source_refs(record: dict) -> list[str]:
    references: list[str] = []

    gem_location_id = clean_text(record.get("GEM location ID"))
    gem_unit_id = clean_text(record.get("GEM unit ID"))
    wiki_url = clean_text(record.get("Wiki URL"))

    if gem_location_id:
        references.append(f"gem:location/{gem_location_id}")

    if gem_unit_id:
        references.append(f"gem:unit/{gem_unit_id}")

    if wiki_url:
        references.append(wiki_url)

    return references


def is_amfilochia_subasset_name(project_name: str | None) -> bool:
    if not project_name:
        return False

    normalized_name = project_name.strip().casefold()
    return normalized_name in {
        "amfilochia georgios hydroelectric plant",
        "amfilochia pygros hydroelectric plant",
    }


def map_hydropower_technology(technology_type: str) -> str:
    normalized_value = technology_type.strip().casefold()

    if "pumped" in normalized_value:
        return "pumped hydro"

    return "conventional hydro"


def parse_optional_float(value: str | None) -> float | None:
    cleaned = clean_text(value)
    if not cleaned:
        return None

    try:
        return round(float(cleaned), 6)
    except ValueError:
        return None


def parse_optional_int(value: str | None) -> int | None:
    parsed = parse_optional_float(value)
    if parsed is None:
        return None
    return int(parsed)


def parse_optional_year(value: str | None) -> int | None:
    parsed = parse_optional_float(value)
    if parsed is None:
        return None
    return int(parsed)


def normalize_date_text(value: str | None) -> str | None:
    cleaned = clean_text(value)
    if not cleaned:
        return None

    numeric_value = parse_optional_float(cleaned)
    if numeric_value is not None and cleaned.replace(".", "", 1).isdigit():
        excel_date = EXCEL_EPOCH + timedelta(days=numeric_value)
        return excel_date.date().isoformat()

    return cleaned.replace("/", "-")


def normalize_country(value: str | None) -> str | None:
    cleaned = clean_text(value)
    if not cleaned:
        return None

    return cleaned.casefold()


def normalize_boolean(value: str | None) -> bool | None:
    cleaned = clean_text(value)
    if not cleaned:
        return None

    normalized_value = cleaned.casefold()
    if normalized_value in {"yes", "true"}:
        return True
    if normalized_value in {"no", "false"}:
        return False
    return None


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
