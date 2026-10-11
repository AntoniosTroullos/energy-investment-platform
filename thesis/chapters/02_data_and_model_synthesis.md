<!--
Chapter 2 source. Markers consumed by build_docx.py:
  # TITLE                  chapter title, 20 pt, ALL CAPS, unnumbered, new page
  ## 2.1 Title             level 2, 16 pt
  ### 2.1.1 Title          level 3, 14 pt
  [[TABLE:T-id]]           insert the table spec of that id from thesis/tables/
  [[FIGURE:F-id|caption|source]]   figure placeholder
  $$ ... $$                display equation, numbered continuously at build time
  [VERIFY: ...]            a citation whose bibliographic entry is not yet verified

Every numeral in this file must appear in numbers_ledger.csv or
numbers_allowlist.txt. Run: python thesis/scripts/check_numbers.py
-->

# DATA & MODEL SYNTHESIS

## 2.1 General Information

This chapter develops the modelling framework from its data foundations to the
solved planning problem. It is organised in the order the pipeline executes, so
that each stage is introduced only after the inputs it consumes have been
described. The sequence is: acquisition and quality control of the underlying
datasets; construction of electricity demand, nationally and regionally;
conversion of weather data into renewable availability; spatial aggregation of
the generation fleet; temporal aggregation of the operating year; the electricity
planning model; its multi-carrier extension; the candidate site screening
procedure; and the software implementation that ties these together.

The study area is the Greek electricity system, represented at the level of the
country's 13 NUTS-2 regions. This resolution is adopted because it is the finest
spatial unit at which the socioeconomic proxies required for demand allocation
are published consistently, and because it corresponds to the administrative
boundaries used by the national statistical authority. Each region forms one
electrical node in the baseline network; a clustered variant subdivides these
nodes further according to the real distribution of generation assets, as
Section 2.5 describes.

A distinction is maintained throughout between the quality of different inputs,
because a planning model mixes observed data, published figures, values inferred
by this work, and assumptions adopted for the purposes of a scenario. Five
provenance classes are used. A *measured* value is an observation, such as a
metered load series. A *sourced* value is published by an identified external
body, such as a technology cost from a national energy agency. A *derived* value
is computed by this work from measured or sourced inputs through a stated
transformation. A *scenario assumption* is a choice adopted to define a case
rather than an estimate of reality. A *placeholder* is an input for which no
defensible figure was found, retained so that the model remains solvable and
labelled so that it is never mistaken for evidence. Every input described in this
chapter is assigned to one of these classes, and no placeholder is reported as a
result anywhere in this thesis.

Two scenarios are analysed throughout. Scenario A, the baseline, represents the
system as currently configured, with the lignite fleet present and natural gas
priced on a long-term planning basis. Scenario B, the alternative, applies two
structural changes to the same network: the lignite fleet is retired, following
the national utility's committed closure programme, and gas is repriced to a
spot-market figure. Both changes are grounded in documented facts rather than in
an assumed trajectory, and they are deliberately independent of one another: one
removes capacity, the other reprices the marginal fuel. Table 1 states the two
definitions.

[[TABLE:T-scenario-definition]]

As the table shows, the two scenarios share a network, a demand series and a
temporal representation, and differ only in the two stated respects. This is a
deliberate design choice: it means any difference in the results can be
attributed to those two changes alone, without the confounding effects that a
broader re-specification would introduce. The consequences of this design are
examined in Section 3.5, where the comparison turns out to be informative in a
way that was not anticipated.

The boundary of the analysis should be stated plainly, since several of the
limitations discussed later follow directly from it. The model is a least-cost
planning formulation. It determines the capacity mix and the dispatch that
minimise total annualised system cost subject to physical and policy
constraints. It is not a market simulation: it contains no unit commitment, no
ramping restrictions, no reserve requirements, no forced outages and no strategic
bidding behaviour. The dual variables it produces are planning shadow prices, and
they are referred to as such throughout.
They are not forecasts of wholesale market prices, and that distinction is
maintained in every results section.
Likewise, the financial indicators computed in Chapter 4 constitute investment
screening rather than a bankable valuation.

## 2.2 Data Acquisition and Quality Control

The model draws on public sources only. These fall into four groups: electricity
demand, the generation inventory, network and regulatory geography, and
technology costs. Each group is described below, together with the processing
applied to it and the checks used to establish that the processing is sound.

### 2.2.1 National Electricity Demand

