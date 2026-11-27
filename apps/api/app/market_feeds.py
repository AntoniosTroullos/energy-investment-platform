"""The live market feeds, and how current each one is.

The problem this solves
-----------------------
The platform reads five external sources that update on five different
clocks. Day-ahead prices publish once a day for tomorrow. IPTO's scheduling
results are re-run through the day. Imbalance settlement arrives a week or two
late because it is money. A reanalysis weather archive trails by days. Nothing
useful can be said about "the current market" without saying which of those a
number came from and how old it is -- and a platform that refetches everything
on every request is both slow and wrong, because it hides the fact that most
of these series have not changed since the last look.

So each feed declares its own refresh cadence and its own expected publication
lag, and this module is the only thing that decides when to go and look again.
A caller asks for a feed and gets back the payload together with its state:
when it was last refreshed, how far behind real time its data actually
reaches, and whether that is normal for this feed or a sign something has
stopped publishing.

Cadence and lag are different things
------------------------------------
*Cadence* is how often it is worth asking the source for something new.
*Lag* is how far behind now the newest data is. A feed can be freshly
refreshed and still be two weeks behind -- that is simply what settlement is,
not a fault -- and it can be badly overdue while its data looks recent. Both
are reported, and `status` is judged on lag against the feed's own
expectation, so settlement is not permanently flagged red for being
settlement.

Failure is a state, not an exception
------------------------------------
An unreachable source makes a feed `unavailable` and leaves every other feed
alone. Nothing here raises: a market dashboard that goes blank because one
spreadsheet endpoint had a bad minute is worse than one that says which panel
is cold.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from . import balancing, day_ahead

STATUS_LIVE = "live"
STATUS_STALE = "stale"
STATUS_UNAVAILABLE = "unavailable"

MINUTES_PER_DAY = 1440


@dataclass(frozen=True)
class FeedSpec:
    key: str
    label: str
    source: str
    cadence_minutes: int
    # How far behind now this feed's newest data is expected to reach. A
    # feed whose data lags more than this has probably stopped publishing.
    expected_lag_minutes: int
    what_it_is_for: str
    load: Callable[[], Any]
    # Pulls the instant the payload's data reaches up to, for lag.
    covers_to: Callable[[Any], str | None]


@dataclass(frozen=True)
class FeedState:
    key: str
    label: str
    source: str
    status: str
    what_it_is_for: str
    cadence_minutes: int
    expected_lag_minutes: int
    refreshed_at_utc: str | None = None
    age_minutes: float | None = None
    covers_to_utc: str | None = None
    lag_minutes: float | None = None
    detail: str | None = None


@dataclass
class _Entry:
    payload: Any = None
    refreshed_at: datetime | None = None
    detail: str | None = None


_cache: dict[str, _Entry] = {}
# One lock for the whole registry. Endpoints are synchronous, so FastAPI runs
# them in a thread pool and two requests can arrive on one cold feed at once;
# without this they would both fetch, and a year of settlement files is not a
# fetch to do twice.
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# What each feed covers
# ---------------------------------------------------------------------------


def _day_ahead_covers_to(curve: day_ahead.DayAheadCurve | None) -> str | None:
    return curve.points[-1].timestamp if curve and curve.points else None


def _isp_covers_to(day: balancing.IspDay | None) -> str | None:
    return day.timestamps_utc[-1] if day and day.timestamps_utc else None


def _week_covers_to(week: balancing.ImbalanceWeek | None) -> str | None:
    return week.to_utc if week else None


def _year_covers_to(year: balancing.BalancingYear | None) -> str | None:
    return year.to_utc if year else None


FEEDS: tuple[FeedSpec, ...] = (
    FeedSpec(
        key="day_ahead",
        label="Day-ahead price",
        source="ENTSO-E Transparency, or Energy-Charts re-publishing it",
        cadence_minutes=60,
        # Day-ahead results for tomorrow publish around midday, so this feed
        # normally reaches INTO the future and its lag is negative.
        expected_lag_minutes=MINUTES_PER_DAY,
        what_it_is_for="What a generator earns per MWh, hour by hour.",
        load=lambda: day_ahead.fetch_day_ahead_curve(),
        covers_to=_day_ahead_covers_to,
    ),
    FeedSpec(
        key="isp_schedule",
        label="Operator scheduling results",
        source=balancing.SOURCE,
        cadence_minutes=30,
        expected_lag_minutes=MINUTES_PER_DAY,
        what_it_is_for=(
            "The grid as the operator is running it: balancing prices, reserve requirements "
            "and every dispatchable unit's schedule, in quarter-hours."
        ),
        load=lambda: balancing.fetch_isp_day(category="ISP3ISPResults"),
        covers_to=_isp_covers_to,
    ),
    FeedSpec(
        key="imbalance_settlement",
        label="Settled imbalance prices",
        source=balancing.SOURCE,
        cadence_minutes=360,
        # Settlement is published weekly and a fortnight behind. That is the
        # process, not a stale feed.
        expected_lag_minutes=21 * MINUTES_PER_DAY,
        what_it_is_for="The price a balance responsible party was actually charged.",
        load=lambda: balancing.fetch_imbalance_week(),
        covers_to=_week_covers_to,
    ),
    FeedSpec(
        key="balancing_year",
        label="Trailing year of balancing prices",
        source=balancing.SOURCE,
        cadence_minutes=720,
        expected_lag_minutes=21 * MINUTES_PER_DAY,
        what_it_is_for="The series a battery is simulated against, hour by hour.",
        load=lambda: balancing.get_balancing_year(),
        covers_to=_year_covers_to,
    ),
)

_BY_KEY = {spec.key: spec for spec in FEEDS}


# ---------------------------------------------------------------------------
# Reading feeds
# ---------------------------------------------------------------------------


def get(key: str, *, refresh: bool = False) -> tuple[Any, FeedState]:
    """A feed's payload and its state, refreshing only if its cadence says to."""
    spec = _BY_KEY.get(key)
    if spec is None:
        raise KeyError(f"No market feed named {key!r}.")

    with _lock:
        entry = _cache.setdefault(key, _Entry())
        if refresh or _is_due(spec, entry):
            _refresh(spec, entry)
        return entry.payload, _state(spec, entry)


