import tempfile
import unittest
from pathlib import Path

from app.scenario_options import (
    InvalidCoupledScenarioError,
    get_scenario_options,
    valid_coupled_combinations,
    validate_coupled_request,
)
from app.settings import load_settings

H2_CSV_HEADER = "scenario,year,import_price_eur_per_mwh,import_capacity_mw\n"


def make_settings(root: Path, csv_body: str | None = None) -> "object":
    """A Settings pointed at a throwaway project root, optionally with a
    h2_market_scenarios.csv already written."""
    if csv_body is not None:
        csv_path = root / "pypsa-greece" / "data" / "static" / "h2_market_scenarios.csv"
        csv_path.parent.mkdir(parents=True)
        csv_path.write_text(csv_body, encoding="utf-8")

    return load_settings({"PYPSA_PROJECT_ROOT": str(root)})


class ValidCoupledCombinationsTests(unittest.TestCase):
    def test_missing_csv_yields_no_combinations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = make_settings(Path(tmpdir))
            self.assertEqual(valid_coupled_combinations(settings), set())

    def test_reads_real_rows_from_the_csv(self):
        body = H2_CSV_HEADER + "baseline_no_trade,2030,,0\nbaseline_no_trade,2040,,0\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = make_settings(Path(tmpdir), body)
            self.assertEqual(
                valid_coupled_combinations(settings),
                {(2030, "baseline_no_trade"), (2040, "baseline_no_trade")},
            )

    def test_blank_or_malformed_rows_are_skipped(self):
        body = H2_CSV_HEADER + "baseline_no_trade,2030,,0\n,,,\nbaseline_no_trade,not-a-year,,0\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = make_settings(Path(tmpdir), body)
            self.assertEqual(valid_coupled_combinations(settings), {(2030, "baseline_no_trade")})


class ValidateCoupledRequestTests(unittest.TestCase):
    def test_accepts_a_combination_that_is_in_the_csv(self):
        body = H2_CSV_HEADER + "baseline_no_trade,2030,,0\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = make_settings(Path(tmpdir), body)
            validate_coupled_request(2030, "baseline_no_trade", settings)  # must not raise

    def test_rejects_a_year_not_defined_for_an_otherwise_known_scenario(self):
        body = H2_CSV_HEADER + "baseline_no_trade,2030,,0\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = make_settings(Path(tmpdir), body)
            with self.assertRaises(InvalidCoupledScenarioError) as ctx:
                validate_coupled_request(2031, "baseline_no_trade", settings)
            self.assertIn("2030", str(ctx.exception))

    def test_rejects_an_unknown_scenario_name(self):
        body = H2_CSV_HEADER + "baseline_no_trade,2030,,0\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = make_settings(Path(tmpdir), body)
            with self.assertRaises(InvalidCoupledScenarioError) as ctx:
                validate_coupled_request(2030, "high_import", settings)
            self.assertIn("baseline_no_trade", str(ctx.exception))

    def test_fails_open_when_the_csv_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = make_settings(Path(tmpdir))
            validate_coupled_request(1999, "anything", settings)  # must not raise


class GetScenarioOptionsTests(unittest.TestCase):
    def test_default_year_choices_are_offered_with_nothing_solved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = make_settings(Path(tmpdir))
            options = get_scenario_options(settings)

            self.assertTrue(all(not year.solved for year in options.electricity_years))
            self.assertIn(2030, [year.year for year in options.electricity_years])
            self.assertEqual(options.coupled_options, [])

    def test_solved_years_are_flagged_and_added_even_if_not_a_default_choice(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            settings = make_settings(root)
            solved_case = root / "data" / "processed" / "pypsa_scenarios" / "future_electricity_2032"
            solved_case.mkdir(parents=True)
            (solved_case / "scenario_result.json").write_text("{}", encoding="utf-8")

            options = get_scenario_options(settings)

            by_year = {year.year: year.solved for year in options.electricity_years}
            self.assertTrue(by_year[2032])
            self.assertFalse(by_year[2030])  # a default choice, but not solved

    def test_coupled_options_carry_a_readable_label_and_electricity_solved_flag(self):
        body = H2_CSV_HEADER + "baseline_no_trade,2030,,0\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            settings = make_settings(root, body)
            solved_case = root / "data" / "processed" / "pypsa_scenarios" / "future_electricity_2030"
            solved_case.mkdir(parents=True)
            (solved_case / "scenario_result.json").write_text("{}", encoding="utf-8")

            options = get_scenario_options(settings)

            self.assertEqual(len(options.coupled_options), 1)
            option = options.coupled_options[0]
            self.assertEqual(option.label, "Baseline No Trade (2030)")
            self.assertTrue(option.electricity_solved)

    def test_limits_come_from_the_shared_scenario_model_constants(self):
        from app.scenario_models import GROWTH_RATE_DEFAULT, TARGET_YEAR_MAX, TARGET_YEAR_MIN

        with tempfile.TemporaryDirectory() as tmpdir:
            options = get_scenario_options(make_settings(Path(tmpdir)))

        self.assertEqual(options.target_year_min, TARGET_YEAR_MIN)
        self.assertEqual(options.target_year_max, TARGET_YEAR_MAX)
        self.assertEqual(options.annual_growth_rate_default, GROWTH_RATE_DEFAULT)


if __name__ == "__main__":
    unittest.main()
