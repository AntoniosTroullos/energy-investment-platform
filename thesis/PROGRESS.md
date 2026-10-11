# Thesis progress log

State on disk so it survives context summarisation. Update after every phase.

## Decisions taken

| # | Decision | Date | By |
|---|---|---|---|
| 1 | Output format: MS Word `.docx` via python-docx. No LaTeX or pandoc is installed; the supervisor's template is itself Word. | 2026-09-30 | author |
| 2 | Title: *A Scenario-Based Optimisation Platform for Renewable Energy Investment and Multi-Carrier System Planning: A Case Study of Greece* | 2026-09-30 | author |
| 3 | Validation is §3.1, opening the results chapter — not a separate chapter. Keeps the template's 5-chapter shape and puts the D0 caveat before the numbers it qualifies. | 2026-09-30 | author |
| 4 | Thesis structure follows the supervisor's template (5 body chapters), overriding the master plan's 9-chapter and the architecture doc's 8-heading proposals. | 2026-09-30 | precedence rule §0.2 |
| 5 | **D2-REVISED:** R8c, the real Greece production coupled run, is a reportable headline result. It becomes §3.7 (4 pp); Chapter 3 grows 16 → 20 pp, Chapter 2 gives up 2 pp. Scenario A vs B stays the chapter's spine. | 2026-09-30 | author |

Decisions D0, D1, D3 and D4 of the master plan §7.2 are final. D2 was superseded by
D2-REVISED on 2026-09-30; the **legacy** coupled 2030 run (R8) is still not a finding,
and is kept strictly distinct from R8c.

## R8c verified on disk 2026-09-30

`data/processed/pypsa_scenarios/coupled_greece_2025_production/`, MODEL commit
`d7be6cc` on branch `thesis-freeze` (past the `thesis-v1` tag).

| Property | Value |
|---|---|
| Accepted | `true` |
| Objective | €2,618,675,494.21/yr — ledger: generator variable 1,444,067,076 / link variable 25,283,603 / generator capital 239,624,463 / link capital 909,700,352 |
| Emissions | 5,776,868.93 tCO₂/yr, all from generators; links 0.0 |
| Total demand | 106,954,818.64 MWh |
| Shadow prices | electricity €24.13/MWh on all 11 mainland buses (identical to 15 s.f.), South Aegean €23.62, Crete €23.90; gas €42.90/MWh_HHV; H₂ €41.21/MWh_LHV; heat ≈€19.54/MWh_th |
| Bus balance | ~3e-12 MW after the `round=12` validator fix |
| Scope | `target_year` 2025, `load_year` 2026, `weather_year` 2026, `temporal_mode` `synthetic_expansion`, 12 real-weather monthly representative days weighted to 8,760 h |
| Settings | trade disabled; electrolyser investment disabled; H₂ `final_demand` target 207,557.27 MWh; H₂ policy `grid`; carbon price €80/tCO₂ |
| Provenance | 9 records, 8 input SHA-256 hashes, manifest present |
| Electricity base | `mid_2026_monthly_days/config.yaml` — the **13-region stylised** fleet |

**Three caveats that travel with every R8c number** (detail in `OUTLINE.md` §3.7 scope
note): the D0 wind bias, as for R4/R5/R13; the electricity fleet is the **stylised**
13-bus fleet (gas 12,040 / hydro 2,020 / lignite 1,900 fixed; solar 8,920 and wind
7,970 extendable to 20,700 and 21,100), **not** the reconciled fleet of R1
(5,949 / 7,545 / 5,016), so R8c capacity figures never describe the real Greek system;
and wind plus heat-supply capacity are endogenous, so R8c is a current-year
**capacity-expansion** run, not a dispatch snapshot — solved wind 9,737.14 MW is
+1,767.14 MW (+22.2 %) on its starting point, while solar did not expand, and the heat
bounds are deliberately non-binding.

**Safe directional claim:** wind availability is understated ~3× yet wind still
expanded 22 %, so R8c's wind expansion is a lower bound.

**Open item — RESOLVED 2026-09-30, Phase 1.** €24.13/MWh is the weight-weighted mean of
a bimodal price duration curve, not a technology's price level. Renewables at or near
zero marginal cost are marginal in 60.80 % of weighted hours (wind €1.90 in 4,291 h,
solar/surplus €0.00 in 1,035 h), hydro €12.00 in 1,444 h, and gas-to-power at its full
€116.87/MWh_e stack in only 1,352 h (15.43 %); 638 h sit at intermediate levels.
Load-weighted mean €24.5152/MWh over 49.915 TWh.

