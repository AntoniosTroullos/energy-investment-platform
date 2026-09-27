"""Real, cited financial analysis for candidate investment sites -- bridges
the static candidate-screening system (app/evaluation.py, zero cost/financial
data) to the real PyPSA-solved scenario results.

Cost/financial assumptions (capital cost, FOM%, lifetime, discount rate,
marginal cost per carrier) are read directly from pypsa-greece's own
data/static/technology_costs.csv -- real, cited, read-only sibling-project
data, not invented here.

The NPV/IRR math (degraded_generation_mwh, npv_eur, annual_net_cash_flows,
irr) is ported -- not imported, since pypsa-greece/src/investment.py depends
on pandas/pypsa, which apps/api deliberately keeps out of its own
requirements.txt -- from that same file, built there for EXISTING generator
clusters in a solved network. A candidate cell has no matching PyPSA
generator, so three more real-but-approximate steps close that gap:

  * captured price -- the candidate's assigned region's own solved
    average_marginal_price_by_bus (real, but a system-wide regional average,
    not a technology-specific captured price).
  * annual generation -- the solved scenario's own NATIONAL capacity factor
    for the carrier (generation_by_carrier_mwh / (installed_capacity_by_carrier_mw
    * 8760), both already in ScenarioMetrics) applied to an assumed capacity.
  * assumed capacity -- cell_area_km2 * buildable_fraction * a power-density
    constant below. This last one is a plain external literature range, NOT
    Greece-specific or independently re-verified this pass -- flag it in any
    response the same way technology_costs.csv's own weaker rows (oil,
    biomass) flag themselves, not as settled fact.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import pyproj
from shapely.geometry import shape
from shapely.ops import transform

from .models import (
    CandidateCell,
    CandidateInvestmentAnalysis,
    PortfolioBreakdownEntry,
)
from .scenario_models import ScenarioMetrics
from .settings import Settings
from .settings import settings as default_settings

TECHNOLOGY_COSTS_RELATIVE_PATH = Path("data") / "static" / "technology_costs.csv"

# Utility-scale power density, MW of nameplate capacity per km^2 of buildable
# land. External literature range (solar: commonly-cited utility-PV figures
# in the ~30-45 MW/km^2 range; onshore wind: commonly-cited array-density
# figures in the ~5-8 MW/km^2 range, driven by turbine spacing, not raw
# footprint) -- NOT Greece-specific, NOT independently re-verified in this
# pass. Treat with at least as much caution as technology_costs.csv's own
# self-flagged weaker rows (oil, biomass).
POWER_DENSITY_MW_PER_KM2 = {"solar": 40.0, "wind": 6.0}

# A candidate cell's grid square (~0.1deg, ~11km x ~9km -- see
# pipeline/generate_candidates.py) is a screening area, not a real single
# project footprint: at the power densities above, a mostly-buildable cell
# implies a several-GW plant, which no real solar/wind project is. Capped
# here at a typical real-world single utility-scale project size (solar:
# commonly seen up to a couple hundred MW; onshore wind: commonly seen up to
# roughly a hundred MW) so capex/NPV describe a plausible single investment,
# not "build over the entire cell." IRR/LCOE/payback are scale-invariant and
# unaffected by this cap either way.
MAX_SINGLE_PROJECT_CAPACITY_MW = {"solar": 200.0, "wind": 100.0}

# Real, cited annual output-degradation rates -- ported verbatim from
# pypsa-greece/src/investment.py (see that file for the NREL/LBNL/
# Staffell&Green citations behind these two figures).
SOLAR_DEGRADATION_PCT_PER_YEAR = 0.5
WIND_DEGRADATION_PCT_PER_YEAR = 1.0
DEGRADATION_PCT_PER_YEAR = {
    "solar": SOLAR_DEGRADATION_PCT_PER_YEAR,
    "wind": WIND_DEGRADATION_PCT_PER_YEAR,
}

# Built once and reused for every cell -- pyproj.Transformer construction
# does a real CRS-database lookup and is too expensive to redo per call
# (this ran once per candidate cell, per request, with no caching).
_TO_EGSA87 = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:2100", always_xy=True).transform

HOURS_PER_YEAR = 8760.0

ASSUMPTIONS_NOTE = {
    "power_density": (
        "Assumed capacity = buildable land area x buildable_fraction x an external "
        f"literature power-density figure ({POWER_DENSITY_MW_PER_KM2['solar']:.0f} MW/km^2 solar, "
        f"{POWER_DENSITY_MW_PER_KM2['wind']:.0f} MW/km^2 onshore wind) -- not Greece-specific, "
        "not independently re-verified -- capped at a typical single utility-scale project size "
        f"({MAX_SINGLE_PROJECT_CAPACITY_MW['solar']:.0f} MW solar, {MAX_SINGLE_PROJECT_CAPACITY_MW['wind']:.0f} MW "
        "onshore wind) since a candidate cell is a screening area, not a real project footprint. "
        "IRR/LCOE/payback are unaffected by this cap; capex/NPV describe that capped single project, "
        "not the cell's full buildable potential."
    ),
    "capacity_factor": (
        "Annual generation uses the solved scenario's own NATIONAL capacity factor for the "
        "technology (real solved generation / installed capacity), not a region- or site-specific figure."
    ),
    "captured_price": (
        "Captured price is the candidate's region's solved average marginal price across ALL "
        "technologies, not a technology-specific captured price (no per-carrier regional price "
        "series exists in this model)."
    ),
    "cost_source": (
        "Capital cost, fixed O&M, lifetime, discount rate and marginal cost are read directly "
        "from pypsa-greece's technology_costs.csv (real, cited)."
    ),
}


@dataclass(frozen=True)
class TechnologyCostRow:
    carrier: str
    marginal_cost_eur_per_mwh: float
    overnight_capex_eur_per_kw: float | None
    lifetime_years: float | None
    discount_rate_pct: float | None
    fom_pct_of_capex: float | None


def technology_costs_path(cfg: Settings = default_settings) -> Path:
    return cfg.pypsa_greece_root / TECHNOLOGY_COSTS_RELATIVE_PATH


def load_technology_costs(cfg: Settings = default_settings) -> dict[str, TechnologyCostRow]:
    path = technology_costs_path(cfg)
    if not path.is_file():
        return {}

    costs: dict[str, TechnologyCostRow] = {}
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            carrier = row.get("carrier")
            if not carrier:
                continue
            costs[carrier] = TechnologyCostRow(
                carrier=carrier,
                marginal_cost_eur_per_mwh=_to_float(row.get("marginal_cost")) or 0.0,
                overnight_capex_eur_per_kw=_to_float(row.get("overnight_capex_eur_per_kw")),
                lifetime_years=_to_float(row.get("lifetime_years")),
                discount_rate_pct=_to_float(row.get("discount_rate_pct")),
                fom_pct_of_capex=_to_float(row.get("fom_pct_of_capex")),
            )
    return costs


def _to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def candidate_carrier(technology: str) -> str | None:
    """Maps a candidate cell's free-text technology ("Solar PV", "Onshore
    Wind", ...) to a technology_costs.csv carrier -- same substring
    convention app/evaluation.py's matches_scenario_rules already uses for
    the same two technologies."""
    normalized = technology.lower()
    if "solar" in normalized:
        return "solar"
    if "wind" in normalized:
        return "wind"
    return None


def cell_area_km2(cell: CandidateCell) -> float:
    """Reprojects to Greece's national grid (EGSA87 / EPSG:2100) before
    measuring area -- same approach as pipeline/fetch_osm_regional_units.py's
    geodesic_area_km2 (raw shapely .area on WGS84 lon/lat degrees is not a
    real area)."""
    projected = transform(_TO_EGSA87, shape(cell.geometry))
    return projected.area / 1_000_000.0


def assumed_capacity_mw(cell: CandidateCell, carrier: str) -> float | None:
    power_density = POWER_DENSITY_MW_PER_KM2.get(carrier)
    max_capacity = MAX_SINGLE_PROJECT_CAPACITY_MW.get(carrier)
    if power_density is None or max_capacity is None or cell.buildable_fraction is None:
        return None
    full_buildout = cell_area_km2(cell) * cell.buildable_fraction * power_density
    return min(full_buildout, max_capacity)


def degraded_generation_mwh(generation_year0_mwh: float, carrier: str, years_elapsed: float) -> float:
    degradation_pct = DEGRADATION_PCT_PER_YEAR.get(carrier, 0.0)
    return generation_year0_mwh * (1 - degradation_pct / 100.0) ** years_elapsed


def _year_fractions(lifetime_years: float) -> tuple[int, float]:
    full_years = int(lifetime_years)
    return full_years, lifetime_years - full_years


def npv_eur(
    capex_eur: float,
    generation_year0_mwh: float,
    captured_price_eur_per_mwh: float,
    marginal_cost_eur_per_mwh: float,
    carrier: str,
    lifetime_years: float,
    discount_rate_pct: float,
    fom_pct_of_capex: float,
) -> float:
    """Standard DCF -- ported verbatim from pypsa-greece/src/investment.py."""
    discount_rate = discount_rate_pct / 100.0
    fixed_opex_eur = capex_eur * fom_pct_of_capex / 100.0
    full_years, fractional_year = _year_fractions(lifetime_years)

    value = -capex_eur
    for year in range(1, full_years + 1):
        generation = degraded_generation_mwh(generation_year0_mwh, carrier, year - 1)
        net_cash_flow = (
            generation * captured_price_eur_per_mwh
            - generation * marginal_cost_eur_per_mwh
            - fixed_opex_eur
        )
        value += net_cash_flow / ((1 + discount_rate) ** year)

    if fractional_year > 1e-9:
        generation = degraded_generation_mwh(generation_year0_mwh, carrier, full_years) * fractional_year
        net_cash_flow = (
            generation * captured_price_eur_per_mwh
            - generation * marginal_cost_eur_per_mwh
            - fixed_opex_eur * fractional_year
        )
        value += net_cash_flow / ((1 + discount_rate) ** lifetime_years)

    return value


def annual_net_cash_flows(
    capex_eur: float,
    generation_year0_mwh: float,
    captured_price_eur_per_mwh: float,
    marginal_cost_eur_per_mwh: float,
    carrier: str,
    lifetime_years: float,
    fom_pct_of_capex: float,
) -> list[float]:
    """Undiscounted cash flows [year0, year1, ...] -- ported verbatim from
    pypsa-greece/src/investment.py."""
    fixed_opex_eur = capex_eur * fom_pct_of_capex / 100.0
    full_years, _ = _year_fractions(lifetime_years)

    flows = [-capex_eur]
    for year in range(1, full_years + 1):
        generation = degraded_generation_mwh(generation_year0_mwh, carrier, year - 1)
        flows.append(
            generation * captured_price_eur_per_mwh
            - generation * marginal_cost_eur_per_mwh
            - fixed_opex_eur
        )
    return flows


def irr(cash_flows: list[float], tolerance: float = 1e-6, max_iterations: int = 200) -> float | None:
    """Bisection on the discount rate that zeroes NPV -- ported verbatim from
    pypsa-greece/src/investment.py. Returns None if the cash flows don't
    bracket a root in [-99%, 1000%] (e.g. never profitable)."""

    def npv_at_rate(rate: float) -> float:
        return sum(cf / ((1 + rate) ** t) for t, cf in enumerate(cash_flows))

    low, high = -0.99, 10.0
    value_low, value_high = npv_at_rate(low), npv_at_rate(high)
    if value_low * value_high > 0:
        return None

    mid = low
    for _ in range(max_iterations):
        mid = (low + high) / 2
        value_mid = npv_at_rate(mid)
        if abs(value_mid) < tolerance:
            return mid
        if value_low * value_mid < 0:
            high = mid
            value_high = value_mid
        else:
            low = mid
            value_low = value_mid
    return mid


def lcoe_eur_per_mwh(
    capex_eur: float,
    generation_year0_mwh: float,
    marginal_cost_eur_per_mwh: float,
    carrier: str,
    lifetime_years: float,
    discount_rate_pct: float,
    fom_pct_of_capex: float,
) -> float | None:
    """Discounted lifetime cost / discounted lifetime generation -- the one
    genuinely new metric here (no upstream equivalent in investment.py),
    using the same year-loop shape as npv_eur for consistency."""
    discount_rate = discount_rate_pct / 100.0
    fixed_opex_eur = capex_eur * fom_pct_of_capex / 100.0
    full_years, fractional_year = _year_fractions(lifetime_years)

    discounted_costs = capex_eur
    discounted_generation = 0.0
    for year in range(1, full_years + 1):
        generation = degraded_generation_mwh(generation_year0_mwh, carrier, year - 1)
        discounted_costs += (fixed_opex_eur + generation * marginal_cost_eur_per_mwh) / ((1 + discount_rate) ** year)
        discounted_generation += generation / ((1 + discount_rate) ** year)

    if fractional_year > 1e-9:
        generation = degraded_generation_mwh(generation_year0_mwh, carrier, full_years) * fractional_year
        discounted_costs += (
            fixed_opex_eur * fractional_year + generation * marginal_cost_eur_per_mwh
        ) / ((1 + discount_rate) ** lifetime_years)
        discounted_generation += generation / ((1 + discount_rate) ** lifetime_years)

    if discounted_generation <= 0:
        return None
    return discounted_costs / discounted_generation


def payback_period_years(cash_flows: list[float]) -> float | None:
    """Simple cumulative payback from the same undiscounted cash flows
    annual_net_cash_flows produces. None if it never pays back within the
    technology's modeled lifetime."""
    cumulative = cash_flows[0]
    for year, flow in enumerate(cash_flows[1:], start=1):
        previous_cumulative = cumulative
        cumulative += flow
        if cumulative >= 0:
            if flow == 0:
                return float(year)
            fraction = -previous_cumulative / flow
            return (year - 1) + fraction
    return None


