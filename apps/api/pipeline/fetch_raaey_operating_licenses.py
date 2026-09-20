from __future__ import annotations

import json
import sys
from pathlib import Path

import requests
from pyproj import Transformer
from shapely.geometry import shape

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

SOURCE_DIR = BASE_DIR / "data" / "source"
WFS_URL = "https://geo.rae.gr/geoserver/wfs"

# "ΑΔΕΙΑ ΛΕΙΤΟΥΡΓΙΑΣ" (Operating License) -- the RAAEY status code closest to
# "actually built and generating," as opposed to production/installation licenses
# (which can be held for years before -- or instead of -- construction) or any of
# the rejected/revoked/ceased codes. See KNOWLEDGE_TRANSFER.md for the full status
# code breakdown and why even this is a lower bound relative to DAPEEP's published
# national totals (calibration is applied downstream, not here).
OPERATING_LICENSE_CODE = "1.3"

LAYERS = {
    "wind": ("rae_status:V_SDI_R_AIOLIKA_ALL", "raaey_operating_wind.geojson"),
    "solar": ("rae_status:V_SDI_R_PHOTOVOLTAICS_ALL", "raaey_operating_solar.geojson"),
}

# RAAEY's geoportal serves geometry in the Greek national grid (EGSA87 / EPSG:2100);
# our pipeline works in WGS84 lat/lon throughout.
_transformer = Transformer.from_crs("EPSG:2100", "EPSG:4326", always_xy=True)


def main():
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    for carrier, (type_name, filename) in LAYERS.items():
        features = fetch_operating_features(type_name, carrier)
        write_geojson(SOURCE_DIR / filename, {"type": "FeatureCollection", "features": features})
        print(f"Wrote {len(features)} operating-license {carrier} projects to {filename}.")


def fetch_operating_features(type_name: str, carrier: str) -> list[dict]:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": type_name,
        "outputFormat": "application/json",
        "cql_filter": f"katastash_code='{OPERATING_LICENSE_CODE}'",
    }
    response = requests.get(WFS_URL, params=params, timeout=180)
    response.raise_for_status()
    payload = response.json()

    features = []
    for raw_feature in payload.get("features", []):
        feature = convert_feature(raw_feature, carrier)
        if feature is not None:
            features.append(feature)
    return features


def convert_feature(raw_feature: dict, carrier: str) -> dict | None:
    properties = raw_feature.get("properties", {})
    geometry = raw_feature.get("geometry")

    if not geometry:
        return None

    site_geometry = shape(geometry)
    if site_geometry.is_empty:
        return None

    centroid = site_geometry.centroid
    longitude, latitude = _transformer.transform(centroid.x, centroid.y)

    return {
        "type": "Feature",
        "properties": {
            "id": f"raaey-operating-{carrier}-{properties.get('id1')}",
            "name": properties.get("company"),
            "carrier": carrier,
            "capacity_mw": properties.get("power_mw"),
            "region": properties.get("kal_perifereia"),
            "regional_unit": properties.get("kal_perif_enothta"),
            "municipality": properties.get("kal_dhmos"),
            "site": properties.get("thesh"),
            "license_number": properties.get("a_m"),
            "katastash_code": properties.get("katastash_code"),
            "katastash_descr": properties.get("katastash_descr"),
            "license_issue_date": properties.get("imerominia_ekdosis_adeias"),
            "source": "RAAEY Operating License (geo.rae.gr)",
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
        },
        "geometry": {
            "type": "Point",
            "coordinates": [round(longitude, 6), round(latitude, 6)],
        },
    }


def write_geojson(path: Path, feature_collection: dict):
    with path.open("w", encoding="utf-8") as f:
        json.dump(feature_collection, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
