import csv
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from .evaluation import get_source_layer_feature_collection
from .models import (
    RegionalDemandAllocationResponse,
    RegionalDemandRow,
)


API_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = API_ROOT.parents[1]
REGIONAL_FEATURES_PATH = (
    API_ROOT / "data" / "processed" / "regional_demand" / "regional_features.csv"
)
MODEL_READY_LOAD_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "national_load"
    / "ipto_system_load_hourly_2022_2026_model_ready.csv"
)


SECTOR_PROXY_WEIGHTS = {
    "residential": {
        "population": 0.85,
        "population_density": 0.15,
    },
    "commercial": {
        "services_gva": 0.35,
        "tourism_nights": 0.30,
        "gdp_million_eur": 0.20,
        "population": 0.15,
    },
    "industrial": {
        "industrial_gva": 0.60,
        "industrial_employment": 0.15,
        "gdp_million_eur": 0.15,
        "population": 0.10,
    },
    "agricultural": {
        "agricultural_gva": 0.55,
        "cultivated_area": 0.25,
        "area_km2": 0.15,
        "population": 0.05,
    },
    "public": {
        "population": 0.60,
        "area_km2": 0.40,
    },
}

SEASONAL_SECTOR_SHARES = {
    "winter": {
        "residential": 0.38,
        "commercial": 0.25,
        "industrial": 0.24,
        "agricultural": 0.04,
        "public": 0.09,
    },
    "spring": {
        "residential": 0.32,
        "commercial": 0.26,
        "industrial": 0.25,
        "agricultural": 0.08,
        "public": 0.09,
    },
    "summer": {
        "residential": 0.29,
        "commercial": 0.34,
        "industrial": 0.20,
        "agricultural": 0.08,
        "public": 0.09,
    },
    "autumn": {
        "residential": 0.34,
        "commercial": 0.27,
        "industrial": 0.24,
        "agricultural": 0.06,
        "public": 0.09,
    },
}

SECTOR_LABELS = {
    "residential": "residential",
    "commercial": "commercial/tourism",
    "industrial": "industrial",
    "agricultural": "agricultural",
    "public": "public/municipal",
}


def get_regional_demand_allocation(
    timestamp_utc: str | None = None,
    national_load_mw: float | None = None,
) -> RegionalDemandAllocationResponse:
    timestamp, national_load, national_source = resolve_national_load(
        timestamp_utc=timestamp_utc,
        national_load_mw=national_load_mw,
    )
    month = timestamp.month
    season = season_for_month(month)
    features = load_regional_features()
    shares = build_monthly_allocation(features, month)
    regions = [
        build_regional_demand_row(row, national_load, month, season)
        for row in shares
    ]
    regions = sorted(regions, key=lambda row: row.allocatedLoadMw, reverse=True)
    regions_geojson = build_regional_demand_geojson(regions)

    return RegionalDemandAllocationResponse(
        timestampUtc=timestamp.isoformat().replace("+00:00", "Z"),
        nationalLoadMw=round(national_load, 3),
        month=month,
        season=season,
        method="estimated regional allocation",
        source=(
            f"{national_source} + Eurostat regional proxies "
            "(population, GDP, monthly tourism nights, sector GVA, UAA, industrial employment)"
        ),
        regions=regions,
        regionsGeojson=regions_geojson,
    )


def resolve_national_load(
    timestamp_utc: str | None,
    national_load_mw: float | None,
) -> tuple[datetime, float, str]:
    latest_timestamp, latest_load = latest_model_ready_national_load()
    timestamp = parse_timestamp_utc(timestamp_utc) if timestamp_utc else latest_timestamp

    if national_load_mw is not None:
        if national_load_mw <= 0:
            raise ValueError("national_load_mw must be positive.")
        return timestamp, float(national_load_mw), "User-supplied national load"

    if timestamp_utc is None:
        return latest_timestamp, latest_load, "IPTO/ADMIE model-ready national load"

    # Previously this branch always returned latest_load regardless of the
    # requested timestamp, silently ignoring timestamp_utc whenever
    # national_load_mw wasn't also supplied -- callers asking for a past date's
    # real load got today's load instead with no indication anything was wrong.
    historical_load = historical_national_load_at(timestamp)
    if historical_load is not None:
        return timestamp, historical_load, "IPTO/ADMIE model-ready national load (historical)"

    return timestamp, latest_load, (
        f"IPTO/ADMIE model-ready national load (no observation for {timestamp.isoformat()}, "
        "fell back to latest available)"
    )


