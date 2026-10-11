<!--
Chapter 3 source. Same marker conventions as Chapter 2.
Every numeral must appear in numbers_ledger.csv or numbers_allowlist.txt.
Run: python thesis/scripts/check_numbers.py
-->

# SYSTEM RESULTS & SCENARIO COMPARISON

## 3.1 Model Validation and Benchmarking

This chapter opens with validation rather than with results. The ordering is
deliberate: two of the checks below identify real defects in the modelling chain,
and the direction in which those defects bias the results governs how every
subsequent number in this thesis may be read. Presenting the results first and
the caveats afterwards would invert that dependency.

Four classes of check are reported. The first establishes that the conversion and
accounting relationships hold exactly. The second compares modelled renewable
availability against observed output. The third tests the siting rules against
assets whose permissibility is already known. The fourth examines sensitivity to
the temporal representation.

### 3.1.1 Analytical and Energy Balance Verification

The conversion relationships of Section 2.8 are verified analytically, on inputs
whose correct outputs are known by construction rather than by simulation. One
unit of electricity through an electrolyser of efficiency 0.7 must yield 0.7
units of hydrogen; a heat pump with a coefficient of performance of 3 must yield
3 units of heat; a gas boiler of efficiency 0.93 must yield 0.93 units. Hydrogen
consumed to produce heat must be counted once, in the hydrogen balance, and not
again in the heat balance. Combustion emissions must be attributed once, at the
shared gas bus, and not additionally at each consuming link. These properties are
asserted as tests rather than inspected after the fact, so a change that breaks
one of them fails the suite rather than producing a quietly wrong result.

Accounting closure is verified at the level of a whole solved system. The
standalone gas model provides the clearest demonstration, because its quantities
are externally anchored. Table 5 reports the outcome.

[[TABLE:T-gas-roundtrip]]

Supply across the entry points totals 78.7499 TWh, which is matched exactly by
total load of 78.7499 TWh, decomposed into 70.1599 TWh of domestic demand and
8.5901 TWh of exports (each figure independently rounded to four decimals, so
the two do not sum to the displayed total at that precision). The residual is
0.000000 TWh. The domestic and export
quantities reproduce the published figures of 70.16 and 8.59 TWh that the loads
were constructed from.

The interpretation of this result requires care, and it is stated explicitly
because the obvious reading is wrong. The model's loads were built *from* those
published figures. Reproducing them therefore demonstrates that network
construction, the solve and weighted annual aggregation preserve the input
quantities without loss or duplication across 864 snapshots weighted to 8,760
hours. It is a conservation check on the pipeline. It is not an independent
validation of the published figures, and no claim of that kind is made.

The acceptance criteria applied to the coupled model are summarised in Table 6.

[[TABLE:T-validation-checks]]

One entry in that table deserves separate comment, because the check itself was
found to be defective. The bus balance criterion requires the residual at every
bus and snapshot to fall below a tolerance far smaller than any physically
meaningful quantity. The diagnostic implementing that check called the modelling
framework's energy balance routine without specifying a rounding precision, and
so inherited a library default coarser than the tolerance it was testing against.
The consequence is that no solve of realistic size could ever have passed,
irrespective of its quality: the check was comparing a quantity rounded to less
precision than the bound it was being compared with. Specifying the precision
explicitly revealed the true residual to be at the level of floating-point noise.

This is reported rather than quietly corrected because it illustrates a failure
mode specific to automated validation. A check that cannot pass is
indistinguishable, from the outside, from a model that cannot satisfy it. The
defect was found only because a production run was attempted and its refusal
investigated rather than accepted.

### 3.1.2 Benchmarking Wind Availability Against Observed Output

Modelled renewable availability can be compared against published generation,
and for wind this comparison is decisive for how the rest of the thesis is read.
The benchmark is the national renewable operator's annual bulletin, from which an
observed fleet capacity factor of 23.83 % is computed. Table 7 sets the modelled
availability of each run family against it.

[[TABLE:T-wind-benchmark]]

[[FIGURE:F-wind-benchmark|Wind availability by run family against the observed benchmark. Source: model output.]]

