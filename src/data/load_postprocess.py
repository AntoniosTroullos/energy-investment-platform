from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


TIMEZONE = "Europe/Athens"
SCOPE = "IPTO System Load - exact system boundary to be validated"


@dataclass(frozen=True)
class PostprocessResult:
    observed_flagged: pd.DataFrame
    anomaly_audit: pd.DataFrame
    model_ready: pd.DataFrame
    monthly_summary: pd.DataFrame
    annual_summary: pd.DataFrame


def run_ipto_postprocessing(
    ipto_path: Path,
    missing_path: Path,
    duplicate_path: Path,
    outlier_path: Path,
    *,
    start_date: str = "2022-01-01",
    end_date: str | None = None,
) -> PostprocessResult:
    ipto = _read_ipto(ipto_path)
    missing = _read_optional_csv(missing_path, ["timestamp"])
    duplicates = _read_optional_csv(duplicate_path, list(ipto.columns) + ["local_date", "year", "month"])
    outliers = _read_optional_csv(outlier_path, list(ipto.columns) + ["local_date", "year", "month", "hourly_jump_mw"])

    expected_index = _expected_index(ipto, missing, start_date=start_date, end_date=end_date)
    observed_flagged = build_observed_flagged(ipto, missing, duplicates, outliers, expected_index)
    anomaly_audit = build_anomaly_audit(observed_flagged, expected_index)
    model_ready = build_model_ready(ipto, missing, duplicates, outliers, expected_index)
    monthly, annual = build_load_summaries(model_ready, value_col="national_load_mw")
    return PostprocessResult(observed_flagged, anomaly_audit, model_ready, monthly, annual)


def build_observed_flagged(
    ipto: pd.DataFrame,
    missing: pd.DataFrame,
    duplicates: pd.DataFrame,
    outliers: pd.DataFrame,
    expected_index: pd.DatetimeIndex,
) -> pd.DataFrame:
    df = ipto.copy()
    df["timestamp_dt"] = _parse_ts(df["timestamp"])
    duplicate_ts = set(_parse_ts(duplicates["timestamp"]).dropna()) if "timestamp" in duplicates else set()
    outlier_ts = set(_parse_ts(outliers["timestamp"]).dropna()) if "timestamp" in outliers else set()
    missing_ts = set(_parse_ts(missing["timestamp"]).dropna()) if "timestamp" in missing else set()

    df["is_missing"] = False
    df["is_duplicate"] = df["timestamp_dt"].isin(duplicate_ts) | df["timestamp"].duplicated(keep=False)
    df["is_negative"] = df["national_load_mw"] < 0
    df["is_zero"] = df["national_load_mw"] == 0
    df["is_outlier"] = df["timestamp_dt"].isin(outlier_ts)
    df["is_extreme_jump"] = df["is_outlier"] & ~(df["is_negative"] | df["is_zero"] | (df["national_load_mw"] < 1000))
    df["issue_type"] = df.apply(_issue_type_for_observed_row, axis=1)
    df["recommended_action"] = df.apply(_recommended_action_for_observed_row, axis=1)
    df["notes"] = df.apply(_notes_for_observed_row, axis=1)

    missing_rows = []
    for ts in sorted(missing_ts):
        if ts in set(df["timestamp_dt"]):
            continue
        missing_rows.append(
            {
                "timestamp": _format_ts(ts),
                "national_load_mw": np.nan,
                "source": "IPTO/ADMIE",
                "timezone": TIMEZONE,
                "scope": SCOPE,
                "source_file": "",
                "file_category": "RealTimeSCADASystemLoad",
                "quality_flag": "missing timestamp from IPTO quality report",
                "is_missing": True,
                "is_duplicate": False,
                "is_negative": False,
                "is_zero": False,
                "is_outlier": False,
                "is_extreme_jump": False,
                "issue_type": "missing_timestamp",
                "recommended_action": "impute_for_model_ready_only",
                "notes": "No observed IPTO row exists for this timestamp.",
                "timestamp_dt": ts,
            }
        )
    if missing_rows:
        df = pd.concat([df, pd.DataFrame(missing_rows)], ignore_index=True)

    output_cols = [
        "timestamp",
        "national_load_mw",
        "source",
        "timezone",
        "scope",
        "source_file",
        "file_category",
        "quality_flag",
        "is_missing",
        "is_duplicate",
        "is_negative",
        "is_zero",
        "is_outlier",
        "is_extreme_jump",
        "issue_type",
        "recommended_action",
        "notes",
    ]
    return df.sort_values("timestamp_dt")[output_cols].reset_index(drop=True)