The gas stack reconstructs exactly and doubles as the M8 input-side-convention worked
example: (42.90 + 17.662468) / 0.5182 = 116.8708 €/MWh_e, where 17.662468 €/MWh_HHV =
14.688 CO₂ (0.1836 × 80) + 2.974468 VOM, and inverting `c_in = η·c_out` returns
5.7400 €/MWh_e — exactly DEA's VOM per the manifest, residual 0.

Not comparable with Scenario A's €83.47/MWh: R8c's stylised fleet carries ~50 % more
renewable capacity than the clustered reconciled fleet. Under D0, €24.13 is an upper
bound. The mainland price spread is 3.55e-15 €/MWh, so no mainland corridor binds —
a finding in its own right about the stylised topology.

## Environment verified 2026-09-30

| Item | Status |
|---|---|
| PLATFORM repo | `C:\Users\megas\dev\energy-investment-platform`, worktree `diploma-thesis-architecture-02118f`, tag `thesis-v1` = `baa2198` ✓ |
| MODEL repo | `C:\Users\megas\PycharmProjects\pythonProject1`, branch `thesis-freeze` now at `d7be6cc`; tag `thesis-v1` still = commit `455fa7f` (annotated tag object `f695ef5` — cite the commit, not the tag SHA) |
| Figures / data venv | `pythonProject1\pypsa-greece\.venv314\Scripts\python.exe` — matplotlib, pandas, geopandas, pypsa, shapely all present |
| Document venv | `thesis\.venv-docx\Scripts\python.exe` — python-docx installed |
| LaTeX / pandoc | Absent. Not required under decision 1. |
| Template PDF | 128 pages, readable via PyMuPDF; style measured into `STYLE_SPEC.md` |

## Scenario spine (confirmed from the code, not from prose)

- **Scenario A (Baseline)** — trusted clustered solve; lignite present; gas at the
  TYNDP planning basis 108.8 €/MWh; weighted-mean bus price 83.47 €/MWh.
- **Scenario B (Post-Lignite / Spot Gas)** — same clustered network re-solved;
  lignite capacity → 0 (PPC's committed 2026 retirement); gas at spot TTF
  144.0 €/MWh; weighted-mean bus price 110.18 €/MWh.

Source: `pypsa-greece/KNOWLEDGE_TRANSFER.md` §321, §366, and the column schema of
`pypsa-greece/data/processed/cluster_investment_evaluation.csv` (77 rows,
`scenario_a_*` / `scenario_b_*`). These two figures still need re-extraction into the
ledger before they are quoted.

## Wind availability, a third defect — found and RESOLVED in Phase 1, 2026-09-30

Found while extracting R4/R5. **Author decision: report R8c as a methodological result
only.** Its system outputs are withheld — 68 ledger rows tagged `WITHHELD-R8c-`,
applied reproducibly by `apply_r8c_withholding()` in `scripts/extract_numbers.py`
rather than by hand. §3.7 drops from 4 pp to 2 pp; Chapter 3 settles at 18 pp.

Retained and citable: 20 R8c claims covering solver acceptance, scope and declared
years/modes, provenance and hash counts, snapshot count and weight sum, the demand
boundary, and the electricity-only demand. Plus 13 new `gas-*` claims deriving the gas
marginal stack from **input files only**, so nothing citable leans on a withheld dual.

### D0's direction is not uniform. There are three run families, not one.

Benchmark: `dapeep_2025_wind_capacity_factor()` = **23.83 %** (the project's own
function, as D0 instructs).

| Run family | Wind availability CF | vs benchmark | Direction |
|---|---|---|---|
| Committed base timeseries (`wind_pu_regional/clustered.csv`), used by the excluded future-year runs | 7.06 % / 7.84 % | 0.30× / 0.33× | ~3× too LOW — **D0 as written, correct here** |
| **Scenario A and B** (`greece_clustered.nc`) — the Base-vs-Alternative spine and the basis for **every economic result in Chapter 4** | **6.08 %** | **0.255×** | **~3.9× too LOW — the worst tier, and the one that matters most** |
| Clustered scenario-builder runs — R5 | 17.46 % | 0.73× | ~27 % too low |
| Stylised 13-bus runs — R4, **and R8c through its electricity base** | 52.02 % | **2.18×** | **~2.2× too HIGH** |

Solar is sound throughout: Scenario A/B solar CF is 16.75 %, within the plausible
Greek range, and solar in R8c's network has proper night-time zeros.

The per-scenario input files carry the same filenames as the committed ones but hold
different content, which is why the families diverge.

### The stylised profile is not a capacity factor at all

Measured on R8c's own solved network (`network.nc`, wind `p_max_pu`, 26 generators ×
288 snapshots):

