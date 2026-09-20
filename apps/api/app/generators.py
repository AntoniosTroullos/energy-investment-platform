from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.ops import unary_union
from shapely.prepared import prep


SOURCE_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "source"
PROCESSED_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed" / "biomass_phase1"
POWER_PLANTS_SOURCE_PATH = SOURCE_DATA_DIR / "power_plants.geojson"
GEM_WIND_GREECE_SOURCE_PATH = SOURCE_DATA_DIR / "gem_wind_greece.geojson"
GOVERNMENT_WIND_GREECE_SOURCE_PATH = SOURCE_DATA_DIR / "government_wind_greece.geojson"
GEM_SOLAR_GREECE_SOURCE_PATH = SOURCE_DATA_DIR / "gem_solar_greece.geojson"
GOVERNMENT_PV_GREECE_SOURCE_PATH = SOURCE_DATA_DIR / "government_photovoltaics_greece.geojson"
GOVERNMENT_STORAGE_GREECE_SOURCE_PATH = SOURCE_DATA_DIR / "government_storage_greece.geojson"
GEM_HYDRO_GREECE_SOURCE_PATH = SOURCE_DATA_DIR / "gem_hydro_greece.geojson"
PUMPED_HYDRO_SEED_SOURCE_PATH = SOURCE_DATA_DIR / "pumped_hydro_seed.geojson"
RAAEY_FOSSIL_FUEL_SOURCE_PATH = SOURCE_DATA_DIR / "raaey_fossil_fuel_plants.geojson"
BIOMASS_PHASE1_REVIEW_PATH = PROCESSED_DATA_DIR / "raaey_biomass_candidates.json"
GREECE_BOUNDARY_SOURCE_PATH = SOURCE_DATA_DIR / "greece_boundary.geojson"
UNKNOWN_REGION_LABEL = "Unknown"
NULL_TEXT_VALUES = {"", "-", "unknown", "n/a", "na", "none", "null"}
SUSPICIOUS_CAPACITY_MW_THRESHOLD = 2500
HYDRO_TECHNOLOGIES = {"hydro", "small_hydro", "pumped_hydro"}
MERGEABLE_GEM_TECHNOLOGIES = {
    "onshore_wind",
    "offshore_wind",
    "solar_pv",
    "hydro",
    "small_hydro",
    "pumped_hydro",
}
GREEK_LIGNITE_NAME_HINTS = (
    "agios dimitri",
    "πτολεμαιδ",
    "ptolema",
    "kardia",
    "meliti",
    "amyntai",
    "megalop",
    "agioudimitri",
    "ptolemaid",
    "kardia",
    "meliti",
    "amyntai",
    "megalopol",
)
SOURCE_PRIORITY = {
    "Greek Government Wind Registry": 5,
    "Greek Government PV Registry": 5,
    "Greek Government Storage Registry": 5,
    "RAAEY Fossil Fuel Registry": 5,
    "Official Project Sources": 4,
    "Global Energy Monitor": 3,
    "OpenStreetMap": 1,
    "Unknown": 0,
}

RAW_TECHNOLOGY_TO_INTERNAL = [
    (("hydroelectric", "pumped"), "pumped_hydro"),
    (("hydro", "pumped"), "pumped_hydro"),
    (("hydro-pumped", "storage"), "pumped_hydro"),
    (("pumped-storage", "hydro"), "pumped_hydro"),
    (("pumped", "storage", "hydro"), "pumped_hydro"),
    (("pumped-storage",), "pumped_hydro"),
    (("reversible",), "pumped_hydro"),
    (("αντλησιοταμίευση",), "pumped_hydro"),
    (("αντλησιοταμιευτικό",), "pumped_hydro"),
    (("αναστρέψιμο", "υδροηλεκτρικό"), "pumped_hydro"),
    (("hydroelectric", "pumped", "storage"), "pumped_hydro"),
    (("hydro", "pumped", "storage"), "pumped_hydro"),
    (("hydro", "storage"), "pumped_hydro"),
    (("reversible", "hydro"), "pumped_hydro"),
    (("pumping", "hydro"), "pumped_hydro"),
    (("αντλησιοταμίευση",), "pumped_hydro"),
    (("αντλησιοταμιευτικό",), "pumped_hydro"),
    (("αναστρέψιμο", "υδροηλεκτρικό"), "pumped_hydro"),
    (("conventional", "storage"), "hydro"),
    (("pumped-hydro",), "pumped_hydro"),
    (("pumped", "hydro"), "pumped_hydro"),
    (("offshore", "wind"), "offshore_wind"),
    (("onshore", "wind"), "onshore_wind"),
    (("small", "hydro"), "small_hydro"),
    (("pumped", "storage"), "pumped_hydro"),
    (("pumped", "hydro"), "pumped_hydro"),
    (("battery",), "battery_storage"),
    (("bess",), "battery_storage"),
    (("storage",), "battery_storage"),
    (("photovoltaic",), "solar_pv"),
    (("solar",), "solar_pv"),
    (("pv",), "solar_pv"),
    (("wind",), "onshore_wind"),
    (("hydroelectric",), "hydro"),
    (("hydro",), "hydro"),
    (("natural gas",), "gas"),
    (("ccgt",), "gas"),
    (("ocgt",), "gas"),
    (("gas",), "gas"),
    (("brown coal",), "lignite"),
    (("lignite",), "lignite"),
    (("coal",), "coal"),
    (("diesel",), "oil"),
    (("mazut",), "oil"),
    (("oil",), "oil"),
    (("biogas",), "biogas"),
    (("biomass",), "biomass"),
    (("cogeneration",), "chp"),
    (("co-generation",), "chp"),
    (("chp",), "chp"),
    (("geothermal",), "geothermal"),
    (("nuclear",), "unknown"),
]

TECHNOLOGY_TO_CATEGORY = {
    "solar_pv": "Solar",
    "onshore_wind": "Wind",
    "offshore_wind": "Wind",
    "hydro": "Hydro",
    "small_hydro": "Hydro",
    "pumped_hydro": "Storage",
    "battery_storage": "Storage",
    "gas": "Gas",
    "lignite": "Lignite",
    "oil": "Oil",
    "biomass": "Biomass/Biogas",
    "biogas": "Biomass/Biogas",
    "chp": "CHP",
    "geothermal": "Geothermal",
    "coal": "Other/Unknown",
    "unknown": "Other/Unknown",
}

TECHNOLOGY_TO_CARRIER = {
    "solar_pv": "solar",
    "onshore_wind": "wind",
    "offshore_wind": "wind",
    "hydro": "hydro",
    "small_hydro": "hydro",
    "pumped_hydro": "pumped_hydro",
    "gas": "gas",
    "lignite": "lignite",
    "coal": "coal",
    "oil": "oil",
    "biomass": "biomass",
    "biogas": "biogas",
    "chp": "chp",
    "battery_storage": "battery",
    "geothermal": "geothermal",
    "unknown": "unknown",
}

TECHNOLOGY_TO_FUEL = {
    "solar_pv": "solar",
    "onshore_wind": "wind",
    "offshore_wind": "wind",
    "hydro": "water",
    "small_hydro": "water",
    "pumped_hydro": "water",
    "gas": "natural_gas",
    "lignite": "lignite",
    "coal": "coal",
    "oil": "oil",
    "biomass": "biomass",
    "biogas": "biogas",
    "chp": None,
    "battery_storage": "electricity",
    "geothermal": "geothermal",
    "unknown": None,
}

INTERNAL_TECHNOLOGY_LABELS = {
    "solar_pv": "Solar PV",
    "onshore_wind": "Onshore Wind",
    "offshore_wind": "Offshore Wind",
    "hydro": "Hydro",
    "small_hydro": "Small Hydro",
    "pumped_hydro": "Pumped Hydro",
    "gas": "Gas",
    "lignite": "Lignite",
    "coal": "Coal",
    "oil": "Oil",
    "biomass": "Biomass",
    "biogas": "Biogas",
    "chp": "CHP",
    "battery_storage": "Battery Storage",
    "geothermal": "Geothermal",
    "unknown": "Unknown",
}


@lru_cache(maxsize=1)
def load_raw_generators_feature_collection() -> dict:
    with POWER_PLANTS_SOURCE_PATH.open("r", encoding="utf-8") as data_file:
        return json.load(data_file)


@lru_cache(maxsize=1)
def get_generators_feature_collection() -> dict:
    canonical_features = []

    for source_path in get_generator_source_paths():
        raw_feature_collection = load_source_feature_collection(source_path)
        last_seen = get_file_timestamp(source_path)
        for feature in raw_feature_collection.get("features", []):
            canonical_feature = build_canonical_generator_feature(feature, last_seen)
            if should_include_canonical_generator_feature(source_path, canonical_feature):
                canonical_features.append(canonical_feature)

    return {
        "type": "FeatureCollection",
        "features": merge_generator_features(canonical_features),
    }


@lru_cache(maxsize=1)
def get_generators() -> list[dict]:
    return [
        feature_to_generator_record(feature)
        for feature in get_generators_feature_collection()["features"]
    ]


def get_generator_source_paths() -> list[Path]:
    source_paths = [POWER_PLANTS_SOURCE_PATH]

    if GEM_WIND_GREECE_SOURCE_PATH.exists():
        source_paths.append(GEM_WIND_GREECE_SOURCE_PATH)

    if GOVERNMENT_WIND_GREECE_SOURCE_PATH.exists():
        source_paths.append(GOVERNMENT_WIND_GREECE_SOURCE_PATH)

    if GEM_SOLAR_GREECE_SOURCE_PATH.exists():
        source_paths.append(GEM_SOLAR_GREECE_SOURCE_PATH)

    if GOVERNMENT_PV_GREECE_SOURCE_PATH.exists():
        source_paths.append(GOVERNMENT_PV_GREECE_SOURCE_PATH)

    if GOVERNMENT_STORAGE_GREECE_SOURCE_PATH.exists():
        source_paths.append(GOVERNMENT_STORAGE_GREECE_SOURCE_PATH)

    if GEM_HYDRO_GREECE_SOURCE_PATH.exists():
        source_paths.append(GEM_HYDRO_GREECE_SOURCE_PATH)

    if PUMPED_HYDRO_SEED_SOURCE_PATH.exists():
        source_paths.append(PUMPED_HYDRO_SEED_SOURCE_PATH)

    if RAAEY_FOSSIL_FUEL_SOURCE_PATH.exists():
        source_paths.append(RAAEY_FOSSIL_FUEL_SOURCE_PATH)

    if BIOMASS_PHASE1_REVIEW_PATH.exists():
        source_paths.append(BIOMASS_PHASE1_REVIEW_PATH)

    return source_paths