def national_capacity_factor(
    carrier: str,
    generation_by_carrier_mwh: dict[str, float],
    installed_capacity_by_carrier_mw: dict[str, float],
) -> float | None:
    generation = generation_by_carrier_mwh.get(carrier)
    capacity = installed_capacity_by_carrier_mw.get(carrier)
    if not generation or not capacity:
        return None
    return generation / (capacity * HOURS_PER_YEAR)


@dataclass(frozen=True)
class CandidateFinancialInputs:
    carrier: str
    capacity_mw: float
    capex_eur: float
    generation_year0_mwh: float
    captured_price_eur_per_mwh: float
    marginal_cost_eur_per_mwh: float
    lifetime_years: float
    discount_rate_pct: float
    fom_pct_of_capex: float


def _derive_financial_inputs(
    cell: CandidateCell,
    region_id: str | None,
    metrics: ScenarioMetrics,
    costs: dict[str, TechnologyCostRow],
) -> tuple[CandidateFinancialInputs | None, str | None, str | None, float | None]:
    """Every place evaluate_candidate_investment used to return early with a
    `message` before this was extracted -- shared by evaluate_candidate_investment
    and candidate_cash_flows (the latter used by the portfolio aggregation
    below) so the derivation exists in exactly one place. Returns (inputs,
    message, carrier, partial_capacity_mw): carrier and partial_capacity_mw
    are filled in as soon as they're known even when a later step fails, so
    a caller can still surface them alongside the message exactly as the
    original, non-extracted version did."""
    carrier = candidate_carrier(cell.technology)
    if carrier is None:
        return None, "Only solar and wind candidates are supported by this analysis.", None, None

    cost_row = costs.get(carrier)
    if cost_row is None or cost_row.overnight_capex_eur_per_kw is None:
        return None, f"No capital cost data for '{carrier}' in technology_costs.csv.", carrier, None

    if region_id is None:
        return None, "This candidate's centroid does not fall inside any of the 13 modeled regions.", carrier, None

    capacity_mw = assumed_capacity_mw(cell, carrier)
    if not capacity_mw:
        return None, "Could not derive an assumed installed capacity for this candidate.", carrier, None

    capacity_factor = national_capacity_factor(
        carrier, metrics.generation_by_carrier_mwh, metrics.installed_capacity_by_carrier_mw
    )
    captured_price = metrics.average_marginal_price_by_bus.get(region_id)
    if capacity_factor is None or captured_price is None:
        return (
            None,
            "This solved scenario has no capacity factor or price data for this carrier/region.",
            carrier,
            capacity_mw,
        )

    capex_eur = capacity_mw * 1000.0 * cost_row.overnight_capex_eur_per_kw
    generation_year0_mwh = capacity_mw * capacity_factor * HOURS_PER_YEAR

    inputs = CandidateFinancialInputs(
        carrier=carrier,
        capacity_mw=capacity_mw,
        capex_eur=capex_eur,
        generation_year0_mwh=generation_year0_mwh,
        captured_price_eur_per_mwh=captured_price,
        marginal_cost_eur_per_mwh=cost_row.marginal_cost_eur_per_mwh,
        lifetime_years=cost_row.lifetime_years or 0.0,
        discount_rate_pct=cost_row.discount_rate_pct or 0.0,
        fom_pct_of_capex=cost_row.fom_pct_of_capex or 0.0,
    )
    return inputs, None, carrier, capacity_mw


