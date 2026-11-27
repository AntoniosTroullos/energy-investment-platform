"""A full year, hour by hour: real Greek prices and real site weather.

Why not representative days
---------------------------
Everything the platform models so far rests on representative days -- twelve
of them, weighted to 8,760 hours. That is the right shape for a capacity
expansion solve, and the wrong shape for valuing a single asset. A battery
earns its money from the spread between the cheapest and dearest hours of each
day, and a representative day has already averaged most of that spread away. A
solar plant's revenue turns on how often price goes negative while the sun is
up, and in a representative year it never does. Degradation over twenty-five
years is a question about 219,000 distinct hours, not twelve.

So this module supplies the other thing: 8,760 real, consecutive hours.

  * Prices -- the Greek day-ahead curve for a calendar year, from the same
    sources as the live feed (ENTSO-E with a token, Energy-Charts otherwise).
    2025 came back with 177 negative hours, 357 at exactly zero and a range of
    -50 to 561 EUR/MWh. None of that survives averaging into a typical day,
    and all of it decides what an asset is worth.
  * Weather -- the ERA5 reanalysis for one location, hour by hour, through
    Open-Meteo's archive. A 30-degree array at Athens sums to 1,983 kWh/m^2 of
    plane-of-array irradiance over 2025, squarely in the expected Greek range.

Both are cached to disk on first fetch, because a year is a few hundred
kilobytes and refetching it per request would be absurd.

European markets moved to a 15-minute settlement period during 2025, so a
year's price series arrives partly quarter-hourly and partly hourly. Prices are
averaged within each UTC hour, which is the correct aggregation for an
energy-weighted revenue calculation and keeps the series aligned with the
weather.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib import error, parse, request

from . import day_ahead

HOURS_PER_YEAR = 8760
CACHE_DIRNAME = "hourly_series"
REQUEST_TIMEOUT_SECONDS = 120

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# The fixed-tilt geometry the yield models assume (see app/site_yield.py).
DEFAULT_TILT_DEGREES = 30
DEFAULT_AZIMUTH_DEGREES = 0


@dataclass(frozen=True)
class PriceYear:
    """One calendar year of Greek day-ahead prices, hour by hour."""

    year: int
    source: str
    redistribution_allowed: bool
    prices_eur_per_mwh: list[float]
    missing_hours: int

    @property
    def mean_eur_per_mwh(self) -> float:
        return sum(self.prices_eur_per_mwh) / len(self.prices_eur_per_mwh) if self.prices_eur_per_mwh else 0.0

    @property
    def negative_hours(self) -> int:
        return sum(1 for price in self.prices_eur_per_mwh if price < 0)

    @property
    def zero_or_negative_hours(self) -> int:
        return sum(1 for price in self.prices_eur_per_mwh if price <= 0)


@dataclass(frozen=True)
class WeatherYear:
    """One calendar year of hourly weather at one location."""

    year: int
    latitude: float
    longitude: float
    plane_of_array_w_m2: list[float]
    temperature_c: list[float]
    wind_speed_100m_kmh: list[float]
    surface_pressure_hpa: list[float]

    @property
    def hours(self) -> int:
        return len(self.plane_of_array_w_m2)


def cache_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "generated" / CACHE_DIRNAME


def _read_cache(name: str) -> dict | None:
    path = cache_dir() / name
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(name: str, payload: dict) -> None:
    directory = cache_dir()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------


def get_price_year(year: int, *, refresh: bool = False) -> PriceYear | None:
    """A calendar year of hourly Greek day-ahead prices, cached on disk.

    Returns None when the year cannot be fetched and nothing is cached -- a
    caller must then fall back to a modelled price series rather than invent
    one."""
    cache_name = f"prices_GR_{year}.json"
    if not refresh:
        cached = _read_cache(cache_name)
        if cached:
            return PriceYear(
                year=year,
                source=cached["source"],
                redistribution_allowed=cached["redistribution_allowed"],
                prices_eur_per_mwh=cached["prices_eur_per_mwh"],
                missing_hours=cached["missing_hours"],
            )

    fetched = _fetch_price_year(year)
    if fetched is None:
        return None

    _write_cache(
        cache_name,
        {
            "source": fetched.source,
            "redistribution_allowed": fetched.redistribution_allowed,
            "prices_eur_per_mwh": [round(price, 2) for price in fetched.prices_eur_per_mwh],
            "missing_hours": fetched.missing_hours,
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )
    return fetched


def _fetch_price_year(year: int) -> PriceYear | None:
    curve = day_ahead.fetch_day_ahead_curve_between(
        datetime(year, 1, 1, tzinfo=timezone.utc),
        datetime(year, 12, 31, 23, 0, tzinfo=timezone.utc),
    )
    if curve is None or not curve.points:
        return None

    hourly = _average_into_hours(curve, year)
    if hourly is None:
        return None
    prices, missing = hourly
    return PriceYear(
        year=year,
        source=curve.source,
        redistribution_allowed=curve.redistribution_allowed,
        prices_eur_per_mwh=prices,
        missing_hours=missing,
    )


def _average_into_hours(curve: day_ahead.DayAheadCurve, year: int) -> tuple[list[float], int] | None:
    """Collapses a curve of any resolution onto the year's UTC hours.

    The market moved to 15-minute settlement partway through 2025, so one
    year's series is genuinely mixed-resolution. Averaging within the hour is
    the right aggregation for revenue (energy over an hour at a price that
    varied within it) and keeps prices aligned with hourly weather.

    An hour with no data at all inherits the previous hour's price -- a gap of
    a few hours in a year of 8,760 must not shift an annual total, and a zero
    would do exactly that by looking like a free hour."""
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    buckets: dict[int, list[float]] = {}

    for point in curve.points:
        try:
            moment = datetime.fromisoformat(point.timestamp)
        except ValueError:
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        index = int((moment.astimezone(timezone.utc) - start).total_seconds() // 3600)
        if 0 <= index < HOURS_PER_YEAR:
            buckets.setdefault(index, []).append(point.price_eur_per_mwh)

    if not buckets:
        return None

    prices: list[float] = []
    missing = 0
    last = None
    for index in range(HOURS_PER_YEAR):
        values = buckets.get(index)
        if values:
            last = sum(values) / len(values)
        else:
            missing += 1
            if last is None:
                last = 0.0
        prices.append(last)
    return prices, missing


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------


def get_weather_year(
    latitude: float,
    longitude: float,
    year: int,
    *,
    refresh: bool = False,
) -> WeatherYear | None:
    """A calendar year of hourly weather at one site, from ERA5 reanalysis.

    Cached per rounded coordinate: a tenth of a degree is about 10 km, finer
    than the reanalysis grid itself, so two candidate cells in the same area
    legitimately share a series instead of each fetching one."""
    key_lat, key_lon = round(latitude, 1), round(longitude, 1)
    cache_name = f"weather_{key_lat}_{key_lon}_{year}.json"

    if not refresh:
        cached = _read_cache(cache_name)
        if cached:
            return WeatherYear(
                year=year,
                latitude=key_lat,
                longitude=key_lon,
                plane_of_array_w_m2=cached["plane_of_array_w_m2"],
                temperature_c=cached["temperature_c"],
                wind_speed_100m_kmh=cached["wind_speed_100m_kmh"],
                surface_pressure_hpa=cached["surface_pressure_hpa"],
            )

    fetched = _fetch_weather_year(key_lat, key_lon, year)
    if fetched is None:
        return None

    _write_cache(
        cache_name,
        {
            "plane_of_array_w_m2": [round(value, 1) for value in fetched.plane_of_array_w_m2],
            "temperature_c": [round(value, 1) for value in fetched.temperature_c],
            "wind_speed_100m_kmh": [round(value, 1) for value in fetched.wind_speed_100m_kmh],
            "surface_pressure_hpa": [round(value, 1) for value in fetched.surface_pressure_hpa],
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )
    return fetched


def _fetch_weather_year(latitude: float, longitude: float, year: int) -> WeatherYear | None:
    query = parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": f"{year}-01-01",
            "end_date": f"{year}-12-31",
            "hourly": ",".join(
                ["global_tilted_irradiance", "temperature_2m", "wind_speed_100m", "surface_pressure"]
            ),
            "tilt": DEFAULT_TILT_DEGREES,
            "azimuth": DEFAULT_AZIMUTH_DEGREES,
            "timezone": "UTC",
        }
    )
    http_request = request.Request(
        f"{OPEN_METEO_ARCHIVE_URL}?{query}",
        headers={"Accept": "application/json", "User-Agent": "energy-investment-platform/0.1"},
    )
    try:
        with request.urlopen(http_request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, json.JSONDecodeError, TimeoutError):
        return None

    hourly = payload.get("hourly") or {}
    timestamps = hourly.get("time") or []
    if not timestamps:
        return None

    # A leap year has 8,784 hours; everything downstream works in whole years
    # of 8,760, so the tail is trimmed rather than left to misalign with the
    # price series.
    length = min(HOURS_PER_YEAR, len(timestamps))

    def column(name: str) -> list[float]:
        values = hourly.get(name) or []
        return [float(value) if isinstance(value, (int, float)) else 0.0 for value in values[:length]] + [
            0.0
        ] * max(0, length - len(values))

    return WeatherYear(
        year=year,
        latitude=latitude,
        longitude=longitude,
        plane_of_array_w_m2=column("global_tilted_irradiance"),
        temperature_c=column("temperature_2m"),
        wind_speed_100m_kmh=column("wind_speed_100m"),
        surface_pressure_hpa=column("surface_pressure"),
    )


def hour_timestamps(year: int) -> list[str]:
    """ISO timestamps for the year's hours, for charting a simulated series."""
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    return [(start + timedelta(hours=hour)).isoformat() for hour in range(HOURS_PER_YEAR)]
