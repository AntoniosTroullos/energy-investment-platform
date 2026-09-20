import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from pipeline.import_raaey_fossil_fuel_plants import (
    load_feature_collection_from_zip,
    map_status,
    normalize_fossil_technology,
)


class ImportRaaeyFossilFuelPlantsTests(unittest.TestCase):
    def test_maps_supported_fossil_statuses(self):
        operating = map_status("ΑΔΕΙΑ ΛΕΙΤΟΥΡΓΙΑΣ")
        self.assertEqual(operating["status"], "operating")
        self.assertEqual(operating["status_category"], "Operating")

        planned = map_status("ΑΔΕΙΑ ΠΑΡΑΓΩΓΗΣ")
        self.assertEqual(planned["status"], "production_license")
        self.assertEqual(planned["status_category"], "Planned")

        unknown = map_status("ΚΑΠΟΙΑ ΑΛΛΗ ΚΑΤΑΣΤΑΣΗ")
        self.assertEqual(unknown["status"], "unknown")
        self.assertEqual(unknown["status_category"], "Unknown")

    def test_normalizes_fossil_technology_from_text_hints(self):
        self.assertEqual(normalize_fossil_technology("μονάδα φυσικού αερίου"), "gas")
        self.assertEqual(normalize_fossil_technology("lignite station"), "lignite")
        self.assertEqual(normalize_fossil_technology("diesel unit"), "oil")
        self.assertEqual(normalize_fossil_technology("coal boiler"), "coal")
        self.assertEqual(normalize_fossil_technology("station without fuel hint"), "unknown")

    def test_loads_empty_feature_collection_from_official_zip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "official.zip"
            payload = {
                "type": "FeatureCollection",
                "features": [],
                "numberReturned": 0,
            }

            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("wfs", json.dumps(payload))
                archive.writestr("datapackage.json", "{}")

            feature_collection = load_feature_collection_from_zip(zip_path)

        self.assertEqual(feature_collection["type"], "FeatureCollection")
        self.assertEqual(feature_collection["features"], [])


if __name__ == "__main__":
    unittest.main()