[[FIGURE:F-wind-duration|Availability duration curves, post-correction: the national committed series and the mid_2026_monthly_days case series, both now derived from the corrected and calibrated power curve. Source: model output.]]

As first found, the two defects described below were neither uniform in
magnitude nor consistent in direction — one understated availability, the
other overstated it by a larger margin — and that asymmetry is the central
finding of the validation chapter. Table 7 reports the corrected state: every
run family now traces to the same calibrated series and none retains a
qualification.

Two distinct defects were present. The first affected the committed availability
series. Its cause was an error of formulation: aerodynamic power rises with the
cube of wind speed, so interpolation between cut-in and rated speed must be
cubic in the speed, as Section 2.4 sets out, and the implementation instead
cubed the normalised speed fraction, a different and systematically smaller
function across the operating range. Before correction, the committed series
averaged 0.0706 and 0.0784 per unit (regional and clustered respectively), ratios
of 0.296 and 0.329 against the benchmark. The correction, together with a
calibration procedure that scales a profile to a target observed capacity
factor, was implemented and tested but not applied until the final validation
stage of this thesis; applying it is the correction recorded for the
second defect below, since both availability series share the same underlying
fix. The committed series now averages 0.2099 and 0.2358 per unit, ratios of
0.881 and 0.990 against the benchmark — no longer a defect by this comparison.

Scenarios A and B, which provide the price and dispatch basis for the economic
analysis of Chapter 4, were subsequently re-solved against the corrected
clustered series. In both cases the capacity- and time-weighted wind
availability factor is 23.834 %, a ratio of 1.000 against the observed benchmark.
The solved dispatch factor is lower, at 18.59 %, because 21.99 % of available
wind energy is curtailed. This distinction is material: 23.834 % tests the
meteorological input and its power-curve transformation, whereas 18.59 % is an
endogenous outcome of dispatch, network and storage constraints. The revised
economic results in Chapter 4 therefore no longer inherit the former wind-input
bias. The `mid_2026_monthly_days` and `long_2026_seasonal_weeks` cases that
feed the temporal-aggregation comparison of Section 3.1.4 were likewise
rebuilt and re-solved against the corrected, calibrated series; neither
carries a qualification in Table 7.

The second defect is unrelated to the first and was found while assembling the
evidence for this chapter. The availability series used by the stylised
13-region runs averaged 52.02 % of installed capacity, a ratio of 2.183 against
the benchmark: not understated but overstated, by more than a factor of two.
Examination of the series showed that it was not a power curve output at all.
Its mean was 0.5169 per unit, its minimum 0.2600 and its maximum 0.8600, and the
share of hours falling below 0.05 was 0.00 %. A wind capacity factor series must
contain calm hours, and this one contained none; its minimum alone exceeded twice
the observed national annual mean, which no representation of turbine output can
do. The solar series in the same files behaved correctly, with 41.67 % of hours
at exactly zero availability and a maximum of 1.0000, which localised the defect
to the wind path rather than to the profile construction as a whole.

Tracing the defect to its source rather than merely its symptom showed that it
was not a second, independent formulation error. The affected file was last
written several weeks before the correction described above was applied to the
national series it is built from; it was a stale derived artefact, produced from
an earlier state of that source file and never regenerated afterwards, not a
distinct bug in the resampling code that builds case-specific inputs from it.
Once this was established, the same correction and calibration procedure used
for the first defect was applied and the case was rebuilt and re-solved. The
corrected series shows the calm-hour structure the uncorrected one lacked: 13.8 %
of hours fall below 0.05 per unit, against 0.00 % before, and no hard floor
remains. Section 3.7 reports the coupled production run against this corrected
series. The temporal-aggregation comparison of Section 3.1.4 draws on the same
case family and was rebuilt and re-solved alongside it; its figures carry no
qualification.

Both defects were found by comparing model output against an external observation
rather than by inspecting the code. This is the argument for benchmarking as a
routine step rather than an optional one: neither error announced itself, both
produced plausible-looking solved systems, and both would have survived into the
results had the comparison not been made.

### 3.1.3 Spatial Constraint Verification Against the Existing Fleet

