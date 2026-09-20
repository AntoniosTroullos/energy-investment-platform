import json
import unittest
from pathlib import Path

from app.pypsa_bridge.normalize import normalize_coupled_result

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# This fixture is a REAL coupled_outputs/scenario_result.json captured from a
# real solve (pythonProject1's build_and_solve_coupled_year.py, run under
# pypsa-greece's .venv314). That script and the network-building code behind
# it (coupled_energy_system.py) were confirmed to be mid-edit/uncommitted
# upstream at plan time -- these tests exist specifically to catch schema
# drift from that ongoing work as a red test rather than a silent runtime
# break.


class CoupledScenarioBridgeNormalizationTests(unittest.TestCase):
    def setUp(self):
        fixture_path = FIXTURES_DIR / "coupled_scenario_result_sample.json"
        self.raw = json.loads(fixture_path.read_text(encoding="utf-8"))

    def test_real_fixture_has_the_expected_top_level_keys(self):
        for key in [
            "year",
            "solved",
            "message",
            "objective_eur_per_year",
            "annual_heat_twh",
            "h2_market_scenario",
            "h2_market_inputs",
            "h2_balance_mwh",
            "link_capacity_mw",
            "average_electricity_price_eur_per_mwh",
        ]:
            self.assertIn(key, self.raw, f"Upstream coupled scenario_result.json is missing expected key '{key}'")

    def test_normalize_coupled_result_round_trips_real_data(self):
        result = normalize_coupled_result("future_electricity_2030", self.raw)

        self.assertEqual(result.case_name, "future_electricity_2030")
        self.assertEqual(result.year, 2030)
        self.assertTrue(result.solved)
        self.assertIsInstance(result.objective_eur_per_year, float)
        self.assertGreater(result.objective_eur_per_year, 0)

        self.assertEqual(result.h2_market_scenario, "baseline_no_trade")
        self.assertIsNotNone(result.h2_market_inputs)
        self.assertEqual(result.h2_market_inputs.scenario, "baseline_no_trade")

        self.assertIsNotNone(result.h2_balance_mwh)
        self.assertGreaterEqual(result.h2_balance_mwh.electrolysis_output, 0)

        # The real fixture currently includes the WIP electrolyzer-expansion
        # fields -- confirm they normalize through when present.
        self.assertIsInstance(result.electrolyzer_expansion_capacity_mw, dict)

    def test_normalize_tolerates_missing_electrolyzer_expansion_fields(self):
        """The WIP electrolyzer-expansion fields are a moving target upstream
        -- an older result on disk (or a rolled-back script version) may not
        write them at all. Must normalize fine either way."""
        raw_without_expansion = {
            key: value
            for key, value in self.raw.items()
            if key not in ("electrolyzer_expansion_cost", "electrolyzer_expansion_capacity_mw")
        }
        result = normalize_coupled_result("future_electricity_2030", raw_without_expansion)
        self.assertTrue(result.solved)
        self.assertEqual(result.electrolyzer_expansion_cost, {})
        self.assertEqual(result.electrolyzer_expansion_capacity_mw, {})

    def test_normalize_tolerates_unknown_new_top_level_keys(self):
        """A future upstream addition must surface via extra="allow", not raise."""
        raw_with_extra = {**self.raw, "brand_new_future_field": {"x": 1}}
        result = normalize_coupled_result("future_electricity_2030", raw_with_extra)
        self.assertTrue(result.solved)


if __name__ == "__main__":
    unittest.main()
