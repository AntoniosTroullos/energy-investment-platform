from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from .settings import settings

# ---------------------------------------------------------------------------
# Cross-repo bridge to the real solve/forecast infrastructure. That code lives
# in a sibling PyCharm project (a separate coding agent's work: ENTSO-E-driven
# demand forecasting, a PyPSA scenario-case builder, multi-year electricity
# solves) and is invoked here via subprocess, not reimplemented or imported
# in-process -- apps/api's own requirements.txt stays free of
# pandas/pypsa/linopy/highspy/xgboost, and the environment boundary is the
# isolation mechanism (see PYPSA_PYTHON below).
# ---------------------------------------------------------------------------

# Paths come from app/settings.py (env-overridable: PYPSA_PROJECT_ROOT,
# PYPSA_PYTHON). Kept as module-level names because callers and tests refer to
# them as scenario_runner.<NAME> (tests patch SCENARIO_ROOT with patch.object).
#
# Confirmed directly (2026-08-28): of four candidate environments on the
# original machine (pythonProject1/.venv, pythonProject1/.venv_new,
# pypsa-greece/.venv, pypsa-greece/.venv314) only .venv314 has
# pypsa+pandas+linopy+highspy+xgboost all importable together. That is why the
# default interpreter is pinned to it rather than discovered -- the others are
# silent traps that fail on unrelated ModuleNotFoundErrors deep inside a
# subprocess. `python -m app.system_status --deep` verifies the configured
# interpreter really can import the whole solver stack.
PYTHON_PROJECT_ROOT = settings.pypsa_project_root
PYPSA_GREECE_ROOT = settings.pypsa_greece_root
PYPSA_PYTHON = settings.pypsa_python

RUN_MULTIYEAR_SCRIPT = settings.run_multiyear_script
RUN_COUPLED_SCRIPT = settings.run_coupled_script
SCENARIO_ROOT = settings.scenario_root

RunState = Literal["not_found", "running", "crashed", "done"]


class ScenarioRunError(RuntimeError):
    pass


class ScenarioPreconditionError(ScenarioRunError):
    """Raised when a coupled solve is requested for a year whose electricity
    case hasn't been solved yet -- build_and_solve_coupled_year.py hard-fails
    (FileNotFoundError) in that situation, so this bridge checks first and
    fails with an actionable message instead of launching a doomed
    subprocess. Kept as a ScenarioRunError subclass so existing callers that
    only catch the base class still see it as a run failure."""


@dataclass(frozen=True)
class ScenarioStatus:
    state: RunState
    pid: int | None = None
    message: str | None = None


def electricity_case_name(target_year: int) -> str:
    return f"future_electricity_{target_year}"


def case_dir(case_name: str) -> Path:
    return SCENARIO_ROOT / case_name


def coupled_result_dir(
    case_name: str,
    chronological_storage: bool = False,
    linked_representative_periods: bool = False,
) -> Path:
    """build_and_solve_coupled_year.py writes into <case_dir>/coupled_outputs/
    -- a sibling of, not a replacement for, the electricity case's own
    scenario_result.json. Scoping the coupled marker/result inside this
    subdirectory (rather than case_dir() directly) means a coupled run's
    RUNNING.json can never collide with an electricity run's, even though
    both share the same case_name/case_dir.

    The two alternate storage-modeling flags change *where* that script
    writes its result, confirmed directly from run_coupled_year(): passing
    chronological_storage=True solves an entirely separate case directory
    (<case_name>_chronological), and linked_representative_periods=True uses
    a different subdirectory name within the same case dir. Both default to
    False so every existing caller (which never passes them) keeps resolving
    the one path this bridge has always used."""
    case_root = (
        case_dir(f"{case_name}_chronological") if chronological_storage else case_dir(case_name)
    )
    subdir = (
        "coupled_outputs_linked_representative_periods"
        if linked_representative_periods
        else "coupled_outputs"
    )
    return case_root / subdir


