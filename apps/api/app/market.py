import json
import io
import zipfile
from datetime import date, timedelta
from xml.etree import ElementTree
from urllib import error, parse, request

from .models import (
    GreeceMarketSignalResponse,
    MarketFlowItem,
    MarketPriceSignal,
)


IPTO_FILE_API_URL = "https://www.admie.gr/getOperationMarketFilewRange"
GREECE_ZONE = "GR"

# IPTO's own ISP file only carries the balancing ("energy up"/imbalance)
# price, not the day-ahead wholesale price a trader would mean by "the
# price." Energy-Charts (Fraunhofer ISE) re-publishes ENTSO-E's day-ahead
# price for Greece on a documented, no-auth API -- used here as a clearly
# separate, clearly-labelled field, best-effort (a failure here must never
# break the IPTO-sourced flow/balancing data above it).
ENERGY_CHARTS_API_URL = "https://api.energy-charts.info/v2/price_current"
ENERGY_CHARTS_LICENSE_NOTE = (
    "Energy-Charts (Fraunhofer ISE) data is licensed for private/internal use; "
    "confirm this use is acceptable before relying on it publicly. See "
    "https://api.energy-charts.info for terms."
)


def get_greece_market_signal() -> GreeceMarketSignalResponse:
    try:
        flow_file_info = find_latest_ipto_file("RealTimeSCADAImportsExports", 4)
        price_file_info = find_latest_ipto_file("ISP3ISPResults", 7)
        flows = fetch_ipto_interconnection_flows(flow_file_info["file_path"])
        current_price = fetch_ipto_current_price(price_file_info["file_path"])
    except RuntimeError as request_error:
        return GreeceMarketSignalResponse(
            source="IPTO/ADMIE public file API",
            zone=GREECE_ZONE,
            status="error",
            currentPrice=MarketPriceSignal(),
            totalImportMw=0,
            totalExportMw=0,
            netImportMw=0,
            flows=[],
            summary=str(request_error),
        )

    total_import = round(sum(flow.powerMw for flow in flows if flow.direction == "import"), 1)
    total_export = round(sum(flow.powerMw for flow in flows if flow.direction == "export"), 1)
    net_import = round(total_import - total_export, 1)
    day_ahead_price = fetch_day_ahead_price()

    return GreeceMarketSignalResponse(
        source="IPTO/ADMIE public file API",
        zone=GREECE_ZONE,
        status="success",
        currentPrice=current_price,
        dayAheadPrice=day_ahead_price,
        dayAheadPriceSource="Energy-Charts (Fraunhofer ISE), via ENTSO-E" if day_ahead_price else None,
        dayAheadPriceLicenseNote=ENERGY_CHARTS_LICENSE_NOTE if day_ahead_price else None,
        totalImportMw=total_import,
        totalExportMw=total_export,
        netImportMw=net_import,
        flows=flows,
        summary=build_market_summary(current_price, total_import, total_export, net_import),
    )


