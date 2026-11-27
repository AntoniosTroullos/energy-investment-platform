"""Greece's balancing and imbalance market, as IPTO settles it.

Why this exists
---------------
Day-ahead is the market this platform could already read, and for a solar or
wind plant it is most of the story. For a battery it is not. A battery in
Greece earns from the spread between what the system pays to be given energy
and what it pays to absorb it, and that spread lives in the balancing market,
not day-ahead. Valuing storage on day-ahead arbitrage alone understates it --
often severely, because the balancing spread is several times the day-ahead
spread and goes negative far more often.

Two feeds, two different things
-------------------------------
*The ISP results file* (`IPTO ISP1`) is the operator's schedule for a market
day: 96 quarter-hours of balancing energy prices, cleared balancing volumes,
reserve requirements by product, and the dispatch of every thermal, hydro and
storage unit on the system. It is published day-ahead and re-run intraday, so
it is the closest thing to a live view of the Greek grid. It also happens to
reveal what the operating Greek battery fleet actually did, hour by hour,
which is the only real-world check this platform has on its own storage model.

*The imbalance file* (`IMBABE`) is settlement: a week of quarter-hours with
the imbalance price each Balance Responsible Party was actually charged, the
mFRR clearing prices up and down, the system's deviation, and the uplift
accounts. It arrives with a lag of roughly one to two weeks, because it is
money rather than a forecast. This is the authoritative price series.

On not hard-coding the pricing rule
-----------------------------------
Greece sets the imbalance price from the marginal balancing product, switching
on the sign of the system deviation, with a band near zero that falls back to
the value of avoided activation (Article 19.6 of the Balancing Market
Rulebook). The rule has been amended more than once and the thresholds are
regulatory parameters, so this module does not encode it. It *measures* it
instead: `pricing_attribution` reports what share of settled periods took the
mFRR up price, the mFRR down price, or neither.

On the most recent settled week that came to roughly a third, a quarter and
two fifths. The two fifths matching neither mFRR price are NOT the dead band:
only 35 of those 282 periods had a system deviation inside the 25 MW band, and
the rest showed deviations as large as the mFRR-priced periods. Something else
in the merit order was marginal in them -- most likely aFRR, whose clearing
price these files do not carry. That is reported as measured rather than
explained away, because a platform that re-derives the rule from this week's
settlement cannot be made wrong by next year's amendment, and a drifting
"neither" share is itself worth seeing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median

from . import ipto

SOURCE = ipto.SOURCE

# An Imbalance Settlement Period in Greece is a quarter of an hour.
ISP_MINUTES = 15
ISP_HOURS = ISP_MINUTES / 60.0
PERIODS_PER_DAY = 96

# The settlement file is weekly and lags real time; look back far enough to
# find the most recent published week without asking for a year of listings.
IMBALANCE_LOOKBACK_DAYS = 28
ISP_LOOKBACK_DAYS = 3

# Reserve products as the ISP file names them, in the order a trader thinks
# about them: fastest first.
RESERVE_PRODUCTS = (
    "FCR Up",
    "FCR Down",
    "aFRR Up",
    "aFRR Down",
    "mFRR Up",
    "mFRR Down",
    "Spinning RR Up",
    "Spinning RR Down",
    "RR Up",
    "RR Down",
)

# Within a period the imbalance price is compared with the mFRR prices to see
# which one set it. Settlement rounds to the cent, so the comparison does too.
PRICE_MATCH_TOLERANCE = 0.01


# ---------------------------------------------------------------------------
# Settled imbalance prices (IMBABE)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImbalancePeriod:
    start_utc: str
    imbalance_price_eur_per_mwh: float
    mfrr_up_eur_per_mwh: float | None
    mfrr_down_eur_per_mwh: float | None
    activated_up_mwh: float | None
    activated_down_mwh: float | None
    system_deviation_mwh: float | None

    @property
    def system_short(self) -> bool | None:
        """True when the system needed energy -- the hours a battery is paid
        most to discharge. None when the deviation was not published."""
        if self.system_deviation_mwh is None:
            return None
        return self.system_deviation_mwh > 0


@dataclass(frozen=True)
class ImbalanceWeek:
    periods: list[ImbalancePeriod]
    file_name: str
    source: str = SOURCE

    @property
    def from_utc(self) -> str | None:
        return self.periods[0].start_utc if self.periods else None

    @property
    def to_utc(self) -> str | None:
        if not self.periods:
            return None
        last = datetime.fromisoformat(self.periods[-1].start_utc) + timedelta(minutes=ISP_MINUTES)
        return last.isoformat()

    @property
    def prices(self) -> list[float]:
        return [period.imbalance_price_eur_per_mwh for period in self.periods]


# IMBABE column layout. The header text carries mojibake (a Δ and a euro sign
# written in a legacy code page), so columns are taken by position, which has
# been stable, and the expected header is checked loosely rather than matched.
_IMB_START = 0
_IMB_ACTIVATED_UP = 2
_IMB_ACTIVATED_DOWN = 3
_IMB_DEVIATION = 5
_IMB_IMBALANCE_PRICE = 7
_IMB_MFRR_UP = 8
_IMB_MFRR_DOWN = 9
_IMB_MIN_COLUMNS = 10


def fetch_imbalance_week(
    *, lookback_days: int = IMBALANCE_LOOKBACK_DAYS, end: date | None = None
) -> ImbalanceWeek | None:
    """The most recently settled week of imbalance prices, or None if IPTO
    published none in the window."""
    try:
        published = ipto.latest_file(ipto.CATEGORY_IMBALANCE, lookback_days, end=end)
        rows = ipto.read_rows(ipto.download(published))
    except ipto.IptoUnavailable:
        return None

    periods = parse_imbalance_rows(rows)
    if not periods:
        return None
    return ImbalanceWeek(periods=periods, file_name=published.name)


def parse_imbalance_rows(rows: list[list[object]]) -> list[ImbalancePeriod]:
    periods: list[ImbalancePeriod] = []
    for row in rows:
        if len(row) < _IMB_MIN_COLUMNS:
            continue
        serial = ipto.to_float(row[_IMB_START])
        price = ipto.to_float(row[_IMB_IMBALANCE_PRICE])
        # The header row's first cell is text, so it fails the serial check and
        # needs no special case.
        if serial is None or price is None or not 40000 < serial < 80000:
            continue
        periods.append(
            ImbalancePeriod(
                start_utc=ipto.athens_serial_to_utc(serial).isoformat(),
                imbalance_price_eur_per_mwh=round(price, 2),
                mfrr_up_eur_per_mwh=_rounded(row, _IMB_MFRR_UP),
                mfrr_down_eur_per_mwh=_rounded(row, _IMB_MFRR_DOWN),
                activated_up_mwh=_rounded(row, _IMB_ACTIVATED_UP, digits=3),
                activated_down_mwh=_rounded(row, _IMB_ACTIVATED_DOWN, digits=3),
                system_deviation_mwh=_rounded(row, _IMB_DEVIATION, digits=3),
            )
        )
    periods.sort(key=lambda period: period.start_utc)
    return periods


def _rounded(row: list[object], column: int, *, digits: int = 2) -> float | None:
    if column >= len(row):
        return None
    value = ipto.to_float(row[column])
    return None if value is None else round(value, digits)


# ---------------------------------------------------------------------------
# What the settled week says
# ---------------------------------------------------------------------------


def imbalance_statistics(week: ImbalanceWeek) -> dict:
    """The settled week as the numbers a storage business case needs."""
    prices = week.prices
    if not prices:
        return {}

    short = [period for period in week.periods if period.system_short is True]
    long = [period for period in week.periods if period.system_short is False]
    ordered = sorted(prices)

    return {
        "periods": len(prices),
        "from_utc": week.from_utc,
        "to_utc": week.to_utc,
        "mean_eur_per_mwh": round(sum(prices) / len(prices), 2),
        "median_eur_per_mwh": round(median(prices), 2),
        "p10_eur_per_mwh": round(_percentile(ordered, 10), 2),
        "p90_eur_per_mwh": round(_percentile(ordered, 90), 2),
        "min_eur_per_mwh": round(ordered[0], 2),
        "max_eur_per_mwh": round(ordered[-1], 2),
        "negative_periods": sum(1 for price in prices if price < 0),
        # The quantity that decides a battery's balancing revenue: what the
        # system pays when it is short, against what it pays when it is long.
        "system_short_periods": len(short),
        "system_long_periods": len(long),
        "mean_price_when_short_eur_per_mwh": _mean_price(short),
        "mean_price_when_long_eur_per_mwh": _mean_price(long),
        "short_long_spread_eur_per_mwh": _spread(_mean_price(short), _mean_price(long)),
        "activated_up_mwh": _total(week, "activated_up_mwh"),
        "activated_down_mwh": _total(week, "activated_down_mwh"),
    }


def mfrr_statistics(week: ImbalanceWeek) -> dict:
    """The mFRR clearing prices, which are what a unit holding manual reserve
    is actually paid for energy when it is called."""
    up = [p.mfrr_up_eur_per_mwh for p in week.periods if p.mfrr_up_eur_per_mwh is not None]
    down = [p.mfrr_down_eur_per_mwh for p in week.periods if p.mfrr_down_eur_per_mwh is not None]
    if not up or not down:
        return {}
    mean_up = sum(up) / len(up)
    mean_down = sum(down) / len(down)
    return {
        "mean_up_eur_per_mwh": round(mean_up, 2),
        "mean_down_eur_per_mwh": round(mean_down, 2),
        "median_up_eur_per_mwh": round(median(up), 2),
        "median_down_eur_per_mwh": round(median(down), 2),
        "max_up_eur_per_mwh": round(max(up), 2),
        "min_down_eur_per_mwh": round(min(down), 2),
        # A battery that discharges on an up call and charges on a down call
        # earns this per MWh cycled, before losses and wear.
        "mean_spread_eur_per_mwh": round(mean_up - mean_down, 2),
        "negative_down_periods": sum(1 for price in down if price < 0),
    }


def pricing_attribution(week: ImbalanceWeek) -> dict:
    """Which price set settlement, measured rather than assumed.

    See the module docstring: Greece's imbalance price follows the marginal
    balancing product, and which products exist and how they are priced are
    regulatory parameters that have changed. Measuring the attribution keeps
    the platform correct across amendments, and the share matching neither mFRR
    price measures how much of settlement these files cannot account for on
    their own."""
    matched_up = 0
    matched_down = 0
    neither = 0
    for period in week.periods:
        price = period.imbalance_price_eur_per_mwh
        if _matches(price, period.mfrr_up_eur_per_mwh):
            matched_up += 1
        elif _matches(price, period.mfrr_down_eur_per_mwh):
            matched_down += 1
        else:
            neither += 1

    total = matched_up + matched_down + neither
    if total == 0:
        return {}
    return {
        "periods": total,
        "set_by_mfrr_up": matched_up,
        "set_by_mfrr_down": matched_down,
        "set_by_neither": neither,
        "set_by_mfrr_up_pct": round(100.0 * matched_up / total, 1),
        "set_by_mfrr_down_pct": round(100.0 * matched_down / total, 1),
        "set_by_neither_pct": round(100.0 * neither / total, 1),
    }


def _matches(price: float, candidate: float | None) -> bool:
    return candidate is not None and abs(price - candidate) <= PRICE_MATCH_TOLERANCE


def _mean_price(periods: list[ImbalancePeriod]) -> float | None:
    if not periods:
        return None
    return round(sum(p.imbalance_price_eur_per_mwh for p in periods) / len(periods), 2)


def _spread(high: float | None, low: float | None) -> float | None:
    return None if high is None or low is None else round(high - low, 2)


def _total(week: ImbalanceWeek, attribute: str) -> float | None:
    values = [getattr(p, attribute) for p in week.periods]
    present = [value for value in values if value is not None]
    return round(sum(present), 1) if present else None


def _percentile(ordered: list[float], percent: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percent / 100.0
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


# ---------------------------------------------------------------------------
# The operator's own schedule for a market day (ISP results)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IspDay:
    """One market day of IPTO's integrated scheduling results."""

    timestamps_utc: list[str]
    file_name: str
    price_up_eur_per_mwh: list[float | None]
    price_down_eur_per_mwh: list[float | None]
    cleared_up_mwh: list[float | None]
    cleared_down_mwh: list[float | None]
    system_load_mw: list[float | None]
    renewables_mw: list[float | None]
    thermal_mw: list[float | None]
    hydro_mw: list[float | None]
    storage_mw: list[float | None]
    reserve_requirement_mw: dict[str, list[float | None]]
    storage_units_mw: dict[str, list[float | None]]
    source: str = SOURCE

    @property
    def periods(self) -> int:
        return len(self.timestamps_utc)