The demand baseline is the national system load series published by the
Independent Power Transmission Operator, supplemented by the actual total load
reported through the European transparency platform. The two sources are used for
different purposes: the national series provides the long, consistent history
required to construct representative operating periods, while the transparency
platform provides the series used to train and evaluate the forecasting models of
Section 2.3.1.

Raw load data require correction before they can be used. Timestamps are
normalised to local time, and the hour-ending-24 convention used in the published
files is converted to the hour-beginning convention the model expects. Five
classes of defect are then flagged: missing timestamps, duplicate timestamps,
missing values, non-positive values, and values that depart implausibly from
their neighbours. Missing values are repaired by a fixed priority: the same hour
of the preceding week is used where available, since the weekly cycle dominates
the load shape; failing that, the mean of the adjacent days at the same hour;
failing that, short linear interpolation; and only as a last resort the series
median. Each repair is recorded alongside the value, together with the method
used and the original content of the field, so that no imputed value can later be
mistaken for an observation.

The outcome of this procedure is summarised in Table 2.

[[TABLE:T-load-qc]]

[[FIGURE:F-load-series|The quality-controlled national system load series, with the monthly mean overlaid. Source: model output.]]

The model-ready series contains 39,359 hourly observations with no missing
timestamps, no duplicate timestamps, no missing values and no non-positive
values. These four zeros are the acceptance criterion for the series, and they
are reported rather than assumed. The anomaly audit retains 151 rows, which are
flagged for review rather than removed: an extreme value may be a data error or a
genuine system event, and the two cannot be distinguished from the series alone.
Retaining them with a flag preserves that ambiguity instead of resolving it
silently.

### 2.2.2 Generation Inventory Reconciliation

No single public register describes the Greek generation fleet completely. Plant
locations are recorded in a collaborative geographic database; capacities and
operating status appear in national licensing registers; a separate international
tracker covers utility-scale renewable projects; and storage assets are best
covered by a national project map. Each source is incomplete in a different way,
and they overlap inconsistently. Constructing a usable inventory therefore
requires merging them and resolving the resulting duplicates.

Records are merged on a coordinate bucket combined with name matching, and
duplicates are resolved by source priority, with official licensing registers
taking precedence over the international tracker, which in turn takes precedence
over the collaborative database. A dedicated source is nominated for each
carrier, so that the carrier most reliably covered by a given register is taken
from that register rather than from the merge as a whole.

Merging alone does not produce correct national totals, because the registers
record licensed rather than commissioned capacity, and the discrepancy differs by
technology. The merged inventory is therefore calibrated to the operating
capacities published by the national renewable energy operator. This calibration
step is the most consequential processing decision in the data chapter, and its
effect is quantified in Section 3.2. In outline, the merged inventory yields
3,070 MW of solar capacity against a published operating total of 7,545 MW, a
calibration factor of 2.458; 5,664 MW of wind against 5,016 MW, a factor of
0.8856; and 201.5 MW of biomass against 137 MW, a factor of 0.6798. Solar is
therefore under-represented in the registers by a factor of roughly two and a
half, while wind and biomass are over-represented. The direction of the error is
not uniform across technologies, which is precisely why a single global
correction would have been inadequate.

The calibrated inventory comprises 1,026 individual assets, which are reduced to
107 spatial clusters by the procedure described in Section 2.5. Not every asset
can be placed geographically: 41 of the 62 biomass records, accounting for
75.4 MW of calibrated capacity, lack usable coordinates. These are retained in
the national totals but excluded from the spatially resolved network, and the
quantity involved is reported so that the omission is visible rather than
implicit.

### 2.2.3 Network, Spatial and Regulatory Layers

Three further families of geographic data are required: the electricity network,
the administrative geography against which demand and constraints are resolved,
and the environmental designations that restrict where new capacity may be built.

The network layers are drawn from the collaborative geographic database, which
provides 3,144 substations and 1,044 transmission line segments. These are used
for two purposes: to assign a connection rating to each generation cluster, as
Section 2.5 describes, and to measure the distance from each candidate site to
the nearest connection point, as Section 2.9 describes. They are not used to
construct the transmission topology itself, which is represented by stylised
inter-regional corridors rather than by the real circuit layout. This is a
significant simplification and it is revisited in Section 3.7.3, where the
solved results show what it costs.

