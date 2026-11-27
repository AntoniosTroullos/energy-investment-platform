import unittest
from datetime import datetime, timedelta

from app import balancing, ipto

# ---------------------------------------------------------------------------
# Settled imbalance prices (IMBABE)
# ---------------------------------------------------------------------------

# Column layout of the settlement file: start, end, activated up, activated
# down, ISP energy, system deviation, curtailment flag, imbalance price,
# mFRR up, mFRR down, then three uplift accounts.
HEADER = [
    "STARTDATE",
    "ENDDATE",
    "Total Activated Balancing Energy UP (MWh)",
    "Total Activated Balancing Energy Down (MWh)",
    "ISP energy",
    "System deviation (MWh)",
    "Curt_Flag",
    "Imbalance Price",
    "mFRR Price UP",
    "mFRR Price Down",
    "Uplift 1",
    "Uplift 2",
    "Uplift 3",
]

FIRST_SERIAL = 46353.0  # 2026-11-27 00:00 Greek time
QUARTER = 0.010416666666


def _settlement_row(
    index: int,
    *,
    imbalance: float,
    mfrr_up: float,
    mfrr_down: float,
    deviation: float,
    activated_up: float = 100.0,
    activated_down: float = 90.0,
) -> list[object]:
    start = FIRST_SERIAL + index * QUARTER
    return [
        start,
        start + QUARTER,
        activated_up,
        activated_down,
        0.0,
        deviation,
        0.0,
        imbalance,
        mfrr_up,
        mfrr_down,
        0.0,
        0.0,
        0.0,
    ]


def _settlement_rows() -> list[list[object]]:
    return [
        HEADER,
        # System short: settlement takes the mFRR up price.
        _settlement_row(0, imbalance=250.0, mfrr_up=250.0, mfrr_down=-100.0, deviation=40.0),
        _settlement_row(1, imbalance=200.0, mfrr_up=200.0, mfrr_down=-50.0, deviation=10.0),
        # System long: settlement takes the mFRR down price.
        _settlement_row(2, imbalance=-100.0, mfrr_up=250.0, mfrr_down=-100.0, deviation=-30.0),
        # Neither mFRR price set it: another product was marginal.
        _settlement_row(3, imbalance=50.0, mfrr_up=250.0, mfrr_down=-100.0, deviation=-1.0),
    ]


class ParseImbalanceRowsTests(unittest.TestCase):
    def setUp(self):
        self.periods = balancing.parse_imbalance_rows(_settlement_rows())

    def test_header_row_is_skipped_without_a_special_case(self):
        self.assertEqual(len(self.periods), 4)

    def test_timestamps_are_utc_from_greek_wall_clock(self):
        self.assertEqual(self.periods[0].start_utc, "2026-11-26T22:00:00+00:00")
        self.assertEqual(self.periods[1].start_utc, "2026-11-26T22:15:00+00:00")

    def test_columns_land_in_the_right_fields(self):
        first = self.periods[0]
        self.assertEqual(first.imbalance_price_eur_per_mwh, 250.0)
        self.assertEqual(first.mfrr_up_eur_per_mwh, 250.0)
        self.assertEqual(first.mfrr_down_eur_per_mwh, -100.0)
        self.assertEqual(first.activated_up_mwh, 100.0)
        self.assertEqual(first.activated_down_mwh, 90.0)
        self.assertEqual(first.system_deviation_mwh, 40.0)

    def test_system_short_follows_the_sign_of_the_deviation(self):
        self.assertTrue(self.periods[0].system_short)
        self.assertFalse(self.periods[2].system_short)

    def test_short_rows_are_ignored(self):
        self.assertEqual(balancing.parse_imbalance_rows([[FIRST_SERIAL, 1.0]]), [])


