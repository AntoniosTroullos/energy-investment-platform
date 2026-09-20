from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.ipto_client import IPTOClient  # noqa: E402
from src.data.ipto_parse import FILE_CATEGORY, SCOPE, TIMEZONE, parse_source_file, write_parsed_daily_files  # noqa: E402
from src.data.quality_checks import build_processed_summaries, run_quality_checks  # noqa: E402


RAW_FILETYPE_DIR = ROOT / "data" / "raw" / "ipto" / "filetype_info"
RAW_FILES_DIR = ROOT / "data" / "raw" / "ipto" / FILE_CATEGORY
SEARCH_DIR = ROOT / "data" / "interim" / "ipto" / "search_responses"
PARSED_DIR = ROOT / "data" / "interim" / "ipto" / "parsed_daily_files"
CATALOG_PATH = ROOT / "data" / "interim" / "ipto" / "ipto_system_load_file_catalog.csv"
VALIDATION_DIR = ROOT / "data" / "validation" / "national_load"
PROCESSED_DIR = ROOT / "data" / "processed" / "national_load"
LOG_PATH = VALIDATION_DIR / "ipto_download_parse.log"


def main() -> int:
    args = parse_args()
    logger = configure_logging()
    start = date.fromisoformat(args.start_date)
    requested_end = date.fromisoformat(args.end_date)
    today_athens = datetime.now(ZoneInfo(TIMEZONE)).date()
    effective_end = requested_end
    clamped = False
    if requested_end > today_athens and not args.allow_future_end_date:
        effective_end = today_athens
        clamped = True

    logger.info("Requested date range: %s to %s", start, requested_end)
    logger.info("Effective date range: %s to %s", start, effective_end)
    if clamped:
        logger.info("Future end date clamped to today in %s: %s", TIMEZONE, effective_end)
    if args.file_category != FILE_CATEGORY:
        logger.warning("This pipeline is tuned for %s; requested category is %s", FILE_CATEGORY, args.file_category)

    ensure_dirs()
    client = IPTOClient(logger=logger)
    filetypes = client.fetch_filetypes()
    write_json(RAW_FILETYPE_DIR / "getFiletypeInfoEN.json", filetypes)

    records: list[dict[str, Any]] = []
    for chunk_start, chunk_end in month_chunks(start, effective_end):
        response = client.find_files(
            chunk_start.isoformat(),
            chunk_end.isoformat(),
            file_category=args.file_category,
            use_range=True,
        )
        response_path = SEARCH_DIR / f"{args.file_category}_{chunk_start.isoformat()}_{chunk_end.isoformat()}.json"
        write_json(response_path, response)
        chunk_records = extract_records(response)
        logger.info("Found %s file records for %s to %s", len(chunk_records), chunk_start, chunk_end)
        records.extend(chunk_records)

    records = dedupe_records(records)
    logger.info("Found %s unique file records total", len(records))
    download_results = client.download_files(records, RAW_FILES_DIR, force=args.force)
    failed_downloads = [
        {"file_path": item.record.get("file_path", ""), "error": item.error or "", "download_status": item.status}
        for item in download_results
        if item.status == "failed"
    ]
    pd.DataFrame(failed_downloads, columns=["file_path", "error", "download_status"]).to_csv(
        VALIDATION_DIR / "ipto_failed_downloads.csv",
        index=False,
    )

    catalog_rows: list[dict[str, Any]] = []
    parsed_frames: list[pd.DataFrame] = []
    failed_parsing: list[dict[str, Any]] = []
    for item in download_results:
        row = catalog_row(item.record)
        row["local_path"] = str(item.local_path or "")
        row["download_status"] = item.status
        row["parse_status"] = "not_attempted"
        row["parse_warning"] = item.error or ""
        if item.local_path and item.local_path.exists():
            result = parse_source_file(item.local_path, logger=logger)
            row["parse_status"] = result.status
            row["parse_warning"] = result.warning
            if result.status == "parsed":
                write_parsed_daily_files(result.data, PARSED_DIR, item.local_path.stem)
                parsed_frames.append(result.data)
                logger.info("Parsed %s rows from %s", len(result.data), item.local_path.name)
            else:
                logger.warning("Parse failed/ambiguous for %s: %s", item.local_path.name, result.warning)
                failed_parsing.append(
                    {
                        "source_file": item.local_path.name,
                        "status": result.status,
                        "warning": result.warning,
                        "original_columns": "|".join(result.original_columns or []),
                    }
                )
        catalog_rows.append(row)

    pd.DataFrame(catalog_rows).to_csv(CATALOG_PATH, index=False)
    pd.DataFrame(failed_parsing, columns=["source_file", "status", "warning", "original_columns"]).to_csv(
        VALIDATION_DIR / "ipto_failed_parsing.csv",
        index=False,
    )

    final = build_final_frame(parsed_frames)
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(output_path, index=False)
    monthly, annual = build_processed_summaries(final, args.start_date, effective_end.isoformat())
    monthly.to_csv(PROCESSED_DIR / "ipto_system_load_monthly_summary_2022_2026.csv", index=False)
    annual.to_csv(PROCESSED_DIR / "ipto_system_load_annual_summary_2022_2026.csv", index=False)
    quality = run_quality_checks(final, VALIDATION_DIR, start_date=args.start_date, effective_end_date=effective_end.isoformat())
    write_readme(args.start_date, args.end_date, effective_end.isoformat(), output_path.relative_to(ROOT), clamped)

    logger.info("Final row count: %s", len(final))
    logger.info("Final date coverage: %s to %s", final["timestamp"].min() if not final.empty else "", final["timestamp"].max() if not final.empty else "")
    logger.info("Quality report rows: %s", len(quality["quality_report"]))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download, parse, and validate IPTO/ADMIE System Load files.")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--file-category", default=FILE_CATEGORY)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-future-end-date", action="store_true")
    parser.add_argument("--force", action="store_true", help="Overwrite already downloaded raw source files.")
    return parser.parse_args()