def fetch_isp_day(
    *, category: str = ipto.CATEGORY_ISP_RESULTS, lookback_days: int = ISP_LOOKBACK_DAYS
) -> IspDay | None:
    """The most recent published ISP day, or None if IPTO is unreachable.

    The day-ahead run (ISP1) is the default because it covers all 96 periods;
    the intraday re-runs cover only the remainder of the day."""
    try:
        published = ipto.latest_file(category, lookback_days)
        # Intraday runs are re-published through the day, so the cached copy of
        # a file named for today may be superseded. Named files are immutable,
        # and IPTO bumps the run number, so the cache stays correct either way.
        rows = ipto.read_rows(ipto.download(published))
    except ipto.IptoUnavailable:
        return None
    return parse_isp_rows(rows, published.name)


def parse_isp_rows(rows: list[list[object]], file_name: str) -> IspDay | None:
    clock = next((row for row in rows if ipto.row_label(row) == "Non Dispatchable Load"), None)
    if clock is None:
        return None
    timestamps = ipto.period_timestamps(clock)
    if not timestamps:
        return None
    width = len(timestamps)

    def series(label: str, *, after: int = 0) -> list[float | None]:
        row = ipto.find_row(rows, label, after=after)
        if row is None:
            return [None] * width
        return [_rounded(row, column + 1, digits=3) for column in range(width)]

    reserves = {product: series(product) for product in RESERVE_PRODUCTS}

    return IspDay(
        timestamps_utc=[stamp.isoformat() for stamp in timestamps],
        file_name=file_name,
        price_up_eur_per_mwh=series("Greece Price Energy Up"),
        price_down_eur_per_mwh=series("Greece Price Energy Down"),
        cleared_up_mwh=series("Greece Cleared Energy Up"),
        cleared_down_mwh=series("Greece Cleared Energy Down"),
        system_load_mw=series("System Load+Losses"),
        renewables_mw=series("Renewables"),
        thermal_mw=series("Total Thermal Production"),
        hydro_mw=series("Total Hydro Production"),
        storage_mw=series("Total Storage Production"),
        reserve_requirement_mw={
            product: values for product, values in reserves.items() if any(v is not None for v in values)
        },
        storage_units_mw=_storage_units(rows, width),
    )


