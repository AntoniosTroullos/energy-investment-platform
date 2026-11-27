"""Industrial demand response: what a large consumer earns for being flexible.

A heavy industrial site is not only a load. It is a dispatchable resource that
the system operator will pay to stand ready and pay again to actually move, and
in a market with 300-plus hours a year at or below zero and others above 500
EUR/MWh, the value of moving consumption is no longer a rounding error.

Three distinct ways a Greek industrial site is paid, modelled separately
because they settle separately and stack:

**1. Availability.** ADMIE's interruptibility scheme contracts industrial load
to be curtailable and pays for the option whether or not it is ever called.
Two products: Type 1 (the larger block, procured annually) and Type 2 (a
smaller, faster product capped at a couple of dozen hours a year). Payment is
per MW of contracted capacity per year, set at auction under a published cap.

**2. Activation.** When the operator calls, the site cuts load and is paid per
MWh not consumed, on top of the availability fee. Activations are bounded: a
maximum number per year, a maximum duration each, and a minimum gap between
them, because a scheme that could interrupt a smelter weekly would have no
takers.

**3. Price response.** Nothing to do with a contract -- simply not running the
expensive hours. A site with any storage in its process (a cold store, a
grinding circuit, an electrolyser) can shift consumption from the dearest hours
to the cheapest and keep the difference.

The cost side, which decides whether any of it is worth doing
--------------------------------------------------------------
Interrupting production is not free. A steel mill that stops loses the output
it would have made, may scrap work in progress, and pays to restart. That cost,
per MWh not consumed, is the number the whole calculation turns on, and it is
specific to the process -- which is why it is a required input here with no
default. A site whose production loss exceeds the activation price should not
be in the scheme, and this module will say so rather than reporting a profit.

Rebound matters too: most processes make up the lost output later, so the
energy comes back, usually in hours the site did not choose.

On the defaults
---------------
The scheme's structure is well documented and stable; its current numbers are
not public. The defaults below are the last published auction caps (70,000
EUR/MW/yr Type 1, 50,000 Type 2) and the documented shape of the products.
Every one is a parameter: a site prices its own contract by passing its own
terms, which is the only use of this that means anything commercially.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

HOURS_PER_YEAR = 8760


class InterruptibilityProduct(str, Enum):
    TYPE_1 = "type_1"
    TYPE_2 = "type_2"


# Last published auction caps for the Greek scheme, EUR per MW of contracted
# capacity per year. The clearing price is at or below these.
DEFAULT_AVAILABILITY_CAP_EUR_PER_MW_YEAR = {
    InterruptibilityProduct.TYPE_1: 70_000.0,
    InterruptibilityProduct.TYPE_2: 50_000.0,
}

# The documented shape of each product: Type 2 is the small, fast one capped at
# roughly a day's worth of interruption a year.
DEFAULT_MAX_ACTIVATION_HOURS = {
    InterruptibilityProduct.TYPE_1: 200.0,
    InterruptibilityProduct.TYPE_2: 24.0,
}


@dataclass(frozen=True)
class InterruptibilityContract:
    """One contracted product."""

    product: InterruptibilityProduct
    contracted_mw: float

    availability_price_eur_per_mw_year: float | None = None
    # Paid per MWh not consumed when the operator calls.
    activation_price_eur_per_mwh: float = 0.0

    max_activation_hours_per_year: float | None = None
    max_activations_per_year: int = 20
    max_duration_hours: int = 4
    # The scheme keeps a floor between consecutive orders so a site is not
    # interrupted repeatedly. Five days is the documented figure.
    min_hours_between_activations: int = 120

    @property
    def availability_rate(self) -> float:
        if self.availability_price_eur_per_mw_year is not None:
            return self.availability_price_eur_per_mw_year
        return DEFAULT_AVAILABILITY_CAP_EUR_PER_MW_YEAR[self.product]

    @property
    def activation_hour_cap(self) -> float:
        if self.max_activation_hours_per_year is not None:
            return self.max_activation_hours_per_year
        return DEFAULT_MAX_ACTIVATION_HOURS[self.product]

    @property
    def annual_availability_revenue_eur(self) -> float:
        return self.contracted_mw * self.availability_rate


@dataclass(frozen=True)
class IndustrialSite:
    """A large consumer's flexibility, as the process actually allows it."""

    name: str
    baseline_load_mw: list[float]

    # The share of load that can physically be dropped on an operator's call.
    interruptible_fraction: float = 0.5

    # What stopping costs per MWh not consumed: foregone output, scrapped work
    # in progress, restart. No default -- it is process-specific and it decides
    # the whole answer.
    production_loss_eur_per_mwh: float = 0.0

    # The share of interrupted production made up afterwards. Energy comes
    # back, in hours the site did not choose.
    rebound_fraction: float = 0.0

    # Load the site can move in time rather than lose, as a share of baseline.
    shiftable_fraction: float = 0.0

    @property
    def annual_consumption_mwh(self) -> float:
        return sum(self.baseline_load_mw)

    @property
    def peak_load_mw(self) -> float:
        return max(self.baseline_load_mw) if self.baseline_load_mw else 0.0