| Statistic | Wind | Solar (same network, for contrast) |
|---|---|---|
| mean | 0.5169 | 0.2889 |
| min | **0.26** | 0.0000 |
| max | 0.86 | 1.0000 |
| fraction exactly 0 | **0.0000** | 0.4167 |
| fraction below 0.05 | **0.0000** | 0.5000 |
| 5th percentile | 0.3200 | 0.0000 |

Solar behaves correctly — night hours are zero. Wind has a hard floor of 0.26 and
**no calm hours anywhere in the year**, with a minimum above Greece's real annual mean
CF. Per-region ratios against the committed profile range from 1.67× to 271×, so it is
not a rescale but a different variable; cubing it does not recover the committed
profile either. The series is almost certainly a normalised wind *speed*, not a
power-curve output. This is a **third defect, distinct from D0's power-curve error**,
located in the scenario builder's profile path.

### Why this is not a "state the bias direction" case

A profile with no calm hours does not merely shift the level — it removes the wind
scarcity structure that *creates* the price distribution. It is what produces R8c's
wind 35.44 TWh (71 % of the 49.9 TWh electricity demand), 23.29 % curtailment, wind
marginal in 48.98 % of weighted hours, and hence the €24.13/MWh mean. Reporting that
price while disclosing "wind is 2.2× too high and never calm" would report a number
the project's own standard rejects.

### What survives regardless, and what does not

**Unaffected — safe to write now:** the formulation and unit conventions (§2.8); the
validator false-positive and its fix; the bus balance closing to ~3e-12 MW; the gas
stack decomposition (€42.90 + €17.662468) / 0.5182 = €116.8708 and the VOM round-trip
to €5.7400/MWh_e with zero residual — a unit-convention verification independent of
the wind profile; the provenance, manifest and hashing machinery; the fact that the run
is accepted and fully provenanced.

**Contaminated — not writable as findings until resolved:** the €24.13/MWh price and
its composition; generation and dispatch mix; curtailment; the +22.2 % wind expansion;
emissions 5,776,868.93 tCO₂/yr; the objective €2,618,675,494.21/yr; and the uniform
mainland price, which is partly a consequence of wind being abundant everywhere.

R5, R13 and the candidate economics are **unaffected by this finding** — they run on
the clustered family, where D0's stated direction (understated) holds.

## Two structural findings from building the tables, 2026-10-01

### 1. Scenario A and B are not the same networks as R5

Two distinct clustered families exist, and they are materially different:

| | Scenario A/B (`pypsa-greece/outputs/clustered/networks/greece_clustered*.nc`) | R5 (`data/processed/pypsa_scenarios/clustered_*`) |
|---|---|---|
| wind | 2.669 TWh, CF 6.08 % | 7.672 TWh, CF 17.46 % |
| gas | 15.209 TWh | 21.180 TWh |
| solar | 11.071 TWh, CF 16.75 % | 7.386 TWh, CF 11.17 % |
| hydro | 5.639 TWh | 7.135 TWh |
| storage | battery 3.741 TWh | pumped hydro 6.045 TWh |
| mean bus price | 83.47 €/MWh | — |

**Consequence for the outline.** §3.3–3.5 must be written from `greece_clustered.nc`,
because `cluster_investment_evaluation.csv` — and therefore every captured price and
NPV in Chapter 4 — is built from those networks. Sourcing §3.3–3.5 from the R5 runs
instead would leave Chapter 4's economics describing a different system from
Chapter 3's dispatch. R5 keeps its role in §3.1.4, the monthly-days-versus-seasonal-weeks
comparison, which is what the plan uses it for.

### 2. Scenario B is a pure cost and price shift, with no dispatch response

Generation is unchanged from A to B across every carrier: gas 15.209 → 15.209, wind
2.669 → 2.669, hydro 5.639 → 5.639, solar 11.071 → 11.074 TWh (+0.03 %), battery
3.741 → 3.738 (−0.07 %). Yet the weighted-mean shadow price rises 31.99 % (83.47 →
110.18 €/MWh), the load-weighted price 32.04 % (88.78 → 117.23), and the objective
26.69 % (€2.0061bn → €2.5415bn per year).

