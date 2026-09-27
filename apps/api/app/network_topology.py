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

from shapely.geometry import mapping, shape
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

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": row.get("name"),
                    "bus0": bus0,
                    "bus1": bus1,
                    "s_nom_mw": s_nom_mw,
                },
                "geometry": {"type": "LineString", "coordinates": [list(start), list(end)]},
            }
        )

    return {"type": "FeatureCollection", "features": features}
