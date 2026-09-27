import unittest
from unittest.mock import patch

from app import investment_analysis
from app.investment_analysis import (
    TechnologyCostRow,
    annual_net_cash_flows,
    assumed_capacity_mw,
    candidate_carrier,
    degraded_generation_mwh,
    evaluate_candidate_investment,
    irr,
    lcoe_eur_per_mwh,
    national_capacity_factor,
    npv_eur,
    payback_period_years,
)
from app.models import CandidateCell
from app.scenario_models import ScenarioMetrics


# A clean, hand-verifiable 2-year fixture: fom/marginal cost are zero so the
# only cash flows are capex (year 0) and undiscounted revenue (years 1-2),
# with year1 revenue set to exactly equal capex so payback lands on a round
# number. Carrier "solar" applies the real 0.5%/yr degradation rate.
CAPEX_EUR = 100_000.0
GENERATION_YEAR0_MWH = 1_000.0
CAPTURED_PRICE = 100.0
MARGINAL_COST = 0.0
LIFETIME_YEARS = 2.0
DISCOUNT_RATE_PCT = 10.0
FOM_PCT = 0.0


class DegradedGenerationTests(unittest.TestCase):
    def test_year_zero_is_undegraded(self):
        self.assertEqual(degraded_generation_mwh(1000.0, "solar", 0), 1000.0)

    def test_solar_degrades_half_a_percent_per_year(self):
        self.assertAlmostEqual(degraded_generation_mwh(1000.0, "solar", 1), 995.0, places=6)

    def test_unknown_carrier_does_not_degrade(self):
        self.assertEqual(degraded_generation_mwh(1000.0, "hydro", 5), 1000.0)


class NpvEurTests(unittest.TestCase):
    def test_matches_hand_computed_two_year_dcf(self):
        # -100000 + 100000/1.1 + 99500/1.1^2 = 73140.4959 (worked by hand)
        value = npv_eur(
            CAPEX_EUR, GENERATION_YEAR0_MWH, CAPTURED_PRICE, MARGINAL_COST,
            "solar", LIFETIME_YEARS, DISCOUNT_RATE_PCT, FOM_PCT,
        )
        self.assertAlmostEqual(value, 73140.4959, delta=0.01)

    def test_fixed_opex_reduces_npv(self):
        with_opex = npv_eur(CAPEX_EUR, GENERATION_YEAR0_MWH, CAPTURED_PRICE, MARGINAL_COST, "solar", LIFETIME_YEARS, DISCOUNT_RATE_PCT, 5.0)
        without_opex = npv_eur(CAPEX_EUR, GENERATION_YEAR0_MWH, CAPTURED_PRICE, MARGINAL_COST, "solar", LIFETIME_YEARS, DISCOUNT_RATE_PCT, FOM_PCT)
        self.assertLess(with_opex, without_opex)


class IrrTests(unittest.TestCase):
    def test_matches_hand_computed_root(self):
        flows = annual_net_cash_flows(
            CAPEX_EUR, GENERATION_YEAR0_MWH, CAPTURED_PRICE, MARGINAL_COST,
            "solar", LIFETIME_YEARS, FOM_PCT,
        )
        self.assertEqual(flows, [-100_000.0, 100_000.0, 99_500.0])
        # Analytic root of -100000 + 100000x + 99500x^2 = 0, x = 1/(1+r): r ~= 0.6157
        value = irr(flows)
        self.assertAlmostEqual(value, 0.6157, delta=0.001)

    def test_never_profitable_case_returns_none(self):
        flows = [-100_000.0, 1.0, 1.0]
        self.assertIsNone(irr(flows))


class LcoeTests(unittest.TestCase):
    def test_matches_hand_computed_value(self):
        # discounted_generation = 1000/1.1 + 995/1.1^2 = 1731.4050; LCOE = 100000/1731.4050
        value = lcoe_eur_per_mwh(
            CAPEX_EUR, GENERATION_YEAR0_MWH, MARGINAL_COST, "solar", LIFETIME_YEARS, DISCOUNT_RATE_PCT, FOM_PCT,
        )
        self.assertAlmostEqual(value, 57.7566, delta=0.01)

    def test_zero_generation_yields_none_rather_than_dividing_by_zero(self):
        value = lcoe_eur_per_mwh(CAPEX_EUR, 0.0, MARGINAL_COST, "solar", LIFETIME_YEARS, DISCOUNT_RATE_PCT, FOM_PCT)
        self.assertIsNone(value)


class PaybackPeriodTests(unittest.TestCase):
    def test_exact_one_year_payback(self):
        flows = [-100_000.0, 100_000.0, 99_500.0]
        self.assertEqual(payback_period_years(flows), 1.0)

    def test_fractional_payback_within_a_year(self):
        flows = [-100_000.0, 50_000.0, 100_000.0]
        # Recovers the remaining 50000 halfway through year 2's 100000 flow.
        self.assertAlmostEqual(payback_period_years(flows), 1.5, places=6)

    def test_never_pays_back_returns_none(self):
        flows = [-100_000.0, 1.0, 1.0]
        self.assertIsNone(payback_period_years(flows))


class CandidateCarrierTests(unittest.TestCase):
    def test_solar_variants_map_to_solar(self):
        self.assertEqual(candidate_carrier("Solar PV"), "solar")

    def test_wind_variants_map_to_wind(self):
        self.assertEqual(candidate_carrier("Onshore Wind"), "wind")

    def test_unrecognized_technology_is_none(self):
        self.assertIsNone(candidate_carrier("Battery Storage"))


