"""Staleness of a solved scenario result.

A cached scenario_result.json can silently disagree with the model that would
be solved today: the upstream project is under active development, so its
code and input tables change after results were written. This module answers
"has anything the result depends on changed since it was solved?" -- from file
modification times only, so it is cheap enough to run on every library listing
and needs no bookkeeping written at solve time (which would not exist for
results solved before this check did).

A result is stale when either:
  * a watched model *code* file (.py) is newer than the result, or
  * a watched model *input* table (.csv) is newer than the result, or
  * (coupled results only) its parent electricity result was re-solved after
    the coupled result was written -- the coupled network is built on top of
    that electricity case, so it no longer describes the current one.

Modification times are a deliberate, conservative signal: an edit that does
not change behaviour (a comment, a reformat) still marks results stale. False
"outdated" is the safe direction here -- it costs a re-solve, whereas a false
"up to date" would present a superseded number as current.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal, Sequence

from pydantic import BaseModel

# Ignore sub-second/filesystem-granularity noise: a file written by the same
# solve run that produced the result must never count as "changed after" it.
MTIME_TOLERANCE_SECONDS = 2.0

# Watched paths, relative to the upstream project root (the sibling PyPSA
# project). Coupled-only files are excluded from the electricity watchlist so
# that editing the gas/hydrogen/heat code does not mark electricity results
# outdated.
COUPLED_ONLY_NAMES = frozenset(
    {
        "build_and_solve_coupled_year.py",
        "coupled_energy_system.py",
        "coupled_inputs.py",
        "gas_market.py",
        "hydrogen_market.py",
        "heating_demand.py",
        "heating_technology_costs.csv",
        "h2_market_scenarios.csv",
        "electrolyzer_technology_costs.csv",
        "eu_greece_energy_targets.csv",
    }
)

_ELECTRICITY_PATTERNS: tuple[str, ...] = (
    "scripts/run_multiyear_electricity.py",
    "scripts/run_pypsa_scenario.py",
    "src/energy_data/*.py",
    "pypsa-greece/src/*.py",
    # The baseline network tables the scenario solves (not the per-carrier
    # heating/gas/hydrogen variants, which only the coupled solve reads).
    "pypsa-greece/data/static/buses.csv",
    "pypsa-greece/data/static/generators.csv",
    "pypsa-greece/data/static/lines.csv",
    "pypsa-greece/data/static/storage_units.csv",
    "pypsa-greece/data/static/technology_costs.csv",
)

_COUPLED_EXTRA_PATTERNS: tuple[str, ...] = (
    "scripts/build_and_solve_coupled_year.py",
    "pypsa-greece/src/*.py",
    "pypsa-greece/data/static/heating_technology_costs.csv",
    "pypsa-greece/data/static/h2_market_scenarios.csv",
    "pypsa-greece/data/static/electrolyzer_technology_costs.csv",
    "pypsa-greece/data/static/eu_greece_energy_targets.csv",
)

ReasonCode = Literal["model_code_changed", "model_inputs_changed", "parent_resolved"]


class StaleReason(BaseModel):
    code: ReasonCode
    detail: str
    changed_at: str  # ISO-8601 UTC


class Staleness(BaseModel):
    solved_at: str | None = None  # ISO-8601 UTC, the result file's mtime
    is_stale: bool = False
    reasons: list[StaleReason] = []


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _expand(root: Path, patterns: Sequence[str], *, include_coupled_only: bool) -> list[Path]:
    found: dict[Path, None] = {}
    for pattern in patterns:
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            if not include_coupled_only and path.name in COUPLED_ONLY_NAMES:
                continue
            found[path] = None
    return list(found)


def electricity_watchlist(project_root: Path) -> list[Path]:
    return _expand(project_root, _ELECTRICITY_PATTERNS, include_coupled_only=False)


def coupled_watchlist(project_root: Path) -> list[Path]:
    return _expand(
        project_root,
        _ELECTRICITY_PATTERNS + _COUPLED_EXTRA_PATTERNS,
        include_coupled_only=True,
    )


def _newer_than(paths: Iterable[Path], threshold: float) -> list[tuple[float, Path]]:
    newer: list[tuple[float, Path]] = []
    for path in paths:
        try:
            modified = path.stat().st_mtime
        except OSError:
            continue  # vanished between glob and stat -- not evidence of change
        if modified > threshold + MTIME_TOLERANCE_SECONDS:
            newer.append((modified, path))
    return newer


def _describe(changed: list[tuple[float, Path]], root: Path, noun: str) -> tuple[str, float]:
    latest_time, latest_path = max(changed, key=lambda item: item[0])
    try:
        shown = latest_path.relative_to(root).as_posix()
    except ValueError:
        shown = latest_path.name
    count = len(changed)
    detail = f"{count} {noun}{'s' if count != 1 else ''} changed since this was solved; latest: {shown}"
    return detail, latest_time


def assess(
    result_path: Path,
    watchlist: Iterable[Path],
    project_root: Path,
    *,
    parent_result_path: Path | None = None,
) -> Staleness | None:
    """Returns None when there is no result to assess (nothing solved yet)."""
    try:
        solved_at = result_path.stat().st_mtime
    except OSError:
        return None

    reasons: list[StaleReason] = []
    changed = _newer_than(watchlist, solved_at)

    code_changed = [item for item in changed if item[1].suffix == ".py"]
    if code_changed:
        detail, when = _describe(code_changed, project_root, "model code file")
        reasons.append(StaleReason(code="model_code_changed", detail=detail, changed_at=_iso(when)))

    inputs_changed = [item for item in changed if item[1].suffix != ".py"]
    if inputs_changed:
        detail, when = _describe(inputs_changed, project_root, "model input table")
        reasons.append(StaleReason(code="model_inputs_changed", detail=detail, changed_at=_iso(when)))

    if parent_result_path is not None:
        parent_newer = _newer_than([parent_result_path], solved_at)
        if parent_newer:
            reasons.append(
                StaleReason(
                    code="parent_resolved",
                    detail="The electricity case this was built on has been re-solved since.",
                    changed_at=_iso(parent_newer[0][0]),
                )
            )

    return Staleness(solved_at=_iso(solved_at), is_stale=bool(reasons), reasons=reasons)