class ImbalanceStatisticsTests(unittest.TestCase):
    def setUp(self):
        self.week = balancing.ImbalanceWeek(
            periods=balancing.parse_imbalance_rows(_settlement_rows()),
            file_name="20261127_IMBABE_01.xlsx",
        )
        self.statistics = balancing.imbalance_statistics(self.week)

    def test_window_covers_the_last_period_in_full(self):
        self.assertEqual(self.statistics["from_utc"], "2026-11-26T22:00:00+00:00")
        # Four quarter-hours from 22:00 ends at 23:00, not 22:45.
        self.assertEqual(self.statistics["to_utc"], "2026-11-26T23:00:00+00:00")

    def test_short_and_long_are_split_by_deviation(self):
        self.assertEqual(self.statistics["system_short_periods"], 2)
        self.assertEqual(self.statistics["system_long_periods"], 2)

    def test_the_spread_a_battery_earns_is_short_mean_minus_long_mean(self):
        # Short: (250 + 200) / 2 = 225. Long: (-100 + 50) / 2 = -25.
        self.assertEqual(self.statistics["mean_price_when_short_eur_per_mwh"], 225.0)
        self.assertEqual(self.statistics["mean_price_when_long_eur_per_mwh"], -25.0)
        self.assertEqual(self.statistics["short_long_spread_eur_per_mwh"], 250.0)

    def test_negative_periods_counted(self):
        self.assertEqual(self.statistics["negative_periods"], 1)

    def test_activated_energy_totalled(self):
        self.assertEqual(self.statistics["activated_up_mwh"], 400.0)
        self.assertEqual(self.statistics["activated_down_mwh"], 360.0)

    def test_empty_week_yields_no_statistics(self):
        empty = balancing.ImbalanceWeek(periods=[], file_name="x")
        self.assertEqual(balancing.imbalance_statistics(empty), {})


class MfrrStatisticsTests(unittest.TestCase):
    def test_spread_is_mean_up_minus_mean_down(self):
        week = balancing.ImbalanceWeek(
            periods=balancing.parse_imbalance_rows(_settlement_rows()),
            file_name="x",
        )
        statistics = balancing.mfrr_statistics(week)
        # Up: (250 + 200 + 250 + 250) / 4 = 237.5. Down: (-100 - 50 - 100 - 100) / 4 = -87.5.
        self.assertEqual(statistics["mean_up_eur_per_mwh"], 237.5)
        self.assertEqual(statistics["mean_down_eur_per_mwh"], -87.5)
        self.assertEqual(statistics["mean_spread_eur_per_mwh"], 325.0)
        self.assertEqual(statistics["negative_down_periods"], 4)


class PricingAttributionTests(unittest.TestCase):
    """The pricing rule is measured, not encoded -- see the module docstring.
    These pin the measurement, not Greece's current regulation."""

    def test_attribution_counts_each_case(self):
        week = balancing.ImbalanceWeek(
            periods=balancing.parse_imbalance_rows(_settlement_rows()),
            file_name="x",
        )
        attribution = balancing.pricing_attribution(week)
        self.assertEqual(attribution["set_by_mfrr_up"], 2)
        self.assertEqual(attribution["set_by_mfrr_down"], 1)
        self.assertEqual(attribution["set_by_neither"], 1)
        self.assertEqual(attribution["set_by_neither_pct"], 25.0)

    def test_shares_sum_to_the_whole_week(self):
        week = balancing.ImbalanceWeek(
            periods=balancing.parse_imbalance_rows(_settlement_rows()),
            file_name="x",
        )
        attribution = balancing.pricing_attribution(week)
        self.assertEqual(
            attribution["set_by_mfrr_up"]
            + attribution["set_by_mfrr_down"]
            + attribution["set_by_neither"],
            attribution["periods"],
        )


class PercentileTests(unittest.TestCase):
    def test_interpolates_between_neighbours(self):
        ordered = [0.0, 10.0, 20.0, 30.0, 40.0]
        self.assertEqual(balancing._percentile(ordered, 0), 0.0)
        self.assertEqual(balancing._percentile(ordered, 100), 40.0)
        self.assertEqual(balancing._percentile(ordered, 50), 20.0)
        self.assertEqual(balancing._percentile(ordered, 25), 10.0)

    def test_single_value(self):
        self.assertEqual(balancing._percentile([7.0], 90), 7.0)


# ---------------------------------------------------------------------------
# Hourly assembly
# ---------------------------------------------------------------------------


