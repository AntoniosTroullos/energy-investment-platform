"""One asset, 8,760 hours at a time, for its whole life.

The platform values candidate sites from annual averages: a capacity factor, a
capture price, a degradation rate applied year by year. That is the right
resolution for screening thousands of cells. It is the wrong resolution for the
question an investor asks once a site is shortlisted -- what does THIS asset,
at THIS location, earn against the hours the market actually had?

This module answers that one. Real weather for the site, real prices for the
year, hour by hour, then the same sequence replayed for every year of the
asset's life with degradation compounding through it.

What hourly resolution changes
------------------------------
**Negative prices.** Greece had 115 hours below zero in 2025 and 323 at or
below zero. A merchant generator does not produce into them -- it would be
paying to run -- so those hours are curtailed, and the hours lost are the sunny
midday ones a solar plant most wants. An annual average cannot see this at all;
it values those hours at the average price, as if they were ordinary.

**Capture, measured not assumed.** The capture price falls out of the
simulation rather than being supplied to it: sum of output times price, over
sum of output, across 8,760 real pairs.

**Degradation against a moving price.** Output fades uniformly across hours, so
degradation alone leaves the capture price unchanged and scales revenue with
volume -- the simulation confirms this rather than assuming it. What makes
later years differ is everything else moving around the fade: escalation, and
for storage a shrinking usable capacity that changes which spreads are worth
taking at all.

Assumptions worth knowing
-------------------------
The asset is a price taker: it earns the market price without moving it. True
for one plant, less true for a large battery in a thin market, and the reason
the storage figures here are an upper bound on what a fleet of them would earn.

Prices repeat each year with an escalation applied. Nobody has next decade's
hours; the shape of a real year is a far better stand-in than a flat average,
and it keeps the hour-by-hour structure that the whole model turns on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .balancing import BalancingYear
from .hourly_series import PriceYear, WeatherYear, get_price_year, get_weather_year
from .investment_analysis import irr, payback_period_years
from .site_yield import (
    NO_OVERSIZING,
    solar_capex_multiplier,
    solar_dc_per_unit_of_ac,
    wind_output_per_unit,
)
from .storage_physics import BatterySpec, StorageYearResult, simulate_storage_lifetime

HOURS_PER_YEAR = 8760

# Output degradation, same rates the screening model uses (NREL / LBNL /
# Staffell & Green, via pypsa-greece's investment module).
DEGRADATION_PCT_PER_YEAR = {"solar": 0.5, "wind": 1.0}

# Which market an asset is settled against. Day-ahead is the right basis for a
# merchant generator and the wrong one for a battery: see
# `balancing_price_series` below.
SETTLEMENT_DAY_AHEAD = "day_ahead"
SETTLEMENT_BALANCING = "balancing"


def balancing_price_series(year: BalancingYear) -> PriceYear:
    """A trailing year of settled balancing prices, as a series the simulation
    can be run against directly.

    Why a battery needs this
    ------------------------
    In Greece the balancing market, not day-ahead, does the physical dispatch,
    and it is where a battery's energy is actually priced. The two series are
    not close: over the trailing year measured here, day-ahead had 115 hours
    below zero and settled balancing had over 1,400, and the balancing spread
    runs at roughly twice the day-ahead spread. Valuing storage on day-ahead
    alone is not conservative, it is wrong -- it prices the asset in a market
    it does not operate in.

    Returning a `PriceYear` rather than a new type is deliberate: the whole
    hour-by-hour engine -- state of charge, the cycle cap, wear, degradation --
    is indifferent to where the prices came from, and should stay that way.
    What changes is only the series and how it is labelled.

    Averaging the settled quarter-hours into hours is conservative for storage:
    it discards the within-hour spread, which a real battery can trade. The
    size of what is discarded travels with the series
    (`mean_intra_hour_spread_eur_per_mwh`) rather than going unmentioned."""
    end = datetime.fromisoformat(year.to_utc)
    window = f"{year.from_utc[:10]} to {year.to_utc[:10]}"
    return PriceYear(
        year=end.year,
        source=f"{year.source} -- settled imbalance price (IMBABE), {year.files_used} weekly files",
        redistribution_allowed=True,
        prices_eur_per_mwh=year.imbalance_price_eur_per_mwh,
        missing_hours=year.missing_hours,
        start_utc=year.from_utc,
        label=f"settled balancing, {window}",
    )


@dataclass
class SimulatedYear:
    year_index: int
    generation_mwh: float
    curtailed_mwh: float
    revenue_eur: float
    capture_price_eur_per_mwh: float | None
    capacity_factor_pct: float
    hours_producing: int
    hours_curtailed: int
    output_retention_pct: float
    # Solar with an oversized array: energy the inverter could not pass. Zero
    # for wind and for a plant built at DC/AC 1.0.
    clipped_mwh: float = 0.0
    hours_clipped: int = 0


@dataclass
class AssetSimulation:
    """A full-life, hour-by-hour simulation of one asset."""

    kind: str
    carrier: str
    capacity_mw: float
    price_year: int
    price_source: str
    lifetime_years: int

    # Which market the asset was settled against, and over what window -- the
    # same battery is worth very different amounts in day-ahead and balancing,
    # so a result that does not say which is not interpretable.
    settlement: str = SETTLEMENT_DAY_AHEAD
    price_window: str = ""

    years: list[SimulatedYear] = field(default_factory=list)
    storage_years: list[StorageYearResult] = field(default_factory=list)

    # Lifetime economics
    capex_eur: float | None = None
    npv_eur: float | None = None
    irr_pct: float | None = None
    payback_years: float | None = None
    lifetime_revenue_eur: float = 0.0

    # First-year hourly traces for charting.
    first_year_output_mw: list[float] = field(default_factory=list)
    first_year_price_eur_per_mwh: list[float] = field(default_factory=list)
    first_year_soc_mwh: list[float] = field(default_factory=list)

    notes: list[str] = field(default_factory=list)


def _annual_cash_flows(
    capex_eur: float,
    net_revenues: list[float],
    fixed_opex_eur: float,
) -> list[float]:
    return [-capex_eur] + [revenue - fixed_opex_eur for revenue in net_revenues]


def _discounted(cash_flows: list[float], discount_rate_pct: float) -> float:
    rate = discount_rate_pct / 100.0
    return sum(flow / ((1 + rate) ** period) for period, flow in enumerate(cash_flows))


# ---------------------------------------------------------------------------
# Generation assets
# ---------------------------------------------------------------------------


def simulate_generation_asset(
    *,
    latitude: float,
    longitude: float,
    carrier: str,
    capacity_mw: float,
    price_year: PriceYear,
    weather: WeatherYear,
    lifetime_years: int = 25,
    capex_eur_per_kw: float | None = None,
    fixed_opex_pct_of_capex: float = 2.0,
    discount_rate_pct: float = 7.0,
    marginal_cost_eur_per_mwh: float = 0.0,
    price_escalation_pct_per_year: float = 0.0,
    curtail_at_negative_prices: bool = True,
    dc_ac_ratio: float = NO_OVERSIZING,
    keep_traces: bool = True,
) -> AssetSimulation:
    """Hour by hour for a solar or wind plant, year by year to end of life.

    `capacity_mw` is the AC rating throughout -- what the plant is permitted,
    connected and settled on. For solar, `dc_ac_ratio` sets how much larger
    the DC array behind it is."""
    # Held unclipped so degradation can act on the DC side, which is where it
    # physically happens, with the inverter limit applied after. Clipping first
    # and fading the result would understate later years: a degraded oversized
    # array still reaches the limit at midday, so part of the fade is absorbed
    # by clipping that no longer happens.
    # Every solar plant has an inverter limit, oversized or not: a 1:1 inverter
    # still cannot pass more than its rating, and cold bright hours push DC
    # above nameplate on their own. Gating this on dc_ac_ratio > 1.0 would have
    # quietly removed the clip that the previous model always applied.
    clips_at_inverter = carrier == "solar"
    if carrier == "solar":
        per_unit = solar_dc_per_unit_of_ac(
            weather.plane_of_array_w_m2, weather.temperature_c, dc_ac_ratio
        )
    elif carrier == "wind":
        per_unit = wind_output_per_unit(
            weather.wind_speed_100m_kmh, weather.temperature_c, weather.surface_pressure_hpa
        )
    else:
        raise ValueError(f"simulate_generation_asset does not model '{carrier}'")

    prices = price_year.prices_eur_per_mwh
    hours = min(len(per_unit), len(prices))
    degradation = DEGRADATION_PCT_PER_YEAR.get(carrier, 0.0) / 100.0

    simulation = AssetSimulation(
        kind="generation",
        carrier=carrier,
        capacity_mw=capacity_mw,
        price_year=price_year.year,
        price_source=price_year.source,
        lifetime_years=lifetime_years,
    )

    net_revenues: list[float] = []
    for year_index in range(lifetime_years):
        retention = (1 - degradation) ** year_index
        escalation = (1 + price_escalation_pct_per_year / 100.0) ** year_index

        generation = 0.0
        curtailed = 0.0
        clipped = 0.0
        revenue = 0.0
        producing = 0
        curtailed_hours = 0
        clipped_hours = 0

        for hour in range(hours):
            faded = per_unit[hour] * retention
            if clips_at_inverter and faded > 1.0:
                clipped += capacity_mw * (faded - 1.0)
                clipped_hours += 1
                faded = 1.0
            available_mw = capacity_mw * faded
            if available_mw <= 0:
                continue
            price = prices[hour] * escalation

            if curtail_at_negative_prices and price < 0:
                # Running would mean paying the market to take the power.
                curtailed += available_mw
                curtailed_hours += 1
                continue

            generation += available_mw
            revenue += available_mw * (price - marginal_cost_eur_per_mwh)
            producing += 1

        capture = revenue / generation if generation > 0 else None
        simulation.years.append(
            SimulatedYear(
                year_index=year_index,
                generation_mwh=round(generation, 1),
                curtailed_mwh=round(curtailed, 1),
                revenue_eur=round(revenue, 2),
                capture_price_eur_per_mwh=round(capture, 2) if capture is not None else None,
                capacity_factor_pct=round(100.0 * generation / (capacity_mw * hours), 2)
                if capacity_mw > 0
                else 0.0,
                hours_producing=producing,
                hours_curtailed=curtailed_hours,
                output_retention_pct=round(100.0 * retention, 2),
                clipped_mwh=round(clipped, 1),
                hours_clipped=clipped_hours,
            )
        )
        net_revenues.append(revenue)

        if keep_traces and year_index == 0:
            # Clipped, like the energy figures above it. `per_unit` is the
            # unclipped DC series, so charting it raw would draw a 100 MW plant
            # exporting 150 MW.
            simulation.first_year_output_mw = [
                round(capacity_mw * min(per_unit[hour] * retention, 1.0), 3) for hour in range(hours)
            ]
            simulation.first_year_price_eur_per_mwh = [round(prices[hour], 2) for hour in range(hours)]

    simulation.lifetime_revenue_eur = round(sum(net_revenues), 2)
    _attach_economics(
        simulation,
        net_revenues,
        # Per kW of AC capacity, scaled for the larger DC array where there is
        # one. Without that scaling, raising the DC/AC ratio would lift output
        # and IRR at no cost -- a free lunch the real world does not offer.
        capex_eur=(
            capacity_mw * 1000.0 * capex_eur_per_kw * solar_capex_multiplier(dc_ac_ratio)
            if capex_eur_per_kw and carrier == "solar"
            else capacity_mw * 1000.0 * capex_eur_per_kw
            if capex_eur_per_kw
            else None
        ),
        fixed_opex_pct_of_capex=fixed_opex_pct_of_capex,
        discount_rate_pct=discount_rate_pct,
    )

    first = simulation.years[0] if simulation.years else None
    last = simulation.years[-1] if simulation.years else None
    if first and first.hours_curtailed:
        simulation.notes.append(
            f"{first.hours_curtailed} hours curtailed in year 1 because the price was below zero "
            f"({round(first.curtailed_mwh):,} MWh of available output not produced). An annual-average "
            "model values those hours at the average price instead."
        )

    if carrier == "solar" and dc_ac_ratio != NO_OVERSIZING:
        simulation.notes.append(
            f"DC array {dc_ac_ratio:.2f}x the {capacity_mw:g} MW AC rating, at "
            f"{solar_capex_multiplier(dc_ac_ratio):.2f}x the capex per kW AC."
        )
        if first and first.hours_clipped:
            lost_pct = 100.0 * first.clipped_mwh / (first.generation_mwh + first.clipped_mwh)
            simulation.notes.append(
                f"The inverter clipped {round(first.clipped_mwh):,} MWh in year 1 over "
                f"{first.hours_clipped} hours -- {lost_pct:.1f}% of what the array could have made. "
                "That is the cost of oversizing, against a larger harvest in every other hour."
            )
        elif first:
            simulation.notes.append(
                "Nothing clipped: Greek midday cell temperatures hold DC output below the inverter "
                "limit even oversized, so at this ratio the extra array is close to free."
            )
        if first and last and first.hours_clipped:
            # Fade hits the DC side, so early clipping absorbs part of it and
            # the plant holds its AC output better than the module warranty
            # alone suggests. Only worth saying when it actually happened.
            ac_retention = 100.0 * last.generation_mwh / first.generation_mwh if first.generation_mwh else 0.0
            simulation.notes.append(
                f"AC output holds at {ac_retention:.1f}% of year 1 by year {lifetime_years}, against "
                f"{last.output_retention_pct:.1f}% of DC nameplate -- early clipping absorbs part of the "
                "fade, so an oversized plant degrades more slowly in the terms that get paid."
            )
    return simulation


# ---------------------------------------------------------------------------
# Storage assets
# ---------------------------------------------------------------------------


def simulate_storage_asset(
    *,
    spec: BatterySpec,
    price_year: PriceYear,
    lifetime_years: int = 15,
    capex_eur_per_kwh: float | None = None,
    fixed_opex_pct_of_capex: float = 2.0,
    discount_rate_pct: float = 8.0,
    price_escalation_pct_per_year: float = 0.0,
    settlement: str = SETTLEMENT_DAY_AHEAD,
    keep_traces: bool = True,
) -> AssetSimulation:
    """Hour by hour for a battery, year by year, with degradation carried.

    `settlement` only labels which market `price_year` came from; pass the
    matching series (see `balancing_price_series`). The physics does not care,
    and the result has to say, because the answer differs by more than any
    parameter in the spec."""
    years = simulate_storage_lifetime(
        price_year.prices_eur_per_mwh,
        spec,
        lifetime_years,
        price_escalation_pct_per_year=price_escalation_pct_per_year,
        keep_first_year_traces=keep_traces,
    )

    simulation = AssetSimulation(
        kind="storage",
        carrier="battery",
        capacity_mw=spec.power_mw,
        price_year=price_year.year,
        price_source=price_year.source,
        lifetime_years=lifetime_years,
        settlement=settlement,
        price_window=price_year.window_label,
        storage_years=years,
    )

    net_revenues = [year.gross_margin_eur for year in years]
    simulation.lifetime_revenue_eur = round(sum(net_revenues), 2)
    _attach_economics(
        simulation,
        net_revenues,
        capex_eur=spec.energy_capacity_mwh * 1000.0 * capex_eur_per_kwh if capex_eur_per_kwh else None,
        fixed_opex_pct_of_capex=fixed_opex_pct_of_capex,
        discount_rate_pct=discount_rate_pct,
    )

    if keep_traces and years and years[0].soc_mwh:
        simulation.first_year_soc_mwh = years[0].soc_mwh
        simulation.first_year_output_mw = years[0].net_grid_mw
        simulation.first_year_price_eur_per_mwh = [
            round(price, 2) for price in price_year.prices_eur_per_mwh[: len(years[0].net_grid_mw)]
        ]

    first, last = (years[0], years[-1]) if years else (None, None)
    if first and last:
        simulation.notes.append(
            f"Capacity retention falls from {first.capacity_retention_pct}% to "
            f"{last.capacity_retention_pct}% of nameplate over {lifetime_years} years at "
            f"{first.equivalent_full_cycles:.0f} equivalent full cycles a year."
        )
        if first.negative_price_hours_charged:
            simulation.notes.append(
                f"Charged in {first.negative_price_hours_charged} hours of negative prices in year 1 -- "
                "paid to take energy off the system."
            )

    if settlement == SETTLEMENT_BALANCING:
        # These three qualifications belong next to the number, not in a
        # methodology appendix: the balancing result is roughly twice the
        # day-ahead one, and each of them bears on whether it is reachable.
        simulation.notes.extend(
            [
                "Settled against IPTO's balancing prices, which is the market that physically "
                "dispatches storage in Greece -- not day-ahead.",
                "A price taker: the spread is taken as given. It is the spread the FIRST battery of "
                "this size sees. Greek storage capacity is growing quickly, and a fleet bidding the "
                "same hours compresses the spread it is bidding for.",
                "Reaching these prices requires a qualified balancing service unit dispatched by the "
                "operator. Day-ahead can simply be traded; this cannot.",
            ]
        )
    return simulation


def _attach_economics(
    simulation: AssetSimulation,
    net_revenues: list[float],
    *,
    capex_eur: float | None,
    fixed_opex_pct_of_capex: float,
    discount_rate_pct: float,
) -> None:
    if capex_eur is None or capex_eur <= 0:
        return
    fixed_opex = capex_eur * fixed_opex_pct_of_capex / 100.0
    flows = _annual_cash_flows(capex_eur, net_revenues, fixed_opex)

    simulation.capex_eur = round(capex_eur, 0)
    simulation.npv_eur = round(_discounted(flows, discount_rate_pct), 0)
    rate = irr(flows)
    simulation.irr_pct = round(rate * 100, 2) if rate is not None else None
    payback = payback_period_years(flows)
    simulation.payback_years = round(payback, 1) if payback is not None else None


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------


def load_inputs(
    latitude: float,
    longitude: float,
    year: int,
) -> tuple[PriceYear | None, WeatherYear | None]:
    """The two series every simulation needs, both disk-cached after the first
    fetch. Returned separately so a caller can report precisely which one is
    missing rather than failing opaquely."""
    return get_price_year(year), get_weather_year(latitude, longitude, year)
