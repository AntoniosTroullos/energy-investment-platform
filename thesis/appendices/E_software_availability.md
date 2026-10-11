<!--
Appendix E. Software availability and reproduction.
Every version here is recorded in references.csv and extracted into the ledger,
so the numbers are traceable like any other.
-->

# APPENDICES

## Appendix E: Software Availability and Reproduction

The work described in this thesis is implemented across two repositories. The
platform and thesis sources are publicly versioned; the modelling repository is
archived locally. The results reported in Chapters 3 and 4 were produced from
the states recorded below.

### Repository states

The platform repository, containing the programmatic interface, the data
pipelines and the web application, is archived at tag `thesis-v1`, commit
`baa2198`. That tag is the result-producing platform state; later commits add the
thesis sources and documentation without changing the archived scenario results.
The modelling repository, containing the optimisation models and
their input pipelines, is archived at tag `thesis-v1`, commit `455fa7f`; note
that the tag is annotated, so the tag object has a different identifier from the
commit, and the commit is the correct reference.

One exception applies. The modelling repository was reopened after the freeze,
with the author's explicit approval, for three pieces of work that postdate
`455fa7f`: the multi-carrier production run discussed in Section 3.7 together
with the scenario contract that assembles its inputs and the validator
correction described in Section 3.1.1 (commit `d7be6cc`); the spatial
site-selection solver fix described in Section 2.10 (commit `fb53a86`); and the
wind availability correction described in Section 3.1.2, applied to the
committed series and to the Section 3.7 run (commit `b1bbbfd`). Work on Chapter 2's Section 2.8 and Section 2.10, and on Chapter 3's Section
3.1.2 and Section 3.7, should therefore be referred to commit `b1bbbfd`, the
branch tip, and everything else to `455fa7f`.

### Code availability

The platform and thesis repository is publicly available at
`https://github.com/AntoniosTroullos/energy-investment-platform`. The modelling
repository is not hosted remotely; its state is archived locally at the commits
cited above and is available to the examination committee on request. Therefore
the document build, platform code and frozen evidence are publicly inspectable,
whereas reproducing the optimisation runs themselves additionally requires the
archived modelling repository and its input datasets.

### Execution environment

Both interpreters are Python 3.14.3. The modelling environment, which solves the
optimisation problems and generates the figures, carries PyPSA 1.1.2, linopy
0.6.6 and highspy 1.14.0 as its optimisation stack; pandas 3.0.2, NumPy 2.4.4,
SciPy 1.17.1 and xarray 2026.2.0 for numerical work; Shapely 2.1.2, pyproj 3.7.2
and GeoPandas 1.1.3 for geometry; netCDF4 1.7.3 for network serialisation;
scikit-learn 1.9.0, statsmodels 0.14.6 and XGBoost 3.3.0 for the forecasting
models; and Matplotlib 3.10.8 for the figures.

The interface environment carries FastAPI 0.115.0, Uvicorn 0.30.6 and Pydantic
2.13.5, together with Shapely 2.1.2 and pyproj 3.7.2 for the geometric
operations performed at request time. The web application is built on Next.js
16.2.2 and React 19.2.4, with MapLibre GL JS 5.21.1 for cartography and Recharts
3.10.1 for the result charts.

### Verification

The automated test suites may be executed from the root of each repository. The
outcome at the time of writing is reported in Section 2.10 and in Table 4: the
modelling repository runs 188 tests of which all pass, and the interface runs 191
tests of which all pass. A failure present during preparation of this thesis, and
its fix, are described in Section 2.10; it affected no result reported in this
thesis.

### Thesis build

The thesis is generated from versioned sources. Numerical claims are extracted
from frozen result files into a ledger, figures and tables derive from the same
evidence, and an automated guard rejects any untraced number in the text. These
scripts produce the document; model corrections and production runs remain
versioned in the modelling repository. Equations are emitted as editable native
Office Math objects.
