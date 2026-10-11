# Thesis Outline — for author approval (Phase 0, §11 of the master plan)

**Title (approved 2026-09-30):**
A Scenario-Based Optimisation Platform for Renewable Energy Investment and
Multi-Carrier System Planning: A Case Study of Greece

**Format:** MS Word `.docx`, built by `scripts/build_docx.py` (python-docx) to the
measured template specification in `STYLE_SPEC.md`.

**Shape:** 5 body chapters + References + Appendices, exactly the template's shape.
Target 91 arabic pages of body text, ~20,500 words, ~33 tables and ~43 figures
(one float every ~1.2 pages, matching the template's density).

**Revision 1, 2026-09-30 (post-freeze):** master plan D2-REVISED admits **R8c**, the
real Greece production coupled run, as a reportable result, so Chapter 3 gained a §3.7.

**Revision 2, 2026-09-30 (Phase 1):** extracting the evidence exposed a third
wind-availability defect — the stylised electricity base feeds a wind profile with a
0.26 floor and no calm hours, 2.27× the observed benchmark. On the author's decision
**R8c's system outputs are withheld** and §3.7 reports it as a methodological result
in 2 pages rather than 4. Chapter 3 settles at 18 pp and Chapter 2 returns to 34 pp.
The two frozen electricity scenarios remain the chapter's organising spine, per the
template. Full reasoning in the §3.7 scope note.

---

## Conflicts between the three planning documents, and how they are resolved

| Conflict | Resolution | Authority |
|---|---|---|
| Master plan proposes 9 chapters; architecture doc proposes 6+2; template has 5 | **5 body chapters**, per the template's shape | Supervisor asked for the template |
| Master plan wants a standalone Validation chapter (Ch. 6) | Becomes **§3.1**, opening the results chapter | Author decision, 2026-09-30 |
| Master plan wants a standalone Discussion chapter (Ch. 8) | **Woven into Ch. 3 and Ch. 4** after each result, plus a synthesis in Ch. 5 | Template has no Discussion chapter |
| Master plan wants numbered RQ1–RQ5 as a section | Objectives stated in prose in **§1.1 and §2.1**, not as a numbered list | Template states its gap and aims implicitly |
| Master plan wants a standalone Implementation chapter (Ch. 5) | Becomes **§2.10**, closing the core chapter | Template's §1.7 "SuperPro Designer" is the analogue precedent |
| Both plans want a limitations table | Limitations stated **inline where each result is reported**, then consolidated in **§5.3** | Template acknowledges limitations "mildly and inline" |

---

## Front matter (template order, roman numerals from the Abstract)

| # | Item | Extent | Notes |
|---|---|---|---|
| — | Title page | 1 p, unnumbered | AUTH logo + Faculty of Engineering / Department / Division; title 16 pt on two lines; "Diploma thesis"; name + Reg. Number; Supervisor; Thessaloniki + month/year. **Needs metadata (see below).** |
| i | ABSTRACT | 1 p | One paragraph, ~370 words, heavily quantitative, no keywords |
| ii–v | ΕΚΤΕΝΗΣ ΠΕΡΙΛΗΨΗ | ~4 pp | Greek extended summary; full technical narrative; Greek number format (125.000 / 91,6) |
| vi | ACKNOWLEDGEMENTS | 1 p | First person; supervisor first |
| vii–viii | Table of Contents | 2 pp | Chapter titles ALL CAPS unnumbered; 3 levels; dotted leaders |
| ix | LIST OF TABLES | 1 p | `Table N: Title ...... page` |
| x | LIST OF FIGURES | 1 p | `Figure N: Title (source) ...... page` |

Not in the template, so **not included** unless you say otherwise: declaration of
authorship, keywords, abbreviations list, nomenclature. Acronyms are defined inline
at first use.

---

## Chapter 1 — INTRODUCTION (18 pp)

Context → alternatives → tool, exactly the template's Chapter 1 pattern. Background
and literature live here; there is no separate literature chapter.

| § | Title | pp | Content sources |
|---|---|---|---|
| 1.1 | Overall | 3 | Greek energy transition; NECP 2024 targets; lignite phase-out; RES growth; investment volumes; the investor's "what, where, why"; the fragmented-data and opaque-model problem; aim and scope in prose |
| 1.2 | Energy System Optimisation Models | 2.5 | PyPSA, PyPSA-Eur, TIMES, OSeMOSYS, Calliope; capacity-expansion theory; ESOM comparison table |
| 1.3 | Spatial and Temporal Aggregation in Planning Models | 2 | Representative days (Kotzur, Poncelet, Hoffmann, Nahmmacher); network clustering |
| 1.4 | Multi-Carrier Systems and Sector Coupling | 2 | P2X, electrolysis, heat pumps; Brown et al. 2018; RED III / RFNBO additionality |
| 1.5 | Electricity Demand Forecasting | 2 | Seasonal naive → SARIMAX → XGBoost → LSTM; Hong & Fan; operational vs planning horizons |
| 1.6 | Renewable Siting and Spatial Constraints | 2 | MCDA siting; Natura 2000; Habitats/Birds Directives; Law 4685/2020; draft May-2026 RES spatial framework |
| 1.7 | Investment Appraisal of Renewable Projects | 2 | NPV/IRR/LCOE/PBP; captured price and cannibalisation (Hirth 2013); degradation (Jordan & Kurtz, Staffell & Green) |
| 1.8 | Public Energy Data for Greece | 1.5 | IPTO/ADMIE, ENTSO-E, RAAEY, GEM, DAPEEP, OSM, Greek Energy Map, DESFA, Eurostat; the licensed-vs-built problem as motivation |
| 1.9 | Modelling and Software Tools Used | 1 | PyPSA + linopy + HiGHS; XGBoost; the FastAPI / Next.js / MapLibre stack — the template's §1.7 analogue |

Floats: ESOM comparison table, literature matrix table; Greek generation mix vs NECP
targets figure, RES capacity growth figure.

---

## Chapter 2 — DATA & MODEL SYNTHESIS (34 pp)

The core chapter, the analogue of the template's "FLOWSHEET SYNTHESIS & ANALYSIS":
the model built up stage by stage, every parameter given a value, a justification and
a citation.

| § | Title | pp | Content sources |
|---|---|---|---|
| 2.1 | General Information | 3 | Assumptions; study area (13 NUTS-2 regions); spatial and temporal resolution; **the two scenarios defined**; provenance classes (measured / sourced / derived / scenario_assumption / placeholder); the boundary of what is and is not modelled; roadmap |
| 2.2 | Data Acquisition and Quality Control | 6 | — |
| 2.2.1 | National electricity demand | 1.5 | M1 — IPTO/ADMIE + ENTSO-E; timestamp normalisation; flags; imputation priority; validation |
| 2.2.2 | Generation inventory reconciliation | 2 | M5 — multi-source merge, dedup, source priority, DAPEEP calibration |
| 2.2.3 | Network, spatial and regulatory layers | 1.5 | M9 — OSM grid; admin regions; Natura 2000; UNESCO; draft RES framework |
| 2.2.4 | Technology and financial cost basis | 1 | IRENA 2024, Lazard v18, DEA, TYNDP 2024, JRC 2024; currency year; real basis |
| 2.3 | Demand Representation | 4 | — |
| 2.3.1 | National demand forecasting | 2 | M3 — feature set; XGBoost hyperparameters; model selection by MAPE |
| 2.3.2 | Regional demand allocation | 2 | M2 — sector proxy shares; conservation proof; "estimated", never "measured" |
| 2.4 | Renewable Availability from Weather Data | 3 | M4 — Open-Meteo reanalysis; PV irradiance ratio; **wind power curve** (the corrected cubic law is derived here, with §3.1.2 cross-referenced); HDD |
| 2.5 | Spatial Aggregation: Generator Clustering | 3 | M5 — point-in-polygon bus assignment; capacity-weighted k-means; cluster–hub line ratings by voltage class |
| 2.6 | Temporal Aggregation: Representative Periods | 2.5 | M6 — weight normalisation to 8760 h; the variants; representation classes |
| 2.7 | The Electricity Planning Model | 4 | M7 — nodal balance, DC flow, availability, storage SOC, objective, annuity/CRF; solver; strict acceptance |
| 2.8 | The Multi-Carrier Planning Model | 4.5 | M8 — carriers and bases (MWh_e / MWh_th / HHV gas / LHV H₂); input-side link convention; the four carrier balances; H₂ target modes; policy modes; trade modes; acceptance criteria. Closes with the **production scenario contract** (`build_greece_production_coupled_scenario.py`): how the gas supply, gas plant parameters, residual gas, incremental regional heat, electrolyser sites and heat bounds were each assembled from already-cited sources, and the two derived constants — the IPCC 2006 default gas CO₂ factor and the ~10 % GCV/NCV differential used to put DEA's LHV efficiency and IPCC's LHV factor onto this model's HHV convention |
| 2.9 | Candidate Site Screening | 2.5 | M9 — hard exclusions and warnings per technology; buildable polygon in EPSG:2100; ~11 km grid; distances; power density |
| 2.10 | Platform Implementation | 3 | Architecture; the PyPSA-bridge-as-subprocess decision; scenario artifact contract and hashing; staleness by mtime; API; UI; reproducibility; test strategy |

Floats: data-flow diagram, system architecture, load series with QC flags, reconciled
fleet map, regional allocation choropleth (summer vs winter), wind power curve (legacy
vs corrected), 13-bus topology, clustered topology, representative-period duration
curves, multi-carrier topology, candidate-cell carving example, component diagram;
data register, provenance classes, load QC summary, capacity by source vs DAPEEP,
forecast feature set, allocation proxies, technology cost table, unit conventions by
carrier, siting rules, scenario definition matrix, API endpoints, test inventory.

---

## Chapter 3 — SYSTEM RESULTS & SCENARIO COMPARISON (18 pp)

The analogue of the template's comparison chapter: the two scenarios compared on
physical KPIs, with relative-percentage-change columns.

**The two scenarios**, both already solved and frozen, are real structural variants
rather than an invented growth curve:

- **Scenario A (Baseline)** — the trusted clustered solve: lignite present, gas at the
  TYNDP planning basis of 108.8 €/MWh. Weighted-mean bus price 83.47 €/MWh.
- **Scenario B (Post-Lignite / Spot Gas)** — the same clustered network re-solved with
  PPC's committed 2026 lignite retirement (lignite capacity → 0) and gas at the spot
  TTF figure of 144.0 €/MWh. Weighted-mean bus price 110.18 €/MWh.

| § | Title | pp | Content sources |
|---|---|---|---|
| 3.1 | Model Validation and Benchmarking | 5 | **Opens the chapter so every caveat precedes the numbers it qualifies** |
| 3.1.1 | Analytical and energy-balance verification | 2 | R8b, R11 — electrolyser 0.75, COP 3, boiler 0.93, no double counting; gas balance round-trip; cyclic closure; bus residual tolerances; test inventory. **Includes the validator false-positive found on 2026-09-30:** `energy_balance()` was called without an explicit `round=`, inheriting PyPSA's global 5-decimal default (1e-5 MW) — coarser than the validator's own 1e-6 MW acceptance bar, so no real-sized solve could ever pass. Fixed with `round=12`; the true residual on the solved network is ~3e-12 MW. A second instance of validation catching a real defect, this time in the validator itself |
| 3.1.2 | Benchmarking wind availability against observed output | 2.5 | The chapter's most substantial validation section, now covering **two distinct defects**. (a) **D0**, the power-curve error: `((v−3)/9)³` instead of `(v³−27)/(1728−27)`, giving 0.088 against 0.186 at 7 m/s; the committed profiles at 0.0706 and 0.0784 per-unit, 0.30–0.33× the DAPEEP 2025 benchmark of **23.83 %** (computed by the project's own `dapeep_2025_wind_capacity_factor()`); the corrected curve and bisection calibration, committed but not applied. (b) **The stylised-base profile defect** found in Phase 1: floor 0.26, no hour below 0.05 all year, mean 0.5169 — 2.27× the benchmark, and not a power-curve output at all, while solar in the same network is correct. A single table gives all three run families and their directions. Presented as validation working as intended, because it found both |
| 3.1.3 | Spatial-constraint verification on the existing fleet | 1 | R12 — 1/29 wind and 4/34 solar excluded; Acropolis trigger at 0.6 km |
| 3.1.4 | Temporal-aggregation sensitivity | 0.5 | R4 — objective within ~0.8 %; relative differences only |
| 3.2 | The Reconciled Generation Inventory | 2.5 | R1 — licensed vs built gap; RAAEY vs DAPEEP vs GEM; clustering outcome. **The strongest D0-independent finding** |
| 3.3 | Scenario A: Baseline Dispatch and Prices | 2.5 | Written from `greece_clustered.nc`, **not** the R5 scenario-builder runs — see the note below. Dispatch mix; nodal planning prices (weighted mean 83.47, load-weighted 88.78 €/MWh); R6's cost-driven lignite exit, with lignite at 0.000 TWh |
| 3.4 | Scenario B: Post-Lignite and Spot-Gas Pricing | 2 | `greece_clustered_scenario_b.nc`; the price and cost response |
| 3.5 | Comparison of the Two Scenarios | 2 | Side-by-side with relative % change columns, per the template. **The finding is that generation is unchanged while prices rise ~32 %** — lignite is already out of merit on cost in A, so retiring it removes no output, and repricing gas does not displace gas from the margin. Argued as a result, not presented as a null |
| 3.6 | Short-Term Operational Case | 1 | R3 — 19/20 Aug 2026 forecast-to-dispatch chain, as a functional demonstration, not an accuracy claim |
| 3.7 | The Coupled Production Run as a Methodological Result | 2 | **R8c**, per D2-REVISED and the author's 2026-09-30 decision. Its **system outputs are withheld** — see the scope note below |
| 3.7.1 | Scenario scope, boundary and inputs | 1 | What the run is, its declared years and modes, the assembled scenario contract, the 9 provenance records and 9 input hashes, and the demand boundary (incremental heat excluded from electricity, residual gas limited to industry/CNG) |
| 3.7.2 | What the run demonstrates, and what is withheld | 1 | That a strict production coupled solve is reachable, accepted and closes; then a frank statement of the wind-profile defect and the consequent withholding, with the fix named as future work. Written in the same register as §3.1.2 on D0 — validation surfacing a real problem |
| 3.8 | Hydrogen Feasibility against NECP Targets | 1 | R9 + **D3** — IEA base case vs RAAEY licensed upper bound at NECP-implied utilisation; diagnostic capacity arithmetic, D0-independent |

