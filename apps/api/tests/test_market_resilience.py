import unittest
from unittest import mock
from urllib import error

from app import market

# A socket read timeout raises the builtin TimeoutError, which is NOT a
# subclass of urllib's URLError. Every best-effort guard in market.py listed
# URLError and not TimeoutError, so the commonest failure these endpoints have
# -- a slow upstream -- escaped the guard and returned 500 for the whole
# market signal, including the IPTO-sourced data that had loaded fine.
#
# Observed in the wild: `GET /market/greece 500` with a TimeoutError raised
# from fetch_day_ahead_price's urlopen.

NETWORK_FAILURES = [
    TimeoutError("The read operation timed out"),
    error.URLError("unreachable"),
    OSError("connection reset"),
]


class DayAheadPriceIsBestEffortTests(unittest.TestCase):
    def test_a_timeout_yields_none_rather_than_raising(self):
        with mock.patch.object(market.request, "urlopen", side_effect=TimeoutError("timed out")):
            self.assertIsNone(market.fetch_day_ahead_price())

    def test_every_plausible_network_failure_is_absorbed(self):
        for failure in NETWORK_FAILURES:
            with self.subTest(failure=type(failure).__name__):
                with mock.patch.object(market.request, "urlopen", side_effect=failure):
                    self.assertIsNone(market.fetch_day_ahead_price())


class IptoFetchesRaiseARecoverableErrorTests(unittest.TestCase):
    """The IPTO fetchers are allowed to fail, but only as RuntimeError, which
    get_greece_market_signal catches and turns into a status="error" response.
    A raw TimeoutError escaping them is a 500."""

    def test_file_listing_timeout_becomes_a_runtime_error(self):
        with mock.patch.object(market.request, "urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaises(RuntimeError):
                market.find_latest_ipto_file("ISP3ISPResults", 7)

    def test_flow_download_timeout_becomes_a_runtime_error(self):
        with mock.patch.object(market.request, "urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaises(RuntimeError):
                market.fetch_ipto_interconnection_flows("https://example.invalid/file.xls")

    def test_price_download_timeout_becomes_a_runtime_error(self):
        with mock.patch.object(market.request, "urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaises(RuntimeError):
                market.fetch_ipto_current_price("https://example.invalid/file.xlsx")


class MarketSignalDegradesRatherThanFailsTests(unittest.TestCase):
    def test_a_total_outage_returns_an_error_status_not_an_exception(self):
        with mock.patch.object(market.request, "urlopen", side_effect=TimeoutError("timed out")):
            response = market.get_greece_market_signal()
        self.assertEqual(response.status, "error")
        self.assertEqual(response.flows, [])
        self.assertTrue(response.summary)

    def test_a_dead_price_feed_does_not_take_down_the_curve_summary(self):
        with mock.patch.object(market.day_ahead, "fetch_day_ahead_curve", side_effect=TimeoutError("x")):
            with self.assertRaises(TimeoutError):
                # The curve builder itself does not guard -- day_ahead's own
                # fetchers do, returning None. This pins that contract: if the
                # guard ever moves, one of these two tests fails.
                market.build_day_ahead_curve_summary()

    def test_a_curve_feed_returning_nothing_is_not_an_error(self):
        with mock.patch.object(market.day_ahead, "fetch_day_ahead_curve", return_value=None):
            self.assertIsNone(market.build_day_ahead_curve_summary())


if __name__ == "__main__":
    unittest.main()
