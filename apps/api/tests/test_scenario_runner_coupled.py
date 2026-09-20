import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import scenario_runner

# run_coupled_scenario's precondition guard (an electricity case must already
# be solved for the requested year) can't be exercised live against real
# data on this machine -- all 3 coupled-eligible years (2030/2040/2050)
# already have solved electricity cases here. This points scenario_runner at
# an empty, isolated SCENARIO_ROOT instead, so "no electricity case exists"
# is real and reproducible without touching the real data directory.


class RunCoupledScenarioPreconditionTests(unittest.TestCase):
    def test_raises_precondition_error_when_electricity_case_not_solved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(scenario_runner, "SCENARIO_ROOT", Path(tmpdir)):
                with self.assertRaises(scenario_runner.ScenarioPreconditionError):
                    asyncio.run(scenario_runner.run_coupled_scenario(2030, "baseline_no_trade"))

                # The guard must fire before any marker/subprocess bookkeeping --
                # confirm no coupled_outputs directory was ever created.
                self.assertFalse((Path(tmpdir) / "future_electricity_2030" / "coupled_outputs").exists())

    def test_precondition_error_is_a_scenario_run_error(self):
        """ScenarioPreconditionError must remain catchable by existing code
        that only checks the base ScenarioRunError class."""
        self.assertTrue(
            issubclass(scenario_runner.ScenarioPreconditionError, scenario_runner.ScenarioRunError)
        )


if __name__ == "__main__":
    unittest.main()