@lru_cache(maxsize=1)
def national_load_series() -> dict[datetime, float]:
    series: dict[datetime, float] = {}
    with MODEL_READY_LOAD_PATH.open("r", encoding="utf-8") as load_file:
        for row in csv.DictReader(load_file):
            load = parse_float(row.get("national_load_mw"))
            if load <= 0:
                continue
            timestamp = parse_platform_load_timestamp(row["timestamp"])
            series[timestamp] = load
    return series


def historical_national_load_at(timestamp: datetime) -> float | None:
    return national_load_series().get(timestamp)


@lru_cache(maxsize=1)
def load_regional_features() -> list[dict[str, float | str]]:
    with REGIONAL_FEATURES_PATH.open("r", encoding="utf-8") as feature_file:
        rows = list(csv.DictReader(feature_file))

    if not rows:
        raise RuntimeError("Regional feature table is empty.")

    numeric_columns = [
        key
        for key in rows[0]
        if key not in {"region_id", "geo", "data_source"}
    ]
    parsed_rows = []
    for row in rows:
        parsed_row: dict[str, float | str] = {
            "region_id": row["region_id"],
            "geo": row["geo"],
            "data_source": row.get("data_source", ""),
        }
        for column in numeric_columns:
            parsed_row[column] = parse_float(row.get(column))
        parsed_rows.append(parsed_row)

    return parsed_rows


def latest_model_ready_national_load() -> tuple[datetime, float]:
    latest_timestamp = None
    latest_load = None

    with MODEL_READY_LOAD_PATH.open("r", encoding="utf-8") as load_file:
        for row in csv.DictReader(load_file):
            load = parse_float(row.get("national_load_mw"))
            if load <= 0:
                continue
            timestamp = parse_platform_load_timestamp(row["timestamp"])
            if latest_timestamp is None or timestamp > latest_timestamp:
                latest_timestamp = timestamp
                latest_load = load

    if latest_timestamp is None or latest_load is None:
        raise RuntimeError("No model-ready national load rows were found.")

    return latest_timestamp, latest_load


def build_monthly_allocation(
    regional_features: list[dict[str, float | str]],
    month: int,
) -> list[dict[str, float | str]]:
    season = season_for_month(month)
    sector_shares = {
        sector: build_sector_share(regional_features, weights, month)
        for sector, weights in SECTOR_PROXY_WEIGHTS.items()
    }
    rows = []

    for feature in regional_features:
        region_id = str(feature["region_id"])
        sector_values = {
            sector: sector_shares[sector][region_id]
            for sector in SECTOR_PROXY_WEIGHTS
        }
        allocation_share = sum(
            sector_values[sector] * SEASONAL_SECTOR_SHARES[season][sector]
            for sector in SECTOR_PROXY_WEIGHTS
        )
        rows.append(
            {
                **feature,
                **{f"{sector}_share": value for sector, value in sector_values.items()},
                "month": float(month),
                "season": season,
                "allocation_share": allocation_share,
            }
        )

    return normalize_rows(rows, "allocation_share")


def build_sector_share(
    regional_features: list[dict[str, float | str]],
    proxy_weights: dict[str, float],
    month: int,
) -> dict[str, float]:
    effective_weights = {}
    for proxy, weight in proxy_weights.items():
        effective_proxy = proxy
        monthly_tourism_proxy = f"tourism_nights_m{month:02d}"
        if proxy == "tourism_nights" and has_positive_proxy(regional_features, monthly_tourism_proxy):
            effective_proxy = monthly_tourism_proxy
        if has_positive_proxy(regional_features, effective_proxy):
            effective_weights[effective_proxy] = weight

    if not effective_weights:
        effective_weights = {"population": 1.0}

    weight_total = sum(effective_weights.values())
    scores = {str(row["region_id"]): 0.0 for row in regional_features}
    for proxy, weight in effective_weights.items():
        proxy_shares = build_proxy_share(regional_features, proxy)
        for region_id, share in proxy_shares.items():
            scores[region_id] += share * (weight / weight_total)

    total_score = sum(scores.values())
    return {
        region_id: score / total_score
        for region_id, score in scores.items()
    }


