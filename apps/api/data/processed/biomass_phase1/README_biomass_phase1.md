# Biomass Phase 1

This folder contains the first staged biomass/biogas/CHP extraction from local RAAEY files.

## How to run

```bash
python pipeline/run_biomass_phase1.py
```

## Outputs

- `raaey_biomass_candidates.csv`
- `raaey_biomass_candidates.json`
- `biomass_candidates_for_review.json`
- `biomass_phase1_quality_report.json`
- `biomass_phase1_summary_by_technology.csv`
- `biomass_phase1_summary_by_region.csv`
- `validation/*.json`
- `../../manual/biomass_manual_points.json`

## Meaning

- RAAEY records represent the licensing/application universe, not proof of operation.
- `derived_status` should only be upgraded by stronger validation sources such as ADMIE.
- `biomass_manual_points.json` can hold manual geolocation evidence for licensed biomass/biogas projects.
- Manual points do not create fake plants. They only enrich a matched record or remain listed as unmatched evidence.
- Current extracted record count: 180
- Current missing capacity count: 0
- Current manual location entries: 24
- Current manual location matches: 21
