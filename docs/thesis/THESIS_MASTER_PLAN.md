# Diploma Thesis — Master Architecture & Structure Plan

> **Who this document is for.** An AI writing agent (Claude Code) that will draft, build and finish the
> diploma thesis in 1–2 days, working with the author (Antonis Troullos). It records everything
> built so far, where it lives, what can be claimed and what can't, and the order to write in.
>
> **Status of this document:** snapshot taken 2026-09-30 from both codebases. The author's
> university regulations and structure are **not included yet**. See §0.2: those rules
> **override** every structural default below.

---

## 0. Operating instructions for the writing agent

### 0.1 Workspace

The work is spread over **two separate repositories**. The agent must be able to read both:

| Alias used below | Absolute path | Role |
|---|---|---|
| `PLATFORM` | `C:\Users\megas\dev\energy-investment-platform` | Data platform, FastAPI backend, Next.js/MapLibre UI, IPTO load pipeline, candidate screening, investment analysis |
| `MODEL` | `C:\Users\megas\PycharmProjects\pythonProject1` | Demand forecasting (ENTSO-E, XGBoost), regional allocation, PyPSA electricity model (`pypsa-greece/`), coupled electricity/gas/H₂/heat model, investment economics, scenario artifacts |
| `THESIS` | `PLATFORM\thesis\` (to be created) | The thesis source (LaTeX or DOCX, whichever the regulations require) |

Start Claude Code in `PLATFORM` and add `MODEL` as an extra working directory (`/add-dir` or
`--add-dir`), or start it in `C:\Users\megas` and name both paths.

### 0.2 Precedence of rules (highest first)

1. **The university / department regulations the author provides** (structure, length, language,
   formatting, citation style, mandatory sections, declaration pages, AI-use policy).
2. **The author's explicit instructions in chat.**
3. **This document.**
4. The agent's own defaults.

When (1) conflicts with §8 (proposed structure), keep the **content map** in §8 and fit it into the
required chapter skeleton.

### 0.3 Non-negotiable writing rules

These come from the project's own engineering culture. Both codebases already enforce the same ideas.

1. **No invented numbers.** Every quantitative claim is traced to a file in `PLATFORM` or `MODEL`
   (result JSON, CSV, test output) or to a cited external source. Keep a `numbers_ledger.csv`
   (claim → value → file path / citation) in `THESIS/`. Re-derive numbers from files, not from the
   prose in this plan. The prose may be stale.
2. **No invented citations.** Every reference must be verified (web search / DOI lookup) before it
   goes in the `.bib`. The seed list in §10 is a starting point, not verified bibliographic data.
3. **Provenance classes are part of the argument.** Every input is described as one of
   `measured`, `sourced`, `derived`, `scenario_assumption`, `placeholder`. This is the class set
   the coupled-model spec defines (`MODEL/docs/superpowers/specs/2026-09-26-coupled-pypsa-model-redesign.md`).
   Placeholders are never presented as data.
4. **Planning results are not market forecasts.** Nodal duals are "planning shadow prices." NPV/IRR
   are "planning economics," not bankable valuations.
5. **Limitations are a strength, not an embarrassment.** The project deliberately surfaces gaps
   (§7). The thesis keeps that stance.
6. **Stop conditions:** when you are missing data, find an ambiguous source, or hit a conflict
   between results, **stop and ask the author**. Do not choose silently. The same rule governs
   the model code.
7. **Both codebases are read-only** (frozen at tag `thesis-v1`, §7.2 D4). The only new code is
   the figure/table/number-extraction scripts under `THESIS/scripts/`. No model re-solves.

---

## 1. Thesis identity (proposal — confirm with author)

**Working title (EN):**
*An Open, Data-Driven Decision-Support Platform for Energy Investment Planning in Greece:
Integrating Geospatial Screening, Demand Forecasting and Sector-Coupled PyPSA Optimisation*

Alternatives:
- *From Infrastructure Registries to Investment Decisions: A Transparent Energy-System Modelling Platform for Greece*
- *Spatially-Explicit, Sector-Coupled Capacity Planning and Investment Screening for the Greek Energy Transition*

**Central research question.**
How can publicly available Greek energy, geospatial and market data be combined with open-source
energy-system optimisation to give transparent, reproducible, location-specific investment
decision support, and what do such models reveal about where and in what to invest in Greece?

**Sub-questions (each maps to a results section):**
- RQ1 — *Data:* How complete and consistent are Greek public registries (RAAEY, GEM, OSM, DAPEEP,
  Greek Energy Map, IPTO/ADMIE, ENTSO-E) for building an energy-system model? Where is the
  licensed-vs-built gap?
- RQ2 — *Demand:* How accurately can national hourly load be forecast from public data, and how
  can it be regionalised defensibly without metered regional data?
- RQ3 — *System optimisation:* What least-cost dispatch and capacity-expansion patterns come out
  of a 13-region (plus clustered) PyPSA model of Greece, and how sensitive are they to temporal
  aggregation?
- RQ4 — *Sector coupling:* What happens when hydrogen, gas and incremental heat are coupled to
  electricity under strict energy-accounting conventions?
- RQ5 — *Siting & investment:* Which locations and technologies are attractive once real regulatory
  constraints (Natura 2000, draft RES spatial framework) and solved-model prices feed a
  project-level DCF (NPV/IRR/LCOE)?

**Claimed contributions:**
1. An integrated, open pipeline from public Greek registries to a solvable PyPSA model, with
   explicit provenance for every input.
2. A reconciled Greek generator inventory (multi-source merge and deduplication, calibration to
   DAPEEP totals, capacity-weighted clustering into 99–107 clusters).
3. A spatial candidate-screening method that carves real Natura 2000 and draft RES-framework
   exclusions out of the candidate geometry (~11 km grid, 718 cells).
4. A sector-coupled planning formulation (electricity–H₂–gas–heat) with dimensional conventions
   (HHV/LHV, input-side link capacity), strict validation and solver-status handling.
5. Linking model outputs to project finance: captured-price DCF with degradation, per-site and
   portfolio IRR.
6. A web decision-support interface (map explorer, Scenario Studio, spatial results, investment
   memo export) that makes the model usable by non-modellers, with automatic result-staleness
   detection.

---

## 2. Register of the work done (inventory)

### 2.1 Timeline

| Period | Where | Milestone |
|---|---|---|
| early (pre-Jul 2026) | MODEL | `PyPSA_First_Try.py`: 5-region prototype |
| Jul 2026 | MODEL `pypsa-greece` | 13-region stylised model; capacity expansion; `metrics.py` (KNOWLEDGE_TRANSFER §4, §17) |
| 25–26 Jul 2026 | both | Real generator clustering (99 clusters), clustered topology (112–114 buses), real per-cluster weather, researched cost table, Greek Energy Map integration (§18–21) |
| 18–19 Aug 2026 | both | Phase 0 (Natura fix, cost-table restructure, Link/Store support); Phase 1 spatial constraints; seasonal representative days (36 days / 864 snapshots); Phase 2 investment economics, Scenario B (§22–24) |
| 19 Aug 2026 → | MODEL | Gas / H₂ / heating market models, Phases A–D (§25) |
| ~20–26 Aug 2026 | MODEL | ENTSO-E pipeline, XGBoost next-day forecasting, demand orchestrator, technical report (`MODEL/reports/`) |
| 28 Aug 2026 | MODEL | Initial git snapshot |
| 25–26 Sep 2026 | MODEL | Integrated architecture spec; **coupled PyPSA redesign** (13 tasks, 160→167 tests); scenario-artifact contract; flexible demand, datacenters, spatial MILP, investment-cost records |
| 20 Sep 2026 | PLATFORM | Git history (re)started: scaffolding, IPTO pipeline, asset pipeline, PyPSA bridge, map explorer, Scenario Studio |
| 26 Sep 2026 | PLATFORM | Scenario options from CSV, dev tooling, staleness flags, network topology & regional metrics, spatial results, real land-constraint polygons, 11 km grid, Scenario Wizard |
| 27 Sep 2026 | PLATFORM | Real IRR/NPV/LCOE per candidate; portfolio IRR; investment-memo export |

The dates come from git logs and `MODEL/pypsa-greece/KNOWLEDGE_TRANSFER.md`. Check them with
`git log` in both repositories before quoting.

### 2.2 Component register

Maturity: **●** production-quality and tested · **◐** working, with caveats · **○** scaffold/diagnostic only

| # | Component | Location | Size | Maturity | Thesis use |
|---|---|---|---|---|---|
| C1 | IPTO/ADMIE national load pipeline (download, parse, QC, impute) | `PLATFORM/src/data/*`, `scripts/download_ipto_system_load.py`, `scripts/postprocess_national_load.py` | ~1.8k LOC | ● | Ch. Data: demand baseline, QC method |
| C2 | Canonical generator merge (OSM + GEM ×3 + gov. registries + RAAEY + pumped-hydro seed + biomass) | `PLATFORM/apps/api/app/generators.py` | 2.7k LOC | ● | Ch. Data: inventory reconciliation |
| C3 | Registry importers (GEM wind/solar/hydro, gov. PV/wind/storage, RAAEY fossil/H₂, OSM power/admin/regional units/islands, Greek Energy Map) | `PLATFORM/apps/api/pipeline/*.py` | ~6k LOC | ● | Ch. Data |
| C4 | Biomass phase-1 ETL (180 records, EGSA87→WGS84, cross-checks) | `PLATFORM/apps/api/app/biomass_phase1.py` | 1.6k LOC | ● | Ch. Data (case study of registry messiness) |
| C5 | Regional demand allocation (Eurostat proxies, sector × season shares) | `PLATFORM/apps/api/app/regional_demand.py`, `MODEL/src/energy_data/regional_allocation.py`, `regional_features.py` | ~1.1k LOC | ◐ | Ch. Methods: demand regionalisation |
| C6 | ENTSO-E ingest + demand forecasting (seasonal naive, Fourier, calendar XGBoost, SARIMAX, RF, LSTM, weather-aware next-day XGBoost) | `MODEL/src/energy_data/entsoe_*.py`, `demand_forecast.py`, `short_term_forecast.py`, `forecast_evaluation.py`, `demand_orchestrator.py` | ~1.7k LOC | ◐ (no rolling backtest yet) | Ch. Methods/Results: forecasting |
| C7 | Weather → availability (Open-Meteo archive; PV irradiance ratio; generic wind power curve 3/12/25 m/s; HDD) | `MODEL/pypsa-greece/src/weather_profiles.py`, `scripts/fetch_cluster_weather_profiles.py`, `MODEL/src/energy_data/weather_data.py` | ~400 LOC | ◐ | Ch. Methods |
| C8 | Generator clustering (point-in-polygon bus assignment, DAPEEP calibration, capacity-weighted k-means, grid distances, voltage-class line ratings) | `MODEL/pypsa-greece/src/generator_clustering.py`, `scripts/build_generator_clusters.py`, `generate_clustered_network_inputs.py` | ~0.9k LOC | ● | Ch. Methods: spatial aggregation |
| C9 | Representative-period selection (wind-tercile stratified, 3 days/month; monthly days; seasonal weeks; linked periods; chronology expansion) | `MODEL/pypsa-greece/scripts/select_representative_days.py`, `MODEL/src/energy_data/linked_representative_periods.py`, `seasonal_storage_chronology.py` | ~0.6k LOC | ◐ | Ch. Methods: temporal aggregation |
| C10 | PyPSA electricity model (13-bus baseline, 112–114-bus clustered variant, capacity expansion, HiGHS) | `MODEL/pypsa-greece/src/build_network.py`, `run_model.py`, `solve_network.py`, `metrics.py`, `config/*.yaml` | ~0.8k LOC | ● | Ch. Methods + Results core |
| C11 | Standalone gas / H₂ / heating market models (Phases A–D) | `MODEL/pypsa-greece/src/{gas_market,hydrogen_market,heating_demand}.py`, `scripts/build_*` | ~0.9k LOC | ○ diagnostic (superseded by C12) | Background / "evolution of the approach" |
| C12 | **Coupled electricity–gas–H₂–heat planning model** (energy conventions, schema, inputs, constraints, validation, metrics, strict solver) | `MODEL/pypsa-greece/src/coupled_*.py`, `energy_conventions.py`, `MODEL/scripts/build_and_solve_coupled_year.py` | ~2.3k LOC | ● code / ◐ production run (§7.2) | Ch. Methods: centrepiece formulation |
| C13 | Scenario-artifact contract (hashing, manifest, validation, provenance) | `MODEL/src/energy_data/scenario_artifact_*.py`, `scenario_contract.py` | ~0.5k LOC | ● | Ch. Implementation: reproducibility |
| C14 | Extensions: flexible demand blocks, datacenters, thermal controls, spatial site-selection MILP, investment-cost records, portfolio report | `MODEL/src/energy_data/{flexible_demand,datacenter_inputs,thermal_controls,spatial_portfolio,investment_costs,investment_portfolio}.py` | ~0.6k LOC | ◐ unit-tested, not used in headline results | Ch. Methods (short) + Future work |
| C15 | Spatial constraint rules (Natura 2000 Habitats/Birds, draft May-2026 RES framework: wind >1200 m, islands <300 km², Attica/Thessaloniki; solar Natura ban, 1.5 % RU cap, UNESCO 1.5 km) | `MODEL/pypsa-greece/src/spatial_constraints.py`, `PLATFORM/apps/api/pipeline/land_constraints.py` | ~0.5k LOC | ● | Ch. Methods: siting |
| C16 | Candidate-cell generation (~0.1° grid, 718 cells; buildable polygon = cell − exclusions; distances to substations/lines; score) | `PLATFORM/apps/api/pipeline/generate_candidates.py` | 0.6k LOC | ◐ (resource score still from 3-zone placeholder) | Ch. Methods/Results: screening |
| C17 | Investment economics: cluster DCF (captured revenue Σ dispatch·price·weight, degradation 0.5 %/1.0 %/yr, CRF annuities) | `MODEL/pypsa-greece/src/investment.py`, `scripts/evaluate_cluster_investment.py`, `battery_economics.py`, `solar_portfolio.py` | ~0.4k LOC | ◐ | Ch. Results: investment |
| C18 | Candidate investment analysis & portfolio IRR (combined cash flows) | `PLATFORM/apps/api/app/investment_analysis.py` | 0.6k LOC | ◐ (national CF, regional avg price) | Ch. Results: investment |
| C19 | PyPSA bridge (subprocess runner, result normalisation, status/staleness) | `PLATFORM/apps/api/app/{scenario_runner,scenarios,staleness,scenario_options,network_topology}.py`, `pypsa_bridge/` | ~1.1k LOC | ● | Ch. Implementation: architecture |
| C20 | Web UI: map explorer (layers, search, drawer, clustering), candidate screening, Scenario Studio / Wizard, results charts, spatial results choropleth, scenario comparison, investment panel, portfolio, memo export | `PLATFORM/apps/web/**` | ~11.7k LOC TS/TSX | ● | Ch. Implementation + Demonstration |
| C21 | Market signal (live IPTO price & interconnector flows) and climate panel (Open-Meteo current + heuristic) | `PLATFORM/apps/api/app/{market,climate}.py` | ~0.5k LOC | ○ context only | Brief mention |
| C22 | Dev tooling: `npm run dev/doctor/test`, env-configurable settings, `/system/status` | `PLATFORM/scripts/*.mjs`, `apps/api/app/{settings,system_status}.py` | ~0.7k LOC | ● | Ch. Implementation: reproducibility |
| C23 | Test suites | `PLATFORM/apps/api/tests` (191 test functions), `MODEL/tests` (179 test functions; last full run 167/167 per SDD ledger) | — | ● | Ch. Validation |

### 2.3 Existing documents to mine (read these first, in this order)

1. `MODEL/pypsa-greece/KNOWLEDGE_TRANSFER.md`: the narrative history, §1–25. **Richest source.**
2. `MODEL/docs/superpowers/specs/2026-09-26-coupled-pypsa-model-redesign.md`: coupled formulation, conventions, equations, validation rules.
3. `MODEL/docs/superpowers/specs/2026-09-25-integrated-energy-investment-architecture-design.md`: overall architecture and theory decisions.
4. `MODEL/reports/greece_energy_model_technical_report.html`: forecasting, allocation and PyPSA equations; next-day case results.
5. `MODEL/docs/superpowers/plans/*.md` and `MODEL/.superpowers/sdd/*/progress.md`: implementation logs and rulings.
6. `MODEL/pypsa-greece/NETWORK_OVERVIEW.md`: 13-region topology (Mermaid graph with line ratings).
7. `PLATFORM/README.md`, `apps/api/README.md`, `apps/api/data/README.md`: data contracts per layer.
8. `PLATFORM/data/processed/national_load/{README,POSTPROCESSING_README}.md`: IPTO QC methodology.
9. `PLATFORM/apps/api/data/processed/biomass_phase1/README_biomass_phase1.md`.
10. Module docstrings: `investment_analysis.py`, `land_constraints.py`, `staleness.py`, `network_topology.py`, `scenario_options.py` all carry method rationale in prose.

`PLATFORM/PROJECT_CONTEXT.md` is **stale**. It says "mock data, no backend." Use it only to
describe the project's early phase, never the current state.

---

## 3. As-built system architecture

### 3.1 Layered view (thesis Figure: "System architecture")

```
┌────────────────────────── PUBLIC DATA SOURCES ──────────────────────────┐
│ IPTO/ADMIE (load, price, flows) · ENTSO-E (actual load) · RAAEY registries │
│ GEM trackers · OSM (grid, admin, islands) · DAPEEP · DESFA · Greek Energy │
│ Map · Natura 2000 · UNESCO · Eurostat · Open-Meteo (weather, elevation)  │
│ NECP 2024 · ELSTAT · IRENA/Lazard/DEA/TYNDP/JRC cost literature          │
└───────────────┬───────────────────────────────────┬──────────────────────┘
                │ importers / ETL (PLATFORM)        │ fetch + forecast (MODEL)
                ▼                                   ▼
