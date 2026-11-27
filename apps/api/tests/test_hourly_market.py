import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app import hourly_market
from app.hourly_market import HourlyMarket, get_hourly_market
from app.investment_analysis import (
    PRICE_BASIS_HOURLY,
    PRICE_BASIS_HOURLY_NATIONAL_SHAPE,
    PRICE_BASIS_REGIONAL_AVERAGE,
    TechnologyCostRow,
    evaluate_candidate_investment,
)
from app.models import CandidateCell
from app.scenario_models import ScenarioMetrics


# A two-region fixture with the numbers chosen so every derived figure is
# checkable by hand:
#   Attica   price 100, solar captures 50  -> capture rate 50%
#   Crete    price  80, no solar at all    -> falls back to the national rate
#   national price 100, solar captures 60  -> national capture rate 60%
HOURLY_FIXTURE = {
    "schema_version": 1,
    "case_name": "fixture_case",
    "regions": ["Attica", "Crete"],
    "national": {
        "time_weighted_price_eur_per_mwh": 100.0,
        "load_weighted_price_eur_per_mwh": 102.0,
        "carriers": {
            "solar": {
                "installed_capacity_mw": 1000.0,
                "availability_capture_price_eur_per_mwh": 60.0,
                "availability_capacity_factor_pct": 18.0,
                "realised_capture_price_eur_per_mwh": 58.0,
                "curtailment_pct": 2.0,
            }
        },
    },
    "by_region": {
        "Attica": {
            "time_weighted_price_eur_per_mwh": 100.0,
            "carriers": {
                "solar": {
                    "installed_capacity_mw": 500.0,
                    "availability_capture_price_eur_per_mwh": 50.0,
                    "availability_capacity_factor_pct": 20.0,
                    "capture_rate_pct": 50.0,
                }
            },
        },
        "Crete": {"time_weighted_price_eur_per_mwh": 80.0, "carriers": {}},
    },
}


def fixture_market() -> HourlyMarket:
    return HourlyMarket(**HOURLY_FIXTURE)


class CapturePriceTests(unittest.TestCase):
    def test_region_with_the_technology_uses_its_own_capture_price(self):
        market = fixture_market()
        self.assertEqual(market.capture_price("Attica", "solar"), 50.0)
        self.assertEqual(market.capture_basis("Attica", "solar"), "region")

    def test_region_without_the_technology_applies_the_national_rate_to_its_own_price(self):
        # National capture rate is 60/100 = 60%; Crete's own price level is 80,
        # so the estimate is 48 -- NOT the national capture price of 60, which
        # would import another region's price level along with its profile.
        market = fixture_market()
        self.assertAlmostEqual(market.capture_price("Crete", "solar"), 48.0, places=9)
        self.assertEqual(market.capture_basis("Crete", "solar"), "national_shape")

    def test_unknown_carrier_has_no_capture_price_rather_than_a_zero(self):
        market = fixture_market()
        self.assertIsNone(market.capture_price("Attica", "wind"))
        self.assertIsNone(market.capture_basis("Attica", "wind"))

    def test_capacity_factor_prefers_the_region_then_falls_back_nationally(self):
        market = fixture_market()
        self.assertEqual(market.capacity_factor_pct("Attica", "solar"), 20.0)
        self.assertEqual(market.capacity_factor_pct("Crete", "solar"), 18.0)

    def test_capture_rate_is_reported_against_the_regions_own_price(self):
        market = fixture_market()
        self.assertEqual(market.capture_rate_pct("Attica", "solar"), 50.0)


class LoadingTests(unittest.TestCase):
    def test_a_case_with_no_extracted_layer_is_none_not_an_error(self):
        get_hourly_market.cache_clear()
        self.assertIsNone(get_hourly_market("a_case_that_was_never_extracted"))

    def test_a_malformed_file_is_none_rather_than_a_crash(self):
        get_hourly_market.cache_clear()
        with patch.object(hourly_market, "hourly_market_path") as path_fn:
            broken = Path(__file__).parent / "fixtures" / "not_json_at_all.json"
            path_fn.return_value = broken
            try:
                broken.write_text("{nope", encoding="utf-8")
                self.assertIsNone(get_hourly_market("broken_case"))
            finally:
                broken.unlink(missing_ok=True)
        get_hourly_market.cache_clear()

    def test_the_real_extracted_files_parse(self):
        # Guards the contract between pipeline/extract_hourly_market.py (which
        # writes these, on the solver side of the bridge) and this module. A
        # change to the extractor's output shape must fail here, not in a
        # response.
        directory = hourly_market.hourly_market_dir()
        if not directory.is_dir():
            self.skipTest("no extracted hourly market files in this checkout")
        for path in sorted(directory.glob("*.json")):
            with self.subTest(case=path.stem):
                market = HourlyMarket(**json.loads(path.read_text(encoding="utf-8")))
                self.assertEqual(market.schema_version, 1)
                self.assertTrue(market.regions)
                self.assertIsNotNone(market.national.time_weighted_price_eur_per_mwh)


