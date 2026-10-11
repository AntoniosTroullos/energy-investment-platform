"""The claims audit: does the prose say what the evidence supports?

check_numbers.py establishes that every number is traceable. That is necessary
and not sufficient: a traceable number can still be stated without its caveat,
or described in language the evidence does not carry. This script performs the
checks traceability cannot.

Five checks:

  1. WITHHELD   A withheld quantity must not be named as a finding.
  2. CAVEAT     A figure whose only ledger claims are flagged as biased must
                appear in a section that acknowledges the bias. Every
                wind-affected figure in this thesis is either an upper bound or
                withheld, and one quoted without that qualification
                misrepresents it.
  3. MARKERS    Unresolved [VERIFY: ...] citation markers.
  4. LANGUAGE   Overclaiming vocabulary for a least-cost planning model.
  5. VOICE      First person outside the acknowledgements.

Two rules keep the audit trustworthy rather than noisy. A value is attributed to
the BEST claim available for it -- an unbiased citable claim outranks a biased
one, which outranks a withheld one -- because the same number frequently appears
as both an input and a solved output. And only distinctive tokens are checked,
since short round numbers collide with section references, years and counts.

Exit code 1 if any hard check fails.

    python thesis/scripts/claims_audit.py
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

THESIS = Path(__file__).resolve().parents[1]
LEDGER = THESIS / "numbers_ledger.csv"
SOURCES = ("frontmatter/*.md", "chapters/*.md", "appendices/*.md")

NUMBER_RE = re.compile(
    r"(?<![\w.,])(?<![A-Za-z]-)(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)")

CROSSREF_RE = re.compile(
    r"(?:Table|Figure|Equation|Chapter|Section|Appendix|Eq\.|§)\s*[A-Z]?\.?\s*$",
    re.IGNORECASE)

CAVEAT_RE = re.compile(
    r"upper bound|lower bound|understat|overstat|withheld|withhold|caveat|bias|"
    r"not comparable|qualif|defect|stylised|placeholder|estimated|stated "
    r"direction|Section 3\.1\.2|Section 4\.1",
    re.IGNORECASE)

OVERCLAIM = [
    # "proved sufficient", "proved able", "proved to be" are the copular sense
    # (turned out to be), not a claim of proof. Only the assertive form is an
    # overclaim for a model result.
    (re.compile(r"\bprove[sd]?\s+(?:that|it|this)\b|\bthis proves\b|\bproof that\b",
                re.I),
     'use "indicates" or "shows"'),
    (re.compile(r"\baccurate(ly)?\b", re.I), "unsupported without a backtest"),
    (re.compile(r"\bbankable\b", re.I), 'use "investment screening"'),
    (re.compile(r"\bmarket price", re.I), 'use "planning shadow price"'),
    (re.compile(r"\bmeasured regional (demand|load)", re.I),
     'must be "estimated regional demand allocation"'),
    (re.compile(r"\bthe first (?:to|study|model|work|attempt)\b|\bnovel\b|"
                r"\bunprecedented\b", re.I), "priority claim needs support"),
    (re.compile(r"\bwill (?:be|happen|occur|result)\b", re.I),
     "a planning result is not a prediction"),
]

FIRST_PERSON = re.compile(r"\b(I|we|our|my|us)\b")

CITABLE, BIASED, WITHHELD = "citable", "biased", "withheld"


def load_ledger() -> dict[float, tuple[str, str]]:
    """value -> (rank, claim_id), keeping the best claim for each value."""
    rank = {CITABLE: 0, BIASED: 1, WITHHELD: 2}
    best: dict[float, tuple[str, str]] = {}
    with LEDGER.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                value = float(row["value"].replace(",", ""))
            except ValueError:
                continue
            if row["claim_id"].startswith("WITHHELD-"):
                kind = WITHHELD
            elif row["wind_bias"].strip() in ("understated", "overstated"):
                kind = BIASED
            else:
                kind = CITABLE
            current = best.get(value)
            if current is None or rank[kind] < rank[current[0]]:
                best[value] = (kind, row["claim_id"])
    return best


def distinctive(token: str) -> bool:
    """Specific enough to attribute to one claim without coincidence."""
    digits = token.replace(",", "").replace(".", "").lstrip("0")
    if len(digits) < 3:
        return False
    try:
        value = float(token.replace(",", ""))
    except ValueError:
        return False
    if 1900 <= value <= 2100 and "." not in token:
        return False
    return "." in token or value >= 1000


def resolve(token: str, ledger: dict[float, tuple[str, str]]):
    try:
        value = float(token.replace(",", ""))
    except ValueError:
        return None
    if value in ledger:
        return ledger[value]
    _, _, frac = token.partition(".")
    if not frac:
        return None
    hits = [v for v in ledger if round(v, len(frac)) == value]
    if not hits:
        return None
    # Prefer the best-ranked claim among the rounding matches.
    order = {CITABLE: 0, BIASED: 1, WITHHELD: 2}
    return min((ledger[v] for v in hits), key=lambda e: order[e[0]])


def sections(text: str):
    """Yield (heading, start_line, body) for each section of a source file."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    lines = text.splitlines()
    marks = [i for i, l in enumerate(lines) if l.startswith("#")]
    if not marks:
        yield ("(file)", 1, "\n".join(lines))
        return
    for n, start in enumerate(marks):
        end = marks[n + 1] if n + 1 < len(marks) else len(lines)
        yield (lines[start].lstrip("# ").strip(), start + 1,
               "\n".join(lines[start + 1:end]))