Floats: aggregation comparison, **wind availability by run family vs the DAPEEP
benchmark**, **wind availability duration curves — committed, clustered and stylised,
showing the missing calm hours**, capacity by source bar chart, Scenario A dispatch
stack, nodal price map, Scenario B dispatch stack, A-vs-B clustered bars, next-day
dispatch, H₂ capacity vs NECP targets; validation checks and tolerances, **the
three-tier wind benchmark table**, spatial QA, aggregation comparison, reconciled
capacity, Scenario A metrics, Scenario B metrics, A-vs-B with relative % change,
**R8c scope-and-boundary table**, H₂ feasibility arithmetic.

The coupled-system Sankey and the shadow-price-by-carrier chart are **dropped**: both
would render withheld outputs. The gas-stack decomposition figure moves to §2.8, where
it is built from inputs.

### Which clustered networks §3.3–3.5 use, and why it matters

Two clustered families exist and they are materially different. §3.3–3.5 use
`pypsa-greece/outputs/clustered/networks/greece_clustered*.nc` (wind 2.669 TWh at
CF 6.08 %, gas 15.209 TWh, solar 11.071 TWh at CF 16.75 %, mean bus price
83.47 €/MWh), because `cluster_investment_evaluation.csv` — and therefore every
captured price and NPV in Chapter 4 — is built from exactly those networks. Sourcing
§3.3–3.5 from the R5 scenario-builder runs instead (wind 7.672 TWh at CF 17.46 %, gas
21.180 TWh, solar 7.386 TWh) would leave Chapter 4's economics describing a different
system from Chapter 3's dispatch. R5 keeps the role the master plan gives it, in
§3.1.4's monthly-days-versus-seasonal-weeks comparison.

