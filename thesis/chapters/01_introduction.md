<!--
Chapter 1 source. Same marker conventions as later chapters.

CITATIONS: entries written as (Author, Year) are VERIFIED in references.md.
Entries written as [VERIFY: ...] are NOT yet verified and must be confirmed or
removed before submission. Rule 0.3 forbids invented citations, so no reference
appears here in final form unless references.md records it as verified.

Run: python thesis/scripts/check_numbers.py
-->

# INTRODUCTION

## 1.1 Overall

Greece is in the middle of a structural change in how its electricity is
produced. A lignite fleet that supplied the bulk of generation for decades is
being retired; solar and wind capacity has grown rapidly; natural gas has become
the marginal technology in most hours; and national policy sets targets for
hydrogen and for the decarbonisation of heat that imply investment well beyond
anything yet built. Each of these changes creates investment decisions, and each
decision requires an answer to the same three questions: what to build, where to
build it, and whether the result will pay.

Those questions are harder to answer than they appear, for reasons that are
largely about data and modelling rather than about engineering. The information
needed is dispersed across registers maintained by different bodies for different
purposes, which overlap inconsistently and disagree about what exists. The
revenue a generator earns depends on the hours in which it produces and on what
every other generator is doing in those same hours, which cannot be established
without a model of the whole system. And the places where new capacity may
physically be built are constrained by environmental designations and spatial
planning rules whose boundaries are published separately from any energy dataset.

A further difficulty is that models capable of answering such questions are
typically opaque to the people who must act on them. An investor presented with a
capacity expansion result has no way to see which inputs were measured, which
were assumed, and which were placeholders retained to keep the model solvable.
This matters because the distinction frequently determines the answer.

This thesis addresses that combination of problems by building a workflow that
runs from public data through to project-level financial indicators, and by
insisting at every stage that the provenance of each input remains visible. Its
aim is not to produce a forecast of the Greek energy system, which a least-cost
planning model cannot provide, but to demonstrate that a transparent and
reproducible chain from public registers to investment screening is achievable,
and to report honestly what such a chain does and does not establish.

The remainder of this chapter introduces the modelling and analytical approaches
the work draws on. Section 1.2 covers energy system optimisation and Section 1.3
the aggregation techniques that make it tractable. Section 1.4 covers multi-carrier
systems. Section 1.5 covers demand forecasting, Section 1.6 renewable siting, and
Section 1.7 the appraisal of renewable investments. Section 1.8 surveys the
public Greek data landscape, and Section 1.9 describes the tools used.

## 1.2 Energy System Optimisation Models

Energy system optimisation models determine the capacity mix and operation that
minimise total system cost subject to physical and policy constraints. They are
distinguished from simulation models in that the configuration is an output
rather than an input.

Several open frameworks are in wide use. This work builds on PyPSA (Brown et al.,
2018), a toolbox for simulating and optimising power systems over multiple
periods, which represents conventional generation, variable renewables, storage,
coupling to other energy carriers, and mixed alternating and direct current
networks. PyPSA was selected for three reasons: it is open, so the formulation
can be inspected rather than trusted; it represents sector coupling natively,
which this work requires; and it has an established record of application at
national and continental scale. The continental application PyPSA-Eur (Hörsch et
al., 2018) provides the first open model dataset of the European power system at
transmission network level, and demonstrates the data-assembly problem this
thesis encounters at national scale.

Other frameworks occupy adjacent positions. (Loulou et al., 2005) represents long-horizon technology pathways with rich technology
detail but limited spatial resolution. (Howells et al., 2011)
emphasises accessibility and low barriers to entry. (Pfenninger & Pickering, 2018) emphasises explicit separation of model structure from
data. The selection among them is largely determined by whether spatial detail,
temporal detail or technology detail matters most for the question at hand. For
investment screening at regional resolution with sector coupling, PyPSA is the
natural fit.