def build_anomaly_audit(observed_flagged: pd.DataFrame, expected_index: pd.DatetimeIndex) -> pd.DataFrame:
    df = observed_flagged.copy()
    df["timestamp_dt"] = _parse_ts(df["timestamp"])
    value_by_ts = (
        df.dropna(subset=["national_load_mw"])
        .sort_values(["timestamp_dt", "national_load_mw"])
        .groupby("timestamp_dt")["national_load_mw"]
        .first()
    )
    issue_rows = df[df["issue_type"] != "ok"].copy()
    rows: list[dict[str, Any]] = []
    for _, row in issue_rows.iterrows():
        ts = row["timestamp_dt"]
        previous_value = _neighbor_value(value_by_ts, ts, -1)
        next_value = _neighbor_value(value_by_ts, ts, 1)
        issue_type = str(row["issue_type"])
        rows.append(
            {
                "timestamp": row["timestamp"],
                "issue_type": issue_type,
                "observed_value": row["national_load_mw"],
                "previous_value": previous_value,
                "next_value": next_value,
                "source_file": row.get("source_file", ""),
                "possible_cause": _possible_cause(issue_type, row),
                "recommended_action": row["recommended_action"],
                "repair_priority": _repair_priority(issue_type),
            }
        )
    columns = [
        "timestamp",
        "issue_type",
        "observed_value",
        "previous_value",
        "next_value",
        "source_file",
        "possible_cause",
        "recommended_action",
        "repair_priority",
    ]
    return pd.DataFrame(rows, columns=columns)


def build_model_ready(
    ipto: pd.DataFrame,
    missing: pd.DataFrame,
    duplicates: pd.DataFrame,
    outliers: pd.DataFrame,
    expected_index: pd.DatetimeIndex,
    kaggle: pd.DataFrame | None = None,
) -> pd.DataFrame:
    duplicate_ts = set(_parse_ts(duplicates["timestamp"]).dropna()) if "timestamp" in duplicates else set()
    outlier_ts = set(_parse_ts(outliers["timestamp"]).dropna()) if "timestamp" in outliers else set()
    missing_ts = set(_parse_ts(missing["timestamp"]).dropna()) if "timestamp" in missing else set()

    working = ipto.copy()
    working["timestamp_dt"] = _parse_ts(working["timestamp"])
    resolved_rows = []
    for ts, group in working.groupby("timestamp_dt", dropna=True):
        resolved = _resolve_duplicate_group(ts, group, duplicate_ts)
        resolved_rows.append(resolved)
    resolved_df = pd.DataFrame(resolved_rows).set_index("timestamp_dt").sort_index()

    model = pd.DataFrame(index=expected_index)
    model.index.name = "timestamp_dt"
    for col in ["national_load_mw", "source", "timezone", "scope", "source_file", "quality_flag"]:
        model[col] = resolved_df[col] if col in resolved_df else np.nan
    model["was_imputed"] = False
    model["imputation_method"] = ""
    model["original_value"] = np.nan
    model["issue_type"] = ""
    model["source_priority"] = "ipto_primary_observed"
    model["notes"] = ""

    if "duplicate_issue_type" in resolved_df:
        duplicate_aligned = resolved_df.reindex(model.index)
        mask = duplicate_aligned["duplicate_issue_type"].fillna("") != ""
        model.loc[mask, "issue_type"] = duplicate_aligned.loc[mask, "duplicate_issue_type"]
        model.loc[mask, "quality_flag"] = _append_text(model.loc[mask, "quality_flag"], duplicate_aligned.loc[mask, "duplicate_issue_type"])
        model.loc[mask, "notes"] = duplicate_aligned.loc[mask, "duplicate_note"]

    missing_mask = model["national_load_mw"].isna()
    model.loc[missing_mask, "issue_type"] = "missing_timestamp"
    model.loc[missing_mask, "original_value"] = np.nan

    invalid_mask = (model["national_load_mw"] <= 0) & model["national_load_mw"].notna()
    model.loc[invalid_mask, "original_value"] = model.loc[invalid_mask, "national_load_mw"]
    model.loc[invalid_mask, "issue_type"] = "negative_or_zero_load"

    suspicious_low_mask = (model["national_load_mw"] > 0) & (model["national_load_mw"] < 1000)
    clear_jump_mask = pd.Series(False, index=model.index)
    for ts in sorted(outlier_ts):
        if ts in model.index and _is_clear_local_inconsistency(model, ts):
            clear_jump_mask.loc[ts] = True
    repair_mask = missing_mask | invalid_mask | clear_jump_mask
    model.loc[clear_jump_mask & (model["issue_type"] == ""), "original_value"] = model.loc[clear_jump_mask, "national_load_mw"]
    model.loc[clear_jump_mask & (model["issue_type"] == ""), "issue_type"] = "outlier_repaired_clear_local_inconsistency"

    kaggle_map = _kaggle_2022_map(kaggle) if kaggle is not None else {}
    for ts in model.index[repair_mask]:
        original = model.at[ts, "original_value"]
        value, method, priority, note = _choose_imputation_value(model["national_load_mw"], ts, kaggle_map)
        model.at[ts, "national_load_mw"] = value
        model.at[ts, "was_imputed"] = True
        model.at[ts, "imputation_method"] = method
        model.at[ts, "source_priority"] = priority
        model.at[ts, "quality_flag"] = _append_single(model.at[ts, "quality_flag"], "model_ready_imputed")
        model.at[ts, "notes"] = _append_single(model.at[ts, "notes"], note)
        if pd.notna(original):
            model.at[ts, "notes"] = _append_single(model.at[ts, "notes"], f"original_value={original}")

    keep_outlier_mask = pd.Series(model.index.isin(outlier_ts), index=model.index) & ~repair_mask
    keep_outlier_mask = keep_outlier_mask | suspicious_low_mask
    model.loc[keep_outlier_mask, "notes"] = _append_text(
        model.loc[keep_outlier_mask, "notes"],
        pd.Series("outlier kept because it is positive and not clearly inconsistent with adjacent hours", index=model.loc[keep_outlier_mask].index),
    )
    model.loc[keep_outlier_mask & (model["issue_type"] == ""), "issue_type"] = "outlier_kept_for_review"

    model["source"] = model["source"].fillna("IPTO/ADMIE")
    model["timezone"] = TIMEZONE
    model["scope"] = SCOPE
    model["quality_flag"] = model["quality_flag"].fillna("").replace("", "model_ready")
    model["timestamp"] = [_format_ts(ts) for ts in model.index]

    output = model.reset_index(drop=True)[
        [
            "timestamp",
            "national_load_mw",
            "source",
            "timezone",
            "scope",
            "quality_flag",
            "was_imputed",
            "imputation_method",
            "original_value",
            "issue_type",
            "source_priority",
            "notes",
        ]
    ]
    return output