A consequence worth stating plainly in §3.1.2 and again in §4.1: Scenario A and B sit
in the **worst** wind tier, at 0.255× the observed benchmark — about 3.9× too low,
which is D0 exactly as written. Since understated wind raises the shadow prices every
other technology captures, the solar, hydro and biomass economics in Chapter 4 carry a
correspondingly strong upward bias and are reported as upper bounds throughout. Solar
availability itself is sound (CF 16.75 %, within the plausible Greek range).

### Scope note for §3.7 — R8c is a methodological result, not a system result

Verified against the run's own files on 2026-09-30, then narrowed by the author's
decision the same day after a third wind-availability defect was found.

**What the run is.** A current-system coupled electricity–gas–H₂–heat planning run:
`target_year` 2025, `load_year` and `weather_year` 2026, on the 13-region
non-clustered electricity base (`mid_2026_monthly_days`). Accepted by the strict
solver gate. Nine provenance records, nine input hashes, a manifest, and a bus
balance closed to ~3e-12 MW. Trade disabled, electrolyser investment disabled,
H₂ target mode `final_demand` (207,557.27 MWh_LHV), policy mode `grid`, CO₂ at
€80/tCO₂. Temporal provenance records 12 **real-weather** monthly representative
days weighted to 8,760 h — not the `hour_of_day_mean` fallback that flattened the
excluded D1 runs.