The mechanism is coherent and worth stating as a finding rather than presenting as a
null result: lignite already generates 0.000 TWh in Scenario A because its €157/MWh
marginal cost keeps it out of merit (R6), so retiring it removes no output; and
repricing gas from €108.80 to €144.00/MWh raises the marginal cost without displacing
gas from the margin, since nothing cheaper has spare capacity. The reading is that
the post-lignite transition is, in this model's economics, already complete on cost
grounds before any retirement policy applies — so the retirement is fiscally and
politically consequential but physically neutral here, while a spot-gas shock passes
almost undamped into prices. §3.5 makes that argument explicitly.

## Gaps closed 2026-10-01

### R11 gas balance — derived live, exact

From `pypsa-greece/outputs/gas/networks/greece_gas.nc`, 864 snapshots weighted to
8,760 h: supply 78.7499 TWh_HHV = domestic 70.1599 + exports 8.5901, residual
**0.000000 TWh (0.0000 %)**. The domestic and export figures reproduce DESFA's
published 2025 values of 70.16 and 8.59 TWh.

**Framed precisely in the thesis:** the loads were *built from* those published
figures, so reproducing them shows the pipeline preserves the input quantities
through construction, solve and weighted annual aggregation. It is a conservation
check on the pipeline, **not** an independent validation of DESFA's numbers. The
standalone gas model stays diagnostic and is never summed with coupled results.

### R15 / R8b test counts — the plan's figures were stale, and one test fails

Both suites were run and their output captured to `thesis/evidence/`.

| Repository | Tests | Passing | Failing | Runtime |
|---|---|---|---|---|
| MODEL (`pythonProject1`) | **186** | 185 | **1** | 134.663 s |
| PLATFORM (`apps/api`) | **191** | 191 | 0 | 33.694 s |

The plan quoted 179 MODEL test functions and "167/167"; the live count is 186 with
one failure. PLATFORM's 191 matches.

**The failure, characterised.** `tests/test_spatial_portfolio.py::test_land_cap_and_grid_upgrade_cost_are_enforced`
fails because the spatial site-selection MILP in `src/energy_data/spatial_portfolio.py`
does not let a site's fixed grid-upgrade cost deter selecting that site. Verified by
diagnostic runs: the capacity allocation is identical with and without the
€1,000/yr upgrade (dense 5.5556 MW, compact 44.4444 MW in both cases), so the
upgrade merely adds €1,000 to the reported objective without influencing the
decision. The model therefore reports **€1,944.44/yr** where building only the
compact site costs **€1,000.000001/yr** and satisfies every constraint — and adding
an optional candidate to a minimisation can never raise the true optimum, so the
reported answer is not least-cost.

**Consequences.** R15 cannot claim a clean suite; §2.10 reports 186/185/1 with the
defect named. The spatial MILP (C14) is an optional extension that **no reported
result depends on**, so nothing else in the thesis is affected; it moves from
"unit-tested" to future work with a known defect. Not fixed: the repositories are
read-only apart from the coupled chapter, and a fix is the author's call.

### R16 screenshots — environment prepared 2026-10-01

Correcting my earlier note: the repository root *does* have a `package.json` with
`dev`, `doctor` and `test` scripts, and the main checkout has both a root `.venv`
and an `apps/api/.venv`. The gap was the **worktree**, which had no `node_modules`
and no API virtualenv at all.

Prepared in the worktree so the screenshots come from the same tree as the thesis:

- `apps/web` dependencies installed.
- `apps/api/.venv` created from `apps/api/requirements.txt` (fastapi 0.115.0,
  uvicorn 0.30.6, xlrd 2.0.1, osm2geojson 0.3.2, shapely 2.1.2, pyproj 3.7.2).
  `scripts/lib/env.mjs::resolveApiPython()` looks for exactly that path, or an
  `API_PYTHON` override.
- `.claude/launch.json` already defined `energy-dev-alt-ports`, which starts both
  halves via `node scripts/dev.mjs` on API 8100 and web 3100. `dev.mjs` imports
  only Node builtins, so the repository root needs no `node_modules`.

**The app code screenshotted is exactly the tagged state.** `git diff thesis-v1 HEAD`
over `apps/`, `src/`, `scripts/` and `requirements.txt` is empty; the only
difference on this branch is the master plan document. So §4.8's figures honestly
depict `thesis-v1`.

