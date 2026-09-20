# Backend Data Contracts

This folder defines the source-layer contracts for the backend infrastructure and candidate-generation pipeline.

The structure is:

- `source/`
  Starter input layers used by the pipeline.
- `generated/`
  Pipeline outputs that the API can serve to the frontend.
- `raw/`
  Manually downloaded source files used by offline ingestion/extraction steps.
- `processed/`
  Intermediate staged outputs and quality reports produced by backend pipelines.
- `manual/`
  Small hand-maintained helper files for evidence that should enrich a staged dataset
  without pretending to be a full scraped source.

## Source layers

### `source/region_boundary.geojson`
- Purpose: defines the pilot screening region where candidate cells can be created.
- Geometry type: `Polygon`
- Required properties:
  - `id`
  - `name`

### `source/substations.geojson`
- Purpose: provides Greece-wide grid connection anchor points for the infrastructure explorer and for distance calculations.
- Geometry type: `Point`
- Required properties:
  - `id`
  - `name`
  - `voltage_kv`

### `source/transmission_lines.geojson`
- Purpose: provides Greece-wide transmission infrastructure for the infrastructure explorer and for distance-to-line calculations, including submarine interconnectors where OSM maps them as power cables.
- Geometry type: `LineString`
- Required properties:
  - `id`
  - `name`
  - `voltage_kv`
- Useful optional properties:
  - `power_type`
  - `location`
  - `is_submarine`

### `source/power_plants.geojson`
- Purpose: provides a Greece-wide backend-owned baseline of mapped power plants.
- Geometry type: `Point`
- Required properties:
  - `id`
  - `name`
  - `technology`
  - `status`

### `source/gem_wind_greece.geojson`
- Purpose: stores Greece-only wind generator records imported from the Global Energy Monitor Global Wind Power Tracker, including both the main above-threshold sheet and the below-threshold sheet.
- Geometry type: `Point`
- Required properties:
  - `id`
  - `name`
  - `project_name`
  - `technology`
  - `capacity_mw`
  - `status`
  - `status_category`
  - `primary_source`
  - `gem_location_id`
  - `gem_phase_id`
- Useful optional properties:
  - `operator`
  - `owner`
  - `threshold_bucket`
  - `municipality`
  - `regional_unit`
  - `region`
  - `source_refs`
  - `wiki_url`

### `source/government_wind_greece.geojson`
- Purpose: stores government-registry wind assets imported from the official
  RAAEY wind zip after converting polygon footprints into backend-owned point
  markers and preserving wind-specific fields such as turbine counts.
- Geometry type: `Point`
- Required properties:
  - `id`
  - `name`
  - `technology`
  - `status`
  - `status_category`
  - `primary_source`
- Useful optional properties:
  - `license_id`
  - `application_code`
  - `government_registry_id`
  - `capacity_mw`
  - `nominal_capacity_mw`
  - `wind_turbine_count_total`
  - `wind_turbine_count_raw`
  - `equivalent_typical_turbines`
  - `turbine_diameter_summary`
  - `environmental_terms_approved`
  - `municipality`
  - `regional_unit`
  - `region`
  - `source_refs`
  - `location_accuracy`

### `source/gem_solar_greece.geojson`
- Purpose: stores Greece-only solar generator records imported from the Global Energy Monitor Global Solar Power Tracker, including utility-scale projects and one distributed aggregate summary record.
- Geometry type: `Point` for utility-scale assets, `null` for the distributed aggregate summary.
- Required properties:
  - `id`
  - `name`
  - `project_name`
  - `technology`
  - `capacity_mw`
  - `status`
  - `status_category`
  - `primary_source`
  - `source_dataset`
- Useful optional properties:
  - `capacity_rating`
  - `technology_type`
  - `municipality`
  - `regional_unit`
  - `region`
  - `threshold_bucket`
  - `display_on_map`
  - `source_refs`
  - `wiki_url`

### `source/government_photovoltaics_greece.geojson`
- Purpose: stores government-registry photovoltaic assets imported from `V_SDI_R_PHOTOVOLTAICS_ALL.csv` after cautious status filtering and duplicate checks against the current generator feed.
- Geometry type: `Point`
- Required properties:
  - `id`
  - `name`
  - `project_name`
  - `technology`
  - `capacity_mw`
  - `status`
  - `status_category`
  - `primary_source`
  - `source_dataset`