def _storage_units(rows: list[list[object]], width: int) -> dict[str, list[float | None]]:
    """Every storage unit's scheduled dispatch, positive discharging.

    This is the Greek battery and pumped-storage fleet as the operator
    dispatches it. The section is located by its heading rather than by row
    number, because IPTO adds units to it as they connect -- which, for a
    market this young, happens often."""
    bounds = ipto.section_bounds(rows, "Storage Units")
    if bounds is None:
        return {}
    start, end = bounds
    units: dict[str, list[float | None]] = {}
    for row in rows[start:end]:
        label = ipto.row_label(row)
        if not label or label.startswith("Total"):
            continue
        units[label] = [_rounded(row, column + 1, digits=3) for column in range(width)]
    return units


def storage_fleet_behaviour(day: IspDay) -> dict:
    """What the operating Greek storage fleet did on this day, and at what
    prices -- the one real-world check available on the storage model.

    A unit's dispatch is positive discharging and negative charging, so the
    fleet's charge and discharge volumes can be weighted by the balancing
    price in the same period to recover the prices it actually traded at."""
    if not day.storage_units_mw:
        return {}

    charge_energy = 0.0
    discharge_energy = 0.0
    charge_value = 0.0
    discharge_value = 0.0
    periods_charging = 0
    periods_discharging = 0

    for index in range(day.periods):
        fleet = sum(
            values[index]
            for values in day.storage_units_mw.values()
            if index < len(values) and values[index] is not None
        )
        energy = abs(fleet) * ISP_HOURS
        if fleet < 0:
            periods_charging += 1
            charge_energy += energy
            price = day.price_down_eur_per_mwh[index]
            if price is not None:
                charge_value += price * energy
        elif fleet > 0:
            periods_discharging += 1
            discharge_energy += energy
            price = day.price_up_eur_per_mwh[index]
            if price is not None:
                discharge_value += price * energy

    return {
        "units": len(day.storage_units_mw),
        "periods_charging": periods_charging,
        "periods_discharging": periods_discharging,
        "charged_mwh": round(charge_energy, 1),
        "discharged_mwh": round(discharge_energy, 1),
        "average_charge_price_eur_per_mwh": round(charge_value / charge_energy, 2) if charge_energy else None,
        "average_discharge_price_eur_per_mwh": (
            round(discharge_value / discharge_energy, 2) if discharge_energy else None
        ),
        "round_trip_spread_eur_per_mwh": (
            round(discharge_value / discharge_energy - charge_value / charge_energy, 2)
            if charge_energy and discharge_energy
            else None
        ),
    }


