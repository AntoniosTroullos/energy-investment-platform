# Working bibliography

Master plan rule 0.3: no invented citations. Every entry must be verified before
it reaches the reference list. This file records verification status so that an
unverified entry cannot reach the final document unnoticed.

Status values:
- **VERIFIED** — author, year, venue and DOI confirmed against a search or the
  publisher record on the date shown.
- **PARTIAL** — identifier confirmed, one field still to confirm (noted).
- **TO VERIFY** — cited in the draft behind a `[VERIFY: ...]` marker, not yet
  confirmed. These must all be resolved or removed before submission.

Citation style is APA 7, author–date, as the template uses.

---

## VERIFIED (2026-10-01)

**Brown, T., Hörsch, J., & Schlachtberger, D. (2018).** PyPSA: Python for Power
System Analysis. *Journal of Open Research Software*, 6(1), 4.
https://doi.org/10.5334/jors.188

**Brown, T., Schlachtberger, D., Kies, A., Schramm, S., & Greiner, M. (2018).**
Synergies of sector coupling and transmission reinforcement in a cost-optimised,
highly renewable European energy system. *Energy*, 160, 720–739.
https://doi.org/10.1016/j.energy.2018.06.222

**Chen, T., & Guestrin, C. (2016).** XGBoost: A scalable tree boosting system. In
*Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge
Discovery and Data Mining* (pp. 785–794).
https://doi.org/10.1145/2939672.2939785
*(page range to confirm against the ACM record)*

**Hirth, L. (2013).** The market value of variable renewables: The effect of
solar wind power variability on their relative price. *Energy Economics*, 38,
218–236. https://doi.org/10.1016/j.eneco.2013.02.004

**Hong, T., & Fan, S. (2016).** Probabilistic electric load forecasting: A
tutorial review. *International Journal of Forecasting*, 32(3), 914–938.
https://doi.org/10.1016/j.ijforecast.2015.11.011

**Hörsch, J., Hofmann, F., Schlachtberger, D., & Brown, T. (2018).** PyPSA-Eur:
An open optimisation model of the European transmission system. *Energy Strategy
Reviews*, 22, 207–215. https://doi.org/10.1016/j.esr.2018.07.001

**Kotzur, L., Markewitz, P., Robinius, M., & Stolten, D. (2018).** Time series
aggregation for energy system design: Modeling seasonal storage. *Applied
Energy*, 213, 123–135. https://doi.org/10.1016/j.apenergy.2018.01.023

## Supervisor-requested additions (2026-10-01)

Four papers the supervisor asked to see in the literature review. Verification
was attempted for each; the status below is exactly what could be confirmed.

**Di Bella, A., Seibold, T., Brown, T., & Tavoni, M. (2026).** Decarbonization
without deindustrialization in future pathways for European industry. *Cell
Reports Sustainability*. https://doi.org/10.1016/j.crsus.2026.100837
**VERIFIED** — title, authors, journal and DOI all confirmed, and the content
matches: an extended PyPSA-Eur model with process-level representation of iron
and steel, cement, methanol, ammonia and high-value chemicals, comparing domestic
low-carbon production against imports. Earlier circulated as arXiv:2510.08199
under the title *Pursuing decarbonization and competitiveness: a narrow corridor
for European green industrial transformation*; the journal version was retitled.
Volume and article number still to add.

**Wafad, A. A., Sher, F., Khzouz, M., & Ioannou, A. (2026).** Integrated wind
hydrogen multicarrier microgrids for industrial decarbonisation and net zero
transition. *Energy for Sustainable Development*, 95, 102133.
https://doi.org/10.1016/j.esd.2026.102133
**PARTIAL** — the DOI constructed from the volume and article number resolves
(302) to Elsevier PII S0973082626002103 in *Energy for Sustainable Development*,
so the article exists at that identifier. The publisher page could not be read,
so the title and author list have not been confirmed independently of the
supervisor's own list. **Confirm against the publisher record.**

