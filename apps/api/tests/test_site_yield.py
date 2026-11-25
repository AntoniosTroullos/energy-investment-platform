import unittest
from datetime import datetime, timedelta, timezone

from app.day_ahead import DayAheadCurve, PricePoint, capture_for_hourly_series
from app.site_yield import (
    CUT_IN_MS,
    CUT_OUT_MS,
    RATED_MS,
    SOLAR_SYSTEM_LOSS_FRACTION,
    STANDARD_AIR_DENSITY,
    WIND_LOSS_FRACTION,
    air_density,
    power_curve,
    solar_output_per_unit,
    wind_output_per_unit,
)


class SolarModelTests(unittest.TestCase):
    def test_night_produces_nothing(self):
        self.assertEqual(solar_output_per_unit([0.0, 0.0], [12.0, 11.0]), [0.0, 0.0])

    def test_standard_test_conditions_give_rated_output_less_system_losses(self):
        # 1000 W/m^2 with a cell at 25 C is the definition of rated output, so
        # the only thing left is the loss stack.
        air_temperature = 25.0 - (45.0 - 20.0) / 800.0 * 1000.0  # makes T_cell exactly 25
        output = solar_output_per_unit([1000.0], [air_temperature])[0]
        self.assertAlmostEqual(output, 1 - SOLAR_SYSTEM_LOSS_FRACTION, places=6)

    def test_a_hotter_cell_produces_less(self):
        cool = solar_output_per_unit([800.0], [10.0])[0]
        hot = solar_output_per_unit([800.0], [35.0])[0]
        self.assertLess(hot, cool)

    def test_output_never_exceeds_rated_capacity(self):
        # Irradiance above 1000 W/m^2 happens; a per-unit output above 1.0 does
        # not, because the inverter clips.
        self.assertLessEqual(solar_output_per_unit([1400.0], [5.0])[0], 1.0)


class WindModelTests(unittest.TestCase):
    def test_below_cut_in_produces_nothing(self):
        self.assertEqual(power_curve(CUT_IN_MS - 0.1), 0.0)

    def test_above_cut_out_shuts_down(self):
        # The physically important discontinuity: a storm means zero output,
        # not maximum output.
        self.assertEqual(power_curve(CUT_OUT_MS + 0.1), 0.0)
        self.assertEqual(power_curve(CUT_OUT_MS), 0.0)

    def test_rated_speed_gives_full_output(self):
        self.assertEqual(power_curve(RATED_MS), 1.0)
        self.assertEqual(power_curve(CUT_OUT_MS - 0.1), 1.0)

    def test_the_ramp_is_monotonic_between_cut_in_and_rated(self):
        speeds = [CUT_IN_MS + step * 0.5 for step in range(int((RATED_MS - CUT_IN_MS) / 0.5) + 1)]
        values = [power_curve(speed) for speed in speeds]
        self.assertEqual(values, sorted(values))

    def test_losses_are_applied_to_the_hourly_series(self):
        # 50 km/h = 13.9 m/s, above rated, at standard conditions.
        output = wind_output_per_unit([50.0], [15.0], [1013.25])[0]
        self.assertAlmostEqual(output, 1 - WIND_LOSS_FRACTION, places=2)

    def test_thin_air_reduces_output(self):
        dense = wind_output_per_unit([25.0], [5.0], [1020.0])[0]
        thin = wind_output_per_unit([25.0], [35.0], [900.0])[0]
        self.assertLess(thin, dense)


class AirDensityTests(unittest.TestCase):
    def test_standard_conditions_give_about_standard_density(self):
        self.assertAlmostEqual(air_density(15.0, 1013.25), STANDARD_AIR_DENSITY, places=2)

    def test_nonsense_inputs_fall_back_to_standard_density(self):
        self.assertEqual(air_density(-300.0, 1013.25), STANDARD_AIR_DENSITY)
        self.assertEqual(air_density(15.0, 0.0), STANDARD_AIR_DENSITY)


def quarter_hourly_curve(start: datetime, hourly_prices: list[float]) -> DayAheadCurve:
    """A curve at 15-minute resolution, so the hour-matching in
    capture_for_hourly_series has to average within the hour."""
    points = []
    for index, price in enumerate(hourly_prices):
        for quarter in range(4):
            stamp = start + timedelta(hours=index, minutes=15 * quarter)
            points.append(PricePoint(timestamp=stamp.isoformat(), price_eur_per_mwh=price))
    return DayAheadCurve(points=points, source="test", redistribution_allowed=True)


class SiteCaptureTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc)

    def test_a_site_producing_only_in_cheap_hours_captures_the_cheap_price(self):
        curve = quarter_hourly_curve(self.start, [100.0, 100.0, 20.0, 20.0])
        timestamps = [(self.start + timedelta(hours=hour)).isoformat() for hour in range(4)]
        output = [0.0, 0.0, 0.5, 0.5]

        result = capture_for_hourly_series(curve, timestamps, output)
        self.assertEqual(result["capture_price_eur_per_mwh"], 20.0)
        self.assertEqual(result["flat_mean_eur_per_mwh"], 60.0)
        self.assertEqual(result["capture_rate_pct"], 33.3)
        self.assertEqual(result["matched_hours"], 4)

    def test_hours_outside_the_price_window_are_skipped_not_zero_filled(self):
        curve = quarter_hourly_curve(self.start, [50.0, 50.0])
        timestamps = [(self.start + timedelta(hours=hour)).isoformat() for hour in range(6)]
        output = [1.0] * 6

        result = capture_for_hourly_series(curve, timestamps, output)
        self.assertEqual(result["matched_hours"], 2)
        self.assertEqual(result["capture_price_eur_per_mwh"], 50.0)

    def test_no_overlap_at_all_is_none(self):
        curve = quarter_hourly_curve(self.start, [50.0])
        far_later = [(self.start + timedelta(days=30)).isoformat()]
        self.assertIsNone(capture_for_hourly_series(curve, far_later, [1.0]))

    def test_a_site_that_never_produces_has_no_capture_price(self):
        curve = quarter_hourly_curve(self.start, [50.0, 50.0])
        timestamps = [(self.start + timedelta(hours=hour)).isoformat() for hour in range(2)]
        self.assertIsNone(capture_for_hourly_series(curve, timestamps, [0.0, 0.0]))

    def test_mismatched_series_lengths_are_rejected(self):
        curve = quarter_hourly_curve(self.start, [50.0])
        self.assertIsNone(capture_for_hourly_series(curve, [self.start.isoformat()], [1.0, 1.0]))

    def test_naive_weather_timestamps_are_treated_as_utc(self):
        # Open-Meteo is asked for UTC and returns "2026-11-20T00:00" with no
        # offset; the prices carry one. They must still match.
        curve = quarter_hourly_curve(self.start, [80.0])
        result = capture_for_hourly_series(curve, ["2026-11-20T00:00"], [1.0])
        self.assertEqual(result["capture_price_eur_per_mwh"], 80.0)


if __name__ == "__main__":
    unittest.main()
