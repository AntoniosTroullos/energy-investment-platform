from __future__ import annotations

import logging
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd


TIMEZONE = "Europe/Athens"
SCOPE = "IPTO System Load - exact system boundary to be validated"
FILE_CATEGORY = "RealTimeSCADASystemLoad"

LOAD_PATTERNS = [
    "load",
    "system load",
    "φορτίο",
    "φορτιο",
    "mw",
    "value",
    "actual",
    "πραγματικό",
    "πραγματικο",
]
FORECAST_EXCLUDE_PATTERNS = [
    "forecast",
    "πρόβλεψη",
    "προβλεψη",
    "isp",
    "schedule",
]
DATE_PATTERNS = ["date", "ημερομην", "day", "delivery day"]
HOUR_PATTERNS = ["hour", "ώρα", "ωρα", "period"]
TIMESTAMP_PATTERNS = ["timestamp", "datetime", "date time", "ημερομηνία/ώρα", "ημερομηνια/ωρα"]


@dataclass
class ParseResult:
    source_file: Path
    status: str
    data: pd.DataFrame
    warning: str = ""
    original_columns: list[str] | None = None


def parse_source_file(path: Path, logger: logging.Logger | None = None) -> ParseResult:
    logger = logger or logging.getLogger(__name__)
    try:
        frames = _read_candidate_tables(path)
    except Exception as exc:  # noqa: BLE001
        return ParseResult(path, "failed", pd.DataFrame(), f"read failed: {exc}", [])

    successful: list[ParseResult] = []
    warnings: list[str] = []
    for label, frame in frames:
        if frame.empty:
            continue
        try:
            result = _parse_table(frame, path, label)
            successful.append(result)
        except ValueError as exc:
            warnings.append(f"{label}: {exc}")
            logger.debug("Could not parse %s table %s: %s", path, label, exc)

    if not successful:
        return ParseResult(path, "failed", pd.DataFrame(), "; ".join(warnings) or "no parseable table", [])
    if len(successful) > 1:
        non_empty = [item for item in successful if not item.data.empty]
        if len(non_empty) > 1:
            combined = pd.concat([item.data for item in non_empty], ignore_index=True)
            if combined["timestamp"].duplicated().any():
                return ParseResult(
                    path,
                    "ambiguous",
                    pd.DataFrame(),
                    "multiple sheets/tables parsed with overlapping timestamps",
                    successful[0].original_columns,
                )
            warning = "combined multiple non-overlapping sheets/tables"
            combined = combined.sort_values("timestamp").reset_index(drop=True)
            combined["parse_quality_flag"] = _append_flag(combined["parse_quality_flag"], warning)
            return ParseResult(path, "parsed", combined, warning, successful[0].original_columns)
    return successful[0]


def write_parsed_daily_files(parsed: pd.DataFrame, output_dir: Path, source_stem: str) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if parsed.empty:
        return []
    working = parsed.copy()
    working["_date"] = (
        pd.to_datetime(working["timestamp"], errors="coerce", utc=True)
        .dt.tz_convert(TIMEZONE)
        .dt.strftime("%Y%m%d")
    )
    written: list[Path] = []
    for date_key, group in working.groupby("_date", dropna=False):
        safe_date = str(date_key) if isinstance(date_key, str) and date_key != "NaT" else source_stem[:8]
        output_path = output_dir / f"{safe_date}_{FILE_CATEGORY}.csv"
        group = group.drop(columns=["_date"]).sort_values("timestamp")
        group.to_csv(output_path, index=False)
        written.append(output_path)
    return written


def _read_candidate_tables(path: Path) -> list[tuple[str, pd.DataFrame]]:
    suffix = path.suffix.lower()
    if suffix == ".zip":
        tables: list[tuple[str, pd.DataFrame]] = []
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(path) as archive:
                archive.extractall(tmp)
            for member in Path(tmp).rglob("*"):
                if member.suffix.lower() in {".csv", ".xls", ".xlsx"}:
                    tables.extend(_read_candidate_tables(member))
        return tables
    if suffix == ".csv":
        return [(path.name, _read_csv_flexible(path))]
    if suffix in {".xls", ".xlsx"}:
        sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
        return [
            (str(name), _promote_header(frame))
            for name, frame in sheets.items()
            if "metadata" not in str(name).lower()
        ]
    raise ValueError(f"unsupported file type: {suffix}")


