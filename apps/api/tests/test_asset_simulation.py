import unittest

from app.asset_simulation import (
    SETTLEMENT_BALANCING,
    SETTLEMENT_DAY_AHEAD,
    balancing_price_series,
    simulate_generation_asset,
    simulate_storage_asset,
)
from app.balancing import BalancingYear
from app.hourly_series import PriceYear, WeatherYear
from app.storage_physics import BatterySpec

HOURS = 8760


def price_year(prices: list[float]) -> PriceYear:
    return PriceYear(
        year=2025,
        source="test",
        redistribution_allowed=True,
        prices_eur_per_mwh=prices,
        missing_hours=0,
    )


def daily_solar_shape() -> list[float]:
    """A crude day: sun from 06:00 to 18:00, peaking at noon."""
    day = []
    for hour in range(24):
        day.append(max(0.0, 1.0 - abs(hour - 12) / 6.0) * 900.0 if 6 <= hour <= 18 else 0.0)
    return day


def weather_year() -> WeatherYear:
    irradiance = (daily_solar_shape() * 365)[:HOURS]
    return WeatherYear(
        year=2025,
        latitude=38.0,
        longitude=23.7,
        plane_of_array_w_m2=irradiance,
        temperature_c=[20.0] * HOURS,
        wind_speed_100m_kmh=[30.0] * HOURS,
        surface_pressure_hpa=[1013.0] * HOURS,
    )


class GenerationSimulationTests(unittest.TestCase):
    def test_a_flat_price_gives_a_capture_price_equal_to_it(self):
        simulation = simulate_generation_asset(
            latitude=38.0,
            longitude=23.7,
            carrier="solar",
            capacity_mw=100.0,
            price_year=price_year([80.0] * HOURS),
            weather=weather_year(),
            lifetime_years=1,
        )
        self.assertAlmostEqual(simulation.years[0].capture_price_eur_per_mwh, 80.0, places=2)

    def test_cheap_daylight_hours_pull_the_capture_price_below_the_mean(self):
        # Solar's own hours priced at 20, every other hour at 140. The flat
        # mean is well above what solar is paid -- the cannibalisation the
        # annual-average model cannot see.
        day = [140.0] * 24
        for hour in range(9, 16):
            day[hour] = 20.0
        prices = (day * 365)[:HOURS]

        simulation = simulate_generation_asset(
            latitude=38.0,
            longitude=23.7,
            carrier="solar",
            capacity_mw=100.0,
            price_year=price_year(prices),
            weather=weather_year(),
            lifetime_years=1,
        )
        mean = sum(prices) / len(prices)
        self.assertLess(simulation.years[0].capture_price_eur_per_mwh, mean)

    def test_negative_price_hours_are_curtailed_not_sold_at_a_loss(self):
        day = [50.0] * 24
        for hour in range(11, 14):
            day[hour] = -30.0
        prices = (day * 365)[:HOURS]

        curtailing = simulate_generation_asset(
            latitude=38.0, longitude=23.7, carrier="solar", capacity_mw=100.0,
            price_year=price_year(prices), weather=weather_year(), lifetime_years=1,
        )
        running = simulate_generation_asset(
            latitude=38.0, longitude=23.7, carrier="solar", capacity_mw=100.0,
            price_year=price_year(prices), weather=weather_year(), lifetime_years=1,
            curtail_at_negative_prices=False,
        )

        self.assertGreater(curtailing.years[0].hours_curtailed, 0)
        self.assertEqual(running.years[0].hours_curtailed, 0)
        # Not producing into a negative price earns more than producing into it.
        self.assertGreater(curtailing.years[0].revenue_eur, running.years[0].revenue_eur)
        self.assertLess(curtailing.years[0].generation_mwh, running.years[0].generation_mwh)

    def test_degradation_scales_volume_but_not_the_capture_price(self):
        simulation = simulate_generation_asset(
            latitude=38.0, longitude=23.7, carrier="solar", capacity_mw=100.0,
            price_year=price_year([80.0] * HOURS), weather=weather_year(), lifetime_years=10,
        )
        first, last = simulation.years[0], simulation.years[-1]
        self.assertLess(last.generation_mwh, first.generation_mwh)
        # Output fades uniformly across hours, so the price it is paid does not
        # move -- only the volume does.
        self.assertAlmostEqual(
            last.capture_price_eur_per_mwh, first.capture_price_eur_per_mwh, places=2
        )
        self.assertAlmostEqual(last.output_retention_pct, 100 * 0.995**9, places=2)

    def test_an_unmodelled_carrier_is_rejected_rather_than_guessed_at(self):
        with self.assertRaises(ValueError):
            simulate_generation_asset(
                latitude=38.0, longitude=23.7, carrier="hydro", capacity_mw=10.0,
                price_year=price_year([80.0] * HOURS), weather=weather_year(),
            )

    def test_economics_are_attached_when_a_capex_is_given(self):
        simulation = simulate_generation_asset(
            latitude=38.0, longitude=23.7, carrier="solar", capacity_mw=100.0,
            price_year=price_year([80.0] * HOURS), weather=weather_year(),
            lifetime_years=25, capex_eur_per_kw=600.0,
        )
        self.assertEqual(simulation.capex_eur, 60_000_000)
        self.assertIsNotNone(simulation.npv_eur)
        self.assertIsNotNone(simulation.irr_pct)

    def test_no_capex_leaves_economics_absent_rather_than_zero(self):
        simulation = simulate_generation_asset(
            latitude=38.0, longitude=23.7, carrier="solar", capacity_mw=100.0,
            price_year=price_year([80.0] * HOURS), weather=weather_year(), lifetime_years=1,
        )
        self.assertIsNone(simulation.npv_eur)
        self.assertIsNone(simulation.irr_pct)


