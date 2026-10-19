"""Environment-driven configuration for the API.

Everything that used to be a hard-coded, machine-specific absolute path (the
sibling PyPSA project and the one virtualenv that can import its solver stack)
is resolved here instead, so a different machine or checkout location is a
one-line env override rather than a source edit.

The defaults reproduce the previous hard-coded values on this machine, so
nothing changes unless an override is set:

    PYPSA_PROJECT_ROOT   root of the sibling project that owns the scenario
                         scripts (default: ~/PycharmProjects/pythonProject1)
    PYPSA_PYTHON         interpreter used to run those scripts (default: the
                         .venv314 inside <root>/pypsa-greece -- the only one of
                         that project's environments that has pypsa, pandas,
                         linopy, highspy and xgboost all importable together)
    API_CORS_ORIGINS     comma-separated browser origins allowed to call the API
                         (default: the local Next.js dev server on :3000)

On a machine without the sibling project (e.g. a deployed server), scenario
results fall back to the read-only snapshot bundled at
apps/api/data/processed/pypsa_scenarios. That snapshot has no live solver
behind it, so routes that trigger a new solve still fail there -- only
previously-computed results are servable from it.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

ENV_PYPSA_PROJECT_ROOT = "PYPSA_PROJECT_ROOT"
ENV_PYPSA_PYTHON = "PYPSA_PYTHON"
ENV_CORS_ORIGINS = "API_CORS_ORIGINS"

DEFAULT_CORS_ORIGINS: tuple[str, ...] = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)

# Interpreter location differs between Windows and POSIX virtualenvs.
_VENV_PYTHON_RELATIVE = Path("Scripts") / "python.exe" if sys.platform == "win32" else Path("bin") / "python"


@dataclass(frozen=True)
class Settings:
    pypsa_project_root: Path
    pypsa_greece_root: Path
    pypsa_python: Path
    run_multiyear_script: Path
    run_coupled_script: Path
    scenario_root: Path
    cors_origins: tuple[str, ...]


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Builds Settings from an environment mapping (os.environ by default).
    Taking the mapping as a parameter keeps this a pure function, so tests can
    exercise every override without touching the real environment."""
    env = os.environ if environ is None else environ

    project_root = _path_from_env(env, ENV_PYPSA_PROJECT_ROOT) or (
        Path.home() / "PycharmProjects" / "pythonProject1"
    )
    pypsa_greece_root = project_root / "pypsa-greece"
    pypsa_python = _path_from_env(env, ENV_PYPSA_PYTHON) or (
        pypsa_greece_root / ".venv314" / _VENV_PYTHON_RELATIVE
    )

    scenario_root = project_root / "data" / "processed" / "pypsa_scenarios"
    if not scenario_root.exists():
        bundled_scenario_root = Path(__file__).resolve().parent.parent / "data" / "processed" / "pypsa_scenarios"
        if bundled_scenario_root.exists():
            scenario_root = bundled_scenario_root

    return Settings(
        pypsa_project_root=project_root,
        pypsa_greece_root=pypsa_greece_root,
        pypsa_python=pypsa_python,
        run_multiyear_script=project_root / "scripts" / "run_multiyear_electricity.py",
        run_coupled_script=project_root / "scripts" / "build_and_solve_coupled_year.py",
        scenario_root=scenario_root,
        cors_origins=_parse_origins(env.get(ENV_CORS_ORIGINS)),
    )


def _path_from_env(env: Mapping[str, str], name: str) -> Path | None:
    value = env.get(name, "").strip()
    return Path(value).expanduser() if value else None


def _parse_origins(raw: str | None) -> tuple[str, ...]:
    if not raw or not raw.strip():
        return DEFAULT_CORS_ORIGINS

    origins = tuple(origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip())
    return origins or DEFAULT_CORS_ORIGINS


settings = load_settings()