def payload(key: str) -> Any:
    return get(key)[0]


def state(key: str) -> FeedState:
    return get(key)[1]


def all_states() -> list[FeedState]:
    """Every feed's state, in the order a reader wants them: the fastest-moving
    first. Each is fetched through `get`, so a cold feed warms here and a warm
    one costs nothing."""
    return [get(spec.key)[1] for spec in FEEDS]


def _is_due(spec: FeedSpec, entry: _Entry) -> bool:
    if entry.refreshed_at is None:
        return True
    age = (_now() - entry.refreshed_at).total_seconds() / 60.0
    return age >= spec.cadence_minutes


def _refresh(spec: FeedSpec, entry: _Entry) -> None:
    """Fetch, and treat any failure as a state rather than an error.

    A previously fetched payload is deliberately kept when a refresh fails: an
    hour-old price curve is far more use than nothing, and its age is reported
    so nobody mistakes it for current."""
    try:
        fetched = spec.load()
    except Exception as failure:  # noqa: BLE001 -- a feed must not take the API down
        entry.detail = f"Refresh failed: {type(failure).__name__}."
        if entry.payload is None:
            entry.refreshed_at = _now()
        return

    if fetched is None:
        entry.detail = "The source returned nothing for the window asked."
        if entry.payload is None:
            entry.refreshed_at = _now()
        return

    entry.payload = fetched
    entry.refreshed_at = _now()
    entry.detail = None


def _state(spec: FeedSpec, entry: _Entry) -> FeedState:
    if entry.payload is None:
        return FeedState(
            key=spec.key,
            label=spec.label,
            source=spec.source,
            status=STATUS_UNAVAILABLE,
            what_it_is_for=spec.what_it_is_for,
            cadence_minutes=spec.cadence_minutes,
            expected_lag_minutes=spec.expected_lag_minutes,
            refreshed_at_utc=_iso(entry.refreshed_at),
            detail=entry.detail or "Not available.",
        )

    covers_to = spec.covers_to(entry.payload)
    lag = _lag_minutes(covers_to)
    status = STATUS_LIVE
    detail = entry.detail
    if lag is not None and lag > spec.expected_lag_minutes:
        status = STATUS_STALE
        detail = detail or (
            f"Newest data is {lag / MINUTES_PER_DAY:.1f} days old; this feed normally reaches "
            f"within {spec.expected_lag_minutes / MINUTES_PER_DAY:.0f}."
        )

    return FeedState(
        key=spec.key,
        label=spec.label,
        source=spec.source,
        status=status,
        what_it_is_for=spec.what_it_is_for,
        cadence_minutes=spec.cadence_minutes,
        expected_lag_minutes=spec.expected_lag_minutes,
        refreshed_at_utc=_iso(entry.refreshed_at),
        age_minutes=(
            round((_now() - entry.refreshed_at).total_seconds() / 60.0, 1) if entry.refreshed_at else None
        ),
        covers_to_utc=covers_to,
        lag_minutes=None if lag is None else round(lag, 1),
        detail=detail,
    )


def _lag_minutes(covers_to: str | None) -> float | None:
    """How far behind now the newest data reaches. Negative for a feed that
    publishes ahead of time, which day-ahead does by design."""
    if not covers_to:
        return None
    try:
        moment = datetime.fromisoformat(covers_to)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (_now() - moment).total_seconds() / 60.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat(timespec="seconds") if moment else None


def reset() -> None:
    """Drop every cached payload. For tests, and for an operator who wants to
    force a full re-read without restarting the process."""
    with _lock:
        _cache.clear()