def reserve_requirement_summary(day: IspDay) -> dict:
    """The average MW the operator requires of each reserve product -- the size
    of the market a new battery would be bidding into."""
    summary: dict[str, dict] = {}
    for product, values in day.reserve_requirement_mw.items():
        present = [value for value in values if value is not None]
        if not present or max(present) <= 0:
            continue
        summary[product] = {
            "mean_mw": round(sum(present) / len(present), 1),
            "max_mw": round(max(present), 1),
            "min_mw": round(min(present), 1),
        }
    return summary


# ---------------------------------------------------------------------------
# A trailing year of settled balancing prices
# ---------------------------------------------------------------------------
#
# The point of assembling a year is that it lets a battery be simulated hour by
# hour against the prices it would actually have been settled at, rather than
# against a day-ahead series with a balancing "uplift" multiplied on top. The
# weekly settlement files go back far enough to build one, and each is a
# hundred-odd kilobytes, so the whole year is a cheap one-off fetch that then
# lives on disk.
#
# It is a TRAILING year, not a calendar year: settlement lags by a week or two
# and IPTO's listing window does not reach back far enough for a complete
# calendar year anyway. Trailing twelve months is also what a commercial
# question actually asks -- what would this asset have earned in the market as
# it has recently been.

TRAILING_YEAR_DAYS = 365
YEAR_LOOKBACK_DAYS = 400
CACHE_DIRNAME = "balancing"
# Bumped whenever the assembled series changes shape or meaning, so a cached
# year from older logic is never silently reused. Keyed into the file name
# because the settled date alone would not distinguish them.
CACHE_VERSION = 2