def evaluate_candidate_with_cash_flows(
    cell: CandidateCell,
    region_id: str | None,
    metrics: ScenarioMetrics,
    costs: dict[str, TechnologyCostRow],
) -> tuple[CandidateInvestmentAnalysis, list[float] | None]:
    """One derivation pass producing both the per-candidate analysis and its
    annual cash flows -- evaluate_candidate_investment and
    candidate_cash_flows are thin wrappers around this, so a caller needing
    both (the portfolio endpoint) never derives the same financial inputs
    for the same candidate twice."""
    inputs, message, carrier, capacity_mw = _derive_financial_inputs(cell, region_id, metrics, costs)

    if inputs is None:
        return (
            CandidateInvestmentAnalysis(
                candidate_id=cell.id,
                technology=cell.technology,
                carrier=carrier,
                region_id=region_id,
                assumed_capacity_mw=round(capacity_mw, 2) if capacity_mw is not None else None,
                message=message,
            ),
            None,
        )

    npv_value = npv_eur(
        capex_eur=inputs.capex_eur,
        generation_year0_mwh=inputs.generation_year0_mwh,
        captured_price_eur_per_mwh=inputs.captured_price_eur_per_mwh,
        marginal_cost_eur_per_mwh=inputs.marginal_cost_eur_per_mwh,
        carrier=inputs.carrier,
        lifetime_years=inputs.lifetime_years,
        discount_rate_pct=inputs.discount_rate_pct,
        fom_pct_of_capex=inputs.fom_pct_of_capex,
    )
    flows = annual_net_cash_flows(
        capex_eur=inputs.capex_eur,
        generation_year0_mwh=inputs.generation_year0_mwh,
        captured_price_eur_per_mwh=inputs.captured_price_eur_per_mwh,
        marginal_cost_eur_per_mwh=inputs.marginal_cost_eur_per_mwh,
        carrier=inputs.carrier,
        lifetime_years=inputs.lifetime_years,
        fom_pct_of_capex=inputs.fom_pct_of_capex,
    )
    lcoe_value = lcoe_eur_per_mwh(
        capex_eur=inputs.capex_eur,
        generation_year0_mwh=inputs.generation_year0_mwh,
        marginal_cost_eur_per_mwh=inputs.marginal_cost_eur_per_mwh,
        carrier=inputs.carrier,
        lifetime_years=inputs.lifetime_years,
        discount_rate_pct=inputs.discount_rate_pct,
        fom_pct_of_capex=inputs.fom_pct_of_capex,
    )
    irr_value = irr(flows)
    payback_value = payback_period_years(flows)

    analysis = CandidateInvestmentAnalysis(
        candidate_id=cell.id,
        technology=cell.technology,
        carrier=inputs.carrier,
        region_id=region_id,
        assumed_capacity_mw=round(inputs.capacity_mw, 2),
        capex_eur=round(inputs.capex_eur, 0),
        annual_generation_year0_mwh=round(inputs.generation_year0_mwh, 1),
        captured_price_eur_per_mwh=round(inputs.captured_price_eur_per_mwh, 2),
        lcoe_eur_per_mwh=round(lcoe_value, 2) if lcoe_value is not None else None,
        npv_eur=round(npv_value, 0),
        irr_pct=round(irr_value * 100, 2) if irr_value is not None else None,
        payback_years=round(payback_value, 1) if payback_value is not None else None,
    )
    return analysis, flows


