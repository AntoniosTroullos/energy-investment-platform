import unittest

from pipeline.fetch_osm_power import parse_voltage_kv


class VoltageParserTests(unittest.TestCase):
    def test_parses_single_voltage_value(self):
        self.assertEqual(parse_voltage_kv("400000"), 400)
        self.assertEqual(parse_voltage_kv("150000"), 150)
        self.assertEqual(parse_voltage_kv("20"), 20)

    def test_parses_semicolon_separated_multi_circuit_value(self):
        self.assertEqual(parse_voltage_kv("400000;150000"), 400)

    def test_parses_slash_and_comma_separated_multi_circuit_value(self):
        self.assertEqual(parse_voltage_kv("400000/150000"), 400)
        self.assertEqual(parse_voltage_kv("154000,34500"), 154)

    def test_handles_missing_or_empty_voltage(self):
        self.assertIsNone(parse_voltage_kv(None))
        self.assertIsNone(parse_voltage_kv(""))
        self.assertIsNone(parse_voltage_kv("unknown"))


if __name__ == "__main__":
    unittest.main()
