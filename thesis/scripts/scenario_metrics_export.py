"""Export Scenario A and B metrics in the platform's ScenarioMetrics shape.

Step 1 of the candidate-economics derivation. The platform's own investment
functions expect a ScenarioMetrics object, but the frozen API will only build
one for cases matching `future_electricity_YYYY`, every one of which decision D1
excludes from the thesis. This script builds the same structure from the two
solved clustered networks instead, so that candidate economics can be derived
against Scenario A and B rather than against an excluded case.

It is a transcription, not a reimplementation: every field is read from the
solved network and none is recomputed by a different method than the model used.

Run with the MODEL interpreter (it needs pypsa):
    ...\\pypsa-greece\\.venv314\\Scripts\\python.exe thesis/scripts/scenario_metrics_export.py

Writes thesis/evidence/scenario_metrics_{A,B}.json for step 2
(candidate_economics.py), which runs under the API interpreter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pypsa

MODEL = Path(r"C:\Users\megas\PycharmProjects\pythonProject1")
OUT = Path(__file__).resolve().parents[1] / "evidence"

NETWORKS = {
    "A": (MODEL / "pypsa-greece/outputs/clustered/networks/greece_clustered.nc",
          "Baseline"),
    "B": (MODEL / "pypsa-greece/outputs/clustered/networks/greece_clustered_scenario_b.nc",
          "Post-Lignite / Spot Gas"),
}

# The 13 model regions. A clustered network also carries per-cluster buses, and
# only the regional hubs correspond to the regions candidate cells fall inside.
REGIONS = [
    "Attica", "Central_Greece", "Central_Macedonia", "Crete",
    "Eastern_Macedonia_Thrace", "Epirus", "Ionian_Islands", "North_Aegean",
    "Peloponnese", "South_Aegean", "Thessaly", "Western_Greece",
    "Western_Macedonia",
]


def export(label: str, path: Path, name: str) -> dict:
    n = pypsa.Network(str(path))
    w = n.snapshot_weightings.objective
    total_w = float(w.sum())
    mp = n.buses_t.marginal_price

    # Weight-weighted mean price at each regional hub. Candidate cells are
    # joined to regions, so only these buses are relevant.
    prices: dict[str, float] = {}
    for region in REGIONS:
        if region in mp.columns:
            prices[region] = round(float((mp[region] * w).sum() / total_w), 4)
        else:
            matches = [c for c in mp.columns if c == region or c.startswith(f"{region}_")]
            if matches:
                series = mp[matches].mean(axis=1)
                prices[region] = round(float((series * w).sum() / total_w), 4)

    generation: dict[str, float] = {}
    capacity: dict[str, float] = {}
    cf_by_generator: dict[str, float] = {}
    for carrier in sorted(n.generators.carrier.unique()):
        idx = n.generators.index[n.generators.carrier == carrier]
        gen = float(n.generators_t.p[idx].mul(w, axis=0).sum().sum())
        cap = float(n.generators.p_nom_opt[idx].sum())
        generation[carrier] = round(gen, 2)
        capacity[carrier] = round(cap, 2)
    for gen_name in n.generators.index:
        cap = float(n.generators.p_nom_opt[gen_name])
        if cap > 0:
            energy = float((n.generators_t.p[gen_name] * w).sum())
            cf_by_generator[gen_name] = round(energy / (cap * total_w), 6)

    payload = {
        "scenario": label,
        "scenario_name": name,
        "source_network": str(path),
        "snapshots": len(n.snapshots),
        "weighted_hours": total_w,
        "installed_capacity_by_carrier_mw": capacity,
        "optimized_capacity_by_carrier_mw": capacity,
        "generation_by_carrier_mwh": generation,
        "average_marginal_price_by_bus": prices,
        "capacity_factor_by_generator": cf_by_generator,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / f"scenario_metrics_{label}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"  + Scenario {label} ({name}): {len(prices)} regional prices, "
          f"{len(generation)} carriers -> {out_path.name}")
    return payload


def main() -> int:
    for label, (path, name) in NETWORKS.items():
        if not path.exists():
            print(f"  ! missing network for Scenario {label}: {path}")
            continue
        export(label, path, name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
