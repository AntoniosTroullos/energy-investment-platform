"""Where valid PyPSA scenario parameters come from.

Both scenario request types used to hard-code their valid choices: the
coupled year/H2-scenario combination was frozen in scenario_models.py as
Literals, and the frontend kept its own separate copy of the same list in two
different panels. All three had to be edited in step whenever the real source
of truth -- pypsa-greece/data/static/h2_market_scenarios.csv -- gained a row,
and nothing enforced that they were kept in sync.

This module reads that CSV directly, so:
  * GET /scenarios/options gives the frontend a picker built from what is
    actually solvable, not a hard-coded list.
  * validate_coupled_request() turns a combination the CSV doesn't define into
    a clean 422 instead of a crashed subprocess (build_and_solve_coupled_year.py
    raises a bare ValueError for anything not in that CSV).
"""

from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel

from .scenario_models import (
    GROWTH_RATE_DEFAULT,
    GROWTH_RATE_MAX,
    GROWTH_RATE_MIN,
    TARGET_YEAR_MAX,
    TARGET_YEAR_MIN,
)
from .settings import Settings
from .settings import settings as default_settings
from .system_status import list_solved_electricity_years

H2_MARKET_SCENARIOS_RELATIVE_PATH = Path("data") / "static" / "h2_market_scenarios.csv"

# Electricity years offered when nothing has been solved yet. Purely a
# starting point for the picker -- any year in [TARGET_YEAR_MIN,
# TARGET_YEAR_MAX] can still be typed/selected and solved; already-solved
# years (whatever they are) are always added on top of this set.
DEFAULT_ELECTRICITY_YEAR_CHOICES: tuple[int, ...] = (2030, 2035, 2040, 2045, 2050)


class InvalidCoupledScenarioError(ValueError):
    """(target_year, h2_market_scenario) is not a row in
    h2_market_scenarios.csv. Not a ScenarioRunError subclass: this is a
    malformed request (422), not a run that failed or a precondition that
    was not yet met (409/428)."""


class ElectricityYearOption(BaseModel):
    year: int
    solved: bool


class CoupledScenarioOption(BaseModel):
    target_year: int
    h2_market_scenario: str
    label: str
    # Whether run_coupled_scenario's own precondition (the electricity case
    # for this year is solved) is met right now -- lets the frontend grey
    # out an option instead of the user discovering the 428 by clicking it.
    electricity_solved: bool


class ScenarioOptionsResponse(BaseModel):
    target_year_min: int
    target_year_max: int
    annual_growth_rate_min: float
    annual_growth_rate_max: float
    annual_growth_rate_default: float
    electricity_years: list[ElectricityYearOption]
    coupled_options: list[CoupledScenarioOption]


def h2_market_scenarios_path(cfg: Settings = default_settings) -> Path:
    return cfg.pypsa_greece_root / H2_MARKET_SCENARIOS_RELATIVE_PATH


def load_h2_market_scenario_rows(cfg: Settings = default_settings) -> list[dict[str, str]]:
    path = h2_market_scenarios_path(cfg)
    if not path.is_file():
        return []

    with path.open("r", encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def valid_coupled_combinations(cfg: Settings = default_settings) -> set[tuple[int, str]]:
    combinations: set[tuple[int, str]] = set()
    for row in load_h2_market_scenario_rows(cfg):
        year_text, scenario = row.get("year"), row.get("scenario")
        if not year_text or not scenario:
            continue
        try:
            combinations.add((int(year_text), scenario))
        except ValueError:
            continue
    return combinations


def validate_coupled_request(
    target_year: int,
    h2_market_scenario: str,
    cfg: Settings = default_settings,
) -> None:
    combinations = valid_coupled_combinations(cfg)
    if not combinations:
        # The CSV is missing or unreadable -- a data/environment problem, not
        # something this specific request got wrong. Fail open here and let
        # the actual solve attempt surface that separately, rather than block
        # every coupled request on it.
        return

    if (target_year, h2_market_scenario) in combinations:
        return

    years_for_scenario = sorted(year for year, scenario in combinations if scenario == h2_market_scenario)
    if years_for_scenario:
        raise InvalidCoupledScenarioError(
            f"H2 market scenario '{h2_market_scenario}' is not defined for {target_year}. "
            f"It is defined for: {years_for_scenario}."
        )

    known_scenarios = sorted({scenario for _, scenario in combinations})
    raise InvalidCoupledScenarioError(
        f"Unknown H2 market scenario '{h2_market_scenario}'. Known scenarios: {known_scenarios}."
    )


def get_scenario_options(cfg: Settings = default_settings) -> ScenarioOptionsResponse:
    solved_years = set(list_solved_electricity_years(cfg.scenario_root))

    electricity_years = [
        ElectricityYearOption(year=year, solved=year in solved_years)
        for year in sorted(solved_years | set(DEFAULT_ELECTRICITY_YEAR_CHOICES))
    ]

    coupled_options = [
        CoupledScenarioOption(
            target_year=year,
            h2_market_scenario=scenario,
            label=f"{scenario.replace('_', ' ').title()} ({year})",
            electricity_solved=year in solved_years,
        )
        for year, scenario in sorted(valid_coupled_combinations(cfg))
    ]

    return ScenarioOptionsResponse(
        target_year_min=TARGET_YEAR_MIN,
        target_year_max=TARGET_YEAR_MAX,
        annual_growth_rate_min=GROWTH_RATE_MIN,
        annual_growth_rate_max=GROWTH_RATE_MAX,
        annual_growth_rate_default=GROWTH_RATE_DEFAULT,
        electricity_years=electricity_years,
        coupled_options=coupled_options,
    )
