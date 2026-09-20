import tempfile
import unittest
from pathlib import Path

from app.biomass_phase1 import (
    apply_manual_entry_to_record,
    apply_manual_location_evidence,
    build_candidate_record,
    capacities_within_tolerance,
    derive_admie_status,
    detect_header_row_index,
    detect_column_bindings,
    normalize_manual_location_entry,
    find_possible_duplicates,
    normalize_biomass_technology,
    parse_biomass_capacity_to_mw,
    row_is_biomass_related,
)


class BiomassCapacityParserTests(unittest.TestCase):
    def test_parses_greek_and_metric_capacity_formats(self):
        self.assertEqual(parse_biomass_capacity_to_mw(1)["value_mw"], 1)
        self.assertEqual(parse_biomass_capacity_to_mw("1,5 MW")["value_mw"], 1.5)
        self.assertEqual(parse_biomass_capacity_to_mw("1.5 MW")["value_mw"], 1.5)
        self.assertEqual(parse_biomass_capacity_to_mw("2.996 MW")["value_mw"], 2.996)
        self.assertEqual(parse_biomass_capacity_to_mw("3.831 MW")["value_mw"], 3.831)
        self.assertEqual(parse_biomass_capacity_to_mw("1500 kW")["value_mw"], 1.5)
        self.assertEqual(parse_biomass_capacity_to_mw("0.001 GW")["value_mw"], 1)
        self.assertEqual(parse_biomass_capacity_to_mw("1.000 kW")["value_mw"], 1)
        self.assertEqual(parse_biomass_capacity_to_mw("1.000,5 kW")["value_mw"], 1.0005)

    def test_missing_capacity_stays_null(self):
        self.assertIsNone(parse_biomass_capacity_to_mw("-")["value_mw"])
        self.assertIsNone(parse_biomass_capacity_to_mw("")["value_mw"])
        self.assertIsNone(parse_biomass_capacity_to_mw(None)["value_mw"])
        self.assertIsNone(parse_biomass_capacity_to_mw("unknown")["value_mw"])


class BiomassNormalizationTests(unittest.TestCase):
    def test_normalizes_biogas_and_chp_logic(self):
        biogas_record = {"ΤΕΧΝΟΛΟΓΙΑ": "ΒΙΟΑΕΡΙΟ"}
        result = normalize_biomass_technology(biogas_record)
        self.assertEqual(result["technology"], "biogas")
        self.assertEqual(result["technology_category"], "Biomass/Biogas")

        chp_biomass_record = {"ΤΕΧΝΟΛΟΓΙΑ": "ΒΙΟΜΑΖΑ ΣΗΘΥΑ"}
        chp_biomass_result = normalize_biomass_technology(chp_biomass_record)
        self.assertEqual(chp_biomass_result["technology"], "biomass")
        self.assertTrue(chp_biomass_result["is_chp"])

        chp_only_record = {"ΤΕΧΝΟΛΟΓΙΑ": "ΣΗΘΥΑ"}
        chp_only_result = normalize_biomass_technology(chp_only_record)
        self.assertEqual(chp_only_result["technology"], "chp")
        self.assertEqual(chp_only_result["technology_category"], "CHP")

    def test_detects_biomass_related_rows(self):
        self.assertTrue(row_is_biomass_related({"ΤΕΧΝΟΛΟΓΙΑ": "ΒΙΟΜΑΖΑ"}))
        self.assertTrue(row_is_biomass_related({"Κατηγορία": "landfill gas"}))
        self.assertFalse(row_is_biomass_related({"ΤΕΧΝΟΛΟΓΙΑ": "ΑΙΟΛΙΚΑ"}))


class BiomassHeaderAndStatusTests(unittest.TestCase):
    def test_detects_raaey_header_row(self):
        rows = [
            ["ΤΙΤΛΟΣ", "", ""],
            ["ΑΙΤΗΣΗ", "ΕΤΑΙΡΕΙΑ", "ΤΕΧΝΟΛΟΓΙΑ", "ΕΓΚΑΤΕΣΤΗΜΕΝΗ ΙΣΧΥΣ (MW)", "ΔΗΜΟΣ"],
            ["A-1", "ΕΤΑΙΡΕΙΑ Α", "ΒΙΟΜΑΖΑ", "1,5", "ΑΘΗΝΑΙΩΝ"],
        ]
        self.assertEqual(detect_header_row_index(rows), 1)

    def test_raaey_only_record_does_not_become_operating(self):
        raw_record = {
            "ΑΙΤΗΣΗ": "A-1",
            "ΕΤΑΙΡΕΙΑ": "ΒΙΟΕΝΕΡΓΕΙΑ ΑΕ",
            "ΘΕΣΗ": "ΘΕΣΗ Α",
            "ΤΕΧΝΟΛΟΓΙΑ": "ΒΙΟΜΑΖΑ",
            "ΕΓΚΑΤΕΣΤΗΜΕΝΗ ΙΣΧΥΣ (MW)": "2,5",
            "ΔΗΜΟΣ": "ΘΕΡΜΗΣ",
        }
        bindings = detect_column_bindings(list(raw_record.keys()))
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "dummy.xlsx"
            temp_path.write_text("placeholder", encoding="utf-8")
            record = build_candidate_record(
                raw_record=raw_record,
                source_file="dummy.xlsx",
                source_sheet="ΑΔΕΙΕΣ",
                source_row_number=3,
                source_group="res_certificates",
                column_bindings=bindings,
                workbook_path=temp_path,
            )
        self.assertEqual(record["status"], "licensed")
        self.assertNotEqual(record["derived_status"], "operating")

    def test_admie_plus_evidence_maps_to_operating(self):
        self.assertEqual(
            derive_admie_status({"status_col": "+"}),
            "operating",
        )
        self.assertEqual(
            derive_admie_status({"status_col": "2"}),
            "connection_offer",
        )


