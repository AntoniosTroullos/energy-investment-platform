import unittest
from unittest.mock import patch

from app.scenario_models import ElectricityScenarioResult, ScenarioMetrics
from app.scenarios import (
    REGION_METRIC_KEYS,
    _region_metric_values,
    get_scenario_regions_delta_geojson,
    get_scenario_regions_geojson,
)

FAKE_REGIONS = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "properties": {"id": "Attica", "name": "Attica"}, "geometry": {"type": "Point", "coordinates": [23.7, 38.0]}},
        {"type": "Feature", "properties": {"id": "Crete", "name": "Crete"}, "geometry": {"type": "Point", "coordinates": [25.0, 35.3]}},
    ],
}


def make_result(case_name: str, target_year: int, *, generation: dict, load: dict, price: dict, peak: dict) -> ElectricityScenarioResult:
    return ElectricityScenarioResult(
        case_name=case_name,
        target_year=target_year,
        solved=True,
        message="Optimization completed successfully.",
        objective_eur=1_000_000.0,
        metrics=ScenarioMetrics(
            generation_by_bus_mwh=generation,
            total_load_by_bus_mwh=load,
            average_marginal_price_by_bus=price,
            peak_load_by_bus_mw=peak,
        ),
    )


class RegionMetricValuesTests(unittest.TestCase):
    def test_net_position_is_generation_minus_load(self):
        metrics = ScenarioMetrics(
            generation_by_bus_mwh={"Attica": 8_000_000.0},
            total_load_by_bus_mwh={"Attica": 19_000_000.0},
        )
        values = _region_metric_values("Attica", metrics)
        self.assertEqual(values["net_position_mwh"], -11_000_000.0)

    def test_missing_generation_or_load_gives_none_net_position_not_a_crash(self):
        metrics = ScenarioMetrics(total_load_by_bus_mwh={"Attica": 19_000_000.0})
        values = _region_metric_values("Attica", metrics)
        self.assertIsNone(values["net_position_mwh"])

    def test_unknown_bus_gives_all_none_values(self):
        values = _region_metric_values("Nowhere", ScenarioMetrics())
        self.assertTrue(all(value is None for value in values.values()))

    def test_covers_every_declared_region_metric_key(self):
        values = _region_metric_values("Attica", ScenarioMetrics())
        self.assertEqual(set(values.keys()), set(REGION_METRIC_KEYS))


class GetScenarioRegionsGeojsonTests(unittest.TestCase):
    def test_joins_metrics_onto_every_region_feature(self):
        result = make_result(
            "future_electricity_2030", 2030,
            generation={"Attica": 8_000_000.0, "Crete": 4_700_000.0},
            load={"Attica": 19_000_000.0, "Crete": 3_600_000.0},
            price={"Attica": 81.7, "Crete": 81.2},
            peak={"Attica": 3000.0, "Crete": 900.0},
        )
        with patch("app.scenarios.get_scenario_result", return_value=result), \
             patch("app.scenarios.network_topology.get_simplified_admin_regions", return_value=FAKE_REGIONS):
            geojson = get_scenario_regions_geojson("future_electricity_2030")

        by_id = {f["properties"]["id"]: f["properties"] for f in geojson["features"]}
        self.assertEqual(by_id["Attica"]["scenario_case_name"], "future_electricity_2030")
        self.assertEqual(by_id["Attica"]["net_position_mwh"], -11_000_000.0)
        self.assertEqual(by_id["Crete"]["net_position_mwh"], 1_100_000.0)
        # The source feature's own properties (name) must survive alongside
        # the injected metric ones, not be replaced by them.
        self.assertEqual(by_id["Attica"]["name"], "Attica")


class GetScenarioRegionsDeltaGeojsonTests(unittest.TestCase):
    def test_delta_is_b_minus_a_for_every_metric(self):
        result_a = make_result(
            "future_electricity_2030", 2030,
            generation={"Attica": 8_000_000.0}, load={"Attica": 19_000_000.0},
            price={"Attica": 81.7}, peak={"Attica": 3000.0},
        )
        result_b = make_result(
            "future_electricity_2050", 2050,
            generation={"Attica": 9_500_000.0}, load={"Attica": 21_000_000.0},
            price={"Attica": 85.0}, peak={"Attica": 3200.0},
        )

        def fake_get_scenario_result(case_name):
            return {"future_electricity_2030": result_a, "future_electricity_2050": result_b}[case_name]

        with patch("app.scenarios.get_scenario_result", side_effect=fake_get_scenario_result), \
             patch("app.scenarios.network_topology.get_simplified_admin_regions", return_value=FAKE_REGIONS):
            geojson = get_scenario_regions_delta_geojson("future_electricity_2030", "future_electricity_2050")

        attica = next(f["properties"] for f in geojson["features"] if f["properties"]["id"] == "Attica")
        self.assertEqual(attica["scenario_case_name_a"], "future_electricity_2030")
        self.assertEqual(attica["scenario_case_name_b"], "future_electricity_2050")
        self.assertEqual(attica["generation_mwh_a"], 8_000_000.0)
        self.assertEqual(attica["generation_mwh_b"], 9_500_000.0)
        self.assertEqual(attica["generation_mwh_delta"], 1_500_000.0)
        self.assertEqual(attica["average_marginal_price_eur_per_mwh_delta"], 85.0 - 81.7)

    def test_a_region_missing_from_one_case_gets_none_deltas_not_a_crash(self):
        result_a = make_result("case_a", 2030, generation={}, load={}, price={}, peak={})
        result_b = make_result("case_b", 2050, generation={"Attica": 1.0}, load={}, price={}, peak={})

        def fake_get_scenario_result(case_name):
            return {"case_a": result_a, "case_b": result_b}[case_name]

        with patch("app.scenarios.get_scenario_result", side_effect=fake_get_scenario_result), \
             patch("app.scenarios.network_topology.get_simplified_admin_regions", return_value=FAKE_REGIONS):
            geojson = get_scenario_regions_delta_geojson("case_a", "case_b")

        attica = next(f["properties"] for f in geojson["features"] if f["properties"]["id"] == "Attica")
        self.assertIsNone(attica["generation_mwh_delta"])
        self.assertEqual(attica["generation_mwh_b"], 1.0)


if __name__ == "__main__":
    unittest.main()
