<!--
Chapter 5. Template: about three pages, continuous prose, no bullet lists, no
new evidence. It restates the aim and method, synthesises the strongest
validated results with their headline numbers, states the limitations briefly,
and proposes concrete future work.
Run: python thesis/scripts/check_numbers.py
-->

# CONCLUSIONS & FUTURE RESEARCH

## 5.1 Summary of Findings

This study developed and evaluated a reproducible workflow connecting public
Greek energy data to a solvable energy system model and onward to project-level
investment appraisal, spanning the reconciliation of generation registers, the
construction of national and regional demand, spatial and temporal aggregation,
a least-cost planning formulation and its multi-carrier extension, a siting
procedure grounded in real regulatory geography, and a discounted cash-flow
appraisal of existing assets and prospective sites.

Four findings stand independently of the limitations discussed below. The
reconciliation of public registers showed that licensed and operating capacity
diverge, and diverge in opposite directions by technology: merged registers
understate operating solar capacity by a factor of 2.458 while overstating wind
by 0.8856 and biomass by 0.6798, so no single correction could serve. The cost
ordering between lignite and gas proved sufficient on its own to exclude lignite
from dispatch, which produced 0.000 TWh at a marginal cost of 157 EUR/MWh against
108.8 EUR/MWh for gas, with no emissions constraint or retirement policy
required. Retiring that fleet and repricing gas therefore changed generation in
no carrier while raising the weighted-mean planning shadow price by 31.65 per
cent and system cost by 30.14 per cent: within this model's economics the
lignite transition is already complete on cost grounds, so the policy is
fiscally consequential but physically neutral, and a system whose price is set by
gas transmits a fuel-price shock almost undamped. Finally, computing revenue as
captured rather than average price showed solar clusters earning 27.31 EUR/MWh
against a system mean of 71.41 — the cannibalisation effect an average-price
appraisal would have concealed — while wind, hydro and biomass earned above
the mean at 78.44, 99.46 and 108.17 EUR/MWh, a scarcity premium the same
appraisal would equally have concealed. Re-solving against the corrected wind series made the
technology's economics reportable: 11 of 29 operating wind clusters have
positive NPV in Scenario A and 13 in Scenario B.

Separately, capacity arithmetic showed the national hydrogen trajectory to be
unreachable from the existing fleet. At the utilisation of 45.46 per cent implied
by the plan's own production target and capacity objective, the operational
project base yields 0.208 TWh per year against a 2030 target of 1.2 TWh, and even
complete build-out of every licensed project reaches 1.081 TWh.

## 5.2 Methodological Contribution

The principal contribution is methodological rather than numerical: a workflow in
which every input carries a provenance record and an evidence class, every
derived product is checked against its inputs, and every scenario is validated
before it is solved. That discipline is not administrative. It is what refused a
production run while its inputs were incomplete, what made the licensed-versus-
built divergence visible rather than silently absorbed, and what made three
separate defects findable — two in modelled wind availability and one in a
validation check that could never have passed. Correcting the power curve,
regenerating the stale derivative and re-solving the affected cases converted
that diagnosis into a verified result: wind availability is 23.834 per cent,
dispatch is 18.59 per cent and 21.99 per cent of available energy is curtailed.
Supporting contributions are the
multi-carrier formulation with explicitly declared carrier bases, where the
entire difference between 108.8 and 116.8708 EUR/MWh for the same commodity price
proved to be the change of heating-value basis; the reconciled generation
inventory itself; and the connection of a planning model to project appraisal
without conflating the two ledgers.

## 5.3 Limitations

The limitations are substantial and bear on much of the quantitative content.
The wind calibration resolves the identified input defect but does not turn a
reduced planning model into a validated market simulation. The thirteen-node network with
stylised corridors carries no congestion signal, and
comparable work finds that such coarse representations understate system cost by
close to a quarter. Regional demand is an estimated allocation rather than a
metered series; the temporal representation has not been validated against a full
chronological year; the formulation is a planning model and not a market
simulation; and the candidate screening ranks regions and technologies rather
than sites, since 96.4 per cent of solar cells and 100.0 per cent of wind cells
reach the assumed capacity cap. The portfolio appraisal is likewise static:
installing the screened capacity would alter dispatch and the prices used to
value it.
The siting rules applied are those of the consultation draft rather than the
framework subsequently approved, so the screening describes what that draft would
have permitted rather than what the instrument now in force permits.
All tests in the modelling repository pass, including a spatial site-selection
MILP whose non-optimality, caused by a solver presolve interaction with the
model's own tie-break cost rather than by the model's formulation, was found
and fixed in the course of producing this thesis.

## 5.4 Future Research

The most valuable late-stage correction proved also to be the smallest: applying
the already implemented and tested wind power curve and calibration, regenerating
the derived series, and re-solving the affected production cases. Scenarios A
and B, the coupled production run, and the temporal-aggregation comparison of
Section 3.1.4 all now use the corrected, calibrated input; no reported run
retains the qualification. Beyond that, a genuine 8,760-hour reference solve would allow
the reduced
temporal representations to be validated rather than merely compared with one
another; rebuilding the multi-carrier run on the reconciled rather than the
stylised fleet would make its capacity outputs statements about the real system;
the real transmission topology would supply the congestion signal the present
network lacks; and site-specific availability with technology-specific regional
prices would give the candidate screening the discrimination between sites it
does not currently possess. Enabling the cross-border trade and electrolyser
investment that were disabled in the production run, adding rolling-origin
forecast backtesting, and integrating storage arbitrage revenue would each extend
the work along a path it is already formulated to follow.

Each of these is a bounded change to a workflow that already runs end to end
rather than a redesign. That is itself a result: the architecture proved able to
surface its own defects, and the work remaining is largely the work of acting on
what it surfaced.
