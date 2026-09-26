import json
import sys
from math import cos, radians
from pathlib import Path

from shapely.geometry import mapping, shape

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pipeline.land_constraints import evaluate_cell, load_constraint_layers

SOURCE_DIR = BASE_DIR / "data" / "source"
GENERATED_DIR = BASE_DIR / "data" / "generated"
OUTPUT_PATH = GENERATED_DIR / "candidate_cells.geojson"

# A simple square grid keeps the first generation step easy to inspect. Each
# cell's geometry is no longer necessarily this full square, though -- see
# land_constraints.evaluate_cell, called below, which clips it down to the
# real buildable land left once hard exclusions (Natura 2000 for solar,
# banned regions/regional units/small islands for wind) are subtracted.
GRID_STEP_DEGREES = 0.45

# Below this, a cell's remaining buildable land isn't a real candidate site --
# dropped entirely (land_constraints.MIN_BUILDABLE_FRACTION). Below this
# (higher) threshold, it's still real and kept, but flagged for review: most
# of the cell was lost to a hard exclusion, same screening-tool-threshold
# reasoning the old (single, cruder) 15%-Natura-overlap cutoff used -- not a
# legal figure, a real siting decision would evaluate the specific
# development footprint, not the whole grid cell.
CONSTRAINT_REVIEW_BUILDABLE_FRACTION_THRESHOLD = 0.5


