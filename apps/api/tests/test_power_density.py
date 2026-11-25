import json
import unittest
from unittest.mock import patch

from app import power_density
from app.power_density import (
    BASIS_LITERATURE,
    BASIS_MEASURED,
    LITERATURE_MW_PER_KM2,
    MIN_SAMPLE_PLANTS,
    get_power_density,
)


def measurement(carrier: str, *, count: int, headline: float, statistic: str = "median") -> dict:
    return {
        "schema_version": 1,
        "measured_at_utc": "2026-11-25T00:00:00+00:00",
        "carriers": {
            carrier: {
                "plant_count": count,
                "headline_mw_per_km2": headline,
                "headline_statistic": statistic,
                "total_area_km2": 12.5,
            }
        },
    }


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        get_power_density.cache_clear()
        power_density.load_measurement.cache_clear()

    def tearDown(self):
        get_power_density.cache_clear()
        power_density.load_measurement.cache_clear()

    def test_a_large_enough_sample_replaces_the_literature_figure(self):
        with patch.object(power_density, "load_measurement", return_value=measurement("solar", count=38, headline=55.45)):
            density = get_power_density("solar")
        self.assertEqual(density.mw_per_km2, 55.45)
        self.assertEqual(density.basis, BASIS_MEASURED)
        self.assertEqual(density.plant_count, 38)

    def test_too_small_a_sample_keeps_the_literature_figure(self):
        # One mapped plant is a worse estimate than a published range, not a
        # better one -- the whole point of the threshold.
        with patch.object(power_density, "load_measurement", return_value=measurement("wind", count=1, headline=7.34)):
            density = get_power_density("wind")
        self.assertEqual(density.mw_per_km2, LITERATURE_MW_PER_KM2["wind"])
        self.assertEqual(density.basis, BASIS_LITERATURE)

    def test_the_threshold_boundary_is_inclusive(self):
        with patch.object(
            power_density,
            "load_measurement",
            return_value=measurement("solar", count=MIN_SAMPLE_PLANTS, headline=50.0),
        ):
            self.assertEqual(get_power_density("solar").basis, BASIS_MEASURED)

    def test_no_measurement_file_at_all_falls_back_silently(self):
        with patch.object(power_density, "load_measurement", return_value=None):
            density = get_power_density("solar")
        self.assertEqual(density.mw_per_km2, LITERATURE_MW_PER_KM2["solar"])
        self.assertEqual(density.basis, BASIS_LITERATURE)

    def test_an_unsized_carrier_has_no_density(self):
        with patch.object(power_density, "load_measurement", return_value=None):
            self.assertIsNone(get_power_density("hydro"))

    def test_the_description_says_which_basis_it_rests_on(self):
        with patch.object(power_density, "load_measurement", return_value=measurement("solar", count=38, headline=55.45)):
            self.assertIn("built Greek solar plants", get_power_density("solar").describe())
        get_power_density.cache_clear()
        with patch.object(power_density, "load_measurement", return_value=None):
            self.assertIn("literature", get_power_density("solar").describe())


class RealMeasurementFileTests(unittest.TestCase):
    def test_the_committed_measurement_parses_and_is_plausible(self):
        path = power_density.measurement_path()
        if not path.is_file():
            self.skipTest("no calibration in this checkout")
        payload = json.loads(path.read_text(encoding="utf-8"))
        for carrier, stats in payload["carriers"].items():
            with self.subTest(carrier=carrier):
                if not stats.get("plant_count"):
                    continue
                headline = stats["headline_mw_per_km2"]
                self.assertIsNotNone(headline)
                # Guard rails, not expectations: a calibration that drifts
                # outside these is a data problem to look at, not a new fact.
                bounds = {"solar": (20.0, 120.0), "wind": (2.0, 15.0)}[carrier]
                self.assertGreaterEqual(headline, bounds[0])
                self.assertLessEqual(headline, bounds[1])


if __name__ == "__main__":
    unittest.main()