The underlying problem is a capacity expansion formulation: investment variables
determine what is built, operational variables determine how it runs, and the
two are optimised jointly so that the capital cost of avoiding an operating cost
is weighed against that cost directly. The outcome is a least-cost configuration
and a set of dual variables on the balance constraints. Those duals are
frequently described as prices, and the description requires care: they are the
marginal cost of supplying an additional unit at a node in a least-cost plan,
which is not the same as the price that would emerge from a market with strategic
behaviour, unit commitment and reserve requirements. This thesis refers to them
throughout as planning shadow prices.

## 1.3 Spatial and Temporal Aggregation in Planning Models

A capacity expansion problem over every hour of a year, at every node of a real
network, is rarely tractable, and the aggregation required to make it solvable is
itself a modelling decision with consequences.

Temporal aggregation replaces the full year with a smaller set of periods, each
weighted to represent a number of real hours. Kotzur et al. (2018) show that the
conventional approach of modelling typical periods independently prevents energy
being carried between them, which makes seasonal storage impossible to represent
adequately in systems with high renewable shares, and propose a formulation that
links periods through explicit storage states. This limitation bears directly on
the present work, whose representations are discussed in Section 2.6 and whose
consequences are revisited in Section 3.1.4. Related treatments of how temporal
resolution affects long-term results (Poncelet et al., 2016) and surveys of the available aggregation methods (Hoffmann et al., 2020) reach compatible conclusions: reduced representations
systematically understate the value of flexibility and the cost of scarcity, and
the error grows with the renewable share.

Spatial aggregation raises a parallel question. A model node may represent a
country, a region, or a cluster of physically proximate assets. Coarser
representation loses the congestion that determines where generation is worth
building; finer representation multiplies the problem size and demands network
data that may not exist publicly. The approach adopted here, described in Section
2.5, clusters real assets within administrative regions so that the spatial
distribution of capacity is preserved even though the transmission topology
between regions remains stylised.

How much the network representation matters has been quantified directly.
Frysztacki et al. (2021) vary the number of nodes in a European model between 37
and 1,024 and find that the choice is not a matter of presentation: resolving
capacity placement finely reduces costs by up to a tenth, while a model with low
network resolution ignores congestion and underestimates system cost by close to
a quarter. The error is one-directional, which makes it particularly awkward,
since a coarse model does not merely add noise but systematically flatters the
system it represents.

That finding bears directly on the present work and is returned to in Section
5.3. The model developed here uses 13 regional nodes connected by stylised
corridors rather than the real circuit layout, which places it below the
entire range Frysztacki and colleagues examine, not merely at its coarse end.
Section 3.7.3 reports the consequence in the solved results: ten of the eleven
mainland nodes share an identical planning shadow price, with only one node
showing a material difference, so the model still carries only a minimal
congestion signal compared with the real transmission topology.

The investment implications of network representation are correspondingly large.
Tehranchi et al. (2026) model United States power system investment to 2050
across policy scenarios and find that transmission expansion lowers system cost
in every scenario examined, while also finding that renewable tax credits alone
cut emissions substantially even without new interregional lines. A model that
represents transmission coarsely will therefore tend to misstate the value of
building it, and one that cannot represent congestion cannot distinguish a policy
that works through the network from one that works through generation economics.

The common thread is that both forms of aggregation are defensible only when
their effect is bounded. A reduced representation should be validated against the
full problem it replaces. Section 3.1.4 reports what the present work was and was
not able to establish in that respect.

## 1.4 Multi-Carrier Systems and Sector Coupling

Electricity, gas, hydrogen and heat have historically been modelled separately,
with each carrier's model treating the others as exogenous. Sector coupling
removes that separation, representing conversions between carriers as decision
variables so that the model chooses, for instance, whether to meet heat demand
with a heat pump drawing electricity or a boiler drawing gas.

Brown et al. (2018) present a spatially and temporally resolved sector-coupled
model of Europe and find that the benefit of transmission reinforcement falls as
sectors become more tightly coupled, because coupling provides flexibility that
transmission would otherwise have had to supply. The finding illustrates why
carriers cannot sensibly be studied in isolation: a conclusion about one is
conditional on assumptions about the others.