The administrative geography comprises the 13 regions used as model nodes, 74
regional units used for the sub-regional siting rules, and 571 island geometries
used to apply the island-specific provisions of the draft siting framework. The
environmental layer consists of 443 Natura 2000 designations, covering both the
habitats and the birds directives.

The generation registers were introduced in Section 2.2.2; their extents are
recorded here for completeness. The international tracker contributes 5,666
solar, 1,469 wind and 25 hydro records. The national registry exports contribute
1,954 wind, 877 photovoltaic and 18 storage records. The operating-licence
register contributes 437 wind and 442 solar records, and the national project map
4,029 project records. Hydrogen is represented by 18 project records and 3
pipeline records. The contrast between the licence registers and the operating
register is the subject of Section 3.2.

A point of legal status must be stated clearly, and is repeated wherever these
rules are applied. The spatial restrictions implemented in this work derive from
the draft framework for the spatial planning of renewable energy that was issued
for public consultation in May 2026. That draft was the version available when
these inputs were assembled, and it is the version the code implements. The
framework has since been approved (Hellenic Republic, 2026), after the inputs
were frozen, and the enacted text may differ from the consultation draft in ways
not reflected here. Results that depend on these rules therefore describe what
the draft would have permitted, which is not the same as describing what the
framework now in force permits.

Two of the draft's provisions are additionally not implemented, because the
available sources either disagree on the value or state the requirement without
quantifying it: a municipal-level cap on wind coverage, and a general setback
distance from settlements. Omitting them makes the screening less restrictive
than even the draft would be in practice, so the candidate set reported in
Section 4.4 should be read as an upper bound on what would qualify. The two
effects compound in the same direction: the screening applies an older and
incompletely implemented rule set, so it is permissive on both counts.

### 2.2.4 Technology and Financial Cost Basis

Costs enter the model in two distinct roles, and conflating them is a common
source of error. In the planning problem, a technology carries an annualised
fixed cost and a variable operating cost, and the optimiser trades these against
one another. In the investment appraisal of Chapter 4, the same technology
carries a capital outlay and a stream of cash flows discounted over its life.
These two ledgers are kept separate throughout, and no figure is transferred
between them without restating its basis.

Annualised fixed costs are computed from an overnight capital cost by the capital
recovery factor, with a fixed operating and maintenance charge expressed as a
proportion of that capital cost:

$$ c^{\text{fix}} = \text{CAPEX} \cdot \text{CRF}(r, n) + \text{FOM}, \qquad
   \text{CRF}(r, n) = \frac{r (1 + r)^n}{(1 + r)^n - 1} $$

where $r$ is the real discount rate and $n$ the asset lifetime. A uniform real
discount rate of 7 % is applied to every technology. This is a simplification:
in practice the cost of capital differs by technology and by the risk profile of
the revenue arrangement, and modelling that variation would change the relative
attractiveness of capital-intensive and fuel-intensive options. The uniform rate
is adopted because no defensible technology-specific figures for the Greek market
were identified, and a single stated rate is preferable to a set of plausible but
unsourced ones. The consequence is quantified in Section 4.7.

Solar photovoltaic capacity is assigned an overnight capital cost of
594.86 EUR/kW over a 37.5-year life with a fixed operating charge of 2.2 % of
capital cost per year, giving an annualised 58,300 EUR/MW. Onshore wind is
assigned 1,438.88 EUR/kW over 28.5 years at 1.235 %, giving 135,600 EUR/MW, and
a variable cost of 1.9 EUR/MWh. Combined-cycle gas is assigned 1,142.11 EUR/kW
over 25 years at 3.339 %, giving 136,200 EUR/MW.

The marginal cost of gas generation deserves separate treatment, because it is
both the price-setting technology in most hours and the point at which the
dimensional conventions of Section 2.8 become material. In the electricity-only
model it is carried as a single composite figure of 108.8 EUR/MWh. That figure is
not an assumption but a derivation: a commodity price of 42.90 EUR/MWh on a
thermal basis, divided by a combined-cycle efficiency of 0.57 on a lower-heating-
value basis, gives a fuel component of 75.26 EUR/MWh of electricity; to this are
added a variable operating charge of 5.74 EUR/MWh and a carbon charge of
0.347 tCO2/MWh at 80 EUR/tCO2. Lignite is carried at 157 EUR/MWh on the same
basis, reflecting the older units that make up most of the Greek fleet. The
ordering of these two figures, rather than their absolute level, drives one of
the clearest results in Chapter 3.