def configure_logging() -> logging.Logger:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ipto_system_load")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger


def ensure_dirs() -> None:
    for path in [RAW_FILETYPE_DIR, RAW_FILES_DIR, SEARCH_DIR, PARSED_DIR, VALIDATION_DIR, PROCESSED_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def month_chunks(start: date, end: date) -> list[tuple[date, date]]:
    chunks: list[tuple[date, date]] = []
    cursor = start.replace(day=1)
    while cursor <= end:
        chunk_start = max(cursor, start)
        next_month = cursor + relativedelta(months=1)
        chunk_end = min(next_month - relativedelta(days=1), end)
        chunks.append((chunk_start, chunk_end))
        cursor = next_month
    return chunks


def extract_records(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if isinstance(response, dict):
        for key in ("data", "files", "results", "rows"):
            value = response.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if "file_path" in response:
            return [response]
    return []


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for record in records:
        key = str(record.get("file_path") or json.dumps(record, sort_keys=True, ensure_ascii=False))
        if key not in seen:
            seen.add(key)
            deduped.append(record)
    return deduped


def catalog_row(record: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "file_path",
        "local_path",
        "file_description",
        "file_process",
        "file_datatype",
        "file_coverageperiod",
        "file_fromdate",
        "file_todate",
        "file_published",
        "download_status",
        "parse_status",
        "parse_warning",
    ]
    return {field: record.get(field, "") for field in fields}


def build_final_frame(parsed_frames: list[pd.DataFrame]) -> pd.DataFrame:
    columns = ["timestamp", "national_load_mw", "source", "timezone", "scope", "source_file", "file_category", "quality_flag"]
    if not parsed_frames:
        return pd.DataFrame(columns=columns)
    combined = pd.concat(parsed_frames, ignore_index=True)
    combined = combined.rename(columns={"load_mw": "national_load_mw", "parse_quality_flag": "quality_flag"})
    combined["source"] = "IPTO/ADMIE"
    combined["timezone"] = TIMEZONE
    combined["scope"] = SCOPE
    combined = combined[columns]
    combined = combined.drop_duplicates()
    combined = combined.sort_values("timestamp").reset_index(drop=True)
    return combined


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_readme(start_date: str, requested_end_date: str, effective_end_date: str, output_path: Path, clamped: bool) -> None:
    text = f"""# IPTO/ADMIE System Load

This folder contains the first national electricity demand/load data layer for the PyPSA Greece workflow.

- Source: IPTO/ADMIE Operation & Market Files API
- FileCategory: `RealTimeSCADASystemLoad`
- Data type: System Load
- Requested date range: `{start_date}` to `{requested_end_date}`
- Effective date range after clamping future dates: `{start_date}` to `{effective_end_date}`
- Future end date clamped: `{clamped}`
- Final processed CSV: `{output_path.as_posix()}`
- Raw files: `data/raw/ipto/RealTimeSCADASystemLoad/`

## API Endpoints

- `https://www.admie.gr/getFiletypeInfoEN`
- `https://www.admie.gr/getOperationMarketFilewRange?dateStart=YYYY-MM-DD&dateEnd=YYYY-MM-DD&FileCategory=RealTimeSCADASystemLoad`
- `https://www.admie.gr/getOperationMarketFile?dateStart=YYYY-MM-DD&dateEnd=YYYY-MM-DD&FileCategory=RealTimeSCADASystemLoad`

The pipeline uses the range endpoint by default and queries in monthly chunks.

## Parsing Assumptions

The parser supports CSV, XLS, XLSX, and ZIP files containing those formats. It scans all Excel sheets, promotes likely header rows, detects timestamp/date/hour columns, and selects a likely System Load MW column only when the confidence gap is high enough. Ambiguous files are reported instead of being silently parsed.

Timestamps are normalized to `Europe/Athens`. Hour-ending `24` values are moved to the following local midnight. Sub-hourly duplicate timestamps are not averaged silently; duplicate and irregular timestamp conditions are reported in validation outputs.

## Quality Checks

Validation outputs cover missing timestamps, duplicate timestamps, non-hourly gaps, negative or zero load values, suspicious low/high values, daily row-count anomalies, monthly and annual completeness, source-file coverage gaps, extreme consecutive-hour jumps, and incomplete current-year handling.

## Known Limitations

The exact IPTO System Load boundary still needs to be validated against ENTSO-E Actual Total Load and national annual electricity-demand totals. Excel formats can change over time, so failed or ambiguous source files should be reviewed in `data/validation/national_load/ipto_failed_parsing.csv`.

## Next Step

Build the ENTSO-E comparison downloader and compare hourly, monthly, and annual totals before using this baseline for regional spatial disaggregation.
"""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    (PROCESSED_DIR / "README.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