Industry is where coupling becomes most consequential, because it is where
electrification, hydrogen and trade interact. Di Bella et al. (2026) extend
PyPSA-Eur with process-level representation of iron and steel, cement, methanol,
ammonia and high-value chemicals, and find that deep industrial decarbonisation
is technically feasible and led by electrification, but that competitiveness
depends on policy choices rather than on technology alone: importing
part-processed green intermediates and completing manufacture domestically
reduces cost substantially against producing everything at home. The result is
instructive for this thesis in a specific way. It is not a statement about
industry so much as a demonstration that the answer a coupled model gives is
conditional on the policy and trade assumptions supplied to it, which is why the
formulation in Section 2.8 represents trade and policy modes as explicit
configuration rather than burying them in the data.

Coupling is also being applied at the scale of individual industrial sites rather
than whole systems. Wafad et al. (2026) examine integrated wind–hydrogen
multicarrier microgrids for industrial decarbonisation and report that the
configuration becomes financially viable only under a supporting policy regime,
which shifts the project from unattractive to a positive internal rate of return.
That finding connects the two halves of the present work: a multicarrier
configuration is a technical design question and an investment question
simultaneously, and a model that answers only the first has not answered the one
an investor asks.

Coupling introduces an accounting problem that is easy to underestimate.
Different carriers are conventionally quoted on different bases — natural gas on
either a higher or a lower heating value, hydrogen customarily on a lower heating
value — and a conversion efficiency is meaningful only once the basis of both its
input and its output is declared. Mixing bases silently produces errors of the
same order as the effects being studied, a point this thesis quantifies in
Section 2.8. The same applies to emissions and to energy that passes through more
than one carrier, which must be counted exactly once.

Policy adds further structure. Rules governing when hydrogen produced from grid
electricity may be considered renewable (European Parliament and Council, 2018; European Commission, 2023) impose temporal matching and
additionality requirements that change the operating pattern of an electrolyser
and therefore its economics. A model intended to inform investment in such assets
must be able to represent those rules explicitly rather than assuming them away.

## 1.5 Electricity Demand Forecasting

Demand is an input to a planning model, and the method used to produce it
determines what the model can be asked.

Forecasting approaches span a wide range of complexity. Simple benchmarks exploit
the strong daily, weekly and seasonal periodicity of electricity demand. Classical
time series methods extend these with explicit autoregressive and moving-average
structure. Machine learning methods, of which gradient boosting (Chen & Guestrin,
2016) is now the most widely used for tabular problems, accommodate large feature
sets and non-linear interactions, at the cost of interpretability.

Hong and Fan (2016) survey the field and draw a distinction that matters here:
between point forecasts, which give a single expected trajectory, and
probabilistic forecasts, which characterise the distribution of outcomes. Their
review also emphasises the importance of evaluation protocol. A model evaluated
on a single held-out period may perform very differently under rolling-origin
evaluation, in which it is repeatedly retrained as the origin advances. This
thesis implements several model families and selects between them by error
comparison, but does not perform rolling-origin backtesting, and consequently
makes no claim about sustained forecast accuracy — a limitation stated at the
point of use in Section 2.3.1 and again in Section 5.3.

A second problem is spatial. Planning models require demand at each node, but
metered demand is typically published only nationally. Where regional series do
not exist, national demand must be allocated using proxies for regional activity,
which produces an estimate rather than an observation. The distinction is
preserved throughout this thesis.

A third consideration is that demand need not be treated as fixed at all. Nahid
and Roy (2026) extend a PyPSA model of the Bangladesh power system to represent
demand-side solutions explicitly, and find that pairing energy efficiency and
demand flexibility with supply expansion substantially reduces both the capacity
that must be built and the financing required, relative to meeting the same
service from supply alone. The result matters for how the present work should be
read. The model developed here treats demand as exogenous, so the capacity and
cost it reports are those of a supply-side solution, and a system able to move or
reduce load would need less of both. Flexible-demand components exist in the
model's implementation but are not used in any reported result, which is
recorded as a limitation in Section 5.3 and as future work in Section 5.4.

## 1.6 Renewable Siting and Spatial Constraints