def build_load_summaries(df: pd.DataFrame, *, value_col: str = "national_load_mw") -> tuple[pd.DataFrame, pd.DataFrame]:
    working = df.copy()
    working["timestamp_dt"] = _parse_ts(working["timestamp"])
    working["year"] = working["timestamp_dt"].dt.tz_convert(TIMEZONE).dt.year
    working["month"] = working["timestamp_dt"].dt.tz_convert(TIMEZONE).dt.month
    working["was_imputed"] = working.get("was_imputed", False)
    monthly = (
        working.groupby(["year", "month"])
        .agg(
            energy_mwh=(value_col, "sum"),
            average_load_mw=(value_col, "mean"),
            peak_load_mw=(value_col, "max"),
            min_load_mw=(value_col, "min"),
            hours_count=(value_col, "count"),
            imputed_hours_count=("was_imputed", "sum"),
        )
        .reset_index()
    )
    monthly["quality_flag"] = np.where(monthly["imputed_hours_count"] > 0, "contains_imputed_rows", "ok")
    annual = (
        working.groupby(["year"])
        .agg(
            energy_mwh=(value_col, "sum"),
            average_load_mw=(value_col, "mean"),
            peak_load_mw=(value_col, "max"),
            min_load_mw=(value_col, "min"),
            hours_count=(value_col, "count"),
            imputed_hours_count=("was_imputed", "sum"),
        )
        .reset_index()
    )
    annual["quality_flag"] = np.where(annual["imputed_hours_count"] > 0, "contains_imputed_rows", "ok")
    return monthly, annual


def validate_model_ready(df: pd.DataFrame) -> dict[str, int]:
    parsed = _parse_ts(df["timestamp"])
    return {
        "rows": len(df),
        "missing_timestamp_rows": int(parsed.isna().sum()),
        "duplicate_timestamps": int(df["timestamp"].duplicated().sum()),
        "missing_load_values": int(df["national_load_mw"].isna().sum()),
        "non_positive_load_values": int((df["national_load_mw"] <= 0).sum()),
    }


