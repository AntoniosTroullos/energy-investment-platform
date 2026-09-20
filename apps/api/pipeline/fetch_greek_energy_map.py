from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

SOURCE_DIR = BASE_DIR / "data" / "source"

# Public Supabase project backing greekenergymap.org. Found by inspecting the site's
# own client-side network calls -- this is the same read-only REST endpoint and anon
# key any visitor's browser already uses to render the public map (anon key is
# intentionally shipped client-side, scoped by Supabase Row Level Security, not a
# secret credential). Attribution: Greek Energy Map, https://www.greekenergymap.org.
SUPABASE_URL = "https://weoykykfrvtxngpijijl.supabase.co/rest/v1/projects"
SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indlb3lreWtmcnZ0eG5ncGlqaWpsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMyMjA4MzYsImV4cCI6MjA4ODc5NjgzNn0."
    "0IVBPYcZyh1DJCwhC8K7YMrnP8Gxzg2CxDd-moSGsCg"
)
PAGE_SIZE = 1000


def main():
    projects = fetch_all_projects()
    feature_collection = build_feature_collection(projects)

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = SOURCE_DIR / "greek_energy_map_projects.geojson"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(feature_collection, f, indent=2, ensure_ascii=False)

    print(f"Fetched {len(projects)} projects, wrote {len(feature_collection['features'])} located features to {output_path}")


def fetch_all_projects() -> list[dict]:
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    }
    all_projects = []
    offset = 0

    while True:
        params = {
            "select": "*",
            "order": "created_at.asc,id.asc",
            "offset": offset,
            "limit": PAGE_SIZE,
        }
        response = requests.get(SUPABASE_URL, headers=headers, params=params, timeout=60)
        response.raise_for_status()
        page = response.json()

        if not page:
            break

        all_projects.extend(page)
        offset += PAGE_SIZE

    return all_projects


def build_feature_collection(projects: list[dict]) -> dict:
    features = []

    for project in projects:
        latitude = project.get("latitude")
        longitude = project.get("longitude")
        if latitude is None or longitude is None:
            continue

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": f"greekenergymap-{project['id']}",
                    "name": project.get("name_en"),
                    "name_el": project.get("name_el"),
                    "category": project.get("category"),
                    "status": project.get("status"),
                    "capacity_mw": project.get("capacity"),
                    "year": project.get("year"),
                    "budget_eur": project.get("budget"),
                    "owner": project.get("owner_en"),
                    "description": project.get("description_en"),
                    "source": "Greek Energy Map (greekenergymap.org)",
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [longitude, latitude],
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


if __name__ == "__main__":
    main()