┌──────────── DATA PRODUCTS ─────────────┐  ┌────────── DEMAND & WEATHER ─────────┐
│ 27 GeoJSON source layers (apps/api/data)│  │ national load (IPTO, ENTSO-E)       │
│ canonical generator feed + QA reports   │  │ XGBoost / Fourier / SARIMAX models  │
│ candidate cells (718, constraint-carved)│  │ 13-region allocation (Eurostat)     │
│ regional features, biomass staging      │  │ p_max_pu per region / cluster, HDD  │
└──────────────┬─────────────────────────┘  └───────────────┬─────────────────────┘
               │ HTTP snapshot (fetch_real_generators.py)    │
               ▼                                             ▼
┌──────────────────── MODELLING ENGINE (MODEL/pypsa-greece) ─────────────────────┐
│ clustering → network inputs → versioned scenario artifact (hash, manifest)     │
│ PyPSA LP (HiGHS): electricity 13-bus / clustered 114-bus; capacity expansion   │
│ coupled electricity–gas(HHV)–H₂(LHV)–heat; policy/trade constraints; storage   │
│ pre/post-solve validation → metrics → investment DCF                            │
└──────────────────────────────┬─────────────────────────────────────────────────┘
                               │ subprocess + result files (scenario_result.json)
                               ▼
