import unittest
from datetime import datetime, timedelta, timezone

from app import market_feeds


class _Payload:
    """Stands in for a feed's payload, carrying how far its data reaches."""

    def __init__(self, covers_to: datetime | None, tag: str = "a"):
        self.covers_to = covers_to.isoformat() if covers_to else None
        self.tag = tag


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FeedRegistryTestCase(unittest.TestCase):
    """The registry is module-level state, so each test installs its own feed
    and clears the cache afterwards."""

    key = "test_feed"

    def install(
        self,
        load,
        *,
        cadence_minutes: int = 60,
        expected_lag_minutes: int = market_feeds.MINUTES_PER_DAY,
    ) -> None:
        spec = market_feeds.FeedSpec(
            key=self.key,
            label="Test feed",
            source="test",
            cadence_minutes=cadence_minutes,
            expected_lag_minutes=expected_lag_minutes,
            what_it_is_for="testing",
            load=load,
            covers_to=lambda payload: payload.covers_to,
        )
        market_feeds._BY_KEY[self.key] = spec
        self.addCleanup(market_feeds._BY_KEY.pop, self.key, None)
        self.addCleanup(market_feeds.reset)
        market_feeds.reset()


class CadenceTests(FeedRegistryTestCase):
    def test_a_cold_feed_is_fetched_once_and_then_cached(self):
        calls = []

        def load():
            calls.append(1)
            return _Payload(_now())

        self.install(load)
        market_feeds.get(self.key)
        market_feeds.get(self.key)
        market_feeds.get(self.key)
        # Cadence has not elapsed, so one fetch serves all three reads. This is
        # the whole point: a year of settlement files must not be refetched per
        # request.
        self.assertEqual(len(calls), 1)

    def test_an_elapsed_cadence_refetches(self):
        calls = []

        def load():
            calls.append(1)
            return _Payload(_now())

        self.install(load, cadence_minutes=0)
        market_feeds.get(self.key)
        market_feeds.get(self.key)
        self.assertEqual(len(calls), 2)

    def test_explicit_refresh_ignores_the_cadence(self):
        calls = []

        def load():
            calls.append(1)
            return _Payload(_now())

        self.install(load, cadence_minutes=10_000)
        market_feeds.get(self.key)
        market_feeds.get(self.key, refresh=True)
        self.assertEqual(len(calls), 2)


class FailureTests(FeedRegistryTestCase):
    def test_a_raising_loader_becomes_a_state_not_an_exception(self):
        def load():
            raise TimeoutError("the source hung")

        self.install(load)
        payload, state = market_feeds.get(self.key)
        self.assertIsNone(payload)
        self.assertEqual(state.status, market_feeds.STATUS_UNAVAILABLE)
        self.assertIn("TimeoutError", state.detail)

    def test_a_loader_returning_nothing_is_unavailable(self):
        self.install(lambda: None)
        _, state = market_feeds.get(self.key)
        self.assertEqual(state.status, market_feeds.STATUS_UNAVAILABLE)
        self.assertIn("returned nothing", state.detail)

    def test_a_failed_refresh_keeps_the_last_good_payload(self):
        attempts = []

        def load():
            attempts.append(1)
            if len(attempts) == 1:
                return _Payload(_now(), tag="good")
            raise ConnectionError("gone")

        self.install(load, cadence_minutes=0)
        first, _ = market_feeds.get(self.key)
        self.assertEqual(first.tag, "good")

        # An hour-old curve beats nothing, and its age is reported so nobody
        # mistakes it for current.
        second, state = market_feeds.get(self.key)
        self.assertEqual(second.tag, "good")
        self.assertIn("Refresh failed", state.detail)
        self.assertNotEqual(state.status, market_feeds.STATUS_UNAVAILABLE)

    def test_one_cold_feed_does_not_disturb_another(self):
        """A market dashboard must not go blank because one spreadsheet
        endpoint had a bad minute."""
        warm_key = "test_feed_warm"
        self.install(lambda: None)
        warm = market_feeds.FeedSpec(
            key=warm_key,
            label="Warm feed",
            source="test",
            cadence_minutes=60,
            expected_lag_minutes=market_feeds.MINUTES_PER_DAY,
            what_it_is_for="testing",
            load=lambda: _Payload(_now()),
            covers_to=lambda payload: payload.covers_to,
        )
        market_feeds._BY_KEY[warm_key] = warm
        self.addCleanup(market_feeds._BY_KEY.pop, warm_key, None)

        _, cold_state = market_feeds.get(self.key)
        payload, warm_state = market_feeds.get(warm_key)
        self.assertEqual(cold_state.status, market_feeds.STATUS_UNAVAILABLE)
        self.assertEqual(warm_state.status, market_feeds.STATUS_LIVE)
        self.assertIsNotNone(payload)


class LagTests(FeedRegistryTestCase):
    def test_data_within_the_expected_lag_is_live(self):
        self.install(lambda: _Payload(_now() - timedelta(hours=2)))
        _, state = market_feeds.get(self.key)
        self.assertEqual(state.status, market_feeds.STATUS_LIVE)
        self.assertAlmostEqual(state.lag_minutes, 120, delta=1)

    def test_data_beyond_the_expected_lag_is_stale(self):
        self.install(lambda: _Payload(_now() - timedelta(days=5)))
        _, state = market_feeds.get(self.key)
        self.assertEqual(state.status, market_feeds.STATUS_STALE)
        self.assertIn("days old", state.detail)

    def test_a_feed_that_lags_by_design_is_not_flagged(self):
        # Settlement is published a fortnight behind. That is the process, not
        # a stale feed, so its own expectation has to govern.
        self.install(
            lambda: _Payload(_now() - timedelta(days=12)),
            expected_lag_minutes=21 * market_feeds.MINUTES_PER_DAY,
        )
        _, state = market_feeds.get(self.key)
        self.assertEqual(state.status, market_feeds.STATUS_LIVE)

    def test_a_feed_publishing_ahead_of_now_has_negative_lag(self):
        # Day-ahead publishes tomorrow's prices around midday.
        self.install(lambda: _Payload(_now() + timedelta(hours=10)))
        _, state = market_feeds.get(self.key)
        self.assertLess(state.lag_minutes, 0)
        self.assertEqual(state.status, market_feeds.STATUS_LIVE)

    def test_a_payload_with_no_coverage_has_no_lag(self):
        self.install(lambda: _Payload(None))
        _, state = market_feeds.get(self.key)
        self.assertIsNone(state.lag_minutes)
        self.assertEqual(state.status, market_feeds.STATUS_LIVE)


class RegistryShapeTests(unittest.TestCase):
    def test_unknown_feed_raises(self):
        with self.assertRaises(KeyError):
            market_feeds.get("not_a_feed")

    def test_every_declared_feed_is_reachable_by_key(self):
        for spec in market_feeds.FEEDS:
            self.assertIn(spec.key, market_feeds._BY_KEY)

    def test_feeds_declare_a_cadence_and_an_expectation(self):
        for spec in market_feeds.FEEDS:
            self.assertGreater(spec.cadence_minutes, 0, spec.key)
            self.assertGreater(spec.expected_lag_minutes, 0, spec.key)
            self.assertTrue(spec.what_it_is_for.strip(), spec.key)


if __name__ == "__main__":
    unittest.main()
