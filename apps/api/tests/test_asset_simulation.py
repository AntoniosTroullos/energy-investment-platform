import unittest

from app.asset_simulation import simulate_generation_asset, simulate_storage_asset
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