Where renewable capacity may be built is determined by physical resource,
connection availability and regulation, and the third of these is frequently
binding before the other two.

### 1.6.1 The regulatory setting

In the European context, protected area designations established under the
Habitats Directive (Council of the European Union, 1992) and the Birds Directive
(European Parliament and Council, 2009) constrain development across substantial
land areas, with the strength of the constraint varying by designation and by
national implementation. The two directives together establish the Natura 2000
network, which is the single largest spatial constraint applied in this work.

Greek national law governs the licensing of renewable installations through Law
4685/2020 (Hellenic Republic, 2020), whose second chapter restructured the
licensing procedure for renewable energy sources. A substantially more
restrictive spatial planning regime for renewables was issued for public
consultation in May 2026, introducing elevation limits for wind development,
restrictions on small islands and constraints near cultural designations, and was
subsequently approved as a Special Framework for Spatial Planning of Renewable
Energy Sources (Hellenic Republic, 2026).

The timing of that approval requires a qualification that applies wherever these
rules appear in this thesis. The siting rules implemented in this work are those
of the consultation draft, which was the version available when the model inputs
were assembled and frozen. The framework was approved after that point. The
results reported in Chapters 3 and 4 therefore describe what the draft would have
permitted, and the enacted text may differ from it in ways this work does not
capture. This is a limitation rather than a technicality: a screening study whose
rules are one revision behind the instrument now in force cannot be read as a
statement about what is currently permissible, and Section 5.3 records it as
such.

### 1.6.2 Methods for assessing where capacity can be built

Two broad approaches to siting appear in the literature, and the distinction
between them determines what a siting study can be used for.

The first treats siting as a ranking problem. Multiple criteria of differing kinds
— resource quality, grid proximity, land cover, protection status, visual and
acoustic impact — are normalised, weighted and combined into a composite
suitability index, and locations are ordered by that index. The approach is
flexible and produces an immediately usable ranking, but the weights are
analyst-chosen and the resulting score conceals which criterion is actually
binding at any given location.

The second treats siting as an eligibility problem. Rather than scoring land, it
determines which land is excluded and reports what remains. Ryberg et al. (2018)
formalise this approach and apply it across Europe, evaluating thirty-six
constraints commonly used in the literature and showing that the eligible area
is highly sensitive to which constraints are applied and at what threshold — a
result that matters because those thresholds are frequently adopted without
justification. Their framework is the methodological ancestor of the procedure
used in Chapter 2 of this thesis.

This work follows the eligibility approach, and deliberately so. The exclusions
are carved out of the candidate geometry directly, so that what remains is the
land actually available, and the distances, overlaps and triggered conditions are
reported separately rather than collapsed into a single number. The reasoning is
that for an investor the identity of the binding constraint is more actionable
than an aggregate score: a site excluded by a protected area designation and a
site excluded by distance from the grid present entirely different problems, and
a composite index makes them indistinguishable. Section 4.4 accordingly reports
the screening outputs as geometry and distances rather than as a ranked list, and
Section 4.5 is explicit that the resulting economics do not discriminate between
sites.

McKenna et al. (2022) review the wider field of large-scale onshore wind
assessment and distinguish between geographical, technical, economic and feasible
potential — a hierarchy in which each level applies further constraints to the
one above. The distinction locates the present work precisely. The screening of
Chapter 4 establishes a geographical and partly technical potential: it
determines where development is physically and legally possible and what capacity
that land could carry. It does not establish feasible potential, which would
require the social acceptance, planning and grid connection factors that the same
review identifies as the least well represented in the literature and the most
often decisive in practice.

## 1.7 Investment Appraisal of Renewable Projects

The translation from a system model to an investment decision rests on
discounted cash flow analysis, from which net present value, internal rate of
return, levelised cost of energy and payback period are derived. The inputs are
capital cost, operating cost, output and the price that output earns, over an
assumed life and at an assumed discount rate.