**Why its system outputs are withheld.** R8c's wind availability profile is not a
power-curve output. Measured on its own solved network: mean 0.5169, **minimum
0.26**, maximum 0.86, and **no hour anywhere in the year below 0.05**. Solar in the
same network behaves correctly (41.67 % exact zeros at night, max 1.0), so this is
specific to wind and distinct from D0's power-curve error — it sits in the scenario
builder's wind path. Per-region ratios against the committed profile run from 1.67×
to 271×, so it is not a rescale but a different variable, most likely a normalised
wind speed. Against the project's own DAPEEP 2025 benchmark of 23.83 %, the run's
wind availability is 2.27× too high.

A profile with no calm hours does not merely shift the price level, it removes the
wind scarcity structure that *creates* the price distribution. Under the project's
own rule — a number is a finding only if its run is valid by the project's own
standards — the following are **withheld** and tagged `WITHHELD-` in the ledger, the
same treatment wind NPV/IRR receives under D0: the objective and its cost ledger,
emissions, all solved shadow prices, the dispatch mix and generation by carrier,
curtailment, the endogenous wind and solar expansion, and the uniform-mainland-price
observation. Sixty-eight ledger rows carry that tag.

**What R8c does establish, and §3.7 reports.** That a strict production coupled solve
of the Greek multi-carrier system is reachable and passes every acceptance gate: the
scenario contract can be assembled from already-cited sources; the preflight that
once refused incomplete inputs now passes on complete ones; the bus balance closes to
~3e-12 MW; and the run carries full provenance, hashing and a manifest. Combined with
§2.8's formulation and §3.1.1's analytical tests and synthetic 8,760 h reference, that
is a genuine methodological contribution. It is stated as such, without borrowing the
authority of numbers that are withheld.

