<!--
Chapter 4 source. Same marker conventions as Chapters 2 and 3.
Every numeral must appear in numbers_ledger.csv or numbers_allowlist.txt.
Run: python thesis/scripts/check_numbers.py
-->

# SITING & ECONOMIC EVALUATION

## 4.1 Economic Parameters

This chapter translates the solved systems of Chapter 3 into project-level
financial indicators. Four are reported: net present value, internal rate of
return, levelised cost of energy, and payback period. Each is computed from the
same discounted cash-flow formulation, applied either to an existing generation
cluster or to a prospective candidate site.

The parameters governing that calculation are given in Table 14.

[[TABLE:T-economic-parameters]]

A single real discount rate of 7 % is applied to every technology. As Section
2.2.4 explains, this is a deliberate simplification: the cost of capital varies
by technology and by the risk profile of the revenue arrangement, and no
defensible technology-specific figures for the Greek market were identified.
Section 4.7 quantifies what this choice is worth. Asset lifetimes are
technology-specific and taken from the same cost basis as the planning model, so
that a technology's economic life is consistent between the two ledgers.

Revenue is computed as captured revenue, meaning the sum over snapshots of
dispatch multiplied by the nodal planning shadow price in that snapshot and by
the snapshot weight. This is not the same as annual energy multiplied by an
average price, and the difference is the subject of Section 4.2.

Three exclusions should be stated at the outset. Storage arbitrage revenue is not
included in any figure reported here. Grid connection charges enter only through
the screening distances of Section 4.4 and not as a modelled cost. Revenue
support mechanisms are not represented, so every result is a merchant case.

A fourth qualification concerns interpretation rather than data validity. The
economics derive from Scenarios A and B after both were re-solved with the
corrected wind series: its availability factor is 23.834 %, equal to the
observed benchmark at the reported precision, while its dispatch factor is
18.59 % after curtailment. The former wind-input bias therefore no longer
qualifies the results. They remain conditional merchant-case appraisals,
however, because the solved prices are planning shadow prices from a reduced
network, not forecasts of realised market revenue.

## 4.2 Captured Revenue and Price Cannibalisation

The distinction between captured price and average price is not a refinement; it
determines the sign of several results in this chapter.

A generator earns the price prevailing in the hours when it actually produces. A
technology whose output is concentrated in hours when many similar units are also
producing will depress the price in precisely those hours, and will therefore
earn less per unit than the system average. Computing revenue as annual energy
multiplied by an average price assumes this correlation away.

The magnitude of the effect in Scenario A is substantial. The system-wide
weighted-mean planning shadow price is 71.41 EUR/MWh. Against that, solar
clusters capture 27.31 EUR/MWh, wind clusters 78.44 EUR/MWh, hydro clusters
99.46 EUR/MWh and biomass clusters 108.17 EUR/MWh.

Solar therefore earns well under half the system average, while wind and the two
dispatchable carriers earn above it. The mechanism is the one described above:
solar output is strongly simultaneous across the fleet and depresses its own
price, whereas hydro and biomass can place output in higher-priced hours. Wind's
captured price is also above the unweighted bus mean because its spatial and
temporal production pattern is not uniform. An appraisal using the system
average would therefore overstate solar revenue and understate the other three
technologies in this solved case.

[[FIGURE:F-cannibalisation|Captured price by carrier against the system weighted mean under both scenarios. Solar captures well below the system average while the dispatchable carriers capture above it. Source: model output.]]

Scenario B reproduces the pattern at a higher level, with solar capturing
35.47 EUR/MWh, wind 102.59 EUR/MWh, hydro 131.02 EUR/MWh and biomass
143.08 EUR/MWh against a system mean of 94.01 EUR/MWh. The ordering is unchanged,
which indicates that it is structural rather than an artefact of one price
level. The absolute values nevertheless remain scenario-dependent: captured
price is a joint outcome of the resource profile, regional location, dispatch
constraints and the marginal technology.

## 4.3 Investment Evaluation of the Existing Clustered Fleet

The clusters of Section 2.5 can be appraised directly, since the solved scenarios
give each one its own dispatch and its own captured price. Table 15 reports the
outcome by technology.

[[TABLE:T-cluster-investment]]