┌──────────────────── PLATFORM API (FastAPI, apps/api) ───────────────────────────┐
│ ~50 endpoints: layers, generators/QA, regional demand, scenario run/status/      │
│ result/compare/map, coupled run, candidate investment, portfolio, system status  │
│ staleness assessment (mtime watchlists)                                          │
└──────────────────────────────┬─────────────────────────────────────────────────┘
                               ▼
┌──────────────────── WEB UI (Next.js 16, React 19, MapLibre 5, Recharts) ────────┐
│ Map explorer · candidate screening & compare · Scenario Studio/Wizard ·          │
│ results charts · spatial results choropleth · investment panel · portfolio ·     │
│ investment memo (print/export)                                                    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Key design decisions (each gets a paragraph in the Implementation chapter)

| Decision | Rationale (source) |
|---|---|
| API calls the PyPSA project as a **subprocess**, not an import | Keeps `apps/api` free of pandas/pypsa/linopy/highspy (`PLATFORM/README.md` "The PyPSA bridge") |
| File-backed GeoJSON/CSV, no database | Simplicity and transparency; `lru_cache` for performance |
| HTTP-snapshot pattern (API → timestamped snapshot → model) | Reproducible model inputs with a manifest (`fetch_real_generators.py`) |
| Scenario artifact as the boundary between data and model | Hashes, provenance, validation before solve (integrated architecture spec) |
| Strict solver acceptance (`SolveResult.accepted`) | Infeasible/non-optimal never reported as success (coupled spec) |
| Input-side `Link.p_nom` convention, HHV gas / LHV H₂ | Dimensional consistency (coupled spec, `energy_conventions.py`) |
| Existing vs candidate assets as separate components | No double-counting CAPEX (commit `47653a6`) |
| Staleness by modification time | Conservative: a false "stale" costs a re-solve; a false "fresh" misleads (`staleness.py`) |
| Scenario options read from `h2_market_scenarios.csv` | One source of truth; invalid combos → HTTP 422 (`scenario_options.py`) |
| Draft RES rules duplicated in API and model, not imported | Independent dependency sets (`land_constraints.py` docstring) |

---

## 4. Data register

Produce a table from this list in the Data chapter. **Re-count features from the files** and don't
trust these numbers blindly (they were counted 2026-09-30).