class IntoHoursTests(unittest.TestCase):
    def _periods(self, prices: list[float], *, start: int = 0) -> list[balancing.ImbalancePeriod]:
        return [
            balancing.ImbalancePeriod(
                start_utc=ipto.athens_serial_to_utc(FIRST_SERIAL + (start + index) * QUARTER).isoformat(),
                imbalance_price_eur_per_mwh=price,
                mfrr_up_eur_per_mwh=price + 10,
                mfrr_down_eur_per_mwh=price - 10,
                activated_up_mwh=1.0,
                activated_down_mwh=1.0,
                system_deviation_mwh=1.0 if index % 2 == 0 else -1.0,
            )
            for index, price in enumerate(prices)
        ]

    def test_four_quarter_hours_average_into_one_hour(self):
        year = balancing._into_hours(self._periods([100.0, 200.0, 300.0, 400.0]), files_used=1)
        self.assertEqual(year.hours, 1)
        self.assertEqual(year.imbalance_price_eur_per_mwh[0], 250.0)

    def test_intra_hour_spread_is_carried_not_discarded(self):
        year = balancing._into_hours(self._periods([100.0, 200.0, 300.0, 400.0]), files_used=1)
        self.assertEqual(year.intra_hour_spread_eur_per_mwh[0], 300.0)
        self.assertEqual(year.mean_intra_hour_spread_eur_per_mwh, 300.0)

    def test_system_short_share_within_the_hour(self):
        year = balancing._into_hours(self._periods([100.0, 200.0, 300.0, 400.0]), files_used=1)
        # Two of four quarter-hours had a positive deviation.
        self.assertEqual(year.system_short_share[0], 0.5)

    def test_a_gap_hour_carries_the_previous_price_rather_than_zero(self):
        # Hour 0, then nothing in hour 1, then hour 2. A zero would read as a
        # free hour and a battery would charge into it.
        periods = self._periods([100.0, 100.0, 100.0, 100.0]) + self._periods([50.0], start=8)
        year = balancing._into_hours(periods, files_used=1)
        self.assertEqual(year.hours, 3)
        self.assertEqual(year.missing_hours, 1)
        self.assertEqual(year.imbalance_price_eur_per_mwh[1], 100.0)
        self.assertEqual(year.imbalance_price_eur_per_mwh[2], 50.0)

    def test_duplicate_instants_collapse_so_a_revision_does_not_double_count(self):
        periods = self._periods([100.0]) + self._periods([900.0])
        year = balancing._into_hours(periods, files_used=2)
        self.assertEqual(year.hours, 1)
        self.assertEqual(year.imbalance_price_eur_per_mwh[0], 900.0)

    def test_series_is_trimmed_to_exactly_one_year(self):
        # Over-collecting is deliberate (weekly files do not align to the
        # window edge); leaving the overshoot in would inflate every annual
        # total computed from the series.
        hours = balancing.HOURS_PER_YEAR + 48
        prices = [float(index % 100) for index in range(hours * 4)]
        year = balancing._into_hours(self._periods(prices), files_used=60)
        self.assertEqual(year.hours, balancing.HOURS_PER_YEAR)
        self.assertEqual(len(year.mfrr_up_eur_per_mwh), balancing.HOURS_PER_YEAR)
        self.assertEqual(len(year.intra_hour_spread_eur_per_mwh), balancing.HOURS_PER_YEAR)
        # The window the series reports must be the window it actually holds:
        # from_utc has to move forward with the trim, not stay where the
        # over-collected series began.
        span = datetime.fromisoformat(year.to_utc) - datetime.fromisoformat(year.from_utc)
        self.assertEqual(span, timedelta(hours=balancing.HOURS_PER_YEAR))

    def test_no_periods_yields_nothing(self):
        self.assertIsNone(balancing._into_hours([], files_used=0))


class NewestRevisionTests(unittest.TestCase):
    def test_a_revision_supersedes_the_original_for_its_date(self):
        files = [
            ipto.PublishedFile("IMBABE", "20261116_IMBABE_01.xlsx", "a"),
            ipto.PublishedFile("IMBABE", "20261116_IMBABE_02.xlsx", "b"),
            ipto.PublishedFile("IMBABE", "20261109_IMBABE_01.xlsx", "c"),
        ]
        chosen = balancing._newest_revisions(files)
        self.assertEqual([item.name for item in chosen], ["20261109_IMBABE_01.xlsx", "20261116_IMBABE_02.xlsx"])

    def test_files_without_a_date_are_dropped(self):
        files = [ipto.PublishedFile("IMBABE", "latest.xlsx", "a")]
        self.assertEqual(balancing._newest_revisions(files), [])


# ---------------------------------------------------------------------------
# The operator's schedule (ISP results)
# ---------------------------------------------------------------------------


def _clock(label: str) -> list[object]:
    return [label] + [FIRST_SERIAL + index * QUARTER for index in range(4)]


