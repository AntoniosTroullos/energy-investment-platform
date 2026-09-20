from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.load_postprocess import (  # noqa: E402
    build_load_summaries,
    run_ipto_postprocessing,
    validate_model_ready,
)
from src.data.load_source_compare import (  # noqa: E402
    build_master_candidate,
    compare_ipto_kaggle_2022,
    load_kaggle_merge_ready,
)


PROCESSED_DIR = ROOT / "data" / "processed" / "national_load"
VALIDATION_DIR = ROOT / "data" / "validation" / "national_load"


DEFAULT_IPTO = PROCESSED_DIR / "ipto_system_load_hourly_2022_2026.csv"
DEFAULT_MISSING = VALIDATION_DIR / "ipto_system_load_missing_timestamps.csv"
DEFAULT_DUPLICATES = VALIDATION_DIR / "ipto_system_load_duplicate_timestamps.csv"
DEFAULT_OUTLIERS = VALIDATION_DIR / "ipto_system_load_outliers.csv"
DEFAULT_KAGGLE = PROCESSED_DIR / "kaggle_gr_load_hourly_2019_2022_merge_ready.csv"


def main() -> int:
    args = parse_args()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

    result = run_ipto_postprocessing(
        Path(args.ipto),
        Path(args.missing),
        Path(args.duplicates),
        Path(args.outliers),
        start_date=args.start_date,
        end_date=args.end_date,
    )

    observed_path = PROCESSED_DIR / "ipto_system_load_hourly_2022_2026_observed_flagged.csv"
    audit_path = VALIDATION_DIR / "ipto_anomaly_audit_2022_2026.csv"
    model_ready_path = PROCESSED_DIR / "ipto_system_load_hourly_2022_2026_model_ready.csv"
    monthly_path = PROCESSED_DIR / "ipto_system_load_monthly_summary_2022_2026_model_ready.csv"
    annual_path = PROCESSED_DIR / "ipto_system_load_annual_summary_2022_2026_model_ready.csv"

    result.observed_flagged.to_csv(observed_path, index=False)
    result.anomaly_audit.to_csv(audit_path, index=False)
    result.model_ready.to_csv(model_ready_path, index=False)
    result.monthly_summary.to_csv(monthly_path, index=False)
    result.annual_summary.to_csv(annual_path, index=False)

    validation = validate_model_ready(result.model_ready)
    validation_path = VALIDATION_DIR / "ipto_model_ready_validation_summary.csv"
    pd.DataFrame([validation]).to_csv(validation_path, index=False)
    if any(value for key, value in validation.items() if key != "rows"):
        raise RuntimeError(f"Model-ready validation failed: {validation}")

    kaggle, kaggle_status = load_kaggle_merge_ready(Path(args.kaggle))
    comparison, overlap_summary, decision = compare_ipto_kaggle_2022(result.model_ready, kaggle)
    comparison.to_csv(VALIDATION_DIR / "ipto_kaggle_overlap_comparison_2022.csv", index=False)
    overlap_summary.to_csv(VALIDATION_DIR / "ipto_kaggle_overlap_summary_2022.csv", index=False)
    decision["input_status"] = kaggle_status
    decision.to_csv(VALIDATION_DIR / "kaggle_usage_decision_report.csv", index=False)

    master = build_master_candidate(result.model_ready, kaggle, decision)
    master_path = PROCESSED_DIR / "national_load_hourly_master_2019_2026_candidate.csv"
    master_monthly_path = PROCESSED_DIR / "national_load_master_monthly_summary_2019_2026_candidate.csv"
    master_annual_path = PROCESSED_DIR / "national_load_master_annual_summary_2019_2026_candidate.csv"
    if master is not None:
        master.to_csv(master_path, index=False)
        master_monthly, master_annual = build_load_summaries(master, value_col="national_load_mw")
        master_monthly.to_csv(master_monthly_path, index=False)
        master_annual.to_csv(master_annual_path, index=False)
        master_status = f"created at {master_path.relative_to(ROOT)}"
    else:
        for path in [master_path, master_monthly_path, master_annual_path]:
            if path.exists():
                path.unlink()
        master_status = "not created because Kaggle decision rules did not allow auxiliary history"

    write_readme(
        observed_path,
        model_ready_path,
        comparison_path=VALIDATION_DIR / "ipto_kaggle_overlap_comparison_2022.csv",
        decision_path=VALIDATION_DIR / "kaggle_usage_decision_report.csv",
        master_status=master_status,
        kaggle_status=kaggle_status,
        validation=validation,
        decision=decision,
    )

    print(f"Observed flagged IPTO: {observed_path.relative_to(ROOT)} rows={len(result.observed_flagged)}")
    print(f"Anomaly audit: {audit_path.relative_to(ROOT)} rows={len(result.anomaly_audit)}")
    print(f"Model-ready IPTO: {model_ready_path.relative_to(ROOT)} rows={len(result.model_ready)}")
    print(f"Kaggle status: {kaggle_status}")
    print(f"Master candidate: {master_status}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Post-process IPTO/ADMIE national load and compare Kaggle auxiliary data.")
    parser.add_argument("--ipto", default=str(DEFAULT_IPTO))
    parser.add_argument("--missing", default=str(DEFAULT_MISSING))
    parser.add_argument("--duplicates", default=str(DEFAULT_DUPLICATES))
    parser.add_argument("--outliers", default=str(DEFAULT_OUTLIERS))
    parser.add_argument("--kaggle", default=str(DEFAULT_KAGGLE))
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default=None)
    return parser.parse_args()


