from __future__ import annotations

from ..scenario_models import (
    CoupledScenarioResult,
    ElectricityScenarioParameters,
    ElectricityScenarioResult,
    ScenarioMetrics,
)


def normalize_electricity_result(
    case_name: str,
    raw: dict,
    *,
    solved_at_utc: str | None = None,
) -> ElectricityScenarioResult:
    """The single place a raw scenario_result.json (written by
    pythonProject1/scripts/run_multiyear_electricity.py -- code this repo
    doesn't own and doesn't control the shape of) gets mapped into this
    API's response models. Keep all raw-dict key access here, nowhere else,
    so a future upstream rename or addition needs exactly one edit.

    solved_at_utc is not in that raw JSON at all -- the upstream script never
    timestamps its own output -- so callers with filesystem access pass in the
    result file's mtime instead (scenarios.py); a caller working from a
    fixture or an in-memory dict (tests) can leave it out."""
    metrics_raw = raw.get("metrics") or {}
    request_raw = raw.get("request")
    return ElectricityScenarioResult(
        case_name=case_name,
        target_year=_extract_target_year(case_name, raw),
        solved=bool(raw.get("solved", False)),
        message=str(raw.get("message", "")),
        objective_eur=raw.get("objective"),
        metrics=ScenarioMetrics(**metrics_raw),
        parameters=ElectricityScenarioParameters(**request_raw) if isinstance(request_raw, dict) else None,
        solved_at_utc=solved_at_utc,
    )


def normalize_coupled_result(case_name: str, raw: dict) -> CoupledScenarioResult:
    """The single place a raw coupled_outputs/scenario_result.json (written
    by pythonProject1/scripts/build_and_solve_coupled_year.py -- confirmed
    mid-edit/uncommitted upstream) gets mapped into this API's response
    models. Unlike normalize_electricity_result, the raw top-level keys here
    already match CoupledScenarioResult's field names 1:1 (year, solved,
    message, objective_eur_per_year, ...), so this is close to a direct
    spread -- case_name just needs injecting since the raw JSON doesn't carry
    it (it's derived from the case directory, not written by the script)."""
    return CoupledScenarioResult(case_name=case_name, **raw)


def _extract_target_year(case_name: str, raw: dict) -> int:
    request_data = raw.get("request")
    if isinstance(request_data, dict) and request_data.get("target_year"):
        return int(request_data["target_year"])

    # Fallback: case names from scenario_runner.electricity_case_name() follow
    # "future_electricity_{year}" -- parse it out rather than fail outright if
    # the upstream request-echo shape ever changes.
    digits = "".join(ch for ch in case_name if ch.isdigit())
    return int(digits) if digits else 0