The price term is where the analysis most often goes wrong, and Hirth (2013)
explains why. The value of variable renewable generation falls as its penetration
rises, because output is correlated across the fleet: when the wind blows, it
blows for everyone, and the resulting supply depresses the price in exactly the
hours when that technology is producing. A generator therefore earns a captured
price that diverges systematically from the system average, and the divergence
widens with deployment. An appraisal that multiplies annual energy by an average
price assumes this effect away. Section 4.2 computes the captured price directly
from the solved dispatch and finds a divergence of the magnitude Hirth's analysis
anticipates.

Output declines over an asset's life, and the rate differs by technology. Jordan
and Kurtz (2013) review nearly two thousand reported degradation rates for
photovoltaic systems and find a median of 0.5 % per year, the figure adopted in
this work. For wind, Staffell and Green (2014) analyse several hundred wind farms
and find load factors declining by roughly 0.4 percentage points per year from an
initial figure near 28 %, raising the levelised cost by around 9 % over the asset
life. Published wind estimates vary considerably by fleet and vintage (Hamilton et al., 2020), and this thesis adopts a
rate within the published range while noting the spread.

A related question is what an appraisal is for. Studies that stop at a levelised
cost answer whether a technology is cheap; studies that report an internal rate
of return answer whether a project is worth financing, which is a different
question and the one an investor asks. Wafad et al. (2026) take the latter route
for a multicarrier industrial configuration, reporting the policy conditions
under which the rate of return turns positive, and the present work follows the
same logic in Chapter 4 by carrying the model's own dispatch and prices through
to net present value and rate of return rather than stopping at a cost per unit.

The discount rate is the remaining major judgement. A single rate applied across
technologies implicitly assumes that capital-intensive and fuel-intensive
investments carry the same risk, which they do not. This thesis applies a uniform
rate for want of defensible technology-specific figures for the Greek market, and
quantifies the consequence of that choice in Section 4.7 rather than leaving it
implicit.

## 1.8 Public Energy Data for Greece

The data available for Greek energy modelling is substantial but fragmented, and
the fragmentation is itself a research problem rather than an inconvenience.

Demand is published by the transmission system operator and, in parallel, through
the European transparency platform. Generation capacity appears in several
places: national licensing registers record what has been permitted,
international trackers record utility-scale projects, a collaborative geographic
database records plant locations, and the national renewable operator publishes
operating capacity and output. These sources are constructed for different
purposes and do not agree. A licence register records intent; an operating
bulletin records reality; and the gap between them differs by technology, as
Section 3.2 quantifies.

Network geography is available principally through the collaborative database,
which records substations and line segments with voltage class but not thermal
capacity. Environmental designations are published by the European environment
agency, administrative geography by the same collaborative source, and regional
socioeconomic indicators by the European statistical office. Weather comes from
reanalysis archives rather than from measurement at turbine or array locations.
Technology costs come from international agency and consultancy publications
rather than from Greek project data.

The consequence is that any Greek energy model is an exercise in reconciliation
before it is an exercise in optimisation, and that the reconciliation decisions
materially affect the results. This thesis treats that reconciliation as a
reportable contribution rather than as preprocessing.

## 1.9 Modelling and Software Tools

The modelling is implemented in PyPSA (Brown et al., 2018), with the resulting
linear and mixed-integer problems solved by the HiGHS solver (Huangfu & Hall, 2018) through an optimisation interface layer (Hofmann, 2023).
Demand forecasting uses gradient-boosted trees (Chen & Guestrin, 2016) alongside
classical and benchmark alternatives. Geometric operations — the point-in-polygon
assignment of assets to regions, the carving of exclusions from candidate cells,
and the distance queries to network features — use standard computational
geometry libraries with spatial indexing, and areas are computed in the national
projected coordinate system rather than in geographic coordinates.

The surrounding platform is implemented as a programmatic interface and a web
application, described in Section 2.10. The reason for describing the software
stack in a thesis chapter at all is that reproducibility depends on it: the
scenario artifact mechanism, the input hashing and the staleness checks are
properties of the implementation rather than of the formulation, and they are
what allow the results in Chapters 3 and 4 to be traced back to the inputs that
produced them.
