import unittest

from app.storage_physics import (
    BatterySpec,
    capacity_retention_pct,
    simulate_storage_lifetime,
    simulate_storage_year,
)


def flat_day(price: float) -> list[float]:
    return [price] * 24


def two_level_day(cheap: float, dear: float, cheap_hours: int = 6) -> list[float]:
    """A day with a clean cheap block and a clean dear block."""
    return [cheap] * cheap_hours + [dear] * (24 - cheap_hours)


SPEC = BatterySpec(power_mw=10.0, energy_capacity_mwh=40.0, grid_charge_eur_per_mwh=0.0)


class SpecTests(unittest.TestCase):
    def test_usable_energy_is_the_soc_window_not_the_nameplate(self):
        self.assertAlmostEqual(SPEC.usable_energy_mwh, 40.0 * 0.90, places=6)

    def test_each_leg_carries_the_square_root_of_the_round_trip(self):
        self.assertAlmostEqual(SPEC.one_way_efficiency**2, SPEC.round_trip_efficiency, places=9)


class DispatchTests(unittest.TestCase):
    def test_a_flat_price_produces_no_trading(self):
        # No spread means no trade: a round trip at a flat price is a
        # guaranteed loss of the efficiency and the wear.
        result = simulate_storage_year(flat_day(100.0) * 10, SPEC)
        self.assertEqual(result.energy_charged_mwh, 0.0)
        self.assertEqual(result.energy_discharged_mwh, 0.0)

    def test_a_spread_too_small_to_clear_losses_is_left_alone(self):
        # 100 -> 110 is a 10% spread; a round trip costs 12% plus 6 EUR of
        # wear, so taking it would destroy value.
        result = simulate_storage_year(two_level_day(100.0, 110.0) * 10, SPEC)
        self.assertEqual(result.energy_discharged_mwh, 0.0)

    def test_a_wide_spread_is_traded(self):
        result = simulate_storage_year(two_level_day(20.0, 200.0) * 10, SPEC)
        self.assertGreater(result.energy_discharged_mwh, 0.0)
        self.assertGreater(result.gross_margin_eur, 0.0)

    def test_round_trip_losses_match_the_efficiency(self):
        result = simulate_storage_year(two_level_day(10.0, 300.0) * 30, SPEC)
        ratio = result.energy_discharged_mwh / result.energy_charged_mwh
        # Discharged over charged must equal the round trip, barring the small
        # amount still sitting in the pack at the end of the run.
        self.assertAlmostEqual(ratio, SPEC.round_trip_efficiency, delta=0.02)

    def test_power_rating_caps_what_can_move_in_an_hour(self):
        result = simulate_storage_year(two_level_day(10.0, 300.0) * 5, SPEC, keep_traces=True)
        self.assertTrue(all(abs(value) <= SPEC.power_mw + 1e-6 for value in result.net_grid_mw))

    def test_state_of_charge_stays_inside_its_window(self):
        result = simulate_storage_year(two_level_day(10.0, 300.0) * 20, SPEC, keep_traces=True)
        floor = SPEC.energy_capacity_mwh * SPEC.min_soc_fraction
        ceiling = SPEC.energy_capacity_mwh * SPEC.max_soc_fraction
        self.assertGreaterEqual(min(result.soc_mwh), floor - 1e-6)
        self.assertLessEqual(max(result.soc_mwh), ceiling + 1e-6)

    def test_charge_is_carried_across_the_day_boundary(self):
        # State of charge must not reset at midnight: what the battery did
        # yesterday evening constrains this morning.
        result = simulate_storage_year(two_level_day(10.0, 300.0) * 3, SPEC, keep_traces=True)
        self.assertEqual(len(result.soc_mwh), 72)
        self.assertGreater(result.final_soc_mwh, 0.0)

    def test_negative_prices_are_paid_for_charging(self):
        day = [-20.0] * 6 + [200.0] * 18
        result = simulate_storage_year(day * 10, SPEC)
        self.assertGreater(result.negative_price_hours_charged, 0)
        # Buying at a negative price is income, so the energy cost is negative.
        self.assertLess(result.charging_cost_eur, 0.0)

    def test_the_daily_cycle_cap_is_respected(self):
        spec = BatterySpec(power_mw=40.0, energy_capacity_mwh=40.0, max_cycles_per_day=1.0)
        # Alternating cheap and dear hours would allow many cycles a day.
        day = [10.0, 300.0] * 12
        result = simulate_storage_year(day * 5, spec)
        self.assertLessEqual(result.equivalent_full_cycles / 5.0, 1.0 + 1e-6)

    def test_grid_charges_can_make_an_otherwise_good_spread_unprofitable(self):
        prices = two_level_day(40.0, 90.0) * 10
        free = simulate_storage_year(prices, BatterySpec(power_mw=10.0, energy_capacity_mwh=40.0))
        taxed = simulate_storage_year(
            prices, BatterySpec(power_mw=10.0, energy_capacity_mwh=40.0, grid_charge_eur_per_mwh=25.0)
        )
        self.assertGreater(free.energy_discharged_mwh, 0.0)
        self.assertEqual(taxed.energy_discharged_mwh, 0.0)


class DegradationTests(unittest.TestCase):
    def test_a_brand_new_battery_is_at_full_capacity(self):
        self.assertEqual(capacity_retention_pct(SPEC, 0, 0), 100.0)

    def test_calendar_and_cycle_fade_both_apply(self):
        calendar_only = capacity_retention_pct(SPEC, 2, 0)
        with_cycles = capacity_retention_pct(SPEC, 2, 600)
        self.assertLess(calendar_only, 100.0)
        self.assertLess(with_cycles, calendar_only)

    def test_retention_never_falls_below_end_of_life(self):
        self.assertEqual(capacity_retention_pct(SPEC, 100, 100_000), SPEC.end_of_life_retention_pct)

    def test_lifetime_carries_degradation_forward_and_shrinks_throughput(self):
        prices = two_level_day(10.0, 300.0) * 365
        years = simulate_storage_lifetime(prices, SPEC, 10)

        self.assertEqual(len(years), 10)
        self.assertEqual(years[0].capacity_retention_pct, 100.0)
        self.assertLess(years[-1].capacity_retention_pct, years[0].capacity_retention_pct)
        # Less usable capacity means less energy through the same price shape.
        self.assertLess(years[-1].energy_discharged_mwh, years[0].energy_discharged_mwh)

    def test_price_escalation_lifts_later_margins(self):
        prices = two_level_day(10.0, 300.0) * 365
        flat = simulate_storage_lifetime(prices, SPEC, 5)
        rising = simulate_storage_lifetime(prices, SPEC, 5, price_escalation_pct_per_year=10.0)
        self.assertGreater(rising[-1].gross_margin_eur, flat[-1].gross_margin_eur)


class EmptySpecTests(unittest.TestCase):
    def test_a_zero_power_battery_simulates_to_nothing_rather_than_dividing_by_zero(self):
        result = simulate_storage_year(two_level_day(10.0, 300.0), BatterySpec(power_mw=0.0, energy_capacity_mwh=10.0))
        self.assertEqual(result.energy_discharged_mwh, 0.0)

    def test_no_prices_at_all_is_handled(self):
        self.assertEqual(simulate_storage_year([], SPEC).energy_discharged_mwh, 0.0)


if __name__ == "__main__":
    unittest.main()
