import unittest

from app.evaluation import get_source_layer_feature_collection
from app.main import hydrogen_pipelines, hydrogen_projects


class SourceLayerTests(unittest.TestCase):
    def test_hydrogen_projects_source_is_valid_feature_collection(self):
        feature_collection = get_source_layer_feature_collection(
            "hydrogen_projects.geojson"
        )

        self.assertEqual(feature_collection["type"], "FeatureCollection")
        self.assertGreater(len(feature_collection["features"]), 0)

        first_feature = feature_collection["features"][0]
        properties = first_feature["properties"]

        for key in [
            "id",
            "name",
            "project_type",
            "hydrogen_role",
            "status",
            "primary_source",
        ]:
            self.assertIn(key, properties)

    def test_hydrogen_projects_now_include_official_raaey_records(self):
        feature_collection = get_source_layer_feature_collection(
            "hydrogen_projects.geojson"
        )

        official_motor_oil = next(
            (
                feature
                for feature in feature_collection["features"]
                if feature["properties"].get("primary_source")
                == "RAAEY Hydrogen Registry"
                and "ΜΟΤΟΡ ΟΙΛ" in str(feature["properties"].get("name") or "")
            ),
            None,
        )

        self.assertIsNotNone(official_motor_oil)
        self.assertEqual(
            official_motor_oil["properties"].get("electrolyzer_capacity_mw"),
            50,
        )
        self.assertFalse(
            any(
                feature["properties"].get("id") == "hydrogen-project-motor-oil-korinthos"
                for feature in feature_collection["features"]
            )
        )

    def test_hydrogen_projects_endpoint_returns_backend_layer(self):
        feature_collection = hydrogen_projects()
        self.assertEqual(feature_collection["type"], "FeatureCollection")
        self.assertGreater(len(feature_collection["features"]), 0)

    def test_hydrogen_pipelines_source_is_valid_feature_collection(self):
        feature_collection = get_source_layer_feature_collection(
            "hydrogen_pipelines.geojson"
        )

        self.assertEqual(feature_collection["type"], "FeatureCollection")
        self.assertGreater(len(feature_collection["features"]), 0)

        first_feature = feature_collection["features"][0]
        properties = first_feature["properties"]

        for key in [
            "id",
            "name",
            "pipeline_code",
            "development_stage",
            "length_km",
            "primary_source",
        ]:
            self.assertIn(key, properties)

    def test_hydrogen_pipelines_endpoint_returns_backend_layer(self):
        feature_collection = hydrogen_pipelines()
        self.assertEqual(feature_collection["type"], "FeatureCollection")
        self.assertGreater(len(feature_collection["features"]), 0)

    def test_h2dria_csv_test_alignment_is_present(self):
        feature_collection = get_source_layer_feature_collection(
            "hydrogen_pipelines.geojson"
        )

        csv_test_feature = next(
            (
                feature
                for feature in feature_collection["features"]
                if feature["properties"].get("id")
                == "hydrogen-pipeline-h2dria-greek-part-test"
            ),
            None,
        )

        self.assertIsNotNone(csv_test_feature)
        self.assertEqual(
            csv_test_feature["properties"].get("pipeline_category"),
            "CSV Test Alignment",
        )
        self.assertEqual(csv_test_feature["geometry"]["type"], "LineString")
        self.assertGreater(len(csv_test_feature["geometry"]["coordinates"]), 700)


if __name__ == "__main__":
    unittest.main()