**Smoke test passed, 2026-10-01.** `energy-dev-alt-ports` brought both halves up:
API healthy on 8100, web on 3100, `/health` and `/system/status` 200, and the
launcher reported *PyPSA solving: available*. No console errors on any screen.
Screens verified working: map explorer with all seven infrastructure layers and
labelled DESFA entry points; Analysis mode rendering the candidate grid;
`/candidates` 200 with the drawer opening on a cell and showing full screening
geometry (distance to line 4.8 km, to substation 4.9 km, Natura overlap 0, nearest
UNESCO site Meteora at 49.5 km); and Scenario Studio with its four presets and
controls. Working captures in `thesis/figures/screenshots/`.

**Two cautions for the figures.**

1. The launcher reports solved electricity years 2030–2050, so the Scenario Studio
   and the map's scenario-results selector can display the **D1-excluded**
   future-year runs. No figure may show a 2030–2050 result as a finding. Screenshots
   of those surfaces must either leave the selector on *None* or use a 2026 run.
2. The candidate drawer opened on an **onshore wind** candidate. Screening geometry
   is reportable for any technology, but wind **economics** are withheld under D0,
   so the §4.5 figure showing NPV/IRR must use a solar candidate.

**Resolution.** The browser returns captures at 800 px wide regardless of viewport,
which is marginal for print. These files are good enough to compose and caption the
figures against; if the supervisor wants print-crisp UI figures, the author should
retake the same five screens with a native screenshot tool at full resolution. The
framing and layer state to reproduce are recorded above.

## Phase status