| Dataset | Source | Records | Provenance class | Used for |
|---|---|---|---|---|
| National hourly load 2022–2026-06 | IPTO/ADMIE `RealTimeSCADASystemLoad` | 39,359 rows (model-ready) | measured (+ documented imputation) | demand baseline, allocation |
| Actual total load | ENTSO-E Transparency | 180-day windows / multi-year | measured | forecasting training |
| Power plants (OSM) | OpenStreetMap / Overpass | 7,941 | sourced | generator baseline |
| GEM solar / wind / hydro | Global Energy Monitor trackers (Feb/Mar 2026) | 5,666 / 1,469 / 25 | sourced | generator merge |
| Gov. wind / PV / storage | RAAEY GIS registry exports | 1,954 / 877 / 18 | sourced | generator merge |
| RAAEY operating wind / solar (status 1.3) | geo.rae.gr GeoServer | 437 / 442 | sourced | clustering "existing" fleet |
| Greek Energy Map projects | greekenergymap.org public API | 4,029 | sourced | BESS & pumped hydro status |
| RAAEY fossil | RAAEY | 0 (export empty; kept honestly empty) | — | — |
| Hydrogen projects / pipelines | RAAEY H₂ registry (+ IEA DB for coupled run) | 18 / 3 | sourced | H₂ model |
| Substations / transmission lines | OSM | 3,144 / 1,044 | sourced | distances, voltage classes |
| Gas pipelines / import points | DESFA / curated | 8 / 5 | sourced | gas model |
| Admin regions / regional units / islands | OSM admin_level 5 / 6, place=island | 13 / 74 / 571 | sourced | buses, RU cap, island rule |
| Natura 2000 | EEA | 443 | sourced | exclusions |
| UNESCO sites | curated (19 inscriptions, 23 points) | 23 | derived (points, not zones) | solar study trigger |
| Candidate cells | generated | 718 | derived | screening |
| Resource zones | hand-drawn | 3 | **placeholder** | candidate resource score |
| Biomass phase 1 | RAAEY Excel registries | 180 (24 manual locations, 21 matched) | sourced/derived | biomass fleet |
| Technology costs | IRENA 2024, Lazard v18, DEA, TYNDP 2024, JRC 2024 | 10 carriers | sourced (oil: placeholder) | PyPSA costs, DCF |
| Energy targets | NECP 2024 final, ELSTAT SILC 2023, DESFA 2025 | 26 rows | sourced | heat/H₂/gas scenarios |
| Heating tech costs | literature (EU HP review, UK boiler data) | per year | sourced/derived | heat links |
| Weather | Open-Meteo archive/forecast, elevation API | 13 centroids + 63 clusters | measured (reanalysis) | p_max_pu, HDD, CDD |
| Regional features | Eurostat (population, GDP/GVA, tourism nights, employment, land) | 13 regions | sourced | allocation |

---

## 5. Methods register (the equations the thesis must present)

Each method appears here with: what it is, its equation or algorithm, where the code lives, and
the provenance of its parameters. The agent writes the Methods chapter from this list and
verifies each detail against the code.

### M1 — National load QC and imputation (C1)
Timestamps normalised to Europe/Athens, hour-ending-24 fix; flags for missing, duplicate,
non-positive, outlier and extreme-jump values. Imputation priority: same hour previous week →
mean of adjacent days → short linear interpolation → median fallback. Every repair is recorded
(`was_imputed`, `imputation_method`, `original_value`). Validation: 0 missing, 0 duplicate,
0 non-positive values in the model-ready series. Known source flag: 2025-03-15 11:00–14:00
outlier kept for review.

### M2 — Regional demand allocation (C5)
Sector proxy share $q_{r,s}=\sum_k a_{s,k}\,x_{r,k}/\sum_j x_{j,k}$; monthly share
$w_{r,m}=\sum_s \beta_{s,\text{season}(m)}\,q_{r,s}$ (normalised); regional load
$D_{r,t}=D_t\,w_{r,\text{month}(t)}$. Conservation holds by construction:
$\sum_r D_{r,t}=D_t$. It is always labelled "estimated regional demand allocation," never
"measured." Bug fixed along the way: `historical_national_load_at()` (KT §24).

### M3 — Demand forecasting (C6)
Next-day: `XGBRegressor` (500 trees, depth 5, lr 0.05, 0.9 subsampling, seed 42). Features:
calendar + cyclic terms, lags {1,2,3,24,25,48,72,168}, rolling 24/168 h mean and 24 h max, and
population/load-share-weighted weather ($W_t=\sum_r w_r W_{r,t}$,
$\text{CDD}_t=\max(T^{app}_t-22,0)$). Recursive 24-step prediction. Long-term: the model is
selected by saved MAPE comparison among seasonal-naive, annual-profile, Fourier, calendar-XGBoost,
SARIMAX, RF, LSTM and weather-regression. **Gap:** no rolling-origin backtest yet (§7).

### M4 — Weather → availability (C7)
PV: $p^{\max}_{t}=\min(1,\,G_t/1000\ \text{W m}^{-2})$. Wind: generic power curve on 100 m wind
speed (cut-in 3, rated 12, cut-out 25 m/s). Heating shape from Eurostat HDD
($18-\bar T$ if $\bar T\le15^\circ$C). Hydro: stylised cosine seasonal curve (placeholder,
labelled).

### M5 — Generator reconciliation and clustering (C2, C8)
Multi-source merge with dedup (coordinate bucket + name matching); source-priority rules
(official > GEM > OSM). Dedicated sources per carrier (RAAEY operating licences for wind/solar;
Greek Energy Map for BESS/pumped hydro; biomass phase 1). DAPEEP Dec-2025 calibration for
wind/solar/biomass. Bus assignment by STRtree point-in-polygon (`within`) with nearest-region
fallback. Capacity-weighted k-means per (bus, carrier), ~1 cluster per 15 assets, max 6.
Cluster–hub line $s_{nom}$ from the nearest line's voltage class (e.g. 150 kV ≈ 250 MVA,
400 kV ≈ 1200 MVA), floored above cluster capacity. Headline findings: RAAEY undercounts DAPEEP
solar ~2.5×; wind +13 %; GEM/RAAEY licence registries overstate built capacity (~96 GW / ~49 GW
solar). **A key RQ1 result.**

### M6 — Temporal aggregation (C9)
Representative days are weighted so that $\sum_t \omega_t = 8760$. Variants: 12 monthly days
(288 snapshots), 36 wind-tercile stratified days (864), seasonal weeks (672), linked
representative periods (cyclic month-linked), and chronological expansion. The theory decision is
that a genuine 8,760 h run is the reference, and reduced chronology must be validated against it.
The comparison already on disk (`MODEL/data/processed/pypsa_scenarios/scenario_comparison.csv`)
shows monthly days vs seasonal weeks.

### M7 — PyPSA electricity LP (C10)
Nodal balance $\sum_g p_{g,t}+\sum_s p_{s,t}+\sum_l K_{n,l}f_{l,t}=D_{n,t}$; linearised DC flow
with $|f_{l,t}|\le F_l$; availability $0\le p_{g,t}\le \bar p_{g,t}P_g$; storage SOC
$e_{s,t}=(1-\lambda_s)e_{s,t-1}+\eta^{st}p^{ch}_{s,t}-p^{dis}_{s,t}/\eta^{dis}$, cyclic.
Objective $\min \sum_g c_gP_g+\sum_s c_sP_s+\sum_t\omega_t\big[\sum_g m_g p_{g,t}+\ldots\big]$.
Annuity $c=\text{CRF}(r,n)\cdot\text{capex}+\text{FOM}$,
$\text{CRF}=\frac{r(1+r)^n}{(1+r)^n-1}$. Solver: HiGHS via linopy.

### M8 — Coupled planning model (C12): **methodological centrepiece**
Carriers and bases: electricity MWh_e, heat MWh_th, gas MWh HHV, H₂ MWh LHV. Link convention
$q=\eta f$, $0\le f\le F^{in}$, $F^{in}=F^{out}/\eta$, $c^{in}=\eta\,c^{out}$. Balances for
electricity, H₂, gas and regional heat (copy them from the spec §"Carrier Balances"). Objective
with candidate CAPEX, weighted variable cost and export revenue. H₂ target modes (final demand
$=$ target vs domestic production $\ge$ target). Policy modes: grid electrolysis baseline, hourly
additionality/matching, emissions-intensity threshold. Trade: bounded, anti-arbitrage LP, or MILP
directionality ($z_t$ binary). Acceptance criteria: bus residual $<10^{-6}$ MW, annual relative
imbalance $<10^{-6}$, cyclic closure, no simultaneous import/export. Analytical tests: 1 MWh_e
through a 75 % electrolyser gives 0.75 MWh H₂; COP 3 gives 3 MWh_th; a 93 % boiler gives 0.93.