# A year means a year. The weekly files do not align to the window edge, so
# assembly deliberately over-collects and the series is then trimmed to its
# last 8,760 hours. Leaving the overshoot in would inflate every annual total
# computed from it by however many extra days happened to come back.
HOURS_PER_YEAR = 8760


@dataclass(frozen=True)
class BalancingYear:
    """A trailing twelve months of settled balancing prices, hour by hour."""

    from_utc: str
    to_utc: str
    imbalance_price_eur_per_mwh: list[float]
    mfrr_up_eur_per_mwh: list[float]
    mfrr_down_eur_per_mwh: list[float]
    system_short_share: list[float]
    intra_hour_spread_eur_per_mwh: list[float]
    missing_hours: int
    files_used: int
    source: str = SOURCE

    @property
    def hours(self) -> int:
        return len(self.imbalance_price_eur_per_mwh)

    @property
    def mean_eur_per_mwh(self) -> float:
        prices = self.imbalance_price_eur_per_mwh
        return sum(prices) / len(prices) if prices else 0.0

    @property
    def negative_hours(self) -> int:
        return sum(1 for price in self.imbalance_price_eur_per_mwh if price < 0)

    @property
    def mean_intra_hour_spread_eur_per_mwh(self) -> float:
        """How much price variation hourly averaging discards.

        A battery trades within the hour as well as across the day, so this is
        revenue the hourly simulation cannot see. Reporting it is the
        difference between a conservative number and an unexplained one."""
        spreads = self.intra_hour_spread_eur_per_mwh
        return sum(spreads) / len(spreads) if spreads else 0.0


def cache_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "generated" / CACHE_DIRNAME


def latest_settled_date(*, lookback_days: int = YEAR_LOOKBACK_DAYS) -> date | None:
    """The market date of the most recently published settlement file."""
    try:
        files = ipto.list_files(ipto.CATEGORY_IMBALANCE, lookback_days)
    except ipto.IptoUnavailable:
        return None
    dates = [published.file_date for published in files if published.file_date]
    return max(dates) if dates else None


