"""The 13-region network's fixed shape: region polygons (simplified for the
map) and the 14 transmission corridors between them.

Two things this module deliberately does NOT do:
  * Read anything from pypsa-greece except the one static table
    (data/static/lines.csv) that lists the corridors -- read-only access to
    the sibling project, no edits to it.
  * Give a corridor real geographic routing. lines.csv has no coordinates at
    all (a PyPSA network only needs bus0/bus1/reactance/resistance, not a
    physical route), so "the line between two regions" is drawn here as the
    straight segment between their polygon centroids -- a schematic corridor,
    not a claim about where the real towers run.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from shapely.geometry import Point, mapping, shape
from shapely.prepared import prep

from .evaluation import get_source_layer_feature_collection, load_candidate_cells
from .settings import Settings
from .settings import settings as default_settings

LINES_RELATIVE_PATH = Path("data") / "static" / "lines.csv"

# Degrees. ~95% smaller than the raw admin_regions.geojson (117,864 vertices,
# 2.8MB as topojson-free GeoJSON) with no visible loss at national map scale --
# see the measurements in the commit that introduced this. Shared by the
# choropleth and the schematic corridor-centroid calculation so both draw from
# the same simplified shape.
REGION_SIMPLIFY_TOLERANCE_DEGREES = 0.002


@lru_cache(maxsize=1)
def get_simplified_admin_regions() -> dict:
    raw = get_source_layer_feature_collection("admin_regions.geojson")
    features = []
    for feature in raw.get("features", []):
        geometry = feature.get("geometry")
        if not geometry:
            features.append(feature)
            continue

        simplified = shape(geometry).simplify(REGION_SIMPLIFY_TOLERANCE_DEGREES, preserve_topology=True)
        features.append({**feature, "geometry": mapping(simplified)})

    return {**raw, "features": features}


@lru_cache(maxsize=1)
def get_region_centroids() -> dict[str, tuple[float, float]]:
    """Centroid (longitude, latitude) per region id, from the ORIGINAL
    (unsimplified) polygons -- simplification barely moves a centroid, but
    there is no reason to accept even that for a value computed once and
    cached for the life of the process."""
    raw = get_source_layer_feature_collection("admin_regions.geojson")
    centroids: dict[str, tuple[float, float]] = {}
    for feature in raw.get("features", []):
        region_id = feature.get("properties", {}).get("id")
        geometry = feature.get("geometry")
        if not region_id or not geometry:
            continue
        centroid = shape(geometry).centroid
        centroids[region_id] = (centroid.x, centroid.y)
    return centroids


@lru_cache(maxsize=1)
def get_candidate_region_ids() -> dict[str, str | None]:
    """Which of the 13 admin regions each candidate cell's centroid falls
    inside -- candidate cells carry no region/bus identifier of their own
    (see pipeline/generate_candidates.py), so this is a new geometry join,
    not a plain key lookup. Uses the ORIGINAL (unsimplified) region
    boundaries, like get_region_centroids, each wrapped in shapely.prepared
    .prep -- the same technique app/generators.py's
    get_prepared_greece_boundary already uses for point-in-region membership
    tests. A cell whose centroid falls outside all 13 (e.g. a small island
    not covered by any admin-region polygon) maps to None rather than being
    dropped."""
    raw_regions = get_source_layer_feature_collection("admin_regions.geojson")
    prepared_regions: list[tuple[str, object]] = []
    for feature in raw_regions.get("features", []):
        region_id = feature.get("properties", {}).get("id")
        geometry = feature.get("geometry")
        if not region_id or not geometry:
            continue
        prepared_regions.append((region_id, prep(shape(geometry))))

    region_ids: dict[str, str | None] = {}
    for cell in load_candidate_cells():
        centroid = shape(cell.geometry).centroid
        region_ids[cell.id] = next(
            (region_id for region_id, prepared in prepared_regions if prepared.contains(centroid)),
            None,
        )
    return region_ids


# ---------------------------------------------------------------------------
# Corridor provenance: how much of the modelled network is real
# ---------------------------------------------------------------------------
#
# The 13-region network is a stylised abstraction. That has always been stated
# in prose, in this file and in the thesis, and prose is not something a reader
# of the map can check. The functions below turn it into a measurement instead:
# for every modelled corridor, how many real transmission circuits actually
# cross between those two regions, at what voltages, from the OSM transmission
# layer this platform already carries.
#
# A corridor with real 400 kV circuits behind it is a simplification of
# something that exists. A corridor with none is a modelling convenience. The
# difference matters to anyone reading a price spread off this network, and
# until now nothing distinguished them.

# Real lines are sampled rather than tested vertex by vertex: a long corridor
# can carry hundreds of vertices and only its ends decide which regions it
# connects. Sampling every Nth vertex plus both ends keeps the join to a few
# thousand point-in-polygon tests.
LINE_VERTEX_SAMPLE_STRIDE = 10


@lru_cache(maxsize=1)
def _prepared_regions() -> list[tuple[str, object]]:
    raw = get_source_layer_feature_collection("admin_regions.geojson")
    prepared: list[tuple[str, object]] = []
    for feature in raw.get("features", []):
        region_id = feature.get("properties", {}).get("id")
        geometry = feature.get("geometry")
        if region_id and geometry:
            prepared.append((region_id, prep(shape(geometry))))
    return prepared


# A submarine cable's route is at sea, so none of its vertices falls inside any
# land polygon and a containment test alone finds nothing -- which would wrongly
# report every island interconnector as unsupported. Both endpoints are
# therefore snapped to the nearest region within this distance (degrees, roughly
# 30 km at Greek latitudes): far enough to reach a landing point just off the
# coast, close enough not to invent a connection across open water.
LANDFALL_SNAP_DEGREES = 0.3


@lru_cache(maxsize=1)
def _region_shapes() -> list[tuple[str, object]]:
    raw = get_source_layer_feature_collection("admin_regions.geojson")
    shapes: list[tuple[str, object]] = []
    for feature in raw.get("features", []):
        region_id = feature.get("properties", {}).get("id")
        geometry = feature.get("geometry")
        if region_id and geometry:
            shapes.append((region_id, shape(geometry)))
    return shapes


def _containing_region(point: Point) -> str | None:
    for region_id, prepared in _prepared_regions():
        if prepared.contains(point):
            return region_id
    return None


def _nearest_region(point: Point, limit_degrees: float) -> str | None:
    best_id, best_distance = None, limit_degrees
    for region_id, geometry in _region_shapes():
        distance = geometry.distance(point)
        if distance <= best_distance:
            best_id, best_distance = region_id, distance
    return best_id


def _regions_touched(coordinates: list) -> set[str]:
    regions: set[str] = set()
    sampled = coordinates[:: LINE_VERTEX_SAMPLE_STRIDE] or []
    if coordinates:
        sampled = [coordinates[0], *sampled, coordinates[-1]]
    for coordinate in sampled:
        region_id = _containing_region(Point(coordinate[0], coordinate[1]))
        if region_id:
            regions.add(region_id)

    if len(regions) >= 2 or not coordinates:
        return regions

    # Offshore route: fall back to where each end makes landfall.
    for coordinate in (coordinates[0], coordinates[-1]):
        point = Point(coordinate[0], coordinate[1])
        region_id = _containing_region(point) or _nearest_region(point, LANDFALL_SNAP_DEGREES)
        if region_id:
            regions.add(region_id)
    return regions


@lru_cache(maxsize=1)
def get_real_interregional_lines() -> dict[frozenset, dict]:
    """Real OSM transmission lines grouped by the pair of regions they connect.

    A line is evidence for a region pair when its sampled vertices fall in
    exactly two regions. Lines that stay inside one region are internal
    reinforcement, not a corridor; a line crossing three or more regions is
    counted for each adjacent pair it spans, since the model has no
    three-ended corridor to attribute it to."""
    collection = get_source_layer_feature_collection("transmission_lines.geojson")
    evidence: dict[frozenset, dict] = {}

    for feature in collection.get("features", []):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "LineString":
            continue
        regions = _regions_touched(geometry.get("coordinates") or [])
        if len(regions) < 2:
            continue

        properties = feature.get("properties") or {}
        voltage = properties.get("voltage_kv")
        submarine = bool(properties.get("is_submarine"))

        ordered = sorted(regions)
        for first_index, first in enumerate(ordered):
            for second in ordered[first_index + 1 :]:
                key = frozenset((first, second))
                entry = evidence.setdefault(key, {"circuit_count": 0, "voltages_kv": set(), "submarine": False})
                entry["circuit_count"] += 1
                if isinstance(voltage, (int, float)) and voltage > 0:
                    entry["voltages_kv"].add(int(voltage))
                entry["submarine"] = entry["submarine"] or submarine
    return evidence


def corridor_provenance(cfg: Settings = default_settings) -> dict:
    """What the modelled network is, corridor by corridor, and how much of it
    the real transmission layer corroborates."""
    real = get_real_interregional_lines()
    corridors = []
    corroborated = 0

    for row in load_transmission_corridor_rows(cfg):
        bus0, bus1 = row.get("bus0"), row.get("bus1")
        if not bus0 or not bus1:
            continue
        entry = real.get(frozenset((bus0, bus1)))
        if entry:
            corroborated += 1
        corridors.append(
            {
                "id": row.get("name"),
                "bus0": bus0,
                "bus1": bus1,
                "modelled_rating_mw": _to_float(row.get("s_nom")),
                "real_circuits_found": entry["circuit_count"] if entry else 0,
                "real_voltages_kv": sorted(entry["voltages_kv"]) if entry else [],
                "includes_submarine_cable": bool(entry["submarine"]) if entry else False,
                # Scoped to this platform's own data, deliberately: "not in the
                # OSM layer" is a statement about coverage, not a claim that
                # the link does not exist. The four corridors that fail here
                # are all long submarine interconnectors, which is exactly
                # where OSM coverage is thinnest -- the Attica-Crete HVDC is
                # built and simply is not mapped in this extract.
                "status": "corroborated" if entry else "not_in_osm_layer",
                "note": None
                if entry
                else (
                    "No circuit between these regions appears in this platform's OSM transmission "
                    "layer. For a submarine interconnector that usually means the cable is unmapped, "
                    "not that it is absent -- treat this as missing evidence, not as evidence of "
                    "absence."
                ),
            }
        )

    total = len(corridors)
    return {
        "region_polygons": (
            "Real: OpenStreetMap administrative regions, the same 13 the model buses are named for."
        ),
        "corridor_routing": (
            "Schematic. pypsa-greece's lines.csv carries no coordinates, so each corridor is drawn "
            "as the straight segment between two region centroids. It is not a claim about where "
            "the towers run."
        ),
        "corridor_ratings": (
            "Stylised. The s_nom values are the model's own assumed corridor capacities, not ADMIE's "
            "published circuit ratings, and no ADMIE topology is used anywhere in this platform. A "
            "price spread read off this network describes the modelled corridors, not the real grid."
        ),
        "corroboration_method": (
            "Each modelled corridor is checked against the OSM transmission layer this platform "
            f"already carries ({len(real)} region pairs are connected by at least one real line). A "
            "corridor is 'corroborated' when real circuits cross between those two regions -- which "
            "says the connection exists, NOT that its modelled rating is right. Offshore routes are "
            "matched by where each end makes landfall, since a submarine cable's path lies outside "
            "every land polygon."
        ),
        "corridor_count": total,
        "corroborated_count": corroborated,
        "corroborated_pct": round(100.0 * corroborated / total, 1) if total else None,
        "corridors": corridors,
    }


def _to_float(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def _lines_csv_path(cfg: Settings) -> Path:
    return cfg.pypsa_greece_root / LINES_RELATIVE_PATH


def load_transmission_corridor_rows(cfg: Settings = default_settings) -> list[dict[str, str]]:
    path = _lines_csv_path(cfg)
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def get_network_topology_geojson(cfg: Settings = default_settings) -> dict:
    """A LineString per transmission corridor (schematic: centroid to
    centroid -- see module docstring), carrying its rated capacity so the
    frontend can draw corridor width proportional to s_nom."""
    centroids = get_region_centroids()
    real = get_real_interregional_lines()
    features = []

    for row in load_transmission_corridor_rows(cfg):
        bus0, bus1 = row.get("bus0"), row.get("bus1")
        start, end = centroids.get(bus0 or ""), centroids.get(bus1 or "")
        if not start or not end:
            continue  # a bus this corridor names isn't a region we have a polygon for

        try:
            s_nom_mw = float(row["s_nom"])
        except (KeyError, ValueError):
            s_nom_mw = None

        evidence = real.get(frozenset((bus0, bus1)))
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": row.get("name"),
                    "bus0": bus0,
                    "bus1": bus1,
                    "s_nom_mw": s_nom_mw,
                    # Whether real transmission circuits cross between these two
                    # regions, so the map can distinguish a simplification of
                    # something real from a modelling convenience.
                    "real_circuits_found": evidence["circuit_count"] if evidence else 0,
                    "real_voltages_kv": sorted(evidence["voltages_kv"]) if evidence else [],
                },
                "geometry": {"type": "LineString", "coordinates": [list(start), list(end)]},
            }
        )

    return {"type": "FeatureCollection", "features": features}