@dataclass
class ActivationEvent:
    start_hour: int
    duration_hours: int
    energy_not_consumed_mwh: float
    payment_eur: float
    avoided_energy_cost_eur: float
    production_loss_eur: float
    price_at_activation_eur_per_mwh: float


@dataclass
class DemandResponseResult:
    site_name: str
    year: int

    availability_revenue_eur: float = 0.0
    activation_revenue_eur: float = 0.0
    avoided_energy_cost_eur: float = 0.0
    production_loss_eur: float = 0.0
    rebound_cost_eur: float = 0.0
    load_shifting_saving_eur: float = 0.0

    activation_count: int = 0
    activation_hours: float = 0.0
    energy_not_consumed_mwh: float = 0.0

    baseline_energy_cost_eur: float = 0.0
    events: list[ActivationEvent] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def net_benefit_eur(self) -> float:
        """Everything the flexibility earns, less everything it costs."""
        return (
            self.availability_revenue_eur
            + self.activation_revenue_eur
            + self.avoided_energy_cost_eur
            + self.load_shifting_saving_eur
            - self.production_loss_eur
            - self.rebound_cost_eur
        )

    @property
    def net_benefit_pct_of_energy_bill(self) -> float | None:
        if self.baseline_energy_cost_eur <= 0:
            return None
        return 100.0 * self.net_benefit_eur / self.baseline_energy_cost_eur


def simulate_demand_response(
    site: IndustrialSite,
    prices_eur_per_mwh: list[float],
    contracts: list[InterruptibilityContract],
    *,
    year: int = 2025,
) -> DemandResponseResult:
    """A year of flexibility for one industrial site, hour by hour."""
    hours = min(len(site.baseline_load_mw), len(prices_eur_per_mwh))
    result = DemandResponseResult(site_name=site.name, year=year)
    result.baseline_energy_cost_eur = round(
        sum(site.baseline_load_mw[hour] * prices_eur_per_mwh[hour] for hour in range(hours)), 2
    )

    for contract in contracts:
        result.availability_revenue_eur += contract.annual_availability_revenue_eur
        _simulate_activations(site, prices_eur_per_mwh, contract, hours, result)

    result.load_shifting_saving_eur = _simulate_load_shifting(site, prices_eur_per_mwh, hours)

    _round_result(result)
    _add_notes(site, contracts, result)
    return result


def _simulate_activations(
    site: IndustrialSite,
    prices: list[float],
    contract: InterruptibilityContract,
    hours: int,
    result: DemandResponseResult,
) -> None:
    """Calls the contract in the hours the system is tightest.

    The operator activates when the system is short, and system shortage is
    what a high price IS -- scarcity is the price signal, not a separate
    variable. So the candidate hours are the dearest of the year, taken in
    order and subject to every contract limit: the hour cap, the activation
    count, the duration of each call and the minimum gap between them.

    This is a model of a scheme whose real calls depend on operational
    conditions no price series contains. It answers "what would this contract
    have been worth in a year that looked like this one", which is the
    question a site signing it needs answered."""
    available_mw = site.peak_load_mw * site.interruptible_fraction
    deliverable_mw = min(contract.contracted_mw, available_mw)
    if deliverable_mw <= 0 or hours <= 0:
        return

    ranked = sorted(range(hours), key=lambda hour: prices[hour], reverse=True)
    activated_hours: list[int] = []
    hours_used = 0.0
    # Counted per contract, not across all of them: the limits belong to the
    # product. A site holding both products can be called under each on its
    # own terms, which is the point of holding both.
    calls_made = 0

    for start in ranked:
        if calls_made >= contract.max_activations_per_year:
            break
        if hours_used >= contract.activation_hour_cap:
            break
        if any(abs(start - previous) < contract.min_hours_between_activations for previous in activated_hours):
            continue

        duration = int(
            min(
                contract.max_duration_hours,
                hours - start,
                contract.activation_hour_cap - hours_used,
            )
        )
        if duration <= 0:
            continue

        energy = 0.0
        avoided = 0.0
        for hour in range(start, start + duration):
            curtailed_mw = min(deliverable_mw, site.baseline_load_mw[hour])
            energy += curtailed_mw
            avoided += curtailed_mw * prices[hour]

        payment = energy * contract.activation_price_eur_per_mwh
        loss = energy * site.production_loss_eur_per_mwh

        result.events.append(
            ActivationEvent(
                start_hour=start,
                duration_hours=duration,
                energy_not_consumed_mwh=round(energy, 2),
                payment_eur=round(payment, 2),
                avoided_energy_cost_eur=round(avoided, 2),
                production_loss_eur=round(loss, 2),
                price_at_activation_eur_per_mwh=round(prices[start], 2),
            )
        )
        result.activation_revenue_eur += payment
        result.avoided_energy_cost_eur += avoided
        result.production_loss_eur += loss
        result.energy_not_consumed_mwh += energy
        result.activation_count += 1
        result.activation_hours += duration
        calls_made += 1
        activated_hours.append(start)
        hours_used += duration

        if site.rebound_fraction > 0:
            # Made up later, at hours the site does not choose -- valued at the
            # year's average price, since the catch-up is not optimised.
            average_price = sum(prices[:hours]) / hours
            result.rebound_cost_eur += energy * site.rebound_fraction * average_price