def fetch_day_ahead_price() -> MarketPriceSignal | None:
    """Best-effort: the day-ahead price is a supplementary field, so any
    failure here (network, schema change) returns None rather than raising,
    which would otherwise take down the whole market signal response."""
    query = parse.urlencode({"bzn": GREECE_ZONE})
    url = f"{ENERGY_CHARTS_API_URL}?{query}"

    try:
        with request.urlopen(url, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))

        data_points = payload.get("data") or []
        if not data_points:
            return None

        latest = data_points[-1]
        value = latest.get("values", {}).get("day_ahead_price")
        timestamp = latest.get("timestamp")
        if value is None:
            return None

        return MarketPriceSignal(
            valueEurMwh=round(float(value), 2),
            datetime=timestamp,
            temporalGranularity="15_minutes",
            label="Day-ahead wholesale price",
        )
    except (error.URLError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def find_latest_ipto_file(file_category: str, days_back: int) -> dict:
    today = date.today()
    query = parse.urlencode(
        {
            "dateStart": (today - timedelta(days=days_back)).isoformat(),
            "dateEnd": today.isoformat(),
            "FileCategory": file_category,
        }
    )
    url = f"{IPTO_FILE_API_URL}?{query}"

    try:
        with request.urlopen(url, timeout=30) as response:
            files = json.loads(response.read().decode("utf-8"))
    except error.URLError as request_error:
        raise RuntimeError("Could not reach IPTO public market file API.") from request_error
    except json.JSONDecodeError as request_error:
        raise RuntimeError("IPTO file API returned invalid JSON.") from request_error

    if not isinstance(files, list) or not files:
        raise RuntimeError(f"No recent IPTO {file_category} files were found.")

    return files[0]


def fetch_ipto_interconnection_flows(file_url: str) -> list[MarketFlowItem]:
    try:
        import xlrd
    except ImportError as import_error:
        raise RuntimeError(
            "Install xlrd to parse IPTO .xls interconnection flow files."
        ) from import_error

    try:
        with request.urlopen(file_url, timeout=30) as response:
            file_contents = response.read()
    except error.URLError as request_error:
        raise RuntimeError("Could not download latest IPTO interconnection file.") from request_error

    workbook = xlrd.open_workbook(file_contents=file_contents)
    sheet = workbook.sheet_by_index(0)
    flows = []

    for row_index in range(0, sheet.nrows, 3):
        title = str(sheet.cell_value(row_index, 1)).strip()
        if "REALTIME NET" not in title:
            continue

        zone = title.replace("REALTIME NET (MWh)", "").strip()
        latest_value = latest_numeric_value(sheet.row_values(row_index + 2))
        if latest_value is None:
            continue

        # Positive net-flow values are treated as imports into Greece for this MVP.
        direction = "import" if latest_value >= 0 else "export"
        flows.append(
            MarketFlowItem(
                zone=normalize_ipto_zone_name(zone),
                direction=direction,
                powerMw=round(abs(latest_value), 1),
            )
        )

    if not flows:
        raise RuntimeError("IPTO interconnection file did not contain parseable flows.")

    return flows


def fetch_ipto_current_price(file_url: str) -> MarketPriceSignal:
    try:
        with request.urlopen(file_url, timeout=30) as response:
            file_contents = response.read()
    except error.URLError as request_error:
        raise RuntimeError("Could not download latest IPTO ISP price file.") from request_error

    rows = read_xlsx_rows(file_contents, "xl/worksheets/sheet1.xml")

    for row in rows:
        row_name = str(row[0]).strip() if row else ""
        if row_name == "Greece Price Energy Up":
            price = latest_numeric_value(row)
            if price is None:
                break

            return MarketPriceSignal(
                valueEurMwh=round(price, 2),
                temporalGranularity="15_minutes",
                label="Current ISP energy up price",
            )

    raise RuntimeError("IPTO ISP file did not contain a parseable Greece current price.")


def read_xlsx_rows(file_contents: bytes, worksheet_path: str) -> list[list[object]]:
    workbook = zipfile.ZipFile(io.BytesIO(file_contents))
    shared_strings = read_xlsx_shared_strings(workbook)
    root = ElementTree.fromstring(workbook.read(worksheet_path))
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows = []

    for row in root.findall(".//x:row", namespace):
        values: list[object] = []

        for cell in row.findall("x:c", namespace):
            reference = cell.attrib.get("r", "")
            value = cell.find("x:v", namespace)
            if value is None or value.text is None:
                continue

            column_index = get_excel_column_index(reference)
            while len(values) <= column_index:
                values.append("")

            if cell.attrib.get("t") == "s":
                shared_index = int(value.text)
                values[column_index] = shared_strings[shared_index]
            else:
                numeric_value = to_float(value.text)
                values[column_index] = numeric_value if numeric_value is not None else value.text

        rows.append(values)

    return rows


def read_xlsx_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []

    root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings = []

    for item in root.findall("x:si", namespace):
        parts = [
            text.text or ""
            for text in item.findall(".//x:t", namespace)
        ]
        strings.append("".join(parts))

    return strings


def get_excel_column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    column_index = 0

    for letter in letters:
        column_index = (column_index * 26) + (ord(letter.upper()) - 64)

    return column_index - 1


def latest_numeric_value(row_values: list) -> float | None:
    # IPTO files include hourly columns 1-24 plus a trailing column 25 that is
    # currently a placeholder/summary value. Use only the real hourly values.
    for value in reversed(row_values[1:25]):
        number_value = to_float(value)
        if number_value is not None:
            return number_value

    return None


def normalize_ipto_zone_name(zone: str) -> str:
    zone_map = {
        "FYROM": "North Macedonia",
        "ITALY": "Italy",
        "ALBANIA": "Albania",
        "BULGARIA": "Bulgaria",
        "TURKEY": "Turkey",
    }

    return zone_map.get(zone.upper(), zone.title())


def build_market_summary(
    current_price: MarketPriceSignal,
    total_import: float,
    total_export: float,
    net_import: float,
) -> str:
    price_text = (
        f"current ISP energy price is {current_price.valueEurMwh} EUR/MWh"
        if current_price.valueEurMwh is not None
        else "current ISP energy price is unavailable"
    )
    flow_text = "net importer" if net_import >= 0 else "net exporter"

    return (
        f"Greece is currently a {flow_text}. The {price_text}, with "
        f"{total_import} MW imported and {total_export} MW exported."
    )


def to_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None

    return None