The siting rules of Section 2.9 can be tested against assets whose permissibility
is independently known, because a plant that exists was evidently permitted under
the regime in force when it was built. Applying the draft framework's rules to
the existing fleet therefore provides a check on the implementation. Table 8
reports the outcome.

[[TABLE:T-spatial-qa]]

Of 63 wind and solar clusters evaluated, 5 would not be sitable under the draft
framework: 1 wind cluster and 4 solar clusters. The result is best read as a
property of the draft rules rather than of the model. These are real operating
installations; the finding is that the draft framework, applied as written, would
prohibit a small number of facilities that already exist. That is a coherent
outcome for a tightening of siting policy, and the small proportion involved
suggests the implementation is neither inert nor excessively aggressive. The
rules applied are those of the consultation draft, which the framework approved
afterwards may have altered, so the count is a property of that draft rather
than of the instrument now in force.

### 3.1.4 Sensitivity to Temporal Aggregation

The representations of Section 2.6 can be compared against one another. Table 9
reports two reduced representations of the same system.

[[TABLE:T-aggregation]]

The objectives differ by 0.49 %, and total load differs by a correspondingly
small margin. This is a sensitivity between two reduced representations, not a
validation against a full chronological year, and it is reported as such. The
comparison establishes that the solution is not strongly sensitive to which of
these two reductions is chosen; it establishes nothing about how either compares
with an 8,760-hour reference, because no such reference has been produced. The
distinction matters because reduced representations are known to understate the
value of storage and the cost of scarcity, and a comparison between two of them
cannot detect a bias they share.

## 3.2 The Reconciled Generation Inventory

The reconciliation procedure of Section 2.2.2 produces a result that is of
interest independently of the modelling it supports, because it quantifies the
difference between what is licensed and what is operating.

The merged registers describe 1,026 individual assets, which are aggregated into
107 spatial clusters. Calibrating against published operating capacities changes
the picture substantially, and differently for each technology. Solar capacity in
the merged registers totals 3,070 MW against a published operating total of
7,545 MW, a calibration factor of 2.458. Wind totals 5,664 MW against 5,016 MW,
a factor of 0.8856. Biomass totals 201.5 MW against 137 MW, a factor of 0.6798.

The solar discrepancy is the most consequential and the most instructive. The
registers capture well under half the operating solar capacity, which is
consistent with a fleet containing a large number of small installations that
fall below the threshold at which projects appear in the trackers and licence
exports used here. Wind, by contrast, is over-represented: the registers include
capacity that is licensed but not generating. The two errors run in opposite
directions, which is why no single correction factor could have been applied, and
why a model built on uncalibrated register data would have misstated the relative
scale of the two technologies by a factor of nearly three.

A practical consequence is recorded here. Not every asset can be placed
geographically: 41 of the 62 biomass records, representing 75.4 MW of calibrated
capacity, lack usable coordinates. These are retained in national totals but
cannot enter the spatially resolved network. The quantity is small relative to
the system but material relative to the biomass fleet, and it is stated so that
the omission is visible in any regional biomass result.

[[FIGURE:F-reconciliation|Merged register capacity against capacity calibrated to published operating totals, with the calibration factor shown above each pair. Source: model output.]]

## 3.3 Scenario A: Baseline Dispatch and Prices

Scenario A solves the clustered network under the baseline assumptions of
Section 2.1. Its weighted-mean planning shadow price across buses is
71.41 EUR/MWh, and its load-weighted equivalent is 77.25 EUR/MWh. The difference
between the two indicates that demand
is modestly concentrated in higher-priced hours, as expected.

Solar contributes 11.082 TWh, gas 10.471 TWh, wind 8.169 TWh, hydro
4.960 TWh, battery discharge 3.731 TWh and biomass 0.349 TWh. The corrected wind
series therefore changes the physical interpretation of the baseline: wind is a
material contributor rather than a residual one, while gas remains the principal
dispatchable source.

Lignite produces 0.000 TWh. This is the clearest single result in the chapter and
it follows directly from the cost ordering established in Section 2.2.4. Lignite
carries a marginal cost of 157 EUR/MWh against 108.8 EUR/MWh for gas, so it is
never economic to dispatch ahead of gas, and in a least-cost formulation with
sufficient gas capacity it is therefore never dispatched at all. The lignite fleet
is present in the model, is available, and does not run. No retirement policy, no
emissions constraint and no renewable target is required to produce this outcome;
cost ordering alone is sufficient.