**Nahid, F. A., & Roy, J. (2026).** Integrating demand-side solutions for
affordable accelerated decarbonization: a case of Bangladesh power supply system.
*Energy and Climate Change*, 7, 100275.
https://doi.org/10.1016/j.egycc.2026.100275
**PARTIAL** — the DOI resolves (302) to Elsevier PII S2666278726000413 in *Energy
and Climate Change*, so the article exists. Title and authors not independently
confirmed; related PyPSA-based Bangladesh capacity-expansion work by the same
lead author was found. **Confirm against the publisher record.**

**Kamran, T., Barnes, T., F., M., & Azevedo, I. M. L. (2026).** Costs and
benefits of transmission investments in the United States under different policy
scenarios. *Environmental Research Letters*.
**TO VERIFY** — could not be located. Searches returned the group's related
PyPSA-USA work and conference presentations on exactly this subject, but not this
article, and no DOI was found. Two author names were abbreviated in the source
the supervisor sent ("Kamran T.", "Martha F."), so the full names are also
unconfirmed. **The DOI and the complete author list are needed before this can be
cited.**

## PARTIAL

**Jordan, D. C., & Kurtz, S. R. (2013).** Photovoltaic degradation rates — An
analytical review. *Progress in Photovoltaics: Research and Applications*, 21(1).
https://doi.org/10.1002/pip.1182
*Verified: authors, year, journal, volume, issue, DOI, and the median degradation
rate of 0.5 %/year that this thesis adopts. Page range still to confirm.*

**Staffell, I., & Green, R. (2014).** How does wind farm performance decline with
age? *Renewable Energy*, 66, 775–786.
https://doi.org/10.1016/j.renene.2013.10.041
*Verified: authors, year, journal, pages, DOI. Volume ambiguous — one source
gives 65, the repository identifier gives 66. Confirm against the publisher
record before submission.*

## TO VERIFY

Cited in the Chapter 1 draft behind `[VERIFY: ...]` markers. Each must be
confirmed or removed.

- Huangfu, Q., & Hall, J. A. J. — HiGHS parallel dual simplex
- Poncelet, K., et al. — impact of temporal resolution on long-term energy system
  models, IEEE Transactions on Power Systems
- Hoffmann, M., et al. — review of time series aggregation methods, *Energies*
- Loulou, R., et al. — TIMES model generator documentation
- Howells, M., et al. — OSeMOSYS
- Pfenninger, S., & Pickering, B. — Calliope
- Hofmann, F., et al. — linopy
- Nahmmacher, P., et al. — representative days for capacity expansion
- Greek Law 4685/2020
- Council Directive 92/43/EEC (Habitats)
- Directive 2009/147/EC (Birds)
- Directive (EU) 2018/2001 as amended, and Delegated Regulation (EU) 2023/1184
  on renewable fuels of non-biological origin
- Greece National Energy and Climate Plan, 2024 final update
- Draft Special Framework for Spatial Planning of Renewable Energy Sources
  (May 2026, public consultation)
- IRENA, *Renewable Power Generation Costs in 2024*
- Danish Energy Agency, *Technology Data for Generation of Electricity and
  District Heating*
- ENTSO-E & ENTSOG, *Ten-Year Network Development Plan 2024*
- IPCC (2006), *Guidelines for National Greenhouse Gas Inventories*, Vol. 2 Ch. 2
- Lazard, *Levelized Cost of Energy+*
- Lawrence Berkeley National Laboratory / *Joule* (2023) — wind fleet performance
  decline

## Data sources cited through their own provenance records

These are recorded in the scenario manifests and input ledgers rather than as
literature, and are cited in the text by organisation and year: the national
transmission system operator's load series, the European transparency platform,
the national renewable energy operator's annual bulletin, the national gas system
operator's statistics, the national licensing registers, the international
generation trackers, the collaborative geographic database, the European
environment agency's protected site designations, the European statistical
office's regional indicators, and the reanalysis weather archive.
