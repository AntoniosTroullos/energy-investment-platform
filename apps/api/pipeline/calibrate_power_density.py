"""Measures how densely Greece actually builds solar and wind, in MW/km^2.

Why this exists
---------------
`assumed_capacity_mw` -- which sets every candidate's capex, and through it
every NPV -- multiplied buildable area by a power density taken from an external
literature range (40 MW/km^2 solar, 6 MW/km^2 onshore wind). That figure was
honest about being a guess: not Greece-specific, not re-verified. It is also the
single most leveraged number in the whole investment chain, so "a plausible
international figure" is the weakest link holding up the strongest claims.

Greece has thousands of built solar and wind plants whose footprints are mapped
in OpenStreetMap as polygons with a tagged capacity. Dividing one by the other
measures the thing directly: the density at which these two technologies are
actually deployed in this country, on this terrain, under these planning rules.

The existing `fetch_osm_power.py` asks Overpass for `out center`, which collapses
every plant to a point and throws the footprint away -- which is why this is a
separate fetch rather than a field added to that one.

Method, and what it does and does not measure
---------------------------------------------
For each mapped plant: footprint area in EGSA87 (EPSG:2100, Greece's own
projected grid -- degrees are not an area), tagged capacity parsed from
`plant:output:electricity`, density = capacity / area.

  * Solar: the polygon is the panel field, so this is array density including
    inter-row spacing, roads and inverter stations inside the fence -- the right
    denominator for "how much of this buildable land becomes MW".
  * Wind: the polygon is the wind farm boundary, so this is array density set by
    turbine spacing, not turbine footprint. Also the right denominator, and the
    reason wind's figure is an order of magnitude below solar's.

It does NOT measure the best achievable density, or what a developer could build
with today's modules on a perfect site. It measures the central tendency of what
has been built. For screening, that is the more defensible number.

The aggregate (total MW / total km^2) is reported alongside the median because
they answer different questions: the median describes a typical plant, the
aggregate describes what a given quantity of land has historically yielded. The
API uses the median, as the one less moved by a single large mis-tagged plant.

Usage
-----
    python apps/api/pipeline/calibrate_power_density.py [--out <path>]
                                                        [--min-area-km2 0.01]

Writes `apps/api/data/generated/power_density_greece.json`. Network access to an
Overpass endpoint is required; without it the API keeps using the literature
fallback and says so in its assumptions block.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, parse, request

import pyproj
from shapely.geometry import MultiPoint, Polygon
from shapely.ops import transform

OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

GREECE_BBOX = {"south": 34.5, "west": 19.0, "north": 42.0, "east": 29.8}

# Plants smaller than a hectare are rooftop and car-park installations whose
# polygon is the building, not the land a utility-scale project would occupy.
# Including them would pull the solar figure towards rooftop densities, which
# have nothing to do with siting a field.
DEFAULT_MIN_AREA_KM2 = 0.01

# Per-carrier method, because the two carriers' footprints come from different
# kinds of mapping and need different handling.
#
# Solar polygons are drawn fence lines: the area is the real one, every plant
# measures the same thing, and the MEDIAN describes a typical plant.
#
# Wind footprints are almost all convex hulls over mapped turbines (Greek wind
# farms are mapped as turbine groups, not boundaries). A hull over five
# turbines is far smaller than the land that farm occupies, so small farms
# report impossibly high densities. The measurement shows it plainly -- median
# density by minimum footprint, on this dataset:
#
#     >=0.01 km^2  n=58  median 17.22   aggregate 7.61
#     >=1 km^2     n=41  median 13.78   aggregate 6.93
#     >=2 km^2     n=30  median 11.23   aggregate 6.02
#     >=5 km^2     n=11  median  6.98   aggregate 4.35
#
# So wind is measured from farms of at least 2 km^2, and reported as the
# CAPACITY-WEIGHTED AGGREGATE (total MW / total km^2) rather than the median:
# that is the definition of array density, it is dominated by the large,
# well-mapped farms, and it does not move with how many small farms happen to
# be in OSM this month. It lands at ~6 MW/km^2, inside the 5-8 MW/km^2 band the
# literature gives for onshore wind -- an independent confirmation rather than
# an assumption.
CARRIER_METHOD = {
    "solar": {"min_area_km2": 0.01, "statistic": "median"},
    "wind": {"min_area_km2": 2.0, "statistic": "aggregate"},
}

# Tagging-error guard rails. A Greek solar field at 300 MW/km^2 or a wind farm
# at 0.1 MW/km^2 is a mis-tagged capacity or a mis-drawn boundary, not a real
# outlier worth keeping. Every rejection is counted and reported, so the filter
# can be audited rather than trusted.
PLAUSIBLE_DENSITY_MW_PER_KM2 = {
    "solar": (5.0, 250.0),
    "wind": (0.5, 60.0),
}

# OSM's plant:source values that map onto the two carriers this calibrates.
SOURCE_TO_CARRIER = {
    "solar": "solar",
    "wind": "wind",
}

_TO_EGSA87 = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:2100", always_xy=True).transform


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=None, help="Output JSON path")
    parser.add_argument("--min-area-km2", type=float, default=DEFAULT_MIN_AREA_KM2)
    parser.add_argument(
        "--from-cache",
        action="store_true",
        help="Reuse the last raw Overpass response instead of refetching (it is rate-limited)",
    )
    args = parser.parse_args(argv)

    try:
        elements = load_elements(use_cache=args.from_cache)
    except RuntimeError as exc:
        print(f"Overpass fetch failed: {exc}", file=sys.stderr)
        return 1

    measurements, rejected = measure(elements, args.min_area_km2)
    payload = summarise(measurements, rejected, args.min_area_km2)

    out_path = Path(args.out) if args.out else default_out_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    for carrier, stats in payload["carriers"].items():
        print(
            f"{carrier}: n={stats['plant_count']} "
            f"headline={stats['headline_mw_per_km2']} MW/km2 ({stats['headline_statistic']}) "
            f"[median {stats['median_mw_per_km2']}, aggregate {stats['aggregate_mw_per_km2']}] "
            f"over {stats['total_area_km2']} km2"
        )
    print(f"wrote {out_path}")
    return 0


def raw_cache_path() -> Path:
    """The raw Overpass response, kept out of git (data/raw/ is ignored).
    Overpass is rate-limited and answers this query slowly, so re-deriving the
    statistics from a response already fetched must not mean refetching it."""
    return Path(__file__).resolve().parent.parent / "data" / "raw" / "osm" / "power_plant_footprints.json"


def load_elements(*, use_cache: bool) -> list[dict]:
    cache = raw_cache_path()
    if use_cache:
        if not cache.is_file():
            raise RuntimeError(f"no cached response at {cache}")
        return json.loads(cache.read_text(encoding="utf-8"))

    elements = fetch_overpass(build_query())
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(elements), encoding="utf-8")
    return elements


def default_out_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "generated" / "power_density_greece.json"


def build_query() -> str:
    bbox = (
        f"{GREECE_BBOX['south']},{GREECE_BBOX['west']},"
        f"{GREECE_BBOX['north']},{GREECE_BBOX['east']}"
    )
    # `out geom` (not `out center`) is the whole point: the footprint is the
    # measurement. Plain `out geom;` -- adding the `tags` modifier returns
    # relations with an EMPTY member list, which silently cost every wind farm
    # mapped as a group of turbine nodes rather than as a drawn boundary, i.e.
    # almost all of them in Greece.
    return f"""
