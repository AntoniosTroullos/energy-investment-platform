# API

Simple FastAPI backend for scenario evaluation.

## Run locally

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the server:

```bash
uvicorn app.main:app --reload
```

## Fetch Greece-wide infrastructure data

Substations, transmission lines, submarine transmission cables, and power plants can be refreshed from
OpenStreetMap via Overpass for the Greece-wide national MVP baseline.

```bash
python pipeline/fetch_osm_power.py
```

## Import Greece wind generator data from Global Energy Monitor

If the Global Wind Power Tracker workbook is available locally, extract the Greece-only
wind rows from both the main tracker sheet and the below-threshold sheet:

```bash
python pipeline/import_gem_wind_greece.py "C:\\path\\to\\Global-Wind-Power-Tracker-February-2026.xlsx"
```

This writes `data/source/gem_wind_greece.geojson`. The `/plants` and `/generators`
endpoints automatically fold those GEM wind assets into the canonical plant feed
while preserving source metadata.

## Import Greece wind records from the government registry zip

If the official wind zip is available locally, import the government wind records
into a backend-owned supplemental source:

```bash
python pipeline/import_government_wind_greece.py "C:\\path\\to\\gis-raaey-wms-rae_status-v_sdi_r_aiolika1237_count_ag-fy5j57_9.zip"
```

This writes:

- `data/source/government_wind_greece.geojson`
- `data/processed/government_wind_import_report.json`

The importer keeps the process explicit:

- it converts official wind polygons into point markers for the explorer
- it preserves official status, capacity, and turbine-count metadata
- it keeps the official source separate and lets the canonical generator merge prefer it over lower-confidence wind records when a strong overlap exists

## Import Greece solar generator data from Global Energy Monitor

If the Global Solar Power Tracker workbook is available locally, extract the Greece-only
solar rows from both the utility-scale sheet and the distributed aggregate sheet:

```bash
python pipeline/import_gem_solar_greece.py "C:\\path\\to\\Global-Solar-Power-Tracker-February-2026.xlsx"
```

This writes `data/source/gem_solar_greece.geojson`. The `/plants` and `/generators`
endpoints automatically fold those GEM solar assets into the canonical plant feed.
The distributed aggregate record is kept in the backend for capacity coverage and summaries,
but it is not displayed as a map point in the frontend.

## Import Greece photovoltaic records from the government registry CSV

If the government CSV export is available locally, import only the live or licensed
photovoltaic records that are not already represented in the current backend plant feed:

```bash
python pipeline/import_government_photovoltaics_greece.py "C:\\path\\to\\V_SDI_R_PHOTOVOLTAICS_ALL.csv"
```

This writes:

- `data/source/government_photovoltaics_greece.geojson`
- `data/processed/government_photovoltaics_import_report.json`

The importer is intentionally cautious:

- it keeps operation, installation, production, exempted, DEDDIE-submitted, and under-evaluation records
- it skips rejected, revoked, ceased, and clearly inactive records
- it compares each government record against the current canonical generator feed and only writes non-duplicates

## Import Greece hydropower generator data from Global Energy Monitor

If the Global Hydropower Tracker workbook is available locally, extract the Greece-only
hydropower rows from the main tracker sheet and any below-threshold sheet rows if they exist:

```bash
python pipeline/import_gem_hydro_greece.py "C:\\path\\to\\Global-Hydropower-Tracker-March-2026.xlsx"
```

This writes `data/source/gem_hydro_greece.geojson`. The `/plants` and `/generators`
endpoints automatically fold those GEM hydropower assets into the canonical plant feed.
When this source is present, unmatched OSM hydropower assets outside Greece are excluded
to reduce hydropower noise in the live generator layer.

## Import official RAAEY fossil-fuel power stations

If the official RAAEY fossil-fuel zip is available locally, convert it into a
backend-owned supplemental source layer:

```bash
python pipeline/import_raaey_fossil_fuel_plants.py "C:\\path\\to\\gis-raaey-wms-rae_status-v_sdi_r_orykta_all-hn5879de.zip"
```

This writes:

- `data/source/raaey_fossil_fuel_plants.geojson`
- `data/processed/raaey_fossil_fuel_plants_import_report.json`

The importer is intentionally honest:

- if the official export contains records, they are mapped into a clean backend source file
- if the official export is empty, the importer writes an empty supplemental layer instead of inventing fossil records
- the existing app continues to rely on the broader generator baseline for fossil coverage unless the official export actually contains rows

## Import Greece storage records from the government registry CSVs

If the storage CSV exports are available locally, import the installation-license
and operation-license storage assets into a backend-owned supplemental source:

```bash
python pipeline/import_government_storage_greece.py "C:\\path\\to\\v_sdi_r_storage12.csv" "C:\\path\\to\\v_sdi_r_storage13.csv"
```

This writes:

