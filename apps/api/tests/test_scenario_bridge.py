import json
import unittest
from pathlib import Path

from app.pypsa_bridge.normalize import normalize_electricity_result
from app.scenario_models import ScenarioMetrics

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# This fixture is a REAL scenario_result.json captured from a real solve
# (pythonProject1's run_multiyear_electricity.py, run under pypsa-greece's
# .venv314), not a hand-written mock. The point of this test is to fail
# loudly the moment that upstream, actively-evolving code changes this
# schema -- converting a silent runtime break (a frontend chart reading
# metrics.generation_by_carrier_mwh and getting undefined) into a red test.


class ScenarioBridgeNormalizationTests(unittest.TestCase):
    def setUp(self):
        fixture_path = FIXTURES_DIR / "scenario_result_electricity_sample.json"
        self.raw = json.loads(fixture_path.read_text(encoding="utf-8"))

    def test_real_fixture_has_the_expected_top_level_keys(self):
        for key in ["request", "solved", "message", "objective", "metrics"]:
            self.assertIn(key, self.raw, f"Upstream scenario_result.json is missing expected key '{key}'")

    def test_real_fixture_metrics_have_the_expected_keys(self):
        expected_metric_keys = set(ScenarioMetrics.model_fields.keys())
        actual_metric_keys = set(self.raw["metrics"].keys())
        missing = expected_metric_keys - actual_metric_keys
        self.assertFalse(
            missing,
            f"Upstream metrics.py no longer produces these expected keys: {missing}",
        )

    def test_normalize_electricity_result_round_trips_real_data(self):
        result = normalize_electricity_result("future_electricity_2035", self.raw)

        self.assertEqual(result.case_name, "future_electricity_2035")
        self.assertEqual(result.target_year, 2035)
        self.assertTrue(result.solved)
        self.assertIsInstance(result.objective_eur, float)
        self.assertGreater(result.objective_eur, 0)

        # Real carriers this project's baseline network always defines --
        # if these disappear, something upstream changed the technology set.
        for carrier in ["solar", "wind", "gas", "hydro"]:
            self.assertIn(carrier, result.metrics.installed_capacity_by_carrier_mw)

        # All 13 real Greek administrative regions must be present in every
        # per-bus metric -- a partial region set would silently break the
        # map choropleth join in app/scenarios.py.
        expected_buses = {
            "Attica", "Central_Greece", "Central_Macedonia", "Crete",
            "Eastern_Macedonia_Thrace", "Epirus", "Ionian_Islands",
            "North_Aegean", "Peloponnese", "South_Aegean", "Thessaly",
            "Western_Greece", "Western_Macedonia",
        }
        self.assertEqual(set(result.metrics.peak_load_by_bus_mw.keys()), expected_buses)

    def test_normalize_tolerates_unknown_new_metrics_keys(self):
        """A future upstream addition (e.g. a new metrics.py output) must
        surface via ScenarioMetrics's extra="allow", not raise."""
        raw_with_extra = {**self.raw, "metrics": {**self.raw["metrics"], "brand_new_future_metric": {"x": 1}}}
        result = normalize_electricity_result("future_electricity_2035", raw_with_extra)
        self.assertTrue(result.solved)


if __name__ == "__main__":
    unittest.main()
