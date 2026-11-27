"""Battery storage, simulated hour by hour against real prices.

A battery is not a generator with a capacity factor. Its output in any hour is
a decision constrained by what it did in the hours before: energy it did not
store this morning is not available this evening, every round trip loses a
fixed share to heat, and every cycle consumes a little of the asset itself. A
capacity factor cannot express any of that, which is why storage needs its own
model rather than a row in the generation table.

What is modelled
----------------

**State of charge.** Carried hour to hour across the whole year, never reset at
a day boundary. A battery that empties itself into a Tuesday evening peak
starts Wednesday empty, and that is exactly the constraint that limits how much
of the market's spread it can actually capture.

**Round-trip efficiency, split.** An 88% round trip is not "lose 12% on the way
out" -- it is roughly sqrt(0.88) ~ 0.938 each way. Charging 1 MWh from the grid
puts 0.938 MWh in the cells; discharging that gives 0.88 MWh back to the grid.
The distinction matters because the loss on the way in is paid for at the
charging price and the loss on the way out is foregone at the discharge price.

**Depth of discharge.** Usable energy is the window between `min_soc_fraction`
and `max_soc_fraction`, not the nameplate. A 100 MWh battery held between 10%
and 95% has 85 MWh to trade with.

**Self-discharge.** Small, but it is the reason a battery cannot profitably sit
charged for a week waiting for a better price.

**Degradation, two kinds.** Calendar fade happens because time passes.
Cycle fade happens because energy moved through the cells, counted in
equivalent full cycles. Both shrink usable capacity year over year, and the
asset reaches end of life at a retention floor (commonly 70-80% of nameplate)
rather than at zero.

**The cost of a cycle.** The decisive piece of economics, and the one most
revenue estimates leave out. Moving energy wears the battery out, so a cycle
has a marginal cost: roughly the cell replacement cost spread over the cycles
the warranty promises. A battery that chases every 5 EUR/MWh spread earns
revenue and destroys value. The dispatch below will not take a trade whose
spread does not clear that cost.

Dispatch
--------
A per-day threshold strategy, walked hour by hour so chronology and state of
charge are always respected: charge in the cheapest hours of the day, discharge
in the dearest, where "cheapest" and "dearest" mean the price ranks a battery
of this duration can physically reach. Each discharge must clear the round-trip
loss, the grid charges on both legs, and the cycle cost.

This is deliberately a simple merchant strategy, not a perfect-foresight
optimum. Perfect foresight over a year would report a revenue no operator can
achieve, since nobody knows tomorrow's prices today. A day-ahead market does
publish the day's prices before the day starts, which is exactly the horizon
this strategy assumes -- so it is both achievable and non-trivial.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

HOURS_PER_YEAR = 8760
HOURS_PER_DAY = 24


@dataclass(frozen=True)
class BatterySpec:
    """A grid-scale battery. Defaults describe a utility-scale lithium
    iron phosphate (LFP) system, the chemistry essentially all new Greek
    storage uses: long cycle life, modest energy density, good safety."""

    power_mw: float
    energy_capacity_mwh: float

    # Round trip, AC to AC, including inverter losses. 86-90% is the current
    # range for a new LFP system; 88% is a common mid-point.
    round_trip_efficiency: float = 0.88

    # The usable window. Operators hold a floor to protect cell life and a
    # ceiling because the last few percent charge slowly.
    min_soc_fraction: float = 0.05
    max_soc_fraction: float = 0.95

    # Losses while idle, including auxiliary and thermal management load.
    self_discharge_pct_per_month: float = 2.0

    # Degradation. An LFP system warranted to 6,000 equivalent full cycles
    # with roughly 70% retention at end of life implies about 0.005% capacity
    # loss per cycle; calendar fade of about 1.5%/yr is typical of warranty
    # terms for a thermally managed system.
    cycle_fade_pct_per_equivalent_cycle: float = 0.005
    calendar_fade_pct_per_year: float = 1.5
    end_of_life_retention_pct: float = 70.0

    # What one MWh of throughput costs in wear: replacement cost of the cells
    # divided by the energy they will pass before the warranty floor. This is
    # what stops the model trading spreads that look profitable and are not.
    cycle_cost_eur_per_mwh: float = 6.0

    # Network charges and losses on each leg. Charging pays the price plus
    # these; discharging receives the price minus them.
    grid_charge_eur_per_mwh: float = 0.0

    # A hard ceiling on daily throughput, as warranties usually impose one.
    max_cycles_per_day: float = 1.5

    @property
    def usable_energy_mwh(self) -> float:
        return self.energy_capacity_mwh * (self.max_soc_fraction - self.min_soc_fraction)

    @property
    def duration_hours(self) -> float:
        return self.usable_energy_mwh / self.power_mw if self.power_mw > 0 else 0.0

    @property
    def one_way_efficiency(self) -> float:
        """Each leg carries the square root of the round trip."""
        return math.sqrt(max(0.0, min(1.0, self.round_trip_efficiency)))

    @property
    def self_discharge_per_hour(self) -> float:
        return (self.self_discharge_pct_per_month / 100.0) / (30.0 * 24.0)


@dataclass
class StorageYearResult:
    """One simulated year."""

    year_index: int
    capacity_retention_pct: float
    usable_energy_mwh: float

    energy_charged_mwh: float = 0.0
    energy_discharged_mwh: float = 0.0
    charging_cost_eur: float = 0.0
    discharge_revenue_eur: float = 0.0
    cycle_cost_eur: float = 0.0
    equivalent_full_cycles: float = 0.0

    hours_charging: int = 0
    hours_discharging: int = 0
    hours_idle: int = 0
    negative_price_hours_charged: int = 0

    final_soc_mwh: float = 0.0

    # Hourly traces, for charting one simulated year.
    soc_mwh: list[float] = field(default_factory=list)
    net_grid_mw: list[float] = field(default_factory=list)

    @property
    def gross_margin_eur(self) -> float:
        """Energy revenue less energy cost and wear. Not profit: fixed O&M,
        capex and tax live in the investment model, not here."""
        return self.discharge_revenue_eur - self.charging_cost_eur - self.cycle_cost_eur

    @property
    def round_trip_losses_mwh(self) -> float:
        return self.energy_charged_mwh - self.energy_discharged_mwh

    @property
    def average_charge_price_eur_per_mwh(self) -> float | None:
        return self.charging_cost_eur / self.energy_charged_mwh if self.energy_charged_mwh > 0 else None

    @property
    def average_discharge_price_eur_per_mwh(self) -> float | None:
        return (
            self.discharge_revenue_eur / self.energy_discharged_mwh if self.energy_discharged_mwh > 0 else None
        )


def capacity_retention_pct(
    spec: BatterySpec,
    years_elapsed: float,
    cumulative_equivalent_cycles: float,
) -> float:
    """Remaining capacity as a percentage of nameplate.

    Calendar and cycle fade are added rather than compounded -- the convention
    warranties are written in -- and the result is floored at end-of-life
    retention. Past that floor the asset is retired or augmented; this model
    does not pretend it keeps degrading gracefully to nothing."""
    fade = (
        spec.calendar_fade_pct_per_year * years_elapsed
        + spec.cycle_fade_pct_per_equivalent_cycle * cumulative_equivalent_cycles
    )
    return max(spec.end_of_life_retention_pct, 100.0 - fade)


def simulate_storage_year(
    prices_eur_per_mwh: list[float],
    spec: BatterySpec,
    *,
    year_index: int = 0,
    cumulative_equivalent_cycles: float = 0.0,
    start_soc_fraction: float | None = None,
    keep_traces: bool = False,
) -> StorageYearResult:
    """One year of hourly dispatch against a real price series."""
    retention = capacity_retention_pct(spec, year_index, cumulative_equivalent_cycles) / 100.0
    nameplate = spec.energy_capacity_mwh * retention
    usable = nameplate * (spec.max_soc_fraction - spec.min_soc_fraction)
    floor_mwh = nameplate * spec.min_soc_fraction
    ceiling_mwh = nameplate * spec.max_soc_fraction

    result = StorageYearResult(
        year_index=year_index,
        capacity_retention_pct=round(retention * 100.0, 2),
        usable_energy_mwh=round(usable, 3),
    )
    if usable <= 0 or spec.power_mw <= 0 or not prices_eur_per_mwh:
        return result

    efficiency = spec.one_way_efficiency
    soc = floor_mwh + usable * (start_soc_fraction if start_soc_fraction is not None else 0.5)
    daily_throughput_cap = spec.max_cycles_per_day * usable

    for day_start in range(0, len(prices_eur_per_mwh), HOURS_PER_DAY):
        day = prices_eur_per_mwh[day_start : day_start + HOURS_PER_DAY]
        if not day:
            continue
        charge_ceiling, discharge_floor = _day_thresholds(day, spec)
        discharged_today = 0.0

        for hour_offset, price in enumerate(day):
            # Idle losses apply every hour, whatever the battery does.
            soc -= soc * spec.self_discharge_per_hour
            soc = max(floor_mwh, soc)

            charged_mwh = 0.0
            discharged_mwh = 0.0

            if price <= charge_ceiling and soc < ceiling_mwh:
                # Grid energy drawn this hour, limited by power rating, by the
                # room left in the pack, and by the charge-side loss.
                headroom_grid_mwh = (ceiling_mwh - soc) / efficiency
                charged_mwh = min(spec.power_mw, headroom_grid_mwh)
                if charged_mwh > 0:
                    soc += charged_mwh * efficiency
                    cost = charged_mwh * (price + spec.grid_charge_eur_per_mwh)
                    result.charging_cost_eur += cost
                    result.energy_charged_mwh += charged_mwh
                    result.hours_charging += 1
                    if price < 0:
                        # Being paid to charge. Rare, and the single best hour
                        # a battery can have.
                        result.negative_price_hours_charged += 1

            elif price >= discharge_floor and soc > floor_mwh and discharged_today < daily_throughput_cap:
                available_grid_mwh = (soc - floor_mwh) * efficiency
                discharged_mwh = min(spec.power_mw, available_grid_mwh, daily_throughput_cap - discharged_today)
                net_price = price - spec.grid_charge_eur_per_mwh
                # The trade must clear its own wear cost; otherwise the right
                # move is to hold the energy.
                if discharged_mwh > 0 and net_price > spec.cycle_cost_eur_per_mwh:
                    soc -= discharged_mwh / efficiency
                    result.discharge_revenue_eur += discharged_mwh * net_price
                    result.cycle_cost_eur += discharged_mwh * spec.cycle_cost_eur_per_mwh
                    result.energy_discharged_mwh += discharged_mwh
                    result.hours_discharging += 1
                    discharged_today += discharged_mwh
                else:
                    discharged_mwh = 0.0

            if charged_mwh == 0.0 and discharged_mwh == 0.0:
                result.hours_idle += 1

            if keep_traces:
                result.soc_mwh.append(round(soc, 3))
                result.net_grid_mw.append(round(discharged_mwh - charged_mwh, 3))

    result.equivalent_full_cycles = round(result.energy_discharged_mwh / usable, 2) if usable > 0 else 0.0
    result.final_soc_mwh = round(soc, 3)
    result.energy_charged_mwh = round(result.energy_charged_mwh, 2)
    result.energy_discharged_mwh = round(result.energy_discharged_mwh, 2)
    result.charging_cost_eur = round(result.charging_cost_eur, 2)
    result.discharge_revenue_eur = round(result.discharge_revenue_eur, 2)
    result.cycle_cost_eur = round(result.cycle_cost_eur, 2)
    return result


def _day_thresholds(day_prices: list[float], spec: BatterySpec) -> tuple[float, float]:
    """The charge and discharge price thresholds for one day.

    A battery of N hours' duration can fill in about N hours and empty in about
    N, so it should buy in roughly the N cheapest hours of the day and sell in
    the N dearest. The thresholds are the prices at those ranks, with one
    economic test applied on top: the dearest hours must beat the cheapest by
    more than the round trip plus wear, or there is no trade worth making and
    the thresholds collapse so nothing fires."""
    ordered = sorted(day_prices)
    slots = max(1, min(len(day_prices) // 2, int(round(spec.duration_hours))))

    charge_ceiling = ordered[slots - 1]
    discharge_floor = ordered[-slots]

    # Delivering 1 MWh to the grid means buying 1/RTE from it: one MWh out of
    # the pack costs 1/eta to put in, and 1/eta again to get back out. So the
    # cheap hour's price -- and the network charge paid on it -- are both
    # grossed up by the round trip before being compared with the dear hour.
    round_trip = max(spec.round_trip_efficiency, 1e-9)
    delivered_cost = (charge_ceiling + spec.grid_charge_eur_per_mwh) / round_trip
    realised_revenue = discharge_floor - spec.grid_charge_eur_per_mwh
    if realised_revenue - delivered_cost <= spec.cycle_cost_eur_per_mwh:
        return float("-inf"), float("inf")
    return charge_ceiling, discharge_floor


def simulate_storage_lifetime(
    prices_eur_per_mwh: list[float],
    spec: BatterySpec,
    lifetime_years: int,
    *,
    price_escalation_pct_per_year: float = 0.0,
    keep_first_year_traces: bool = False,
) -> list[StorageYearResult]:
    """Year on year to end of life, carrying degradation forward.

    The same hourly price shape is reused for every year, scaled by any
    escalation: the shape of a year of Greek prices is a far better description
    of a future year than a flat average, and nobody has next decade's actual
    hours. What changes year to year is the battery -- less usable capacity,
    so fewer MWh through a spread that is itself moving."""
    results: list[StorageYearResult] = []
    cumulative_cycles = 0.0
    soc_fraction = 0.5

    for year_index in range(lifetime_years):
        escalation = (1 + price_escalation_pct_per_year / 100.0) ** year_index
        prices = (
            prices_eur_per_mwh
            if escalation == 1.0
            else [price * escalation for price in prices_eur_per_mwh]
        )
        year = simulate_storage_year(
            prices,
            spec,
            year_index=year_index,
            cumulative_equivalent_cycles=cumulative_cycles,
            start_soc_fraction=soc_fraction,
            keep_traces=keep_first_year_traces and year_index == 0,
        )
        cumulative_cycles += year.equivalent_full_cycles
        if year.usable_energy_mwh > 0:
            soc_fraction = max(0.0, min(1.0, year.final_soc_mwh / year.usable_energy_mwh))
        results.append(year)

    return results