**The gas marginal stack survives intact, and moves to §2.8.** It is the worked example
of the M8 input-side link convention, and it is derived from **input files only**, so it
does not depend on any withheld result:

- commodity €42.90/MWh_HHV (`gas_supply.csv`, basis `gas_HHV_commodity`, TYNDP 2024),
  across 5 DESFA entry points totalling 23,067 MW_HHV
- efficiency 0.5182 MWh_e/MWh_HHV, VOM €5.74/MWh_e, emission factor
  0.1836 tCO₂/MWh_HHV (`gas_plant_parameters.csv`; DEA and IPCC 2006, HHV-converted)
- input-side link cost = €14.688 CO₂ + €2.974468 VOM = **€17.662468/MWh_HHV**, which
  matches the value built into the solved network exactly
- (42.90 + 17.662468) ÷ 0.5182 = **€116.8708/MWh_e**

Inverting `c_in = η·c_out` returns €5.7400/MWh_e, exactly the DEA figure, with zero
residual. That round-trip verifies the convention, the HHV conversion and the input
assembly independently of the solve.

**Also unaffected, and reported where it belongs.** The validator false-positive and its
fix go to §3.1.1: `energy_balance()` was called without an explicit `round=`, inheriting
PyPSA's 5-decimal global default (1e-5 MW), coarser than the validator's own 1e-6 MW
bar, so no real-sized solve could ever pass. Fixed with `round=12`; the true residual is
~3e-12 MW. Validation catching a defect in the validator itself.