def _running_marker_path(case_name: str) -> Path:
    return case_dir(case_name) / "RUNNING.json"


def _result_path(case_name: str) -> Path:
    return case_dir(case_name) / "scenario_result.json"


def _coupled_running_marker_path(
    case_name: str,
    chronological_storage: bool = False,
    linked_representative_periods: bool = False,
) -> Path:
    return coupled_result_dir(case_name, chronological_storage, linked_representative_periods) / "RUNNING.json"


def _coupled_result_path(
    case_name: str,
    chronological_storage: bool = False,
    linked_representative_periods: bool = False,
) -> Path:
    return coupled_result_dir(case_name, chronological_storage, linked_representative_periods) / "scenario_result.json"


def _pid_is_alive(pid: int) -> bool:
    """Windows-specific liveness check (this dev environment is win32) --
    os.kill(pid, 0) is a POSIX liveness idiom that Windows does not support
    the same way, so this shells out to tasklist instead. A cross-platform
    deployment would swap this for psutil.pid_exists() (a new dependency,
    deliberately not added just for this one check)."""
    try:
        output = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return str(pid) in output.stdout
    except Exception:
        return False


def poll_status(case_name: str) -> ScenarioStatus:
    """Electricity case status. See _poll() for the marker/result race logic
    this delegates to."""
    return _poll(_running_marker_path(case_name), _result_path(case_name))


def poll_coupled_status(
    case_name: str,
    chronological_storage: bool = False,
    linked_representative_periods: bool = False,
) -> ScenarioStatus:
    """Coupled (gas/hydrogen/heat) case status -- same race-free logic as
    poll_status(), pointed at the storage-method-specific marker/result path."""
    return _poll(
        _coupled_running_marker_path(case_name, chronological_storage, linked_representative_periods),
        _coupled_result_path(case_name, chronological_storage, linked_representative_periods),
    )