def _isp_rows() -> list[list[object]]:
    return [
        ["", "Integrated Scheduling Process : ISP1"],
        _clock("Non Dispatchable Load"),
        ["System Load+Losses", 5000.0, 5100.0, 5200.0, 5300.0],
        ["Renewables", 1000.0, 1100.0, 1200.0, 1300.0],
        _clock("Energy Marginal Prices"),
        ["Greece Price Energy Up", 300.0, 300.0, 100.0, 100.0],
        ["Greece Price Energy Down", 50.0, 50.0, 20.0, 20.0],
        _clock("Cleared Energy"),
        ["Greece Cleared Energy Up", 10.0, 10.0, 10.0, 10.0],
        ["Greece Cleared Energy Down", 5.0, 5.0, 5.0, 5.0],
        _clock("Storage Units"),
        # Discharging in the two dear periods, charging in the two cheap ones.
        ["MYT_BZ1_01_SB", 100.0, 100.0, -100.0, -100.0],
        ["PPC_BZ1_01_SB", 0.0, 0.0, -100.0, -100.0],
        ["Total Storage Production", 100.0, 100.0, -200.0, -200.0],
        _clock("Reserve Requirements"),
        ["FCR Up", 65.0, 65.0, 65.0, 65.0],
        ["mFRR Up", 500.0, 600.0, 700.0, 800.0],
        # A product the operator is not procuring at all must not be reported.
        ["RR Up", 0.0, 0.0, 0.0, 0.0],
        _clock("Corridor Limit"),
        ["ignored", 1.0, 1.0, 1.0, 1.0],
    ]


class ParseIspRowsTests(unittest.TestCase):
    def setUp(self):
        self.day = balancing.parse_isp_rows(_isp_rows(), "20261127_ISP1ISPResults_01.xlsx")

    def test_periods_come_from_the_clock_row(self):
        self.assertEqual(self.day.periods, 4)
        self.assertEqual(self.day.timestamps_utc[0], "2026-11-26T22:00:00+00:00")

    def test_price_and_mix_series_are_read(self):
        self.assertEqual(self.day.price_up_eur_per_mwh, [300.0, 300.0, 100.0, 100.0])
        self.assertEqual(self.day.price_down_eur_per_mwh, [50.0, 50.0, 20.0, 20.0])
        self.assertEqual(self.day.system_load_mw[0], 5000.0)
        self.assertEqual(self.day.renewables_mw[-1], 1300.0)

    def test_storage_units_exclude_the_section_total(self):
        self.assertEqual(sorted(self.day.storage_units_mw), ["MYT_BZ1_01_SB", "PPC_BZ1_01_SB"])

    def test_without_a_clock_row_there_is_no_day(self):
        self.assertIsNone(balancing.parse_isp_rows([["nothing", 1.0]], "x"))


class StorageFleetBehaviourTests(unittest.TestCase):
    def setUp(self):
        self.day = balancing.parse_isp_rows(_isp_rows(), "x")
        self.behaviour = balancing.storage_fleet_behaviour(self.day)

    def test_charging_and_discharging_periods_counted(self):
        self.assertEqual(self.behaviour["periods_discharging"], 2)
        self.assertEqual(self.behaviour["periods_charging"], 2)

    def test_energy_is_power_times_the_quarter_hour(self):
        # Discharge: 100 MW for two quarter-hours = 50 MWh.
        self.assertEqual(self.behaviour["discharged_mwh"], 50.0)
        # Charge: 200 MW for two quarter-hours = 100 MWh.
        self.assertEqual(self.behaviour["charged_mwh"], 100.0)

    def test_prices_pair_discharge_with_up_and_charge_with_down(self):
        self.assertEqual(self.behaviour["average_discharge_price_eur_per_mwh"], 300.0)
        self.assertEqual(self.behaviour["average_charge_price_eur_per_mwh"], 20.0)
        self.assertEqual(self.behaviour["round_trip_spread_eur_per_mwh"], 280.0)

    def test_a_day_with_no_storage_section_yields_nothing(self):
        day = balancing.parse_isp_rows(
            [row for row in _isp_rows() if "Storage" not in str(row[0])], "x"
        )
        self.assertEqual(balancing.storage_fleet_behaviour(day), {})


class ReserveRequirementSummaryTests(unittest.TestCase):
    def setUp(self):
        self.summary = balancing.reserve_requirement_summary(balancing.parse_isp_rows(_isp_rows(), "x"))

    def test_products_being_procured_are_summarised(self):
        self.assertEqual(self.summary["FCR Up"], {"mean_mw": 65.0, "max_mw": 65.0, "min_mw": 65.0})
        self.assertEqual(self.summary["mFRR Up"]["mean_mw"], 650.0)
        self.assertEqual(self.summary["mFRR Up"]["max_mw"], 800.0)

    def test_a_product_at_zero_throughout_is_omitted(self):
        self.assertNotIn("RR Up", self.summary)

    def test_a_product_absent_from_the_file_is_omitted(self):
        self.assertNotIn("aFRR Down", self.summary)


if __name__ == "__main__":
    unittest.main()