None of the 34 solar clusters has positive net present value in Scenario A,
whereas 15 do in Scenario B; their mean internal rates of return are 3.06 % and
5.94 %. All 6 biomass clusters are positive in both scenarios, with mean returns
of 11.65 % and 18.59 %. Seven hydro rows have positive calibrated capacity and
all are positive in both scenarios, with mean returns of 8.57 % and 12.76 %.
For wind, 11 of 29 clusters are NPV-positive in Scenario A and 13 in Scenario B;
among the 26 clusters for which an internal rate of return is defined, the mean
rises from 4.64 % to 9.04 % and the median from 4.56 % to 8.02 %.
[[FIGREF:F-cluster-npv-map]] places these results geographically and shows that
technology alone does not determine value: clusters of the same technology span
both positive and negative outcomes because resource quality, dispatch timing
and regional prices differ.

[[FIGURE:F-cluster-npv-map|Net present value by positive-capacity cluster under Scenario A. Colour carries value, marker shape carries technology and marker area carries calibrated capacity. Source: model output.]]

[[FIGREF:F-irr-distribution]] shows how these returns are distributed within each technology, and
[[FIGREF:F-ab-npv-scatter]] shows how each individual cluster moves between the two scenarios. The
movement is one-directional: all 76 positive-capacity clusters gain value under
Scenario B. The change is not uniform, because each cluster has a different
dispatch profile and therefore a different exposure to the hours in which gas
sets the marginal price. The increase is large enough to move 15 solar clusters
and two additional wind clusters into positive NPV.

[[FIGURE:F-irr-distribution|Internal rate of return by positive-capacity cluster and technology under both scenarios, against the 7 % discount rate. Horizontal bars show the median among defined IRRs. Source: model output.]]

[[FIGURE:F-ab-npv-scatter|Net present value of each positive-capacity cluster under Scenario A against Scenario B. Points above the dashed line gain value under Scenario B. Source: model output.]]

The hydro source contains an eighth row with zero calibrated capacity. Applying
the cash-flow formula to a zero-scale asset produces no meaningful project
return, so that row is retained for data traceability but excluded from captured-
price and IRR summaries and from the figures. This is not selective reporting:
the exclusion criterion is physical capacity greater than zero and is applied
before comparing outcomes. More generally, the cluster results describe the
operation of an existing fleet under replacement-cost assumptions; they do not
constitute a greenfield construction appraisal. The improvement from Scenario A
to Scenario B should likewise be interpreted as exposure to the gas-price
assumption, not as a change in the underlying assets or their resource quality.

## 4.4 Candidate Site Screening Results

The screening procedure of Section 2.9 yields the candidate set reported in
Table 16.

[[TABLE:T-candidate-screening]]

The procedure generates 718 candidate cells. Each carries its buildable fraction
after exclusions, its overlap with protected designations, its distance to the
nearest substation and transmission line, and the identity and distance of the
nearest world heritage site.

These screening outputs are the most robust results in the chapter. They depend
on geometry and on the published designations, not on any solved dispatch. A
cell's buildable fraction, its distance to the grid and its protected-area
overlap would therefore be unchanged by any energy-market scenario.

[[FIGREF:F-candidate-carving]] shows the screening operating on two individual cells, and makes
visible the asymmetry between the two technologies' rules described in Section
2.9. A solar cell has any intersecting protected area subtracted from its
geometry, because the designation is treated as prohibitive. A wind cell does
not: for wind the same designation raises a conditional licensing flag and the
geometry is left intact, the hard subtraction coming instead from banned
regions, banned regional units and small islands. The buildable fraction a cell
reports is therefore not comparable across technologies without knowing which
rule produced it.

[[FIGURE:F-candidate-carving|Two candidate cells with their exclusions subtracted. Left: a solar cell clipped by an intersecting Natura 2000 site. Right: a wind cell clipped by a banned regional unit, its protected-area overlap left intact as a conditional flag. Dashed outlines mark the original cell. Source: screening output.]]

Two limitations stated in Section 2.9 bear on how the set should be read. The
resource score attached to each cell derives from a coarse placeholder zoning
layer rather than from the reanalysis data used for the operating fleet, so it
orders cells only approximately and is not a resource assessment. And because two
provisions of the draft framework are not implemented, the set is less
restrictive than that framework would be in practice.

## 4.5 Candidate-Level Investment Evaluation

Each screened cell can be appraised by the same discounted cash-flow method
applied to the existing fleet, using the region's solved price and the
technology's capacity factor.

A derivation note is required here, because the platform's own interface cannot
produce this result for the scenarios used in this thesis. Its candidate
analysis accepts only cases matching a future-year naming pattern, and every such
case is excluded from this thesis by the decision recorded in Section 3.1.2's
companion discussion of run families. The results below were therefore produced
by calling the platform's own investment functions directly, supplying Scenario A
and B metrics in place of a future-year case. The financial calculation is
unchanged; only its inputs differ.