def _poll(marker: Path, result: Path) -> ScenarioStatus:
    """The RUNNING.json marker (written before the subprocess launches,
    removed only after it exits -- see run_electricity_scenario /
    run_coupled_scenario) is checked BEFORE the result file, which resolves
    two real races at once: a poll right after a re-run starts won't read
    the previous run's now-stale result (marker still present -> reported as
    running), and a poll can never observe a partially-written result file
    (the upstream script finishes writing scenario_result.json before it
    exits, and the marker isn't removed until that exit is observed here)."""
    if marker.exists():
        try:
            marker_data = json.loads(marker.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return ScenarioStatus("running")  # marker mid-write

        pid = marker_data.get("pid")
        if pid is not None and not _pid_is_alive(pid):
            return ScenarioStatus(
                "crashed",
                pid=pid,
                message=(
                    "The solver process is no longer running but never finished writing a "
                    "result -- it likely crashed, was killed, or the API server restarted "
                    "mid-solve. Re-run the scenario."
                ),
            )
        return ScenarioStatus("running", pid=pid)

    if result.exists():
        return ScenarioStatus("done")

    return ScenarioStatus("not_found")


async def run_electricity_scenario(
    target_year: int,
    annual_growth_rate: float,
    force_fetch: bool = False,
) -> str:
    """Starts a real electricity scenario solve in the background via the
    real run_multiyear_electricity.py CLI. Returns the case name -- it also
    serves as the job id, since the case directory on disk IS the job's
    state (no separate job store)."""
    case_name = electricity_case_name(target_year)

    status = poll_status(case_name)
    if status.state == "running":
        raise ScenarioRunError(f"A solve for '{case_name}' is already running (PID {status.pid}).")

    marker = _running_marker_path(case_name)
    case_dir(case_name).mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps({"started_at_utc": datetime.now(timezone.utc).isoformat(), "target_year": target_year}),
        encoding="utf-8",
    )

    args = [
        str(PYPSA_PYTHON),
        str(RUN_MULTIYEAR_SCRIPT),
        "--years",
        str(target_year),
        "--annual-growth-rate",
        str(annual_growth_rate),
    ]
    if force_fetch:
        args.append("--force-fetch")

    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(PYTHON_PROJECT_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    # Record the real OS PID immediately (not after the process finishes) so
    # a poll arriving right after this call sees a live, checkable marker.
    marker.write_text(
        json.dumps(
            {
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "target_year": target_year,
                "pid": process.pid,
            }
        ),
        encoding="utf-8",
    )

    asyncio.create_task(_await_and_cleanup(process, marker, case_name))
    return case_name


async def run_coupled_scenario(
    target_year: int,
    h2_market_scenario: str,
    chronological_storage: bool = False,
    linked_representative_periods: bool = False,
) -> str:
    """Starts a real coupled gas/hydrogen/heat solve via
    build_and_solve_coupled_year.py, which layers onto an *already-solved*
    electricity case for the same year (it hard-fails with FileNotFoundError
    otherwise -- true for both alternate storage-modeling methods too, since
    the script checks the base case before branching on either flag).
    Checked here via poll_status() -- the same function that already tracks
    electricity-case status -- so a doomed subprocess is never launched in
    the first place."""
    case_name = electricity_case_name(target_year)

    electricity_status = poll_status(case_name)
    if electricity_status.state != "done":
        raise ScenarioPreconditionError(
            f"Electricity case for {target_year} must be solved first "
            f"(current state: {electricity_status.state})."
        )

    coupled_status = poll_coupled_status(case_name, chronological_storage, linked_representative_periods)
    if coupled_status.state == "running":
        raise ScenarioRunError(
            f"A coupled solve for '{case_name}' is already running (PID {coupled_status.pid})."
        )

    marker = _coupled_running_marker_path(case_name, chronological_storage, linked_representative_periods)
    coupled_result_dir(case_name, chronological_storage, linked_representative_periods).mkdir(
        parents=True, exist_ok=True
    )
    marker.write_text(
        json.dumps(
            {
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "target_year": target_year,
                "h2_market_scenario": h2_market_scenario,
            }
        ),
        encoding="utf-8",
    )

    args = [
        str(PYPSA_PYTHON),
        str(RUN_COUPLED_SCRIPT),
        "--year",
        str(target_year),
        "--h2-market-scenario",
        h2_market_scenario,
    ]
    if chronological_storage:
        args.append("--chronological-storage")
    if linked_representative_periods:
        args.append("--linked-representative-periods")

    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(PYTHON_PROJECT_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    marker.write_text(
        json.dumps(
            {
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "target_year": target_year,
                "h2_market_scenario": h2_market_scenario,
                "pid": process.pid,
            }
        ),
        encoding="utf-8",
    )

    asyncio.create_task(_await_and_cleanup(process, marker, case_name))
    return case_name


async def _await_and_cleanup(process: "asyncio.subprocess.Process", marker: Path, case_name: str) -> None:
    stdout, stderr = await process.communicate()
    marker.unlink(missing_ok=True)
    if process.returncode != 0:
        # No exception is raised here (nothing awaits this task) -- the
        # crashed state is surfaced to callers via poll_status the next time
        # they ask, per the module docstring. Logged for local debugging.
        print(
            f"[scenario_runner] '{case_name}' exited with code {process.returncode}.\n"
            f"stderr:\n{stderr.decode('utf-8', errors='replace')[-4000:]}"
        )


def get_result(case_name: str) -> dict:
    result = _result_path(case_name)
    if not result.exists():
        raise FileNotFoundError(f"No result found for '{case_name}'.")
    return json.loads(result.read_text(encoding="utf-8"))


def get_coupled_result(
    case_name: str,
    chronological_storage: bool = False,
    linked_representative_periods: bool = False,
) -> dict:
    result = _coupled_result_path(case_name, chronological_storage, linked_representative_periods)
    if not result.exists():
        raise FileNotFoundError(f"No coupled result found for '{case_name}'.")
    return json.loads(result.read_text(encoding="utf-8"))