def evaluate_candidate_investment(
    cell: CandidateCell,
    region_id: str | None,
    metrics: ScenarioMetrics,
    costs: dict[str, TechnologyCostRow],
) -> CandidateInvestmentAnalysis:
    analysis, _ = evaluate_candidate_with_cash_flows(cell, region_id, metrics, costs)
    return analysis


def candidate_cash_flows(
    cell: CandidateCell,
    region_id: str | None,
    metrics: ScenarioMetrics,
    costs: dict[str, TechnologyCostRow],
) -> list[float] | None:
    """The same undiscounted annual cash flows evaluate_candidate_investment
    derives internally for its own IRR/payback -- exposed standalone for any
    caller that only needs the flows (e.g. combine_cash_flows for a
    portfolio-level cash-flow stream, rather than averaging each candidate's
    own IRR, which is not how IRR combines across investments)."""
    _, flows = evaluate_candidate_with_cash_flows(cell, region_id, metrics, costs)
    return flows


def combine_cash_flows(flows_list: list[list[float]]) -> list[float]:
    """Zero-pads each candidate's own (whole-years-only, per
    annual_net_cash_flows) cash-flow list to the longest one and sums
    element-wise -- the correct way to get a portfolio-level cash-flow
    stream (and, from it, a real portfolio IRR/payback via irr()/
    payback_period_years()), as opposed to averaging each candidate's own
    IRR, which is not how IRR combines across investments. Implies that a
    technology's cash flows simply stop at its own modeled lifetime -- no
    repowering/reinvestment is assumed after that."""
    if not flows_list:
        return []
    max_len = max(len(flows) for flows in flows_list)
    combined = [0.0] * max_len
    for flows in flows_list:
        for index, value in enumerate(flows):
            combined[index] += value
    return combined


