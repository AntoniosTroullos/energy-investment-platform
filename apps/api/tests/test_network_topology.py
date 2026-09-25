import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.network_topology import (
    REGION_SIMPLIFY_TOLERANCE_DEGREES,
    get_network_topology_geojson,
    get_region_centroids,
    get_simplified_admin_regions,
    load_transmission_corridor_rows,
)
from app.settings import load_settings

LINES_CSV_HEADER = "name,bus0,bus1,s_nom,x,r\n"


def count_vertices(geometry: dict) -> int:
    if geometry["type"] == "Polygon":
        return sum(len(ring) for ring in geometry["coordinates"])
    if geometry["type"] == "MultiPolygon":
        return sum(len(ring) for polygon in geometry["coordinates"] for ring in polygon)
    return 0


def make_settings_with_lines(root: Path, csv_body: str | None = None):
    if csv_body is not None:
        csv_path = root / "pypsa-greece" / "data" / "static" / "lines.csv"
        csv_path.parent.mkdir(parents=True)
        csv_path.write_text(csv_body, encoding="utf-8")
    return load_settings({"PYPSA_PROJECT_ROOT": str(root)})


class SimplifiedAdminRegionsTests(unittest.TestCase):
    """Exercises the real, checked-in admin_regions.geojson (see the ratio
    check below rather than a fixed number, since the raw file may itself
    grow or shrink slightly with future data updates)."""

    def test_simplification_keeps_every_region_but_shrinks_vertices_a_lot(self):
        get_simplified_admin_regions.cache_clear()
        from app.evaluation import get_source_layer_feature_collection

        raw = get_source_layer_feature_collection("admin_regions.geojson")
        simplified = get_simplified_admin_regions()

        raw_ids = {f["properties"].get("id") for f in raw["features"]}
        simplified_ids = {f["properties"].get("id") for f in simplified["features"]}
        self.assertEqual(raw_ids, simplified_ids)

        raw_vertices = sum(count_vertices(f["geometry"]) for f in raw["features"])
        simplified_vertices = sum(count_vertices(f["geometry"]) for f in simplified["features"])
        self.assertLess(simplified_vertices, raw_vertices * 0.25)

    def test_result_is_cached_across_calls(self):
        get_simplified_admin_regions.cache_clear()
        first = get_simplified_admin_regions()
        second = get_simplified_admin_regions()
        self.assertIs(first, second)


class RegionCentroidsTests(unittest.TestCase):
    def test_every_real_region_has_a_centroid_inside_greece(self):
        get_region_centroids.cache_clear()
        centroids = get_region_centroids()

        expected_ids = {
            "Attica", "Central_Greece", "Central_Macedonia", "Crete",
            "Eastern_Macedonia_Thrace", "Epirus", "Ionian_Islands",
            "North_Aegean", "Peloponnese", "South_Aegean", "Thessaly",
            "Western_Greece", "Western_Macedonia",
        }
        self.assertEqual(set(centroids.keys()), expected_ids)

        for region_id, (longitude, latitude) in centroids.items():
            self.assertTrue(18 <= longitude <= 30, f"{region_id} longitude {longitude} looks wrong")
            self.assertTrue(34 <= latitude <= 42, f"{region_id} latitude {latitude} looks wrong")


class NetworkTopologyGeojsonTests(unittest.TestCase):
    FAKE_CENTROIDS = {
        "Attica": (23.7, 38.0),
        "Peloponnese": (22.3, 37.5),
        "Crete": (25.0, 35.3),
    }

    def test_builds_one_linestring_per_corridor_with_capacity(self):
        body = LINES_CSV_HEADER + "Attica_Peloponnese,Attica,Peloponnese,1700,0.0002,0.00004\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = make_settings_with_lines(Path(tmpdir), body)
            with patch("app.network_topology.get_region_centroids", return_value=self.FAKE_CENTROIDS):
                topology = get_network_topology_geojson(settings)

        self.assertEqual(len(topology["features"]), 1)
        feature = topology["features"][0]
        self.assertEqual(feature["geometry"]["type"], "LineString")
        self.assertEqual(
            feature["geometry"]["coordinates"],
            [[23.7, 38.0], [22.3, 37.5]],
        )
        self.assertEqual(feature["properties"]["s_nom_mw"], 1700.0)
        self.assertEqual(feature["properties"]["bus0"], "Attica")
        self.assertEqual(feature["properties"]["bus1"], "Peloponnese")

    def test_corridor_naming_an_unknown_bus_is_skipped_not_crashed(self):
        body = LINES_CSV_HEADER + "Attica_Nowhere,Attica,Nowhere,500,0.0002,0.00004\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = make_settings_with_lines(Path(tmpdir), body)
            with patch("app.network_topology.get_region_centroids", return_value=self.FAKE_CENTROIDS):
                topology = get_network_topology_geojson(settings)

        self.assertEqual(topology["features"], [])

    def test_missing_lines_csv_yields_an_empty_but_valid_feature_collection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = make_settings_with_lines(Path(tmpdir))
            with patch("app.network_topology.get_region_centroids", return_value=self.FAKE_CENTROIDS):
                topology = get_network_topology_geojson(settings)

        self.assertEqual(topology, {"type": "FeatureCollection", "features": []})

    def test_malformed_capacity_value_yields_none_rather_than_crashing(self):
        body = LINES_CSV_HEADER + "Attica_Crete,Attica,Crete,not-a-number,0.0002,0.00004\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = make_settings_with_lines(Path(tmpdir), body)
            with patch("app.network_topology.get_region_centroids", return_value=self.FAKE_CENTROIDS):
                topology = get_network_topology_geojson(settings)

        self.assertIsNone(topology["features"][0]["properties"]["s_nom_mw"])


class LoadTransmissionCorridorRowsTests(unittest.TestCase):
    def test_reads_real_row_shape(self):
        body = LINES_CSV_HEADER + "A_B,A,B,900,0.0003,0.00006\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = make_settings_with_lines(Path(tmpdir), body)
            rows = load_transmission_corridor_rows(settings)

        self.assertEqual(rows, [{"name": "A_B", "bus0": "A", "bus1": "B", "s_nom": "900", "x": "0.0003", "r": "0.00006"}])

    def test_simplify_tolerance_is_a_small_positive_number(self):
        # Sanity guard against an accidental unit mistake (e.g. metres instead
        # of degrees) rather than a real behavioural assertion.
        self.assertTrue(0 < REGION_SIMPLIFY_TOLERANCE_DEGREES < 0.1)


if __name__ == "__main__":
    unittest.main()