def _newest_revisions(files: list[ipto.PublishedFile]) -> list[ipto.PublishedFile]:
    """One file per market date: the highest run number.

    IPTO re-publishes a settlement week when figures are revised, as
    `..._02.xlsx` beside `..._01.xlsx`. The revision supersedes the original,
    so taking the greater name per date takes the corrected one."""
    best: dict[date, ipto.PublishedFile] = {}
    for published in files:
        stamp = published.file_date
        if stamp is None:
            continue
        current = best.get(stamp)
        if current is None or published.name > current.name:
            best[stamp] = published
    return [best[key] for key in sorted(best)]


def get_balancing_year(*, refresh: bool = False, lookback_days: int = YEAR_LOOKBACK_DAYS) -> BalancingYear | None:
    """A trailing year of hourly settled balancing prices, cached on disk.

    Returns None when IPTO is unreachable and nothing is cached. A caller must
    then value storage on day-ahead alone and say so, rather than guess at a
    balancing spread."""
    end = latest_settled_date(lookback_days=lookback_days)
    cache_name = f"balancing_year_v{CACHE_VERSION}_{end.isoformat()}.json" if end else None

    if not refresh and cache_name:
        cached = _read_cache(cache_name)
        if cached:
            return BalancingYear(**cached)
    if not refresh and end is None:
        # Offline: any cached year is better than nothing, and its own window
        # tells the caller how old it is.
        newest = _newest_cached()
        if newest:
            return newest
        return None

    year = _assemble_balancing_year(end, lookback_days=lookback_days)
    if year is None:
        return None
    if cache_name:
        _write_cache(cache_name, year)
    return year


def _assemble_balancing_year(end: date | None, *, lookback_days: int) -> BalancingYear | None:
    try:
        files = ipto.list_files(ipto.CATEGORY_IMBALANCE, lookback_days)
    except ipto.IptoUnavailable:
        return None

    last = end or date.today()
    first = last - timedelta(days=TRAILING_YEAR_DAYS)
    wanted = [
        published
        for published in _newest_revisions(files)
        # A weekly file named for its first day can reach up to seven days past
        # it, so a file starting just before the window still contributes.
        if published.file_date is not None and first - timedelta(days=7) <= published.file_date <= last
    ]
    if not wanted:
        return None

    periods: list[ImbalancePeriod] = []
    used = 0
    for published in wanted:
        try:
            rows = ipto.read_rows(ipto.download(published))
        except ipto.IptoUnavailable:
            continue
        parsed = parse_imbalance_rows(rows)
        if parsed:
            used += 1
            periods.extend(parsed)

    if not periods:
        return None
    return _into_hours(periods, used)