**Future work gains a first item.** Diagnose and fix the stylised base's wind profile,
verify it has calm hours and a mean near the observed 23.83 %, then re-solve R8c and the
stylised electricity runs. That single fix would convert R8c's withheld outputs into
reportable results and remove the R4 caveat at the same time.

## Chapter 4 — SITING & ECONOMIC EVALUATION (18 pp)

The analogue of the template's "DESIGN & ECONOMIC EVALUATION", including its
sensitivity-analysis section with tornado charts.

| § | Title | pp | Content sources |
|---|---|---|---|
| 4.1 | Economic Parameters | 2.5 | The template's parameter-table section: indicators (NPV, IRR, LCOE, PBP); discount rate 7 % real; lifetimes; degradation rates; currency year; annual operating hours; **explicit scope exclusions** |
| 4.2 | Captured Revenue and Price Cannibalisation | 2 | M10 — captured revenue Σ dispatch·price·weight vs average price × energy; why the shortcut fails; solar captured price well below the system average |
| 4.3 | Investment Evaluation of the Existing Clustered Fleet | 3.5 | R13 — 77 clusters, Scenario A vs B, per carrier. Solar/hydro/biomass as **upper bounds** under D0; **wind NPV/IRR withheld**, with the reason given |
| 4.4 | Candidate Site Screening Results | 2.5 | R14 geometry — 718 cells; exclusion statistics; buildable fractions; grid distances. D0-independent |
| 4.5 | Candidate-Level Investment Evaluation | 3 | R14 economics — per-cell NPV/IRR/LCOE; regional patterns; the placeholder-resource-score and national-CF caveats stated inline |
| 4.6 | Portfolio Construction and Portfolio Returns | 1.5 | Combined-cash-flow portfolio IRR, not an average of IRRs |
| 4.7 | Sensitivity Analysis | 2.5 | OFAT, ±range; economic group (discount rate, CAPEX, gas price, degradation) and technical group (capacity factor, power density, lifetime); **tornado charts for NPV and IRR, one per scenario** |
| 4.8 | Platform Demonstration | 1.5 | R16 — the decision-support walkthrough: map explorer → candidate screening → Scenario Wizard → spatial results → portfolio → memo export |

Floats: captured vs system price by carrier, cluster NPV map, IRR distribution
histogram, A-vs-B NPV scatter, candidate-cell carved polygons map, candidate IRR
choropleth, portfolio cash-flow profile, four tornado charts (NPV and IRR × two
scenarios), six UI screenshots; economic parameters, capex and cost assumptions by
technology, captured vs average price, cluster evaluation A vs B with relative %
change, candidate screening statistics, candidate economics summary, portfolio
metrics, sensitivity ranges and sources.

---

## Chapter 5 — CONCLUSIONS & FUTURE RESEARCH (3 pp)

All prose, no bullet lists, per the template.

| § | Title | pp |
|---|---|---|
| 5.1 | Summary of the work and headline findings | 1.25 |
| 5.2 | Contributions | 0.5 |
| 5.3 | Limitations | 0.75 |
| 5.4 | Future research | 0.5 |

Future work, in the master plan's priority order: apply the wind calibration and
re-solve everything, R8c included; a genuine 8,760 h reference run, which R8c's own
temporal provenance record names as the missing validation for its representative-day
chronology; **re-run the coupled model on the reconciled fleet of R1 rather than the
stylised 13-bus fleet**, and with binding heat-capacity bounds, which together would
turn R8c's capacity outputs into statements about the real Greek system; the real
ADMIE topology, which the uniform mainland shadow price in §3.7.3 shows to matter;
rolling-origin forecast backtests; enabling electrolyser investment and cross-border
trade, both disabled in R8c; unit commitment and a market tier; storage arbitrage NPV;
the spatial MILP portfolio; the end-to-end optimisation API.