- Useful optional properties:
  - `license_id`
  - `application_code`
  - `government_registry_id`
  - `site_name`
  - `municipality`
  - `regional_unit`
  - `region`
  - `source_refs`
  - `location_accuracy`

### `source/raaey_fossil_fuel_plants.geojson`
- Purpose: stores official RAAEY fossil-fuel power-station records as a cautious
  backend-owned supplemental generator source.
- Geometry type: `Point`
- Required properties:
  - `id`
  - `name`
  - `technology`
  - `status`
  - `primary_source`
- Useful optional properties:
  - `license_id`
  - `application_code`
  - `government_registry_id`
  - `capacity_mw`
  - `nominal_capacity_mw`
  - `status_category`
  - `license_status`
  - `operator`
  - `owner`
  - `developer`
  - `municipality`
  - `regional_unit`
  - `region`
  - `location_accuracy`
  - `source_refs`

### `source/government_storage_greece.geojson`
- Purpose: stores government-registry storage assets imported from
  `v_sdi_r_storage12.csv` and `v_sdi_r_storage13.csv` after cautious duplicate
  checks against the current generator feed.
- Geometry type: `Point`
- Required properties:
  - `id`
  - `name`
  - `technology`
  - `status`
  - `status_category`
  - `primary_source`
- Useful optional properties:
  - `license_id`
  - `application_code`
  - `government_registry_id`
  - `generation_capacity_mw`
  - `pumping_capacity_mw`
  - `energy_capacity_mwh`
  - `guaranteed_capacity_mwh`
  - `environmental_terms_approved`
  - `municipality`
  - `regional_unit`
  - `region`
  - `source_refs`
  - `location_accuracy`

### `source/gem_hydro_greece.geojson`
- Purpose: stores Greece-only hydropower generator records imported from the Global Energy Monitor Global Hydropower Tracker.
- Geometry type: `Point`
- Required properties:
  - `id`
  - `name`
  - `project_name`
  - `technology`
  - `capacity_mw`
  - `status`
  - `status_category`
  - `primary_source`
  - `source_dataset`
- Useful optional properties:
  - `technology_type`
  - `operator`
  - `owner`
  - `river_watercourse`
  - `complex`
  - `municipality`
  - `regional_unit`
  - `region`
  - `country_role`
  - `threshold_bucket`
  - `source_refs`
  - `wiki_url`

### `source/pumped_hydro_seed.geojson`
- Purpose: stores a small official-source pumped-hydro seed layer so storage-specific
  fields can be preserved cleanly in the canonical generator feed.
- Geometry type: `FeatureCollection` with nullable geometry when no safe point geometry
  is available from the current official source set.
- Required properties:
  - `id`
  - `name`
  - `technology`
  - `status`
  - `primary_source`
  - `source_refs`
- Useful optional properties:
  - `operator`
  - `owner`
  - `developer`
  - `nominal_capacity_mw`
  - `generation_capacity_mw`
  - `pumping_capacity_mw`
  - `upper_reservoir`
  - `lower_reservoir`
  - `reservoir_system`
  - `reversible_units`
  - `count_in_summary`
  - `display_on_map`

### `source/gas_pipelines.geojson`
- Purpose: provides a beginner-readable national gas transmission backbone layer for the infrastructure explorer.
- Geometry type: `LineString`
- Required properties:
  - `id`
  - `name`
  - `pipeline_role`
  - `operator`
  - `status`
- Useful optional properties:
  - `diameter_in`
  - `source`

### `source/gas_import_points.geojson`
- Purpose: provides the main natural gas import entry points that feed Greece.
- Geometry type: `Point`
- Required properties:
  - `id`
  - `name`
  - `import_type`
  - `connected_system`
  - `operator`
  - `status`
- Useful optional properties:
  - `design_capacity_nm3h`
  - `source`

### `source/hydrogen_projects.geojson`
- Purpose: provides a backend-owned hydrogen project layer centered on official
  RAAEY hydrogen production-unit records, while allowing a few clearly separate
  legacy seed points for non-overlapping hydrogen infrastructure such as the
  refuelling-station and hydrogen-valley anchors.
- Geometry type: `Point`
- Required properties:
  - `id`
  - `name`
  - `project_type`
  - `hydrogen_role`
  - `status`
- Useful optional properties:
  - `operator`
  - `hydrogen_type`
  - `electrolyzer_capacity_mw`
  - `annual_output_tpa`
  - `license_id`
  - `application_code`
  - `government_registry_id`
  - `license_status`
  - `status_category`
  - `region`
  - `regional_unit`
  - `municipality`
  - `municipal_unit`
  - `location_confidence`
  - `source`
  - `primary_source`
  - `source_refs`
  - `notes`

