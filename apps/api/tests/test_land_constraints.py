import json
import tempfile
import unittest
from pathlib import Path

from shapely.geometry import Point, box, mapping

from pipeline.land_constraints import (
    MIN_BUILDABLE_FRACTION,
    SOLAR_UNESCO_STUDY_TRIGGER_KM,
    WIND_ISLAND_AREA_THRESHOLD_KM2,
    evaluate_cell,
    load_constraint_layers,
)

# A throwaway constraint-layer tree, not the real (443-feature, 45MB) natura_2000
# file -- every test controls exactly what it's checking against.


def write_geojson(path: Path, features: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")


def feature(geometry, **properties) -> dict:
    return {"type": "Feature", "properties": properties, "geometry": mapping(geometry)}


class LandConstraintsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.source_dir = Path(self._tmp.name)

        # A real-shaped Attica-like polygon, a small island, one Natura site,
        # and one UNESCO point -- all synthetic coordinates, no real data.
        self.attica_box = box(23.5, 37.8, 24.1, 38.2)
        self.small_island = box(25.0, 36.0, 25.05, 36.05)  # tiny -> well under the km2 threshold
        self.natura_site = box(21.0, 39.0, 21.5, 39.5)
        self.unesco_point = Point(21.2, 39.2)  # inside the natura site, for a UNESCO-distance test

        write_geojson(
            self.source_dir / "natura_2000.geojson",
            [feature(self.natura_site, site_type="Habitats Directive Site")],
        )
        write_geojson(
            self.source_dir / "admin_regions.geojson",
            [feature(self.attica_box, id="Attica"), feature(box(20.0, 40.0, 20.5, 40.5), id="Central_Macedonia")],
        )
        write_geojson(
            self.source_dir / "regional_units.geojson",
            [feature(box(22.9, 40.55, 23.1, 40.7), name="Thessaloniki Regional Unit")],
        )
        write_geojson(
            self.source_dir / "greek_islands.geojson",
            [
                feature(self.small_island, name="Tiny Island", area_km2=5.0),
                feature(box(26.0, 35.0, 27.0, 36.0), name="Big Island", area_km2=1000.0),
            ],
        )
        write_geojson(
            self.source_dir / "unesco_sites_greece.geojson",
            [feature(self.unesco_point, name="Test Site")],
        )

        self.layers = load_constraint_layers(self.source_dir)

    # -- Solar: Natura 2000 is an absolute ban, geometrically subtracted --

    def test_solar_cell_overlapping_natura_gets_that_area_subtracted(self):
        cell = box(21.2, 39.2, 21.8, 39.8)  # half inside the natura site
        result = evaluate_cell(cell, "Solar PV", self.layers)

        self.assertIsNotNone(result.buildable_geometry)
        self.assertLess(result.buildable_fraction, 1.0)
        self.assertGreater(result.buildable_fraction, 0.0)
        # The remaining geometry must not still overlap the natura site.
        self.assertAlmostEqual(result.buildable_geometry.intersection(self.natura_site).area, 0.0, places=9)

    def test_solar_cell_entirely_inside_natura_is_hard_excluded(self):
        cell = box(21.1, 39.1, 21.4, 39.4)  # fully inside the natura site
        result = evaluate_cell(cell, "Solar PV", self.layers)

        self.assertTrue(result.hard_excluded)
        self.assertLess(result.buildable_fraction, MIN_BUILDABLE_FRACTION)

    def test_solar_cell_untouched_by_natura_keeps_full_geometry(self):
        cell = box(24.5, 38.5, 25.0, 39.0)  # nowhere near the natura site
        result = evaluate_cell(cell, "Solar PV", self.layers)

        self.assertIsNone(result.buildable_geometry)
        self.assertEqual(result.buildable_fraction, 1.0)
        self.assertFalse(result.hard_excluded)
        self.assertEqual(result.natura_2000_overlap_fraction, 0.0)

    def test_solar_cell_far_from_unesco_site_is_not_a_warning(self):
        cell = box(24.5, 38.5, 25.0, 39.0)  # far from the fixture UNESCO point
        result = evaluate_cell(cell, "Solar PV", self.layers)

        # Confirms the trigger is real-distance-based, not always-on.
        self.assertFalse(result.unesco_study_trigger_warning)
        self.assertGreater(result.nearest_unesco_site_km, SOLAR_UNESCO_STUDY_TRIGGER_KM)

    def test_solar_near_unesco_site_triggers_study_warning(self):
        cell = box(21.15, 39.15, 21.25, 39.25)  # contains the UNESCO point itself
        result = evaluate_cell(cell, "Solar PV", self.layers)

        self.assertLessEqual(result.nearest_unesco_site_km, SOLAR_UNESCO_STUDY_TRIGGER_KM)
        self.assertTrue(result.unesco_study_trigger_warning)
        self.assertEqual(result.nearest_unesco_site_name, "Test Site")

    # -- Wind: Natura 2000 is a warning only, never clipped from geometry --

    def test_wind_cell_overlapping_natura_keeps_full_geometry_but_warns(self):
        cell = box(21.2, 39.2, 21.8, 39.8)  # same half-overlap cell as the solar test above
        result = evaluate_cell(cell, "Onshore Wind", self.layers)

        self.assertIsNone(result.buildable_geometry)  # Natura alone never clips wind
        self.assertEqual(result.buildable_fraction, 1.0)
        self.assertGreater(result.natura_2000_overlap_fraction, 0.0)
        self.assertTrue(result.natura_2000_conditional_warning)
        self.assertFalse(result.hard_excluded)

    def test_wind_cell_in_banned_region_is_hard_excluded(self):
        cell = box(23.6, 37.9, 23.9, 38.1)  # inside the Attica fixture
        result = evaluate_cell(cell, "Onshore Wind", self.layers)

        self.assertTrue(result.hard_excluded)
        self.assertLess(result.buildable_fraction, MIN_BUILDABLE_FRACTION)

    def test_wind_cell_straddling_banned_region_border_keeps_the_outside_part(self):
        # Half inside Attica (23.5-24.1), half outside (24.1-24.7).
        cell = box(23.8, 37.9, 24.4, 38.1)
        result = evaluate_cell(cell, "Onshore Wind", self.layers)

        self.assertIsNotNone(result.buildable_geometry)
        self.assertGreater(result.buildable_fraction, 0.0)
        self.assertLess(result.buildable_fraction, 1.0)
        self.assertFalse(result.hard_excluded)
        # The remaining geometry must not still overlap Attica.
        self.assertAlmostEqual(result.buildable_geometry.intersection(self.attica_box).area, 0.0, places=9)

    def test_wind_cell_on_small_island_is_hard_excluded(self):
        cell = box(25.005, 36.005, 25.045, 36.045)  # fully inside the tiny island fixture
        result = evaluate_cell(cell, "Onshore Wind", self.layers)

        self.assertTrue(result.hard_excluded)

    def test_wind_cell_on_large_island_is_not_excluded_by_island_rule(self):
        cell = box(26.2, 35.2, 26.8, 35.8)  # inside the "Big Island" fixture (1000 km2)
        result = evaluate_cell(cell, "Onshore Wind", self.layers)

        self.assertFalse(result.hard_excluded)
        self.assertIsNone(result.buildable_geometry)

    def test_wind_cell_in_banned_regional_unit_is_hard_excluded(self):
        cell = box(22.95, 40.58, 23.05, 40.65)  # inside the Thessaloniki fixture
        result = evaluate_cell(cell, "Onshore Wind", self.layers)

        self.assertTrue(result.hard_excluded)

    def test_wind_cell_far_from_every_exclusion_keeps_full_geometry(self):
        cell = box(28.0, 40.0, 28.5, 40.5)
        result = evaluate_cell(cell, "Onshore Wind", self.layers)

        self.assertIsNone(result.buildable_geometry)
        self.assertEqual(result.buildable_fraction, 1.0)
        self.assertFalse(result.hard_excluded)
        self.assertFalse(result.natura_2000_conditional_warning)


class LoadConstraintLayersTests(unittest.TestCase):
    def test_wind_hard_exclusion_threshold_is_the_real_cited_value(self):
        self.assertEqual(WIND_ISLAND_AREA_THRESHOLD_KM2, 300.0)


if __name__ == "__main__":
    unittest.main()
