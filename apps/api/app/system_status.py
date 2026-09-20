"""Readiness checks for the API, its data layers and the PyPSA bridge.

One implementation serves two consumers so the interpretation of the
configured paths lives in exactly one place:

* GET /system/status  -- lets the frontend explain *why* solving is
  unavailable (and disable Solve) instead of failing with a cryptic subprocess
  error after the user has already clicked.
* `python -m app.system_status [--deep] [--json] [--strict]` -- the CLI behind
  `npm run doctor`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel, Field

from .evaluation import GENERATED_DATA_PATH, SOURCE_DATA_DIR
from .settings import Settings, settings as default_settings

# The layers the map and analysis views cannot start without.
REQUIRED_SOURCE_LAYERS: tuple[str, ...] = (
    "substations.geojson",
    "transmission_lines.geojson",
    "power_plants.geojson",
    "admin_regions.geojson",
    "greece_boundary.geojson",
    "natura_2000.geojson",
    "gas_pipelines.geojson",
    "hydrogen_projects.geojson",
)

# Everything the solver subprocess imports. Checked by --deep only, because
# starting that interpreter and importing pypsa/linopy takes several seconds.
SOLVER_STACK_IMPORTS: tuple[str, ...] = ("pypsa", "pandas", "linopy", "highspy", "xgboost")
DEEP_CHECK_TIMEOUT_SECONDS = 90

ELECTRICITY_CASE_PATTERN = re.compile(r"^future_electricity_(\d{4})$")


class CheckItem(BaseModel):
    name: str
    ok: bool
    detail: str = ""


class BridgeStatus(BaseModel):
    ready: bool
    project_root: str
    python: str
    scenario_root: str
    checks: list[CheckItem] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    # None = not checked (needs deep=True); True/False = checked.
    solver_stack_ok: bool | None = None
    solver_stack_error: str | None = None
    solved_electricity_years: list[int] = Field(default_factory=list)


class DataStatus(BaseModel):
    ready: bool
    layers: list[CheckItem] = Field(default_factory=list)


class SystemStatusResponse(BaseModel):
    api: str = "ok"
    bridge: BridgeStatus
    data: DataStatus
    cors_origins: list[str] = Field(default_factory=list)


def list_solved_electricity_years(scenario_root: Path) -> list[int]:
    """Years whose bridge-created electricity case has a result on disk. A
    plain directory scan (no process-liveness probing) so it stays cheap
    enough to call on every status request."""
    if not scenario_root.exists():
        return []

    years: list[int] = []
    for entry in scenario_root.iterdir():
        match = ELECTRICITY_CASE_PATTERN.match(entry.name)
        if match and entry.is_dir() and (entry / "scenario_result.json").exists():
            years.append(int(match.group(1)))

    return sorted(years)


def check_bridge(cfg: Settings = default_settings, deep: bool = False) -> BridgeStatus:
    checks = [
        CheckItem(
            name="PyPSA project root",
            ok=cfg.pypsa_project_root.is_dir(),
            detail=str(cfg.pypsa_project_root),
        ),
        CheckItem(
            name="Solver interpreter",
            ok=cfg.pypsa_python.is_file(),
            detail=str(cfg.pypsa_python),
        ),
        CheckItem(
            name="Electricity run script",
            ok=cfg.run_multiyear_script.is_file(),
            detail=str(cfg.run_multiyear_script),
        ),
        CheckItem(
            name="Coupled run script",
            ok=cfg.run_coupled_script.is_file(),
            detail=str(cfg.run_coupled_script),
        ),
        CheckItem(
            name="Scenario output root",
            ok=cfg.scenario_root.is_dir(),
            detail=str(cfg.scenario_root),
        ),
    ]

    missing = [check.name for check in checks if not check.ok]
    status = BridgeStatus(
        ready=not missing,
        project_root=str(cfg.pypsa_project_root),
        python=str(cfg.pypsa_python),
        scenario_root=str(cfg.scenario_root),
        checks=checks,
        missing=missing,
        solved_electricity_years=list_solved_electricity_years(cfg.scenario_root),
    )

    if deep and cfg.pypsa_python.is_file():
        status.solver_stack_ok, status.solver_stack_error = _check_solver_stack(cfg.pypsa_python)
        if not status.solver_stack_ok:
            status.ready = False
            status.missing.append("Solver stack imports")

    return status


def _check_solver_stack(python: Path) -> tuple[bool, str | None]:
    code = "import " + ", ".join(SOLVER_STACK_IMPORTS)
    try:
        completed = subprocess.run(
            [str(python), "-c", code],
            capture_output=True,
            text=True,
            timeout=DEEP_CHECK_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"{type(exc).__name__}: {exc}"

    if completed.returncode == 0:
        return True, None

    last_line = (completed.stderr.strip().splitlines() or ["import failed"])[-1]
    return False, last_line


def check_data() -> DataStatus:
    layers = [
        CheckItem(name=filename, ok=(SOURCE_DATA_DIR / filename).is_file(), detail=str(SOURCE_DATA_DIR / filename))
        for filename in REQUIRED_SOURCE_LAYERS
    ]
    layers.append(
        CheckItem(
            name="candidate_cells.geojson",
            ok=GENERATED_DATA_PATH.is_file(),
            detail=str(GENERATED_DATA_PATH),
        )
    )
    return DataStatus(ready=all(layer.ok for layer in layers), layers=layers)


def get_system_status(cfg: Settings = default_settings, deep: bool = False) -> SystemStatusResponse:
    return SystemStatusResponse(
        bridge=check_bridge(cfg, deep=deep),
        data=check_data(),
        cors_origins=list(cfg.cors_origins),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _mark(ok: bool) -> str:
    # ASCII only: the default Windows console code page cannot encode the
    # usual check/cross glyphs.
    return "[ok]" if ok else "[!!]"


def format_report(status: SystemStatusResponse) -> str:
    lines: list[str] = []

    lines.append(f"PyPSA bridge  {'READY' if status.bridge.ready else 'NOT READY (solving disabled)'}")
    for check in status.bridge.checks:
        lines.append(f"  {_mark(check.ok)} {check.name}: {check.detail}")
    if status.bridge.solver_stack_ok is not None:
        detail = "all importable" if status.bridge.solver_stack_ok else (status.bridge.solver_stack_error or "")
        lines.append(f"  {_mark(status.bridge.solver_stack_ok)} Solver stack ({', '.join(SOLVER_STACK_IMPORTS)}): {detail}")
    years = ", ".join(str(year) for year in status.bridge.solved_electricity_years) or "none"
    lines.append(f"  Solved electricity years: {years}")

    lines.append("")
    lines.append(f"Data layers   {'READY' if status.data.ready else 'INCOMPLETE'}")
    for layer in status.data.layers:
        lines.append(f"  {_mark(layer.ok)} {layer.name}")

    lines.append("")
    lines.append(f"CORS origins  {', '.join(status.cors_origins)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the API's data layers and PyPSA bridge.")
    parser.add_argument("--deep", action="store_true", help="also import the solver stack in the solver interpreter (slow)")
    parser.add_argument("--json", action="store_true", help="print the raw status as JSON")
    parser.add_argument("--strict", action="store_true", help="exit non-zero when the PyPSA bridge is not ready, too")
    args = parser.parse_args(argv)

    status = get_system_status(deep=args.deep)

    if args.json:
        print(status.model_dump_json(indent=2))
    else:
        print(format_report(status))

    if not status.data.ready:
        return 1
    if args.strict and not status.bridge.ready:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
