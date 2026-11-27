"""The live market view: what the Greek system is doing, and what it pays.

This assembles one response from the feed registry (app/market_feeds.py) so a
client makes a single call and gets the whole market picture with every
number's source and freshness attached, rather than stitching four endpoints
together and guessing which of them went cold.

The finding it is built around
------------------------------
Day-ahead and balancing are not two views of one price. Over the trailing year
measured here, day-ahead ran about 115 hours below zero and settled balancing
over 1,400 -- more than twelve times as many hours in which a battery is paid
to charge rather than paying to. The mean prices differ, the spreads differ by
roughly a factor of two, and in Greece it is the balancing market that
physically dispatches storage. So the comparison is not a footnote on this
response, it is the point of it: a storage business case built on day-ahead
alone is priced in a market the asset does not operate in.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import balancing, hourly_series, market_feeds
from .market_api import (
    BalancingDayOut,
    BalancingYearSummaryOut,
    DayAheadComparisonOut,
    FeedStateOut,
    ImbalanceStatisticsOut,
    LiveMarketResponse,
    MfrrStatisticsOut,
    PricingAttributionOut,
    ReserveRequirementOut,
    StorageFleetBehaviourOut,
)

# The day-ahead year the balancing window is compared against. The trailing
# balancing window straddles two calendar years, so there is no single "same"
# day-ahead year; the most recent complete one is used and the response says
# which, rather than implying the windows align exactly.
COMPARISON_DAY_AHEAD_YEAR = 2025


def build_live_market() -> LiveMarketResponse:
    feeds = market_feeds.all_states()
    week = market_feeds.payload("imbalance_settlement")
    day = market_feeds.payload("isp_schedule")
    year = market_feeds.payload("balancing_year")

    response = LiveMarketResponse(
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        feeds=[FeedStateOut(**vars(state)) for state in feeds],
    )

    if week is not None:
        statistics = balancing.imbalance_statistics(week)
        if statistics:
            response.imbalance = ImbalanceStatisticsOut(**statistics)
        mfrr = balancing.mfrr_statistics(week)
        if mfrr:
            response.mfrr = MfrrStatisticsOut(**mfrr)
        attribution = balancing.pricing_attribution(week)
        if attribution:
            response.pricing_attribution = PricingAttributionOut(**attribution)
        response.settlement_file = week.file_name

    if day is not None:
        response.day = _day_out(day)

    if year is not None:
        summary = balancing.balancing_year_statistics(year)
        if summary:
            response.trailing_year = BalancingYearSummaryOut(**summary)
        response.comparison = _comparison(year)

    response.notes = _notes(response, week, day, year)
    return response


def _day_out(day: balancing.IspDay) -> BalancingDayOut:
    ups = [value for value in day.price_up_eur_per_mwh if value is not None]
    downs = [value for value in day.price_down_eur_per_mwh if value is not None]
    fleet = balancing.storage_fleet_behaviour(day)
    last = day.timestamps_utc[-1] if day.timestamps_utc else ""

    return BalancingDayOut(
        file_name=day.file_name,
        periods=day.periods,
        from_utc=day.timestamps_utc[0] if day.timestamps_utc else "",
        to_utc=last,
        timestamps_utc=day.timestamps_utc,
        price_up_eur_per_mwh=day.price_up_eur_per_mwh,
        price_down_eur_per_mwh=day.price_down_eur_per_mwh,
        system_load_mw=day.system_load_mw,
        renewables_mw=day.renewables_mw,
        storage_mw=day.storage_mw,
        mean_price_up_eur_per_mwh=round(sum(ups) / len(ups), 2) if ups else None,
        mean_price_down_eur_per_mwh=round(sum(downs) / len(downs), 2) if downs else None,
        reserve_requirements=[
            ReserveRequirementOut(product=product, **values)
            for product, values in balancing.reserve_requirement_summary(day).items()
        ],
        storage_fleet=StorageFleetBehaviourOut(**fleet) if fleet else None,
    )


def _comparison(year: balancing.BalancingYear) -> DayAheadComparisonOut:
    """Balancing against day-ahead. Day-ahead comes from the cached price year
    only -- this must not trigger a fetch of a whole year of prices on a market
    dashboard request, so an absent cache simply leaves those fields empty."""
    comparison = DayAheadComparisonOut(
        balancing_mean_eur_per_mwh=round(year.mean_eur_per_mwh, 2),
        balancing_negative_hours=year.negative_hours,
    )

    day_ahead = hourly_series.get_price_year(COMPARISON_DAY_AHEAD_YEAR)
    if day_ahead is None or not day_ahead.prices_eur_per_mwh:
        return comparison

    comparison.day_ahead_year = day_ahead.year
    comparison.day_ahead_mean_eur_per_mwh = round(day_ahead.mean_eur_per_mwh, 2)
    comparison.day_ahead_negative_hours = day_ahead.negative_hours
    comparison.mean_premium_eur_per_mwh = round(year.mean_eur_per_mwh - day_ahead.mean_eur_per_mwh, 2)
    if day_ahead.negative_hours:
        comparison.negative_hour_ratio = round(year.negative_hours / day_ahead.negative_hours, 1)
    return comparison


def _notes(
    response: LiveMarketResponse,
    week: balancing.ImbalanceWeek | None,
    day: balancing.IspDay | None,
    year: balancing.BalancingYear | None,
) -> list[str]:
    notes: list[str] = []

    cold = [state.label for state in response.feeds if state.status == market_feeds.STATUS_UNAVAILABLE]
    if cold:
        notes.append(f"Not reachable right now: {', '.join(cold)}. Other figures are unaffected.")

    if response.mfrr and response.imbalance:
        notes.append(
            f"The system paid {response.imbalance.mean_price_when_short_eur_per_mwh} EUR/MWh on average "
            f"when it was short of energy and {response.imbalance.mean_price_when_long_eur_per_mwh} when "
            f"it was long -- a {response.imbalance.short_long_spread_eur_per_mwh} EUR/MWh spread for an "
            "asset that can move energy between the two."
        )

    if response.pricing_attribution:
        attribution = response.pricing_attribution
        notes.append(
            f"Settlement took the mFRR up price in {attribution.set_by_mfrr_up_pct}% of periods and the "
            f"down price in {attribution.set_by_mfrr_down_pct}%; the remaining "
            f"{attribution.set_by_neither_pct}% priced off neither, so something else in the merit "
            "order was marginal -- most likely aFRR, whose clearing price these files do not publish. "
            "Measured from this week's settlement, not assumed from the rulebook."
        )

    fleet = response.day.storage_fleet if response.day else None
    if fleet and fleet.round_trip_spread_eur_per_mwh is not None:
        notes.append(
            f"Greece's {fleet.units} scheduled storage units charged around "
            f"{fleet.average_charge_price_eur_per_mwh} EUR/MWh and discharged around "
            f"{fleet.average_discharge_price_eur_per_mwh}, a {fleet.round_trip_spread_eur_per_mwh} "
            "EUR/MWh round-trip spread on the day."
        )

    if year is not None:
        notes.append(
            f"The trailing year of settled prices had {year.negative_hours} hours below zero and a mean "
            f"within-hour spread of {round(year.mean_intra_hour_spread_eur_per_mwh, 2)} EUR/MWh. The "
            "hourly simulation averages the quarter-hours, so that spread is revenue it cannot see."
        )

    if response.comparison and response.comparison.negative_hour_ratio:
        notes.append(
            f"Settled balancing had {response.comparison.negative_hour_ratio}x as many negative hours as "
            f"day-ahead {response.comparison.day_ahead_year}. A battery is paid to charge in all of them."
        )

    if week is not None and day is None:
        notes.append("The operator's intraday schedule is unavailable, so today's grid view is missing.")

    return notes
