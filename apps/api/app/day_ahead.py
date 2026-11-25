"""Greece's day-ahead wholesale price, as a curve rather than a number.

Why a curve
-----------
The market panel showed a single latest day-ahead price. For an investment
platform that is the least useful form of the number: what decides whether a
solar project is worth building is not the average price but the price AT THE
HOURS IT PRODUCES, and a point reading cannot express that. The same quantity
the solved scenarios now report as a capture price exists in the real market
too, and this module computes it from the actual curve.

The capture proxy
-----------------
A price curve alone still cannot say what solar earns -- that needs a
production shape. The solved scenarios carry one: the national availability of
each variable carrier by hour of day (`hour_of_day_availability_pu` in
app/hourly_market.py), measured on the solved network. Applying that shape to
today's real prices gives

    sum(price_h * shape_h) / sum(shape_h)

which is what a price-taking plant of that technology would have earned in the
real Greek day-ahead market over the period fetched. It is explicitly a proxy
on two counts, and the response says so: the shape is a modelled annual average
by hour, not today's weather, and it is national, not site-specific. What it is
good for is the comparison it enables -- modelled capture rate against actual
market capture rate -- which is the honest way to ask whether the model's
cannibalisation story resembles the market's.

Sources, and the licence question
---------------------------------
ENTSO-E's Transparency Platform is the origin of this data. It is used directly
when `ENTSOE_API_TOKEN` is set -- the deployment's own licensed access, free to
register for, with no redistribution restriction attached by a third party.

Without a token the fallback is Energy-Charts (Fraunhofer ISE), which
re-publishes the same ENTSO-E series over a no-auth API. Its own licence text
is explicit that the data is "for private and internal use only" and that
external or commercial use is prohibited. That text is returned verbatim with
every response that uses it, and `redistribution_allowed` is false, so a caller
cannot mistake it for data it may republish. Any public-facing deployment
should set a token.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib import error, parse, request
from xml.etree import ElementTree

ENV_ENTSOE_TOKEN = "ENTSOE_API_TOKEN"

ENTSOE_API_URL = "https://web-api.tp.entsoe.eu/api"
# Greece's bidding zone / control area EIC code.
ENTSOE_GREECE_DOMAIN = "10YGR-HTSO-----Y"

ENERGY_CHARTS_SERIES_URL = "https://api.energy-charts.info/price"
ENERGY_CHARTS_ZONE = "GR"

SOURCE_ENTSOE = "ENTSO-E Transparency Platform"
SOURCE_ENERGY_CHARTS = "Energy-Charts (Fraunhofer ISE), re-publishing ENTSO-E"

DEFAULT_LOOKBACK_DAYS = 2
REQUEST_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class PricePoint:
    timestamp: str
    price_eur_per_mwh: float


@dataclass(frozen=True)
class DayAheadCurve:
    points: list[PricePoint]
    source: str
    redistribution_allowed: bool
    licence_note: str | None = None
    unit: str = "EUR/MWh"

    @property
    def prices(self) -> list[float]:
        return [point.price_eur_per_mwh for point in self.points]


def entsoe_token(environ: dict[str, str] | None = None) -> str | None:
    env = os.environ if environ is None else environ
    token = env.get(ENV_ENTSOE_TOKEN, "").strip()
    return token or None


def fetch_day_ahead_curve(lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> DayAheadCurve | None:
    """The day-ahead curve from the best source available, or None if neither
    answers. Never raises: the market panel's IPTO-sourced flow data must not
    go down because a price feed did."""
    token = entsoe_token()
    if token:
        curve = _fetch_from_entsoe(token, lookback_days)
        if curve is not None:
            return curve
    return _fetch_from_energy_charts(lookback_days)


# ---------------------------------------------------------------------------
# ENTSO-E
# ---------------------------------------------------------------------------


def _fetch_from_entsoe(token: str, lookback_days: int) -> DayAheadCurve | None:
    now = datetime.now(timezone.utc)
    # Day-ahead results for tomorrow publish around midday, so the window
    # reaches forward as well as back.
    period_start = (now - timedelta(days=lookback_days)).strftime("%Y%m%d%H00")
    period_end = (now + timedelta(days=1)).strftime("%Y%m%d%H00")

    query = parse.urlencode(
        {
            "documentType": "A44",
            "in_Domain": ENTSOE_GREECE_DOMAIN,
            "out_Domain": ENTSOE_GREECE_DOMAIN,
            "periodStart": period_start,
            "periodEnd": period_end,
            "securityToken": token,
        }
    )
    try:
        with request.urlopen(f"{ENTSOE_API_URL}?{query}", timeout=REQUEST_TIMEOUT_SECONDS) as response:
            points = _parse_entsoe_prices(response.read())
    except (error.URLError, ElementTree.ParseError, ValueError, TimeoutError):
        return None

    if not points:
        return None
    return DayAheadCurve(
        points=points,
        source=SOURCE_ENTSOE,
        redistribution_allowed=True,
        licence_note=None,
    )


def _parse_entsoe_prices(payload: bytes) -> list[PricePoint]:
    """Publication_MarketDocument -> TimeSeries -> Period -> Point. Each Period
    gives a start instant and a resolution; each Point a 1-based position and a
    price. Namespaces vary by document version, so matching is on local tag
    names rather than a pinned namespace URI."""
    root = ElementTree.fromstring(payload)
    points: list[PricePoint] = []

    for period in _iter_local(root, "Period"):
        start_text = _first_text(period, "timeInterval", "start")
        resolution = _first_text(period, "resolution")
        if not start_text or not resolution:
            continue
        start = _parse_instant(start_text)
        step = _parse_resolution(resolution)
        if start is None or step is None:
            continue

        for point in _iter_local(period, "Point"):
            position_text = _first_text(point, "position")
            price_text = _first_text(point, "price.amount")
            if not position_text or not price_text:
                continue
            try:
                position = int(position_text)
                price = float(price_text)
            except ValueError:
                continue
            stamp = start + step * (position - 1)
            points.append(PricePoint(timestamp=stamp.isoformat(), price_eur_per_mwh=round(price, 2)))

    points.sort(key=lambda item: item.timestamp)
    return points


def _iter_local(element, local_name: str):
    for child in element.iter():
        if child.tag.rsplit("}", 1)[-1] == local_name:
            yield child


def _first_text(element, *local_names: str) -> str | None:
    current = element
    for name in local_names:
        current = next((child for child in _iter_local(current, name)), None)
        if current is None:
            return None
    return (current.text or "").strip() or None


def _parse_instant(text: str) -> datetime | None:
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None


def _parse_resolution(text: str) -> timedelta | None:
    return {"PT15M": timedelta(minutes=15), "PT30M": timedelta(minutes=30), "PT60M": timedelta(hours=1), "P1D": timedelta(days=1)}.get(
        text.strip().upper()
    )


# ---------------------------------------------------------------------------
# Energy-Charts (fallback)
# ---------------------------------------------------------------------------


def _fetch_from_energy_charts(lookback_days: int) -> DayAheadCurve | None:
    today = datetime.now(timezone.utc).date()
    query = parse.urlencode(
        {
            "bzn": ENERGY_CHARTS_ZONE,
            "start": (today - timedelta(days=lookback_days)).isoformat(),
            "end": today.isoformat(),
        }
    )
    try:
        with request.urlopen(f"{ENERGY_CHARTS_SERIES_URL}?{query}", timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, json.JSONDecodeError, TimeoutError):
        return None

    seconds = payload.get("unix_seconds") or []
    prices = payload.get("price") or []
    if not seconds or len(seconds) != len(prices):
        return None

    points = [
        PricePoint(
            timestamp=datetime.fromtimestamp(int(second), tz=timezone.utc).isoformat(),
            price_eur_per_mwh=round(float(price), 2),
        )
        for second, price in zip(seconds, prices)
        if price is not None
    ]
    if not points:
        return None

    return DayAheadCurve(
        points=points,
        source=SOURCE_ENERGY_CHARTS,
        # Their own terms: private and internal use only. Stated verbatim and
        # flagged, never quietly passed on as republishable data.
        redistribution_allowed=False,
        licence_note=str(payload.get("license_info") or "").strip() or None,
        unit=str(payload.get("unit") or "EUR/MWh"),
    )


# ---------------------------------------------------------------------------
# Derived statistics
# ---------------------------------------------------------------------------


def curve_statistics(curve: DayAheadCurve) -> dict:
    prices = curve.prices
    if not prices:
        return {}
    ordered = sorted(prices)
    return {
        "point_count": len(prices),
        "from_utc": curve.points[0].timestamp,
        "to_utc": curve.points[-1].timestamp,
        "mean_eur_per_mwh": round(sum(prices) / len(prices), 2),
        "min_eur_per_mwh": round(ordered[0], 2),
        "max_eur_per_mwh": round(ordered[-1], 2),
        "median_eur_per_mwh": round(ordered[len(ordered) // 2], 2),
        "spread_eur_per_mwh": round(ordered[-1] - ordered[0], 2),
        "negative_price_points": sum(1 for price in prices if price < 0),
    }


def capture_proxy(curve: DayAheadCurve, hour_of_day_shape: list[float]) -> dict | None:
    """What a price-taking plant with this hour-of-day production shape would
    have earned over the fetched curve, and that as a fraction of the curve's
    flat mean. Returns None when the shape and the curve do not overlap."""
    if len(hour_of_day_shape) != 24:
        return None

    weighted_value = 0.0
    weighted_volume = 0.0
    for point in curve.points:
        hour = _hour_of(point.timestamp)
        if hour is None:
            continue
        weight = hour_of_day_shape[hour]
        weighted_value += point.price_eur_per_mwh * weight
        weighted_volume += weight

    if weighted_volume <= 0:
        return None

    capture = weighted_value / weighted_volume
    prices = curve.prices
    flat_mean = sum(prices) / len(prices)
    return {
        "capture_price_eur_per_mwh": round(capture, 2),
        "flat_mean_eur_per_mwh": round(flat_mean, 2),
        "capture_rate_pct": round(100.0 * capture / flat_mean, 1) if flat_mean else None,
    }


def _hour_of(timestamp: str) -> int | None:
    """Hour of day in Greek local time.

    The hour-of-day shape is indexed by Greek local time, because that is the
    clock the sun and the market both run on, while price timestamps arrive in
    UTC. Getting this wrong would shift solar's production two or three hours
    against the price curve and quietly invert the capture result.

    The offset is computed from the EU rule rather than from zoneinfo, because
    a stock Windows Python has no tz database and this is not worth a
    dependency in an API that deliberately carries almost none."""
    try:
        moment = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (moment.astimezone(timezone.utc) + timedelta(hours=greek_utc_offset_hours(moment))).hour


def greek_utc_offset_hours(moment: datetime) -> int:
    """EET (UTC+2), or EEST (UTC+3) between 01:00 UTC on the last Sunday of
    March and 01:00 UTC on the last Sunday of October -- the EU-wide rule, which
    Greece has followed without exception for the period this platform covers."""
    utc = moment.astimezone(timezone.utc)
    start = _last_sunday(utc.year, 3).replace(hour=1, tzinfo=timezone.utc)
    end = _last_sunday(utc.year, 10).replace(hour=1, tzinfo=timezone.utc)
    return 3 if start <= utc < end else 2


def _last_sunday(year: int, month: int) -> datetime:
    day = 31 if month in (1, 3, 5, 7, 8, 10, 12) else 30
    last = datetime(year, month, day)
    # weekday(): Monday is 0, Sunday is 6.
    return last - timedelta(days=(last.weekday() + 1) % 7)