Of the 718 cells, 652 could be evaluated. The remaining 66 have centroids that
fall outside all 13 model regions, mostly offshore or on small islands, and
without a region they have no price to capture.

For solar, the median net present value is 110.5 million EUR under Scenario A,
rising to 193.9 million EUR under Scenario B, with median internal rates of
return of 14.96 % and 20.66 % and a median levelised cost close to
41.91 EUR/MWh. Wind displays much greater scenario sensitivity: median NPV moves
from -40.4 million EUR in Scenario A to 0.3 million EUR in Scenario B, while the
median internal rate of return rises from 3.66 % to 6.97 %. None of the 215 wind
candidates has positive NPV in Scenario A, compared with 206 in Scenario B.

These figures carry a limitation more fundamental than the wind caveat, and it
must be stated plainly because it bears directly on what the screening is for.
The economics do not discriminate between sites. Three features of the derivation
combine to produce this: annual generation uses the carrier's national capacity
factor rather than a site-specific resource estimate; the captured price is the
region's average across all technologies rather than a technology-specific
captured price; and 96.4 % of solar cells, together with 100.0 % of wind cells,
reach the assumed capacity cap, so their assumed capacity is identical. The consequence is visible in the results
themselves, where the median solar net present value equals the maximum: the
majority of cells return exactly the same figure. [[FIGREF:F-candidate-degeneracy]] shows both halves of
this mechanism together.

[[FIGURE:F-candidate-degeneracy|Left: candidate cells reaching the assumed capacity cap, by technology. Right: the spread of appraisal outcomes across the solar cells under Scenario A, each metric on its own scale, with the median marked. Source: model output.]]

What the candidate economics therefore provide is a regional and technological
screen, not a site ranking. Two cells in the same region with the same buildable
area receive the same appraisal regardless of their actual resource quality.
Using them to choose between neighbouring sites would attribute to the model a
discrimination it does not possess. Section 5.4 identifies the two changes that
would give it that discrimination: site-specific availability from the same
reanalysis data already used for the operating fleet, and a technology-specific
captured price per region.

## 4.6 Portfolio Construction and Portfolio Returns

Individual rates of return do not combine by averaging. A portfolio return must
be computed from the combined cash flows of its constituents, which is what the
platform's portfolio calculation does and what is reported here.

Taking every evaluable solar candidate as a single portfolio gives a return of
14.952 % under Scenario A and 20.6517 % under Scenario B, with payback periods
of 6.5136 and 4.7619 years. The wind portfolio moves from 3.6712 % to 6.9824 %,
with payback periods of 16.6614 and 11.6376 years. The combined portfolio across
both technologies returns 11.2387 % under Scenario A and 15.871 % under
Scenario B.

The scale of this portfolio must be stated, because it determines how the figures
should be read. The 437 evaluable solar candidates represent 84.97 GW of
capacity and an initial outlay of 50.55 billion EUR. Against an operating solar
fleet of 7,545 MW reported in Section 3.2, this is more than ten times the
capacity currently installed, and it far exceeds any plausible deployment
programme for a system whose total electricity demand is of the order of
49.915 TWh per year.

Two qualifications attach to the returns themselves. First, the portfolio is an
unconstrained aggregation of every evaluable cell: its initial outlay is
81.48 billion EUR, of which 50.55 billion EUR is solar and 30.94 billion EUR is
wind (the two components are rounded independently and so do not sum exactly
to the total). Second, adding this capacity would change dispatch and depress the prices
used to value it; the calculation is therefore a static screening appraisal,
not an equilibrium expansion plan.

This portfolio is therefore a statement of screened technical potential, not an
investment plan, and its return is a property of the candidate set rather than a
recommendation. Deploying any substantial fraction of it would depress the very
prices the appraisal assumes, since the captured prices used here come from a
solved system that does not contain the additional capacity. The portfolio
calculation is reported because it demonstrates the method and because the
underlying combination of cash flows is correct; it is not reported as an
investable proposition, and the cannibalisation mechanism of Section 4.2 is
precisely the reason it cannot be.

## 4.7 Sensitivity Analysis

The appraisal rests on parameters that are uncertain to differing degrees. A
one-factor-at-a-time analysis varies each in isolation, holding the others at
their base values, and records the resulting swing in net present value and
internal rate of return. The base case is a solar candidate at the capacity cap,
which Section 4.5 shows to be representative of 96.4 % of the solar set.