def _read_csv_flexible(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1253", "iso-8859-7"):
        for sep in (None, ";", ",", "\t"):
            try:
                frame = pd.read_csv(path, header=None, dtype=object, encoding=encoding, sep=sep, engine="python")
                return _promote_header(frame)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
    raise ValueError(f"could not read csv: {last_error}")


def _promote_header(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.dropna(how="all").dropna(axis=1, how="all")
    if raw.empty:
        return raw
    best_idx = 0
    best_score = -1
    scan = raw.head(min(len(raw), 20))
    for idx, row in scan.iterrows():
        values = [_norm(value) for value in row.tolist()]
        score = sum(_contains_any(value, DATE_PATTERNS + HOUR_PATTERNS + TIMESTAMP_PATTERNS + LOAD_PATTERNS) for value in values)
        text_count = sum(bool(re.search(r"[A-Za-zΑ-Ωα-ω]", value)) for value in values)
        score += min(text_count, 4)
        hour_label_count = sum(_parse_hour_column(value) is not None for value in row.tolist())
        has_date_label = any(value == "date" or _contains_any(value, DATE_PATTERNS) for value in values)
        if has_date_label and hour_label_count >= 20:
            score += 100
        if score > best_score:
            best_idx = int(idx)
            best_score = score
    header = [str(value).strip() if pd.notna(value) else f"unnamed_{i}" for i, value in enumerate(raw.loc[best_idx])]
    frame = raw.loc[best_idx + 1 :].copy()
    frame.columns = _dedupe_columns(header)
    return frame.dropna(how="all").reset_index(drop=True)


def _parse_table(frame: pd.DataFrame, source_file: Path, label: str) -> ParseResult:
    original_columns = [str(col) for col in frame.columns]
    frame = frame.dropna(how="all").copy()
    if frame.empty:
        raise ValueError("empty table")

    wide = _parse_wide_hour_table(frame, source_file, label, original_columns)
    if wide is not None:
        return wide

    load_col, load_warning = _detect_load_column(frame)
    timestamps, ts_warning, raw_date, raw_hour, raw_timestamp = _build_timestamps(frame)
    load_values = pd.to_numeric(_clean_numeric_series(frame[load_col]), errors="coerce")

    parsed = pd.DataFrame(
        {
            "timestamp": timestamps,
            "load_mw": load_values,
            "raw_timestamp": raw_timestamp,
            "raw_date": raw_date,
            "raw_hour": raw_hour,
            "source_file": source_file.name,
            "file_category": FILE_CATEGORY,
            "timezone": TIMEZONE,
            "scope": SCOPE,
            "parse_quality_flag": "ok",
        }
    )
    parsed = parsed.dropna(subset=["timestamp", "load_mw"])
    if parsed.empty:
        raise ValueError("no rows with valid timestamp and load")

    warnings = [item for item in [load_warning, ts_warning, f"sheet/table={label}"] if item]
    if warnings:
        parsed["parse_quality_flag"] = "; ".join(warnings)

    parsed["timestamp"] = pd.to_datetime(parsed["timestamp"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S%z")
    parsed = parsed.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    return ParseResult(source_file, "parsed", parsed, "; ".join(warnings), original_columns)


def _parse_wide_hour_table(
    frame: pd.DataFrame,
    source_file: Path,
    label: str,
    original_columns: list[str],
) -> ParseResult | None:
    date_col = next((col for col in frame.columns if _norm(col) == "date" or _contains_any(_norm(col), DATE_PATTERNS)), None)
    if date_col is None:
        return None

    hour_cols: list[tuple[Any, int]] = []
    for col in frame.columns:
        if col == date_col:
            continue
        hour = _parse_hour_column(col)
        if hour is not None:
            hour_cols.append((col, hour))
    if len(hour_cols) < 20:
        return None

    parsed_rows: list[dict[str, Any]] = []
    skipped_non_dst_hour25 = False
    for _, row in frame.iterrows():
        parsed_date = pd.to_datetime(row.get(date_col), errors="coerce", dayfirst=True)
        if pd.isna(parsed_date):
            continue
        local_date = pd.Timestamp(parsed_date).normalize()
        expected_hours = _expected_local_hours(local_date)
        for col, hour_ending in hour_cols:
            load_value = pd.to_numeric(_clean_numeric_series(pd.Series([row.get(col)])), errors="coerce").iloc[0]
            if pd.isna(load_value):
                continue
            hour_index = hour_ending - 1
            if hour_ending == 25 and float(load_value) == 0:
                continue
            if hour_ending == 25 and expected_hours != 25:
                skipped_non_dst_hour25 = True
                continue
            if hour_ending == 25:
                hour_index = 24
            timestamp = local_date + pd.Timedelta(hours=hour_index)
            timestamp = _localize_timestamp_series(pd.Series([timestamp])).iloc[0]
            parsed_rows.append(
                {
                    "timestamp": timestamp,
                    "load_mw": float(load_value),
                    "raw_timestamp": f"{row.get(date_col)} {hour_ending}",
                    "raw_date": str(row.get(date_col)),
                    "raw_hour": str(hour_ending),
                    "source_file": source_file.name,
                    "file_category": FILE_CATEGORY,
                    "timezone": TIMEZONE,
                    "scope": SCOPE,
                    "parse_quality_flag": f"wide hourly table; selected primary block from sheet/table={label}",
                }
            )
        break

    if not parsed_rows:
        return None
    parsed = pd.DataFrame(parsed_rows).sort_values("timestamp").reset_index(drop=True)
    if parsed["timestamp"].duplicated().any():
        parsed["parse_quality_flag"] = _append_flag(parsed["parse_quality_flag"], "; duplicate timestamps detected during wide parse")
    if skipped_non_dst_hour25:
        parsed["parse_quality_flag"] = _append_flag(parsed["parse_quality_flag"], "; skipped non-DST hour 25 template value")
    parsed["timestamp"] = pd.to_datetime(parsed["timestamp"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S%z")
    parsed = parsed.dropna(subset=["timestamp"]).reset_index(drop=True)
    warning = "wide hourly table parsed; primary source block selected; IPTO boundary remains to be validated"
    if skipped_non_dst_hour25:
        warning += "; skipped non-DST hour 25 template value"
    return ParseResult(source_file, "parsed", parsed, warning, original_columns)


def _parse_hour_column(value: Any) -> int | None:
    if isinstance(value, int) and 1 <= value <= 25:
        return value
    if isinstance(value, float) and value.is_integer() and 1 <= int(value) <= 25:
        return int(value)
    text = str(value).strip()
    if re.fullmatch(r"\d{1,2}", text):
        hour = int(text)
        if 1 <= hour <= 25:
            return hour
    return None


def _expected_local_hours(local_date: pd.Timestamp) -> int:
    start = pd.Timestamp(local_date.date(), tz=TIMEZONE)
    end = pd.Timestamp(local_date.date() + timedelta(days=1), tz=TIMEZONE)
    return len(pd.date_range(start=start, end=end, freq="h", inclusive="left"))


def _detect_load_column(frame: pd.DataFrame) -> tuple[str, str]:
    scores: list[tuple[int, str, str]] = []
    for col in frame.columns:
        col_text = _norm(col)
        if _contains_any(col_text, FORECAST_EXCLUDE_PATTERNS):
            continue
        if _contains_any(col_text, DATE_PATTERNS + HOUR_PATTERNS + TIMESTAMP_PATTERNS):
            continue
        numeric = pd.to_numeric(_clean_numeric_series(frame[col]), errors="coerce")
        numeric_ratio = float(numeric.notna().mean()) if len(numeric) else 0.0
        if numeric_ratio < 0.5:
            continue
        score = int(numeric_ratio * 50)
        for pattern in LOAD_PATTERNS:
            if pattern in col_text:
                score += 20
        median_value = numeric.dropna().median() if numeric.notna().any() else None
        if median_value is not None and 1000 <= median_value <= 15000:
            score += 20
        scores.append((score, str(col), f"numeric_ratio={numeric_ratio:.2f}, median={median_value}"))

    scores.sort(reverse=True)
    if not scores:
        raise ValueError("no load column candidate")
    if len(scores) > 1 and scores[0][0] - scores[1][0] < 15:
        raise ValueError(f"ambiguous load columns: {scores[:4]}")
    warning = f"selected load column '{scores[0][1]}' ({scores[0][2]})"
    return scores[0][1], warning


def _build_timestamps(frame: pd.DataFrame) -> tuple[pd.Series, str, pd.Series, pd.Series, pd.Series]:
    timestamp_cols = [col for col in frame.columns if _contains_any(_norm(col), TIMESTAMP_PATTERNS)]
    for col in timestamp_cols:
        parsed = _localize_timestamp_series(pd.to_datetime(frame[col], errors="coerce", dayfirst=True))
        if parsed.notna().mean() > 0.7:
            raw = frame[col].astype(str)
            return parsed, f"timestamp column '{col}' localized to {TIMEZONE}", pd.Series("", index=frame.index), pd.Series("", index=frame.index), raw

    date_cols = [col for col in frame.columns if _contains_any(_norm(col), DATE_PATTERNS)]
    hour_cols = [col for col in frame.columns if _contains_any(_norm(col), HOUR_PATTERNS)]
    best: tuple[float, str, str, pd.Series] | None = None
    for date_col in date_cols or list(frame.columns):
        dates = pd.to_datetime(frame[date_col], errors="coerce", dayfirst=True)
        if dates.notna().mean() < 0.5:
            continue
        if hour_cols:
            for hour_col in hour_cols:
                candidate = _combine_date_hour(dates, frame[hour_col])
                score = float(candidate.notna().mean())
                if best is None or score > best[0]:
                    best = (score, str(date_col), str(hour_col), candidate)
        else:
            candidate = _localize_timestamp_series(dates)
            score = float(candidate.notna().mean())
            if best is None or score > best[0]:
                best = (score, str(date_col), "", candidate)
    if best is None or best[0] < 0.7:
        raise ValueError("could not build reliable timestamps")

    _, date_col, hour_col, timestamps = best
    raw_date = frame[date_col].astype(str)
    raw_hour = frame[hour_col].astype(str) if hour_col else pd.Series("", index=frame.index)
    raw_timestamp = (raw_date + " " + raw_hour).str.strip()
    warning = f"timestamp built from date='{date_col}' hour='{hour_col or 'none'}'"
    if timestamps.duplicated().any():
        warning += "; duplicate timestamps detected during parsing"
    return timestamps, warning, raw_date, raw_hour, raw_timestamp


def _combine_date_hour(dates: pd.Series, hours: pd.Series) -> pd.Series:
    parsed_hours = hours.map(_parse_hour_value)
    base = dates.dt.normalize()
    adjusted_dates = base.copy()
    hour_numbers = parsed_hours.copy()
    hour_ending_24 = hour_numbers == 24
    adjusted_dates.loc[hour_ending_24] = adjusted_dates.loc[hour_ending_24] + pd.Timedelta(days=1)
    hour_numbers.loc[hour_ending_24] = 0
    naive = adjusted_dates + pd.to_timedelta(hour_numbers, unit="h")
    return _localize_timestamp_series(naive)


def _localize_timestamp_series(series: pd.Series) -> pd.Series:
    localized = []
    for value in series:
        if pd.isna(value):
            localized.append(pd.NaT)
            continue
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is not None:
            localized.append(timestamp.tz_convert(TIMEZONE))
            continue
        try:
            localized.append(timestamp.tz_localize(TIMEZONE, ambiguous="infer", nonexistent="shift_forward"))
        except Exception:
            try:
                localized.append(timestamp.tz_localize(TIMEZONE, ambiguous=True, nonexistent="shift_forward"))
            except Exception:
                localized.append(pd.NaT)
    return pd.Series(localized, index=series.index)


def _parse_hour_value(value: Any) -> float:
    if pd.isna(value):
        return float("nan")
    if isinstance(value, pd.Timestamp):
        return float(value.hour)
    text = str(value).strip()
    match = re.search(r"(\d{1,2})(?::\d{2})?", text)
    if not match:
        return float("nan")
    hour = int(match.group(1))
    if 1 <= hour <= 24 and not text.startswith("0"):
        return float(hour - 1)
    return float(hour)


def _clean_numeric_series(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.replace("\u00a0", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.extract(r"([-+]?\d+(?:\.\d+)?)", expand=False)
    )


def _append_flag(series: pd.Series, flag: str) -> pd.Series:
    return series.astype(str).where(series.astype(str) != "ok", "") + flag


def _dedupe_columns(columns: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for column in columns:
        base = column or "unnamed"
        seen[base] = seen.get(base, 0) + 1
        result.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
    return result


def _norm(value: Any) -> str:
    return str(value).strip().lower()


def _contains_any(value: str, patterns: list[str]) -> bool:
    return any(pattern.lower() in value for pattern in patterns)
