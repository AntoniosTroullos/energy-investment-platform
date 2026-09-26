"""Real, cited siting-constraint rules for candidate-cell screening.

Before this module, a candidate's polygon was always its full grid square --
Natura 2000 only lowered its investment score and set a `land_excluded` flag
past a hand-picked 15%-overlap threshold, never changed what land the polygon
actually claimed as a candidate site. This module makes the polygon itself
reflect the real, technology-specific siting rules: a candidate's geometry
becomes the buildable land actually left inside its grid cell once hard
exclusions are subtracted, not the raw square.

Same real government framework already ported for pypsa-greece's generator
clustering (pypsa-greece/src/spatial_constraints.py): Greece's draft (May
2026) "Special Framework for Spatial Planning of RES", cross-checked across
four independently fetched sources on 2026-08-19 (protothema.gr,
athens-times.com x2, news.gtp.gr -- see pypsa-greece's KNOWLEDGE_TRANSFER.md
section 23 for the full citation list and exact quoted wording). It was in
public consultation as of that date, so these are draft rules, not yet law,
same caveat as the original port. Duplicated here rather than imported --
apps/api does not import the sibling project's Python at runtime (its own
dependency set stays independent, same reasoning as the PyPSA scenario
bridge using subprocess rather than an in-process import).

Two real, technology-specific distinctions this module makes -- both
load-bearing for what actually gets carved out of a candidate's geometry
versus merely flagged as a warning:
  * Solar: Natura 2000 is an ABSOLUTE BAN -- its area is subtracted from a
    solar candidate's geometry entirely.
  * Wind: Natura 2000 overlap is CONDITIONAL LICENSING under Law 4685/2020,
    not a ban -- never clipped from wind geometry, only reported as an
    overlap fraction and a warning. Wind's real hard exclusions instead are
    region-based: Attica (a banned region), the Thessaloniki metro area (a
    banned regional unit), and any island under the wind area threshold.

Two rules from the same research are explicitly NOT modeled here, same as
the original port: the disputed wind coverage cap (sources disagree on the
percentage), and the general settlement setback distance (no source states a
figure). Also not modeled: the wind elevation limit -- pypsa-greece's port
fetches real per-site elevation for that; this pipeline has no elevation
data source wired in, so wind's hard-exclusion set here is region/island
based only, not elevation based. Stated, not silently dropped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from shapely import STRtree
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

WIND_ISLAND_AREA_THRESHOLD_KM2 = 300.0
WIND_BANNED_REGIONS = {"Attica"}  # matches admin_regions.geojson's "id"
WIND_BANNED_REGIONAL_UNIT_SUBSTRINGS = {"Thessaloniki"}  # matched against regional_units.geojson's "name"

# Real, cited (news.gtp.gr, "Solar Energy Restrictions") -- a mandatory
# visual-impact/environmental study trigger, explicitly NOT an automatic
# rejection. No equivalent wind-specific distance rule was found in any of
# the four sources.
SOLAR_UNESCO_STUDY_TRIGGER_KM = 1.5

# A cell reduced to less than this fraction of its original area isn't a
# meaningful candidate site once hard exclusions are subtracted -- dropped by
# the caller rather than emitted as a near-empty sliver polygon.
MIN_BUILDABLE_FRACTION = 0.01

KM_PER_DEGREE_LAT = 111.0


def _load_geojson(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as geojson_file:
        return json.load(geojson_file)


@dataclass(frozen=True)
class ConstraintLayers:
    natura_2000_geometries: list[BaseGeometry]
    natura_2000_index: STRtree
    # One precomputed union: every real hard wind exclusion (banned region +
    # banned regional units + small islands) merged into a single geometry,
    # so testing a cell against it is one intersects()/difference() call
    # rather than three separate feature-set queries.
    wind_hard_exclusion: BaseGeometry
    unesco_points: list[tuple[str, Point]]


def load_constraint_layers(source_dir: Path) -> ConstraintLayers:
    natura_2000 = _load_geojson(source_dir / "natura_2000.geojson")
    natura_2000_geometries = [shape(f["geometry"]) for f in natura_2000["features"]]

    admin_regions = _load_geojson(source_dir / "admin_regions.geojson")
    banned_region_geometries = [
        shape(f["geometry"])
        for f in admin_regions["features"]
        if f["properties"].get("id") in WIND_BANNED_REGIONS
    ]

    regional_units = _load_geojson(source_dir / "regional_units.geojson")
    banned_regional_unit_geometries = [
        shape(f["geometry"])
        for f in regional_units["features"]
        if any(s in (f["properties"].get("name") or "") for s in WIND_BANNED_REGIONAL_UNIT_SUBSTRINGS)
    ]

    islands = _load_geojson(source_dir / "greek_islands.geojson")
    small_island_geometries = [
        shape(f["geometry"])
        for f in islands["features"]
        if (f["properties"].get("area_km2") or 0) < WIND_ISLAND_AREA_THRESHOLD_KM2
    ]

    wind_hard_exclusion_parts = (
        banned_region_geometries + banned_regional_unit_geometries + small_island_geometries
    )
    wind_hard_exclusion = unary_union(wind_hard_exclusion_parts) if wind_hard_exclusion_parts else shape(
        {"type": "GeometryCollection", "geometries": []}
    )

    unesco = _load_geojson(source_dir / "unesco_sites_greece.geojson")
    unesco_points = [
        (f["properties"]["name"], shape(f["geometry"])) for f in unesco["features"]
    ]

    return ConstraintLayers(
        natura_2000_geometries=natura_2000_geometries,
        natura_2000_index=STRtree(natura_2000_geometries),
        wind_hard_exclusion=wind_hard_exclusion,
        unesco_points=unesco_points,
    )


@dataclass(frozen=True)
class CellConstraintResult:
    # The real buildable land left in this cell for this technology, after
    # subtracting whatever is a hard exclusion for it. None if nothing was
    # subtracted (the common case -- most cells touch no hard exclusion).
    buildable_geometry: BaseGeometry | None
    buildable_fraction: float  # 1.0 when buildable_geometry is None
    hard_excluded: bool  # buildable_fraction < MIN_BUILDABLE_FRACTION
    natura_2000_overlap_fraction: float  # of the ORIGINAL cell, always computed (both technologies)
    natura_2000_conditional_warning: bool  # wind only: overlap exists but isn't a ban
    nearest_unesco_site_name: str | None
    nearest_unesco_site_km: float | None
    unesco_study_trigger_warning: bool  # solar only: within the study-trigger radius


def _natura_2000_union_for_cell(cell_shape: BaseGeometry, layers: ConstraintLayers) -> BaseGeometry | None:
    match_indices = layers.natura_2000_index.query(cell_shape, predicate="intersects")
    if len(match_indices) == 0:
        return None
    return unary_union([layers.natura_2000_geometries[i] for i in match_indices])


def _distance_km(point: Point, other: Point) -> float:
    reference_latitude = (point.y + other.y) / 2
    km_per_degree_lon = KM_PER_DEGREE_LAT * abs(_cos_deg(reference_latitude))
    dx_km = (point.x - other.x) * km_per_degree_lon
    dy_km = (point.y - other.y) * KM_PER_DEGREE_LAT
    return (dx_km**2 + dy_km**2) ** 0.5


def _cos_deg(degrees: float) -> float:
    from math import cos, radians

    return cos(radians(degrees))


def _nearest_unesco(centroid: Point, layers: ConstraintLayers) -> tuple[str, float] | None:
    if not layers.unesco_points:
        return None
    distances = [(_distance_km(centroid, point), name) for name, point in layers.unesco_points]
    distance_km, name = min(distances)
    return name, distance_km


def evaluate_cell(
    cell_shape: BaseGeometry,
    technology: str,
    layers: ConstraintLayers,
) -> CellConstraintResult:
    """The one entry point generate_candidates.py calls per grid cell, once
    its technology (Solar PV / Onshore Wind) is already decided. Everything
    technology-specific -- what's a hard exclusion versus a warning -- is
    decided here, in one place, rather than scattered through the caller."""
    centroid = cell_shape.centroid
    natura_union = _natura_2000_union_for_cell(cell_shape, layers)
    natura_overlap_fraction = (
        cell_shape.intersection(natura_union).area / cell_shape.area if natura_union is not None else 0.0
    )

    nearest_unesco = _nearest_unesco(centroid, layers)
    nearest_unesco_name = nearest_unesco[0] if nearest_unesco else None
    nearest_unesco_km = nearest_unesco[1] if nearest_unesco else None

    is_solar = "Solar" in technology
    buildable_geometry: BaseGeometry | None = None

    if is_solar:
        # Absolute ban -- subtract every intersecting Natura 2000 polygon from
        # the candidate's own geometry, not just flag it.
        if natura_union is not None:
            buildable_geometry = cell_shape.difference(natura_union)
        natura_conditional_warning = False
        unesco_warning = nearest_unesco_km is not None and nearest_unesco_km <= SOLAR_UNESCO_STUDY_TRIGGER_KM
    else:
        # Wind: Natura 2000 is conditional licensing (Law 4685/2020), not a
        # ban -- reported, never clipped. The real hard exclusion is region/
        # island based instead.
        if cell_shape.intersects(layers.wind_hard_exclusion):
            buildable_geometry = cell_shape.difference(layers.wind_hard_exclusion)
        natura_conditional_warning = natura_overlap_fraction > 0.0
        unesco_warning = False  # no cited wind-specific UNESCO distance rule

    if buildable_geometry is not None:
        buildable_fraction = buildable_geometry.area / cell_shape.area
    else:
        buildable_fraction = 1.0

    return CellConstraintResult(
        buildable_geometry=buildable_geometry,
        buildable_fraction=buildable_fraction,
        hard_excluded=buildable_fraction < MIN_BUILDABLE_FRACTION,
        natura_2000_overlap_fraction=round(natura_overlap_fraction, 4),
        natura_2000_conditional_warning=natura_conditional_warning,
        nearest_unesco_site_name=nearest_unesco_name,
        nearest_unesco_site_km=round(nearest_unesco_km, 2) if nearest_unesco_km is not None else None,
        unesco_study_trigger_warning=unesco_warning,
    )