def write_readme(
    observed_path: Path,
    model_ready_path: Path,
    *,
    comparison_path: Path,
    decision_path: Path,
    master_status: str,
    kaggle_status: str,
    validation: dict[str, int],
    decision: pd.DataFrame,
) -> None:
    decision_text = decision.iloc[0]["decision"] if not decision.empty else "not_safe_for_direct_merge"
    text = f"""# National Load Post-Processing

This layer audits and prepares the IPTO/ADMIE national System Load baseline for model use. It does not modify raw IPTO files and does not build regional allocation or forecasting.

## Source Roles

- Primary source for 2022-2026: IPTO/ADMIE `RealTimeSCADASystemLoad`.
- Auxiliary historical source: Kaggle Greece load dataset, only for 2019-2021 if 2022 overlap validation allows it.
- Kaggle input status: `{kaggle_status}`.

## Outputs

- Observed flagged IPTO file: `{observed_path.relative_to(ROOT).as_posix()}`
- Model-ready IPTO file: `{model_ready_path.relative_to(ROOT).as_posix()}`
- Anomaly audit: `data/validation/national_load/ipto_anomaly_audit_2022_2026.csv`
- IPTO vs Kaggle 2022 comparison: `{comparison_path.relative_to(ROOT).as_posix()}`
- Kaggle usage decision: `{decision_path.relative_to(ROOT).as_posix()}`
- Master candidate status: `{master_status}`

## Anomaly Handling

The observed flagged file preserves IPTO observed values and adds flags for missing timestamps, duplicates, negative values, zero values, outliers, and extreme jumps. Missing timestamps are represented as flagged rows with blank observed values.

The model-ready file creates a continuous hourly series. Repairs are documented row by row with `was_imputed`, `imputation_method`, `original_value`, `issue_type`, `source_priority`, and `notes`.

Imputation priority:

1. 2022 Kaggle matching timestamp only as fallback when available and still pending overlap validation.
2. Same hour previous week when available and positive.
3. Average of same hour previous and next day.
4. Short-gap linear interpolation.
5. Positive series median fallback only as a last resort.

Duplicate timestamps are resolved by keeping identical duplicates once or choosing the conflicting value closest to local consistency. Conflicting duplicates are not averaged.

Negative and zero load values are invalid for national system load and are repaired in the model-ready file. Outliers and jumps are kept unless they are non-positive or clearly inconsistent with adjacent hours.

## Validation

Model-ready validation summary:

- Rows: `{validation.get("rows", "")}`
- Missing timestamp rows: `{validation.get("missing_timestamp_rows", "")}`
- Duplicate timestamps: `{validation.get("duplicate_timestamps", "")}`
- Missing load values: `{validation.get("missing_load_values", "")}`
- Non-positive load values: `{validation.get("non_positive_load_values", "")}`

Kaggle decision: `{decision_text}`. IPTO/ADMIE remains primary for 2022-2026 regardless of this decision.

## Limitations

Kaggle is not a primary source and can only be used as auxiliary historical context after 2022 overlap validation. The IPTO System Load boundary still needs comparison with ENTSO-E Actual Total Load and national annual electricity-demand totals.

## Next Step

Proceed to regional/evidence-weighted spatial allocation only after source boundary validation and model-ready load acceptance.
"""
    (PROCESSED_DIR / "POSTPROCESSING_README.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
