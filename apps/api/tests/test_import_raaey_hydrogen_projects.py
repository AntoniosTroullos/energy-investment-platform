import unittest

from pipeline.import_raaey_hydrogen_projects import (
    find_duplicate_official_feature,
    get_geometry_point,
)


class ImportRaaeyHydrogenProjectsTests(unittest.TestCase):
    def test_get_geometry_point_returns_weighted_polygon_centroid(self):
        geometry = {
            "type": "MultiPolygon",
            "coordinates": [
                [
                    [
                        [100.0, 100.0],
                        [120.0, 100.0],
                        [120.0, 120.0],
                        [100.0, 120.0],
                        [100.0, 100.0],
                    ]
                ]
            ],
        }

        centroid = get_geometry_point(geometry)

        self.assertEqual(centroid, (110.0, 110.0))

    def test_duplicate_detection_uses_existing_geometry_when_lat_lon_are_missing(self):
        existing_feature = {
            "type": "Feature",
            "properties": {
                "id": "hydrogen-project-motor-oil-korinthos",
                "name": "Motor Oil Korinthos Renewable Hydrogen Project",
                "operator": "Motor Oil",
                "electrolyzer_capacity_mw": 50,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [23.118, 37.923],
            },
        }
        official_feature = {
            "type": "Feature",
            "properties": {
                "id": "hydrogen-project-raaey-13",
                "name": "ΜΟΤΟΡ ΟΙΛ ΕΛΛΑΣ ΔΙΥΛΙΣΤΗΡΙΑ ΚΟΡΙΝΘΟΥ ΑΕ - ΣΟΥΣΑΚΙ",
                "operator": "ΜΟΤΟΡ ΟΙΛ ΕΛΛΑΣ ΔΙΥΛΙΣΤΗΡΙΑ ΚΟΡΙΝΘΟΥ ΑΕ",
                "municipality": "ΛΟΥΤΡΑΚΙΟΥ - ΠΕΡΑΧΩΡΑΣ - ΑΓΙΩΝ ΘΕΟΔΩΡΩΝ",
                "electrolyzer_capacity_mw": 50,
                "latitude": 37.922715,
                "longitude": 23.07956,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [23.07956, 37.922715],
            },
        }

        duplicate = find_duplicate_official_feature(existing_feature, [official_feature])

        self.assertIsNotNone(duplicate)
        self.assertEqual(duplicate["properties"]["id"], "hydrogen-project-raaey-13")


if __name__ == "__main__":
    unittest.main()
