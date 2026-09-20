import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from pipeline.import_government_wind_greece import (
    load_feature_collection_from_zip,
    map_status,
    normalize_wind_technology,
    parse_total_decimal_count,
    parse_total_integer_count,
)


class GovernmentWindImportTests(unittest.TestCase):
    def test_maps_supported_wind_statuses(self):
        operating = map_status("ΑΔΕΙΑ ΛΕΙΤΟΥΡΓΙΑΣ")
        self.assertEqual(operating["status"], "operating")
        self.assertEqual(operating["status_category"], "Operating")

        planned = map_status("ΑΔΕΙΑ ΠΑΡΑΓΩΓΗΣ")
        self.assertEqual(planned["status"], "production_license")
        self.assertEqual(planned["status_category"], "Planned")

        announced = map_status("ΒΕΒΑΙΩΣΗ ΚΑΤΑΧΩΡΙΣΗΣ ΠΟΛΥΓΩΝΟΥ")
        self.assertEqual(announced["status_category"], "Announced")

    def test_normalizes_wind_technology(self):
        self.assertEqual(normalize_wind_technology("ξηρά"), "onshore_wind")
        self.assertEqual(normalize_wind_technology("offshore area"), "offshore_wind")

    def test_parses_turbine_counts(self):
        self.assertEqual(parse_total_integer_count("4 , 0 , 1"), 5)
        self.assertEqual(parse_total_decimal_count("6.40 , - , 1.60"), 8.0)
        self.assertIsNone(parse_total_integer_count("-"))

    def test_loads_feature_collection_from_zip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "wind.zip"
            payload = {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "properties": {}, "geometry": None}],
            }

            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("wfs", json.dumps(payload))

            loaded = load_feature_collection_from_zip(zip_path)

        self.assertEqual(loaded["type"], "FeatureCollection")
        self.assertEqual(len(loaded["features"]), 1)


if __name__ == "__main__":
    unittest.main()
