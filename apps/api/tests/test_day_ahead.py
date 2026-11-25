import unittest
from datetime import datetime, timedelta, timezone

from app.day_ahead import (
    DayAheadCurve,
    PricePoint,
    _parse_entsoe_prices,
    capture_proxy,
    curve_statistics,
    entsoe_token,
    greek_utc_offset_hours,
)

# A minimal but real-shaped ENTSO-E day-ahead document: one Period, hourly
# resolution, three points. Namespaced exactly as the live API returns it.
ENTSOE_DOCUMENT = b"""<?xml version="1.0" encoding="UTF-8"?>
<Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:0">
  <TimeSeries>
    <Period>
      <timeInterval>
        <start>2026-11-24T23:00Z</start>
        <end>2026-11-25T02:00Z</end>
      </timeInterval>
      <resolution>PT60M</resolution>
      <Point><position>1</position><price.amount>80.10</price.amount></Point>
      <Point><position>2</position><price.amount>75.50</price.amount></Point>
      <Point><position>3</position><price.amount>-1.25</price.amount></Point>
    </Period>
  </TimeSeries>
</Publication_MarketDocument>
"""


class GreekClockTests(unittest.TestCase):
    def test_winter_is_two_hours_ahead_of_utc(self):
        self.assertEqual(greek_utc_offset_hours(datetime(2026, 1, 15, tzinfo=timezone.utc)), 2)

    def test_summer_is_three_hours_ahead_of_utc(self):
        self.assertEqual(greek_utc_offset_hours(datetime(2026, 7, 15, tzinfo=timezone.utc)), 3)

    def test_the_switch_is_the_last_sunday_of_march(self):
        # 29 March 2026 is the last Sunday; the day before is still winter.
        self.assertEqual(greek_utc_offset_hours(datetime(2026, 3, 28, 2, tzinfo=timezone.utc)), 2)
        self.assertEqual(greek_utc_offset_hours(datetime(2026, 3, 29, 2, tzinfo=timezone.utc)), 3)

    def test_the_switch_back_is_the_last_sunday_of_october(self):
        self.assertEqual(greek_utc_offset_hours(datetime(2026, 10, 24, 2, tzinfo=timezone.utc)), 3)
        self.assertEqual(greek_utc_offset_hours(datetime(2026, 10, 25, 2, tzinfo=timezone.utc)), 2)


class EntsoeParsingTests(unittest.TestCase):
    def test_positions_become_timestamps_at_the_periods_resolution(self):
        points = _parse_entsoe_prices(ENTSOE_DOCUMENT)
        self.assertEqual(len(points), 3)
        self.assertEqual(points[0].timestamp, "2026-11-24T23:00:00+00:00")
        self.assertEqual(points[1].timestamp, "2026-11-25T00:00:00+00:00")
        self.assertEqual(points[2].timestamp, "2026-11-25T01:00:00+00:00")

    def test_negative_prices_survive(self):
        # Negative day-ahead prices are real and are exactly the hours a
        # renewable investment case turns on -- never clamp them to zero.
        points = _parse_entsoe_prices(ENTSOE_DOCUMENT)
        self.assertEqual(points[2].price_eur_per_mwh, -1.25)

    def test_a_document_with_no_points_yields_nothing_rather_than_raising(self):
        empty = b'<?xml version="1.0"?><Publication_MarketDocument></Publication_MarketDocument>'
        self.assertEqual(_parse_entsoe_prices(empty), [])


def hourly_curve(prices: list[float]) -> DayAheadCurve:
    """A curve starting at 00:00 Greek winter time (22:00 UTC the day before),
    one point per hour, so hour indices line up with list positions."""
    base = datetime(2026, 1, 14, 22, 0, tzinfo=timezone.utc)
    points = [
        PricePoint(timestamp=(base + timedelta(hours=index)).isoformat(), price_eur_per_mwh=price)
        for index, price in enumerate(prices)
    ]
    return DayAheadCurve(points=points, source="test", redistribution_allowed=True)


class CaptureProxyTests(unittest.TestCase):
    def test_a_flat_shape_captures_the_flat_mean(self):
        curve = hourly_curve([float(hour) for hour in range(24)])
        result = capture_proxy(curve, [1.0] * 24)
        self.assertAlmostEqual(result["capture_price_eur_per_mwh"], result["flat_mean_eur_per_mwh"], places=2)
        self.assertAlmostEqual(result["capture_rate_pct"], 100.0, places=1)

    def test_a_daytime_shape_against_cheap_daytime_prices_captures_below_the_mean(self):
        # Prices 100 overnight, 20 in the middle of the day: the shape of a
        # cannibalised solar market. A solar-shaped producer must come out
        # below the flat mean, which is the whole point of the measure.
        prices = [100.0] * 24
        for hour in range(9, 17):
            prices[hour] = 20.0
        shape = [0.0] * 24
        for hour in range(9, 17):
            shape[hour] = 1.0

        result = capture_proxy(hourly_curve(prices), shape)
        self.assertEqual(result["capture_price_eur_per_mwh"], 20.0)
        self.assertLess(result["capture_rate_pct"], 100.0)

    def test_an_all_zero_shape_has_no_capture_price(self):
        self.assertIsNone(capture_proxy(hourly_curve([50.0] * 24), [0.0] * 24))

    def test_a_wrong_length_shape_is_rejected(self):
        self.assertIsNone(capture_proxy(hourly_curve([50.0] * 24), [1.0] * 12))


class StatisticsTests(unittest.TestCase):
    def test_statistics_describe_the_curve(self):
        stats = curve_statistics(hourly_curve([10.0, -5.0, 30.0, 20.0]))
        self.assertEqual(stats["point_count"], 4)
        self.assertEqual(stats["min_eur_per_mwh"], -5.0)
        self.assertEqual(stats["max_eur_per_mwh"], 30.0)
        self.assertEqual(stats["negative_price_points"], 1)
        self.assertEqual(stats["spread_eur_per_mwh"], 35.0)

    def test_an_empty_curve_has_no_statistics(self):
        self.assertEqual(curve_statistics(DayAheadCurve(points=[], source="test", redistribution_allowed=True)), {})


class TokenTests(unittest.TestCase):
    def test_a_blank_token_counts_as_absent(self):
        self.assertIsNone(entsoe_token({"ENTSOE_API_TOKEN": "   "}))

    def test_a_set_token_is_returned_stripped(self):
        self.assertEqual(entsoe_token({"ENTSOE_API_TOKEN": " abc "}), "abc")


if __name__ == "__main__":
    unittest.main()
