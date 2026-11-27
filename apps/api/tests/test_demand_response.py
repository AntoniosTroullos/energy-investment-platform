import unittest

from app.demand_response import (
    DEFAULT_AVAILABILITY_CAP_EUR_PER_MW_YEAR,
    IndustrialSite,
    InterruptibilityContract,
    InterruptibilityProduct,
    continuous_process_load,
    simulate_demand_response,
    two_shift_load,
)

HOURS = 8760


def rising_prices() -> list[float]:
    """A year where every hour has a distinct price, so "the dearest hours"
    is unambiguous and activations are easy to reason about."""
    return [float(hour) for hour in range(HOURS)]


def flat_site(load_mw: float = 100.0, **kwargs) -> IndustrialSite:
    defaults = {
        "name": "Test works",
        "baseline_load_mw": continuous_process_load(load_mw),
        "interruptible_fraction": 0.5,
        "production_loss_eur_per_mwh": 0.0,
    }
    defaults.update(kwargs)
    return IndustrialSite(**defaults)


class AvailabilityTests(unittest.TestCase):
    def test_availability_is_paid_whether_or_not_the_site_is_ever_called(self):
        # Prices flat at zero: no hour is worth activating, yet the option
        # still earns. That is what an availability payment is.
        contract = InterruptibilityContract(
            product=InterruptibilityProduct.TYPE_1, contracted_mw=10.0
        )
        result = simulate_demand_response(flat_site(), [0.0] * HOURS, [contract])

        expected = 10.0 * DEFAULT_AVAILABILITY_CAP_EUR_PER_MW_YEAR[InterruptibilityProduct.TYPE_1]
        self.assertEqual(result.availability_revenue_eur, expected)
        self.assertTrue(any("never called" in note for note in result.notes))

    def test_an_explicit_contract_price_overrides_the_published_cap(self):
        contract = InterruptibilityContract(
            product=InterruptibilityProduct.TYPE_1,
            contracted_mw=10.0,
            availability_price_eur_per_mw_year=42_000.0,
        )
        result = simulate_demand_response(flat_site(), [0.0] * HOURS, [contract])
        self.assertEqual(result.availability_revenue_eur, 420_000.0)


class ActivationTests(unittest.TestCase):
    def test_the_operator_calls_in_the_dearest_hours(self):
        contract = InterruptibilityContract(
            product=InterruptibilityProduct.TYPE_1,
            contracted_mw=10.0,
            activation_price_eur_per_mwh=100.0,
            max_activations_per_year=1,
        )
        result = simulate_demand_response(flat_site(), rising_prices(), [contract])

        self.assertEqual(result.activation_count, 1)
        # The last hour of a rising year is the dearest.
        self.assertEqual(result.events[0].start_hour, HOURS - 1)

    def test_the_hour_cap_limits_the_year(self):
        contract = InterruptibilityContract(
            product=InterruptibilityProduct.TYPE_2,
            contracted_mw=10.0,
            activation_price_eur_per_mwh=100.0,
            max_activations_per_year=100,
            max_duration_hours=4,
            min_hours_between_activations=1,
        )
        result = simulate_demand_response(flat_site(), rising_prices(), [contract])
        # Type 2's documented cap is 24 hours a year.
        self.assertLessEqual(result.activation_hours, 24.0)

    def test_the_minimum_gap_between_calls_is_respected(self):
        contract = InterruptibilityContract(
            product=InterruptibilityProduct.TYPE_1,
            contracted_mw=10.0,
            activation_price_eur_per_mwh=100.0,
            max_activations_per_year=5,
            min_hours_between_activations=500,
        )
        result = simulate_demand_response(flat_site(), rising_prices(), [contract])

        starts = sorted(event.start_hour for event in result.events)
        gaps = [later - earlier for earlier, later in zip(starts, starts[1:])]
        self.assertTrue(all(gap >= 500 for gap in gaps), gaps)

    def test_each_contract_keeps_its_own_limits(self):
        # Holding both products must allow calls under each. A shared counter
        # silently starved the second product once the first hit its cap.
        contracts = [
            InterruptibilityContract(
                product=InterruptibilityProduct.TYPE_1,
                contracted_mw=10.0,
                activation_price_eur_per_mwh=100.0,
                max_activations_per_year=2,
            ),
            InterruptibilityContract(
                product=InterruptibilityProduct.TYPE_2,
                contracted_mw=5.0,
                activation_price_eur_per_mwh=200.0,
                max_activations_per_year=2,
            ),
        ]
        result = simulate_demand_response(flat_site(), rising_prices(), contracts)
        self.assertEqual(result.activation_count, 4)

    def test_curtailment_cannot_exceed_what_the_process_can_give_up(self):
        # Contracted for 50 MW, but only 20 MW of the load is interruptible.
        contract = InterruptibilityContract(
            product=InterruptibilityProduct.TYPE_1,
            contracted_mw=50.0,
            activation_price_eur_per_mwh=100.0,
            max_activations_per_year=1,
            max_duration_hours=1,
        )
        site = flat_site(load_mw=100.0, interruptible_fraction=0.2)
        result = simulate_demand_response(site, rising_prices(), [contract])
        self.assertAlmostEqual(result.events[0].energy_not_consumed_mwh, 20.0, places=6)

    def test_production_loss_is_charged_against_the_activation_payment(self):
        contract = InterruptibilityContract(
            product=InterruptibilityProduct.TYPE_1,
            contracted_mw=10.0,
            activation_price_eur_per_mwh=100.0,
            max_activations_per_year=1,
            max_duration_hours=1,
        )
        site = flat_site(production_loss_eur_per_mwh=40.0)
        result = simulate_demand_response(site, rising_prices(), [contract])

        energy = result.events[0].energy_not_consumed_mwh
        self.assertAlmostEqual(result.production_loss_eur, energy * 40.0, places=2)

    def test_a_contract_that_pays_less_than_it_costs_is_flagged(self):
        contract = InterruptibilityContract(
            product=InterruptibilityProduct.TYPE_1,
            contracted_mw=10.0,
            activation_price_eur_per_mwh=50.0,
        )
        site = flat_site(production_loss_eur_per_mwh=200.0)
        result = simulate_demand_response(site, rising_prices(), [contract])
        self.assertTrue(any("costs more than it pays" in note for note in result.notes))

    def test_rebound_energy_is_charged_back(self):
        contract = InterruptibilityContract(
            product=InterruptibilityProduct.TYPE_1,
            contracted_mw=10.0,
            activation_price_eur_per_mwh=100.0,
            max_activations_per_year=1,
        )
        without = simulate_demand_response(flat_site(), rising_prices(), [contract])
        with_rebound = simulate_demand_response(
            flat_site(rebound_fraction=1.0), rising_prices(), [contract]
        )
        self.assertEqual(without.rebound_cost_eur, 0.0)
        self.assertGreater(with_rebound.rebound_cost_eur, 0.0)
        self.assertLess(with_rebound.net_benefit_eur, without.net_benefit_eur)