### M9 — Siting constraints and candidate generation (C15, C16)
Hard exclusions and warnings per technology (list in §2.2 C15). Buildable polygon =
cell ∩ ¬(exclusions), with area measured in EGSA87 (EPSG:2100). Natura overlap fraction is
exposed (past threshold 0.15). Distances to the nearest substation and line use STRtree plus
safe-radius pruning. The draft framework (public consultation until 2026-06-24) is **not
enacted law**; say so every time.

### M10 — Investment economics (C17, C18)
Captured revenue $R=\sum_t p_{g,t}\,\lambda_{n(g),t}\,\omega_t$ (not average price × energy:
this captures cannibalisation). Degraded generation $E_y=E_0(1-\delta)^y$ with
$\delta_{PV}=0.5\%$ (Jordan & Kurtz 2013), $\delta_{wind}=1.0\%$ (range 0.17–1.6 %;
LBNL 2023, Staffell & Green 2014). NPV at 7 % real (a labelled simplification), IRR by root
finding, LCOE and payback. Candidate-cell capacity = area × buildable fraction × power density
(40 MW/km² PV, 6 MW/km² wind; literature, not Greek-specific), capped at 200/100 MW. Portfolio
IRR on combined cash flows (not an average of IRRs).

### M11 — Reproducibility machinery (C13, C19, C22)
Scenario-artifact hashing (path-normalised JSON), manifests, provenance records, staleness
watchlists, `/system/status`, `npm run doctor`.

---

## 6. Results register (what can be reported, with files)

All paths are relative to `MODEL/data/processed/pypsa_scenarios/` unless stated. **Re-extract
every number from the JSON/CSV**; the values below are for orientation only.

| ID | Result | File(s) | Headline (orientation) | Reportability |
|---|---|---|---|---|
| R1 | Registry reconciliation / licensed-vs-built gap | `MODEL/pypsa-greece/data/processed/generator_clusters_report.json`, KT §18/§21 | 99 clusters; solar 7,545 / gas 5,949 / wind 5,016 / lignite 4,769 / hydro 1,851 MW; BESS 0 → 495 MW; PHS 699 → 815 MW | ✅ strong |
| R2 | National load QC | `PLATFORM/data/validation/national_load/*.csv` | 39,359 h clean; anomaly audit | ✅ |
| R3 | Next-day forecasts and dispatch 19/20 Aug 2026 | `orchestrator_next_day_2026081{9,20}_weather/` | 20 Aug: 164.7 GWh, peak 7.70 GW; gas-led | ✅ as functional backtest (not accuracy claim) |
| R4 | Temporal-aggregation comparison | `scenario_comparison.csv`, `mid_2026_monthly_days/`, `long_2026_seasonal_weeks/`, `clustered_*` | objective within ~0.8 %; generation mix similar | ✅ (flag stylised inputs) |
| R5 | Clustered real-fleet annual runs 2026 | `clustered_mid_2026_monthly_days/`, `clustered_long_2026_seasonal_weeks/` | gas ≈ 21 TWh, solar ≈ 7.4, wind ≈ 7.7, hydro ≈ 7.2, lignite 0 | ⚠️ report with the D0 caveat (wind understated, gas overstated) |
| R6 | Cost-driven lignite exit | KT §20, `technology_costs.csv` | lignite €157/MWh > gas €108.8/MWh, so lignite doesn't dispatch | ✅ good discussion point |
| R7 | Future electricity 2030–2050 capacity expansion | `future_electricity_{2030..2050}/` | stylised fleet, hour-of-day fallback profiles | ❌ not a result (D1); capability only |
| R8 | Coupled 2030 (legacy runner) | `future_electricity_2030/coupled_outputs*/` | — | ❌ not a result (D2); qualitative "motivated the redesign" only |
| R8b | Coupled model verification | `MODEL/tests/test_coupled_*`, synthetic 8,760 h case, preflight refusal log | analytical balances hold; synthetic reference optimal; production preflight blocks incomplete inputs | ✅ Chapter 6 |
| R9 | H₂ feasibility vs NECP, bounded | IEA (≈52 MW) vs RAAEY (271.55 MW) × NECP utilisation | 2030 target missed under both bounds at NECP utilisation; 2040/2050 far out of reach | ✅ as a diagnostic finding (D3) |
| R10 | Standalone heating optimum | KT §25 Phase D | heat pumps dominate (~6.4 GW); balance 49.03 TWh | ⚠️ diagnostic model, superseded by coupled spec |
| R11 | Gas balance round-trip | KT §25 Phase B | 78.75 TWh imports = 70.16 domestic + 8.59 export | ✅ validation example |
| R12 | Spatial-constraint QA on the existing fleet | `generator_clusters_spatial_constraints.csv`, `spatial_constraints_report.json` | 1/29 wind excluded, 4/34 solar excluded, Acropolis trigger at 0.6 km | ✅ |
| R13 | Cluster investment evaluation (Scen. A vs B) | `MODEL/pypsa-greece/data/processed/cluster_investment_evaluation.csv` (77 rows) | biomass/hydro NPV+; solar mostly NPV+ (captured ≈ €40–45/MWh vs system ≈ €80–108, i.e. cannibalisation); wind withheld | ⚠️ solar/hydro/biomass as upper bounds (D0); cannibalisation sign is robust; wind NPV/IRR not reported |
| R14 | Candidate-cell screening and investment | API `/candidates`, `/candidates/investment-analysis`, `/candidates/portfolio-analysis` | 718 cells; per-cell NPV/IRR/LCOE; portfolio IRR | ✅ (flag national CF and placeholder resource score) |
| R15 | Software quality | test suites | 191 + 179 test functions; coupled redesign 160/160 → 167/167 | ✅ |
| R16 | UI demonstration | screenshots of running app | map, Scenario Studio, spatial results, memo | ✅ (capture them in phase 2) |

---

## 7. Honesty register — limitations, inconsistencies, open decisions

### 7.1 Limitations to state in the thesis (the Discussion chapter must cover each one)
- The 13-region network and line ratings are **stylised** corridors, not the real ADMIE topology;
  corridor drawings on the map are schematic.
- Regional demand is proxy-allocated, not metered.
- Forecast accuracy has not been shown by rolling-origin backtests.
- No unit commitment, ramping, reserves, outages or hydro water budgets; this is planning
  economics, not market simulation.
- Representative days vs 8,760 h: reduced chronology has not been validated quantitatively against
  a genuine 8,760 h reference yet.
- Wind availability in all solved runs is about 3× below observed output, because of a
  power-curve defect plus centroid smoothing (D0). The fix and calibration are committed but not
  applied. Future-year runs used hour-of-day mean profiles (D1).
- Hydro seasonal curve is stylised. Oil marginal cost and the biomass/small-hydro costs are
  weak or placeholder.
- The discount rate is a uniform 7 %; technology-specific WACC is not modelled.
- Candidate resource scores still come from the placeholder `resource_zones.geojson`
  (3 polygons). Candidate economics use the national capacity factor and the regional
  all-technology average price.
- The spatial rules are a **draft** framework (May 2026), not law. The municipal wind cap and
  settlement setback are not implemented (sources disagree or give no value). UNESCO sites are
  points, not zones.
- Standalone gas/H₂/heat models are diagnostic and must not be summed with coupled results.
- Storage NPV (arbitrage) is not integrated in the headline DCF.

### 7.2 Resolved decisions (final, 2026-09-30, agreed with the author)

