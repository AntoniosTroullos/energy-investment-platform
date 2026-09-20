import unittest

from app.regional_demand import (
    build_monthly_allocation,
    get_regional_demand_allocation,
    load_regional_features,
    season_for_month,
)


class RegionalDemandAllocationTests(unittest.TestCase):
    def test_month_to_season_mapping(self):
        self.assertEqual(season_for_month(1), "winter")
        self.assertEqual(season_for_month(4), "spring")
        self.assertEqual(season_for_month(8), "summer")
        self.assertEqual(season_for_month(11), "autumn")

    def test_feature_table_covers_all_project_regions(self):
        features = load_regional_features()

        self.assertEqual(len(features), 13)
        self.assertEqual(
            {row["region_id"] for row in features},
            {
                "Attica",
                "Central_Greece",
                "Central_Macedonia",
                "Crete",
                "Eastern_Macedonia_Thrace",
                "Epirus",
                "Ionian_Islands",
                "North_Aegean",
                "Peloponnese",
                "South_Aegean",
                "Thessaly",
                "Western_Greece",
                "Western_Macedonia",
            },
        )

    def test_monthly_allocation_shares_sum_to_one(self):
        features = load_regional_features()

        for month in range(1, 13):
            allocation = build_monthly_allocation(features, month)
            self.assertAlmostEqual(
                sum(float(row["allocation_share"]) for row in allocation),
                1.0,
                places=9,
                msg=f"month={month}",
            )

    def test_august_tourism_increases_island_commercial_share(self):
        features = load_regional_features()
        january = build_monthly_allocation(features, 1)
        august = build_monthly_allocation(features, 8)

        def commercial_share(rows, region_id):
            row = next(row for row in rows if row["region_id"] == region_id)
            return float(row["commercial_share"])

        for region_id in ["Crete", "Ionian_Islands", "South_Aegean"]:
            self.assertGreater(
                commercial_share(august, region_id),
                commercial_share(january, region_id),
                msg=region_id,
            )

    def test_endpoint_preserves_national_load_and_returns_geojson(self):
        result = get_regional_demand_allocation(
            timestamp_utc="2026-08-01T12:00:00Z",
            national_load_mw=8500,
        )

        self.assertEqual(result.month, 8)
        self.assertEqual(result.season, "summer")
        self.assertEqual(len(result.regions), 13)
        self.assertEqual(result.regionsGeojson["type"], "FeatureCollection")
        self.assertEqual(len(result.regionsGeojson["features"]), 13)
        self.assertAlmostEqual(
            sum(region.allocatedLoadMw for region in result.regions),
            8500,
            places=2,
        )
        self.assertTrue(
            all(region.allocationShare > 0 for region in result.regions)
        )

    def test_fastapi_handler_returns_response_model(self):
        from app.main import regional_demand_allocation

        result = get_regional_demand_allocation(
            timestamp_utc="2026-01-01T00:00:00Z",
            national_load_mw=5000,
        )
        endpoint_result = regional_demand_allocation(
            timestamp_utc="2026-01-01T00:00:00Z",
            national_load_mw=5000,
        )

        self.assertEqual(result.nationalLoadMw, 5000)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.season, "winter")
        self.assertEqual(endpoint_result.nationalLoadMw, result.nationalLoadMw)
        self.assertEqual(len(endpoint_result.regions), 13)


if __name__ == "__main__":
    unittest.main()
