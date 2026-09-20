import unittest

from pipeline.import_government_storage_greece import (
    get_government_point,
    map_storage_status,
    normalize_storage_technology,
    normalize_yes_no,
)


class GovernmentStorageImportTests(unittest.TestCase):
    def test_maps_supported_storage_statuses(self):
        operating = map_storage_status("ΑΔΕΙΑ ΛΕΙΤΟΥΡΓΙΑΣ", "operation")
        self.assertEqual(operating["status"], "operating")
        self.assertEqual(operating["status_category"], "Operating")

        installation = map_storage_status("ΑΔΕΙΑ ΕΓΚΑΤΑΣΤΑΣΗΣ", "installation")
        self.assertEqual(installation["status"], "installation_license")
        self.assertEqual(installation["status_category"], "Under Construction")

        fallback_operation = map_storage_status(None, "operation")
        self.assertEqual(fallback_operation["status_category"], "Operating")

    def test_normalizes_storage_technologies(self):
        self.assertEqual(normalize_storage_technology("ΣΥΣΣΩΡΕΥΤΕΣ"), "battery_storage")
        self.assertEqual(normalize_storage_technology("ΣΥΣΣΩΡΕΥΕΤΣ"), "battery_storage")
        self.assertEqual(normalize_storage_technology("ΑΝΤΛΗΣΙΟΤΑΜΙΕΥΣΗ"), "pumped_hydro")

    def test_normalizes_yes_no(self):
        self.assertTrue(normalize_yes_no("ΝΑΙ"))
        self.assertFalse(normalize_yes_no("ΟΧΙ"))
        self.assertIsNone(normalize_yes_no(""))

    def test_extracts_polygon_bbox_center_from_wkt(self):
        point = get_government_point(
            "MULTIPOLYGON (((404797.77 4242635.45, 404782.14 4242661.70, 404810.01 4242636.06, 404797.77 4242635.45)))"
        )
        self.assertIsNotNone(point)
        self.assertAlmostEqual(point[0], 404796.075, places=3)
        self.assertAlmostEqual(point[1], 4242648.575, places=3)


if __name__ == "__main__":
    unittest.main()
