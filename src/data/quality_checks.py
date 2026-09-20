from __future__ import annotations

from pathlib import Path
from datetime import timedelta

import pandas as pd


def run_quality_checks(
    final_df: pd.DataFrame,
    validation_dir: Path,
    *,
    start_date: str,
    effective_end_date: str,
) -> dict[str, pd.DataFrame]:
    validation_dir.mkdir(parents=True, exist_ok=True)
    df = final_df.copy()
    df["timestamp_dt"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df["local_date"] = df["timestamp_dt"].dt.tz_convert("Europe/Athens").dt.date
    df["year"] = df["timestamp_dt"].dt.tz_convert("Europe/Athens").dt.year
    df["month"] = df["timestamp_dt"].dt.tz_convert("Europe/Athens").dt.month

    expected = pd.date_range(
        start=pd.Timestamp(start_date, tz="Europe/Athens"),
        end=pd.Timestamp(effective_end_date, tz="Europe/Athens") + pd.Timedelta(hours=23),
        freq="h",
    )
    actual_index = pd.DatetimeIndex(df["timestamp_dt"].dropna()).tz_convert("Europe/Athens")
    missing = pd.DataFrame({"timestamp": expected.difference(actual_index).strftime("%Y-%m-%d %H:%M:%S%z")})

    duplicates = df[df["timestamp"].duplicated(keep=False)].drop(columns=["timestamp_dt"])
    outliers = df[
        (df["national_load_mw"] < 1000)
        | (df["national_load_mw"] > 15000)
        | (df["national_load_mw"] <= 0)
    ].drop(columns=["timestamp_dt"])

    sorted_df = df.sort_values("timestamp_dt")
    sorted_df["hourly_jump_mw"] = sorted_df["national_load_mw"].diff().abs()
    jumps = sorted_df[sorted_df["hourly_jump_mw"] > 3000].drop(columns=["timestamp_dt"])
    if not jumps.empty:
        outliers = pd.concat([outliers, jumps], ignore_index=True).drop_duplicates()

    daily = df.groupby("local_date").agg(
        hours_count=("timestamp", "count"),
        min_load_mw=("national_load_mw", "min"),
        max_load_mw=("national_load_mw", "max"),
    ).reset_index()
    daily_expected = pd.DataFrame({"local_date": pd.date_range(start_date, effective_end_date, freq="D").date})
    daily = daily_expected.merge(daily, on="local_date", how="left").fillna({"hours_count": 0})
    daily["expected_hours_count"] = daily["local_date"].map(_expected_hours_for_local_date)
    daily["missing_hours_count"] = (daily["expected_hours_count"] - daily["hours_count"]).clip(lower=0)
    daily["quality_flag"] = daily["missing_hours_count"].map(lambda value: "ok" if value == 0 else "incomplete_day")

    monthly = _summary(df, ["year", "month"], expected, ["year", "month"])
    annual = _summary(df, ["year"], expected, ["year"])

    quality_rows = [
        ("rows", len(df), "info"),
        ("start_timestamp", df["timestamp"].min() if not df.empty else "", "info"),
        ("end_timestamp", df["timestamp"].max() if not df.empty else "", "info"),
        ("missing_timestamps", len(missing), "warning" if len(missing) else "ok"),
        ("duplicate_timestamps", len(duplicates), "warning" if len(duplicates) else "ok"),
        ("outlier_or_extreme_jump_rows", len(outliers), "warning" if len(outliers) else "ok"),
        ("negative_load_rows", int((df["national_load_mw"] < 0).sum()), "error" if (df["national_load_mw"] < 0).any() else "ok"),
        ("zero_load_rows", int((df["national_load_mw"] == 0).sum()), "warning" if (df["national_load_mw"] == 0).any() else "ok"),
        ("non_hourly_or_missing_frequency", len(missing), "warning" if len(missing) else "ok"),
        ("incomplete_current_year_handling", effective_end_date, "info"),
    ]
    quality_report = pd.DataFrame(quality_rows, columns=["check", "value", "severity"])

    outputs = {
        "quality_report": quality_report,
        "missing_timestamps": missing,
        "duplicate_timestamps": duplicates,
        "outliers": outliers,
        "daily_completeness": daily,
        "monthly_summary": monthly,
        "annual_summary": annual,
    }
    outputs["quality_report"].to_csv(validation_dir / "ipto_system_load_quality_report.csv", index=False)
    outputs["missing_timestamps"].to_csv(validation_dir / "ipto_system_load_missing_timestamps.csv", index=False)
    outputs["duplicate_timestamps"].to_csv(validation_dir / "ipto_system_load_duplicate_timestamps.csv", index=False)
    outputs["outliers"].to_csv(validation_dir / "ipto_system_load_outliers.csv", index=False)
    outputs["daily_completeness"].to_csv(validation_dir / "ipto_system_load_daily_completeness.csv", index=False)
    outputs["monthly_summary"].to_csv(validation_dir / "ipto_system_load_monthly_summary.csv", index=False)
    return outputs


def build_processed_summaries(final_df: pd.DataFrame, start_date: str, effective_end_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = final_df.copy()
    df["timestamp_dt"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True).dt.tz_convert("Europe/Athens")
    df["year"] = df["timestamp_dt"].dt.year
    df["month"] = df["timestamp_dt"].dt.month
    expected = pd.date_range(
        start=pd.Timestamp(start_date, tz="Europe/Athens"),
        end=pd.Timestamp(effective_end_date, tz="Europe/Athens") + pd.Timedelta(hours=23),
        freq="h",
    )
    return _summary(df, ["year", "month"], expected, ["year", "month"]), _summary(df, ["year"], expected, ["year"])


def _summary(df: pd.DataFrame, group_cols: list[str], expected: pd.DatetimeIndex, expected_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=group_cols + ["energy_mwh", "average_load_mw", "peak_load_mw", "min_load_mw", "hours_count", "missing_hours_count", "quality_flag"])
    summary = df.groupby(group_cols).agg(
        energy_mwh=("national_load_mw", "sum"),
        average_load_mw=("national_load_mw", "mean"),
        peak_load_mw=("national_load_mw", "max"),
        min_load_mw=("national_load_mw", "min"),
        hours_count=("timestamp", "count"),
    ).reset_index()
    expected_frame = pd.DataFrame({"timestamp": expected})
    expected_frame["year"] = expected_frame["timestamp"].dt.year
    expected_frame["month"] = expected_frame["timestamp"].dt.month
    expected_counts = expected_frame.groupby(expected_cols).size().reset_index(name="expected_hours_count")
    summary = summary.merge(expected_counts, on=expected_cols, how="left")
    summary["missing_hours_count"] = (summary["expected_hours_count"] - summary["hours_count"]).clip(lower=0)
    summary["quality_flag"] = summary["missing_hours_count"].map(lambda value: "ok" if value == 0 else "incomplete_period")
    return summary.drop(columns=["expected_hours_count"]).sort_values(group_cols).reset_index(drop=True)


def _expected_hours_for_local_date(value: object) -> int:
    start = pd.Timestamp(value, tz="Europe/Athens")
    end = pd.Timestamp(start.date() + timedelta(days=1), tz="Europe/Athens")
    return len(pd.date_range(start=start, end=end, freq="h", inclusive="left"))
