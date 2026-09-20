from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


TIMEZONE = "Europe/Athens"


def load_kaggle_merge_ready(path: Path) -> tuple[pd.DataFrame | None, str]:
    if not path.exists():
        return None, f"Kaggle auxiliary file not found: {path}"
    try:
        raw = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return None, f"Kaggle auxiliary file is empty: {path}"

    timestamp_col = _find_column(raw, ["timestamp", "datetime", "date_time", "date"])
    load_col = _find_column(raw, ["national_load_mw", "load_mw", "load", "actual_load", "value", "mw"])
    if not timestamp_col or not load_col:
        return None, f"Kaggle file could not be normalized; columns={list(raw.columns)}"

    normalized = pd.DataFrame(
        {
            "timestamp": raw[timestamp_col],
            "national_load_mw": pd.to_numeric(raw[load_col], errors="coerce"),
            "source": raw["source"] if "source" in raw.columns else "Kaggle auxiliary Greece load",
            "timezone": raw["timezone"] if "timezone" in raw.columns else TIMEZONE,
            "scope": raw["scope"] if "scope" in raw.columns else "Kaggle auxiliary historical Greece load - boundary to be validated",
        }
    )
    normalized["timestamp_dt"] = pd.to_datetime(normalized["timestamp"], errors="coerce", utc=True)
    normalized = normalized.dropna(subset=["timestamp_dt", "national_load_mw"])
    normalized["timestamp"] = normalized["timestamp_dt"].dt.tz_convert(TIMEZONE).dt.strftime("%Y-%m-%d %H:%M:%S%z")
    return normalized, "loaded"