Under Scenario A the base case returns an internal rate of return of 14.8212 %. The
ordering of parameters by the net present value swing they produce is as follows.
Captured price and capacity factor each produce a swing of 96.54 % of the base
value for a variation of a fifth either way. The discount rate, varied between
5 % and 9 %, produces a swing of 93.38 %. Capital cost, varied by a fifth, produces
56.54 %. The degradation rate, varied across its published range, produces
18.95 %, and asset lifetime, varied between 30 and 45 years, produces 16.49 %.

[[FIGURE:F-tornado-npv|Sensitivity of net present value to each parameter varied in isolation, for both scenarios. Parameters are ordered by their effect under Scenario A so that the two panels are directly comparable. Source: model output.]]

Two features of this result are worth drawing out, because both serve as checks
on the calculation rather than as findings about the technology.

First, captured price and capacity factor produce identical swings. This is
necessarily so: revenue is their product, and a proportional change in either has
the same effect. The identity confirms the implementation, and it carries a
methodological implication — the appraisal cannot distinguish an error in the
price from an error in the resource, so the wind availability defect of Section
3.1.2 and a price error of the same proportion would be indistinguishable in
these results.

Second, the discount rate produces the third-largest swing in net present value
but a swing of exactly 0.0 percentage points in the internal rate of return. This
is correct by construction, since the internal rate of return is the discount
rate at which net present value vanishes and cannot itself depend on the rate
assumed. That it emerges exactly rather than approximately indicates the rate is
being solved rather than approximated.

The practical reading is that the appraisal is governed by revenue assumptions
above all. A fifth either way on captured price or capacity factor moves NPV by
almost the full base value, slightly more than the effect of the discount rate
across a range spanning the plausible cost of capital and substantially more
than the effect of capital cost. The corrected wind input removes the identified
calibration bias, but it does not eliminate resource, curtailment or future-price
uncertainty; the sensitivity analysis quantifies why those uncertainties remain
decision-critical.

## 4.8 Platform Demonstration

The methods of this thesis are delivered through a web application, and this
section describes what it does rather than repeating results already reported.

The application opens on a national map carrying the infrastructure layers of
Section 2.2.3: generation assets, substations, transmission corridors, gas
pipelines and entry points, and hydrogen projects and pipelines, each
independently toggled. [[FIGREF:ui-01-map-explorer]] shows this default view,
with the reconciled generation inventory of Section 3.2 clustered by proximity
and the gas and hydrogen networks drawn over it.

[[FIGURE:ui-01-map-explorer|The infrastructure view, showing the reconciled generation inventory clustered by proximity together with the transmission, gas and hydrogen layers. Each layer is independently toggled. Source: platform interface.]]

Switching from the infrastructure view to the analysis view renders the
candidate grid of Section 2.9 over the mainland, shown in
[[FIGREF:ui-02-candidate-cells]]. The grid covers the screening region rather
than the whole map, which is the visual counterpart of the 66 cells excluded
from appraisal in Section 4.5 for falling outside every model region.

[[FIGURE:ui-02-candidate-cells|The analysis view, with the screened candidate grid rendered over the mainland alongside the infrastructure layers. Source: platform interface.]]

Selecting a cell opens a panel giving its record.
[[FIGREF:ui-03-candidate-drawer]] shows the summary a selection returns, and
[[FIGREF:ui-04-screening-geometry]] the screening fields below it: buildable
fraction, distances to the nearest line and substation, the exclusion and
conditional-warning flags of Section 4.4, protected-area overlap, and the
identity and distance of the nearest world heritage site. The panel reports the
conditional Natura 2000 flag separately from the exclusion flag, which is the
interface counterpart of the rule asymmetry shown in
[[FIGREF:F-candidate-carving]].

[[FIGURE:ui-03-candidate-drawer|The asset detail panel for a selected candidate cell, giving its identity, technology and composite investment score. Source: platform interface.]]

[[FIGURE:ui-04-screening-geometry|The same panel scrolled to the screening record: connection distances, exclusion and conditional-warning flags, protected-area overlap and nearest world heritage site. Source: platform interface.]]

A separate configuration view, shown in [[FIGREF:ui-05-scenario-studio]],
exposes the screening controls as presets and sliders, so that the candidate set
can be filtered by budget tier, technology, connection distance and investment
score without editing a configuration file. Results of solved scenarios are
rendered on the same map, and the application reports whether each displayed
product is current with respect to the inputs it derives from, using the
staleness mechanism described in Section 2.10.

[[FIGURE:ui-05-scenario-studio|The configuration view, exposing the screening parameters as presets and controls. Changes apply to the candidate set shown on the map. Source: platform interface.]]

The purpose of the interface is to make the provenance of a number visible at the
point where it is used. Each panel states the scenario a figure comes from and
the assumptions behind it, which is the same discipline this thesis applies in
prose.