def build_proxy_share(
    regional_features: list[dict[str, float | str]],
    column: str,
) -> dict[str, float]:
    values = {
        str(row["region_id"]): max(float(row.get(column, 0) or 0), 0)
        for row in regional_features
    }
    total = sum(values.values())
    if total <= 0:
        raise RuntimeError(f"Cannot build proxy share for {column}.")
    return {
        region_id: value / total
        for region_id, value in values.items()
    }


def build_regional_demand_row(
    row: dict[str, float | str],
    national_load_mw: float,
    month: int,
    season: str,
) -> RegionalDemandRow:
    sector_contributions = {
        sector: float(row[f"{sector}_share"]) * SEASONAL_SECTOR_SHARES[season][sector]
        for sector in SECTOR_PROXY_WEIGHTS
    }
    dominant_sector = max(sector_contributions, key=sector_contributions.get)
    allocation_share = float(row["allocation_share"])

    return RegionalDemandRow(
        regionId=str(row["region_id"]),
        geo=str(row["geo"]),
        allocatedLoadMw=national_load_mw * allocation_share,
        allocationShare=round(allocation_share, 8),
        residentialShare=round(float(row["residential_share"]), 8),
        commercialShare=round(float(row["commercial_share"]), 8),
        industrialShare=round(float(row["industrial_share"]), 8),
        agriculturalShare=round(float(row["agricultural_share"]), 8),
        publicShare=round(float(row["public_share"]), 8),
        dominantDriver=SECTOR_LABELS[dominant_sector],
        month=month,
        season=season,
    )


def build_regional_demand_geojson(regions: list[RegionalDemandRow]) -> dict:
    region_by_id = {region.regionId: region for region in regions}
    feature_collection = get_source_layer_feature_collection("admin_regions.geojson")
    features = []

    for feature in feature_collection["features"]:
        properties = feature.get("properties") or {}
        region_id = properties.get("id")
        allocation = region_by_id.get(region_id)
        if allocation is None:
            continue

        features.append(
            {
                **feature,
                "properties": {
                    **properties,
                    "allocated_load_mw": allocation.allocatedLoadMw,
                    "allocation_share": allocation.allocationShare,
                    "allocation_pct": round(allocation.allocationShare * 100, 3),
                    "residential_share": allocation.residentialShare,
                    "commercial_share": allocation.commercialShare,
                    "industrial_share": allocation.industrialShare,
                    "agricultural_share": allocation.agriculturalShare,
                    "public_share": allocation.publicShare,
                    "dominant_driver": allocation.dominantDriver,
                    "month": allocation.month,
                    "season": allocation.season,
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def normalize_rows(
    rows: list[dict[str, float | str]],
    column: str,
) -> list[dict[str, float | str]]:
    total = sum(float(row[column]) for row in rows)
    if total <= 0:
        raise RuntimeError(f"Cannot normalize {column}.")
    for row in rows:
        row[column] = float(row[column]) / total
    return rows


def has_positive_proxy(
    regional_features: list[dict[str, float | str]],
    column: str,
) -> bool:
    return sum(float(row.get(column, 0) or 0) for row in regional_features) > 0


def season_for_month(month: int) -> str:
    if month in {12, 1, 2}:
        return "winter"
    if month in {3, 4, 5}:
        return "spring"
    if month in {6, 7, 8}:
        return "summer"
    if month in {9, 10, 11}:
        return "autumn"
    raise ValueError(f"Invalid month: {month}")


def parse_timestamp_utc(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def parse_platform_load_timestamp(value: str) -> datetime:
    timestamp = datetime.strptime(value, "%Y-%m-%d %H:%M:%S%z")
    return timestamp.astimezone(timezone.utc)


def parse_float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)
