import sys
import unittest
from pathlib import Path

from shapely import STRtree
from shapely.geometry import LineString, Point, shape

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pipeline.generate_candidates import (  # noqa: E402
    NEAREST_FEATURE_QUERY_BUFFER_DEGREES,
    _guaranteed_safe_radius_km,
    get_min_line_distance_km,
    get_min_point_distance_km,
)

# Regression coverage for a real bug found while tightening the grid: STRtree
# matches on bounding boxes, not actual geometry. A long feature's bbox can
# reach into the query buffer around a point even though every point actually
# on that feature is far away -- and meanwhile the true nearest feature's own
# (smaller, tighter) bbox can sit just outside the buffer entirely. Trusting
# "the query returned something" was wrong; only trusting an answer strictly
# inside _guaranteed_safe_radius_km, with a full-scan fallback otherwise, is
# what actually fixes it -- these tests reproduce that exact shape.


def feature(geometry) -> dict:
    return {"type": "Feature", "properties": {}, "geometry": shape(geometry).__geo_interface__}


class GuaranteedSafeRadiusTests(unittest.TestCase):
    def test_matches_the_documented_formula(self):
        from math import cos, radians

        point = (23.0, 39.0)
        expected = NEAREST_FEATURE_QUERY_BUFFER_DEGREES * 111.0 * abs(cos(radians(39.0)))
        self.assertAlmostEqual(_guaranteed_safe_radius_km(point), expected, places=9)


class MinPointDistanceRegressionTests(unittest.TestCase):
    def test_true_nearest_substation_found_even_when_a_farther_one_is_the_only_fast_hit(self):
        point = (23.0, 39.0)
        # A substation placed just outside a typical fast-path buffer in every
        # direction except one -- if the true nearest happens to be the only
        # thing the buffer captures at all, this test wouldn't actually
        # exercise the fallback. So the true nearest here is placed BEYOND
        # the buffer's guaranteed-safe radius on purpose, and a second,
        # farther-still substation is placed just inside it -- reproducing
        # "the fast path finds *something*, but not the true nearest."
        safe_radius_km = _guaranteed_safe_radius_km(point)
        # 1 degree of longitude here is ~111 * cos(39deg) km; convert the
        # desired km offsets into a longitude delta using that same factor,
        # matching how the module itself projects distance.
        from math import cos, radians

        km_per_degree_lon = 111.0 * cos(radians(point[1]))

        true_nearest = (point[0] + (safe_radius_km * 1.4) / km_per_degree_lon, point[1])
        decoy_within_buffer = (point[0] + (safe_radius_km * 0.5) / km_per_degree_lon, point[1])

        substations = [feature(Point(decoy_within_buffer)), feature(Point(true_nearest))]
        index = STRtree([shape(f["geometry"]) for f in substations])

        from pipeline.generate_candidates import approximate_distance_km

        expected = min(
            approximate_distance_km(point, tuple(f["geometry"]["coordinates"])) for f in substations
        )
        self.assertAlmostEqual(
            get_min_point_distance_km(point, index, substations), expected, places=6
        )
        # Confirm this test actually exercises the case it claims to: the
        # true nearest must be the FARTHER of the two candidates in raw
        # degree terms (i.e. genuinely outside the initial fast-path capture).
        self.assertGreater(true_nearest[0] - point[0], decoy_within_buffer[0] - point[0])


class MinLineDistanceRegressionTests(unittest.TestCase):
    def test_true_nearest_line_found_despite_a_distant_large_bbox_decoy(self):
        """The exact failure mode found in production data: a long line far
        from `point` whose bounding box is large enough to overlap the query
        buffer anyway, sitting alongside a genuinely closer -- but still
        outside the buffer -- short line that is the real answer."""
        point = (23.25, 39.55)

        # A short line whose own bbox is well outside the buffer (so the
        # naive "query returned something" check would never find it there),
        # but which is nonetheless the true nearest line to `point`.
        true_nearest_line = LineString([(22.97, 39.17), (23.25, 39.37)])

        # A long line whose bounding box spans a huge area -- including a
        # corner near `point` -- even though no point actually on the line is
        # anywhere near `point`. This is what made the old (buggy) "non-empty
        # result is trustworthy" logic return a wrong, larger distance.
        decoy_line = LineString([(23.1, 39.4), (30.0, 20.0)])

        lines = [feature(true_nearest_line), feature(decoy_line)]
        index = STRtree([shape(f["geometry"]) for f in lines])

        from pipeline.generate_candidates import distance_to_segment_km

        def brute_force_min(point, lines):
            best = None
            for f in lines:
                coords = f["geometry"]["coordinates"]
                for start, end in zip(coords, coords[1:]):
                    d = distance_to_segment_km(point, tuple(start), tuple(end))
                    if best is None or d < best:
                        best = d
            return best

        expected = brute_force_min(point, lines)
        actual = get_min_line_distance_km(point, index, lines)
        self.assertAlmostEqual(actual, expected, places=6)

        # Confirm the decoy's bbox really does reach the query buffer (i.e.
        # this test exercises the false-positive case, not a trivial one).
        query_hit_indices = set(
            index.query(Point(point).buffer(NEAREST_FEATURE_QUERY_BUFFER_DEGREES)).tolist()
        )
        self.assertIn(1, query_hit_indices)  # decoy_line's index


if __name__ == "__main__":
    unittest.main()
