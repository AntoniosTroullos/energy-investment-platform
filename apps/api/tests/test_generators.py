import unittest

from app.generators import (
    POWER_PLANTS_SOURCE_PATH,
    build_canonical_generator_feature,
    filter_feature_collection,
    get_file_timestamp,
    get_generators_feature_collection,
    get_generators_missing_capacity,
    get_generators_quality_pumped_hydro,
    get_generators_sources_coverage,
    get_generators_summary_storage,
    get_generators_summary_by_technology,
    is_line_feature_in_greece,
    is_point_feature_in_greece,
    map_technology_category,
    merge_generator_features,
    normalize_generator_technology,
    parse_capacity_to_mw,
    should_include_canonical_generator_feature,
)
from app.main import plants

ATHENS_POINT = [23.7275, 37.9715]
ISTANBUL_POINT = [29.1306, 40.9354]


class CapacityParserTests(unittest.TestCase):
    def test_parses_supported_capacity_formats(self):
        self.assertEqual(parse_capacity_to_mw(500)["value_mw"], 500)
        self.assertEqual(parse_capacity_to_mw("500")["value_mw"], 500)
        self.assertEqual(parse_capacity_to_mw("500 MW")["value_mw"], 500)
        self.assertEqual(parse_capacity_to_mw("0.5 GW")["value_mw"], 500)
        self.assertEqual(parse_capacity_to_mw("500000 kW")["value_mw"], 500)
        self.assertEqual(parse_capacity_to_mw("500,5 MW")["value_mw"], 500.5)

    def test_handles_ambiguous_and_missing_capacity_values(self):
        ambiguous_result = parse_capacity_to_mw("1.456 MW")
        self.assertEqual(ambiguous_result["value_mw"], 1456)
        self.assertIn("ambiguous_capacity_separator", ambiguous_result["warnings"])
        self.assertIsNone(parse_capacity_to_mw(None)["value_mw"])
        self.assertIsNone(parse_capacity_to_mw("-")["value_mw"])


class TechnologyNormalizationTests(unittest.TestCase):
    def test_normalizes_internal_technology_values(self):
        self.assertEqual(normalize_generator_technology("photovoltaic"), "solar_pv")
        self.assertEqual(normalize_generator_technology("offshore wind"), "offshore_wind")
        self.assertEqual(normalize_generator_technology("conventional storage"), "hydro")
        self.assertEqual(normalize_generator_technology("pumped storage"), "pumped_hydro")
        self.assertEqual(
            normalize_generator_technology("hydroelectric pumped storage"),
            "pumped_hydro",
        )
        self.assertEqual(normalize_generator_technology("αντλησιοταμίευση"), "pumped_hydro")
        self.assertEqual(normalize_generator_technology("natural gas"), "gas")
        self.assertEqual(normalize_generator_technology("missing"), "unknown")

    def test_normal_hydro_is_not_misclassified(self):
        self.assertEqual(normalize_generator_technology("hydroelectric"), "hydro")
        self.assertEqual(normalize_generator_technology("small hydro"), "small_hydro")

    def test_maps_display_categories(self):
        self.assertEqual(map_technology_category("solar_pv"), "Solar")
        self.assertEqual(map_technology_category("offshore_wind"), "Wind")
        self.assertEqual(map_technology_category("battery_storage"), "Storage")
        self.assertEqual(map_technology_category("lignite"), "Lignite")
        self.assertEqual(map_technology_category("biogas"), "Biomass/Biogas")
        self.assertEqual(map_technology_category("unknown"), "Other/Unknown")

    def test_recovers_greek_lignite_from_known_station_names(self):
        self.assertEqual(
            normalize_generator_technology("coal"),
            "coal",
        )
        feature = {
            "type": "Feature",
            "properties": {
                "id": "osm-lignite-1",
                "name": "Ατμοηλεκτρικός Σταθμός Αγίου Δημητρίου",
                "operator": "ΔΕΗ",
                "technology": "coal",
                "primary_source": "OpenStreetMap",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [21.929858, 40.39219],
            },
        }

        canonical_feature = build_canonical_generator_feature(
            feature,
            get_file_timestamp(POWER_PLANTS_SOURCE_PATH),
        )

        self.assertEqual(
            canonical_feature["properties"]["technology"],
            "lignite",
        )
        self.assertEqual(
            canonical_feature["properties"]["technology_category"],
            "Lignite",
        )

    def test_excludes_non_greek_osm_power_plants_from_canonical_feed(self):
        feature = {
            "type": "Feature",
            "properties": {
                "id": "osm-foreign-1",
                "name": "Foreign Gas Plant",
                "operator": "Foreign Operator",
                "technology": "gas",
                "primary_source": "OpenStreetMap",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [29.073336, 40.293097],
            },
        }

        canonical_feature = build_canonical_generator_feature(
            feature,
            get_file_timestamp(POWER_PLANTS_SOURCE_PATH),
        )

        self.assertFalse(
            should_include_canonical_generator_feature(
                POWER_PLANTS_SOURCE_PATH,
                canonical_feature,
            )
        )