def _simulate_load_shifting(site: IndustrialSite, prices: list[float], hours: int) -> float:
    """Moving shiftable load from the dearest hours of each day to the cheapest.

    Day by day, not across the year: a process can usually move a batch within
    a shift or overnight, almost never across a month. The saving is the price
    difference on the energy moved."""
    if site.shiftable_fraction <= 0 or hours <= 0:
        return 0.0

    saving = 0.0
    for day_start in range(0, hours - 23, 24):
        day = list(range(day_start, day_start + 24))
        ordered = sorted(day, key=lambda hour: prices[hour])
        # Move the load of the four dearest hours into the four cheapest.
        cheapest, dearest = ordered[:4], ordered[-4:]
        for source, target in zip(dearest, cheapest):
            movable = site.baseline_load_mw[source] * site.shiftable_fraction
            delta = prices[source] - prices[target]
            if delta > 0:
                saving += movable * delta
    return saving


def _round_result(result: DemandResponseResult) -> None:
    result.availability_revenue_eur = round(result.availability_revenue_eur, 2)
    result.activation_revenue_eur = round(result.activation_revenue_eur, 2)
    result.avoided_energy_cost_eur = round(result.avoided_energy_cost_eur, 2)
    result.production_loss_eur = round(result.production_loss_eur, 2)
    result.rebound_cost_eur = round(result.rebound_cost_eur, 2)
    result.load_shifting_saving_eur = round(result.load_shifting_saving_eur, 2)
    result.energy_not_consumed_mwh = round(result.energy_not_consumed_mwh, 2)
    result.activation_hours = round(result.activation_hours, 2)


def _add_notes(
    site: IndustrialSite,
    contracts: list[InterruptibilityContract],
    result: DemandResponseResult,
) -> None:
    for contract in contracts:
        if (
            site.production_loss_eur_per_mwh > 0
            and contract.activation_price_eur_per_mwh < site.production_loss_eur_per_mwh
        ):
            result.notes.append(
                f"{contract.product.value}: being called costs more than it pays "
                f"({site.production_loss_eur_per_mwh:.0f} EUR/MWh of lost production against "
                f"{contract.activation_price_eur_per_mwh:.0f} EUR/MWh of activation payment). The "
                "availability fee still earns, but every call is a loss -- worth checking the "
                "contracted volume against what the process can really give up."
            )

    if result.availability_revenue_eur > 0 and result.activation_revenue_eur == 0:
        result.notes.append(
            "Paid to stand ready and never called in this year's prices: the availability fee is "
            "the whole return."
        )

    if result.net_benefit_eur > 0 and result.baseline_energy_cost_eur > 0:
        result.notes.append(
            f"Flexibility is worth {result.net_benefit_eur:,.0f} EUR a year against an energy bill of "
            f"{result.baseline_energy_cost_eur:,.0f} EUR "
            f"({result.net_benefit_pct_of_energy_bill:.1f}% of it)."
        )


# ---------------------------------------------------------------------------
# A baseline load profile, for a site that has not supplied its own
# ---------------------------------------------------------------------------


def continuous_process_load(average_mw: float, hours: int = HOURS_PER_YEAR) -> list[float]:
    """A continuous process: a smelter, a cement kiln, a paper mill. Nearly
    flat, because stopping is expensive -- which is exactly why its flexibility
    is valuable and costly at the same time."""
    return [average_mw] * hours


def two_shift_load(peak_mw: float, base_mw: float, hours: int = HOURS_PER_YEAR) -> list[float]:
    """A two-shift operation: full load 06:00-22:00 on weekdays, base load
    otherwise. A site with this shape has real freedom to move its hours."""
    profile: list[float] = []
    for hour in range(hours):
        hour_of_day = hour % 24
        day_of_week = (hour // 24) % 7
        working = day_of_week < 5 and 6 <= hour_of_day < 22
        profile.append(peak_mw if working else base_mw)
    return profile
