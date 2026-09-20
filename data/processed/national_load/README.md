# IPTO/ADMIE System Load

This folder contains the first national electricity demand/load data layer for the PyPSA Greece workflow.

- Source: IPTO/ADMIE Operation & Market Files API
- FileCategory: `RealTimeSCADASystemLoad`
- Data type: System Load
- Requested date range: `2022-01-01` to `2026-12-31`
- Effective date range after clamping future dates: `2022-01-01` to `2026-06-28`
- Future end date clamped: `True`
- Final processed CSV: `data/processed/national_load/ipto_system_load_hourly_2022_2026.csv`
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