def audit() -> int:
    ledger = load_ledger()
    paths = [p for g in SOURCES for p in sorted(THESIS.glob(g))]
    found = {"withheld": [], "caveat": [], "markers": [], "language": [],
             "voice": []}
    checked = 0

    for path in paths:
        text = path.read_text(encoding="utf-8")
        is_ack = "acknowledge" in path.name.lower()
        for heading, start, body in sections(text):
            # The caveat may be stated anywhere in the section, not necessarily
            # in the same paragraph as the figure.
            section_has_caveat = bool(CAVEAT_RE.search(body))

            for m in NUMBER_RE.finditer(body):
                token = m.group(1)
                before = body[max(0, m.start() - 24):m.start()]
                if CROSSREF_RE.search(before) or not distinctive(token):
                    continue
                checked += 1
                entry = resolve(token, ledger)
                if entry is None:
                    continue
                kind, claim_id = entry
                if kind == WITHHELD:
                    found["withheld"].append((path.name, heading, token, claim_id))
                elif kind == BIASED and not section_has_caveat:
                    found["caveat"].append((path.name, heading, token, claim_id))

            for pattern, advice in OVERCLAIM:
                for m in pattern.finditer(body):
                    # Kept deliberately short. A wide window suppresses real
                    # findings whenever any negation happens to appear earlier
                    # in the paragraph, which is a false pass.
                    pre = body[max(0, m.start() - 55):m.start()].lower()
                    if re.search(r"\b(not|never|rather than|cannot|no)\b", pre):
                        continue
                    found["language"].append(
                        (path.name, heading, m.group(0), advice))

            if not is_ack:
                for m in FIRST_PERSON.finditer(body):
                    found["voice"].append((path.name, heading, m.group(0)))

            for m in re.finditer(r"\[VERIFY:([^\]]+)\]", body):
                found["markers"].append(
                    (path.name, heading, " ".join(m.group(1).split())[:60]))

    print(f"CLAIMS AUDIT - {len(paths)} files, {checked} distinctive figures checked\n")

    def report(key, title, fmt, limit=10):
        items = found[key]
        print(f"{title}: {len(items)}")
        for item in items[:limit]:
            print(fmt(item))
        if len(items) > limit:
            print(f"    ... and {len(items) - limit} more")
        print()
        return len(items)

    hard = report("withheld", "[1] WITHHELD QUANTITIES CITED AS FINDINGS",
                  lambda i: f"    {i[0]} / {i[1][:40]}\n        {i[2]} -> {i[3]}")
    hard += report("caveat", "[2] BIASED FIGURES IN A SECTION WITH NO CAVEAT",
                   lambda i: f"    {i[0]} / {i[1][:40]}\n        {i[2]} -> {i[3]}")
    hard += report("markers", "[3] UNRESOLVED CITATION MARKERS",
                   lambda i: f"    {i[0]} / {i[1][:40]}: {i[2]}")
    soft = report("language", "[4] OVERCLAIMING LANGUAGE (review)",
                  lambda i: f"    {i[0]} / {i[1][:34]}: \"{i[2]}\" - {i[3]}")
    soft += report("voice", "[5] FIRST PERSON OUTSIDE ACKNOWLEDGEMENTS (review)",
                   lambda i: f"    {i[0]} / {i[1][:40]}: \"{i[2]}\"")

    if hard:
        print(f"FAILED: {hard} finding(s) need action; {soft} flagged for review.")
        return 1
    print(f"PASSED: no withheld citations, no unqualified biased figures, no "
          f"unresolved markers. {soft} item(s) flagged for review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(audit())
