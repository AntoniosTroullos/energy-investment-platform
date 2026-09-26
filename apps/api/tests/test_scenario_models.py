import unittest

from pydantic import ValidationError

from app.scenario_models import CoupledScenarioRunRequest, ElectricityScenarioRunRequest


class ElectricityScenarioRunRequestTests(unittest.TestCase):
    def test_force_fetch_defaults_to_false(self):
        request = ElectricityScenarioRunRequest(target_year=2030, annual_growth_rate=0.01)
        self.assertFalse(request.force_fetch)

    def test_force_fetch_can_be_set(self):
        request = ElectricityScenarioRunRequest(target_year=2030, annual_growth_rate=0.01, force_fetch=True)
        self.assertTrue(request.force_fetch)


class CoupledScenarioRunRequestTests(unittest.TestCase):
    def test_storage_flags_default_to_false(self):
        request = CoupledScenarioRunRequest(target_year=2030, h2_market_scenario="baseline_no_trade")
        self.assertFalse(request.chronological_storage)
        self.assertFalse(request.linked_representative_periods)

    def test_chronological_storage_alone_is_valid(self):
        request = CoupledScenarioRunRequest(
            target_year=2030, h2_market_scenario="baseline_no_trade", chronological_storage=True
        )
        self.assertTrue(request.chronological_storage)

    def test_linked_representative_periods_alone_is_valid(self):
        request = CoupledScenarioRunRequest(
            target_year=2030,
            h2_market_scenario="baseline_no_trade",
            linked_representative_periods=True,
        )
        self.assertTrue(request.linked_representative_periods)

    def test_both_storage_methods_at_once_is_rejected(self):
        with self.assertRaises(ValidationError):
            CoupledScenarioRunRequest(
                target_year=2030,
                h2_market_scenario="baseline_no_trade",
                chronological_storage=True,
                linked_representative_periods=True,
            )


if __name__ == "__main__":
    unittest.main()