Wind's contribution corresponds to a dispatch capacity factor of 18.59 %. This
does not conflict with the calibrated input factor of 23.834 %: the difference is
the 21.99 % share of available wind energy that the optimisation curtails. The
separation of input availability, dispatched output and curtailment prevents an
operational outcome from being misread as a failure of meteorological
calibration.

## 3.4 Scenario B: Post-Lignite and Spot-Gas Pricing

Scenario B re-solves the identical network with the lignite fleet retired and gas
repriced from the planning-basis figure to the spot figure of 144.0 EUR/MWh.

The weighted-mean planning shadow price rises to 94.01 EUR/MWh and the
load-weighted price to 101.79 EUR/MWh. The objective rises from
1.2230 billion EUR per year to 1.5915 billion EUR per year.

The dispatch, however, is almost exactly unchanged. Gas produces 10.471 TWh,
hydro 4.960 TWh, wind 8.169 TWh and biomass 0.349 TWh, all unchanged at the
reported precision. Solar moves from 11.082 to 11.076 TWh and battery discharge
from 3.731 to 3.737 TWh, differences of well under a tenth of a per cent.

As in Scenario A, wind availability is 23.834 %, dispatch is 18.59 % and
curtailment is 21.99 %. Since both scenarios use the same corrected renewable
inputs and differ only in the lignite and gas assumptions, their comparison
isolates the scenario intervention rather than a change in weather data.

## 3.5 Comparison of the Two Scenarios

Table 10 sets the two scenarios side by side with relative changes.

[[TABLE:T-scenario-comparison]]

[[FIGURE:F-scenario-comparison|Generation by carrier and weighted-mean planning shadow price under the two scenarios. Generation is unchanged while the price rises by almost a third. Source: model output.]]

The comparison yields a result that is more informative than a simple shift in
the generation mix would have been. Prices rise by 31.65 % on a weighted-mean
basis and 31.76 % on a load-weighted basis, and system cost rises by 30.14 %,
while physical dispatch is unchanged to within rounding in every carrier.

Both components of the scenario contribute to this outcome, for different
reasons. Retiring lignite removes no generation because, as Section 3.3
establishes, lignite was already producing nothing: its marginal cost placed it
outside the merit order regardless of whether it remained in service. The
retirement therefore has no physical effect in this model at all. Repricing gas
does not displace gas from the margin either, because no cheaper technology has
spare capacity to substitute for it; the price increase passes through to the
shadow price almost undamped, raising system cost without altering the quantity
dispatched.

Two implications follow. The first concerns the lignite phase-out: within this
model's economics, the transition away from lignite is already complete on cost
grounds before any retirement policy is applied. The policy is therefore
consequential for employment, for regional economies and for the utility's
balance sheet, but it is physically neutral in the dispatch. The second concerns
exposure to fuel prices: a system in which gas sets the price in most hours, and
in which no alternative has spare capacity, transmits a commodity price shock
almost fully into system costs. The 31.65 % price increase arises from a change
in a single input.

The magnitude remains conditional on the model boundary. Representative days,
stylised transmission corridors and the absence of cross-border trade constrain
the available substitution channels, so the result should be read as a
controlled planning-model sensitivity rather than a forecast of wholesale market
pass-through. Within that boundary, however, the comparison is internally
consistent: both scenarios share the same demand, corrected wind availability,
installed fleet and temporal weights.

## 3.6 Short-Term Operational Case

The forecasting chain of Section 2.3.1 is exercised end to end on two consecutive
days, to demonstrate that the components connect: a demand forecast is produced,
allocated to regions, converted into a network input, and solved for dispatch.

The case is reported as a functional demonstration and not as a measure of
predictive skill. As Section 2.3.1 records, the forecasting models have not been
evaluated by rolling-origin backtesting, so no claim about sustained accuracy is
available. What the case establishes is that the pipeline executes without manual
intervention and produces a dispatch consistent with its inputs.