def load_source_feature_collection(source_path: Path) -> dict:
    with source_path.open("r", encoding="utf-8") as data_file:
        payload = json.load(data_file)

    if isinstance(payload, dict) and payload.get("type") == "FeatureCollection":
        return payload

    if isinstance(payload, list):
        return {
            "type": "FeatureCollection",
            "features": [
                generator_record_to_feature(record)
                for record in payload
                if isinstance(record, dict)
            ],
        }

    raise ValueError(f"Unsupported generator source payload in {source_path}")


def generator_record_to_feature(record: dict) -> dict:
    geometry = record.get("geometry")
    properties = {key: value for key, value in record.items() if key != "geometry"}
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": geometry,
    }


def get_generators_summary_by_technology() -> list[dict]:
    grouped: dict[str, dict] = {}

    for generator in get_generators():
        if not include_generator_in_summary(generator):
            continue

        category = generator["technology_category"]
        summary = grouped.setdefault(
            category,
            {
                "technology_category": category,
                "count_assets": 0,
                "total_nominal_capacity_mw": 0.0,
                "count_missing_capacity": 0,
                "count_missing_coordinates": 0,
            },
        )
        summary["count_assets"] += 1

        nominal_capacity = generator["nominal_capacity_mw"]
        if nominal_capacity is None:
            summary["count_missing_capacity"] += 1
        else:
            summary["total_nominal_capacity_mw"] = round(
                summary["total_nominal_capacity_mw"] + nominal_capacity,
                3,
            )

        if generator["latitude"] is None or generator["longitude"] is None:
            summary["count_missing_coordinates"] += 1

    return sorted(
        grouped.values(),
        key=lambda item: (-item["total_nominal_capacity_mw"], item["technology_category"]),
    )


def get_generators_summary_by_region() -> list[dict]:
    grouped: dict[str, dict] = {}

    for generator in get_generators():
        if not include_generator_in_summary(generator):
            continue

        region_name = (
            text_or_none(generator.get("regional_unit"))
            or text_or_none(generator.get("region"))
            or text_or_none(generator.get("municipality"))
            or UNKNOWN_REGION_LABEL
        )
        summary = grouped.setdefault(
            region_name,
            {
                "region": region_name,
                "count_assets": 0,
                "total_nominal_capacity_mw": 0.0,
                "count_missing_capacity": 0,
                "count_missing_coordinates": 0,
            },
        )
        summary["count_assets"] += 1

        nominal_capacity = generator["nominal_capacity_mw"]
        if nominal_capacity is None:
            summary["count_missing_capacity"] += 1
        else:
            summary["total_nominal_capacity_mw"] = round(
                summary["total_nominal_capacity_mw"] + nominal_capacity,
                3,
            )

        if generator["latitude"] is None or generator["longitude"] is None:
            summary["count_missing_coordinates"] += 1

    return sorted(
        grouped.values(),
        key=lambda item: (-item["total_nominal_capacity_mw"], item["region"]),
    )


def get_generators_missing_capacity() -> dict:
    missing_assets = [
        summarize_generator_issue(generator)
        for generator in get_generators()
        if generator["nominal_capacity_mw"] is None
    ]

    return {
        "count": len(missing_assets),
        "assets": missing_assets,
    }


def get_generators_missing_technology() -> dict:
    missing_assets = [
        summarize_generator_issue(generator)
        for generator in get_generators()
        if generator["technology"] == "unknown"
    ]

    return {
        "count": len(missing_assets),
        "assets": missing_assets,
    }


def get_generators_missing_coordinates() -> dict:
    missing_assets = [
        summarize_generator_issue(generator)
        for generator in get_generators()
        if generator["latitude"] is None or generator["longitude"] is None
    ]

    return {
        "count": len(missing_assets),
        "assets": missing_assets,
    }


def get_generators_duplicates() -> dict:
    duplicate_items = detect_possible_duplicates(get_generators())

    return {
        "count": len(duplicate_items),
        "possible_duplicates": duplicate_items,
    }


def get_generators_sources_coverage() -> dict:
    generators = get_generators()
    grouped: dict[str, dict] = {}

    for generator in generators:
        source_name = generator["primary_source"] or "Unknown"
        source_summary = grouped.setdefault(
            source_name,
            {
                "primary_source": source_name,
                "count_assets": 0,
                "count_with_nominal_capacity": 0,
                "count_with_operator": 0,
                "count_with_coordinates": 0,
                "count_with_source_refs": 0,
            },
        )
        source_summary["count_assets"] += 1

        if generator["nominal_capacity_mw"] is not None:
            source_summary["count_with_nominal_capacity"] += 1

        if text_or_none(generator.get("operator")):
            source_summary["count_with_operator"] += 1

        if generator["latitude"] is not None and generator["longitude"] is not None:
            source_summary["count_with_coordinates"] += 1

        if generator["source_refs"]:
            source_summary["count_with_source_refs"] += 1

    return {
        "total_assets": len(generators),
        "sources": sorted(
            grouped.values(),
            key=lambda item: (-item["count_assets"], item["primary_source"]),
        ),
    }


def get_generators_pypsa_export() -> dict:
    exports = [
        {
            "id": generator["id"],
            "name": generator["name"],
            "pypsa_bus": generator["pypsa_bus"],
            "carrier": generator["carrier"],
            "p_nom": generator["nominal_capacity_mw"],
            "p_nom_pump": generator.get("pumping_capacity_mw"),
            "generation_capacity_mw": generator.get("generation_capacity_mw"),
            "pumping_capacity_mw": generator.get("pumping_capacity_mw"),
            "max_hours": get_storage_duration_hours(generator),
            "technology_category": generator["technology_category"],
            "source": generator["primary_source"],
            "confidence": generator["source_confidence"],
            "source_refs": generator.get("source_refs"),
            "latitude": generator.get("latitude"),
            "longitude": generator.get("longitude"),
            "status_category": generator.get("status_category"),
            "region": generator.get("region"),
        }
        for generator in get_generators()
    ]

    missing_pypsa_bus = sum(
        1 for generator in exports if not text_or_none(generator["pypsa_bus"])
    )

    return {
        "total_assets": len(exports),
        "count_missing_pypsa_bus": missing_pypsa_bus,
        "generators": exports,
    }


def get_generators_summary_storage() -> dict:
    storage_generators = [
        generator
        for generator in get_generators()
        if generator.get("technology_category") == "Storage"
        and include_generator_in_summary(generator)
    ]

    total_generation_capacity = round(
        sum((generator.get("generation_capacity_mw") or generator.get("nominal_capacity_mw") or 0) for generator in storage_generators),
        3,
    )
    total_pumping_capacity = round(
        sum((generator.get("pumping_capacity_mw") or 0) for generator in storage_generators),
        3,
    )

    return {
        "technology_category": "Storage",
        "count_assets": len(storage_generators),
        "total_generation_capacity_mw": total_generation_capacity,
        "total_pumping_capacity_mw": total_pumping_capacity,
        "count_missing_generation_capacity": sum(
            1
            for generator in storage_generators
            if generator.get("generation_capacity_mw") is None
            and generator.get("nominal_capacity_mw") is None
        ),
        "count_missing_pumping_capacity": sum(
            1 for generator in storage_generators if generator.get("pumping_capacity_mw") is None
        ),
    }


def get_generators_quality_storage() -> dict:
    storage_generators = [
        generator for generator in get_generators() if generator.get("technology_category") == "Storage"
    ]
    storage_asset_ids = {generator["id"] for generator in storage_generators}
    storage_duplicates = [
        duplicate
        for duplicate in detect_possible_duplicates(get_generators())
        if any(asset_id in storage_asset_ids for asset_id in duplicate["asset_ids"])
    ]

    return {
        "total_assets": len(storage_generators),
        "total_generation_capacity_mw": round(
            sum((generator.get("generation_capacity_mw") or generator.get("nominal_capacity_mw") or 0) for generator in storage_generators),
            3,
        ),
        "total_pumping_capacity_mw": round(
            sum((generator.get("pumping_capacity_mw") or 0) for generator in storage_generators),
            3,
        ),
        "missing_generation_capacity": summarize_storage_issues(
            storage_generators,
            lambda generator: generator.get("generation_capacity_mw") is None
            and generator.get("nominal_capacity_mw") is None,
        ),
        "missing_pumping_capacity": summarize_storage_issues(
            storage_generators,
            lambda generator: generator.get("pumping_capacity_mw") is None,
        ),
        "missing_geometry": summarize_storage_issues(
            storage_generators,
            lambda generator: generator.get("latitude") is None or generator.get("longitude") is None,
        ),
        "missing_source_refs": summarize_storage_issues(
            storage_generators,
            lambda generator: len(generator.get("source_refs") or []) == 0,
        ),
        "possible_duplicates": {
            "count": len(storage_duplicates),
            "possible_duplicates": storage_duplicates,
        },
    }


