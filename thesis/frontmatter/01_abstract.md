<!--
English abstract. Template: one page, a SINGLE paragraph of about 370 words,
heavily quantitative, no keywords, no citations, no equations or floats.
Run: python thesis/scripts/check_numbers.py
-->

# ABSTRACT

This thesis develops and evaluates a reproducible workflow connecting public
Greek energy data to a solvable energy system model and onward to project-level
investment appraisal. Generation records from several incomplete public
registers are merged, deduplicated and calibrated against published operating
capacities, yielding 1,026 assets aggregated into 107 spatial clusters across
the country's 13 regions; the calibration shows that merged registers understate
operating solar capacity by a factor of 2.458 while overstating wind by 0.8856
and biomass by 0.6798, so no single correction could have been applied. National
demand is assembled from 39,359 quality-controlled hourly observations and
allocated regionally by sector-weighted socioeconomic proxies that conserve
national energy exactly. A least-cost planning model is solved for two
scenarios: a baseline, and an alternative in which the lignite fleet is retired
and gas is repriced from a planning basis of 108.8 EUR/MWh to a spot figure of
144.0 EUR/MWh. The lignite fleet generates 0.000 TWh in both, because its
marginal cost of 157 EUR/MWh places it outside the merit order, so the
alternative scenario changes generation in no carrier while raising the
weighted-mean planning shadow price by 31.65 per cent, from 71.41 to
94.01 EUR/MWh, and system cost by 30.14 per cent; the lignite transition is thus
already complete on cost grounds, and the system transmits a fuel price shock
almost undamped. Computing revenue as captured rather than average price shows
solar clusters earning 27.31 EUR/MWh against a system mean of 71.41, the
cannibalisation effect an average-price appraisal would have concealed, while
wind, hydro and biomass earn above the system mean at 78.44, 99.46 and
108.17 EUR/MWh respectively, a scarcity premium an average-price appraisal
would equally have concealed. A screening procedure carving protected areas
and draft spatial planning rules out of a national grid yields 718 candidate
cells. Capacity arithmetic at the utilisation of 45.46 per cent implied by
national policy shows the operational electrolyser base producing 0.208 TWh
annually against a 2030 target of 1.2 TWh. Benchmarking modelled wind
availability against published output identified an incorrect power-curve
formulation, a stale derived file and a validation check that could never pass.
After correction, calibration and re-solution, wind availability equals the
23.834 per cent benchmark; dispatch is 18.59 per cent after 21.99 per cent
curtailment. The resulting wind appraisal is reportable and strongly
scenario-dependent: 11 of 29 operating clusters have positive net present value
in the baseline and 13 in the high-gas-price case. The work therefore shows that
provenance and external benchmarking are not registry functions but integral
parts of defensible energy-system engineering.