def load_geojson(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as geojson_file:
        return json.load(geojson_file)


def main():
    region = load_geojson(SOURCE_DIR / "region_boundary.geojson")
    substations = load_geojson(SOURCE_DIR / "substations.geojson")
    lines = load_geojson(SOURCE_DIR / "transmission_lines.geojson")
    resource_zones = load_geojson(SOURCE_DIR / "resource_zones.geojson")
    # Real Natura 2000, admin-region, regional-unit and island data -- see
    # land_constraints.py's module docstring for the cited government siting
    # framework these back. Loaded once; each layer's own index/union is built
    # inside load_constraint_layers, not per grid cell.
    constraint_layers = load_constraint_layers(SOURCE_DIR)

    region_polygon = region["features"][0]["geometry"]["coordinates"][0]
    region_bbox = get_polygon_bbox(region_polygon)

    generated_features = []
    dropped_hard_excluded_count = 0
    candidate_index = 1
    x = region_bbox["min_x"]

    while x < region_bbox["max_x"]:
        y = region_bbox["min_y"]

        while y < region_bbox["max_y"]:
            cell_polygon = build_square_polygon(x, y, GRID_STEP_DEGREES)
            centroid = get_polygon_centroid(cell_polygon)

            # Keep cells that intersect the screening region, not just cells whose
            # centroid lands inside it. This makes the grid behave more like a
            # real screening layer around the region edges.
            if not polygons_intersect(cell_polygon, region_polygon):
                y += GRID_STEP_DEGREES
                continue

            solar_score, wind_score = get_resource_scores(centroid, resource_zones)
            technology = "Solar PV" if solar_score >= wind_score else "Onshore Wind"
            distance_to_substation_km = get_min_point_distance_km(
                centroid,
                substations["features"],
            )
            distance_to_line_km = get_min_line_distance_km(
                centroid,
                lines["features"],
            )

            cell_shape = shape({"type": "Polygon", "coordinates": [cell_polygon]})
            constraint_result = evaluate_cell(cell_shape, technology, constraint_layers)

            # Nothing left worth calling a candidate -- e.g. a wind cell fully
            # inside Attica, or a solar cell fully inside a Natura 2000 site.
            # Dropped rather than emitted as a degenerate near-empty polygon.
            if constraint_result.hard_excluded:
                dropped_hard_excluded_count += 1
                y += GRID_STEP_DEGREES
                continue

            candidate_geometry = (
                constraint_result.buildable_geometry
                if constraint_result.buildable_geometry is not None
                else cell_shape
            )
            excluded = (
                constraint_result.buildable_fraction
                < CONSTRAINT_REVIEW_BUILDABLE_FRACTION_THRESHOLD
            )
            connection_cost_level = get_connection_cost_level(
                distance_to_substation_km,
                distance_to_line_km,
            )
            investment_score = calculate_investment_score(
                technology=technology,
                solar_score=solar_score,
                wind_score=wind_score,
                distance_to_substation_km=distance_to_substation_km,
                distance_to_line_km=distance_to_line_km,
                connection_cost_level=connection_cost_level,
                excluded=excluded,
            )

            generated_features.append(
                build_candidate_feature(
                    candidate_index=candidate_index,
                    candidate_geometry=candidate_geometry,
                    technology=technology,
                    solar_score=solar_score,
                    wind_score=wind_score,
                    distance_to_substation_km=distance_to_substation_km,
                    distance_to_line_km=distance_to_line_km,
                    excluded=excluded,
                    buildable_fraction=constraint_result.buildable_fraction,
                    natura_2000_overlap_fraction=constraint_result.natura_2000_overlap_fraction,
                    natura_2000_conditional_warning=constraint_result.natura_2000_conditional_warning,
                    nearest_unesco_site_name=constraint_result.nearest_unesco_site_name,
                    nearest_unesco_site_km=constraint_result.nearest_unesco_site_km,
                    unesco_study_trigger_warning=constraint_result.unesco_study_trigger_warning,
                    connection_cost_level=connection_cost_level,
                    investment_score=investment_score,
                )
            )

            candidate_index += 1
            y += GRID_STEP_DEGREES

        x += GRID_STEP_DEGREES

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as output_file:
        json.dump(
            {
                "type": "FeatureCollection",
                "features": generated_features,
            },
            output_file,
            indent=2,
        )

    print(
        f"Generated {len(generated_features)} candidate cells at {OUTPUT_PATH} "
        f"({dropped_hard_excluded_count} grid cells dropped -- no meaningful buildable land left)"
    )


def build_candidate_feature(
    candidate_index: int,
    candidate_geometry,  # a shapely Polygon or MultiPolygon
    technology: str,
    solar_score: int,
    wind_score: int,
    distance_to_substation_km: float,
    distance_to_line_km: float,
    excluded: bool,
    buildable_fraction: float,
    natura_2000_overlap_fraction: float,
    natura_2000_conditional_warning: bool,
    nearest_unesco_site_name: str | None,
    nearest_unesco_site_km: float | None,
    unesco_study_trigger_warning: bool,
    connection_cost_level: str,
    investment_score: int,
) -> dict:
    candidate_id = f"cand-{candidate_index:03d}"

    return {
        "type": "Feature",
        "properties": {
            "id": candidate_id,
            "name": f"{technology} Candidate {candidate_index:03d}",
            "technology": technology,
            "solar_score": solar_score,
            "wind_score": wind_score,
            "distance_to_substation_km": round(distance_to_substation_km, 1),
            "distance_to_line_km": round(distance_to_line_km, 1),
            "excluded": excluded,
            "land_excluded": excluded,
            # The fraction of this grid cell that is actually buildable land
            # for this technology, after subtracting whatever is a hard
            # exclusion for it (1.0 = nothing was subtracted). The polygon's
            # own geometry already reflects this -- this is that same fact as
            # a number, for the UI/scoring to read without re-deriving it from
            # geometry area.
            "buildable_fraction": round(buildable_fraction, 4),
            "natura_2000_overlap_fraction": natura_2000_overlap_fraction,
            # Wind only: real (Law 4685/2020) conditional-licensing signal --
            # Natura 2000 overlap that is a warning, never a geometric
            # exclusion, for this technology. Always False for solar, where
            # any overlap is instead cut out of the geometry entirely.
            "natura_2000_conditional_warning": natura_2000_conditional_warning,
            # Solar only: real (news.gtp.gr-cited) mandatory-study trigger --
            # a warning, not an exclusion, so it never touches the geometry.
            "nearest_unesco_site_name": nearest_unesco_site_name,
            "nearest_unesco_site_km": nearest_unesco_site_km,
            "unesco_study_trigger_warning": unesco_study_trigger_warning,
            "connection_cost_level": connection_cost_level,
            "status": "Constraint Review" if excluded else "Screened Candidate",
            "investment_score": investment_score,
        },
        "geometry": mapping(candidate_geometry),
    }


def build_square_polygon(min_x: float, min_y: float, step: float) -> list[list[float]]:
    max_x = round(min_x + step, 6)
    max_y = round(min_y + step, 6)

    return [
        [round(min_x, 6), round(min_y, 6)],
        [max_x, round(min_y, 6)],
        [max_x, max_y],
        [round(min_x, 6), max_y],
        [round(min_x, 6), round(min_y, 6)],
    ]


def get_polygon_bbox(polygon: list[list[float]]) -> dict[str, float]:
    xs = [coordinate[0] for coordinate in polygon]
    ys = [coordinate[1] for coordinate in polygon]

    return {
        "min_x": min(xs),
        "max_x": max(xs),
        "min_y": min(ys),
        "max_y": max(ys),
    }


def get_polygon_centroid(polygon: list[list[float]]) -> tuple[float, float]:
    bbox = get_polygon_bbox(polygon)
    return (
        (bbox["min_x"] + bbox["max_x"]) / 2,
        (bbox["min_y"] + bbox["max_y"]) / 2,
    )


def point_in_polygon(point: tuple[float, float], polygon: list[list[float]]) -> bool:
    # Ray casting is enough for the simple local polygons used in this pipeline.
    x, y = point
    inside = False

    for start, end in zip(polygon, polygon[1:]):
        x1, y1 = start
        x2, y2 = end

        intersects = ((y1 > y) != (y2 > y)) and (
            x < ((x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9)) + x1
        )

        if intersects:
            inside = not inside

    return inside


def get_resource_scores(
    centroid: tuple[float, float],
    resource_zones: dict,
) -> tuple[int, int]:
    for zone in resource_zones["features"]:
        zone_polygon = zone["geometry"]["coordinates"][0]

        if point_in_polygon(centroid, zone_polygon):
            return (
                int(zone["properties"]["solar_score"]),
                int(zone["properties"]["wind_score"]),
            )

    return (60, 60)


def polygons_intersect(left_polygon: list[list[float]], right_polygon: list[list[float]]) -> bool:
    left_bbox = get_polygon_bbox(left_polygon)
    right_bbox = get_polygon_bbox(right_polygon)

    if not bboxes_intersect(left_bbox, right_bbox):
        return False

    if any(point_in_polygon(tuple(vertex), right_polygon) for vertex in left_polygon[:-1]):
        return True

    if any(point_in_polygon(tuple(vertex), left_polygon) for vertex in right_polygon[:-1]):
        return True

    for left_start, left_end in zip(left_polygon, left_polygon[1:]):
        for right_start, right_end in zip(right_polygon, right_polygon[1:]):
            if segments_intersect(
                tuple(left_start),
                tuple(left_end),
                tuple(right_start),
                tuple(right_end),
            ):
                return True

    return False


def bboxes_intersect(left: dict[str, float], right: dict[str, float]) -> bool:
    return not (
        left["max_x"] <= right["min_x"]
        or left["min_x"] >= right["max_x"]
        or left["max_y"] <= right["min_y"]
        or left["min_y"] >= right["max_y"]
    )


def segments_intersect(
    left_start: tuple[float, float],
    left_end: tuple[float, float],
    right_start: tuple[float, float],
    right_end: tuple[float, float],
) -> bool:
    left_one = point_orientation(left_start, left_end, right_start)
    left_two = point_orientation(left_start, left_end, right_end)
    right_one = point_orientation(right_start, right_end, left_start)
    right_two = point_orientation(right_start, right_end, left_end)

    if left_one == 0 and point_on_segment(right_start, left_start, left_end):
        return True

    if left_two == 0 and point_on_segment(right_end, left_start, left_end):
        return True

    if right_one == 0 and point_on_segment(left_start, right_start, right_end):
        return True

    if right_two == 0 and point_on_segment(left_end, right_start, right_end):
        return True

    return (left_one > 0) != (left_two > 0) and (right_one > 0) != (right_two > 0)


def point_orientation(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
    point_c: tuple[float, float],
) -> int:
    value = (
        (point_b[1] - point_a[1]) * (point_c[0] - point_b[0])
        - (point_b[0] - point_a[0]) * (point_c[1] - point_b[1])
    )

    if abs(value) < 1e-9:
        return 0

    return 1 if value > 0 else -1


def point_on_segment(
    point: tuple[float, float],
    segment_start: tuple[float, float],
    segment_end: tuple[float, float],
) -> bool:
    return (
        min(segment_start[0], segment_end[0]) <= point[0] <= max(segment_start[0], segment_end[0])
        and min(segment_start[1], segment_end[1]) <= point[1] <= max(segment_start[1], segment_end[1])
    )


def get_min_point_distance_km(point: tuple[float, float], features: list[dict]) -> float:
    distances = [
        approximate_distance_km(point, tuple(feature["geometry"]["coordinates"]))
        for feature in features
    ]
    return min(distances)


def get_min_line_distance_km(point: tuple[float, float], features: list[dict]) -> float:
    min_distance = None

    for feature in features:
        coordinates = feature["geometry"]["coordinates"]

        for start, end in zip(coordinates, coordinates[1:]):
            distance = distance_to_segment_km(point, tuple(start), tuple(end))

            if min_distance is None or distance < min_distance:
                min_distance = distance

    return min_distance if min_distance is not None else 0.0


def distance_to_segment_km(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    point_x, point_y = lon_lat_to_xy(point, point[1])
    start_x, start_y = lon_lat_to_xy(start, point[1])
    end_x, end_y = lon_lat_to_xy(end, point[1])

    dx = end_x - start_x
    dy = end_y - start_y

    if dx == 0 and dy == 0:
        return ((point_x - start_x) ** 2 + (point_y - start_y) ** 2) ** 0.5

    projection = (
        ((point_x - start_x) * dx) + ((point_y - start_y) * dy)
    ) / ((dx * dx) + (dy * dy))
    projection = max(0.0, min(1.0, projection))

    closest_x = start_x + projection * dx
    closest_y = start_y + projection * dy

    return ((point_x - closest_x) ** 2 + (point_y - closest_y) ** 2) ** 0.5


def approximate_distance_km(
    left: tuple[float, float],
    right: tuple[float, float],
) -> float:
    left_x, left_y = lon_lat_to_xy(left, (left[1] + right[1]) / 2)
    right_x, right_y = lon_lat_to_xy(right, (left[1] + right[1]) / 2)

    return ((right_x - left_x) ** 2 + (right_y - left_y) ** 2) ** 0.5


def lon_lat_to_xy(point: tuple[float, float], reference_latitude: float) -> tuple[float, float]:
    kilometers_per_degree_lat = 111.0
    kilometers_per_degree_lon = 111.0 * cos(radians(reference_latitude))

    return (
        point[0] * kilometers_per_degree_lon,
        point[1] * kilometers_per_degree_lat,
    )


def get_connection_cost_level(
    distance_to_substation_km: float,
    distance_to_line_km: float,
) -> str:
    combined_distance = distance_to_substation_km + distance_to_line_km

    if combined_distance <= 12:
        return "Low"

    if combined_distance <= 22:
        return "Medium"

    return "High"


def calculate_investment_score(
    technology: str,
    solar_score: int,
    wind_score: int,
    distance_to_substation_km: float,
    distance_to_line_km: float,
    connection_cost_level: str,
    excluded: bool,
) -> int:
    # The first scoring pass stays explicit on purpose so it is easy to tune later.
    base_resource_score = wind_score if "Wind" in technology else solar_score
    substation_penalty = distance_to_substation_km * 1.2
    line_penalty = distance_to_line_km * 0.8
    connection_penalty = (
        4 if connection_cost_level == "Low" else 12 if connection_cost_level == "Medium" else 22
    )
    exclusion_penalty = 35 if excluded else 0

    raw_score = (
        base_resource_score
        - substation_penalty
        - line_penalty
        - connection_penalty
        - exclusion_penalty
    )

    return max(0, min(100, round(raw_score)))


if __name__ == "__main__":
    main()