def get_generators_quality_pumped_hydro() -> dict:
    pumped_hydro_generators = [
        generator for generator in get_generators() if generator.get("technology") == "pumped_hydro"
    ]
    hydro_generators = [
        generator for generator in get_generators() if generator.get("technology") in {"hydro", "small_hydro"}
    ]

    return {
        "total_assets": len(pumped_hydro_generators),
        "total_generation_capacity_mw": round(
            sum((generator.get("generation_capacity_mw") or generator.get("nominal_capacity_mw") or 0) for generator in pumped_hydro_generators),
            3,
        ),
        "total_pumping_capacity_mw": round(
            sum((generator.get("pumping_capacity_mw") or 0) for generator in pumped_hydro_generators),
            3,
        ),
        "assets_missing_generation_capacity": summarize_storage_issues(
            pumped_hydro_generators,
            lambda generator: generator.get("generation_capacity_mw") is None
            and generator.get("nominal_capacity_mw") is None,
        ),
        "assets_missing_pumping_capacity": summarize_storage_issues(
            pumped_hydro_generators,
            lambda generator: generator.get("pumping_capacity_mw") is None,
        ),
        "assets_missing_geometry": summarize_storage_issues(
            pumped_hydro_generators,
            lambda generator: generator.get("latitude") is None or generator.get("longitude") is None,
        ),
        "assets_missing_source_refs": summarize_storage_issues(
            pumped_hydro_generators,
            lambda generator: len(generator.get("source_refs") or []) == 0,
        ),
        "assets_with_invalid_category": summarize_storage_issues(
            pumped_hydro_generators,
            lambda generator: generator.get("technology_category") != "Storage",
        ),
        "assets_with_invalid_carrier": summarize_storage_issues(
            pumped_hydro_generators,
            lambda generator: generator.get("carrier") != "pumped_hydro",
        ),
        "assets_missing_generation_with_pumping": summarize_storage_issues(
            pumped_hydro_generators,
            lambda generator: generator.get("pumping_capacity_mw") is not None
            and generator.get("generation_capacity_mw") is None
            and generator.get("nominal_capacity_mw") is None,
        ),
        "assets_nominal_equals_pumping_while_generation_differs": summarize_storage_issues(
            pumped_hydro_generators,
            lambda generator: generator.get("nominal_capacity_mw") is not None
            and generator.get("pumping_capacity_mw") is not None
            and generator.get("generation_capacity_mw") is not None
            and generator.get("nominal_capacity_mw") == generator.get("pumping_capacity_mw")
            and generator.get("generation_capacity_mw") != generator.get("pumping_capacity_mw"),
        ),
        "assets_name_suggests_pumped_hydro_but_classified_otherwise": [
            summarize_generator_issue(generator)
            for generator in hydro_generators
            if looks_like_pumped_hydro(generator)
        ],
        "assets_classified_as_pumped_hydro_but_may_be_normal_hydro": [
            summarize_generator_issue(generator)
            for generator in pumped_hydro_generators
            if may_be_normal_hydro(generator)
        ],
    }