class GeneratorApiShapeTests(unittest.TestCase):
    def test_plants_endpoint_returns_canonical_fields(self):
        feature_collection = plants()
        self.assertEqual(feature_collection["type"], "FeatureCollection")
        self.assertGreater(len(feature_collection["features"]), 0)

        first_feature = feature_collection["features"][0]
        properties = first_feature["properties"]

        for key in [
            "id",
            "name",
            "technology",
            "technology_category",
            "carrier",
            "capacity_mw",
            "nominal_capacity_mw",
            "primary_source",
            "source_confidence",
            "latitude",
            "longitude",
        ]:
            self.assertIn(key, properties)

    def test_summary_by_technology_returns_expected_shape(self):
        summary = get_generators_summary_by_technology()
        self.assertGreater(len(summary), 0)

        first_row = summary[0]
        self.assertIn("technology_category", first_row)
        self.assertIn("count_assets", first_row)
        self.assertIn("total_nominal_capacity_mw", first_row)
        self.assertIn("count_missing_capacity", first_row)
        self.assertIn("count_missing_coordinates", first_row)

    def test_missing_capacity_quality_report_is_consistent(self):
        report = get_generators_missing_capacity()
        self.assertIn("count", report)
        self.assertIn("assets", report)
        self.assertEqual(report["count"], len(report["assets"]))

    def test_feature_collection_exposes_nominal_capacity_fields(self):
        feature_collection = get_generators_feature_collection()
        self.assertGreater(len(feature_collection["features"]), 0)

        for feature in feature_collection["features"][:25]:
            self.assertIn("technology_category", feature["properties"])
            self.assertIn("nominal_capacity_mw", feature["properties"])

    def test_sources_coverage_includes_global_energy_monitor(self):
        sources_coverage = get_generators_sources_coverage()
        source_names = {
            item["primary_source"] for item in sources_coverage["sources"]
        }

        self.assertIn("OpenStreetMap", source_names)
        self.assertIn("Global Energy Monitor", source_names)
        self.assertIn("RAAEY", source_names)
        self.assertIn("Greek Government Wind Registry", source_names)
        self.assertIn("Greek Government PV Registry", source_names)
        self.assertIn("Greek Government Storage Registry", source_names)

    def test_feature_collection_includes_gem_solar_records(self):
        feature_collection = get_generators_feature_collection()
        solar_features = [
            feature
            for feature in feature_collection["features"]
            if feature["properties"].get("source_dataset")
            == "Global Solar Power Tracker, February 2026 release"
        ]

        self.assertGreater(len(solar_features), 0)
        self.assertTrue(
            any(
                feature["properties"].get("technology") == "solar_pv"
                for feature in solar_features
            )
        )
        self.assertTrue(
            any(
                feature["properties"].get("display_on_map") is False
                for feature in solar_features
            )
        )

    def test_feature_collection_includes_gem_hydro_records(self):
        feature_collection = get_generators_feature_collection()
        hydro_features = [
            feature
            for feature in feature_collection["features"]
            if feature["properties"].get("source_dataset")
            == "Global Hydropower Tracker, March 2026 release"
        ]

        self.assertGreater(len(hydro_features), 0)
        self.assertTrue(
            any(
                feature["properties"].get("technology") in {"hydro", "pumped_hydro"}
                for feature in hydro_features
            )
        )

    def test_feature_collection_includes_biomass_phase_records(self):
        feature_collection = get_generators_feature_collection()
        biomass_features = [
            feature
            for feature in feature_collection["features"]
            if feature["properties"].get("primary_source") == "RAAEY"
            and feature["properties"].get("technology_category") == "Biomass/Biogas"
        ]

        self.assertGreater(len(biomass_features), 0)
        self.assertTrue(
            any(
                feature["geometry"] is not None
                for feature in biomass_features
            )
        )

    def test_feature_collection_includes_government_pv_records(self):
        feature_collection = get_generators_feature_collection()
        government_features = [
            feature
            for feature in feature_collection["features"]
            if feature["properties"].get("primary_source") == "Greek Government PV Registry"
        ]

        self.assertGreater(len(government_features), 0)
        first_feature = government_features[0]["properties"]
        self.assertEqual(first_feature["technology"], "solar_pv")
        self.assertIn(first_feature["status_category"], {"Operating", "Under Construction", "Planned", "Pre-Construction", "Announced"})

    def test_feature_collection_includes_official_amfilochia_seed(self):
        feature_collection = get_generators_feature_collection()
        amfilochia_features = [
            feature
            for feature in feature_collection["features"]
            if feature["properties"].get("id") == "official-pumped-hydro-amfilochia"
        ]

        self.assertEqual(len(amfilochia_features), 1)
        properties = amfilochia_features[0]["properties"]
        self.assertEqual(properties["technology"], "pumped_hydro")
        self.assertEqual(properties["technology_category"], "Storage")
        self.assertEqual(properties["nominal_capacity_mw"], 680)
        self.assertEqual(properties["generation_capacity_mw"], 680)
        self.assertEqual(properties["pumping_capacity_mw"], 730)

    def test_feature_collection_includes_government_storage_records(self):
        feature_collection = get_generators_feature_collection()
        storage_features = [
            feature
            for feature in feature_collection["features"]
            if feature["properties"].get("primary_source")
            == "Greek Government Storage Registry"
        ]

        self.assertGreater(len(storage_features), 0)
        first_properties = storage_features[0]["properties"]
        self.assertEqual(first_properties["technology_category"], "Storage")
        self.assertIn(first_properties["technology"], {"battery_storage", "pumped_hydro"})
        self.assertIn(first_properties["status_category"], {"Operating", "Under Construction"})

    def test_feature_collection_includes_government_wind_records(self):
        feature_collection = get_generators_feature_collection()
        wind_features = [
            feature
            for feature in feature_collection["features"]
            if feature["properties"].get("primary_source") == "Greek Government Wind Registry"
        ]

        self.assertGreater(len(wind_features), 0)
        first_properties = wind_features[0]["properties"]
        self.assertIn(first_properties["technology"], {"onshore_wind", "offshore_wind"})
        self.assertEqual(first_properties["technology_category"], "Wind")
        self.assertIn(
            first_properties["status_category"],
            {"Operating", "Under Construction", "Planned", "Announced"},
        )

    def test_merge_generator_features_prefers_higher_confidence_official_wind_source(self):
        gem_feature = {
            "type": "Feature",
            "properties": {
                "id": "gem-wind-1",
                "name": "Wind Alpha",
                "project_name": "Wind Alpha",
                "technology": "onshore_wind",
                "nominal_capacity_mw": 30.0,
                "latitude": 39.5,
                "longitude": 22.3,
                "primary_source": "Global Energy Monitor",
                "source": "Global Energy Monitor",
                "source_confidence": 3,
            },
            "geometry": {"type": "Point", "coordinates": [22.3, 39.5]},
        }
        official_feature = {
            "type": "Feature",
            "properties": {
                "id": "gov-wind-1",
                "name": "Wind Alpha Official",
                "project_name": "Wind Alpha",
                "technology": "onshore_wind",
                "nominal_capacity_mw": 30.0,
                "latitude": 39.5004,
                "longitude": 22.3004,
                "primary_source": "Greek Government Wind Registry",
                "source": "Greek Government Wind Registry",
                "source_confidence": 5,
                "wind_turbine_count_total": 6,
            },
            "geometry": {"type": "Point", "coordinates": [22.3004, 39.5004]},
        }

        merged_features = merge_generator_features([gem_feature, official_feature])

        self.assertEqual(len(merged_features), 1)
        merged_properties = merged_features[0]["properties"]
        self.assertEqual(
            merged_properties["primary_source"],
            "Greek Government Wind Registry",
        )
        self.assertEqual(merged_properties["wind_turbine_count_total"], 6)

    def test_merge_generator_features_does_not_merge_wind_into_solar(self):
        solar_feature = {
            "type": "Feature",
            "properties": {
                "id": "osm-solar-1",
                "name": "Kasidi 9",
                "project_name": "Kasidi 9",
                "technology": "solar_pv",
                "technology_category": "Solar",
                "nominal_capacity_mw": 9.0,
                "latitude": 37.98,
                "longitude": 23.72,
                "primary_source": "OpenStreetMap",
                "source": "OpenStreetMap",
                "source_confidence": 1,
            },
            "geometry": {"type": "Point", "coordinates": [23.72, 37.98]},
        }
        official_wind_feature = {
            "type": "Feature",
            "properties": {
                "id": "gov-wind-2",
                "name": "Ariadni 9",
                "project_name": "Kasidi 9",
                "technology": "onshore_wind",
                "technology_category": "Wind",
                "nominal_capacity_mw": 9.0,
                "latitude": 37.9804,
                "longitude": 23.7204,
                "primary_source": "Greek Government Wind Registry",
                "source": "Greek Government Wind Registry",
                "source_confidence": 5,
            },
            "geometry": {"type": "Point", "coordinates": [23.7204, 37.9804]},
        }

        merged_features = merge_generator_features([solar_feature, official_wind_feature])

        self.assertEqual(len(merged_features), 2)
        technologies = {feature["properties"]["technology"] for feature in merged_features}
        self.assertEqual(technologies, {"solar_pv", "onshore_wind"})

    def test_storage_summary_reports_generation_and_pumping_capacity(self):
        summary = get_generators_summary_storage()
        self.assertEqual(summary["technology_category"], "Storage")
        self.assertIn("total_generation_capacity_mw", summary)
        self.assertIn("total_pumping_capacity_mw", summary)

    def test_pumped_hydro_quality_report_tracks_missing_pumping_capacity(self):
        report = get_generators_quality_pumped_hydro()
        self.assertGreater(report["total_assets"], 0)
        self.assertIn("assets_missing_pumping_capacity", report)
        self.assertIn("assets_name_suggests_pumped_hydro_but_classified_otherwise", report)


