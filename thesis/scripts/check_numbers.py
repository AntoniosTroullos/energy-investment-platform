"""Fail the build on any number in the thesis that is not in the ledger.

This is the mechanical enforcement of master plan rule 0.3: "No invented numbers.
Every quantitative claim is traced to a file ... or to a cited external source."

It performs three checks, in order of severity:

  1. WITHHELD  -- a number that matches only a `WITHHELD-` ledger row. This is the
     most important check in this project: it catches citing R8c's system outputs
     or wind NPV/IRR, which the author's decisions bar from appearing as findings.
  2. UNTRACED  -- a number with no ledger match, no structural exemption and no
     allowlist entry.
  3. LANGUAGE  -- words that overclaim for a planning model ("market price",
     "forecast", "optimal", "proves"), reported as warnings.

Usage:
    python thesis/scripts/check_numbers.py                 # all chapter sources
    python thesis/scripts/check_numbers.py path/to/file.md  # specific files
    python thesis/scripts/check_numbers.py --stats          # ledger coverage
    python thesis/scripts/check_numbers.py --verbose        # show every match

Exit code 0 when clean, 1 on any WITHHELD or UNTRACED finding.

Allowlist: thesis/numbers_allowlist.txt, one entry per line as
    <number>  # reason
Use it only for numbers that are genuinely structural (page budgets, counts of
chapters) or that come from a cited source recorded in the reference list.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

THESIS = Path(__file__).resolve().parents[1]
LEDGER = THESIS / "numbers_ledger.csv"
ALLOWLIST = THESIS / "numbers_allowlist.txt"

# Ledger values kept as written, so tokens that are not plain numbers -- notably
# dotted software versions such as 3.14.3 -- can be matched literally.
RAW_VALUES: dict[str, str] = {}
DEFAULT_GLOBS = ("frontmatter/*.md", "chapters/*.md", "appendices/*.md")

# A number, optionally with a currency prefix or a percent suffix. Thousands
# separators are allowed. The lookarounds keep us from splitting identifiers
# like "EPSG:2100" or version strings.
# The leading lookbehind also rejects a digit attached to a word by a hyphen,
# so classification names like "NUTS-2" and "COVID-19" are not read as numbers.
GREEK_NUMBER_RE = re.compile(
    r"(?<![\w.,])(?<![A-Za-z]-)"
    r"(?P<num>\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)"
    r"(?![\w.]*\d)"
)

NUMBER_RE = re.compile(
    r"(?<![\w.,])(?<![A-Za-z]-)"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?![\w,]*\d)"
)

# A number that is part of a legal instrument's name is an identifier, not a
# quantity: Directive 92/43/EEC, Law 4685/2020, Regulation (EU) 2023/1184.
LEGAL_REF_RE = re.compile(
    r"\b(?:Directive|Regulation|Law|Decision|Treaty|Act)\b[^.]{0,40}$",
    re.IGNORECASE,
)

# Contexts in which a following number is a cross-reference, not a claim.
CROSSREF_RE = re.compile(
    r"(?:Table|Figure|Equation|Chapter|Section|Appendix|Eq\.|§)\s*"
    r"[A-Z]?\.?\s*$",
    re.IGNORECASE,
)

# Usage that explicitly disclaims a term is correct, so a match preceded by one
# of these is not reported.
NEGATION_RE = re.compile(
    r"\b(?:not|never|rather than|instead of|no|avoid|avoids|without|cannot|"
    r"distinct from|as opposed to)\b[^.]{0,40}$"
)

# LaTeX exponents and subscripts are notation, not quantities: the 2 in
# "W m^{-2}" is a unit exponent, and t in "D_{r,t}" is an index. These are
# stripped before a line is scanned for numbers.
TEX_SCRIPT_RE = re.compile(r"[\^_]\{[^}]*\}|[\^_]-?\d+")

# Overclaiming language for a least-cost planning model.
LANGUAGE_RULES = [
    (re.compile(r"\bmarket price", re.I),
     'say "planning shadow price"'),
    # Demand forecasting is a legitimate named activity and is described as such
    # in Section 2.3.1. This rule targets calling a PLANNING result a forecast,
    # so it fires only when a price, market or dispatch word is nearby. The
    # hyphenated compound "forecast-to-dispatch" names the pipeline whose first
    # stage is that demand forecast, so it is not the error this rule is for.
    (re.compile(r"\b(?:forecasts?|predicts?|prediction)\b(?!-to-)[^.]{0,60}\b(?:price|market|dispatch)\b"
                r"|\b(?:price|market)\b[^.]{0,40}\b(?:forecasts?|predicts?|prediction)\b", re.I),
     'for model output say "least-cost planning result", not a forecast'),
    (re.compile(r"\boptimal\b(?![^.]{0,40}\b(?:status|solver)\b)"
                r"(?<!reports an optimal)", re.I),
     'prefer "least-cost" unless referring to solver status'),
    (re.compile(r"\bproves?\b", re.I),
     'prefer "indicates" or "shows"'),
    (re.compile(r"\baccurate\b", re.I),
     "unsupported without a backtest; state the metric instead"),
    (re.compile(r"\bmeasured regional (?:demand|load)", re.I),
     'must be "estimated regional demand allocation"'),
    (re.compile(r"\bbankable\b", re.I),
     'say "investment screening"'),
]


def self_check() -> None:
    """Fail loudly if this file's own regex escapes have been mangled.

    Editing this script through a shell heredoc has twice turned a `\\b`
    word-boundary escape into a literal backspace byte, silently disabling a
    rule. A disabled rule is worse than a missing one, because the guard still
    reports success. This catches it at startup.
    """
    source = Path(__file__).read_bytes()
    control = {b for b in source if b < 9 or 13 < b < 32}
    if control:
        sys.exit(f"check_numbers.py contains control byte(s) {sorted(control)}: "
                 f"a regex escape has been mangled. Repair before trusting any "
                 f"result from this script.")


# A dotted software version such as 3.14.3 or 2026.2.0. These must be matched
# whole: the general number pattern would otherwise read "3.14.3" as "3.14".
VERSION_RE = re.compile(r"(?<![\w.,])\d+\.\d+\.\d+(?![\d\w])")


def parse_number(token: str, greek: bool = False) -> float | None:
    """Parse a prose number.

    English convention: comma groups thousands, dot is the decimal separator.
    Greek convention, used in the extended summary: dot groups thousands, comma
    is the decimal separator, so 1.026 means one thousand and twenty-six and
    83,47 means eighty-three point four seven.
    """
    try:
        if greek:
            return float(token.replace(".", "").replace(",", "."))
        return float(token.replace(",", ""))
    except ValueError:
        return None


def load_ledger() -> tuple[dict[float, list[str]], dict[float, list[str]]]:
    """Return (citable, withheld) maps from numeric value to claim ids."""
    citable: dict[float, list[str]] = {}
    withheld: dict[float, list[str]] = {}
    RAW_VALUES.clear()
    if not LEDGER.exists():
        sys.exit(f"ledger not found: {LEDGER}")
    with LEDGER.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            raw = str(row["value"]).strip()
            RAW_VALUES[raw] = row["claim_id"]
            value = parse_number(raw)
            if value is None:
                continue
            target = withheld if row["claim_id"].startswith("WITHHELD-") else citable
            target.setdefault(value, []).append(row["claim_id"])
    return citable, withheld


def load_allowlist() -> dict[float, str]:
    allowed: dict[float, str] = {}
    if not ALLOWLIST.exists():
        return allowed
    for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        token, _, reason = line.partition("#")
        value = parse_number(token.strip())
        if value is not None:
            allowed[value] = reason.strip() or "allowlisted"
    return allowed


def matches(value: float, token: str, ledger: dict[float, list[str]]) -> list[str]:
    """Does a prose number match a ledger value, allowing for rounding?

    Prose rounds ("24.13"); the ledger keeps precision ("24.1268"). A prose
    token matches if some ledger value, rounded to the token's own number of
    decimal places, equals it. Integers in prose also match a ledger value
    within half a unit, which covers "about 8,760 hours".
    """
    if value in ledger:
        return ledger[value]
    _, _, frac = token.partition(".")
    places = len(frac)
    hits: list[str] = []
    for candidate, ids in ledger.items():
        if places:
            if round(candidate, places) == value:
                hits.extend(ids)
        elif abs(candidate - value) < 0.05:
            # An integer in prose matches a ledger value only when that value
            # IS essentially the integer (8760.0 -> 8760). A loose tolerance
            # here would let an unrelated figure such as 12.67 capture "13".
            hits.extend(ids)
    return hits


def is_year(value: float, token: str) -> bool:
    return "." not in token and 1900 <= value <= 2100 and value.is_integer()


def check_file(path: Path, citable, withheld, allowed, verbose: bool) -> dict:
    text = path.read_text(encoding="utf-8")
    # A file may declare the Greek number convention on its first line.
    greek = bool(re.search(r"<!--\s*numbers:\s*greek\s*-->", text[:200]))
    number_re = GREEK_NUMBER_RE if greek else NUMBER_RE
    findings = {"withheld": [], "untraced": [], "language": [],
                "matched": 0, "crossref": 0, "years": 0, "allowlisted": 0,
                "negated": 0}

    in_comment = False
    previous = ""
    for lineno, line in enumerate(text.splitlines(), start=1):
        # HTML comments can span many lines; authoring notes live in them, so
        # their contents must not be checked.
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        if "<!--" in line and "-->" not in line:
            in_comment = True
            continue
        if line.lstrip().startswith(("```", "<!--", "|---")):
            continue
        # A markdown heading carries its own section number, which is a
        # cross-reference, not a claim.
        if line.lstrip().startswith("#"):
            continue

        scan_line = TEX_SCRIPT_RE.sub(" ", line)
        for vm in VERSION_RE.finditer(scan_line):
            token = vm.group(0)
            # "Section 3.1.1" is a cross-reference, not a version number, and
            # must be judged by the same context rule as any other reference.
            before = scan_line[max(0, vm.start() - 24):vm.start()]
            if vm.start() < 24:
                before = previous[-24:] + " " + before
            if CROSSREF_RE.search(before) or LEGAL_REF_RE.search(before):
                findings["crossref"] += 1
            elif token in RAW_VALUES:
                findings["matched"] += 1
            else:
                findings["untraced"].append((lineno, token, line.strip()[:110]))
        scan_line = VERSION_RE.sub(lambda m: " " * len(m.group(0)), scan_line)
        for m in number_re.finditer(scan_line):
            token = m.group("num")
            value = parse_number(token, greek)
            if value is None:
                continue

            # Wrapped prose can split "Section 4.1" across a line break, so the
            # tail of the previous line counts as preceding context.
            preceding = scan_line[max(0, m.start() - 24):m.start()]
            if m.start() < 24:
                preceding = previous[-24:] + " " + preceding
            if CROSSREF_RE.search(preceding) or LEGAL_REF_RE.search(preceding):
                findings["crossref"] += 1
                continue

            # The allowlist is short and author-curated, so an explicit entry
            # wins over a fuzzy match against any ledger row.
            if value in allowed:
                findings["allowlisted"] += 1
                continue

            hit_withheld = matches(value, token, withheld)
            hit_citable = matches(value, token, citable)

            if hit_withheld and not hit_citable:
                findings["withheld"].append(
                    (lineno, token, hit_withheld[:3], line.strip()[:110]))
                continue
            if hit_citable:
                findings["matched"] += 1
                if verbose:
                    print(f"    ok  {path.name}:{lineno} {token} -> "
                          f"{hit_citable[0]}")
                continue
            if value in allowed:
                findings["allowlisted"] += 1
                continue
            if is_year(value, token):
                findings["years"] += 1
                continue
            findings["untraced"].append((lineno, token, line.strip()[:110]))

        previous = line

        if greek:
            continue
        for pattern, advice in LANGUAGE_RULES:
            for m in pattern.finditer(line):
                # Prose that explicitly disclaims the term is correct usage,
                # e.g. "these are not forecasts of market prices".
                before = line[max(0, m.start() - 40):m.start()].lower()
                if NEGATION_RE.search(before):
                    findings["negated"] += 1
                    continue
                findings["language"].append(
                    (lineno, m.group(0), advice, line.strip()[:110]))

    return findings


def report(path: Path, f: dict) -> int:
    problems = len(f["withheld"]) + len(f["untraced"])
    if not problems and not f["language"]:
        print(f"  OK  {path.name}: {f['matched']} traced, "
              f"{f['crossref']} cross-refs, {f['years']} years, "
              f"{f['allowlisted']} allowlisted, "
              f"{f['negated']} negated-usage skips")
        return 0

    print(f"\n  {path}")
    for lineno, token, ids, context in f["withheld"]:
        print(f"    WITHHELD line {lineno}: {token} matches {', '.join(ids)}")
        print(f"      {context}")
        print("      This number is barred from appearing as a finding.")
    for lineno, token, context in f["untraced"]:
        print(f"    UNTRACED line {lineno}: {token}")
        print(f"      {context}")
    for lineno, word, advice, context in f["language"]:
        print(f"    language line {lineno}: \"{word}\" - {advice}")
        print(f"      {context}")
    return problems


def print_stats(citable, withheld) -> None:
    with LEDGER.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    print(f"ledger: {len(rows)} claims")
    print(f"  citable distinct values : {len(citable)}")
    print(f"  withheld distinct values: {len(withheld)}")
    by_section: dict[str, int] = {}
    by_bias: dict[str, int] = {}
    for r in rows:
        by_section[r["section"]] = by_section.get(r["section"], 0) + 1
        by_bias[r["wind_bias"]] = by_bias.get(r["wind_bias"], 0) + 1
    print("\n  by section:")
    for k in sorted(by_section):
        print(f"    {k:<10} {by_section[k]:>4}")
    print("\n  by wind bias:")
    for k in sorted(by_bias):
        print(f"    {k:<14} {by_bias[k]:>4}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    self_check()
    citable, withheld = load_ledger()
    allowed = load_allowlist()

    if args.stats:
        print_stats(citable, withheld)
        return 0

    paths = args.paths or sorted(
        p for g in DEFAULT_GLOBS for p in THESIS.glob(g))
    if not paths:
        print("no chapter sources yet - nothing to check.")
        print(f"ledger holds {len(citable)} citable and {len(withheld)} "
              f"withheld distinct values, ready for drafting.")
        return 0

    print(f"checking {len(paths)} file(s) against {LEDGER.name}\n")
    total = 0
    for path in paths:
        total += report(path, check_file(path, citable, withheld, allowed,
                                         args.verbose))

    print()
    if total:
        print(f"FAILED: {total} untraceable or withheld number(s).")
        return 1
    print("PASSED: every number traces to the ledger.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