## 3.7 The Coupled Production Run

### 3.7.1 Scope, Boundary and Inputs

A production run of the multi-carrier model of Section 2.8 was constructed and
solved for the Greek system. Its configuration is given in Table 11.

[[TABLE:T-r8c-scope]]

The run represents the current system rather than a future one: its target year
is 2025 and it draws demand and weather from 2026. It uses the 13-region
non-clustered electricity base, with the stylised rather than the reconciled
fleet. Its temporal representation comprises 288 snapshots weighted to 8,760
hours, drawn from real-weather representative days. Cross-border trade is
disabled and electrolyser investment is disabled, so the hydrogen fleet is fixed
at its existing capacity. The hydrogen target is expressed as final demand, at
207,557.27 MWh per year, under a policy in which electrolysis draws on grid
electricity. Carbon is priced at 80.0 EUR per tonne.

The demand boundary is stated explicitly because multi-carrier models are
particularly exposed to double counting. Incremental heat demand is excluded from
the electricity balance, since it is served through the heat carrier; residual
gas demand is restricted to the industrial and compressed-natural-gas sectors,
excluding power generation and incremental heat, both of which are represented
explicitly elsewhere in the model.

The run carries 9 provenance records and 9 hashed input files, and was accepted
by the solver gate.

### 3.7.2 Energy Balance, Generation Mix and Capacity

The run's system outputs are reported in this thesis. An earlier solve, against
the availability series later found to be a stale, defective artefact (Section
3.1.2), produced results that were withheld for that reason; the series has since
been corrected and the run re-solved against it, and what follows is the
corrected run.

What the run establishes first is methodological, and holds independently of any
particular solved values. A multi-carrier planning problem for the Greek system
can be assembled from documented sources, with every input carrying a provenance
record and a hash; the validation gate that previously refused the run while its
inputs were incomplete accepts it once they are complete; the carrier balances
close to the level of floating-point noise; and the unit conventions survive the
round trip described in Section 2.8. Taken with the analytical tests of Section
3.1.1 and the reference case built to exercise the formulation, this constitutes
evidence that the formulation is correct and that a production solve is
reachable.

Electricity-only demand, with incremental heat excluded per the demand boundary
of Section 3.7.1, is 49.915 TWh per year — within half a per cent of the 49.9146
TWh carried by the same case in Section 3.1.4, which is expected, since both draw
on the same regional load forecast. Total demand across all four carriers is
106,954,818.64 MWh per year. Table 12 sets out the solved generation mix.

[[TABLE:T-r8c-generation]]

Gas supplies the largest share of generation, 73.475 TWh, from a solved capacity
of 23,067 MW operating at a 36.36 % capacity factor; wind follows at 22.023 TWh,
solar at 15.606 TWh, hydro at 5.619 TWh, and lignite at 0.144 TWh. Wind's capacity
factor from dispatch, 22.25 %, sits close to the 23.83 % DAPEEP benchmark of
Section 3.1.2, as the corrected and calibrated series is built to do. The model
expands wind capacity endogenously from its 7,970 MW starting point to 11,300 MW,
an increase of 3,330 MW or 41.78 %; solar does not expand beyond its starting
8,920 MW. Total system cost is EUR 4,254,905,347.11 per year, of which EUR
3,283,981,673 is generator variable cost, EUR 451,548,000 generator capital, EUR
276,566,398.21 link capital (the gas-to-power, heat and electrolysis conversion
paths) and EUR 242,809,275.87 link variable cost. CO2 emissions, counted once at
the shared gas entry per the convention of Section 2.8, are 13,490,058.36 tonnes
per year.

### 3.7.3 Shadow Prices and Price Formation

The solved electricity shadow price is no longer uniform across the mainland.
Ten of the eleven mainland buses share an identical price of EUR 79.5508 per
MWh; the eleventh, North Aegean, is lower at EUR 74.0531, a spread of EUR 5.50
between the two — against a flat EUR 24.13 across every bus in the withheld
run, where the uncorrected series' absence of calm hours had left wind
abundant enough, everywhere, that no mainland corridor ever bound. (Crete and
South Aegean are island systems outside this mainland grouping; their own
solved prices are EUR 80.5362 and EUR 70.2709 respectively, and are not part
of the mainland spread above.) A non-trivial
spread across otherwise symmetric mainland buses is itself a more credible
outcome for a stylised corridor topology than the earlier flat price was.