- `data/source/government_storage_greece.geojson`
- `data/processed/government_storage_import_report.json`

The importer keeps the flow cautious:

- it treats `storage12` as installation-license evidence and `storage13` as operation-license evidence
- it preserves storage-specific fields such as generation power, charging or pumping power, and energy capacity
- it skips strong duplicate matches against the current generator feed instead of blindly appending overlapping records
- if one of the source files is empty, it records that honestly in the import report

## Biomass / biogas phase 1

The first biomass phase reads local RAAEY files from:

- `data/raw/raaey/res_certificates`
- `data/raw/raaey/res_applications`
- `data/raw/raaey/ceased_or_revoked`

Optional validation hooks look for:

- `data/raw/deddie`
- `data/raw/admie`
- `data/raw/dapeep`

Run it with:

```bash
python pipeline/run_biomass_phase1.py
```

It writes staged outputs to:

- `data/processed/biomass_phase1/`

Optional manual biomass geolocation evidence can be stored in:

- `data/manual/biomass_manual_points.json`

This file is useful for user-supplied or manually verified points. It does not create
fake biomass plants by itself. The pipeline only uses it to enrich a matched RAAEY
record or to report unmatched evidence in the quality report.

Including:

- `raaey_biomass_candidates.csv`
- `raaey_biomass_candidates.json`
- `biomass_candidates_for_review.json`
- `biomass_phase1_quality_report.json`
- `biomass_phase1_summary_by_technology.csv`
- `biomass_phase1_summary_by_region.csv`
- `validation/*.json`

## Pumped-hydro official seed layer

The backend also ships a small official pumped-hydro seed layer:

- `data/source/pumped_hydro_seed.geojson`

It currently covers:

- Sfikia Pumped Storage HPP
- Thissavros Pumped Storage HPP
- Amfilochia Pumped Storage

This layer is merged into the canonical generator feed to preserve storage-specific
fields such as generation capacity, pumping capacity, reservoirs, developer, and
official source references without breaking the broader `/plants` flow.

## Generator quality reports

You can print the full generator quality report locally:

```bash
python pipeline/report_generators_quality.py
```

The JSON report now includes storage and pumped-hydro-specific sections.

## Generate candidate cells

Candidate cells are generated offline from simple source GeoJSON layers.

```bash
python pipeline/generate_candidates.py
```

The generated file is written to `data/generated/candidate_cells.geojson` and is
used by both `/candidates` and `/scenario/evaluate`.

## Market signal data

The Greece market signal endpoint uses public IPTO/ADMIE files for current
operational price and interconnection flow data. It does not require an
Electricity Maps token.

## Import official RAAEY hydrogen production units

If the official RAAEY hydrogen zip is available locally, import the production
units into the backend-owned hydrogen project layer:

```bash
python pipeline/import_raaey_hydrogen_projects.py "C:\\path\\to\\gis-raaey-wms-rae_status-v_sdi_r_hydrogen_all-azl5cazf.zip"
```

This writes:

- `data/source/hydrogen_projects.geojson`
- `data/processed/hydrogen_projects_import_report.json`

The importer keeps the current frontend/backend flow intact:

- official RAAEY production-unit polygons are converted into point markers for the explorer
- overlapping low-confidence starter entries are replaced by the official records
- clearly different legacy hydrogen assets, like the refuelling-station and White Dragon anchors, are kept

## Hydrogen infrastructure baseline

The backend now includes hydrogen infrastructure layers:

- `data/source/hydrogen_projects.geojson`
- `data/source/hydrogen_pipelines.geojson`

`hydrogen_projects.geojson` now uses the official RAAEY hydrogen production-units
registry as the main source of truth for production assets, while
`hydrogen_pipelines.geojson` remains a separate backend-owned line layer.

## Endpoints

- `GET /health`
- `GET /candidates`
- `GET /plants`
- `GET /generators`
- `GET /generators/summary/by-technology`
- `GET /generators/summary/by-region`
- `GET /generators/summary/storage`
- `GET /generators/quality/missing-capacity`
- `GET /generators/quality/missing-technology`
- `GET /generators/quality/missing-coordinates`
- `GET /generators/quality/duplicates`
- `GET /generators/quality/storage`
- `GET /generators/quality/pumped-hydro`
- `GET /generators/quality/biomass-phase1`
- `GET /generators/quality/report`
- `GET /generators/summary/biomass-phase1`
- `GET /generators/sources/coverage`
- `GET /generators/export/pypsa`
- `GET /substations`
- `GET /transmission-lines`
- `GET /gas-pipelines`
- `GET /gas-import-points`
- `GET /hydrogen-projects`
- `GET /hydrogen-pipelines`
- `GET /natura-2000`
- `GET /climate/asset`
- `GET /market/greece`
- `GET /market/greece-boundary`
- `POST /scenario/evaluate`
