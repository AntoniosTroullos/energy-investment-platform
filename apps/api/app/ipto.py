"""IPTO/ADMIE's public market file API -- the shared client.

Greece's transmission operator publishes its market results as dated
spreadsheets behind one JSON endpoint: ask it for a file category and a date
range, get back a list of files newest-first, then download the one you want.
Every dynamic market series this platform reads arrives that way, so the
listing, the download, the on-disk cache and the spreadsheet parsing live here
rather than being re-implemented per feed.

What matters about these files
------------------------------
*Timestamps are Greek local time.* The spreadsheets carry Excel date serials,
and an Imbalance Settlement Period is defined on the Greek clock, so a serial
has to be read as local time and converted -- not treated as UTC. Getting this
wrong shifts every price two or three hours against the production it is
supposed to value, which is the kind of error that still looks plausible on a
chart. `athens_serial_to_utc` does the conversion from the EU daylight-saving
rule, for the same reason app/day_ahead.py does: a stock Windows Python has no
tz database and this API deliberately carries almost no dependencies.

*Files are immutable once published.* A file named for a date and a run number
never changes, so downloads are cached on disk by file name and never
re-fetched. That is what makes a weekly settlement file cheap enough to read on
a request: the first read costs a download, the rest cost a disk read.

*Caching is per file, not per feed.* How often to look for a NEW file is a
different question, and it belongs to the feed registry in
app/market_feeds.py, not here.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib import parse, request
from xml.etree import ElementTree

FILE_API_URL = "https://www.admie.gr/getOperationMarketFilewRange"
SOURCE = "IPTO/ADMIE public market file API"

REQUEST_TIMEOUT_SECONDS = 40

# Excel's day zero. The 1900 leap-year bug means serials below 61 are wrong,
# which no market file ever reaches.
EXCEL_EPOCH = datetime(1899, 12, 30)

_SPREADSHEET_NAMESPACE = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

# File categories this platform reads. Named here so a caller cannot quietly
# ask for a category that does not exist and get an empty feed.
CATEGORY_ISP_RESULTS = "ISP1ISPResults"  # full day, 96 ISPs, published day-ahead
CATEGORY_ISP_INTRADAY = "ISP3ISPResults"  # rest of day, re-run intraday
CATEGORY_IMBALANCE = "IMBABE"  # settled imbalance + mFRR prices, weekly
CATEGORY_SCADA_FLOWS = "RealTimeSCADAImportsExports"


def cache_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "generated" / "ipto"


@dataclass(frozen=True)
class PublishedFile:
    category: str
    name: str
    url: str
    description: str | None = None

    @property
    def file_date(self) -> date | None:
        """The date in the file name (YYYYMMDD prefix), which is the market day
        the file describes -- not the day it was published."""
        match = re.match(r"(\d{8})", self.name)
        if not match:
            return None
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").date()
        except ValueError:
            return None


class IptoUnavailable(RuntimeError):
    """IPTO could not be reached, or published nothing for the window asked."""


# ---------------------------------------------------------------------------
# Listing and downloading
# ---------------------------------------------------------------------------


def list_files(category: str, days_back: int, *, end: date | None = None) -> list[PublishedFile]:
    """Files published for a category over a window, newest first."""
    last = end or date.today()
    query = parse.urlencode(
        {
            "dateStart": (last - timedelta(days=days_back)).isoformat(),
            "dateEnd": last.isoformat(),
            "FileCategory": category,
        }
    )
    try:
        with request.urlopen(f"{FILE_API_URL}?{query}", timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except OSError as request_error:  # OSError covers URLError, TimeoutError and SSLError
        raise IptoUnavailable(f"Could not reach IPTO's file API for {category}.") from request_error
    except json.JSONDecodeError as request_error:
        raise IptoUnavailable(f"IPTO's file API returned invalid JSON for {category}.") from request_error

    if not isinstance(payload, list):
        raise IptoUnavailable(f"IPTO's file API returned no list for {category}.")

    files: list[PublishedFile] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("file_path") or "").strip()
        if not url:
            continue
        files.append(
            PublishedFile(
                category=category,
                name=url.rsplit("/", 1)[-1],
                url=url,
                description=str(entry.get("file_description") or "").strip() or None,
            )
        )
    return files


def latest_file(category: str, days_back: int, *, end: date | None = None) -> PublishedFile:
    files = list_files(category, days_back, end=end)
    if not files:
        raise IptoUnavailable(f"IPTO published no {category} files in the last {days_back} days.")
    return files[0]


def download(published: PublishedFile, *, use_cache: bool = True) -> bytes:
    """A published file's bytes, from disk if it has been fetched before.

    Published files never change, so a cache hit needs no validation."""
    cached = cache_dir() / published.category / published.name
    if use_cache and cached.exists():
        return cached.read_bytes()

    try:
        with request.urlopen(published.url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            contents = response.read()
    except OSError as request_error:
        raise IptoUnavailable(f"Could not download {published.name}.") from request_error

    if use_cache:
        try:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(contents)
        except OSError:
            pass  # A read-only data directory is not a reason to fail the fetch.
    return contents


# ---------------------------------------------------------------------------
# Spreadsheet reading
# ---------------------------------------------------------------------------


def read_rows(contents: bytes, worksheet: str = "xl/worksheets/sheet1.xml") -> list[list[object]]:
    """An .xlsx worksheet as rows of values, with shared strings resolved and
    gaps in the sparse cell layout filled, so row[n] is always column n."""
    try:
        workbook = zipfile.ZipFile(io.BytesIO(contents))
    except zipfile.BadZipFile as bad_file:
        raise IptoUnavailable("IPTO file was not a readable spreadsheet.") from bad_file

    shared = _shared_strings(workbook)
    try:
        root = ElementTree.fromstring(workbook.read(worksheet))
    except (KeyError, ElementTree.ParseError) as bad_sheet:
        raise IptoUnavailable(f"IPTO file had no readable {worksheet}.") from bad_sheet

    rows: list[list[object]] = []
    for row in root.findall(".//x:row", _SPREADSHEET_NAMESPACE):
        values: list[object] = []
        for cell in row.findall("x:c", _SPREADSHEET_NAMESPACE):
            value = cell.find("x:v", _SPREADSHEET_NAMESPACE)
            if value is None or value.text is None:
                continue
            column = column_index(cell.attrib.get("r", ""))
            while len(values) <= column:
                values.append("")
            if cell.attrib.get("t") == "s":
                index = int(value.text)
                values[column] = shared[index] if 0 <= index < len(shared) else ""
            else:
                number = to_float(value.text)
                values[column] = number if number is not None else value.text
        rows.append(values)
    return rows


def _shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
    return [
        "".join(text.text or "" for text in item.findall(".//x:t", _SPREADSHEET_NAMESPACE))
        for item in root.findall("x:si", _SPREADSHEET_NAMESPACE)
    ]


def column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter.upper()) - 64)
    return index - 1


def to_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def row_label(row: list[object]) -> str:
    return str(row[0]).strip() if row else ""


def find_row(rows: list[list[object]], label: str, *, after: int = 0) -> list[object] | None:
    """The first row with this exact label at or after an index.

    `after` matters because these files repeat labels: "Thermal Units" is both
    a summary line near the top and a section heading further down, and
    "Energy Surplus" appears twice. A caller that knows which section it is in
    can say so."""
    for row in rows[after:]:
        if row_label(row) == label:
            return row
    return None


def section_bounds(rows: list[list[object]], heading: str) -> tuple[int, int] | None:
    """The row range belonging to a section heading.

    A section heading in these files is recognisable: its own row carries the
    period timestamps rather than data. The section runs to the next such row.
    That is sturdier than counting rows, which changes whenever IPTO connects
    a new unit."""
    start: int | None = None
    for index, row in enumerate(rows):
        if start is None:
            if row_label(row) == heading and _is_timestamp_row(row):
                start = index + 1
            continue
        if _is_timestamp_row(row):
            return start, index
    return (start, len(rows)) if start is not None else None


def _is_timestamp_row(row: list[object]) -> bool:
    if len(row) < 3:
        return False
    first = to_float(row[1])
    second = to_float(row[2])
    if first is None or second is None:
        return False
    # Excel serials for any plausible market date, one period apart.
    return 40000 < first < 80000 and 0 < second - first < 1


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------


def athens_serial_to_utc(serial: float) -> datetime:
    """An Excel date serial written on the Greek clock, as a UTC instant."""
    return athens_naive_to_utc(EXCEL_EPOCH + timedelta(days=float(serial)))


def athens_naive_to_utc(naive: datetime) -> datetime:
    """A Greek wall-clock time as a UTC instant.

    The inverse of day_ahead.greek_utc_offset_hours, which converts the other
    way. Expressed in local terms the EU rule is: EEST (UTC+3) from 03:00 on
    the last Sunday of March until 04:00 on the last Sunday of October, EET
    (UTC+2) otherwise.

    The hour from 03:00 to 04:00 on the October switch day happens twice in
    local time, and a wall-clock reading alone cannot say which. The first
    (still EEST) is taken, which is the ISO-8601 convention and the one IPTO's
    own files follow -- they carry 96 periods on that day, not 100, so the
    repeated hour is not represented at all."""
    offset = 3 if _dst_start(naive.year) <= naive < _dst_end(naive.year) else 2
    return (naive - timedelta(hours=offset)).replace(tzinfo=timezone.utc)


def _dst_start(year: int) -> datetime:
    return _last_sunday(year, 3).replace(hour=3)


def _dst_end(year: int) -> datetime:
    return _last_sunday(year, 10).replace(hour=4)


def _last_sunday(year: int, month: int) -> datetime:
    day = 31 if month in (1, 3, 5, 7, 8, 10, 12) else 30
    last = datetime(year, month, day)
    return last - timedelta(days=(last.weekday() + 1) % 7)


def period_timestamps(row: list[object]) -> list[datetime]:
    """The UTC instants on a section-heading row, which is where these files
    carry their period clock."""
    stamps: list[datetime] = []
    for value in row[1:]:
        serial = to_float(value)
        if serial is None or not 40000 < serial < 80000:
            continue
        stamps.append(athens_serial_to_utc(serial))
    return stamps