class AssumedCapacityMwTests(unittest.TestCase):
    def test_multiplies_area_by_buildable_fraction_and_power_density(self):
        cell = _make_cell(buildable_fraction=0.5)
        with patch.object(investment_analysis, "cell_area_km2", return_value=2.0):
            capacity = assumed_capacity_mw(cell, "solar")
        # 2.0 km^2 * 0.5 buildable * 40 MW/km^2 (POWER_DENSITY_MW_PER_KM2["solar"])
        self.assertAlmostEqual(capacity, 40.0, places=6)

    def test_missing_buildable_fraction_yields_none(self):
        cell = _make_cell(buildable_fraction=None)
        self.assertIsNone(assumed_capacity_mw(cell, "solar"))

    def test_unknown_carrier_yields_none(self):
        cell = _make_cell(buildable_fraction=0.5)
        self.assertIsNone(assumed_capacity_mw(cell, "hydro"))

    def test_full_buildout_of_a_large_cell_is_capped_at_a_single_project_size(self):
        # A real ~0.1deg screening cell (~11km x ~9km, ~99 km^2) at full
        # buildable_fraction implies several GW at these power densities --
        # no real single solar project is that size, so this must be capped,
        # not returned as a multi-GW "candidate."
        cell = _make_cell(buildable_fraction=1.0)
        with patch.object(investment_analysis, "cell_area_km2", return_value=99.0):
            capacity = assumed_capacity_mw(cell, "solar")
        self.assertEqual(capacity, investment_analysis.MAX_SINGLE_PROJECT_CAPACITY_MW["solar"])

    def test_real_small_square_area_is_a_plausible_positive_number(self):
        # Loose sanity bound, not a pinned figure: a ~0.01deg square near
        # Athens should be on the order of a fraction of a km^2 to a few
        # km^2, not zero, negative, or off by a factor of 1e6 (a dropped
        # /1_000_000 conversion would land far outside this range).
        cell = _make_cell(
            buildable_fraction=1.0,
            geometry={
                "type": "Polygon",
                "coordinates": [[[23.70, 37.98], [23.71, 37.98], [23.71, 37.99], [23.70, 37.99], [23.70, 37.98]]],
            },
        )
        area = investment_analysis.cell_area_km2(cell)
        self.assertTrue(0.1 < area < 5.0, f"area {area} km^2 looks wrong")


class NationalCapacityFactorTests(unittest.TestCase):
    def test_computes_generation_over_capacity_times_hours(self):
        # 4380 MWh / (1 MW * 8760h) = 0.5 capacity factor
        value = national_capacity_factor("solar", {"solar": 4380.0}, {"solar": 1.0})
        self.assertAlmostEqual(value, 0.5, places=6)

    def test_missing_carrier_yields_none(self):
        self.assertIsNone(national_capacity_factor("wind", {"solar": 100.0}, {"solar": 1.0}))

    def test_zero_capacity_yields_none_rather_than_dividing_by_zero(self):
        self.assertIsNone(national_capacity_factor("solar", {"solar": 100.0}, {"solar": 0.0}))


class EvaluateCandidateInvestmentTests(unittest.TestCase):
    def _metrics(self) -> ScenarioMetrics:
        return ScenarioMetrics(
            generation_by_carrier_mwh={"solar": 4380.0},
            installed_capacity_by_carrier_mw={"solar": 1.0},
            average_marginal_price_by_bus={"Attica": 80.0},
        )

    def _costs(self) -> dict:
        return {
            "solar": TechnologyCostRow(
                carrier="solar",
                marginal_cost_eur_per_mwh=0.0,
                overnight_capex_eur_per_kw=600.0,
                lifetime_years=25.0,
                discount_rate_pct=7.0,
                fom_pct_of_capex=2.0,
            )
        }

    def test_unsupported_technology_reports_a_message_not_a_crash(self):
        cell = _make_cell(technology="Battery Storage")
        result = evaluate_candidate_investment(cell, "Attica", self._metrics(), self._costs())
        self.assertIsNone(result.npv_eur)
        self.assertIn("solar and wind", result.message)

    def test_missing_region_reports_a_message_not_a_crash(self):
        cell = _make_cell()
        result = evaluate_candidate_investment(cell, None, self._metrics(), self._costs())
        self.assertIsNone(result.npv_eur)
        self.assertIn("13 modeled regions", result.message)

    def test_full_pipeline_produces_all_real_metrics_for_a_supported_case(self):
        cell = _make_cell(buildable_fraction=0.8)
        with patch.object(investment_analysis, "cell_area_km2", return_value=1.0):
            result = evaluate_candidate_investment(cell, "Attica", self._metrics(), self._costs())

        self.assertIsNone(result.message)
        self.assertEqual(result.carrier, "solar")
        self.assertAlmostEqual(result.assumed_capacity_mw, 32.0, places=2)  # 1.0 * 0.8 * 40
        self.assertEqual(result.captured_price_eur_per_mwh, 80.0)
        self.assertIsNotNone(result.npv_eur)
        self.assertIsNotNone(result.lcoe_eur_per_mwh)
        self.assertIsNotNone(result.payback_years)


def _make_cell(technology: str = "Solar PV", buildable_fraction: float | None = 0.5, geometry: dict | None = None) -> CandidateCell:
    return CandidateCell(
        id="cell-1",
        name="Cell 1",
        technology=technology,
        solar_score=80.0,
        wind_score=10.0,
        distance_to_substation_km=5.0,
        distance_to_line_km=3.0,
        land_excluded=False,
        connection_cost_level="Low",
        status="Screened Candidate",
        investment_score=70.0,
        geometry=geometry or {"type": "Polygon", "coordinates": [[[23.0, 38.0], [23.1, 38.0], [23.1, 38.1], [23.0, 38.1], [23.0, 38.0]]]},
        buildable_fraction=buildable_fraction,
    )


if __name__ == "__main__":
    unittest.main()