| Phase | Description | Status |
|---|---|---|
| 0 | Setup, toolchain, style spec, outline | **Done — outline awaiting author approval** |
| 1 | Evidence extraction | **Complete.** 888 ledger claims, 15 table specs, 7 generated figures, captured test runs and derived evidence files. |
| 2 | UI screenshots from the running app | Not started |
| 3 | Drafting | **All five chapters plus front matter and Appendix E drafted.** ~16.6k words. `check_numbers.py` passes on all 10 sources: 0 untraced, 0 withheld. Ledger 913 claims. **references.csv at 71 entries, 27 verified.** Remaining: 4 references outstanding (draft RES framework, DAPEEP URL, NECP official URL, TIMES), 6 needing one field, 10 [VERIFY:] markers in Ch1, Ch5 trim, claims audit. |
| 4 | Integration & audit | **Both guards fully clean.** `check_numbers.py` and `claims_audit.py` report 0 findings across all five checks. 12 figures placed. **Correction applied:** the RES spatial framework was enacted 19.08.2026 (Ministerial Decision YPEN/DNEP/89998/3072, Gazette D' 694), so the thesis no longer claims it is a draft awaiting enactment; it now states that the implemented rules are the consultation draft's and may differ from the enacted text. |

## 2026-10-02: the wind defect is fixed and R8c is un-withheld; the MILP bug is fixed

Both done at the author's explicit request ("lets clear the wind problem... lets fix
this [MILP]... lets solve them"), in MODEL on `thesis-freeze`, commits `fb53a86` and
`b1bbbfd` (past `d7be6cc`).

### Spatial-portfolio MILP (R15) — fixed, 186/186 now pass

Root cause confirmed by direct diagnostic, not guessed: `select_portfolio`'s binary
`build` variable carries a deliberately tiny `1e-6` tie-break cost. HiGHS's own log
warns *"Problem has some excessively small costs"*, then **presolve** reduces the
model to empty via variable fixing and reports a non-optimal split (dense+compact,
€1,944.44/yr) as "Optimal" with 0 B&B nodes and 0 LP iterations — not a real search.
A strictly cheaper, fully feasible solution exists (pure compact, €1,000.00/yr).
Disabling presolve (`model.setOptionValue("presolve", "off")`) makes HiGHS actually
branch-and-bound and find the true optimum. Verified directly before and after.
Negligible cost at this model's scale (a handful of candidate sites per solve).
**R15 now reads 186/186, no caveat.**

### Wind (D0) — the fix existed, was never run; now applied and R8c re-solved

`scripts/calibrate_wind_profiles.py` (curve correction + DAPEEP calibration) was
written and unit-tested (7/7) weeks ago but **never actually run**: its required
input snapshot, `data/timeseries/legacy/`, did not exist on disk, so it failed
immediately on the first line that reads it. Confirmed the *current* canonical
`wind_pu_regional/clustered.csv` genuinely **are** the legacy fraction-cubed curve
(fleet CF 7.60%, matching `wind_power_curve_pu`'s own docstring number), seeded
`legacy/` from them, and ran the real fix. Calibrated fleet CF: **23.834%**, against
DAPEEP's observed 23.83% target — report at
`pypsa-greece/data/processed/wind_calibration_report.json`.

**This also explains the "third, distinct defect" flagged above** (mean 0.52, floor
0.26, zero calm hours all year in `mid_2026_monthly_days`). It was never a separate
bug in the scenario builder's profile path. That case's `wind_pu_regional.csv` was
written **26 July**; the canonical source file's own mtime is **19 August** — three
weeks later. The case was simply built from whatever the source file held *before*
whatever regenerated it on 19 Aug, and nobody ever rebuilt the case afterward. A
stale derived artifact, not new code to debug.

**Regenerated and re-solved** (`scripts/run_pypsa_scenario.py --no-solve`, then
solved directly — that script's own solve step calls `solve_network()` with a
two-value-return contract the function no longer has; not touched, since a one-off
direct solve was faster and safer than fixing a second script tonight). New wind
profile on the solved network: mean 0.21, min 0.0074, **13.8% of hours below 0.05**
(vs 0% before) — the hard-floor, no-calm-hours signature is gone.

**R8c re-solved with the corrected input, accepted, optimal.** Numbers move
substantially, in the expected direction (weaker, more realistic average wind ⇒
more gas dispatch):

| | Withheld run (wrong wind) | **New run (fixed wind)** |
|---|---|---|
| Objective | €2,618,675,494/yr | **€4,254,905,347/yr** |
| Emissions | 5,776,869 tCO₂/yr | **13,490,058 tCO₂/yr** |
| Electricity shadow price, mainland | €24.13/MWh (uniform, flagged as implausible) | **€79.55/MWh** (€70.27–80.54 range across all 13 buses — no longer flat) |
| Gas shadow price | €42.90/MWh_HHV | €43.59/MWh_HHV |
| H₂ shadow price | €41.21/MWh_LHV | €118.73/MWh_LHV |
| Heat shadow price | ≈€19.54/MWh_th | ≈€28.50/MWh_th |
| Wind capacity (output side) | 9,737 MW (+22.2% expansion) | 11,300 MW (at its extendable ceiling again) |
| Bus balance | ~3e-12 MW | still machine-precision (validator fix from Sept 30 still in effect) |

**Author decision needed before this goes in the text:** un-withhold R8c using
*these* numbers (replacing the 68 `WITHHELD-R8c-` ledger rows and rewriting §3.7
from "methodological result only" back to a real headline result), or keep §3.7 as
currently drafted and treat this as Future Work delivered early. Mainland prices are
no longer uniform (€70.27–80.54 vs the old flat €24.13), which is itself a more
credible finding — worth a sentence either way. Re-running `extract_numbers.py`'s
`apply_r8c_withholding()` step is what un-withholding requires mechanically; not
done yet pending that decision.

**Not touched, deliberately:** Scenario A/B (`greece_clustered*.nc`) and R5's
clustered family. Those are pre-solved binary networks, independent of the CSV
source files this fix changed, and are the thesis's already-drafted Chapter 3/4
spine — re-solving them this close to submission, with prose already written
against their specific numbers, was judged too risky for tonight. They remain
correctly caveated under D0 as before (Scenario A/B: CF 6.08%, the worst-affected
tier, understated ~3.9×; R5: CF 17.46%, understated ~27%).

## Outstanding author input

All resolved as of 2026-10-02. Items 1-4 were already filled in metadata.json
(department, division, registration number 5725, supervisor Prof. Michael C.
Georgiadis, Thessaloniki/October 2026) by the time this list was checked
against it. Item 5 (code availability, Appendix E) was resolved today: cites
the private GitHub repository (AntoniosTroullos/energy-investment-platform),
available to the committee on request; MODEL is not yet hosted remotely.

The 10 `[VERIFY:]` markers in Chapter 1 and the 4 outstanding references
(draft RES framework, DAPEEP URL, NECP official URL, TIMES) noted below as
still open were also already resolved by the time they were checked tonight
-- this list had not been updated after that work. NECP's citation still uses
the IEA policy-tracker URL, not a ypen.gov.gr PDF: several targeted searches
could not locate the Ministry's own hosted copy. If the author has that link
on hand, it is a one-line swap in references.csv.