# A cell big enough that the capacity cap applies, so capacity is identical
# across the cases below and only price/capacity-factor differ.
def make_cell(cell_id: str = "cell-1") -> CandidateCell:
    return CandidateCell(
        id=cell_id,
        name="Cell 1",
        technology="Solar PV",
        solar_score=80.0,
        wind_score=10.0,
        distance_to_substation_km=5.0,
        distance_to_line_km=3.0,
        land_excluded=False,
        connection_cost_level="Low",
        status="Screened Candidate",
        investment_score=70.0,
        geometry={
            "type": "Polygon",
            "coordinates": [[[23.0, 38.0], [23.1, 38.0], [23.1, 38.1], [23.0, 38.1], [23.0, 38.0]]],
        },
        buildable_fraction=1.0,
    )


SOLAR_COSTS = {
    "solar": TechnologyCostRow(
        carrier="solar",
        marginal_cost_eur_per_mwh=0.0,
        overnight_capex_eur_per_kw=600.0,
        lifetime_years=25.0,
        discount_rate_pct=7.0,
        fom_pct_of_capex=2.0,
    )
}

METRICS = ScenarioMetrics(
    generation_by_carrier_mwh={"solar": 1_000_000.0},
    installed_capacity_by_carrier_mw={"solar": 1_000.0},
    average_marginal_price_by_bus={"Attica": 100.0, "Crete": 80.0},
)


class CandidateEconomicsUseTheHourlyLayerTests(unittest.TestCase):
    def test_without_the_hourly_layer_it_falls_back_to_the_regional_average(self):
        analysis = evaluate_candidate_investment(make_cell(), "Attica", METRICS, SOLAR_COSTS, None)
        self.assertEqual(analysis.price_basis, PRICE_BASIS_REGIONAL_AVERAGE)
        self.assertEqual(analysis.captured_price_eur_per_mwh, 100.0)

    def test_with_the_hourly_layer_the_candidate_is_paid_its_capture_price(self):
        analysis = evaluate_candidate_investment(
            make_cell(), "Attica", METRICS, SOLAR_COSTS, fixture_market()
        )
        self.assertEqual(analysis.price_basis, PRICE_BASIS_HOURLY)
        self.assertEqual(analysis.captured_price_eur_per_mwh, 50.0)
        # The flat average stays beside it, so the gap is visible.
        self.assertEqual(analysis.reference_price_eur_per_mwh, 100.0)
        self.assertEqual(analysis.capture_rate_pct, 50.0)

    def test_the_fallback_shape_is_labelled_differently(self):
        analysis = evaluate_candidate_investment(
            make_cell(), "Crete", METRICS, SOLAR_COSTS, fixture_market()
        )
        self.assertEqual(analysis.price_basis, PRICE_BASIS_HOURLY_NATIONAL_SHAPE)
        self.assertAlmostEqual(analysis.captured_price_eur_per_mwh, 48.0, places=6)

    def test_ignoring_cannibalisation_overstates_the_investment_case(self):
        # The whole point of the change, as an assertion: pricing a solar
        # candidate at the flat regional average rather than at what solar
        # actually earns inflates its NPV.
        flat = evaluate_candidate_investment(make_cell(), "Attica", METRICS, SOLAR_COSTS, None)
        captured = evaluate_candidate_investment(
            make_cell(), "Attica", METRICS, SOLAR_COSTS, fixture_market()
        )
        self.assertGreater(flat.npv_eur, captured.npv_eur)

    def test_the_regions_own_capacity_factor_replaces_the_national_one(self):
        analysis = evaluate_candidate_investment(
            make_cell(), "Attica", METRICS, SOLAR_COSTS, fixture_market()
        )
        # 20% from the fixture's Attica solar, not the 11.4% the national
        # metrics above would give (1,000,000 MWh / (1,000 MW * 8760 h)).
        self.assertEqual(analysis.capacity_factor_pct, 20.0)
        self.assertEqual(analysis.capacity_factor_basis, "regional_hourly")


if __name__ == "__main__":
    unittest.main()
