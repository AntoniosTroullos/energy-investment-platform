import unittest
from datetime import datetime

from app import ipto


class AthensClockTests(unittest.TestCase):
    """IPTO's spreadsheets carry Greek wall-clock times. Reading one as UTC
    shifts every price two or three hours against the production it values, so
    these conversions are pinned at the switch instants."""

    def test_winter_is_eet(self):
        self.assertEqual(
            ipto.athens_naive_to_utc(datetime(2026, 11, 27, 0, 0)).isoformat(),
            "2026-11-26T22:00:00+00:00",
        )

    def test_summer_is_eest(self):
        self.assertEqual(
            ipto.athens_naive_to_utc(datetime(2026, 7, 1, 12, 0)).isoformat(),
            "2026-07-01T09:00:00+00:00",
        )

    def test_spring_switch(self):
        # Last Sunday of March 2026 is the 29th. 02:59 local is still EET;
        # 03:00 is the first EEST instant.
        self.assertEqual(
            ipto.athens_naive_to_utc(datetime(2026, 3, 29, 2, 59)).isoformat(),
            "2026-03-29T00:59:00+00:00",
        )
        self.assertEqual(
            ipto.athens_naive_to_utc(datetime(2026, 3, 29, 3, 0)).isoformat(),
            "2026-03-29T00:00:00+00:00",
        )

    def test_autumn_switch(self):
        # Last Sunday of October 2026 is the 25th; EEST runs until 04:00 local.
        self.assertEqual(
            ipto.athens_naive_to_utc(datetime(2026, 10, 25, 3, 59)).isoformat(),
            "2026-10-25T00:59:00+00:00",
        )
        self.assertEqual(
            ipto.athens_naive_to_utc(datetime(2026, 10, 25, 4, 0)).isoformat(),
            "2026-10-25T02:00:00+00:00",
        )

    def test_serial_matches_the_file_it_came_from(self):
        # 46353.0 is the first period of the 2026-11-27 ISP file.
        self.assertEqual(
            ipto.athens_serial_to_utc(46353.0).isoformat(), "2026-11-26T22:00:00+00:00"
        )
        # One quarter-hour later.
        self.assertEqual(
            ipto.athens_serial_to_utc(46353.010416666664).isoformat(),
            "2026-11-26T22:15:00+00:00",
        )


class SpreadsheetHelperTests(unittest.TestCase):
    def test_column_index(self):
        self.assertEqual(ipto.column_index("A1"), 0)
        self.assertEqual(ipto.column_index("Z9"), 25)
        self.assertEqual(ipto.column_index("AA12"), 26)
        self.assertEqual(ipto.column_index("AB3"), 27)

    def test_to_float_rejects_text_and_booleans(self):
        self.assertEqual(ipto.to_float("12.5"), 12.5)
        self.assertEqual(ipto.to_float(3), 3.0)
        self.assertIsNone(ipto.to_float("TOTAL"))
        self.assertIsNone(ipto.to_float(True))
        self.assertIsNone(ipto.to_float(None))


def _clock(label: str, start: float, periods: int = 4) -> list[object]:
    return [label] + [start + index * 0.010416666 for index in range(periods)]


class SectionBoundsTests(unittest.TestCase):
    """Sections are located by their heading rows, which carry the period
    timestamps instead of data. Row numbers would not survive IPTO connecting
    a new unit, which for storage happens often."""

    def setUp(self):
        self.rows: list[list[object]] = [
            _clock("Storage Units", 46353.0),
            ["STO_01", -10.0, -10.0, 5.0, 5.0],
            ["STO_02", 0.0, 0.0, 1.0, 1.0],
            ["Total Storage Production", -10.0, -10.0, 6.0, 6.0],
            _clock("Dispatchable Load", 46353.0),
            ["SFIKIA_PUMP", -220.0, -220.0, 0.0, 0.0],
        ]

    def test_bounds_stop_at_the_next_heading(self):
        self.assertEqual(ipto.section_bounds(self.rows, "Storage Units"), (1, 4))

    def test_last_section_runs_to_the_end(self):
        self.assertEqual(ipto.section_bounds(self.rows, "Dispatchable Load"), (5, 6))

    def test_unknown_heading(self):
        self.assertIsNone(ipto.section_bounds(self.rows, "Nuclear Units"))

    def test_a_data_row_is_not_a_heading(self):
        # "Total Storage Production" carries numbers, not a period clock, so it
        # must not be mistaken for a section start.
        self.assertIsNone(ipto.section_bounds(self.rows, "Total Storage Production"))

    def test_period_timestamps_skip_non_serial_cells(self):
        row = _clock("Storage Units", 46353.0) + ["TOTAL"]
        stamps = ipto.period_timestamps(row)
        self.assertEqual(len(stamps), 4)
        self.assertEqual(stamps[0].isoformat(), "2026-11-26T22:00:00+00:00")


class FindRowTests(unittest.TestCase):
    def test_after_index_disambiguates_repeated_labels(self):
        # These files repeat labels: "Thermal Units" is a summary line near the
        # top and a section heading further down.
        rows: list[list[object]] = [
            ["Thermal Units", 100.0],
            ["something else", 1.0],
            _clock("Thermal Units", 46353.0),
        ]
        self.assertEqual(ipto.find_row(rows, "Thermal Units")[1], 100.0)
        self.assertEqual(ipto.find_row(rows, "Thermal Units", after=1)[0], "Thermal Units")
        self.assertIsNone(ipto.find_row(rows, "Hydro Units"))


class PublishedFileTests(unittest.TestCase):
    def test_file_date_comes_from_the_name(self):
        published = ipto.PublishedFile(
            category="IMBABE",
            name="20261116_IMBABE_01.xlsx",
            url="https://example.invalid/20261116_IMBABE_01.xlsx",
        )
        self.assertEqual(published.file_date.isoformat(), "2026-11-16")

    def test_file_date_is_none_without_a_date_prefix(self):
        published = ipto.PublishedFile(category="IMBABE", name="latest.xlsx", url="x")
        self.assertIsNone(published.file_date)


if __name__ == "__main__":
    unittest.main()