Scenario B replaces the planning-basis gas figure with 144.0 EUR/MWh, derived
from the prevailing spot price for the same commodity. The choice between the two
is a genuine scenario decision rather than a settled question: the planning-basis
figure is the more stable reference for a representative-period baseline, while
the spot figure reflects conditions at the time of the analysis. Presenting both
is more honest than selecting one, and the comparison of Section 3.5 shows what
turns on it.

## 2.3 Demand Representation

Electricity demand enters the model as a time series for each region. No metered
regional series is published, so the regional profiles are constructed in two
steps: a national series is established, and that series is then distributed
across regions using socioeconomic proxies. Both steps are described below, and
the second carries a labelling obligation that is honoured throughout the thesis.

### 2.3.1 National Demand Forecasting

Two forecasting horizons are required. Annual planning needs a full year of
hourly demand consistent with the target year. Short-horizon operation needs a
next-day profile, which is used to demonstrate the forecast-to-dispatch chain in
Section 3.6.

Several model families were implemented so that the choice between them could be
made by comparison rather than by assertion: a seasonal naive benchmark, an
annual profile benchmark, a Fourier-term regression, a calendar-feature gradient
boosting model, a seasonal autoregressive integrated moving average model, a
random forest, and a long short-term memory network. Selection is by mean
absolute percentage error on held-out data. The transparent benchmarks are
retained rather than discarded, because a complex model that cannot beat a
seasonal naive forecast is not worth its opacity.

The next-day model is a gradient-boosted regression trained on 500 boosting
rounds with a maximum tree depth of 5, a learning rate of 0.05, row and column
subsampling fractions of 0.9, and a fixed random seed of 42 so that the result is
reproducible. Its features combine calendar terms, including cyclical encodings
of the hour and the day of week; autoregressive lags at one, two and three hours,
at one day and its neighbours, and at one week, which capture the daily and
weekly cycles that dominate the load shape; rolling means over the preceding day
and week; and a demand-weighted national weather signal. Prediction over the
24-hour horizon is recursive, each predicted hour feeding the lag features of the
next.

One limitation is stated here because it governs how the forecasting results may
be read. The models have been evaluated on held-out data but not by
rolling-origin backtesting, in which the model is repeatedly retrained and
evaluated as the origin advances through the series. Without that, no claim about
sustained forecast accuracy is defensible, and none is made: Section 3.6 reports
the forecast-to-dispatch chain as a demonstration that the pipeline functions
end to end, not as a measurement of predictive skill.

### 2.3.2 Regional Demand Allocation

National demand is distributed across regions by sector-weighted proxies. For
each sector $s$ and region $r$, a proxy share $q_{r,s}$ is formed from normalised
socioeconomic indicators: resident population, economic output, tourism activity,
agricultural land and industrial employment, each matched to the sector whose
consumption it best explains. These are combined into a monthly share using
sector weights $\beta_{s,m}$ that vary by season, since the sectoral composition
of demand differs between summer and winter:

$$ w_{r,m} = \frac{\sum_s \beta_{s,m}\, q_{r,s}}{\sum_{r'} \sum_s \beta_{s,m}\, q_{r',s}} $$

Regional demand in each hour is then the national value scaled by the share for
the month in which that hour falls:

$$ D_{r,t} = D_t \cdot w_{r,\,m(t)} $$

Because the shares are normalised to sum to unity across regions, national energy
is conserved exactly and by construction:

$$ \sum_r D_{r,t} = D_t \qquad \text{for every } t $$

This conservation property is asserted by the formulation and verified by test,
rather than being checked only on the particular series used here.

The result of this procedure is an *estimated regional demand allocation*. It is
described in those terms at every point in this thesis, and never as measured or
observed regional demand. The distinction is not pedantic: the allocation
reproduces the national total exactly by construction, so agreement with national
data provides no evidence whatever about its regional accuracy. Where a regional
result depends materially on the allocation, that dependence is stated.

## 2.4 Renewable Availability from Weather Data

Variable renewable output is represented by an availability factor, the fraction
of installed capacity that is technically available in a given hour. These are
derived from reanalysis weather data rather than from metered generation,
because metered output at the required spatial resolution is not published.

For photovoltaics, availability is taken as global horizontal irradiance relative
to standard test conditions, capped at unity:

$$ \bar p^{\,\text{solar}}_{t} = \min\!\left(1,\; \frac{G_t}{1000\ \text{W m}^{-2}}\right) $$