class BiomassDuplicateTests(unittest.TestCase):
    def test_duplicate_detection_flags_same_license(self):
        base_record = {
            "id": "one",
            "license_id": "ΑΔ-1",
            "normalized_name": "beta energy",
            "municipality": "Κοζάνης",
            "owner": "ΒΗΤΑ ΕΝΕΡΓΕΙΑ",
            "nominal_capacity_mw": 2.0,
            "project_name": "ΕΡΓΟ Α",
            "regional_unit": "Κοζάνης",
        }
        other_record = {
            "id": "two",
            "license_id": "ΑΔ-1",
            "normalized_name": "beta energy",
            "municipality": "Κοζάνης",
            "owner": "ΒΗΤΑ ΕΝΕΡΓΕΙΑ",
            "nominal_capacity_mw": 2.05,
            "project_name": "ΕΡΓΟ Α",
            "regional_unit": "Κοζάνης",
        }
        duplicates = find_possible_duplicates([base_record, other_record])
        self.assertEqual(len(duplicates), 1)
        self.assertIn("same_license_id", duplicates[0]["reasons"])
        self.assertTrue(capacities_within_tolerance(2.0, 2.05))


class BiomassManualLocationTests(unittest.TestCase):
    def test_manual_entry_with_egsa87_coordinates_derives_wgs84_geometry(self):
        manual_entry = normalize_manual_location_entry(
            {
                "id": "manual-biomass-point-999",
                "license_id": "A-1",
                "name": "Test Plant",
                "x_egsa87": 396414.999,
                "y_egsa87": 4505410.003,
                "coordinate_system": "EGSA87",
                "evidence_type": "manual_geolocation",
            },
            999,
        )

        self.assertIsNotNone(manual_entry["latitude"])
        self.assertIsNotNone(manual_entry["longitude"])
        self.assertTrue(34 <= manual_entry["latitude"] <= 43)
        self.assertTrue(19 <= manual_entry["longitude"] <= 30)

    def test_manual_entry_with_wgs84_enriches_record_geometry(self):
        record = {
            "id": "raaey-biomass-001",
            "source_refs": [],
            "data_quality_flags": ["raaey_not_operating_evidence"],
            "latitude": None,
            "longitude": None,
            "geometry": None,
        }
        manual_entry = {
            "id": "manual-biomass-point-001",
            "latitude": 40.123,
            "longitude": 22.456,
            "x_egsa87": None,
            "y_egsa87": None,
            "coordinate_system": "WGS84",
            "evidence_type": "manual_geolocation",
            "notes": "Verified manually.",
            "license_id": "A-1",
            "name": "Test Plant",
        }
        applied_geometry = apply_manual_entry_to_record(record, manual_entry)
        self.assertTrue(applied_geometry)
        self.assertEqual(record["latitude"], 40.123)
        self.assertEqual(record["longitude"], 22.456)
        self.assertEqual(record["geometry"]["type"], "Point")
        self.assertIn("manual_geolocation_applied", record["data_quality_flags"])
        self.assertEqual(record["source_refs"][-1]["source_name"], "Manual biomass location evidence")

    def test_unmatched_manual_location_does_not_create_fake_record(self):
        records = [
            {
                "id": "raaey-biomass-001",
                "license_id": "A-1",
                "name": "Plant A",
                "project_name": "Plant A",
                "owner": "Owner A",
                "normalized_name": "plant a",
                "source_refs": [],
                "data_quality_flags": ["raaey_not_operating_evidence"],
                "latitude": None,
                "longitude": None,
                "geometry": None,
            }
        ]

        original_loader = apply_manual_location_evidence.__globals__["load_manual_biomass_points"]
        apply_manual_location_evidence.__globals__["load_manual_biomass_points"] = lambda: {
            "file_exists": True,
            "entries": [
                {
                    "id": "manual-biomass-point-001",
                    "license_id": None,
                    "name": None,
                    "normalized_name": None,
                    "latitude": None,
                    "longitude": None,
                    "x_egsa87": 217071.441,
                    "y_egsa87": 4383038.133,
                    "coordinate_system": "EGSA87",
                    "evidence_type": "manual_geolocation",
                    "notes": "User-supplied EGSA87 point.",
                }
            ],
            "warnings": [],
        }
        try:
            result = apply_manual_location_evidence(records)
        finally:
            apply_manual_location_evidence.__globals__["load_manual_biomass_points"] = original_loader

        self.assertEqual(len(records), 1)
        self.assertEqual(result["matched_records"], 0)
        self.assertEqual(len(result["unmatched_entries"]), 1)
        self.assertIsNone(records[0]["geometry"])


if __name__ == "__main__":
    unittest.main()