---

## REFERENCES (~12 pp)

APA 7, alphabetical, hanging indent, 12 pt, DOIs as full `https://doi.org/...` URLs.
Target ~90 entries. **Every entry verified by web search or DOI lookup before it is
written**, per §0.3 of the master plan. Nothing in the master plan's seed list is
treated as verified bibliographic data.

## APPENDICES (~14 pp, tables only)

| App. | Content |
|---|---|
| A | Full technology cost table with per-parameter citations |
| B | Data register: every dataset with source, records, date, provenance class |
| C | API endpoint reference |
| D | Validation test inventory |
| E | Software availability. **Three references, not two:** PLATFORM tag `thesis-v1` = `baa2198`; MODEL tag `thesis-v1` = commit `455fa7f` (the tag object itself is `f695ef5` — an annotated tag, so cite the commit) for everything except the coupled chapter; MODEL branch `thesis-freeze` = `d7be6cc` for §2.8's production scenario contract, the validator fix and R8c. State that the MODEL freeze was reopened once, by the author, for the coupled production run |
| F | Supplementary result tables (per-cluster evaluation, per-region candidate statistics) |

---

## Honesty controls carried into the writing

Enforced mechanically where possible.

1. **`numbers_ledger.csv`** — every number in the thesis traced to a file path or a
   citation. `scripts/check_numbers.py` reads the built document and fails on any
   number not in the ledger.
2. **Not presented as findings:** future-year 2030–2050 runs (D1); the legacy coupled
   2030 output (**R8**, D2 unchanged — qualitative mention only, in §2.8's "evolution
   of the approach"; kept strictly distinct from R8c); the standalone heating optimum
   (R10, diagnostic); wind NPV/IRR (D0); and **R8c's system outputs** (68 ledger rows
   tagged `WITHHELD-`, per the §3.7 scope note).
3. **Wind bias is per run family, not global.** The ledger's `wind_bias` column carries
   `none`, `understated`, `overstated` or `withheld` for every claim, because D0's
   direction is not uniform: the committed profiles are ~3× too low (0.30–0.33× the
   23.83 % benchmark), the clustered runs 0.73× (understated — R5, R13, R14 economics),
   and the stylised runs 2.18–2.27× (overstated — R4, and R8c before withholding).
   §3.1.2 presents all three tiers as one table.
4. **Language discipline:** "planning shadow price" not "market price"; "least-cost
   planning result" not "forecast"; "estimated regional allocation" not "measured";
   "investment screening" not "bankable recommendation".
5. **Claims audit before submission** — grep for `optimal`, `proves`, `accurate`,
   `market price`, `predicts`, and every numeral.

### Where the title's multi-carrier claim now stands

The title promises *multi-carrier system planning*. With R8c's system outputs withheld,
that claim rests on the formulation (§2.8), its verification (§3.1.1 — analytical
balances, the synthetic 8,760 h reference case, the gas-stack round-trip, the validator
fix), the demonstration that a strict production coupled solve of Greece is reachable
and closes (§3.7), and the hydrogen feasibility arithmetic (§3.8). That is a defensible
methodological contribution and the title stands on it.

It is, however, weaker than it would be with R8c's prices and dispatch in hand. Two
things follow. First, the abstract and §5.2 must claim the **formulation and its
verification**, never a coupled system outcome for Greece — no captured price, dispatch
mix or cost figure from R8c appears anywhere. Second, if the wind profile is fixed and
R8c re-solved before submission, this section and §3.7 revert to Revision 1's plan and
the claim strengthens materially. Flagged so the choice stays visible rather than
quietly settled.

---

## What I still need from you

Only front-matter metadata, and only before the final build — not blocking for
drafting:

1. Department and Division, as they should read on the title page
2. Your registration number
3. Supervisor's name and title
4. Submission month and year
5. Whether the code will be published (a GitHub or Zenodo link for Appendix E)