def _read_ipto(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"timestamp", "national_load_mw", "source", "timezone", "scope", "source_file", "file_category", "quality_flag"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"{path} is missing required columns: {sorted(missing)}")
    return df


def _read_optional_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=columns)
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=columns)


def _expected_index(ipto: pd.DataFrame, missing: pd.DataFrame, *, start_date: str, end_date: str | None) -> pd.DatetimeIndex:
    ipto_ts = _parse_ts(ipto["timestamp"]).dropna()
    missing_ts = _parse_ts(missing["timestamp"]).dropna() if "timestamp" in missing else pd.Series(dtype="datetime64[ns, UTC]")
    start = pd.Timestamp(start_date, tz=TIMEZONE)
    if end_date:
        end = pd.Timestamp(end_date, tz=TIMEZONE) + pd.Timedelta(hours=23)
    elif not missing_ts.empty:
        end = max(ipto_ts.max(), missing_ts.max()).tz_convert(TIMEZONE)
    else:
        end = ipto_ts.max().tz_convert(TIMEZONE)
    return pd.date_range(start=start, end=end, freq="h").tz_convert("UTC")


def _parse_ts(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def _format_ts(ts: pd.Timestamp) -> str:
    return pd.Timestamp(ts).tz_convert(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S%z")


def _issue_type_for_observed_row(row: pd.Series) -> str:
    issues = []
    if row["is_missing"]:
        issues.append("missing_timestamp")
    if row["is_duplicate"]:
        issues.append("duplicate_timestamp")
    if row["is_negative"]:
        issues.append("negative_load")
    if row["is_zero"]:
        issues.append("zero_load")
    if row["is_extreme_jump"]:
        issues.append("extreme_jump_or_outlier")
    elif row["is_outlier"]:
        issues.append("outlier")
    return ";".join(issues) if issues else "ok"


def _recommended_action_for_observed_row(row: pd.Series) -> str:
    issue = row["issue_type"]
    if issue == "ok":
        return "keep_observed_value"
    if "negative" in issue or "zero" in issue or "missing" in issue:
        return "repair_in_model_ready_only"
    if "duplicate" in issue:
        return "resolve_duplicate_in_model_ready_only"
    return "review_before_repair; keep_if_plausible"


def _notes_for_observed_row(row: pd.Series) -> str:
    if row["issue_type"] == "ok":
        return "Observed IPTO value preserved."
    return "Observed IPTO value preserved in flagged file; any repair happens only in model-ready output."


def _possible_cause(issue_type: str, row: pd.Series) -> str:
    if "missing_timestamp" in issue_type and "03:00:00" in str(row["timestamp"]):
        return "DST/timestamp handling"
    if "missing_timestamp" in issue_type:
        return "missing source file row"
    if "duplicate" in issue_type and "duplicate timestamps detected" in str(row.get("quality_flag", "")):
        return "DST/timestamp handling"
    if "duplicate" in issue_type:
        return "duplicate source file/version"
    if "negative" in issue_type or "zero" in issue_type:
        return "malformed source value"
    if "outlier" in issue_type or "jump" in issue_type:
        return "SCADA/source anomaly"
    return "unknown"


def _repair_priority(issue_type: str) -> str:
    if "missing" in issue_type or "negative" in issue_type or "zero" in issue_type:
        return "high"
    if "duplicate" in issue_type:
        return "medium"
    return "review"


def _neighbor_value(values: pd.Series, ts: pd.Timestamp, direction: int) -> float:
    if pd.isna(ts):
        return np.nan
    idx = values.index.sort_values()
    if direction < 0:
        candidates = idx[idx < ts]
        key = candidates.max() if len(candidates) else None
    else:
        candidates = idx[idx > ts]
        key = candidates.min() if len(candidates) else None
    if key is None:
        return np.nan
    return float(values.loc[key])


def _resolve_duplicate_group(ts: pd.Timestamp, group: pd.DataFrame, duplicate_ts: set[pd.Timestamp]) -> dict[str, Any]:
    group = group.copy()
    values = group["national_load_mw"].astype(float)
    row = group.iloc[0].to_dict()
    row["timestamp_dt"] = ts
    row["duplicate_issue_type"] = ""
    row["duplicate_note"] = ""
    if ts not in duplicate_ts and len(group) == 1:
        return row
    if values.nunique(dropna=False) == 1:
        row["duplicate_issue_type"] = "duplicate_resolved_identical"
        row["duplicate_note"] = "Duplicate timestamp had identical values; one row retained."
        return row
    previous_hint = group["national_load_mw"].shift(1)
    next_hint = group["national_load_mw"].shift(-1)
    target = pd.concat([previous_hint, next_hint]).dropna().mean()
    if pd.isna(target):
        target = values.median()
    best_idx = (values - target).abs().idxmin()
    row = group.loc[best_idx].to_dict()
    row["timestamp_dt"] = ts
    row["duplicate_issue_type"] = "duplicate_resolved_by_local_consistency"
    row["duplicate_note"] = f"Conflicting duplicate values {values.tolist()} resolved by closest local pattern candidate."
    return row


def _is_clear_local_inconsistency(model: pd.DataFrame, ts: pd.Timestamp) -> bool:
    value = model.at[ts, "national_load_mw"] if ts in model.index else np.nan
    if pd.isna(value):
        return False
    if value <= 0:
        return True
    if value < 1000:
        prev_val = _series_at(model["national_load_mw"], ts - pd.Timedelta(hours=1))
        next_val = _series_at(model["national_load_mw"], ts + pd.Timedelta(hours=1))
        neighbor_mean = np.nanmean([prev_val, next_val])
        return pd.notna(neighbor_mean) and neighbor_mean > 2500
    prev_val = _series_at(model["national_load_mw"], ts - pd.Timedelta(hours=1))
    next_val = _series_at(model["national_load_mw"], ts + pd.Timedelta(hours=1))
    if pd.isna(prev_val) or pd.isna(next_val):
        return False
    neighbor_mean = (prev_val + next_val) / 2
    return abs(value - neighbor_mean) > 3500 and abs(prev_val - next_val) < 1500


def _choose_imputation_value(series: pd.Series, ts: pd.Timestamp, kaggle_map: dict[pd.Timestamp, float]) -> tuple[float, str, str, str]:
    if ts.year == 2022 and ts in kaggle_map and pd.notna(kaggle_map[ts]) and kaggle_map[ts] > 0:
        return (
            float(kaggle_map[ts]),
            "kaggle_matching_timestamp_fallback",
            "kaggle_fallback_after_overlap_validation_pending",
            "Used Kaggle only as 2022 fallback candidate pending overlap validation.",
        )
    prev_week = _series_at(series, ts - pd.Timedelta(days=7))
    if pd.notna(prev_week) and prev_week > 0:
        return float(prev_week), "same_hour_previous_week", "ipto_model_imputed", "Used same hour previous week."
    prev_day = _series_at(series, ts - pd.Timedelta(days=1))
    next_day = _series_at(series, ts + pd.Timedelta(days=1))
    if pd.notna(prev_day) and pd.notna(next_day) and prev_day > 0 and next_day > 0:
        return float((prev_day + next_day) / 2), "average_same_hour_previous_next_day", "ipto_model_imputed", "Used average of same hour previous and next day."
    interpolated = series.replace({0: np.nan}).where(series > 0).interpolate(limit=3, limit_direction="both")
    interp_value = _series_at(interpolated, ts)
    if pd.notna(interp_value) and interp_value > 0:
        return float(interp_value), "short_gap_linear_interpolation", "ipto_model_imputed", "Used short-gap linear interpolation."
    fallback = series[series > 0].median()
    return float(fallback), "positive_series_median_fallback", "ipto_model_imputed", "Used positive series median as last-resort fallback."


def _series_at(series: pd.Series, ts: pd.Timestamp) -> float:
    if ts in series.index:
        return series.loc[ts]
    return np.nan


def _kaggle_2022_map(kaggle: pd.DataFrame) -> dict[pd.Timestamp, float]:
    if kaggle is None or kaggle.empty:
        return {}
    working = kaggle.copy()
    working["timestamp_dt"] = _parse_ts(working["timestamp"])
    working = working[working["timestamp_dt"].dt.year == 2022]
    return dict(zip(working["timestamp_dt"], working["national_load_mw"]))


def _append_single(existing: Any, addition: str) -> str:
    existing_text = "" if pd.isna(existing) else str(existing)
    if not existing_text:
        return addition
    if addition in existing_text:
        return existing_text
    return f"{existing_text}; {addition}"


def _append_text(existing: pd.Series, additions: pd.Series) -> pd.Series:
    return pd.Series([_append_single(left, right) for left, right in zip(existing, additions)], index=existing.index)