class LoadShiftingTests(unittest.TestCase):
    def test_a_site_with_nothing_shiftable_saves_nothing(self):
        result = simulate_demand_response(flat_site(shiftable_fraction=0.0), rising_prices(), [])
        self.assertEqual(result.load_shifting_saving_eur, 0.0)

    def test_shifting_within_a_day_earns_the_price_difference(self):
        # Each day: 12 hours at 200, 12 at 20.
        day = [200.0] * 12 + [20.0] * 12
        prices = (day * 365)[:HOURS]
        site = flat_site(load_mw=10.0, shiftable_fraction=0.5)

        result = simulate_demand_response(site, prices, [])
        # Four dearest hours moved into the four cheapest, each day:
        # 5 MW shifted x 180 EUR x 4 hours x 365 days.
        self.assertAlmostEqual(result.load_shifting_saving_eur, 5.0 * 180.0 * 4 * 365, places=2)

    def test_shifting_never_moves_load_into_a_dearer_hour(self):
        result = simulate_demand_response(
            flat_site(shiftable_fraction=0.5), [100.0] * HOURS, []
        )
        self.assertEqual(result.load_shifting_saving_eur, 0.0)


class ProfileTests(unittest.TestCase):
    def test_a_continuous_process_is_flat(self):
        profile = continuous_process_load(50.0, hours=48)
        self.assertEqual(set(profile), {50.0})

    def test_a_two_shift_profile_drops_at_night_and_at_weekends(self):
        profile = two_shift_load(40.0, 10.0, hours=24 * 7)
        self.assertEqual(profile[8], 40.0)  # Thursday 08:00, working
        self.assertEqual(profile[2], 10.0)  # overnight
        self.assertEqual(profile[24 * 5 + 10], 10.0)  # Saturday


class NetBenefitTests(unittest.TestCase):
    def test_net_benefit_nets_every_stream_against_every_cost(self):
        contract = InterruptibilityContract(
            product=InterruptibilityProduct.TYPE_1,
            contracted_mw=10.0,
            availability_price_eur_per_mw_year=10_000.0,
            activation_price_eur_per_mwh=100.0,
            max_activations_per_year=1,
            max_duration_hours=1,
        )
        site = flat_site(production_loss_eur_per_mwh=10.0)
        result = simulate_demand_response(site, rising_prices(), [contract])

        expected = (
            result.availability_revenue_eur
            + result.activation_revenue_eur
            + result.avoided_energy_cost_eur
            + result.load_shifting_saving_eur
            - result.production_loss_eur
            - result.rebound_cost_eur
        )
        self.assertAlmostEqual(result.net_benefit_eur, expected, places=6)

    def test_the_benefit_is_reported_against_the_energy_bill(self):
        result = simulate_demand_response(flat_site(), [100.0] * HOURS, [])
        self.assertAlmostEqual(result.baseline_energy_cost_eur, 100.0 * 100.0 * HOURS, places=2)


if __name__ == "__main__":
    unittest.main()