def get_generators_quality_report() -> dict:
    generators = get_generators()
    duplicates = detect_possible_duplicates(generators)
    missing_capacity = get_generators_missing_capacity()
    missing_technology = get_generators_missing_technology()
    missing_coordinates = get_generators_missing_coordinates()

    technology_breakdown: dict[str, int] = defaultdict(int)
    capacity_by_technology: dict[str, float] = defaultdict(float)
    source_breakdown: dict[str, int] = defaultdict(int)

    for generator in generators:
        technology_breakdown[generator["technology_category"]] += 1
        source_breakdown[generator["primary_source"] or "Unknown"] += 1

        if generator["nominal_capacity_mw"] is not None:
            capacity_by_technology[generator["technology_category"]] += generator[
                "nominal_capacity_mw"
            ]

    capacity_conflicts = [
        item for item in duplicates if "capacity_conflict" in item["reasons"]
    ]
    technology_conflicts = [
        item for item in duplicates if "technology_conflict" in item["reasons"]
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_assets": len(generators),
        "technology_breakdown": [
            {"technology_category": category, "count_assets": count}
            for category, count in sorted(
                technology_breakdown.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ],
        "total_nominal_capacity_by_technology": [
            {
                "technology_category": category,
                "total_nominal_capacity_mw": round(total_capacity, 3),
            }
            for category, total_capacity in sorted(
                capacity_by_technology.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ],
        "missing_capacity": build_quality_stat(missing_capacity["count"], len(generators)),
        "missing_technology": build_quality_stat(
            missing_technology["count"],
            len(generators),
        ),
        "missing_coordinates": build_quality_stat(
            missing_coordinates["count"],
            len(generators),
        ),
        "possible_duplicates": {
            "count": len(duplicates),
            "items": duplicates,
        },
        "capacity_conflicts": {
            "count": len(capacity_conflicts),
            "items": capacity_conflicts,
        },
        "technology_conflicts": {
            "count": len(technology_conflicts),
            "items": technology_conflicts,
        },
        "source_breakdown": [
            {"primary_source": source_name, "count_assets": count}
            for source_name, count in sorted(
                source_breakdown.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ],
        "pypsa_missing_bus": build_quality_stat(
            sum(1 for generator in generators if not text_or_none(generator.get("pypsa_bus"))),
            len(generators),
        ),
        "storage_summary": get_generators_summary_storage(),
        "pumped_hydro_quality": get_generators_quality_pumped_hydro(),
    }


def include_generator_in_summary(generator: dict) -> bool:
    return generator.get("count_in_summary", True) is not False


def get_storage_duration_hours(generator: dict) -> float | None:
    explicit_duration = normalize_optional_number(generator.get("storage_duration_hours"))
    if explicit_duration is not None:
        return round(float(explicit_duration), 3)

    energy_capacity = normalize_optional_number(generator.get("energy_capacity_mwh"))
    generation_capacity = normalize_optional_number(
        generator.get("generation_capacity_mw") or generator.get("nominal_capacity_mw")
    )
    if energy_capacity is None or generation_capacity in {None, 0}:
        return None

    return round(float(energy_capacity) / float(generation_capacity), 3)


def summarize_storage_issues(
    generators: list[dict],
    predicate,
) -> dict:
    issues = [summarize_generator_issue(generator) for generator in generators if predicate(generator)]
    return {"count": len(issues), "assets": issues}


def looks_like_pumped_hydro(generator: dict) -> bool:
    text_fields = [
        generator.get("name"),
        generator.get("project_name"),
        generator.get("other_names"),
        generator.get("technology_type"),
        generator.get("raw_technology"),
    ]
    normalized_text = " ".join(
        str(value).strip().casefold() for value in text_fields if text_or_none(value)
    )

    return any(
        hint in normalized_text
        for hint in [
            "pumped",
            "storage",
            "reversible",
            "αντλησιοταμίευση",
            "αντλησιοταμιευ",
            "αναστρέψιμο",
        ]
    )


def may_be_normal_hydro(generator: dict) -> bool:
    if generator.get("technology") != "pumped_hydro":
        return False

    normalized_text = " ".join(
        str(value).strip().casefold()
        for value in [
            generator.get("name"),
            generator.get("project_name"),
            generator.get("other_names"),
            generator.get("technology_type"),
            generator.get("raw_technology"),
        ]
        if text_or_none(value)
    )

    if any(
        hint in normalized_text
        for hint in ["pumped", "storage", "reversible", "αντλησιοταμίευ", "αναστρέψιμο"]
    ):
        return False

    return generator.get("pumping_capacity_mw") is None


def get_generator_capacity_fields(properties: dict, technology: str) -> dict:
    nominal_keys = [
        "nominal_capacity_mw",
        "capacity_mw",
        "capacity",
        "capacity_nominal",
        "installed_capacity_mw",
        "plant_output_electricity",
        "generator_output_electricity",
        "output_electricity",
        "total_project_capacity_mw",
    ]
    generation_keys = [
        "generation_capacity_mw",
        "turbine_capacity_mw",
        "production_capacity_mw",
        "drawing_capacity_mw",
        "generation_capacity",
        "turbine_capacity",
        "production_capacity",
        "drawing_capacity",
    ]
    pumping_keys = [
        "pumping_capacity_mw",
        "pump_capacity_mw",
        "absorbed_capacity_mw",
        "charging_capacity_mw",
        "pumping_capacity",
        "pump_capacity",
        "absorbed_capacity",
        "charging_capacity",
    ]

    nominal_result = get_capacity_field(properties, nominal_keys)
    generation_result = get_capacity_field(properties, generation_keys)
    pumping_result = get_capacity_field(properties, pumping_keys)
    energy_result = parse_energy_to_mwh(
        first_present_value(
            properties,
            [
                "energy_capacity_mwh",
                "storage_capacity_mwh",
                "usable_energy_capacity_mwh",
            ],
        )
    )

    nominal_capacity_mw = nominal_result["value_mw"]
    generation_capacity_mw = generation_result["value_mw"]
    pumping_capacity_mw = pumping_result["value_mw"]
    warnings = [
        *nominal_result["warnings"],
        *generation_result["warnings"],
        *pumping_result["warnings"],
        *energy_result["warnings"],
    ]

    if technology == "pumped_hydro":
        if generation_capacity_mw is None:
            generation_capacity_mw = nominal_capacity_mw
        if nominal_capacity_mw is None:
            nominal_capacity_mw = generation_capacity_mw
    else:
        if nominal_capacity_mw is None:
            nominal_capacity_mw = generation_capacity_mw
        if generation_capacity_mw is None:
            generation_capacity_mw = nominal_capacity_mw

    round_trip_efficiency = normalize_efficiency_value(
        first_present_value(
            properties,
            ["round_trip_efficiency", "roundtrip_efficiency", "efficiency_round_trip"],
        )
    )
    storage_duration_hours = normalize_optional_number(
        first_present_value(properties, ["storage_duration_hours", "duration_hours"])
    )
    if storage_duration_hours is None and energy_result["value_mwh"] is not None and generation_capacity_mw not in {None, 0}:
        storage_duration_hours = round(
            float(energy_result["value_mwh"]) / float(generation_capacity_mw),
            3,
        )

    return {
        "capacity_mw": nominal_capacity_mw,
        "nominal_capacity_mw": nominal_capacity_mw,
        "generation_capacity_mw": generation_capacity_mw,
        "pumping_capacity_mw": pumping_capacity_mw,
        "energy_capacity_mwh": energy_result["value_mwh"],
        "storage_duration_hours": storage_duration_hours,
        "round_trip_efficiency": round_trip_efficiency,
        "warnings": unique_list(warnings),
    }


def get_capacity_field(properties: dict, keys: list[str]) -> dict:
    raw_value = first_present_value(properties, keys)
    result = parse_capacity_to_mw(raw_value)
    return {
        "raw_value": raw_value,
        "value_mw": result["value_mw"],
        "warnings": result["warnings"],
    }


def parse_energy_to_mwh(raw_value: object) -> dict:
    warnings: list[str] = []
    if raw_value is None:
        return {"value_mwh": None, "warnings": warnings}

    if isinstance(raw_value, (int, float)):
        numeric_value = float(raw_value)
        if numeric_value < 0:
            warnings.append("negative_energy_capacity")
            return {"value_mwh": None, "warnings": warnings}
        return {"value_mwh": round(numeric_value, 3), "warnings": warnings}

    text_value = str(raw_value).strip()
    if text_value.lower() in NULL_TEXT_VALUES:
        return {"value_mwh": None, "warnings": warnings}

    numeric_match = re.search(
        r"(-?\d[\d\s.,]*)\s*(gwh|mwh|kwh)?",
        text_value,
        flags=re.IGNORECASE,
    )
    if not numeric_match:
        warnings.append("unparsed_energy_capacity")
        return {"value_mwh": None, "warnings": warnings}

    normalized_number = normalize_numeric_token(numeric_match.group(1))
    if normalized_number is None:
        warnings.append("unparsed_energy_capacity")
        return {"value_mwh": None, "warnings": warnings}

    if normalized_number["ambiguous"]:
        warnings.append("ambiguous_energy_capacity_separator")

    numeric_value = normalized_number["value"]
    unit = (numeric_match.group(2) or "mwh").lower()
    if numeric_value < 0:
        warnings.append("negative_energy_capacity")
        return {"value_mwh": None, "warnings": warnings}

    if unit == "gwh":
        value_mwh = numeric_value * 1000
    elif unit == "kwh":
        value_mwh = numeric_value / 1000
    else:
        value_mwh = numeric_value

    return {"value_mwh": round(value_mwh, 3), "warnings": warnings}


def normalize_efficiency_value(raw_value: object) -> float | None:
    if raw_value is None:
        return None

    if isinstance(raw_value, (int, float)):
        numeric_value = float(raw_value)
    else:
        text_value = str(raw_value).strip().replace("%", "")
        parsed_value = normalize_numeric_token(text_value)
        if parsed_value is None:
            return None
        numeric_value = float(parsed_value["value"])

    if numeric_value <= 0:
        return None

    if numeric_value > 1:
        if numeric_value <= 100:
            numeric_value = numeric_value / 100
        else:
            return None

    return round(numeric_value, 4)


def build_canonical_generator_feature(
    feature: dict,
    last_seen: str,
) -> dict:
    properties = feature.get("properties", {}) or {}
    geometry = feature.get("geometry")
    longitude, latitude = get_point_coordinates(geometry, properties)
    raw_technology = first_present_value(
        properties,
        [
            "technology",
            "technology_type",
            "fuel",
            "carrier",
            "plant_source",
            "source",
        ],
    )
    normalized_technology = refine_generator_technology(
        normalize_generator_technology(raw_technology),
        properties,
    )
    technology_category = map_technology_category(normalized_technology)
    capacity_fields = get_generator_capacity_fields(properties, normalized_technology)
    source_refs = get_source_refs(properties)
    notes = listify(properties.get("notes")) + capacity_fields["warnings"][:]
    notes.extend(
        get_generator_quality_notes(
            properties,
            normalized_technology,
            capacity_fields["nominal_capacity_mw"],
        )
    )

    capacity_mw = capacity_fields["capacity_mw"]
    nominal_capacity_mw = capacity_fields["nominal_capacity_mw"]
    generation_capacity_mw = capacity_fields["generation_capacity_mw"]
    pumping_capacity_mw = capacity_fields["pumping_capacity_mw"]
    energy_capacity_mwh = capacity_fields["energy_capacity_mwh"]
    storage_duration_hours = capacity_fields["storage_duration_hours"]
    round_trip_efficiency = capacity_fields["round_trip_efficiency"]

    canonical_properties = {
        "id": str(properties.get("id") or build_fallback_id(properties)),
        "name": get_generator_name(properties),
        "operator": normalize_missing_text(properties.get("operator")),
        "technology": normalized_technology,
        "technology_label": INTERNAL_TECHNOLOGY_LABELS[normalized_technology],
        "technology_category": technology_category,
        "carrier": get_generator_carrier(normalized_technology),
        "fuel": get_generator_fuel(properties, normalized_technology),
        "capacity_mw": capacity_mw,
        "nominal_capacity_mw": nominal_capacity_mw,
        "generation_capacity_mw": generation_capacity_mw,
        "pumping_capacity_mw": pumping_capacity_mw,
        "energy_capacity_mwh": energy_capacity_mwh,
        "storage_duration_hours": storage_duration_hours,
        "round_trip_efficiency": round_trip_efficiency,
        "capacity_unit": "MW" if nominal_capacity_mw is not None else None,
        "capacity_type": "nominal" if nominal_capacity_mw is not None else None,
        "status": normalize_status(properties.get("status")),
        "status_category": infer_status_category(properties),
        "license_id": normalize_missing_text(properties.get("license_id")),
        "application_code": normalize_missing_text(properties.get("application_code")),
        "government_registry_id": normalize_missing_text(
            properties.get("government_registry_id")
        ),
        "source_record_id": normalize_missing_text(properties.get("source_record_id")),
        "source": infer_primary_source(properties),
        "primary_source": infer_primary_source(properties),
        "source_confidence": get_source_confidence(
            properties,
            normalized_technology,
            nominal_capacity_mw,
            longitude,
            latitude,
            notes,
        ),
        "confidence_score": get_source_confidence(
            properties,
            normalized_technology,
            nominal_capacity_mw,
            longitude,
            latitude,
            notes,
        ),
        "source_refs": source_refs,
        "raw_sources": [
            {
                "source": infer_primary_source(properties),
                "raw_technology": raw_technology,
                "raw_capacity": first_present_value(
                    properties,
                    [
                        "nominal_capacity_mw",
                        "capacity_mw",
                        "capacity",
                        "capacity_nominal",
                        "plant_output_electricity",
                        "generator_output_electricity",
                        "output_electricity",
                    ],
                ),
                "raw_status": properties.get("status"),
                "raw_status_category": properties.get("status_category"),
                "osm_type": properties.get("osm_type"),
                "osm_id": properties.get("osm_id"),
            }
        ],
        "latitude": latitude,
        "longitude": longitude,
        "region": normalize_missing_text(properties.get("region")),
        "regional_unit": normalize_missing_text(properties.get("regional_unit")),
        "municipality": normalize_missing_text(properties.get("municipality")),
        "connection_level": normalize_missing_text(properties.get("connection_level")),
        "voltage_kv": normalize_optional_number(properties.get("voltage_kv")),
        "grid_operator": normalize_missing_text(properties.get("grid_operator")),
        "nearest_substation_id": normalize_missing_text(
            properties.get("nearest_substation_id")
        ),
        "pypsa_bus": normalize_missing_text(properties.get("pypsa_bus")),
        "commissioning_year": normalize_year(properties.get("commissioning_year")),
        "decommissioning_year": normalize_year(properties.get("decommissioning_year")),
        "last_seen": normalize_missing_text(properties.get("last_seen")) or last_seen,
        "last_updated": normalize_missing_text(properties.get("last_updated")) or last_seen,
        "notes": notes or None,
        "operator_original": properties.get("operator"),
        "raw_name": properties.get("name"),
        "project_name": normalize_missing_text(properties.get("project_name")),
        "phase_name": normalize_missing_text(properties.get("phase_name")),
        "owner": normalize_missing_text(properties.get("owner")),
        "developer": normalize_missing_text(properties.get("developer")),
        "local_name": normalize_missing_text(properties.get("local_name")),
        "other_names": normalize_missing_text(properties.get("other_names")),
        "installation_type": normalize_missing_text(properties.get("installation_type")),
        "capacity_rating": normalize_missing_text(properties.get("capacity_rating")),
        "technology_type": normalize_missing_text(properties.get("technology_type")),
        "location_accuracy": normalize_missing_text(properties.get("location_accuracy")),
        "major_area": normalize_missing_text(properties.get("major_area")),
        "subregion": normalize_missing_text(properties.get("subregion")),
        "global_region": normalize_missing_text(properties.get("global_region")),
        "country": normalize_missing_text(properties.get("country")),
        "country_role": normalize_missing_text(properties.get("country_role")),
        "site_name": normalize_missing_text(properties.get("site_name")),
        "binational": properties.get("binational"),
        "complex": normalize_missing_text(properties.get("complex")),
        "turbines": normalize_optional_number(properties.get("turbines")),
        "river_watercourse": normalize_missing_text(properties.get("river_watercourse")),
        "upper_reservoir": normalize_missing_text(properties.get("upper_reservoir")),
        "lower_reservoir": normalize_missing_text(properties.get("lower_reservoir")),
        "reservoir_system": normalize_missing_text(properties.get("reservoir_system")),
        "reversible_units": normalize_optional_number(properties.get("reversible_units")),
        "annual_generation_gwh": normalize_optional_number(
            properties.get("annual_generation_gwh")
        ),
        "country_1": normalize_missing_text(properties.get("country_1")),
        "country_2": normalize_missing_text(properties.get("country_2")),
        "country_1_capacity_mw": normalize_optional_number(
            properties.get("country_1_capacity_mw")
        ),
        "country_2_capacity_mw": normalize_optional_number(
            properties.get("country_2_capacity_mw")
        ),
        "total_project_capacity_mw": normalize_optional_number(
            properties.get("total_project_capacity_mw")
        ),
        "source_dataset": normalize_missing_text(properties.get("source_dataset")),
        "source_license": normalize_missing_text(properties.get("source_license")),
        "gem_location_id": normalize_missing_text(properties.get("gem_location_id")),
        "gem_phase_id": normalize_missing_text(properties.get("gem_phase_id")),
        "other_ids_location": normalize_missing_text(properties.get("other_ids_location")),
        "other_ids_phase": normalize_missing_text(properties.get("other_ids_phase")),
        "wiki_url": normalize_missing_text(properties.get("wiki_url")),
        "threshold_bucket": normalize_missing_text(properties.get("threshold_bucket")),
        "is_aggregated_record": bool(properties.get("is_aggregated_record")),
        "count_in_summary": properties.get("count_in_summary", True),
        "display_on_map": properties.get("display_on_map", True),
        "parent_project_name": normalize_missing_text(properties.get("parent_project_name")),
        "raw_technology": raw_technology,
        "osm_type": properties.get("osm_type"),
        "osm_id": properties.get("osm_id"),
    }

    return {
        "type": "Feature",
        "properties": canonical_properties,
        "geometry": geometry,
    }


def should_include_canonical_generator_feature(
    source_path: Path,
    canonical_feature: dict,
) -> bool:
    if source_path != POWER_PLANTS_SOURCE_PATH:
        return True

    properties = canonical_feature.get("properties", {})
    if properties.get("primary_source") != "OpenStreetMap":
        return True

    return is_generator_feature_in_greece(canonical_feature)


def refine_generator_technology(
    normalized_technology: str,
    properties: dict,
) -> str:
    if normalized_technology != "coal":
        return normalized_technology

    name_haystack = build_lignite_hint_text(properties)

    if any(hint in name_haystack for hint in GREEK_LIGNITE_NAME_HINTS):
        return "lignite"

    return normalized_technology


def build_lignite_hint_text(properties: dict) -> str:
    raw_text = " ".join(
        str(properties.get(key, ""))
        for key in ["name", "project_name", "site_name", "operator", "owner"]
    ).lower()

    transliterated = (
        raw_text.replace("αι", "ai")
        .replace("ει", "ei")
        .replace("οι", "oi")
        .replace("ου", "ou")
        .replace("γγ", "ng")
        .replace("γκ", "gk")
        .replace("γξ", "nx")
        .replace("γχ", "nch")
        .replace("τσ", "ts")
        .replace("τζ", "tz")
        .replace("θ", "th")
        .replace("χ", "ch")
        .replace("ψ", "ps")
        .replace("ξ", "x")
    )

    greek_character_map = str.maketrans(
        {
            "α": "a",
            "β": "v",
            "γ": "g",
            "δ": "d",
            "ε": "e",
            "ζ": "z",
            "η": "i",
            "ι": "i",
            "κ": "k",
            "λ": "l",
            "μ": "m",
            "ν": "n",
            "ο": "o",
            "π": "p",
            "ρ": "r",
            "σ": "s",
            "ς": "s",
            "τ": "t",
            "υ": "y",
            "φ": "f",
            "ω": "o",
            "ά": "a",
            "έ": "e",
            "ή": "i",
            "ί": "i",
            "ό": "o",
            "ύ": "y",
            "ώ": "o",
            "ϊ": "i",
            "ΐ": "i",
            "ϋ": "y",
            "ΰ": "y",
        }
    )

    return re.sub(
        r"[^a-z0-9]+",
        "",
        transliterated.translate(greek_character_map),
    )


def feature_to_generator_record(feature: dict) -> dict:
    generator = dict(feature.get("properties", {}))
    generator["geometry"] = feature.get("geometry")
    return generator


def merge_generator_features(features: list[dict]) -> list[dict]:
    gem_features = [
        feature
        for feature in features
        if feature.get("properties", {}).get("primary_source") == "Global Energy Monitor"
    ]
    other_features = [
        feature
        for feature in features
        if feature.get("properties", {}).get("primary_source") != "Global Energy Monitor"
    ]

    merged_features = dedupe_gem_features([copy_feature(feature) for feature in gem_features])
    mergeable_indexes = build_mergeable_feature_indexes(merged_features)
    has_gem_hydro_source = any(
        feature.get("properties", {}).get("source_dataset")
        == "Global Hydropower Tracker, March 2026 release"
        for feature in merged_features
    )

    for feature in other_features:
        properties = feature.get("properties", {})
        if properties.get("technology") not in MERGEABLE_GEM_TECHNOLOGIES:
            merged_features.append(copy_feature(feature))
            continue

        match_index = find_matching_mergeable_feature(
            merged_features,
            mergeable_indexes,
            feature,
        )
        if match_index is None:
            if should_keep_unmatched_osm_feature(feature, has_gem_hydro_source):
                merged_features.append(copy_feature(feature))
                register_mergeable_feature_indexes(
                    merged_features[-1],
                    len(merged_features) - 1,
                    mergeable_indexes,
                )
            continue

        merged_features[match_index] = merge_feature_pair(
            merged_features[match_index],
            feature,
        )
        register_mergeable_feature_indexes(
            merged_features[match_index],
            match_index,
            mergeable_indexes,
        )

    return sorted(
        merged_features,
        key=lambda feature: (
            feature.get("properties", {}).get("name") or "",
            feature.get("properties", {}).get("id") or "",
        ),
    )


def dedupe_gem_features(features: list[dict]) -> list[dict]:
    deduped_features: list[dict] = []
    duplicate_indexes = {
        "phase": {},
        "exact": {},
        "name": defaultdict(set),
        "bucket": defaultdict(set),
    }

    for feature in features:
        match_index = find_duplicate_gem_feature(
            deduped_features,
            feature,
            duplicate_indexes,
        )
        if match_index is None:
            deduped_feature = copy_feature(feature)
            deduped_features.append(deduped_feature)
            new_index = len(deduped_features) - 1
            register_duplicate_indexes(deduped_feature, new_index, duplicate_indexes)
            continue

        deduped_features[match_index] = merge_same_source_features(
            deduped_features[match_index],
            feature,
        )
        register_duplicate_indexes(deduped_features[match_index], match_index, duplicate_indexes)

    return deduped_features


def find_duplicate_gem_feature(
    existing_features: list[dict],
    candidate_feature: dict,
    duplicate_indexes: dict[str, dict],
) -> int | None:
    candidate_properties = candidate_feature.get("properties", {})
    for phase_identifier in get_phase_identifiers(candidate_properties):
        if phase_identifier in duplicate_indexes["phase"]:
            return duplicate_indexes["phase"][phase_identifier]

    exact_key = build_exact_duplicate_key(candidate_properties)
    if exact_key is not None and exact_key in duplicate_indexes["exact"]:
        return duplicate_indexes["exact"][exact_key]

    candidate_name = normalize_text(candidate_properties.get("name"))
    candidate_operator = normalize_text(candidate_properties.get("operator"))
    candidate_indices: set[int] = set()

    if candidate_name:
        candidate_indices.update(duplicate_indexes["name"].get(candidate_name, set()))

    candidate_indices.update(
        get_candidate_bucket_indices(
            duplicate_indexes["bucket"],
            candidate_properties.get("latitude"),
            candidate_properties.get("longitude"),
        )
    )

    for index in candidate_indices:
        existing_feature = existing_features[index]
        existing_properties = existing_feature.get("properties", {})
        existing_name = normalize_text(existing_properties.get("name"))
        existing_operator = normalize_text(existing_properties.get("operator"))

        if not candidate_name or not existing_name or not names_match_loose(candidate_name, existing_name):
            continue

        distance_km = get_distance_km(
            candidate_properties.get("latitude"),
            candidate_properties.get("longitude"),
            existing_properties.get("latitude"),
            existing_properties.get("longitude"),
        )
        capacities_match = capacities_within_tolerance(
            candidate_properties.get("nominal_capacity_mw"),
            existing_properties.get("nominal_capacity_mw"),
        )
        operators_match = (
            candidate_operator == existing_operator
            or not candidate_operator
            or not existing_operator
        )

        if (
            distance_km is not None
            and distance_km <= 0.35
            and capacities_match
            and operators_match
        ):
            return index

    return None


def build_exact_duplicate_key(properties: dict) -> tuple | None:
    normalized_name = normalize_text(
        properties.get("project_name") or properties.get("phase_name") or properties.get("name")
    )
    normalized_operator = normalize_text(properties.get("operator") or properties.get("owner"))
    technology = text_or_none(properties.get("technology"))
    nominal_capacity_mw = normalize_optional_number(properties.get("nominal_capacity_mw"))
    latitude = normalize_optional_number(properties.get("latitude"))
    longitude = normalize_optional_number(properties.get("longitude"))
    commissioning_year = normalize_year(properties.get("commissioning_year"))

    if normalized_name is None or technology is None:
        return None

    coordinate_key = None
    if latitude is not None and longitude is not None:
        coordinate_key = (round(float(latitude), 4), round(float(longitude), 4))

    return (
        technology,
        normalized_name,
        normalized_operator,
        nominal_capacity_mw,
        coordinate_key,
        commissioning_year,
        text_or_none(properties.get("threshold_bucket")),
    )


def register_duplicate_indexes(
    feature: dict,
    feature_index: int,
    duplicate_indexes: dict[str, dict],
):
    properties = feature.get("properties", {})

    for phase_identifier in get_phase_identifiers(properties):
        duplicate_indexes["phase"][phase_identifier] = feature_index

    exact_key = build_exact_duplicate_key(properties)
    if exact_key is not None:
        duplicate_indexes["exact"][exact_key] = feature_index

    normalized_name = normalize_text(properties.get("name"))
    if normalized_name:
        duplicate_indexes["name"][normalized_name].add(feature_index)

    for bucket_key in get_coordinate_bucket_keys(
        properties.get("latitude"),
        properties.get("longitude"),
    ):
        duplicate_indexes["bucket"][bucket_key].add(feature_index)


def build_mergeable_feature_indexes(features: list[dict]) -> dict[str, dict]:
    indexes = {
        "by_project_name": defaultdict(set),
        "by_name": defaultdict(set),
        "by_bucket": defaultdict(set),
    }

    for index, feature in enumerate(features):
        register_mergeable_feature_indexes(feature, index, indexes)

    return indexes


def register_mergeable_feature_indexes(
    feature: dict,
    feature_index: int,
    indexes: dict[str, dict],
):
    properties = feature.get("properties", {})

    project_name = normalize_text(
        properties.get("project_name") or properties.get("phase_name") or properties.get("name")
    )
    if project_name:
        indexes["by_project_name"][project_name].add(feature_index)

    name = normalize_text(properties.get("name"))
    if name:
        indexes["by_name"][name].add(feature_index)

    for bucket_key in get_coordinate_bucket_keys(
        properties.get("latitude"),
        properties.get("longitude"),
    ):
        indexes["by_bucket"][bucket_key].add(feature_index)


def get_candidate_bucket_indices(
    bucket_index: dict[str, set[int]],
    latitude: object,
    longitude: object,
) -> set[int]:
    candidate_indices: set[int] = set()

    for bucket_key in get_neighbor_bucket_keys(latitude, longitude):
        candidate_indices.update(bucket_index.get(bucket_key, set()))

    return candidate_indices


def get_coordinate_bucket_keys(latitude: object, longitude: object) -> list[str]:
    normalized_latitude = normalize_optional_number(latitude)
    normalized_longitude = normalize_optional_number(longitude)
    if normalized_latitude is None or normalized_longitude is None:
        return []

    return [get_coordinate_bucket_key(float(normalized_latitude), float(normalized_longitude))]


def get_neighbor_bucket_keys(latitude: object, longitude: object) -> list[str]:
    normalized_latitude = normalize_optional_number(latitude)
    normalized_longitude = normalize_optional_number(longitude)
    if normalized_latitude is None or normalized_longitude is None:
        return []

    latitude_bucket = math.floor(float(normalized_latitude) * 10)
    longitude_bucket = math.floor(float(normalized_longitude) * 10)
    bucket_keys: list[str] = []

    for latitude_offset in (-1, 0, 1):
        for longitude_offset in (-1, 0, 1):
            bucket_keys.append(
                f"{latitude_bucket + latitude_offset}|{longitude_bucket + longitude_offset}"
            )

    return bucket_keys


def get_coordinate_bucket_key(latitude: float, longitude: float) -> str:
    return f"{math.floor(latitude * 10)}|{math.floor(longitude * 10)}"


def merge_same_source_features(primary_feature: dict, secondary_feature: dict) -> dict:
    primary_properties = dict(primary_feature.get("properties", {}))
    secondary_properties = dict(secondary_feature.get("properties", {}))
    merged_properties = dict(primary_properties)

    for key, value in secondary_properties.items():
        if is_missing_property(merged_properties.get(key)) and not is_missing_property(value):
            merged_properties[key] = value

    merged_properties["source_refs"] = unique_list(
        [
            *listify(primary_properties.get("source_refs")),
            *listify(secondary_properties.get("source_refs")),
        ]
    )
    merged_properties["raw_sources"] = unique_raw_sources(
        listify(primary_properties.get("raw_sources"))
        + listify(secondary_properties.get("raw_sources"))
    )
    merged_properties["notes"] = unique_list(
        [
            *listify(primary_properties.get("notes")),
            *listify(secondary_properties.get("notes")),
            "deduped_same_source",
        ]
    )
    merged_properties["source_confidence"] = max(
        normalize_optional_number(primary_properties.get("source_confidence")) or 0,
        normalize_optional_number(secondary_properties.get("source_confidence")) or 0,
    )
    merged_properties["confidence_score"] = merged_properties["source_confidence"]

    latest_seen = max_date_text(
        text_or_none(primary_properties.get("last_seen")),
        text_or_none(secondary_properties.get("last_seen")),
    )
    if latest_seen:
        merged_properties["last_seen"] = latest_seen
        merged_properties["last_updated"] = latest_seen

    merged_geometry = choose_preferred_geometry(primary_feature, secondary_feature)

    return {
        "type": "Feature",
        "properties": merged_properties,
        "geometry": merged_geometry,
    }


def copy_feature(feature: dict) -> dict:
    return {
        "type": "Feature",
        "properties": dict(feature.get("properties", {})),
        "geometry": feature.get("geometry"),
    }


def find_matching_mergeable_feature(
    existing_features: list[dict],
    mergeable_indexes: dict[str, dict],
    candidate_feature: dict,
) -> int | None:
    candidate_properties = candidate_feature.get("properties", {})
    candidate_project_name = normalize_text(
        candidate_properties.get("project_name") or candidate_properties.get("name")
    )
    candidate_name = normalize_text(candidate_properties.get("name"))

    best_index = None
    best_score = 0

    candidate_indices = set()

    if candidate_project_name:
      candidate_indices.update(
          mergeable_indexes["by_project_name"].get(candidate_project_name, [])
      )
      candidate_indices.update(
          mergeable_indexes["by_name"].get(candidate_project_name, [])
      )

    if candidate_name:
      candidate_indices.update(mergeable_indexes["by_name"].get(candidate_name, []))

    candidate_indices.update(
        get_candidate_bucket_indices(
            mergeable_indexes["by_bucket"],
            candidate_properties.get("latitude"),
            candidate_properties.get("longitude"),
        )
    )

    for index in candidate_indices:
        existing_feature = existing_features[index]
        existing_properties = existing_feature.get("properties", {})
        if existing_properties.get("technology") not in MERGEABLE_GEM_TECHNOLOGIES:
            continue
        if not technologies_are_merge_compatible(
            candidate_properties.get("technology"),
            existing_properties.get("technology"),
        ):
            continue

        score = 0
        existing_project_name = normalize_text(
            existing_properties.get("project_name") or existing_properties.get("name")
        )
        existing_name = normalize_text(existing_properties.get("name"))

        if (
            candidate_project_name
            and existing_project_name
            and candidate_project_name == existing_project_name
        ):
            score += 4
        elif candidate_name and existing_name and names_match_loose(candidate_name, existing_name):
            score += 2

        distance_km = get_distance_km(
            candidate_properties.get("latitude"),
            candidate_properties.get("longitude"),
            existing_properties.get("latitude"),
            existing_properties.get("longitude"),
        )
        if distance_km is not None and distance_km <= 1:
            score += 3
        elif distance_km is not None and distance_km <= 3:
            score += 2

        if capacities_within_tolerance(
            candidate_properties.get("nominal_capacity_mw"),
            existing_properties.get("nominal_capacity_mw"),
        ):
            score += 2
        elif (
            candidate_properties.get("nominal_capacity_mw") is None
            or existing_properties.get("nominal_capacity_mw") is None
        ):
            score += 1

        if candidate_properties.get("technology") == existing_properties.get("technology"):
            score += 1

        if score > best_score and score >= 6:
            best_score = score
            best_index = index

    return best_index


def technologies_are_merge_compatible(
    candidate_technology: object,
    existing_technology: object,
) -> bool:
    normalized_candidate = text_or_none(candidate_technology)
    normalized_existing = text_or_none(existing_technology)

    if normalized_candidate is None or normalized_existing is None:
        return False

    if normalized_candidate == normalized_existing:
        return True

    if (
        normalized_candidate in HYDRO_TECHNOLOGIES
        and normalized_existing in HYDRO_TECHNOLOGIES
    ):
        return True

    if (
        normalized_candidate in {"onshore_wind", "offshore_wind"}
        and normalized_existing in {"onshore_wind", "offshore_wind"}
    ):
        return True

    return False


def should_keep_unmatched_osm_feature(
    feature: dict,
    has_gem_hydro_source: bool,
) -> bool:
    properties = feature.get("properties", {})

    if properties.get("primary_source") != "OpenStreetMap":
        return True

    if not has_gem_hydro_source:
        return True

    if properties.get("technology") not in HYDRO_TECHNOLOGIES:
        return True

    return is_generator_feature_in_greece(feature)


def merge_feature_pair(primary_feature: dict, secondary_feature: dict) -> dict:
    primary_properties = dict(primary_feature.get("properties", {}))
    secondary_properties = dict(secondary_feature.get("properties", {}))

    merged_properties = dict(primary_properties)
    fields_to_backfill = [
        "operator",
        "owner",
        "developer",
        "status",
        "region",
        "regional_unit",
        "municipality",
        "connection_level",
        "voltage_kv",
        "grid_operator",
        "nearest_substation_id",
        "pypsa_bus",
        "commissioning_year",
        "decommissioning_year",
        "generation_capacity_mw",
        "pumping_capacity_mw",
        "energy_capacity_mwh",
        "storage_duration_hours",
        "round_trip_efficiency",
        "upper_reservoir",
        "lower_reservoir",
        "reservoir_system",
        "reversible_units",
        "annual_generation_gwh",
        "parent_project_name",
        "count_in_summary",
        "display_on_map",
        "last_seen",
        "last_updated",
    ]

    for field_name in fields_to_backfill:
        if is_missing_property(merged_properties.get(field_name)):
            merged_properties[field_name] = secondary_properties.get(field_name)

    for field_name, field_value in secondary_properties.items():
        if field_name not in merged_properties:
            merged_properties[field_name] = field_value
            continue

        if is_missing_property(merged_properties.get(field_name)) and not is_missing_property(field_value):
            merged_properties[field_name] = field_value

    merged_properties["source_refs"] = unique_list(
        [
            *listify(primary_properties.get("source_refs")),
            *listify(secondary_properties.get("source_refs")),
        ]
    )
    merged_properties["raw_sources"] = unique_raw_sources(
        listify(primary_properties.get("raw_sources"))
        + listify(secondary_properties.get("raw_sources"))
    )
    merged_properties["source_confidence"] = max(
        normalize_optional_number(primary_properties.get("source_confidence")) or 0,
        normalize_optional_number(secondary_properties.get("source_confidence")) or 0,
    )
    merged_properties["confidence_score"] = merged_properties["source_confidence"]
    merged_properties["notes"] = unique_list(
        [
            *listify(primary_properties.get("notes")),
            *listify(secondary_properties.get("notes")),
            "merged_with_osm_context",
        ]
    )

    merged_geometry = choose_preferred_geometry(primary_feature, secondary_feature)

    if should_prefer_secondary_source(primary_properties, secondary_properties):
        merged_properties["primary_source"] = secondary_properties.get("primary_source")
        merged_properties["source"] = secondary_properties.get("source")

    return {
        "type": "Feature",
        "properties": merged_properties,
        "geometry": merged_geometry,
    }


def choose_preferred_geometry(primary_feature: dict, secondary_feature: dict) -> dict | None:
    primary_properties = primary_feature.get("properties", {})
    secondary_properties = secondary_feature.get("properties", {})
    primary_accuracy = text_or_none(primary_properties.get("location_accuracy"))
    secondary_accuracy = text_or_none(secondary_properties.get("location_accuracy"))

    if primary_accuracy == "exact":
        return primary_feature.get("geometry")

    if secondary_accuracy == "exact":
        return secondary_feature.get("geometry")

    return primary_feature.get("geometry") or secondary_feature.get("geometry")


def should_prefer_secondary_source(
    primary_properties: dict,
    secondary_properties: dict,
) -> bool:
    primary_priority = SOURCE_PRIORITY.get(
        text_or_none(primary_properties.get("primary_source")) or "Unknown",
        0,
    )
    secondary_priority = SOURCE_PRIORITY.get(
        text_or_none(secondary_properties.get("primary_source")) or "Unknown",
        0,
    )
    return secondary_priority > primary_priority


def is_missing_property(value: object) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return text_or_none(value) is None

    if isinstance(value, list):
        return len(value) == 0

    return False


def listify(value: object) -> list:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def unique_list(values: list) -> list:
    unique_values: list = []

    for value in values:
        if value is None or value == "":
            continue
        if value not in unique_values:
            unique_values.append(value)

    return unique_values


def unique_raw_sources(values: list[dict]) -> list[dict]:
    unique_values: list[dict] = []
    seen_keys: set[str] = set()

    for value in values:
        if not isinstance(value, dict):
            continue

        identifier = json.dumps(value, sort_keys=True, ensure_ascii=False)
        if identifier in seen_keys:
            continue

        seen_keys.add(identifier)
        unique_values.append(value)

    return unique_values


def parse_capacity_to_mw(raw_capacity: object) -> dict:
    warnings: list[str] = []
    capacity_mw: float | None = None
    normalized_unit: str | None = None

    if raw_capacity is None:
        return {
            "value_mw": None,
            "unit": None,
            "warnings": warnings,
        }

    if isinstance(raw_capacity, (int, float)):
        numeric_value = float(raw_capacity)
        if numeric_value < 0:
            warnings.append("negative_capacity")
        elif math.isfinite(numeric_value):
            capacity_mw = round(numeric_value, 3)
            normalized_unit = "MW"
    else:
        text_value = str(raw_capacity).strip()
        if text_value.lower() in NULL_TEXT_VALUES:
            return {
                "value_mw": None,
                "unit": None,
                "warnings": warnings,
            }

        numeric_match = re.search(
            r"(-?\d[\d\s.,]*)\s*(gw|mw|kw)?",
            text_value,
            flags=re.IGNORECASE,
        )
        if not numeric_match:
            warnings.append("unparsed_capacity")
            return {
                "value_mw": None,
                "unit": None,
                "warnings": warnings,
            }

        number_text = numeric_match.group(1)
        unit = (numeric_match.group(2) or "mw").lower()
        normalized_number = normalize_numeric_token(number_text)
        if normalized_number is None:
            warnings.append("unparsed_capacity")
            return {
                "value_mw": None,
                "unit": None,
                "warnings": warnings,
            }

        if normalized_number["ambiguous"]:
            warnings.append("ambiguous_capacity_separator")

        numeric_value = normalized_number["value"]
        if numeric_value < 0:
            warnings.append("negative_capacity")
        elif unit == "gw":
            capacity_mw = round(numeric_value * 1000, 3)
            normalized_unit = "GW"
        elif unit == "kw":
            capacity_mw = round(numeric_value / 1000, 3)
            normalized_unit = "kW"
        else:
            capacity_mw = round(numeric_value, 3)
            normalized_unit = "MW"

    if capacity_mw is not None and capacity_mw > SUSPICIOUS_CAPACITY_MW_THRESHOLD:
        warnings.append("suspiciously_high_capacity")

    return {
        "value_mw": capacity_mw,
        "unit": normalized_unit,
        "warnings": warnings,
    }


def normalize_generator_technology(raw_value: object) -> str:
    text_value = text_or_none(raw_value)
    if text_value is None:
        return "unknown"

    normalized_text = text_value.lower()
    for keywords, technology in RAW_TECHNOLOGY_TO_INTERNAL:
        if all(keyword in normalized_text for keyword in keywords):
            return technology

    return "unknown"


def map_technology_category(technology: str) -> str:
    return TECHNOLOGY_TO_CATEGORY.get(technology, "Other/Unknown")


def get_generator_carrier(technology: str) -> str:
    return TECHNOLOGY_TO_CARRIER.get(technology, "unknown")


def get_generator_fuel(properties: dict, technology: str) -> str | None:
    raw_fuel = normalize_missing_text(properties.get("fuel"))
    if raw_fuel:
        return raw_fuel

    return TECHNOLOGY_TO_FUEL.get(technology)


def detect_possible_duplicates(generators: list[dict]) -> list[dict]:
    pair_reasons: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_normalized_name_operator: dict[str, list[dict]] = defaultdict(list)
    by_coordinate_bucket: dict[str, list[dict]] = defaultdict(list)
    by_phase_identifier: dict[str, list[dict]] = defaultdict(list)

    for generator in generators:
        normalized_name = normalize_text(generator.get("name"))
        normalized_operator = normalize_text(generator.get("operator"))

        if normalized_name and normalized_operator:
            by_normalized_name_operator[f"{normalized_name}|{normalized_operator}"].append(
                generator
            )

        latitude = generator.get("latitude")
        longitude = generator.get("longitude")
        if latitude is not None and longitude is not None:
            bucket_key = f"{round(float(latitude), 3)}|{round(float(longitude), 3)}"
            by_coordinate_bucket[bucket_key].append(generator)

        for phase_identifier in get_phase_identifiers(generator):
            by_phase_identifier[phase_identifier].append(generator)

    mark_duplicate_reasons(pair_reasons, by_normalized_name_operator, "same_name_operator")
    mark_duplicate_reasons(pair_reasons, by_phase_identifier, "phase_identifier_overlap")

    for coordinate_group in by_coordinate_bucket.values():
        for left_generator, right_generator in iter_pairs(coordinate_group):
            left_key, right_key = sorted((left_generator["id"], right_generator["id"]))
            distance_km = get_distance_km(
                left_generator.get("latitude"),
                left_generator.get("longitude"),
                right_generator.get("latitude"),
                right_generator.get("longitude"),
            )
            if distance_km is not None and distance_km <= 0.35:
                pair_reasons[(left_key, right_key)].add("nearby_coordinates")

            if capacities_within_tolerance(
                left_generator.get("nominal_capacity_mw"),
                right_generator.get("nominal_capacity_mw"),
            ):
                pair_reasons[(left_key, right_key)].add("same_capacity_tolerance")

            if (
                left_generator.get("technology") == right_generator.get("technology")
                and left_generator.get("technology") != "unknown"
            ):
                pair_reasons[(left_key, right_key)].add("same_technology")

    duplicates = []
    generator_lookup = {generator["id"]: generator for generator in generators}

    for (left_id, right_id), reasons in sorted(pair_reasons.items()):
        left_generator = generator_lookup[left_id]
        right_generator = generator_lookup[right_id]

        if not should_flag_duplicate(left_generator, right_generator, reasons):
            continue

        detailed_reasons = sorted(reasons)
        if capacities_conflict(
            left_generator.get("nominal_capacity_mw"),
            right_generator.get("nominal_capacity_mw"),
        ):
            detailed_reasons.append("capacity_conflict")

        if technologies_conflict(
            left_generator.get("technology"),
            right_generator.get("technology"),
        ):
            detailed_reasons.append("technology_conflict")

        duplicates.append(
            {
                "asset_ids": [left_id, right_id],
                "name": left_generator.get("name"),
                "operator": left_generator.get("operator"),
                "technologies": [
                    left_generator.get("technology"),
                    right_generator.get("technology"),
                ],
                "capacities_mw": [
                    left_generator.get("nominal_capacity_mw"),
                    right_generator.get("nominal_capacity_mw"),
                ],
                "coordinates": [
                    [
                        left_generator.get("longitude"),
                        left_generator.get("latitude"),
                    ],
                    [
                        right_generator.get("longitude"),
                        right_generator.get("latitude"),
                    ],
                ],
                "reasons": detailed_reasons,
            }
        )

    return duplicates


def mark_duplicate_reasons(
    pair_reasons: dict[tuple[str, str], set[str]],
    grouped_generators: dict[str, list[dict]],
    reason: str,
):
    for generator_group in grouped_generators.values():
        for left_generator, right_generator in iter_pairs(generator_group):
            left_key, right_key = sorted((left_generator["id"], right_generator["id"]))
            pair_reasons[(left_key, right_key)].add(reason)


def should_flag_duplicate(
    left_generator: dict,
    right_generator: dict,
    reasons: set[str],
) -> bool:
    if "phase_identifier_overlap" in reasons:
        return True

    if "same_name_operator" in reasons and "nearby_coordinates" in reasons:
        return True

    if {
        "nearby_coordinates",
        "same_capacity_tolerance",
        "same_technology",
    }.issubset(reasons):
        return True

    return False


def capacities_within_tolerance(left: object, right: object) -> bool:
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return False

    tolerance = max(1.0, max(abs(float(left)), abs(float(right))) * 0.05)
    return abs(float(left) - float(right)) <= tolerance


def capacities_conflict(left: object, right: object) -> bool:
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return False

    return not capacities_within_tolerance(left, right)


def technologies_conflict(left: object, right: object) -> bool:
    left_value = text_or_none(left)
    right_value = text_or_none(right)

    if left_value is None or right_value is None:
        return False

    if left_value == "unknown" or right_value == "unknown":
        return False

    return left_value != right_value


def build_quality_stat(count: int, total: int) -> dict:
    percentage = round((count / total) * 100, 2) if total else 0
    return {"count": count, "percentage": percentage}


@lru_cache(maxsize=1)
def load_greece_boundary_geometries() -> list[dict]:
    if not GREECE_BOUNDARY_SOURCE_PATH.exists():
        return []

    with GREECE_BOUNDARY_SOURCE_PATH.open("r", encoding="utf-8") as data_file:
        feature_collection = json.load(data_file)

    return [
        feature.get("geometry")
        for feature in feature_collection.get("features", [])
        if feature.get("geometry")
    ]


def is_generator_feature_in_greece(feature: dict) -> bool:
    properties = feature.get("properties", {})
    geometry = feature.get("geometry")
    longitude, latitude = get_point_coordinates(geometry, properties)

    if longitude is None or latitude is None:
        return True

    return is_point_in_greece(float(longitude), float(latitude))


@lru_cache(maxsize=1)
def get_prepared_greece_boundary():
    # Greece's territory is a huge, scattered archipelago (islands run from
    # near Italy to right off the Turkish coast), so its own bounding box
    # spans almost the entire fetch area -- a manual bbox pre-check does not
    # meaningfully shrink the search space. Shapely's prepared geometry (with
    # its own internal spatial index) is what actually makes point lookups
    # against an 11,000+ vertex, 130-polygon boundary fast; shapely is
    # already a project dependency (used for WKT parsing elsewhere).
    boundaries = load_greece_boundary_geometries()
    if not boundaries:
        return None

    polygons = [shape(boundary) for boundary in boundaries]
    unioned = polygons[0] if len(polygons) == 1 else unary_union(polygons)
    return prep(unioned)


def is_point_in_greece(longitude: float, latitude: float) -> bool:
    prepared_boundary = get_prepared_greece_boundary()
    if prepared_boundary is None:
        return True

    return prepared_boundary.contains(Point(longitude, latitude))


def is_point_feature_in_greece(feature: dict) -> bool:
    geometry = feature.get("geometry")
    if not geometry or geometry.get("type") != "Point":
        return True

    coordinates = geometry.get("coordinates", [])
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return True

    return is_point_in_greece(float(coordinates[0]), float(coordinates[1]))


def is_line_feature_in_greece(feature: dict) -> bool:
    # A cross-border interconnector (e.g. HVDC Italy-Greece) legitimately has
    # vertices outside Greece, so a line only counts as out of scope when
    # every vertex falls outside the boundary rather than just one.
    geometry = feature.get("geometry")
    if not geometry or geometry.get("type") != "LineString":
        return True

    coordinates = geometry.get("coordinates", [])
    if not coordinates:
        return True

    return any(
        is_point_in_greece(float(coordinate[0]), float(coordinate[1]))
        for coordinate in coordinates
    )


def filter_feature_collection(feature_collection: dict, predicate) -> dict:
    return {
        **feature_collection,
        "features": [
            feature
            for feature in feature_collection.get("features", [])
            if predicate(feature)
        ],
    }


def summarize_generator_issue(generator: dict) -> dict:
    return {
        "id": generator["id"],
        "name": generator["name"],
        "operator": generator["operator"],
        "technology": generator["technology"],
        "technology_category": generator["technology_category"],
        "nominal_capacity_mw": generator["nominal_capacity_mw"],
        "generation_capacity_mw": generator.get("generation_capacity_mw"),
        "pumping_capacity_mw": generator.get("pumping_capacity_mw"),
        "primary_source": generator["primary_source"],
        "source_refs": generator["source_refs"],
    }


def get_generator_quality_notes(
    properties: dict,
    technology: str,
    capacity_mw: float | None,
) -> list[str]:
    notes: list[str] = []

    if technology == "unknown":
        notes.append("missing_technology")

    if capacity_mw is None:
        notes.append("missing_capacity")

    if technology == "solar_pv" and capacity_mw is not None and capacity_mw >= 1000:
        notes.append("suspicious_rooftop_pv_capacity")

    if (
        technology in {"battery_storage", "pumped_hydro"}
        and normalize_missing_text(properties.get("status")) is None
    ):
        notes.append("missing_status")

    if technology == "pumped_hydro":
        if not get_source_refs(properties):
            notes.append("missing_source_refs")
        if first_present_value(
            properties,
            ["pumping_capacity_mw", "pump_capacity_mw", "absorbed_capacity_mw"],
        ) is None:
            notes.append("missing_pumping_capacity")

    return notes


def get_source_confidence(
    properties: dict,
    technology: str,
    capacity_mw: float | None,
    longitude: float | None,
    latitude: float | None,
    notes: list[str],
) -> float:
    score = 0.35

    if text_or_none(properties.get("name")):
        score += 0.1

    if text_or_none(properties.get("operator")):
        score += 0.1

    if technology != "unknown":
        score += 0.15

    if capacity_mw is not None:
        score += 0.15

    if longitude is not None and latitude is not None:
        score += 0.1

    if get_source_refs(properties):
        score += 0.05

    if any(note.startswith("suspicious") for note in notes):
        score -= 0.1

    return round(max(0.1, min(score, 0.99)), 2)


def first_present_value(properties: dict, keys: list[str]) -> object:
    for key in keys:
        value = properties.get(key)
        if value is None:
            continue

        if isinstance(value, str) and value.strip().lower() in NULL_TEXT_VALUES:
            continue

        return value

    return None


def get_source_refs(properties: dict) -> list:
    raw_source_refs = properties.get("source_refs")
    if isinstance(raw_source_refs, list):
        return [
            value
            for value in raw_source_refs
            if value is not None and value != ""
        ]

    osm_type = normalize_missing_text(properties.get("osm_type"))
    osm_id = properties.get("osm_id")

    if osm_type and osm_id is not None:
        return [f"osm:{osm_type}/{osm_id}"]

    return []


def get_phase_identifiers(generator: dict) -> list[str]:
    identifiers: list[str] = []

    gem_phase_id = text_or_none(generator.get("gem_phase_id"))
    if gem_phase_id:
        identifiers.append(f"gem-phase:{gem_phase_id}")

    other_ids_phase = text_or_none(generator.get("other_ids_phase"))
    if other_ids_phase:
        for value in other_ids_phase.split(","):
            normalized_value = value.strip()
            if normalized_value:
                identifiers.append(f"phase-ref:{normalized_value}")

    osm_type = text_or_none(generator.get("osm_type"))
    osm_id = generator.get("osm_id")
    if osm_type and osm_id is not None:
        identifiers.append(f"osm:{osm_type}/{osm_id}")

    return identifiers


def infer_primary_source(properties: dict) -> str:
    source_value = normalize_missing_text(properties.get("primary_source"))
    if source_value:
        return source_value

    source_value = normalize_missing_text(properties.get("source"))
    if source_value:
        return source_value

    if properties.get("osm_id") is not None:
        return "OpenStreetMap"

    return "Unknown"


def normalize_status(value: object) -> str:
    text_value = text_or_none(value)
    if text_value is None:
        return "Unknown"

    normalized = text_value.replace("_", " ").strip().title()
    return normalized or "Unknown"


STATUS_CATEGORY_PREFIXES = [
    ("operating", "Operating"),
    ("under construction", "Under Construction"),
    ("in construction", "Under Construction"),
    ("construction", "Under Construction"),
    ("pre-construction", "Pre-Construction"),
    ("pre construction", "Pre-Construction"),
    ("announced", "Announced"),
    ("planned", "Planned"),
    ("proposed", "Planned"),
    ("permitted", "Planned"),
    ("licensed", "Planned"),
    ("shelved", "Shelved"),
    ("cancelled", "Cancelled"),
    ("canceled", "Cancelled"),
    ("retired", "Retired"),
    ("decommissioned", "Retired"),
    ("mothballed", "Mothballed"),
]


def infer_status_category(properties: dict) -> str:
    explicit_value = normalize_missing_text(properties.get("status_category"))
    if explicit_value:
        return explicit_value

    status_text = text_or_none(properties.get("status"))
    if status_text is None:
        return "Unknown"

    normalized_status = status_text.strip().casefold()
    for prefix, category in STATUS_CATEGORY_PREFIXES:
        if normalized_status.startswith(prefix):
            return category

    return "Unknown"


def get_generator_name(properties: dict) -> str:
    name = normalize_missing_text(properties.get("name"))
    if name:
        return name

    generator_id = normalize_missing_text(properties.get("id"))
    if generator_id:
        return generator_id

    return "Unknown Generator"


def build_fallback_id(properties: dict) -> str:
    osm_type = properties.get("osm_type")
    osm_id = properties.get("osm_id")
    if osm_type is not None and osm_id is not None:
        return f"osm-plant-{osm_type}-{osm_id}"

    return "generator-unknown"


def get_point_coordinates(
    geometry: dict | None,
    properties: dict,
) -> tuple[float | None, float | None]:
    if geometry and geometry.get("type") == "Point":
        coordinates = geometry.get("coordinates", [])
        if isinstance(coordinates, list) and len(coordinates) >= 2:
            return (
                normalize_optional_number(coordinates[0]),
                normalize_optional_number(coordinates[1]),
            )

    longitude = normalize_optional_number(properties.get("longitude"))
    latitude = normalize_optional_number(properties.get("latitude"))
    return longitude, latitude


def normalize_missing_text(value: object) -> str | None:
    text_value = text_or_none(value)
    if text_value is None:
        return None

    return text_value


def text_or_none(value: object) -> str | None:
    if value is None:
        return None

    text_value = str(value).strip()
    if text_value.lower() in NULL_TEXT_VALUES:
        return None

    return text_value or None


def normalize_optional_number(value: object) -> float | int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if math.isfinite(value):
            return round(value, 6)
        return None

    if isinstance(value, str):
        parsed = normalize_numeric_token(value)
        if parsed is None:
            return None

        numeric_value = parsed["value"]
        if math.isfinite(numeric_value):
            return round(numeric_value, 6)

    return None


def normalize_numeric_token(value: str) -> dict | None:
    cleaned_value = value.strip().replace(" ", "")
    if not cleaned_value:
        return None

    if not re.fullmatch(r"-?[\d.,]+", cleaned_value):
        return None

    ambiguous = False

    if "," in cleaned_value and "." in cleaned_value:
        last_comma = cleaned_value.rfind(",")
        last_dot = cleaned_value.rfind(".")
        if last_comma > last_dot:
            normalized = cleaned_value.replace(".", "").replace(",", ".")
        else:
            normalized = cleaned_value.replace(",", "")
    elif cleaned_value.count(",") == 1 and "." not in cleaned_value:
        left, right = cleaned_value.split(",")
        if len(right) == 3 and len(left) <= 3:
            normalized = f"{left}{right}"
            ambiguous = True
        else:
            normalized = f"{left}.{right}"
    elif cleaned_value.count(".") == 1 and "," not in cleaned_value:
        left, right = cleaned_value.split(".")
        if len(right) == 3 and len(left) <= 3:
            normalized = f"{left}{right}"
            ambiguous = True
        else:
            normalized = cleaned_value
    else:
        normalized = cleaned_value.replace(",", "").replace(".", "")

    try:
        return {
            "value": float(normalized),
            "ambiguous": ambiguous,
        }
    except ValueError:
        return None


def normalize_year(value: object) -> int | None:
    if isinstance(value, int):
        return value

    text_value = text_or_none(value)
    if text_value is None:
        return None

    match = re.search(r"\b(19|20)\d{2}\b", text_value)
    if not match:
        return None

    return int(match.group(0))


def normalize_text(value: object) -> str | None:
    text_value = text_or_none(value)
    if text_value is None:
        return None

    return re.sub(r"[^a-z0-9]+", "", text_value.lower())


def normalize_search_text(value: object) -> str:
    text_value = text_or_none(value)
    if text_value is None:
        return ""

    normalized = unicodedata.normalize("NFKD", text_value.lower())
    accent_free = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return re.sub(r"[\W_]+", "", accent_free, flags=re.UNICODE)


def names_match_loose(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False

    if left == right:
        return True

    shorter = left if len(left) <= len(right) else right
    longer = right if shorter == left else left
    return len(shorter) >= 8 and shorter in longer


def iter_pairs(values: list[dict]):
    for left_index in range(len(values)):
        for right_index in range(left_index + 1, len(values)):
            yield values[left_index], values[right_index]


def get_distance_km(
    left_latitude: object,
    left_longitude: object,
    right_latitude: object,
    right_longitude: object,
) -> float | None:
    if not all(
        isinstance(value, (int, float))
        for value in [left_latitude, left_longitude, right_latitude, right_longitude]
    ):
        return None

    left_lat_rad = math.radians(float(left_latitude))
    left_lon_rad = math.radians(float(left_longitude))
    right_lat_rad = math.radians(float(right_latitude))
    right_lon_rad = math.radians(float(right_longitude))

    delta_lat = right_lat_rad - left_lat_rad
    delta_lon = right_lon_rad - left_lon_rad

    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(left_lat_rad)
        * math.cos(right_lat_rad)
        * math.sin(delta_lon / 2) ** 2
    )
    arc = 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))

    return 6371 * arc


def max_date_text(left: str | None, right: str | None) -> str | None:
    left_value = parse_iso_like_date(left)
    right_value = parse_iso_like_date(right)

    if left_value is None:
        return right

    if right_value is None:
        return left

    return left if left_value >= right_value else right


def parse_iso_like_date(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.replace("/", "-")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def get_file_timestamp(path: Path) -> str:
    modified_timestamp = datetime.fromtimestamp(
        path.stat().st_mtime,
        tz=timezone.utc,
    )
    return modified_timestamp.isoformat()