def compare_ipto_kaggle_2022(ipto: pd.DataFrame, kaggle: pd.DataFrame | None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if kaggle is None or kaggle.empty:
        comparison = pd.DataFrame(
            columns=[
                "timestamp",
                "ipto_load_mw",
                "kaggle_load_mw",
                "difference_mw",
                "absolute_difference_mw",
                "percentage_difference",
                "comparison_flag",
            ]
        )
        summary = _summary_frame(
            {
                "overlapping_hours_count": 0,
                "missing_in_ipto_count": np.nan,
                "missing_in_kaggle_count": np.nan,
                "correlation": np.nan,
                "MAE": np.nan,
                "RMSE": np.nan,
                "MAPE": np.nan,
                "mean_bias_mw": np.nan,
                "mean_bias_percent": np.nan,
                "monthly_energy_mwh_ipto": np.nan,
                "monthly_energy_mwh_kaggle": np.nan,
                "monthly_difference_mwh": np.nan,
                "monthly_difference_percent": np.nan,
                "annual_energy_mwh_ipto": np.nan,
                "annual_energy_mwh_kaggle": np.nan,
                "annual_difference_percent": np.nan,
                "peak_load_ipto_mw": np.nan,
                "peak_load_kaggle_mw": np.nan,
                "peak_load_difference_percent": np.nan,
            }
        )
        decision = decision_report(summary, reason="Kaggle auxiliary file unavailable or empty.")
        return comparison, summary, decision

    ipto_2022 = _normalize_for_compare(ipto, "ipto_load_mw")
    kaggle_2022 = _normalize_for_compare(kaggle, "kaggle_load_mw")
    ipto_2022 = ipto_2022[ipto_2022["timestamp_dt"].dt.year == 2022]
    kaggle_2022 = kaggle_2022[kaggle_2022["timestamp_dt"].dt.year == 2022]

    merged = ipto_2022.merge(kaggle_2022, on="timestamp_dt", how="inner")
    comparison = pd.DataFrame(
        {
            "timestamp": merged["timestamp_dt"].dt.tz_convert(TIMEZONE).dt.strftime("%Y-%m-%d %H:%M:%S%z"),
            "ipto_load_mw": merged["ipto_load_mw"],
            "kaggle_load_mw": merged["kaggle_load_mw"],
        }
    )
    comparison["difference_mw"] = comparison["ipto_load_mw"] - comparison["kaggle_load_mw"]
    comparison["absolute_difference_mw"] = comparison["difference_mw"].abs()
    comparison["percentage_difference"] = np.where(
        comparison["kaggle_load_mw"] != 0,
        comparison["difference_mw"] / comparison["kaggle_load_mw"] * 100,
        np.nan,
    )
    comparison["comparison_flag"] = comparison["percentage_difference"].abs().map(_comparison_flag)

    full_2022 = pd.date_range(
        start=pd.Timestamp("2022-01-01", tz=TIMEZONE),
        end=pd.Timestamp("2022-12-31 23:00:00", tz=TIMEZONE),
        freq="h",
    ).tz_convert("UTC")
    missing_in_ipto = len(full_2022.difference(pd.DatetimeIndex(ipto_2022["timestamp_dt"])))
    missing_in_kaggle = len(full_2022.difference(pd.DatetimeIndex(kaggle_2022["timestamp_dt"])))

    summary = _build_overlap_summary(comparison, missing_in_ipto, missing_in_kaggle)
    decision = decision_report(summary)
    return comparison, summary, decision


def decision_report(summary: pd.DataFrame, reason: str = "") -> pd.DataFrame:
    if summary.empty:
        decision = "not_safe_for_direct_merge"
        reason = reason or "No overlap summary available."
    else:
        row = summary.iloc[0]
        mape = row.get("MAPE", np.nan)
        annual_diff = abs(row.get("annual_difference_percent", np.nan))
        corr = row.get("correlation", np.nan)
        bias = abs(row.get("mean_bias_percent", np.nan))
        if pd.notna(mape) and pd.notna(annual_diff) and mape <= 2 and annual_diff <= 2:
            decision = "usable_as_auxiliary_history_without_scaling"
            reason = "2022 overlap MAPE and annual energy difference are within 2%."
        elif pd.notna(mape) and mape <= 5 and pd.notna(corr) and corr >= 0.85:
            decision = "usable_after_scaling_correction"
            reason = f"2022 overlap MAPE is <=5% with systematic bias around {bias:.2f}%."
        else:
            decision = "not_safe_for_direct_merge"
            reason = reason or "2022 overlap quality does not satisfy direct or scaled merge thresholds."
    return pd.DataFrame(
        [
            {
                "source": "Kaggle auxiliary Greece load",
                "decision": decision,
                "reason": reason,
                "ipto_primary_for_2022_2026": True,
                "usable_for_2019_2021": decision in {
                    "usable_as_auxiliary_history_without_scaling",
                    "usable_after_scaling_correction",
                },
                "scaling_required": decision == "usable_after_scaling_correction",
            }
        ]
    )


def build_master_candidate(
    model_ready: pd.DataFrame,
    kaggle: pd.DataFrame | None,
    decision: pd.DataFrame,
) -> pd.DataFrame | None:
    if decision.empty or not bool(decision.iloc[0].get("usable_for_2019_2021", False)):
        return None
    ipto_part = model_ready.copy()
    ipto_part["timestamp_dt"] = pd.to_datetime(ipto_part["timestamp"], errors="coerce", utc=True)
    ipto_part = ipto_part[ipto_part["timestamp_dt"].dt.year >= 2022]
    ipto_part = ipto_part.assign(
        source="IPTO/ADMIE",
        source_priority="ipto_primary_2022_2026",
    )
    ipto_part = ipto_part[
        ["timestamp", "national_load_mw", "source", "source_priority", "timezone", "scope", "was_imputed", "quality_flag", "notes"]
    ]

    kaggle_part = kaggle.copy() if kaggle is not None else pd.DataFrame()
    if kaggle_part.empty:
        return None
    kaggle_part["timestamp_dt"] = pd.to_datetime(kaggle_part["timestamp"], errors="coerce", utc=True)
    kaggle_part = kaggle_part[kaggle_part["timestamp_dt"].dt.year.between(2019, 2021)]
    if kaggle_part.empty:
        return ipto_part.sort_values("timestamp").reset_index(drop=True)
    kaggle_part = kaggle_part.assign(
        timestamp=kaggle_part["timestamp_dt"].dt.tz_convert(TIMEZONE).dt.strftime("%Y-%m-%d %H:%M:%S%z"),
        source="Kaggle auxiliary Greece load",
        source_priority=str(decision.iloc[0]["decision"]),
        timezone=TIMEZONE,
        scope="Kaggle auxiliary historical Greece load - boundary validated only by 2022 overlap",
        was_imputed=False,
        quality_flag="auxiliary_history",
        notes="Kaggle 2019-2021 included only because 2022 overlap decision allowed auxiliary use.",
    )
    kaggle_part = kaggle_part[
        ["timestamp", "national_load_mw", "source", "source_priority", "timezone", "scope", "was_imputed", "quality_flag", "notes"]
    ]
    return pd.concat([kaggle_part, ipto_part], ignore_index=True).sort_values("timestamp").reset_index(drop=True)


def _normalize_for_compare(df: pd.DataFrame, value_name: str) -> pd.DataFrame:
    working = df.copy()
    working["timestamp_dt"] = pd.to_datetime(working["timestamp"], errors="coerce", utc=True)
    working[value_name] = pd.to_numeric(working["national_load_mw"], errors="coerce")
    return working.dropna(subset=["timestamp_dt", value_name]).groupby("timestamp_dt", as_index=False)[value_name].mean()


def _build_overlap_summary(comparison: pd.DataFrame, missing_in_ipto: int, missing_in_kaggle: int) -> pd.DataFrame:
    if comparison.empty:
        return _summary_frame({"overlapping_hours_count": 0, "missing_in_ipto_count": missing_in_ipto, "missing_in_kaggle_count": missing_in_kaggle})
    diff = comparison["difference_mw"]
    abs_diff = comparison["absolute_difference_mw"]
    pct = comparison["percentage_difference"].replace([np.inf, -np.inf], np.nan)
    ipto_energy = comparison["ipto_load_mw"].sum()
    kaggle_energy = comparison["kaggle_load_mw"].sum()
    annual_diff_pct = ((ipto_energy - kaggle_energy) / kaggle_energy * 100) if kaggle_energy else np.nan
    peak_ipto = comparison["ipto_load_mw"].max()
    peak_kaggle = comparison["kaggle_load_mw"].max()
    peak_diff_pct = ((peak_ipto - peak_kaggle) / peak_kaggle * 100) if peak_kaggle else np.nan

    monthly = comparison.copy()
    monthly["timestamp_dt"] = pd.to_datetime(monthly["timestamp"], errors="coerce", utc=True).dt.tz_convert(TIMEZONE)
    monthly["month"] = monthly["timestamp_dt"].dt.month
    monthly_energy = monthly.groupby("month").agg(
        ipto=("ipto_load_mw", "sum"),
        kaggle=("kaggle_load_mw", "sum"),
    )
    monthly_diff = monthly_energy["ipto"] - monthly_energy["kaggle"]
    monthly_diff_pct = monthly_diff / monthly_energy["kaggle"].replace(0, np.nan) * 100

    return _summary_frame(
        {
            "overlapping_hours_count": len(comparison),
            "missing_in_ipto_count": missing_in_ipto,
            "missing_in_kaggle_count": missing_in_kaggle,
            "correlation": comparison["ipto_load_mw"].corr(comparison["kaggle_load_mw"]),
            "MAE": abs_diff.mean(),
            "RMSE": float(np.sqrt((diff**2).mean())),
            "MAPE": pct.abs().mean(),
            "mean_bias_mw": diff.mean(),
            "mean_bias_percent": pct.mean(),
            "monthly_energy_mwh_ipto": monthly_energy["ipto"].to_json(),
            "monthly_energy_mwh_kaggle": monthly_energy["kaggle"].to_json(),
            "monthly_difference_mwh": monthly_diff.to_json(),
            "monthly_difference_percent": monthly_diff_pct.to_json(),
            "annual_energy_mwh_ipto": ipto_energy,
            "annual_energy_mwh_kaggle": kaggle_energy,
            "annual_difference_percent": annual_diff_pct,
            "peak_load_ipto_mw": peak_ipto,
            "peak_load_kaggle_mw": peak_kaggle,
            "peak_load_difference_percent": peak_diff_pct,
        }
    )


def _summary_frame(values: dict[str, Any]) -> pd.DataFrame:
    columns = [
        "overlapping_hours_count",
        "missing_in_ipto_count",
        "missing_in_kaggle_count",
        "correlation",
        "MAE",
        "RMSE",
        "MAPE",
        "mean_bias_mw",
        "mean_bias_percent",
        "monthly_energy_mwh_ipto",
        "monthly_energy_mwh_kaggle",
        "monthly_difference_mwh",
        "monthly_difference_percent",
        "annual_energy_mwh_ipto",
        "annual_energy_mwh_kaggle",
        "annual_difference_percent",
        "peak_load_ipto_mw",
        "peak_load_kaggle_mw",
        "peak_load_difference_percent",
    ]
    return pd.DataFrame([{column: values.get(column, np.nan) for column in columns}])


def _comparison_flag(abs_percentage_difference: float) -> str:
    if pd.isna(abs_percentage_difference):
        return "not_comparable"
    if abs_percentage_difference <= 2:
        return "close_match"
    if abs_percentage_difference <= 5:
        return "moderate_difference"
    return "large_difference"


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {str(col).strip().lower(): col for col in df.columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    for key, col in normalized.items():
        if any(candidate in key for candidate in candidates):
            return col
    return None