The mean of the eleven mainland buses' own time-weighted prices is EUR 79.0510
per MWh and the load-weighted mean across the whole network is EUR 77.0214 per
MWh; the two differ because demand and price are not independent across
snapshots. The highest price observed on any mainland bus, EUR 157.0000 per
MWh, is exactly lignite's marginal cost (Section 3.3), confirming that lignite
sets the price at the system's tightest hours even though its annual capacity
factor is only 0.87 %. Decomposing the
weighted hours by which technology is marginal: a zero- or near-zero-cost
renewable (solar surplus or wind) sets the price in 23.96 % of hours (wind alone
in 20.46 %, solar surplus in 3.50 %), hydro at its EUR 12.00 marginal cost in
6.96 %, gas at its full input-side marginal stack (Section 3.7.1's gas
decomposition, EUR 116.87 per MWh_e) in 2.66 %, and the remaining 66.42 % of
hours at intermediate levels — a partially loaded mix of gas units below their
full stack cost, consistent with gas supplying the largest share of generation
while rarely being the single price-setting technology at its ceiling price.

The gas and hydrogen shadow prices, EUR 43.5882 per MWh_HHV and EUR 118.7256 per
MWh_LHV respectively, and the heat shadow price of EUR 28.5044 per MWh_th, follow
the same accounting as the withheld run (Section 3.7.1's input-side link-cost
derivation is unaffected by the wind correction, since it depends only on the
gas commodity price, plant efficiency, VOM and the carbon price — all inputs,
not solved outputs).

These figures are not compared against Scenario A's EUR 71.41 per MWh in Section
3.3: the two runs differ in fleet (stylised here, reconciled in Scenario A),
temporal representation and scope, and such a comparison would conflate those
differences with the wind correction itself. The two mean prices are, nonetheless,
now of comparable order of magnitude, which was not true of the withheld run.

## 3.8 Hydrogen Feasibility Against National Targets

The hydrogen question can be addressed without a coupled optimisation, by
capacity arithmetic alone, and the result does not depend on the wind
availability defects discussed above. Table 13 assembles the relevant figures.

[[TABLE:T-h2-feasibility]]

[[FIGURE:F-hydrogen-feasibility|Hydrogen output bounds against the national trajectory. Both the operational base and the licensed upper bound fall below the target at every horizon. Source: model input files and policy documents as cited.]]

The national plan states both a production target and an electrolyser capacity
objective for the same year: 0.92 TWh of production from 231.0 MW of
electrolysis. These two figures jointly imply a utilisation of 45.46 %, which is
adopted here rather than assumed, since it is the plan's own internal
assumption.

Applying that utilisation to the installed base gives the feasibility bounds. The
status-filtered project database, which counts 3 operational or
committed sites totalling 52.12 MW, would produce 0.208 TWh per year. The
licensed register, counting 16 projects totalling 271.55 MW, would produce
1.081 TWh per year if every licensed project were built and operated at the
plan's implied utilisation.

Against the plan's own hydrogen trajectory of 1.2 TWh by 2030, rising to 5.6 TWh
by 2040 and 20.2 TWh by 2050, these bounds fall short at every horizon. The
operational base covers 17.3 % of the 2030 target, 3.7 % of the 2040 target and
1.0 % of the 2050 target. Even the licensed upper bound, which assumes complete
build-out of every licensed project, covers 90.1 % of the 2030 target, 19.3 % of
the 2040 target and 5.4 % of the 2050 target.

The conclusion is that the 2030 target is not reachable from the operational base
and is marginal even on the assumption that every licensed project is completed,
while the 2040 and 2050 trajectories would require capacity far beyond anything
currently in the pipeline. This is a diagnostic finding rather than an
optimisation result: it states what the existing and licensed fleet can produce
at the plan's own utilisation, and compares that with the plan's own targets. It
makes no claim about whether the additional capacity will be built.