**Constraint:** there is no time for model rebuilds or re-solves. The thesis is written from the
results that exist at tag `thesis-v1`. Each decision below therefore controls **how** a result is
reported, not whether it gets regenerated.

**Reporting rule:** a number is presented as a *finding* only if it comes from a run that is valid
under the project's own standards. A number affected by a known defect can appear only together
with that defect, the direction of its bias, and the fix. It is never a headline.

#### D0: Wind availability is about 3× too low in every solved run. Disclose it; do not re-run.
- **Evidence.** Mean wind `p_max_pu` is 0.071 in `pypsa-greece/data/timeseries/wind_pu_regional.csv`
  (and in all `future_electricity_*` inputs) and 0.078 in `wind_pu_clustered.csv`. Solved fleet wind
  CF is **8.0 %** in `future_electricity_2030` and about **17.5 %** in the clustered 2026 runs
  (7.67 TWh / 5,016 MW). The observed benchmark is the DAPEEP 2025 annual bulletin
  (`PLATFORM/apps/api/data/raw/dapeep/34_ANNUAL_2025_min_DELTIO_ELAPE-1.pdf`, wind columns of the
  monthly table): **10,145 GWh** from about 4,750–4,946 MW, i.e. CF ≈ **24 %** (net of curtailment).
  The monthly figures are transcribed in `MODEL/pypsa-greece/scripts/calibrate_wind_profiles.py`,
  and `dapeep_2025_wind_capacity_factor()` computes the CF. Use that function; do not recompute by hand.
- **Cause.** The old `wind_p_max_pu` computed `((v − 3)/9)³`, which cubes the speed *fraction*,
  instead of the power law `(v³ − 27)/(1728 − 27)` (0.088 vs 0.186 at 7 m/s). Region-centroid
  reanalysis smoothing adds to the error.
- **Status at `thesis-v1` (commit `455fa7f`).** The corrected curve, an exact legacy→standard remap,
  a bisection calibration to an observed CF, and 7 unit tests are **committed but not applied**. The
  committed profiles and every solved result still use the old curve.
- **How to write it.**
  - **Chapter 6 (Validation)** gets a subsection "Benchmarking wind availability against observed
    output": the benchmark, the 3× gap, the diagnosis, the corrected equation, and the calibration
    method. Present this as validation working as intended, because it found a real error.
  - **Chapter 7:** every wind-dependent number carries the caveat. State the bias direction:
    - wind generation and wind revenue are **understated**;
    - gas dispatch and system prices are **overstated**;
    - solar/hydro/biomass captured prices and NPVs are therefore **biased upward**. Treat them as
      *upper bounds*. Where the sign of a comparison is robust (solar captured price well below the
      system average, i.e. cannibalisation), say so; where it isn't, don't claim it.
  - **Wind investment results (NPV/IRR, low-CF clusters, "wind mostly unprofitable") are withheld
    as findings.** Explain why in one paragraph and point to future work.
  - **Chapter 9 Future Work, item 1:** apply `calibrate_wind_profiles.py` and re-run.

#### D1: Future-year (2030–2050) electricity runs are NOT results
- **Evidence.** They use the stylised 13-bus fleet (gas 12,040 / solar 8,920 / wind 7,970 MW)
  instead of the reconciled fleet (5,949 / 7,545 / 5,016 MW). They use the D0 wind profiles. And
  because their 2030+ timestamps never match the 2025 weather file, **every snapshot fell back to an
  hour-of-day mean profile** (`pypsa_scenario_builder._select_profile_rows_with_metadata`,
  `method: hour_of_day_mean`), so there is no seasonal or day-to-day variability. The flat 9,020 MW
  of wind isn't a bound (p_nom_max totals 21,100 MW); it follows from these input problems.
- **How to write it.** Leave them out of Chapter 7. Describe the long-term-year pipeline
  (forecast → allocation → representative days → solve) as a platform capability in Chapters 4–5.
  The hour-of-day fallback goes in the limitations: the weather year must be declared, which is
  exactly what the coupled spec's temporal contract requires. Future Work: build on the reconciled
  fleet with a declared weather year.

#### D2: The coupled 2030 output does **not** count as a result
- **Evidence.** It was written 2026-09-26 00:41, before the redesign commits (`d8d7dd9`–`1f957b0`,
  21:24–21:34 the same day), by the legacy runner. It shows the rejected behaviour: total heat
  49.03 TWh instead of incremental useful heat only, and the 0.18 TWh H₂-in-heat subtraction. It
  has no manifest or validation record. Task 13 (SDD ledger) recorded that the strict production
  run was **blocked** by missing inputs.
- **How to write it.** The coupled model is a **methodological contribution** (Ch. 4.7, Ch. 6),
  supported by:
  - the formulation and conventions;
  - the analytical tests (electrolyser 0.75, COP 3, boiler 0.93, no double counting);
  - the synthetic 8,760 h reference case (optimal);
  - the acceptance criteria;
  - the fact that the preflight **correctly refused** incomplete Greek inputs.

  The legacy run appears only qualitatively, in an "evolution of the approach" subsection, as the
  case whose accounting problems (composite €108.8/MWh used as the gas commodity price, the
  disappearing H₂-for-heat share, total instead of incremental heat) motivated the redesign. The
  production coupled run goes to Future Work, with the missing inputs listed.

#### D3: Electrolysers: IEA (status-filtered) as the base case, RAAEY as the licensed upper bound
- **Evidence.** The code makes the IEA DB the sole production source (`hydrogen_market.py`,
  statuses `{"Operational", "FID/Construction"}`, "user-designated"): 3 projects, about **52 MW**
  (Peloponnese 50, Attica 1, Central Macedonia 1.12). RAAEY licences cover 16 projects, **271.55 MW**.
- **How to write it.** Report the NECP hydrogen feasibility check as capacity arithmetic across both
  bounds, using the NECP-implied utilisation (0.92 TWh / 231 MW ≈ 45.5 %). Compute it by script and
  record it in the ledger. Even the RAAEY upper bound (≈1.08 TWh/yr) falls short of the 2030
  1.2 TWh target, and 2040/2050 (5.6 / 20.2 TWh) are far out of reach under either bound. This
  arithmetic doesn't depend on the wind defect. Present it as a diagnostic, not a coupled
  optimisation result.

#### D4: Freeze. **Done.**
- `MODEL`, branch `thesis-freeze`, tag **`thesis-v1`** → `455fa7f`:
  - `3d3970c` freeze of in-progress work (full suite 179/179 pass);
  - `14fe103` archive of the pre-redesign and stylised-fleet outputs, labelled "not thesis results";
  - `455fa7f` corrected wind curve and calibration tooling (not applied; 7/7 tests pass).
- `PLATFORM`: tag **`thesis-v1`** on `master` (`baa2198`, the code state the thesis describes).
  The plan itself lives on branch `claude/thesis-architecture-plan-ea72aa`.
- The appendix "Software availability" cites both tags and hashes. Both codebases are **read-only**
  from here on.

#### Minor items
5. **Two scenario-contract implementations.** Describe `scenario_artifact_*` as the contract and
   `scenario_contract.py` as the thin integrated-plan entry point.
6. **Thesis language / format.** Take them from the regulations.

### 7.3 Results that stand as findings (after D0–D3)
| Strength | Results |
|---|---|
| **Strong, unaffected by D0** | R1 registry reconciliation / licensed-vs-built gap · R2 load QC · R3 next-day forecast pipeline (functional backtest) · R6 lignite-vs-gas cost ordering · R9 H₂ bounds (D3) · R11 gas balance round-trip · R12 spatial-constraint QA · R14 candidate screening geometry (areas, exclusions, distances) · R15 tests · R16 UI |
| **Reportable with the D0 caveat (bias direction stated)** | R4 temporal-aggregation comparison (relative differences only) · R5 clustered 2026 dispatch · R13 solar/hydro/biomass NPV (upper bounds), cannibalisation sign · R14 candidate economics (solar only) |
| **Not findings** | R7 future years (D1) · R8 coupled legacy run (D2) · R10 standalone heating optimum (diagnostic) · wind NPV/IRR (D0) |
---

