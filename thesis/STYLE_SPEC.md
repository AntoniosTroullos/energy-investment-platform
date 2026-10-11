# Style specification — measured from the template thesis

Source: `C:\Antonis\AUTH DOCS\Διπλωματική\Energy Markets Optimiser\Varsami Diploma Example.pdf`
(Varsami, *Design, Techno-economic and Environmental Analysis of a Yellow Pea
Biorefinery*, AUTH, July 2026). 128 PDF pages.

Everything below marked **[measured]** was extracted from the PDF itself with
PyMuPDF on 2026-09-30, not read off a description. This file is the contract that
`scripts/build_docx.py` implements.

## Page

| Property | Value | Evidence |
|---|---|---|
| Paper | A4, 595.32 × 841.92 pt = 21.0 × 29.7 cm, portrait | **[measured]** |
| Left margin | 3.17 cm (Word 1.25" preset) | **[measured]** text block starts at 3.18 cm |
| Right margin | 3.17 cm | **[measured]** text block ends 3.07 cm from edge (justified text falls just short) |
| Top / bottom margin | 2.54 cm | Word 1" preset; footer sits at 1.25 cm from the foot |
| Landscape pages | Allowed for wide tables and diagrams, page number rotated | Template p. 39 |
| Headers | None | — |
| Page number | Bottom right, Calibri 11 pt | **[measured]** Calibri 11.0 pt is the only Calibri in the body |
| Numbering | Roman i… from the ABSTRACT; arabic 1… restarting at the INTRODUCTION; title page unnumbered | **[measured]** PDF p. 12 = arabic p. 1 |

## Type

All Times New Roman, **regular weight** — `TimesNewRomanPSMT`. Bold
(`TimesNewRomanPS-BoldMT`) appears only in table header rows. **[measured]**

| Element | Size | Style | Evidence |
|---|---|---|---|
| Body text | 12 pt | Justified, 1.5 line spacing, 6–8 pt space after, **no first-line indent** | **[measured]** 69,419 chars at 12.0 pt |
| Chapter title | 20 pt | ALL CAPS, regular, left-aligned, unnumbered, new page, `&` not `and` | **[measured]** e.g. `FLOWSHEET SYNTHESIS & ANALYSIS` |
| Level-2 heading | 16 pt | Title Case, regular, left, numbered `1.1` | **[measured]** |
| Level-3 heading | 14 pt | Title Case, regular, left, numbered `1.1.1` | **[measured]** |
| Level-4 heading | — | Does not exist; unnumbered 12 pt run-in sub-headings used instead | **[measured]** |
| Table caption | 9 pt | *Italic*, left-aligned, **above** the table, `Table N: Title` | **[measured]** `TimesNewRomanPS-ItalicMT` 9.0 pt |
| Figure caption | 9 pt | *Italic*, centred, **below** the figure, `Figure N: Title (Source, year)` | **[measured]** |
| Equations | 12 pt | Cambria Math, centred, number right-aligned as `(1)` | **[measured]** `CambriaMath` 12.0 pt |
| Italics in body | 12 pt | Latin names only | **[measured]** |

A chapter goes **straight into its first numbered section** with no introductory
paragraph before it. **[measured]** — `INTRODUCTION` → `1.1 Overall`.

## Numbering

- Tables: continuous across the whole thesis, `Table 1` … `Table N`. Appendices use
  `Table A.1`, `Table B.2` (no colon). **[measured]**
- Figures: continuous, `Figure 1` … `Figure N`.
- Equations: continuous, `(1)` … `(N)`, no chapter prefix. Referred to in prose as
  "Equation 6", not bare "(6)".
- Chapter titles carry no visible number, but their sections do (`1.1`, `2.3.1`), and
  the numbering continues into the back matter — REFERENCES is chapter 6 and
  APPENDICES chapter 7, whose sections read `7.1 Appendix A`. **[measured]**

Two errors in the template are **corrected, not imitated**: the heading `APENDIXES`
becomes `APPENDICES`, and the irregular `7.1 Appendix A` numbering becomes plain
`Appendix A`.

## Tables

Full grid on all borders; bold header row; cells centred; 12 pt body text, 11 pt when
the table is large. Units go in the header in parentheses — `Capacity (MW)`,
`Captured price (€/MWh)`. Literature values carry the citation inside the cell.
Section sub-rows in bold caps are used to split a table
(`SCENARIO A` / `SCENARIO B`).

Every table is introduced in the text **before** it appears ("…as presented in
Table 25.") and interpreted in the paragraph **after** it ("As shown in the table,
…").

## Figures

Charts in the template are Excel-style in Calibri. This thesis uses matplotlib with a
single consistent carrier colour map (master plan §9):

| Carrier | Hex |
|---|---|
| solar | `#F2C300` |
| wind | `#3B8FD9` |
| hydro | `#1F5FA8` |
| gas | `#D9534F` |
| lignite | `#6B4E3D` |
| biomass | `#5E9E4B` |
| battery | `#8E6CC0` |
| pumped_hydro | `#2BA3A3` |
| hydrogen | `#9AD0EC` |
| heat | `#E8883A` |

Every figure needs labelled axes with units, readable ticks and legend, and a
provenance line in the caption: an external source as `(Author, year)`, own output as
`Source: model output` or `Source: author's elaboration`.

## Citations

APA 7 author–date. Parenthetical `(Poore & Nemecek, 2018)`, multiple sources
separated by `;`, `et al.` for three or more authors, `&` inside parentheses.
Narrative form `Geerts et al. (2018) state that…`.

Density in the template is roughly 130 citation groups in ~20,000 words — nearly every
background sentence in the introduction is cited, and every design assumption in the
core chapter is justified with a citation. Match this.

Reference list: alphabetical by first-author surname, not numbered, hanging indent,
12 pt, single-spaced entries, DOIs as full `https://doi.org/...` URLs. Web sources as
`Organisation. (Year). Title. Site.com. URL`.

## Voice

Impersonal third person, mostly passive: "the model was built", "the economic analysis
is conducted", "In this thesis, …". No "I" or "we" outside the acknowledgements.
Present tense for the model and its results ("Table 16 presents…"), past for what was
done ("the network was solved using…").

Paragraphs of 5–10 lines, one idea each. Connectives used in the template: "More
specifically,", "Moreover,", "Therefore,", "In contrast,", "Regarding …,", "In
conclusion,", "Finally,". Acronyms defined at first use, then used alone.

Numbers: comma thousands separator, dot decimals (`5,016 MW`, `83.47 €/MWh`). Percent
changes always quantified ("a 59 % decrease"). Greek abstract uses Greek convention
(`125.000`, `91,6`).

**Justification pattern for every design choice** — state the choice, give the
physical or economic reason, back it with a citation, give the parameter value used.
This is the single most characteristic habit of the template and it applies to every
modelling decision in Chapter 2.

Model entities are named with their real identifiers, the way the template names
`P-11/R-101` and stream `S-110`: name buses, carriers, clusters and scenario
directories exactly as the code does.
