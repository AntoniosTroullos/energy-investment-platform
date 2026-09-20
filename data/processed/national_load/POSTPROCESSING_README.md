# National Load Post-Processing

This layer audits and prepares the IPTO/ADMIE national System Load baseline for model use. It does not modify raw IPTO files and does not build regional allocation or forecasting.

## Source Roles

- Primary source for 2022-2026: IPTO/ADMIE `RealTimeSCADASystemLoad`.
- Auxiliary historical source: Kaggle Greece load dataset, only for 2019-2021 if 2022 overlap validation allows it.
- Kaggle input status: `Kaggle auxiliary file not found: C:\Users\megas\dev\energy-investment-platform\data\processed\national_load\kaggle_gr_load_hourly_2019_2022_merge_ready.csv`.

## Outputs

- Observed flagged IPTO file: `data/processed/national_load/ipto_system_load_hourly_2022_2026_observed_flagged.csv`
- Model-ready IPTO file: `data/processed/national_load/ipto_system_load_hourly_2022_2026_model_ready.csv`
- Anomaly audit: `data/validation/national_load/ipto_anomaly_audit_2022_2026.csv`
- IPTO vs Kaggle 2022 comparison: `data/validation/national_load/ipto_kaggle_overlap_comparison_2022.csv`
- Kaggle usage decision: `data/validation/national_load/kaggle_usage_decision_report.csv`
- Master candidate status: `not created because Kaggle decision rules did not allow auxiliary history`

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

- Rows: `39359`
- Missing timestamp rows: `0`
- Duplicate timestamps: `0`
- Missing load values: `0`
- Non-positive load values: `0`

Kaggle decision: `not_safe_for_direct_merge`. IPTO/ADMIE remains primary for 2022-2026 regardless of this decision.

## Limitations

Kaggle is not a primary source and can only be used as auxiliary historical context after 2022 overlap validation. The IPTO System Load boundary still needs comparison with ENTSO-E Actual Total Load and national annual electricity-demand totals.

## Next Step

Proceed to regional/evidence-weighted spatial allocation only after source boundary validation and model-ready load acceptance.