class GeographicScopeFilterTests(unittest.TestCase):
    def test_point_feature_in_greece_accepts_athens_and_rejects_istanbul(self):
        athens_feature = {"geometry": {"type": "Point", "coordinates": ATHENS_POINT}}
        istanbul_feature = {"geometry": {"type": "Point", "coordinates": ISTANBUL_POINT}}

        self.assertTrue(is_point_feature_in_greece(athens_feature))
        self.assertFalse(is_point_feature_in_greece(istanbul_feature))

    def test_point_feature_without_point_geometry_is_not_excluded(self):
        non_point_feature = {"geometry": {"type": "LineString", "coordinates": []}}
        self.assertTrue(is_point_feature_in_greece(non_point_feature))

    def test_line_feature_is_kept_when_any_vertex_touches_greece(self):
        # Models a cross-border interconnector such as HVDC Italy-Greece,
        # which must not be excluded just because most of it lies abroad.
        interconnector_feature = {
            "geometry": {
                "type": "LineString",
                "coordinates": [ISTANBUL_POINT, ATHENS_POINT],
            }
        }
        self.assertTrue(is_line_feature_in_greece(interconnector_feature))

    def test_line_feature_is_excluded_when_no_vertex_touches_greece(self):
        foreign_feature = {
            "geometry": {
                "type": "LineString",
                "coordinates": [ISTANBUL_POINT, [29.5, 41.5]],
            }
        }
        self.assertFalse(is_line_feature_in_greece(foreign_feature))

    def test_filter_feature_collection_keeps_matching_features_only(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {"geometry": {"type": "Point", "coordinates": ATHENS_POINT}},
                {"geometry": {"type": "Point", "coordinates": ISTANBUL_POINT}},
            ],
        }

        filtered = filter_feature_collection(feature_collection, is_point_feature_in_greece)

        self.assertEqual(len(filtered["features"]), 1)
        self.assertEqual(
            filtered["features"][0]["geometry"]["coordinates"],
            ATHENS_POINT,
        )


if __name__ == "__main__":
    unittest.main()