class StorageSimulationTests(unittest.TestCase):
    def test_a_battery_simulation_carries_its_degradation_notes(self):
        day = [20.0] * 8 + [200.0] * 16
        simulation = simulate_storage_asset(
            spec=BatterySpec(power_mw=10.0, energy_capacity_mwh=40.0),
            price_year=price_year((day * 365)[:HOURS]),
            lifetime_years=10,
            capex_eur_per_kwh=250.0,
        )
        self.assertEqual(len(simulation.storage_years), 10)
        self.assertEqual(simulation.capex_eur, 10_000_000)
        self.assertTrue(any("retention" in note for note in simulation.notes))

    def test_traces_cover_the_first_year_only(self):
        day = [20.0] * 8 + [200.0] * 16
        simulation = simulate_storage_asset(
            spec=BatterySpec(power_mw=10.0, energy_capacity_mwh=40.0),
            price_year=price_year((day * 365)[:HOURS]),
            lifetime_years=3,
        )
        self.assertEqual(len(simulation.first_year_soc_mwh), HOURS)
        self.assertEqual(len(simulation.first_year_price_eur_per_mwh), HOURS)


if __name__ == "__main__":
    unittest.main()


class BalancingSettlementTests(unittest.TestCase):
    """A battery settled against balancing prices rather than day-ahead. The
    engine is the same; only the series and its labelling change."""

    def _balancing_year(self, prices):
        return BalancingYear(
            from_utc="2025-11-22T00:00:00+00:00",
            to_utc="2026-11-22T00:00:00+00:00",
            imbalance_price_eur_per_mwh=prices,
            mfrr_up_eur_per_mwh=[price + 10 for price in prices],
            mfrr_down_eur_per_mwh=[price - 10 for price in prices],
            system_short_share=[0.5] * len(prices),
            intra_hour_spread_eur_per_mwh=[40.0] * len(prices),
            missing_hours=3,
            files_used=54,
        )

    def test_series_carries_its_own_window_not_a_calendar_year(self):
        series = balancing_price_series(self._balancing_year([50.0] * 48))
        self.assertEqual(series.start_utc, "2025-11-22T00:00:00+00:00")
        self.assertEqual(series.window_start.isoformat(), "2025-11-22T00:00:00+00:00")
        self.assertIn("settled balancing", series.window_label)
        self.assertIn("2025-11-22", series.window_label)
        self.assertEqual(series.missing_hours, 3)

    def test_source_names_the_settlement_file_and_how_many_were_read(self):
        series = balancing_price_series(self._balancing_year([50.0] * 48))
        self.assertIn("IMBABE", series.source)
        self.assertIn("54", series.source)
        self.assertTrue(series.redistribution_allowed)

    def test_a_day_ahead_year_still_starts_on_1_january(self):
        series = price_year([10.0] * 48)
        self.assertEqual(series.window_start.isoformat(), "2025-01-01T00:00:00+00:00")
        self.assertEqual(series.window_label, "day-ahead 2025")

    def test_the_wider_balancing_spread_earns_more_on_identical_physics(self):
        # Same daily shape, balancing swinging twice as wide around the same
        # mean. The engine is indifferent to provenance, so the only thing that
        # can move the margin is the spread.
        shape = [20.0, 20.0, 20.0, 20.0, 180.0, 180.0, 180.0, 180.0] * 6
        wide = [-80.0, -80.0, -80.0, -80.0, 280.0, 280.0, 280.0, 280.0] * 6
        spec = BatterySpec(power_mw=10.0, energy_capacity_mwh=40.0)

        narrow_result = simulate_storage_asset(
            spec=spec, price_year=price_year(shape * 183), lifetime_years=1
        )
        wide_result = simulate_storage_asset(
            spec=spec,
            price_year=balancing_price_series(self._balancing_year(wide * 183)),
            lifetime_years=1,
            settlement=SETTLEMENT_BALANCING,
        )
        self.assertGreater(
            wide_result.storage_years[0].gross_margin_eur,
            narrow_result.storage_years[0].gross_margin_eur,
        )

    def test_the_settlement_basis_is_recorded_on_the_result(self):
        spec = BatterySpec(power_mw=10.0, energy_capacity_mwh=40.0)
        prices = [20.0, 200.0] * 24 * 183
        result = simulate_storage_asset(
            spec=spec,
            price_year=balancing_price_series(self._balancing_year(prices)),
            lifetime_years=1,
            settlement=SETTLEMENT_BALANCING,
        )
        self.assertEqual(result.settlement, SETTLEMENT_BALANCING)
        self.assertIn("settled balancing", result.price_window)
        # The three qualifications that belong beside a balancing number.
        joined = " ".join(result.notes)
        self.assertIn("price taker", joined.lower())
        self.assertIn("qualified balancing service unit", joined)

    def test_day_ahead_results_do_not_carry_balancing_caveats(self):
        spec = BatterySpec(power_mw=10.0, energy_capacity_mwh=40.0)
        result = simulate_storage_asset(
            spec=spec, price_year=price_year([20.0, 200.0] * 24 * 183), lifetime_years=1
        )
        self.assertEqual(result.settlement, SETTLEMENT_DAY_AHEAD)
        self.assertNotIn("qualified balancing service unit", " ".join(result.notes))