### `source/hydrogen_pipelines.geojson`
- Purpose: provides backend-owned hydrogen transmission pipe lines for the Greece infrastructure explorer.
- Geometry type: `LineString`
- Required properties:
  - `id`
  - `name`
  - `pipeline_code`
  - `development_stage`
  - `status`
- Useful optional properties:
  - `operator`
  - `hydrogen_role`
  - `project_type`
  - `country_code`
  - `target_year`
  - `capacity_gwh_per_day`
  - `length_km`
  - `estimated_cost_eur`
  - `geometry_confidence`
  - `region`
  - `regional_unit`
  - `source`
  - `primary_source`
  - `source_refs`
  - `notes`

### `source/natura_2000.geojson`
- Purpose: provides protected Natura 2000 areas as a backend-owned context and screening-constraint layer.
- Geometry type: `Polygon` or `MultiPolygon`
- Required properties:
  - `id`
  - `name`
  - `site_type`
- Useful optional properties:
  - `site_code`
  - `member_state`
  - `area_km2`
  - `source`

### `source/exclusions.geojson`
- Purpose: marks areas that should be excluded or heavily penalized during screening.
- Geometry type: `Polygon`
- Required properties:
  - `id`
  - `name`
  - `category`

### `source/resource_zones.geojson`
- Purpose: provides simple resource-quality zones used to assign solar and wind scores.
- Geometry type: `Polygon`
- Required properties:
  - `id`
  - `name`
  - `solar_score`
  - `wind_score`

## Generated output contract

### `generated/candidate_cells.geojson`
- Purpose: backend-owned candidate investment cells served by `/candidates` and evaluated by `/scenario/evaluate`
- Geometry type: `Polygon`
- Feature type: GeoJSON `FeatureCollection`

Each candidate cell should include at least these properties:
- `id`
- `name`
- `technology`
- `excluded`
- `distance_to_substation_km`
- `distance_to_line_km`
- `solar_score`
- `wind_score`
- `investment_score`

Optional but useful companion properties:
- `land_excluded`
- `connection_cost_level`
- `status`

## Notes

- These files are kept beginner-readable even when sourced from real OSM infrastructure.
- `raw/raaey`, `raw/deddie`, `raw/admie`, and `raw/dapeep` support the biomass/biogas phase 1 extraction flow.
- `manual/biomass_manual_points.json` is a manual evidence hook for biomass/biogas locations.
  It can hold user-supplied EGSA87 or WGS84 points and is used only to enrich a matched
  staged record or to report unmatched location evidence.
- `gem_wind_greece.geojson` is a structured supplemental generator source, not a replacement for the full OSM plant baseline.
- `government_wind_greece.geojson` is a high-confidence official wind supplemental
  source. When it overlaps with lower-confidence mergeable wind records, the
  canonical generator flow should prefer the official source metadata.
- `gem_solar_greece.geojson` is a structured supplemental generator source; its distributed aggregate record is used for backend capacity coverage and summaries, but it is intentionally not shown as a map point.
- `gem_hydro_greece.geojson` is a structured supplemental generator source that provides cleaner Greece hydropower coverage than the OSM-only baseline, including pumped-storage projects.
- `pumped_hydro_seed.geojson` adds official-source pumped-hydro metadata and source traceability for key storage assets without inventing missing capacities or coordinates.
- `hydrogen_projects.geojson` now uses the official RAAEY hydrogen production-units
  registry as the main source of truth for production projects and replaces
  overlapping starter entries when the official record is available.
- `raaey_fossil_fuel_plants.geojson` is an official-source supplemental layer for
  fossil-fuel plants. If the downloaded RAAEY export is empty, the file should stay
  honestly empty rather than inventing or copying fossil records into it.
- `government_storage_greece.geojson` is a government-source supplemental storage
  layer. If one of the source status files is empty, the import report should note
  that explicitly instead of inventing missing operating or installation assets.
- `hydrogen_pipelines.geojson` stores hydrogen transmission pipe lines separately from hydrogen project points so the explorer can render them as proper line infrastructure.
- Substations, transmission lines, gas pipelines, gas import points, hydrogen projects, hydrogen pipelines, power plants, and Natura 2000 areas now form the honest Greece-wide infrastructure and context baseline.
- Candidate generation continues to build on top of these backend-owned source layers.
