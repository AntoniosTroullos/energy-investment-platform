import unittest

from pipeline.import_government_photovoltaics_greece import (
    egsa87_to_wgs84,
    find_existing_duplicate,
    get_government_point,
    map_government_status,
)


class GovernmentPhotovoltaicsImportTests(unittest.TestCase):
    def test_maps_supported_government_statuses(self):
        operating = map_government_status("ΑΔΕΙΑ ΛΕΙΤΟΥΡΓΙΑΣ")
        self.assertEqual(operating["status"], "operating")
        self.assertEqual(operating["status_category"], "Operating")

        planned = map_government_status("ΑΔΕΙΑ ΠΑΡΑΓΩΓΗΣ")
        self.assertEqual(planned["status"], "production_license")
        self.assertEqual(planned["status_category"], "Planned")

        self.assertIsNone(map_government_status("ΑΠΟΡΡΙΠΤΙΚΗ ΑΠΟΦΑΣΗ"))
        self.assertIsNone(map_government_status("ΑΥΤΟΔΙΚΑΙΗ ΠΑΥΣΗ"))

    def test_extracts_polygon_bbox_center_from_wkt(self):
        point = get_government_point(
            "MULTIPOLYGON (((372985.5 4304933.56, 373139.82 4305315.44, 373592.73 4305056.06, 372985.5 4304933.56)))"
        )
        self.assertIsNotNone(point)
        self.assertAlmostEqual(point[0], 373289.115, places=3)
        self.assertAlmostEqual(point[1], 4305124.5, places=1)

    def test_converts_egsa87_point_into_greece_bounds(self):
        longitude, latitude = egsa87_to_wgs84(373289.115, 4305217.1)
        self.assertGreater(longitude, 19.0)
        self.assertLess(longitude, 30.0)
        self.assertGreater(latitude, 34.0)
        self.assertLess(latitude, 42.0)

    def test_duplicate_matching_uses_nearby_capacity_match(self):
        candidate = {
            "properties": {
                "id": "gov-pv-1",
                "name": "Gov Solar Alpha",
                "operator": "Gov Solar Alpha SA",
                "nominal_capacity_mw": 10.0,
                "latitude": 38.5,
                "longitude": 23.5,
            }
        }
        existing_feature = {
            "properties": {
                "id": "gem-solar-1",
                "name": "Gov Solar Alpha",
                "operator": "Gov Solar Alpha SA",
                "nominal_capacity_mw": 10.02,
                "latitude": 38.5008,
                "longitude": 23.5009,
            }
        }
        comparison_index = {
            "by_bucket": {"385|235": [existing_feature]},
            "by_name": {"gov solar alpha": [existing_feature]},
        }

        duplicate = find_existing_duplicate(
            candidate,
            [existing_feature],
            comparison_index,
        )
        self.assertIsNotNone(duplicate)
        self.assertEqual(duplicate["id"], "gem-solar-1")


if __name__ == "__main__":
    unittest.main()