This neglects the temperature dependence of module efficiency and any soiling or
shading losses, and so is an optimistic representation of a real array. It is
adopted because the correction terms would require array-level information that
does not exist at national scale.

[[FIGURE:F-wind-power-curve|Turbine availability against wind speed under the correct power law and under the curve actually implemented. The two agree only at the cut-in and rated speeds and diverge across the whole operating range between them. Source: author's elaboration.]]

For wind, availability follows a generic onshore turbine power curve applied to
the wind speed at hub height. The turbine is characterised by three speeds: a
cut-in speed of 3.0 m/s below which no power is produced, a rated speed of
12.0 m/s above which output is capped, and a cut-out speed of 25.0 m/s above
which the machine is shut down. Between cut-in and rated, aerodynamic power rises
with the cube of wind speed, so the correct interpolation is cubic in the speed
itself:

$$ \bar p^{\,\text{wind}}_{t} =
   \frac{v_t^{3} - v_{\text{in}}^{3}}{v_{\text{r}}^{3} - v_{\text{in}}^{3}},
   \qquad v_{\text{in}} \le v_t < v_{\text{r}} $$

with the numerator offset equal to 27 and the denominator equal to 1701.

This equation is stated with care because an earlier implementation did not
satisfy it: it interpolated the *normalised speed fraction* cubically rather
than the speed itself, which is a materially different function and
understates output across the whole operating range. That defect, its
magnitude, its direction and its correction are the subject of Section 3.1.2,
which also documents a second and unrelated defect in the availability series
used by one family of runs. The corrected formulation above has since been
applied to the committed profiles and to every production and comparison run
reported in this thesis; Section 3.1.2 records the correction and the
re-solved results that depend on it.

Heating demand shape is derived from heating degree days, the accumulated
shortfall of daily mean temperature below a comfort threshold, which provides the
seasonal profile against which the heat demand of Section 2.8 is distributed.

## 2.5 Spatial Aggregation: Generator Clustering

The calibrated inventory of Section 2.2.2 contains far more individual assets
than a tractable planning model can carry as separate components. These are
therefore aggregated into clusters, in a way that preserves the spatial
distribution of capacity rather than collapsing it to regional totals.

Each asset is first assigned to a node by locating its coordinates within the
regional geometries, using a spatial index for efficiency, with assignment to the
nearest region as a fallback where a point falls marginally outside every
polygon. Assets are then grouped by node and carrier, and each group is
partitioned by capacity-weighted k-means clustering on the asset coordinates.
Weighting by capacity rather than treating assets equally ensures that cluster
centroids follow where the megawatts are, not merely where the records are.

[[FIGURE:F-fleet-map|The reconciled and calibrated generation fleet after clustering. Marker area is proportional to calibrated capacity and colour denotes carrier. Source: model output.]]

The number of clusters formed from a group is one per 15 assets, bounded above
at 6 clusters for any one node and carrier. The lower bound keeps a single asset
from being lost; the upper bound stops a crowded region from dominating the
component count. Applied to the 1,026 calibrated assets, this produces 107
clusters.

Each cluster is connected to its regional node by a line whose thermal rating is
inferred from the voltage class of the nearest real transmission segment, since
the network data record voltage class but not capacity. A 400 kV segment implies
a rating of 1,200 MVA, 150 kV implies 250 MVA, and 110 kV implies 150 MVA, with a
fallback of 25.0 MVA where no voltage tag is present. The rating is floored above
the cluster's own capacity, so that the connection never artificially constrains
the generation it exists to carry. This is an inference rather than a measurement,
and it is classified accordingly.

## 2.6 Temporal Aggregation: Representative Periods

Solving a planning problem over every hour of a year is expensive, particularly
when capacity is a decision variable and the problem must be solved repeatedly
across scenarios. The operating year is therefore represented by a reduced set of
periods, each carrying a weight that expresses how many hours of the real year it
stands for.

The governing requirement is that the weights reproduce the length of the year:

$$ \sum_t \omega_t = 8760 \ \text{h} $$

This is checked before every solve. It guarantees that annual energy, cost and
emission totals are correctly scaled, and it guarantees nothing else: in
particular it says nothing about whether the selected periods represent the
chronology, the persistence of weather, or the sequence of scarcity events that
determine storage value.

Several representations are implemented. Twelve representative days, one per
month, give 288 snapshots. Thirty-six days, stratified by wind conditions within
each month, give 864 snapshots. Four representative weeks give 672 snapshots and
preserve intra-week chronology at the cost of coverage. Linked representative
periods add explicit storage-state transitions between periods, and a
chronological expansion repeats representative patterns into a full-length row
structure, which supports seasonal storage accounting but does not create genuine
inter-period weather variation.

What the reduction costs can be measured directly against the series the days
are drawn from, without solving anything. [[FIGREF:F-duration-curves]] compares
the load duration curve of the observed year with that of the materialised
thirty-six-day set, each day repeated according to its weight. The two agree
closely through the body of the distribution, the reduced set's mean load
falling 1.32 % short of the observed year. The tails are where they part. The
reduction reaches a highest load of 8,441 MW against an observed peak of
9,141 MW, understating it by 7.66 %, because a set of representative days
selected to span typical conditions is unlikely to contain the single hour of
annual maximum demand. A capacity adequacy question is therefore not one this
temporal representation can answer, although an energy or cost question is.

The extreme lower tail of the observed curve should be read with the same care.
Twenty-five hours of the observed year are flagged by the quality procedure of
Section 2.2.1 as implausible but positive, and retained for review rather than
imputed; they are the reason the observed curve falls away at its right-hand
edge, and that gap is an artefact of the source data rather than an effect of
the reduction.

[[FIGURE:F-duration-curves|Load duration curves for the observed year and for the weighted representative-day set. The reduction tracks the body of the distribution and understates the peak. The observed curve's extreme lower tail contains hours flagged and retained for review, not repaired. Source: author's elaboration from the quality-controlled series and the representative-day selection.]]

Each artifact declares which of these classes it belongs to, so that a downstream
consumer cannot mistake an expanded representative year for an observed one. The
reference against which all of these should be validated is a genuine 8,760-hour
chronological solve. That reference has not been produced in this work. A
comparison between two reduced representations is reported in Section 3.1.4, and
it is presented as a sensitivity between representations rather than as a
validation against the full year, because that is what it is.

## 2.7 The Electricity Planning Model

The electricity model is a linear programme that selects capacity and dispatch to
minimise total annualised system cost. It is implemented with an open-source
energy system modelling framework and solved with an open-source interior-point
and simplex solver.

Each node must balance in every snapshot. Generation, storage discharge net of
charging, and net inflow over the incident lines equal the demand at that node:

$$ \sum_{g \in n} p_{g,t} \;+\; \sum_{s \in n} \left(p^{\text{dis}}_{s,t} - p^{\text{ch}}_{s,t}\right)
   \;+\; \sum_{l} K_{n,l}\, f_{l,t} \;=\; D_{n,t} $$

where $K_{n,l}$ is the incidence of line $l$ at node $n$. Flows are represented by
a linearised direct-current approximation and bounded by the line rating,
$|f_{l,t}| \le F_l$. Generation is bounded by the availability factor of
Section 2.4 applied to installed capacity, $0 \le p_{g,t} \le \bar p_{g,t} P_g$,
where $P_g$ is a decision variable for extendable technologies and a parameter
otherwise. Storage carries a state of charge that evolves with charge and
discharge efficiencies and is constrained to return to its starting value over
the modelled period, so that the solution cannot be subsidised by storage energy
created out of nothing.

The objective combines annualised capacity cost with weighted variable cost:

$$ \min \; \sum_g c^{\text{fix}}_g P_g \;+\; \sum_s c^{\text{fix}}_s P_s
   \;+\; \sum_t \omega_t \sum_g m_g\, p_{g,t} $$

with $c^{\text{fix}}$ from the capital recovery factor of Section 2.2.4, $m_g$ the
marginal cost, and $\omega_t$ the snapshot weight of Section 2.6. The dual
variable of the nodal balance constraint is the planning shadow price at that
node, and it is reported under that name throughout.

[[FIGREF:F-network-topology]] shows the network this formulation is solved on.
Thirteen regional nodes, one per administrative region, are joined by fourteen
corridors whose ratings follow the backbone of the real transmission system but
whose geometry is stylised: each corridor is a single equivalent link between
two regional nodes rather than a representation of the circuits that connect
them. The consequence is stated in Section 5.3 and bears repeating where the
network is introduced, since a topology with one link per regional pair cannot
express congestion within a region and can express congestion between regions
only in aggregate.

[[FIGURE:F-network-topology|The thirteen regional nodes and the fourteen corridors joining them, drawn at the region centroids over the administrative boundaries. Line width is proportional to the corridor rating. Source: model input.]]

A solve is accepted only when the solver reports an optimal status. A result that
is infeasible, unbounded, or terminated at a limit is treated as a failure and no
artifact is written. This matters more than it may appear: a pipeline that writes
output regardless of status will eventually publish a number that no optimisation
ever produced.

## 2.8 The Multi-Carrier Planning Model

The electricity model is extended to represent gas, hydrogen and heat alongside
electricity within a single optimisation. The extension is the methodological
centrepiece of this work, and its value lies less in the additional carriers than
in the conventions that keep them dimensionally consistent.

Four carriers are represented, on explicitly declared bases: electricity in MWh
of electrical energy across 13 nodes; heat in MWh thermal across 13 regional
nodes; natural gas in MWh on a higher heating value basis at a single national
node; and hydrogen in MWh on a lower heating value basis, also at a single
national node. Declaring the basis is not a formality. Natural gas is commonly
quoted on either a higher or a lower heating value basis, and the two differ by
roughly a tenth; hydrogen is conventionally quoted on a lower heating value
basis. Mixing them silently produces errors of the same order as the policy
effects the model is built to study.

Conversions between carriers are represented by links. A link draws $f$ from its
input carrier and delivers $q = \eta f$ to its output carrier. The convention
adopted here is that a link's capacity and its costs are expressed on the
**input** side:

$$ 0 \le f \le F^{\text{in}}, \qquad F^{\text{in}} = F^{\text{out}}/\eta,
   \qquad c^{\text{in}} = \eta\, c^{\text{out}} $$

Either convention is defensible; what is not defensible is using both without
saying so. Fixing the input side means that a capacity limit expressed in the
units of the fuel consumed is directly comparable with the supply available at
that bus.

The conversion efficiencies are as follows. Electrolysis delivers 0.7 MWh of
hydrogen on a lower heating value basis per MWh of electricity. A heat pump
delivers 3 MWh thermal per MWh of electricity. A gas boiler delivers 0.93 MWh
thermal per MWh of gas, and a hydrogen boiler 0.9 MWh thermal per MWh of
hydrogen. Gas-to-power conversion delivers 0.5182 MWh of electricity per MWh of
gas on a higher heating value basis.

[[FIGURE:F-multicarrier-topology|Carrier buses and the conversions between them, with the efficiency of each link and the input-side convention that governs its capacity and cost. Source: author's elaboration.]]

The gas-to-power chain illustrates the convention on real figures, and is set out
in Table 3.

[[TABLE:T-gas-stack]]

As the table shows, the commodity price of 42.90 EUR/MWh and the input-side link
cost of 17.662468 EUR/MWh, comprising a carbon charge of 14.688 and a variable
operating charge of 2.974468, together give a marginal cost of 116.8708 EUR/MWh
of electricity once divided by the conversion efficiency. Inverting the
convention on the operating component returns 5.7400 EUR/MWh of electricity,
which is the figure the cost data supplied, with no residual. The round trip
confirms that the convention is applied consistently rather than merely declared.

This also explains an apparent discrepancy with Section 2.2.4. The
electricity-only model carries gas at a composite 108.8 EUR/MWh, while the
multi-carrier model implies 116.8708 EUR/MWh for the same commodity price. The
difference is not a different price assumption: the composite figure divides the
same 42.90 EUR/MWh by an efficiency of 0.57 expressed on a lower heating value
basis, giving a fuel component of 75.26, and applies a carbon intensity of 0.347
tonnes per MWh of electricity. The multi-carrier formulation uses the higher
heating value basis throughout. The entire gap between the two figures is the
change of basis, which is a concrete demonstration that the convention is worth
several per cent on the price-setting technology.

Policy and trade options are represented explicitly rather than implicitly. The
hydrogen target may be expressed either as final demand or as domestic
production. Electrolysis may draw on grid electricity, or be subject to an hourly
matching requirement, or to an emissions-intensity threshold. Cross-border trade
may be bounded, constrained against arbitrage within the linear programme, or
restricted to one direction at a time through binary variables where exact
exclusivity is required. The configuration used for the solved case in Section
3.7 declares each of these choices.

Acceptance criteria are checked after every solve. Each bus must balance to
within a tolerance far below any physically meaningful quantity; the annual
relative imbalance must satisfy the same bound; storage must close cyclically;
and simultaneous import and export must not occur. These criteria are
supplemented by analytical tests on the conversions themselves, which are
reported in Section 3.1.1 together with an account of a defect that the balance
check itself was found to contain.

## 2.9 Candidate Site Screening

The components described so far represent the system as it exists. Investment
screening requires in addition a set of locations where new capacity might be
placed, together with an assessment of what may legally and physically be built
at each.

Candidate locations are generated on a regular grid of 0.1 degrees, which
corresponds to approximately 11.1 km in the north-south direction. For each cell,
a buildable polygon is computed as the cell geometry less the union of the
exclusions applicable to the technology under consideration. Areas are measured
in the national projected coordinate system, EPSG 2100, rather than in geographic
coordinates, because computing areas on a latitude-longitude grid introduces a
systematic error that varies with latitude.

A cell whose buildable fraction falls below 0.01 is treated as excluded outright.
A cell retaining more than that but less than 0.5 is retained and flagged for
review, on the basis that partial availability is a planning question rather than
a modelling one. Proximity to a world heritage site within 1.5 km triggers a
study requirement for solar development rather than an exclusion, reflecting the
draft framework's treatment of cultural designations as conditional.

Distances from each cell to the nearest substation and the nearest transmission
line are computed using a spatial index with a search radius of 0.3 degrees,
pruning the search without affecting the result for any cell whose nearest
feature lies within that radius. These distances feed the connection cost
component of the screening, and are reported directly in Section 4.4.

The procedure yields 718 candidate cells. Two limitations of the resulting set
should be recorded at the point of construction rather than left to the results
chapter. First, the resource quality attributed to each cell derives from a
coarse placeholder zoning layer rather than from the same reanalysis data used
for the operating fleet, so the resource score is a screening device and not a
resource assessment. Second, the two unimplemented provisions noted in Section
2.2.3 make the screening less restrictive than the draft framework would be.

## 2.10 Platform Implementation

The methods above are implemented across two repositories: a modelling
repository containing the optimisation models and their data pipelines, and a
platform repository containing a programmatic interface and a web application
through which the results are explored. The separation is deliberate and its
boundary is enforced by the architecture.

The interface does not import the modelling code. It invokes it as a separate
process and consumes the result files it produces. This keeps the heavy
scientific dependencies out of the service that must start quickly and stay
responsive, and it makes the boundary between the two explicit: anything crossing
it must be serialisable to a file, which in turn forces the result format to be
self-describing. The alternative, importing the model directly, would have been
simpler to write and considerably harder to reason about.

[[FIGURE:F-architecture|The layered architecture, from public sources through the data products and the modelling engine to the interface and the web application. Source: author's elaboration.]]

Model inputs are assembled into a scenario artifact before any solve begins. The
artifact carries the input files, a hash of each, a manifest recording what was
used, and a provenance record for every input stating its source, its original
units, the transformation applied, and its evidence class. Validation runs
against the artifact before the solver is invoked, so that an incomplete or
inconsistent scenario fails at construction rather than producing a plausible
but unfounded result. This mechanism is what allowed the production case of
Section 3.7 to be refused while its inputs were incomplete, and accepted once
they were not.

Derived products are checked for staleness by comparing modification times
against a watchlist of the inputs they depend on. The check is deliberately
conservative: it reports a product as stale when it cannot prove otherwise. A
false report of staleness costs a recomputation, whereas a false report of
freshness silently publishes an out-of-date number, and the two errors are not
equally acceptable.

Both repositories carry automated tests, whose extent is given in Table 4.

[[TABLE:T-test-coverage]]

The modelling repository runs 188 tests, all of which pass, and the platform
interface runs 191 tests, all of which pass. A failure was present in the
spatial site-selection module during the preparation of this thesis and is
reported here rather than silently corrected, since the alternative, describing
the suite as having always passed, would be false. The defect was specific: on
a two-site test case, the module reported an annual cost of 1944.4444 EUR where
a feasible alternative cost 1000.000001 EUR and satisfied every constraint, and
since adding an optional candidate to a minimisation cannot raise the true
optimum, the reported solution was not least-cost. The cause was not the
model's formulation but a solver interaction: HiGHS's presolve, triggered by
the module's own deliberately small (1e-6) binary tie-break cost, reduced the
problem to an empty one via variable fixing and returned "Optimal" solver
status, with zero branch-and-bound nodes, for a split that is not the
least-cost one, rather than actually searching the problem. Disabling presolve
for this module resolves it; the true least-cost solution is found and
confirmed against the diagnostic figures above.
