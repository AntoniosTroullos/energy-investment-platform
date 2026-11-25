import json
import tempfile
import unittest
from pathlib import Path

from app.settings import DEFAULT_CORS_ORIGINS, bundled_scenario_dir, load_settings
from app.system_status import check_bridge, list_solved_electricity_years


class LoadSettingsTests(unittest.TestCase):
    def test_defaults_derive_everything_from_one_project_root(self):
        settings = load_settings({})

        self.assertEqual(settings.pypsa_greece_root, settings.pypsa_project_root / "pypsa-greece")
        self.assertEqual(
            settings.scenario_root,
            settings.pypsa_project_root / "data" / "processed" / "pypsa_scenarios",
        )
        self.assertEqual(
            settings.run_multiyear_script,
            settings.pypsa_project_root / "scripts" / "run_multiyear_electricity.py",
        )
        self.assertEqual(settings.pypsa_python.parent.parent.name, ".venv314")
        self.assertEqual(settings.cors_origins, DEFAULT_CORS_ORIGINS)

    def test_project_root_override_moves_every_derived_path(self):
        settings = load_settings({"PYPSA_PROJECT_ROOT": str(Path("some") / "other" / "root")})

        root = Path("some") / "other" / "root"
        self.assertEqual(settings.pypsa_project_root, root)
        self.assertEqual(settings.scenario_root, root / "data" / "processed" / "pypsa_scenarios")
        self.assertEqual(settings.run_coupled_script, root / "scripts" / "build_and_solve_coupled_year.py")

    def test_an_explicit_root_is_used_even_when_it_holds_no_scenarios(self):
        # The bundled snapshot is a fallback for the DEFAULT root only. Under
        # an explicit override it must not be substituted: that hid an empty or
        # mistyped root behind the shipped cases, so the API answered with
        # scenarios the configured project does not have.
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_root = Path(tmpdir) / "empty-project"
            settings = load_settings({"PYPSA_PROJECT_ROOT": str(empty_root)})

        self.assertEqual(settings.scenario_root, empty_root / "data" / "processed" / "pypsa_scenarios")
        self.assertNotEqual(settings.scenario_root, bundled_scenario_dir())

    def test_the_default_root_still_falls_back_to_the_bundled_snapshot(self):
        # A deployed server has no sibling project and must still serve the
        # snapshot that ships with the repo.
        settings = load_settings({"PYPSA_PROJECT_ROOT": ""})

        default_scenarios = settings.pypsa_project_root / "data" / "processed" / "pypsa_scenarios"
        expected = default_scenarios if default_scenarios.exists() else bundled_scenario_dir()
        self.assertEqual(settings.scenario_root, expected)

    def test_python_override_is_independent_of_project_root(self):
        custom_python = str(Path("custom") / "python.exe")
        settings = load_settings({"PYPSA_PYTHON": custom_python})

        self.assertEqual(settings.pypsa_python, Path(custom_python))

    def test_blank_overrides_are_ignored(self):
        settings = load_settings({"PYPSA_PROJECT_ROOT": "  ", "PYPSA_PYTHON": "", "API_CORS_ORIGINS": " "})

        self.assertEqual(settings.cors_origins, DEFAULT_CORS_ORIGINS)
        self.assertEqual(settings.pypsa_greece_root, settings.pypsa_project_root / "pypsa-greece")

    def test_cors_origins_are_split_and_trailing_slashes_trimmed(self):
        settings = load_settings({"API_CORS_ORIGINS": "http://localhost:3100/, http://127.0.0.1:3100"})

        self.assertEqual(
            settings.cors_origins,
            ("http://localhost:3100", "http://127.0.0.1:3100"),
        )


class BridgeStatusTests(unittest.TestCase):
    def _make_project(self, root: Path) -> None:
        (root / "scripts").mkdir(parents=True)
        (root / "scripts" / "run_multiyear_electricity.py").write_text("", encoding="utf-8")
        (root / "scripts" / "build_and_solve_coupled_year.py").write_text("", encoding="utf-8")
        (root / "data" / "processed" / "pypsa_scenarios").mkdir(parents=True)

    def test_missing_project_reports_every_missing_piece(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = load_settings({"PYPSA_PROJECT_ROOT": str(Path(tmpdir) / "does-not-exist")})

            status = check_bridge(settings)

        self.assertFalse(status.ready)
        self.assertIn("PyPSA project root", status.missing)
        self.assertIn("Solver interpreter", status.missing)
        self.assertEqual(status.solved_electricity_years, [])
        self.assertIsNone(status.solver_stack_ok)

    def test_complete_project_layout_is_ready_without_the_deep_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._make_project(root)
            fake_python = root / "python.exe"
            fake_python.write_text("", encoding="utf-8")
            settings = load_settings(
                {"PYPSA_PROJECT_ROOT": str(root), "PYPSA_PYTHON": str(fake_python)}
            )

            status = check_bridge(settings)

        self.assertTrue(status.ready, status.missing)
        self.assertEqual(status.missing, [])

    def test_solved_years_only_counts_bridge_cases_that_have_a_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scenario_root = Path(tmpdir)
            for name, has_result in [
                ("future_electricity_2040", True),
                ("future_electricity_2030", True),
                ("future_electricity_2035", False),  # started, never finished
                ("clustered_2026_first24_smoke", True),  # not a bridge case
                ("future_electricity_2030_chronological", True),  # not the plain pattern
            ]:
                (scenario_root / name).mkdir()
                if has_result:
                    (scenario_root / name / "scenario_result.json").write_text(json.dumps({}), encoding="utf-8")

            years = list_solved_electricity_years(scenario_root)

        self.assertEqual(years, [2030, 2040])


if __name__ == "__main__":
    unittest.main()