[out:json][timeout:300];
(
  way["power"="plant"]["plant:source"~"^(solar|wind)$"]({bbox});
  relation["power"="plant"]["plant:source"~"^(solar|wind)$"]({bbox});
);
out geom;
""".strip()


def fetch_overpass(query: str) -> list[dict]:
    encoded = parse.urlencode({"data": query}).encode("utf-8")
    last_error: Exception | None = None
    for url in OVERPASS_URLS:
        http_request = request.Request(
            url,
            data=encoded,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "energy-investment-platform/0.1",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=420) as response:
                return json.loads(response.read().decode("utf-8")).get("elements", [])
        except (json.JSONDecodeError, error.HTTPError, error.URLError, TimeoutError) as request_error:
            last_error = request_error
            continue
    raise RuntimeError(f"every Overpass endpoint failed; last error: {last_error}")


# ---------------------------------------------------------------------------
# Measuring
# ---------------------------------------------------------------------------


def parse_capacity_mw(raw: str | None) -> float | None:
    """OSM capacity tags are free text: "12.5 MW", "500 kW", "1200000 W",
    "4.2MW", "2 MW;1 MW". Anything that does not parse cleanly to a single
    number is dropped rather than guessed at."""
    if not raw:
        return None
    text = str(raw).strip().lower().replace(",", ".")
    if ";" in text:
        return None

    multiplier = 1.0
    for suffix, factor in (("mw", 1.0), ("kw", 1e-3), ("gw", 1e3), ("w", 1e-6)):
        if text.endswith(suffix):
            multiplier = factor
            text = text[: -len(suffix)].strip()
            break
    else:
        return None

    try:
        value = float(text)
    except ValueError:
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    return value * multiplier


def element_polygons(element: dict) -> tuple[list[Polygon], str]:
    """Footprint rings from an Overpass `out geom` element, with the method
    that produced them.

    A way carries its own geometry. A relation may carry either a drawn
    boundary (closed outer rings) or -- which is how most Greek wind farms are
    actually mapped -- a bag of turbine members with no boundary at all. For
    those, the convex hull of the turbine positions is the farm's array
    footprint, which is the standard way array density is measured and the only
    footprint that exists in the data.

    Inner rings (holes) are ignored, which slightly over-states area and so
    slightly UNDER-states density: the conservative direction."""
    if element.get("type") == "way":
        return _rings_from_points(element.get("geometry") or []), "polygon"

    polygons: list[Polygon] = []
    for member in element.get("members") or []:
        if member.get("role") not in (None, "", "outer"):
            continue
        polygons.extend(_rings_from_points(member.get("geometry") or []))
    if polygons:
        return polygons, "polygon"

    hull = _hull_from_members(element.get("members") or [])
    return ([hull], "turbine_hull") if hull is not None else ([], "none")


# A farm needs at least this many mapped turbines before its hull means
# anything: three turbines in a line have a degenerate hull, and a hull over a
# handful of points systematically under-states the land a real farm occupies.
MIN_TURBINES_FOR_HULL = 5


def _hull_from_members(members: list[dict]) -> Polygon | None:
    points: list[tuple[float, float]] = []
    for member in members:
        if "lon" in member and "lat" in member:
            points.append((float(member["lon"]), float(member["lat"])))
            continue
        for point in member.get("geometry") or []:
            if "lon" in point and "lat" in point:
                points.append((float(point["lon"]), float(point["lat"])))

    unique = sorted(set(points))
    if len(unique) < MIN_TURBINES_FOR_HULL:
        return None
    hull = MultiPoint(unique).convex_hull
    return hull if isinstance(hull, Polygon) and not hull.is_empty and hull.area > 0 else None


def _rings_from_points(points: list[dict]) -> list[Polygon]:
    coordinates = [(point["lon"], point["lat"]) for point in points if "lon" in point and "lat" in point]
    if len(coordinates) < 4:
        return []
    if coordinates[0] != coordinates[-1]:
        coordinates.append(coordinates[0])
    try:
        polygon = Polygon(coordinates)
    except (ValueError, TypeError):
        return []
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return [polygon] if (not polygon.is_empty and polygon.area > 0) else []


def area_km2(polygons: list[Polygon]) -> float:
    return sum(transform(_TO_EGSA87, polygon).area for polygon in polygons) / 1_000_000.0


def measure(elements: list[dict], min_area_km2: float) -> tuple[dict[str, list[dict]], dict[str, dict[str, int]]]:
    measurements: dict[str, list[dict]] = {"solar": [], "wind": []}
    rejected: dict[str, dict[str, int]] = {
        carrier: {
            "no_capacity_tag": 0,
            "no_usable_geometry": 0,
            "below_min_area": 0,
            "implausible_density": 0,
        }
        for carrier in measurements
    }

    for element in elements:
        tags = element.get("tags") or {}
        carrier = SOURCE_TO_CARRIER.get(str(tags.get("plant:source", "")).strip().lower())
        if carrier is None:
            continue

        capacity = parse_capacity_mw(tags.get("plant:output:electricity"))
        if capacity is None:
            rejected[carrier]["no_capacity_tag"] += 1
            continue

        polygons, footprint_method = element_polygons(element)
        if not polygons:
            rejected[carrier]["no_usable_geometry"] += 1
            continue

        area = area_km2(polygons)
        carrier_minimum = max(min_area_km2, CARRIER_METHOD[carrier]["min_area_km2"])
        if area < carrier_minimum:
            rejected[carrier]["below_min_area"] += 1
            continue

        density = capacity / area
        low, high = PLAUSIBLE_DENSITY_MW_PER_KM2[carrier]
        if not low <= density <= high:
            rejected[carrier]["implausible_density"] += 1
            continue

        measurements[carrier].append(
            {
                "osm_id": f"{element.get('type')}/{element.get('id')}",
                "name": tags.get("name"),
                "capacity_mw": round(capacity, 4),
                "area_km2": round(area, 6),
                "density_mw_per_km2": round(density, 4),
                "footprint_method": footprint_method,
            }
        )
    return measurements, rejected


def summarise(
    measurements: dict[str, list[dict]],
    rejected: dict[str, dict[str, int]],
    min_area_km2: float,
) -> dict:
    carriers: dict[str, dict] = {}
    for carrier, rows in measurements.items():
        if not rows:
            carriers[carrier] = {"plant_count": 0, "rejected": rejected[carrier]}
            continue
        densities = sorted(row["density_mw_per_km2"] for row in rows)
        total_capacity = sum(row["capacity_mw"] for row in rows)
        total_area = sum(row["area_km2"] for row in rows)
        aggregate = (
            round(sum(row["capacity_mw"] for row in rows) / sum(row["area_km2"] for row in rows), 2)
            if sum(row["area_km2"] for row in rows) > 0
            else None
        )
        statistic = CARRIER_METHOD[carrier]["statistic"]
        headline = round(statistics.median(densities), 2) if statistic == "median" else aggregate
        carriers[carrier] = {
            "plant_count": len(rows),
            # What the API should use, and which statistic produced it. See
            # CARRIER_METHOD above for why the two carriers differ.
            "headline_mw_per_km2": headline,
            "headline_statistic": statistic,
            "min_area_km2": CARRIER_METHOD[carrier]["min_area_km2"],
            "footprint_methods": {
                method: sum(1 for row in rows if row["footprint_method"] == method)
                for method in sorted({row["footprint_method"] for row in rows})
            },
            "median_mw_per_km2": round(statistics.median(densities), 2),
            "mean_mw_per_km2": round(statistics.fmean(densities), 2),
            "p25_mw_per_km2": round(_percentile(densities, 0.25), 2),
            "p75_mw_per_km2": round(_percentile(densities, 0.75), 2),
            "min_mw_per_km2": round(densities[0], 2),
            "max_mw_per_km2": round(densities[-1], 2),
            "total_capacity_mw": round(total_capacity, 1),
            "total_area_km2": round(total_area, 3),
            "aggregate_mw_per_km2": aggregate,
            "largest_plants": sorted(rows, key=lambda row: row["capacity_mw"], reverse=True)[:10],
            "rejected": rejected[carrier],
        }

    return {
        "schema_version": 1,
        "source": "OpenStreetMap via Overpass (power=plant polygons with plant:output:electricity)",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": (
            "Footprint area measured in EGSA87 (EPSG:2100); density = tagged capacity / footprint. "
            "Each carrier has its own minimum footprint and headline statistic (see "
            "`carriers[*].min_area_km2` / `headline_statistic`): solar polygons are drawn fence "
            "lines, so the median of them describes a typical plant; wind footprints are convex "
            "hulls over mapped turbines, which under-state small farms, so wind is measured from "
            "farms of at least 2 km^2 and reported as the capacity-weighted aggregate. "
            f"Plants below {min_area_km2} km^2 excluded as rooftop/car-park installations, and "
            "densities outside a plausibility band excluded as tagging errors (counts in `rejected`). "
            "Solar polygons are panel fields, wind polygons are farm boundaries, so both figures are "
            "array densities including internal spacing -- the right denominator for turning buildable "
            "land into installable MW."
        ),
        "min_area_km2": min_area_km2,
        "plausibility_band_mw_per_km2": PLAUSIBLE_DENSITY_MW_PER_KM2,
        "carriers": carriers,
    }


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    position = fraction * (len(sorted_values) - 1)
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return sorted_values[low]
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


if __name__ == "__main__":
    raise SystemExit(main())