# Single-category concentration threshold used only to generate a
# plain-language note -- an arbitrary, commonly-used-in-practice figure for a
# small portfolio, not a formal risk metric.
CONCENTRATION_THRESHOLD_PCT = 60.0


def build_breakdown(
    included: list[CandidateInvestmentAnalysis],
    key_fn,
) -> list[PortfolioBreakdownEntry]:
    groups: dict[str, list[CandidateInvestmentAnalysis]] = {}
    for analysis in included:
        label = key_fn(analysis) or "unknown"
        groups.setdefault(label, []).append(analysis)

    total_capex = sum(analysis.capex_eur or 0.0 for analysis in included)
    entries = []
    for label, group in groups.items():
        group_capex = sum(analysis.capex_eur or 0.0 for analysis in group)
        group_capacity = sum(analysis.assumed_capacity_mw or 0.0 for analysis in group)
        entries.append(
            PortfolioBreakdownEntry(
                label=label,
                capex_eur=round(group_capex, 0),
                assumed_capacity_mw=round(group_capacity, 2),
                candidate_count=len(group),
                capex_share_pct=round(100.0 * group_capex / total_capex, 1) if total_capex else 0.0,
            )
        )
    entries.sort(key=lambda entry: entry.capex_share_pct, reverse=True)
    return entries


def concentration_flags(breakdown_groups: list[list[PortfolioBreakdownEntry]]) -> list[str]:
    flags = []
    for entries in breakdown_groups:
        for entry in entries:
            if entry.capex_share_pct > CONCENTRATION_THRESHOLD_PCT:
                flags.append(
                    f"{entry.label} accounts for {entry.capex_share_pct:.0f}% of portfolio capex "
                    f"(a single-category concentration above the {CONCENTRATION_THRESHOLD_PCT:.0f}% "
                    "threshold used here -- not a formal risk metric)."
                )
    return flags
