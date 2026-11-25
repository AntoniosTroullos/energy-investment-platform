import unittest
from unittest.mock import patch

from app import network_topology
from app.network_topology import corridor_provenance, get_real_interregional_lines

# Two square regions side by side, plus an island region offshore to the east.
FAKE_REGIONS = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"id": "West"},
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
        },
        {
            "type": "Feature",
            "properties": {"id": "East"},
            "geometry": {"type": "Polygon", "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]]},
        },
        {
            "type": "Feature",
            "properties": {"id": "Island"},
            "geometry": {"type": "Polygon", "coordinates": [[[4, 0], [4.2, 0], [4.2, 0.2], [4, 0.2], [4, 0]]]},
        },
    ],
}


def line(coordinates: list, *, voltage: int | None = 400, submarine: bool = False) -> dict:
    return {
        "type": "Feature",
        "properties": {"voltage_kv": voltage, "is_submarine": submarine},
        "geometry": {"type": "LineString", "coordinates": coordinates},
    }


def layers(lines: list[dict]):
    def _loader(name: str):
        if name == "admin_regions.geojson":
            return FAKE_REGIONS
        if name == "transmission_lines.geojson":
            return {"type": "FeatureCollection", "features": lines}
        return {"type": "FeatureCollection", "features": []}

    return _loader


class RealLineMatchingTests(unittest.TestCase):
    def setUp(self):
        self._clear()

    def tearDown(self):
        self._clear()

    @staticmethod
    def _clear():
        get_real_interregional_lines.cache_clear()
        network_topology._prepared_regions.cache_clear()
        network_topology._region_shapes.cache_clear()

    def test_a_line_crossing_two_regions_is_evidence_for_that_pair(self):
        with patch.object(
            network_topology, "get_source_layer_feature_collection", side_effect=layers([line([[0.5, 0.5], [1.5, 0.5]])])
        ):
            evidence = get_real_interregional_lines()
        self.assertEqual(evidence[frozenset(("West", "East"))]["circuit_count"], 1)
        self.assertEqual(evidence[frozenset(("West", "East"))]["voltages_kv"], {400})

    def test_a_line_inside_one_region_is_not_a_corridor(self):
        with patch.object(
            network_topology, "get_source_layer_feature_collection", side_effect=layers([line([[0.2, 0.5], [0.8, 0.5]])])
        ):
            self.assertEqual(get_real_interregional_lines(), {})

    def test_a_submarine_cable_is_matched_by_where_it_makes_landfall(self):
        # Every vertex of this route is at sea, so containment alone finds
        # nothing -- which would wrongly report every island interconnector as
        # unsupported.
        route = [[2.05, 0.1], [2.5, 0.1], [3.0, 0.1], [3.5, 0.1], [3.95, 0.1]]
        with patch.object(
            network_topology,
            "get_source_layer_feature_collection",
            side_effect=layers([line(route, voltage=150, submarine=True)]),
        ):
            evidence = get_real_interregional_lines()
        self.assertIn(frozenset(("East", "Island")), evidence)
        self.assertTrue(evidence[frozenset(("East", "Island"))]["submarine"])

    def test_a_cable_ending_far_from_any_region_is_not_snapped(self):
        # The snap must reach a landing point just offshore, not invent a
        # connection across open water.
        route = [[2.05, 0.1], [9.0, 0.1]]
        with patch.object(
            network_topology,
            "get_source_layer_feature_collection",
            side_effect=layers([line(route, submarine=True)]),
        ):
            self.assertEqual(get_real_interregional_lines(), {})


CORRIDOR_ROWS = [
    {"name": "West_East", "bus0": "West", "bus1": "East", "s_nom": "1600"},
    {"name": "East_Island", "bus0": "East", "bus1": "Island", "s_nom": "450"},
]


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        RealLineMatchingTests._clear()

    def tearDown(self):
        RealLineMatchingTests._clear()

    def test_corridors_are_split_into_corroborated_and_unmapped(self):
        with patch.object(
            network_topology,
            "get_source_layer_feature_collection",
            side_effect=layers([line([[0.5, 0.5], [1.5, 0.5]])]),
        ), patch.object(network_topology, "load_transmission_corridor_rows", return_value=CORRIDOR_ROWS):
            provenance = corridor_provenance()

        self.assertEqual(provenance["corridor_count"], 2)
        self.assertEqual(provenance["corroborated_count"], 1)
        self.assertEqual(provenance["corroborated_pct"], 50.0)

        by_id = {corridor["id"]: corridor for corridor in provenance["corridors"]}
        self.assertEqual(by_id["West_East"]["status"], "corroborated")
        self.assertEqual(by_id["West_East"]["real_voltages_kv"], [400])
        self.assertEqual(by_id["East_Island"]["status"], "not_in_osm_layer")

    def test_an_unmapped_corridor_says_missing_evidence_not_absence(self):
        with patch.object(
            network_topology, "get_source_layer_feature_collection", side_effect=layers([])
        ), patch.object(network_topology, "load_transmission_corridor_rows", return_value=CORRIDOR_ROWS):
            provenance = corridor_provenance()
        note = provenance["corridors"][0]["note"]
        self.assertIn("not that it is absent", note)

    def test_the_ratings_are_never_claimed_to_be_real(self):
        with patch.object(
            network_topology, "get_source_layer_feature_collection", side_effect=layers([])
        ), patch.object(network_topology, "load_transmission_corridor_rows", return_value=CORRIDOR_ROWS):
            provenance = corridor_provenance()
        self.assertIn("not ADMIE", provenance["corridor_ratings"])


if __name__ == "__main__":
    unittest.main()
