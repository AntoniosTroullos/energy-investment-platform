import os
import tempfile
import unittest
from pathlib import Path

from app import staleness

# Every test builds a throwaway "upstream project" tree and controls file
# mtimes explicitly with os.utime, so nothing depends on wall-clock timing or
# on the real (actively edited) model files.

BASE = 1_700_000_000.0  # arbitrary fixed epoch


def touch(path: Path, mtime: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


class StalenessTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

        self.result = touch(self.root / "results" / "scenario_result.json", BASE)
        self.build_network = touch(self.root / "pypsa-greece/src/build_network.py", BASE - 100)
        self.tech_costs = touch(self.root / "pypsa-greece/data/static/technology_costs.csv", BASE - 100)
        self.coupled_code = touch(self.root / "pypsa-greece/src/coupled_energy_system.py", BASE - 100)
        self.coupled_script = touch(self.root / "scripts/build_and_solve_coupled_year.py", BASE - 100)

    def elec(self, **kwargs):
        return staleness.assess(
            self.result, staleness.electricity_watchlist(self.root), self.root, **kwargs
        )

    def coupled(self, **kwargs):
        return staleness.assess(
            self.result, staleness.coupled_watchlist(self.root), self.root, **kwargs
        )

    def test_missing_result_returns_none(self):
        self.assertIsNone(
            staleness.assess(self.root / "nope.json", staleness.electricity_watchlist(self.root), self.root)
        )

    def test_fresh_when_everything_older_than_result(self):
        result = self.elec()
        self.assertFalse(result.is_stale)
        self.assertEqual(result.reasons, [])
        self.assertIsNotNone(result.solved_at)

    def test_code_change_after_solve_marks_stale_and_names_latest_file(self):
        touch(self.build_network, BASE + 500)
        result = self.elec()
        self.assertTrue(result.is_stale)
        self.assertEqual([r.code for r in result.reasons], ["model_code_changed"])
        self.assertIn("pypsa-greece/src/build_network.py", result.reasons[0].detail)

    def test_input_table_change_is_reported_separately_from_code(self):
        touch(self.build_network, BASE + 500)
        touch(self.tech_costs, BASE + 600)
        codes = {r.code for r in self.elec().reasons}
        self.assertEqual(codes, {"model_code_changed", "model_inputs_changed"})

    def test_change_within_tolerance_is_not_stale(self):
        touch(self.build_network, BASE + staleness.MTIME_TOLERANCE_SECONDS - 0.5)
        self.assertFalse(self.elec().is_stale)

    def test_coupled_only_edits_do_not_stale_an_electricity_result(self):
        touch(self.coupled_code, BASE + 500)
        touch(self.coupled_script, BASE + 500)
        self.assertFalse(self.elec().is_stale)

    def test_coupled_only_edits_do_stale_a_coupled_result(self):
        touch(self.coupled_code, BASE + 500)
        result = self.coupled()
        self.assertTrue(result.is_stale)
        self.assertIn("coupled_energy_system.py", result.reasons[0].detail)

    def test_parent_resolved_after_coupled_result_marks_coupled_stale(self):
        parent = touch(self.root / "electricity" / "scenario_result.json", BASE + 300)
        result = self.coupled(parent_result_path=parent)
        self.assertTrue(result.is_stale)
        self.assertEqual([r.code for r in result.reasons], ["parent_resolved"])

    def test_parent_older_than_coupled_result_is_fine(self):
        parent = touch(self.root / "electricity" / "scenario_result.json", BASE - 300)
        self.assertFalse(self.coupled(parent_result_path=parent).is_stale)

    def test_missing_parent_is_not_treated_as_stale(self):
        self.assertFalse(self.coupled(parent_result_path=self.root / "gone.json").is_stale)


if __name__ == "__main__":
    unittest.main()
