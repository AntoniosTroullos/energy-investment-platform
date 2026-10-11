"""Build the thesis .docx from the chapter sources and table specs.

Implements the measured template specification in STYLE_SPEC.md: A4, Times New
Roman 12 pt justified at 1.5 spacing with no first-line indent, chapter titles
20 pt ALL CAPS unnumbered on a new page, sections 16 pt and subsections 14 pt all
in regular weight, table captions above in 9 pt italic, figure captions below,
continuous numbering of tables, figures and equations across the whole document,
and page numbers bottom right.

Markdown subset consumed:
    # TITLE                 chapter title
    ## 2.1 Title            level 2
    ### 2.1.1 Title         level 3
    [[TABLE:T-id]]          table spec from thesis/tables/
    [[FIGURE:id|caption]]   figure placeholder
    $$ ... $$               native Word display equation (LaTeX source)
    plain paragraphs

Run with the document interpreter:
    thesis/.venv-docx/Scripts/python.exe thesis/scripts/build_docx.py

Equations are converted from LaTeX to MathML and then to native Office Math
(OMML). They therefore remain editable in Word and are not embedded as images.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path

from latex2mathml.converter import convert as latex_to_mathml
from lxml import etree
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

THESIS = Path(__file__).resolve().parents[1]
CHAPTERS = THESIS / "chapters"
TABLES = THESIS / "tables"
FIGURES = THESIS / "figures"
BUILD = THESIS / "build"

BODY_FONT = "Times New Roman"
MATH_FONT = "Cambria Math"
BODY_PT = 12
CAPTION_PT = 9
CHAPTER_PT = 20
L2_PT = 16
L3_PT = 14

TABLE_RE = re.compile(r"^\[\[TABLE:([^\]]+)\]\]$")
FIGURE_RE = re.compile(r"^\[\[FIGURE:([^|\]]+)\|([^\]]*)\]\]$")
# [[FIGREF:id]] is an inline cross-reference. It resolves to the number
# the figure is actually assigned, so prose and figures cannot drift and
# no figure number is typed by hand anywhere in the chapters.
FIGREF_RE = re.compile(r"\[\[FIGREF:([^\]]+)\]\]")
INLINE_MATH_RE = re.compile(r"\$([^$]+)\$")
FIGURE_NUMBERS: dict[str, int] = {}


def number_figures(paths: list[Path]) -> None:
    """Assign figure numbers in the order the documents will render."""
    for path in paths:
        body = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"),
                      flags=re.S)
        for line in body.splitlines():
            m = FIGURE_RE.match(line.strip())
            if m:
                FIGURE_NUMBERS[m.group(1)] = len(FIGURE_NUMBERS) + 1

counters = {"table": 0, "figure": 0, "equation": 0}
table_numbers: dict[str, int] = {}


def _mml2omml_stylesheet() -> Path:
    """Locate Microsoft's MathML-to-Office-Math transform.

    Word installs this stylesheet with Office. ``MML2OMML_XSL`` permits an
    explicit path on machines where Office is installed elsewhere.
    """
    candidates: list[Path] = []
    if configured := os.environ.get("MML2OMML_XSL"):
        candidates.append(Path(configured))
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        if root := os.environ.get(variable):
            candidates.extend(
                [
                    Path(root) / "Microsoft Office" / "root" / "Office16" / "MML2OMML.XSL",
                    Path(root) / "Microsoft Office" / "Office16" / "MML2OMML.XSL",
                ]
            )
    candidates.append(
        Path(r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL")
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        "MML2OMML.XSL was not found. Install Microsoft Word or set "
        "MML2OMML_XSL to the stylesheet path."
    )


_OMML_TRANSFORM: etree.XSLT | None = None


def latex_to_omml(latex: str) -> OxmlElement:
    """Convert a LaTeX expression to a native Word ``m:oMath`` element."""
    global _OMML_TRANSFORM
    if _OMML_TRANSFORM is None:
        _OMML_TRANSFORM = etree.XSLT(etree.parse(str(_mml2omml_stylesheet())))
    mathml = latex_to_mathml(latex.strip())
    transformed = _OMML_TRANSFORM(etree.fromstring(mathml.encode("utf-8")))
    return parse_xml(etree.tostring(transformed.getroot()))


def style_base(document: Document) -> None:
    normal = document.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(BODY_PT)
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), BODY_FONT)
    paragraph = normal.paragraph_format
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    paragraph.line_spacing = 1.5
    paragraph.space_after = Pt(7)
    paragraph.first_line_indent = Pt(0)

    for section in document.sections:
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.left_margin = Cm(3.17)
        section.right_margin = Cm(3.17)
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)


def add_page_numbers(document: Document) -> None:
    """Page number bottom right, as the template has it."""
    for section in document.sections:
        footer_part = section.footer
        footer_part.is_linked_to_previous = False
        footer = footer_part.paragraphs[0]
        for child in list(footer._p):
            if child.tag != qn("w:pPr"):
                footer._p.remove(child)
        footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = footer.add_run()
        fld = OxmlElement("w:fldSimple")
        fld.set(qn("w:instr"), "PAGE")
        run._r.addnext(fld)
        footer.style.font.name = "Calibri"
        footer.style.font.size = Pt(11)


def request_field_updates(document: Document) -> None:
    """Ask Word to refresh the contents and figure/table lists on opening."""
    settings = document.settings.element
    existing = settings.find(qn("w:updateFields"))
    if existing is not None:
        settings.remove(existing)
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    settings.append(update)


def heading(document: Document, text: str, size: int, *, caps: bool = False,
            new_page: bool = False, toc_level: int | None = None) -> None:
    if new_page:
        document.add_page_break()
    p = document.add_paragraph()
    if toc_level is not None:
        p.style = document.styles[f"Heading {toc_level}"]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(10)
    p.paragraph_format.line_spacing = 1.2
    run = p.add_run(text.upper() if caps else text)
    run.font.name = BODY_FONT
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor(0, 0, 0)
    run.bold = False  # the template uses regular weight for every heading


def paragraph(document: Document, text: str) -> None:
    p = document.add_paragraph()
    # Bare markdown emphasis is stripped; the template uses italics only for
    # Latin names, which the prose does not contain.
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    cursor = 0
    for match in INLINE_MATH_RE.finditer(text):
        if match.start() > cursor:
            p.add_run(text[cursor:match.start()])
        p._p.append(latex_to_omml(match.group(1)))
        cursor = match.end()
    if cursor < len(text):
        p.add_run(text[cursor:])


def equation(document: Document, latex: str) -> None:
    counters["equation"] += 1
    p = document.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    tabs = p.paragraph_format.tab_stops
    tabs.add_tab_stop(Cm(7.3), WD_TAB_ALIGNMENT.CENTER)
    tabs.add_tab_stop(Cm(14.6), WD_TAB_ALIGNMENT.RIGHT)
    lead = p.add_run("\t")
    lead.font.name = MATH_FONT
    lead.font.size = Pt(BODY_PT)
    p._p.append(latex_to_omml(latex))
    number = p.add_run(f"\t({counters['equation']})")
    number.font.name = BODY_FONT
    number.font.size = Pt(BODY_PT)


def caption(document: Document, text: str, *, above: bool) -> None:
    p = document.add_paragraph()
    p.alignment = (WD_ALIGN_PARAGRAPH.LEFT if above
                   else WD_ALIGN_PARAGRAPH.CENTER)
    p.paragraph_format.space_before = Pt(6 if above else 4)
    p.paragraph_format.space_after = Pt(4 if above else 10)
    p.paragraph_format.line_spacing = 1.0
    match = re.match(r"^(Table|Figure) (\d+): (.+)$", text)

    def styled_run(value: str):
        run = p.add_run(value)
        run.font.name = BODY_FONT
        run.font.size = Pt(CAPTION_PT)
        run.italic = True
        return run

    if match:
        label, number, body = match.groups()
        styled_run(f"{label} ")
        field = OxmlElement("w:fldSimple")
        field.set(qn("w:instr"), rf"SEQ {label} \* ARABIC")
        result = OxmlElement("w:r")
        result_properties = OxmlElement("w:rPr")
        result_italic = OxmlElement("w:i")
        result_size = OxmlElement("w:sz")
        result_size.set(qn("w:val"), str(CAPTION_PT * 2))
        result_properties.extend((result_italic, result_size))
        result.append(result_properties)
        result_text = OxmlElement("w:t")
        result_text.text = number
        result.append(result_text)
        field.append(result)
        p._p.append(field)
        styled_run(f": {body}")
    else:
        styled_run(text)


def insert_table(document: Document, spec_id: str) -> None:
    path = TABLES / f"{spec_id}.json"
    if not path.exists():
        paragraph(document, f"[missing table spec: {spec_id}]")
        return
    spec = json.loads(path.read_text(encoding="utf-8"))
    counters["table"] += 1
    number = counters["table"]
    table_numbers[spec_id] = number

    caption(document, f"Table {number}: {spec['caption']}", above=True)

    columns = spec["columns"]
    table = document.add_table(rows=1, cols=len(columns))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    header = table.rows[0].cells
    for i, col in enumerate(columns):
        header[i].text = ""
        p = header[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.0
        run = p.add_run(str(col["header"]))
        run.bold = True
        run.font.name = BODY_FONT
        run.font.size = Pt(11)

    for row in spec["rows"]:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            if i >= len(columns):
                break
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            align = columns[i].get("align", "center")
            p.alignment = (WD_ALIGN_PARAGRAPH.LEFT if align == "left"
                           else WD_ALIGN_PARAGRAPH.CENTER)
            p.paragraph_format.line_spacing = 1.0
            run = p.add_run(str(value))
            run.font.name = BODY_FONT
            run.font.size = Pt(11)

    for key in ("notes", "source"):
        if spec.get(key):
            caption(document, spec[key], above=False)


def insert_figure(document: Document, fid: str, text: str) -> None:
    """Embed the generated figure, or a visible placeholder if absent."""
    counters["figure"] += 1
    # Generated figures are PNG at the figures root; interface captures are
    # JPEG under figures/screenshots.
    image = next((c for c in (FIGURES / f"{fid}.png",
                              FIGURES / f"{fid}.jpg",
                              FIGURES / "screenshots" / f"{fid}.png",
                              FIGURES / "screenshots" / f"{fid}.jpg")
                  if c.exists()), None)
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)
    if image is not None:
        # The text block is 21.0 - 2 x 3.17 = 14.66 cm wide. A portrait image
        # scaled to that width would run past the bottom of the page, so it is
        # constrained by height instead.
        from docx.image.image import Image as DocxImage
        probe = DocxImage.from_file(str(image))
        if probe.px_height > probe.px_width:
            p.add_run().add_picture(str(image), height=Cm(17.0))
        else:
            p.add_run().add_picture(str(image), width=Cm(14.0))
    else:
        run = p.add_run(f"[ Figure {counters['figure']} not yet generated: {fid} ]")
        run.font.name = BODY_FONT
        run.font.size = Pt(BODY_PT)
        run.italic = True
    caption(document, f"Figure {counters['figure']}: {text}", above=False)


def render_chapter(document: Document, path: Path, first: bool,
                   front_matter: bool = False) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)

    buffer: list[str] = []
    in_equation = False
    equation_lines: list[str] = []

    def flush() -> None:
        if buffer:
            paragraph(document, " ".join(buffer).strip())
            buffer.clear()

    for raw in text.splitlines():
        line = raw.rstrip()

        if line.strip().startswith("$$"):
            if not in_equation:
                flush()
                in_equation = True
                body = line.strip()[2:].strip()
                equation_lines = [body] if body else []
                if body.endswith("$$"):
                    equation(document, body[:-2].strip())
                    in_equation = False
            else:
                tail = line.strip()[:-2] if line.strip().endswith("$$") else line
                if tail.strip():
                    equation_lines.append(tail.strip())
                equation(document, " ".join(equation_lines))
                in_equation = False
            continue
        if in_equation:
            if line.strip().endswith("$$"):
                equation_lines.append(line.strip()[:-2].strip())
                equation(document, " ".join(equation_lines))
                in_equation = False
            else:
                equation_lines.append(line.strip())
            continue

        if not line.strip():
            flush()
            continue

        m = TABLE_RE.match(line.strip())
        if m:
            flush()
            insert_table(document, m.group(1))
            continue
        m = FIGURE_RE.match(line.strip())
        if m:
            flush()
            insert_figure(document, m.group(1), m.group(2))
            continue

        line = FIGREF_RE.sub(
            lambda m: f"Figure {FIGURE_NUMBERS[m.group(1)]}"
            if m.group(1) in FIGURE_NUMBERS else f"Figure ?? ({m.group(1)})",
            line)

        if line.startswith("### "):
            flush()
            heading(document, line[4:].strip(), L3_PT, toc_level=3)
        elif line.startswith("## "):
            flush()
            heading(document, line[3:].strip(), L2_PT, toc_level=2)
        elif line.startswith("# "):
            flush()
            heading(document, line[2:].strip(),
                    L2_PT if front_matter else CHAPTER_PT, caps=True,
                    new_page=not first, toc_level=1)
        else:
            buffer.append(line.strip())
    flush()


def centred(document: Document, text: str, size: float, *,
            before: int = 0, after: int = 0, italic: bool = False) -> None:
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(text)
    run.font.name = BODY_FONT
    run.font.size = Pt(size)
    run.bold = False
    run.italic = italic


def build_title_page(document: Document, meta: dict) -> None:
    """Reproduces the example diploma's title page layout.

    Everything is Times New Roman, regular weight, with the institutional block
    at the top, the logo beneath it, the title centred in the middle at 16 pt,
    then the thesis type, author, supervisor and place and date.
    """
    for key, size in (("university", 12), ("faculty", 12), ("department", 12)):
        centred(document, meta[key], size, after=4)
    centred(document, meta["division_line_1"], 11, before=10, after=0)
    centred(document, meta["division_line_2"], 11, after=10)

    logo = THESIS / meta.get("logo", "")
    if logo.exists():
        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(18)
        p.add_run().add_picture(str(logo), width=Cm(3.2))

    centred(document, meta["title"], 16, before=24, after=24)
    centred(document, meta["thesis_type"], 14, before=36, after=10)
    centred(document,
            f"{meta['author']} ({meta['registration_label']}: "
            f"{meta['registration_number']})", 14, after=28)
    centred(document, meta["supervisor"], 14, after=36)
    centred(document, meta["city"], 12, before=24, after=0)
    centred(document, meta["month_year"], 12)
    document.add_page_break()


def add_field(document: Document, instruction: str, placeholder: str) -> None:
    """Insert a Word field (used for the contents and the two lists).

    Word populates these when the document is opened and the fields are
    updated, so the entries follow the real headings and captions rather than a
    transcription that could drift.
    """
    p = document.add_paragraph()
    run = p.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = placeholder
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for element in (begin, instr, separate, text, end):
        run._r.append(element)


def format_reference(r: dict) -> str:
    """One reference entry in APA 7, as the example thesis applies it.

    The example lists every author in full rather than using "et al.", puts the
    journal in title case with volume(issue) and pages, and renders the DOI as a
    complete https://doi.org/ link.
    """
    # Do not strip the trailing period: it belongs to the final initial, as in
    # "Schlachtberger, D." The year follows it without a second period.
    authors = (r.get("authors") or "").strip()
    year = (r.get("year") or "n.d.").strip()
    title = (r.get("title") or "").strip().rstrip(".")
    container = (r.get("container") or "").strip()
    volume = (r.get("volume") or "").strip()
    issue = (r.get("issue") or "").strip()
    pages = (r.get("pages") or "").strip()
    publisher = (r.get("publisher") or "").strip()
    doi = (r.get("doi") or "").strip()
    url = (r.get("url") or "").strip()

    parts = [f"{authors} ({year}). {title}."]
    if container:
        locator = container
        if volume:
            locator += f", {volume}"
            if issue:
                locator += f"({issue})"
        if pages:
            locator += f", {pages}"
        parts.append(locator + ".")
    elif publisher:
        parts.append(publisher + ".")
    if doi:
        parts.append(f"https://doi.org/{doi}")
    elif url:
        parts.append(url)
    return " ".join(parts)


def sort_key(r: dict) -> str:
    return (r.get("authors") or r.get("title") or "").lstrip("\"' ").lower()


def build_references(document: Document) -> int:
    """The REFERENCES chapter, generated from references.csv."""
    path = THESIS / "references.csv"
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh)
                if r.get("status") != "NOT_USED_corporate_accounts"]

    document.add_page_break()
    heading(document, "REFERENCES", CHAPTER_PT, caps=True, toc_level=1)
    for r in sorted(rows, key=sort_key):
        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf = p.paragraph_format
        pf.line_spacing = 1.0
        pf.space_after = Pt(8)
        pf.left_indent = Cm(1.0)
        pf.first_line_indent = Cm(-1.0)  # hanging indent
        run = p.add_run(format_reference(r))
        run.font.name = BODY_FONT
        run.font.size = Pt(BODY_PT)
    return len(rows)


def set_page_numbering(section, fmt: str, start: int | None = None) -> None:
    """Lower-case roman for the front matter, arabic restarting at the body."""
    sect_pr = section._sectPr
    existing = sect_pr.find(qn("w:pgNumType"))
    if existing is not None:
        sect_pr.remove(existing)
    pg = OxmlElement("w:pgNumType")
    pg.set(qn("w:fmt"), fmt)
    if start is not None:
        pg.set(qn("w:start"), str(start))
    sect_pr.append(pg)


def main() -> int:
    document = Document()
    style_base(document)

    meta_path = THESIS / "metadata.json"
    if meta_path.exists():
        build_title_page(document, json.loads(meta_path.read_text(encoding="utf-8")))
        print("  + title page")

    front = sorted((THESIS / "frontmatter").glob("*.md"))
    # Numbers must exist before the first figure renders, so they are assigned
    # across every document up front, in render order.
    number_figures(front + sorted(CHAPTERS.glob("*.md"))
                   + sorted((THESIS / "appendices").glob("*.md")))
    for i, path in enumerate(front):
        render_chapter(document, path, first=(i == 0), front_matter=True)
        print(f"  + frontmatter/{path.name}")

    # Contents and the two lists, as Word fields so they follow the real
    # headings and captions. Word fills them when the fields are updated.
    for title, instruction, note in (
        ("Table of Contents", r'TOC \o "1-3" \h \z \u',
         "Right-click and update this field in Word to populate the contents."),
        ("LIST OF TABLES", r'TOC \h \z \c "Table"',
         "Right-click and update this field in Word to populate the list."),
        ("LIST OF FIGURES", r'TOC \h \z \c "Figure"',
         "Right-click and update this field in Word to populate the list."),
    ):
        document.add_page_break()
        heading(document, title, L2_PT)
        add_field(document, instruction, note)
        print(f"  + {title}")

    if front:
        # The body starts a new section so its page numbering can restart at 1
        # in arabic while the front matter keeps lower-case roman.
        set_page_numbering(document.sections[-1], "lowerRoman", start=1)
        document.add_section(WD_SECTION.NEW_PAGE)
        set_page_numbering(document.sections[-1], "decimal", start=1)
        # Counters restart with the body, as the template numbers them.
        counters["table"] = counters["figure"] = counters["equation"] = 0

    style_base(document)
    add_page_numbers(document)
    request_field_updates(document)

    chapters = sorted(CHAPTERS.glob("*.md"))
    if not chapters:
        sys.exit("no chapter sources found")
    for i, path in enumerate(chapters):
        render_chapter(document, path, first=(i == 0))
        print(f"  + {path.name}")

    n_refs = build_references(document)
    print(f"  + REFERENCES ({n_refs} entries)")
    for path in sorted((THESIS / "appendices").glob("*.md")):
        render_chapter(document, path, first=False)
        print(f"  + {path.name}")

    BUILD.mkdir(parents=True, exist_ok=True)
    # Word keeps an exclusive lock on an open document, so the build falls
    # back to a sibling filename rather than failing outright.
    out = BUILD / "thesis_draft.docx"
    if out.exists():
        try:
            with out.open("ab"):
                pass
        except PermissionError:
            out = BUILD / "thesis_draft_latest.docx"
            print(f"  ! thesis_draft.docx is locked; writing {out.name}")
    document.save(out)
    print(f"\n{counters['table']} tables, {counters['figure']} figures, "
          f"{counters['equation']} equations")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