def _into_hours(periods: list[ImbalancePeriod], files_used: int) -> BalancingYear | None:
    """Quarter-hours into UTC hours.

    Averaging within the hour is the right aggregation for revenue and keeps
    the series aligned with the day-ahead and weather years, which are hourly.
    What it costs is the within-hour spread, so that is measured and carried
    rather than silently dropped. Duplicate periods -- a revised week
    overlapping an original -- are collapsed by instant first, latest wins."""
    by_instant: dict[str, ImbalancePeriod] = {}
    for period in periods:
        by_instant[period.start_utc] = period
    ordered = [by_instant[key] for key in sorted(by_instant)]
    if not ordered:
        return None

    first = datetime.fromisoformat(ordered[0].start_utc).replace(minute=0, second=0, microsecond=0)
    last = datetime.fromisoformat(ordered[-1].start_utc).replace(minute=0, second=0, microsecond=0)
    total_hours = int((last - first).total_seconds() // 3600) + 1
    if total_hours <= 0:
        return None

    buckets: dict[int, list[ImbalancePeriod]] = {}
    for period in ordered:
        moment = datetime.fromisoformat(period.start_utc)
        index = int((moment - first).total_seconds() // 3600)
        if 0 <= index < total_hours:
            buckets.setdefault(index, []).append(period)

    imbalance: list[float] = []
    up: list[float] = []
    down: list[float] = []
    short_share: list[float] = []
    spread: list[float] = []
    missing = 0
    carried: tuple[float, float, float] | None = None

    for index in range(total_hours):
        members = buckets.get(index)
        if not members:
            missing += 1
            # Carry the previous hour forward. A zero would read as a free
            # hour and a battery would charge into it.
            values = carried or (0.0, 0.0, 0.0)
            imbalance.append(round(values[0], 2))
            up.append(round(values[1], 2))
            down.append(round(values[2], 2))
            short_share.append(0.0)
            spread.append(0.0)
            continue

        prices = [member.imbalance_price_eur_per_mwh for member in members]
        ups = [m.mfrr_up_eur_per_mwh for m in members if m.mfrr_up_eur_per_mwh is not None]
        downs = [m.mfrr_down_eur_per_mwh for m in members if m.mfrr_down_eur_per_mwh is not None]
        shorts = [m.system_short for m in members if m.system_short is not None]

        mean_price = sum(prices) / len(prices)
        mean_up = sum(ups) / len(ups) if ups else mean_price
        mean_down = sum(downs) / len(downs) if downs else mean_price
        carried = (mean_price, mean_up, mean_down)

        imbalance.append(round(mean_price, 2))
        up.append(round(mean_up, 2))
        down.append(round(mean_down, 2))
        short_share.append(round(sum(1 for value in shorts if value) / len(shorts), 3) if shorts else 0.0)
        spread.append(round(max(prices) - min(prices), 2))

    # Trim to the most recent 8,760 hours, counting the missing hours dropped
    # with them so the reported figure describes the series returned.
    overshoot = max(0, total_hours - HOURS_PER_YEAR)
    if overshoot:
        dropped_missing = sum(1 for index in range(overshoot) if index not in buckets)
        missing -= dropped_missing
        first = first + timedelta(hours=overshoot)
        imbalance = imbalance[overshoot:]
        up = up[overshoot:]
        down = down[overshoot:]
        short_share = short_share[overshoot:]
        spread = spread[overshoot:]

    return BalancingYear(
        from_utc=first.isoformat(),
        to_utc=(last + timedelta(hours=1)).isoformat(),
        imbalance_price_eur_per_mwh=imbalance,
        mfrr_up_eur_per_mwh=up,
        mfrr_down_eur_per_mwh=down,
        system_short_share=short_share,
        intra_hour_spread_eur_per_mwh=spread,
        missing_hours=missing,
        files_used=files_used,
    )


def _read_cache(name: str) -> dict | None:
    path = cache_dir() / name
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_cache(name: str, year: BalancingYear) -> None:
    try:
        directory = cache_dir()
        directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "from_utc": year.from_utc,
            "to_utc": year.to_utc,
            "imbalance_price_eur_per_mwh": year.imbalance_price_eur_per_mwh,
            "mfrr_up_eur_per_mwh": year.mfrr_up_eur_per_mwh,
            "mfrr_down_eur_per_mwh": year.mfrr_down_eur_per_mwh,
            "system_short_share": year.system_short_share,
            "intra_hour_spread_eur_per_mwh": year.intra_hour_spread_eur_per_mwh,
            "missing_hours": year.missing_hours,
            "files_used": year.files_used,
            "source": year.source,
        }
        (directory / name).write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    except OSError:
        pass  # A read-only data directory must not fail the fetch.


def _newest_cached() -> BalancingYear | None:
    try:
        candidates = sorted(cache_dir().glob(f"balancing_year_v{CACHE_VERSION}_*.json"))
    except OSError:
        return None
    for path in reversed(candidates):
        payload = _read_cache(path.name)
        if payload:
            try:
                return BalancingYear(**payload)
            except TypeError:
                continue
    return None


def balancing_year_statistics(year: BalancingYear) -> dict:
    prices = year.imbalance_price_eur_per_mwh
    if not prices:
        return {}
    ordered = sorted(prices)
    return {
        "from_utc": year.from_utc,
        "to_utc": year.to_utc,
        "hours": year.hours,
        "missing_hours": year.missing_hours,
        "files_used": year.files_used,
        "mean_eur_per_mwh": round(year.mean_eur_per_mwh, 2),
        "median_eur_per_mwh": round(median(prices), 2),
        "p10_eur_per_mwh": round(_percentile(ordered, 10), 2),
        "p90_eur_per_mwh": round(_percentile(ordered, 90), 2),
        "min_eur_per_mwh": round(ordered[0], 2),
        "max_eur_per_mwh": round(ordered[-1], 2),
        "negative_hours": year.negative_hours,
        "mean_intra_hour_spread_eur_per_mwh": round(year.mean_intra_hour_spread_eur_per_mwh, 2),
        "source": year.source,
    }