## 8. Proposed thesis structure (default; adapt to the regulations)

Target: **~90–120 pages** of main text (adjust to the regulations). Page budgets are indicative.

**Front matter:** title page · declaration of authorship · (AI-use disclosure, if the institution
requires one) · acknowledgements · abstract (EN) · περίληψη (GR) · keywords · table of contents ·
lists of figures, tables and abbreviations · nomenclature (symbols from §5).

| Ch. | Title | Pages | Content map (sources) | Figures / tables |
|---|---|---|---|---|
| 1 | Introduction | 6–8 | Greek energy transition context (NECP 2024, lignite phase-out, RES growth, H₂ ambitions); investor question "what, where, why"; problem: fragmented data, opaque models; RQ1–RQ5; contributions (§1); thesis outline | F1.1 Greek generation mix / targets |
| 2 | Background & Literature Review | 14–18 | Energy-system optimisation models (PyPSA, PyPSA-Eur, TIMES, OSeMOSYS, Calliope); capacity expansion theory; temporal aggregation (representative days, Kotzur, Poncelet, Hoffmann); sector coupling (P2X, heat pumps); load forecasting (XGBoost, SARIMAX, LSTM); spatial MCDA and RES siting; project finance (NPV/IRR/LCOE, captured price, cannibalisation); Greek regulatory setting (Law 4685/2020, draft RES spatial framework, Natura 2000); research gap | T2.1 comparison of ESOMs; T2.2 literature matrix |
| 3 | Data: Sources, Processing & Quality | 12–15 | §4 register; M1; M5 reconciliation; licensed-vs-built gap (R1); biomass phase 1; provenance classes; QA reports | F3.1 data-flow diagram; T3.1 data register; F3.2 load series and QC; T3.2 capacity by source vs DAPEEP; F3.3 map of reconciled fleet |
| 4 | Methodology | 20–25 | 4.1 overall framework (§3.1) · 4.2 demand forecasting (M3) and regional allocation (M2) · 4.3 weather-to-availability (M4) · 4.4 spatial aggregation and clustering (M5) · 4.5 temporal aggregation (M6) · 4.6 PyPSA electricity LP (M7) · 4.7 coupled model (M8) · 4.8 siting constraints and candidates (M9) · 4.9 investment economics (M10) · 4.10 scenario design (Scenario A/B; target years; H₂ modes) | F4.1 pipeline; F4.2 13-bus topology; F4.3 coupled topology; F4.4 wind power curve; F4.5 candidate carving example; T4.1 cost table; T4.2 scenario matrix; T4.3 siting rules |
| 5 | System Design & Implementation | 10–14 | architecture (§3); design decisions (§3.2); API design (endpoint table); PyPSA bridge and staleness; UI walkthrough; reproducibility (artifacts, hashes, doctor); testing strategy (C23) | F5.1 architecture; F5.2 component diagram; F5.3–5.8 UI screenshots; T5.1 endpoints; T5.2 test coverage |
| 6 | Validation | 6–8 | analytical tests (M8 checks); energy-balance closures (R11, 149,905 = 149,905 MWh); calibration to DAPEEP/DESFA; spatial QA on the existing fleet (R12); temporal-aggregation comparison (R4); solver-status discipline | T6.1 validation checks; F6.1 aggregation comparison |
| 7 | Results | 15–20 | 7.1 current system 2026 (R5, R6) · 7.2 short-term dispatch cases (R3) · 7.3 future-year expansion (R7, framed per §7.2) · 7.4 sector coupling and H₂ (R8–R10) · 7.5 siting and investment (R12–R14): regional NPV/IRR maps, cannibalisation, Scenario A vs B · 7.6 platform demonstration (R16) | F7.x dispatch stacks, price maps, capacity bars, NPV maps, IRR distributions; T7.x key metrics |
| 8 | Discussion | 6–8 | answer RQ1–RQ5; implications for investors and policy (solar cannibalisation → storage/hybrid value; H₂ target infeasibility with today's pipeline; heat-pump economics); limitations (§7.1); threats to validity | T8.1 limitation → impact → mitigation |
| 9 | Conclusions & Future Work | 3–4 | summary of contributions; future work: 8,760 h reference, real ADMIE topology, rolling backtests, unit commitment and market tier, storage NPV, MILP portfolio (C14), datacenters, LLM scenario translation (original vision) | — |
| — | References | — | verified BibTeX | — |
| A | Appendices | 10–20 | A: full cost table with citations; B: data-contract schemas; C: API endpoint list; D: config files; E: test inventory; F: software availability and commit hashes; G: additional figures | — |

---

## 9. Figure & table production plan

Build every figure **from files by script** (`THESIS/scripts/make_figures.py`) so numbers match
the text. Keep one style (matplotlib, vector PDF, consistent carrier colour map). Suggested carrier
colours: solar `#F2C300`, wind `#3B8FD9`, hydro `#1F5FA8`, gas `#D9534F`, lignite `#6B4E3D`,
biomass `#5E9E4B`, battery `#8E6CC0`, pumped_hydro `#2BA3A3`, H₂ `#9AD0EC`, heat `#E8883A`.

| Fig | Content | Input |
|---|---|---|
| Architecture / data-flow / coupled topology | redraw §3.1 and the spec topology (TikZ or draw.io → PDF) | this doc, spec |
| 13-bus network | geo map: region polygons + corridors with MW | `apps/api` `/scenarios/network-topology` or `admin_regions.geojson` + `lines.csv` |
| National load 2022–26 + QC flags | time series, monthly box plot | `ipto_system_load_hourly_2022_2026_model_ready.csv` |
| Fleet map & capacity by source | point map by carrier; bar chart RAAEY vs DAPEEP vs GEM | clusters CSV, report JSON |
| Regional allocation | choropleth of shares (summer vs winter) | `/regional-demand/allocation` or `regional_features.csv` |
| Representative days | load/wind duration curves, full year vs sample | timeseries CSVs, `representative_days.json` |
| Dispatch stacks | stacked area per case | network `.nc` (PyPSA) or result JSON |
| Future expansion | capacity by carrier 2030–2050 | `future_electricity_*/scenario_result.json` |
| Coupled balances | Sankey electricity→H₂/heat, gas | coupled `scenario_result.json` |
| Investment | NPV/IRR by cluster (map + histogram), Scenario A vs B scatter, captured vs average price | `cluster_investment_evaluation.csv` |
| Candidate screening | map of carved candidate polygons; IRR choropleth | `candidate_cells.geojson`, API |
| UI screenshots | 6–8 screens | running app (`npm run dev`) |

---

## 10. Bibliography seed (VERIFY EVERY ENTRY before use)

**Tools and models:** Brown, Hörsch & Schlachtberger (2018) PyPSA, *J. Open Research Software*;
Hörsch et al. (2018) PyPSA-Eur, *Energy Strategy Reviews*; Huangfu & Hall (2018) HiGHS / parallel
dual simplex; Hofmann et al. linopy; Chen & Guestrin (2016) XGBoost, KDD.

**Temporal aggregation:** Kotzur et al. (2018) *Applied Energy*; Poncelet et al. (2017) *IEEE
Trans. Power Syst.*; Hoffmann et al. (2020) review, *Energies*; Nahmmacher et al. (2016).

**Sector coupling:** Brown et al. (2018) "Synergies of sector coupling…", *Energy*; Victoria et al.

**RES economics / cannibalisation:** Hirth (2013) "The market value of variable renewables",
*Energy Economics*; Jordan & Kurtz (2013) PV degradation, *Prog. Photovolt.*; Staffell & Green
(2014) wind degradation, *Renewable Energy*; LBNL/Joule (2023) wind performance decline.

**Costs / data:** IRENA *Renewable Power Generation Costs 2024*; Lazard LCOE+ v18; Danish Energy
Agency *Technology Data*; ENTSO-E TYNDP 2024; JRC hydropower 2024; Greece NECP 2024 (final);
ELSTAT SILC 2023; DESFA 2025 statistics; DAPEEP monthly RES reports; IPTO/ADMIE data portal;
ENTSO-E Transparency Platform; Global Energy Monitor trackers; OpenStreetMap; EEA Natura 2000;
Open-Meteo (Zippenfenig); Eurostat regional statistics.

**Law and policy:** Greek Law 4685/2020; the draft "Special Framework for Spatial Planning of RES"
(May 2026, consultation); Habitats Directive 92/43/EEC; Birds Directive 2009/147/EC; EU RED III
and the delegated act on RFNBO additionality (2023/1184).

**Load forecasting:** Hong & Fan (2016) probabilistic load forecasting review, *IJF*; Box–Jenkins
SARIMA.

Citation style: follow the regulations. The default is IEEE numeric or APA 7.

---

## 11. Execution plan (1–2 days)

Checkpoints marked **⛳** need the author's sign-off before the agent continues.

Freeze is **done** (§7.2 D4, tag `thesis-v1` in both repositories). No remediation or re-runs:
write from the frozen results under the reporting rules in §7.2–7.3.

### Phase 0 — Setup (author + agent, 0.5–1 h)
- Author: give the regulations and template, confirm language, title and RQs.
- Agent: create `THESIS/` (LaTeX: `main.tex`, `chapters/*.tex`, `refs.bib`, `figures/`,
  `scripts/`, `numbers_ledger.csv`), check the build compiles (`latexmk -pdf`).
- **⛳ Approve the final outline** (§8 mapped onto the regulations).

### Phase 1 — Evidence extraction (agent, 1.5–2 h)
- Read §2.3 documents in order.
- Write `THESIS/scripts/extract_numbers.py`, which pulls every result in §6 into
  `numbers_ledger.csv`.
- Write `make_figures.py` and generate all figures in §9 (except screenshots).
- **⛳ Author reviews figures and ledger** (spot-check 10 numbers).

### Phase 2 — Screenshots (author or agent with browser, 30 min)
- `npm run dev` in `PLATFORM`; capture the map explorer, layer panel, candidate drawer with
  investment metrics, Scenario Wizard, results charts, spatial results, portfolio, memo.

### Phase 3 — Drafting (agent, 6–8 h), in dependency order
1. Ch. 3 Data → 2. Ch. 4 Methods → 3. Ch. 5 Implementation → 4. Ch. 6 Validation →
5. Ch. 7 Results → 6. Ch. 8 Discussion → 7. Ch. 2 Literature (with verified citations) →
8. Ch. 1 Introduction → 9. Ch. 9 Conclusions → 10. Abstracts (EN and GR) → 11. Appendices.
- After each chapter: compile, run the number check (every number in `.tex` present in the
  ledger), and write a short summary for the author.
- **⛳ Author reviews Ch. 4 and Ch. 7** (the most technical and the most claim-heavy).

### Phase 4 — Integration & polish (agent, 2–3 h)
- Consistent notation (nomenclature), cross-references, figure/table captions with sources,
  abbreviations list, formatting to the regulations, page-count check, spell check (EN/GR).
- A final "claims audit": grep for numbers and words like *optimal, proves, accurate, market price*
  and check each is justified and properly hedged.
- **⛳ Author final read-through.**

### Phase 5 — (optional) defence deck
- Use **Claude Design** (see §13) or a Slides artifact built from the finished chapters.

---

## 12. Suggested LaTeX skeleton

```
thesis/
  main.tex            % document class per regulations; babel [greek, english]
  frontmatter/        % title, declaration, abstract_en, abstract_gr, acknowledgements
  chapters/01_introduction.tex … 09_conclusions.tex
  appendices/A_costs.tex …
  figures/            % generated PDFs + screenshots
  tables/             % generated .tex tables (from scripts)
  scripts/extract_numbers.py, make_figures.py, make_tables.py
  refs.bib
  numbers_ledger.csv
  Makefile / latexmkrc
```
If Greek text is needed, use XeLaTeX or LuaLaTeX with `fontspec` and a Greek-capable font. If the
university requires Word, generate `.docx` with python-docx or pandoc from Markdown chapters,
using the official template as `--reference-doc`.

---

## 13. Which Claude to use

**Use Claude Code** (desktop Code tab or CLI) for the thesis itself:
- it has to **read two local repositories** (hundreds of files, CSV/JSON results, `.nc` networks);
  only Claude Code has filesystem access;
- it has to **run Python** to extract numbers and draw figures from the real result files, which
  is the core defence against invented numbers;
- it has to **compile LaTeX** (or build DOCX), check cross-references and iterate on the files;
- it can run the app for screenshots, and web search to verify citations.

**Claude Design** is for visual design work (prototypes, slides, one-pagers, posters). It can't
read your repositories or run your models. Use it afterwards for the **defence presentation**
and polished diagrams (architecture figure, poster), and feed it the finished thesis text.

**Model / effort:** use the strongest model at high effort for Methods, Results and Discussion.
Long sessions will auto-summarise, so keep `numbers_ledger.csv` and a `THESIS/PROGRESS.md` log on
disk so state survives.

---

## 14. Author pre-flight checklist

- [ ] University, department, degree programme, supervisor(s), submission date
- [ ] Official regulations (structure, length limits, formatting, citation style, language)
- [ ] Official template (`.cls` / `.docx`) and title-page requirements
- [ ] The institution's AI-use policy and the required disclosure wording
- [ ] Thesis language(s); whether the abstract is needed in both Greek and English
- [ ] Final title and confirmation of RQ1–RQ5
- [ ] Answers to §7.2 items 1–7
- [ ] Both repositories committed and tagged; hashes noted
- [ ] Any prior report or proposal already submitted to the supervisor (to keep consistent)
- [ ] Whether the code will be published (GitHub link / Zenodo DOI in the appendix)

---

## 15. Kick-off prompt (paste into Claude Code)

```
You are helping me write my diploma thesis. Read
C:\Users\megas\dev\energy-investment-platform\docs\thesis\THESIS_MASTER_PLAN.md
completely. It is the master plan. Also read the university regulations I attach below;
they override the plan's default structure.

Workspace: this repo (PLATFORM) and C:\Users\megas\PycharmProjects\pythonProject1 (MODEL).
Treat both as read-only except for a new thesis/ folder in PLATFORM.

Rules: follow §0.3 strictly. No invented numbers or citations. Every number must come from a
file via a script and be recorded in numbers_ledger.csv. When something is ambiguous, stop and
ask me.

Decisions D0–D4 in §7.2 are final and the repositories are frozen at tag thesis-v1
(read-only; no re-runs). Follow the reporting rules in §7.2–7.3.
Start with Phase 0 of §11: propose the final chapter outline mapped onto the regulations and
wait for my approval.
Language: <EN/GR>. Format: <LaTeX template / Word template path>.

<REGULATIONS>
...paste here...
</REGULATIONS>
```
