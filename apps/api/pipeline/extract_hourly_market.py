"""Extracts the hourly market layer from a solved PyPSA network.

Why this exists
---------------
`scenario_result.json` -- the only thing the API could read until now -- carries
*annual averages*: `average_marginal_price_by_bus`, `generation_by_carrier_mwh`,
`capacity_factor_by_generator`. Those averages cannot answer the question an
investor actually asks, which is not "what is the average price in this region"
but "what is the price *at the hours this technology produces*". Solar in Greece
produces into the middle of the day, which is exactly when solar depresses the
price it is paid; a flat regional average hides that effect completely and
over-values every solar site by the size of the cannibalisation it ignores.

The hourly data needed to answer it (bus marginal prices, per-generator
availability and dispatch, snapshot weightings, line flows) exists only inside
the solved `network.nc`, which `apps/api` deliberately cannot read: it keeps
pandas/pypsa/linopy out of its own requirements so the API stays small and
deployable. So this script runs on the OTHER side of that boundary -- under
`PYPSA_PYTHON`, the sibling project's solver interpreter -- reads the solved
network once, and writes a compact, dependency-free JSON that the API then
treats as plain data.

It reads the model repository and writes only into this repository
(`apps/api/data/generated/hourly_market/`), so the upstream model stays
untouched and the derived layer travels with the platform -- including to a
deployment that has no solver and no `network.nc` behind it.

What it computes
----------------
Every price figure is weighted by `snapshot_weightings.objective`, because these
networks are representative days scaled to a full year (12 monthly days x 24 h,
each weighted ~730 h). Treating the 288 rows as equal-weight hours would
silently mis-weight every annual number.

  * time-weighted price     sum(w*lambda) / sum(w)      -- "the average price"
  * load-weighted price     sum(w*lambda*D) / sum(w*D)  -- what demand pays
  * realised capture price  sum(w*lambda*p) / sum(w*p)  -- what the solved fleet earned,
                            after curtailment, per carrier per region
  * availability capture    the same, but weighted by what the technology COULD
                            have produced (p_nom_opt * p_max_pu) rather than by
                            what the solver let it produce. This is the figure a
                            NEW price-taking project at that location would earn:
                            it is not reduced by curtailment the existing fleet
                            happens to suffer, and it is the one the candidate
                            economics use.
  * capture rate            availability capture / time-weighted price. Below
                            100% is cannibalisation: the technology is paid less
                            than the average hour is worth, because it produces
                            when its own kind is abundant.

Usage
-----
    <PYPSA_PYTHON> apps/api/pipeline/extract_hourly_market.py \
        --case clustered_mid_2026_monthly_days \
        [--network <path to network.nc>] [--out <dir>] [--no-series]

With no `--network`, the network is located under the sibling project's
`data/processed/pypsa_scenarios/<case>/` (`PYPSA_PROJECT_ROOT` honoured), trying
`network.nc` and then `coupled_outputs/network.nc`.

`--no-series` drops the hourly chart series and keeps only the derived
economics, for long cases (seasonal weeks = 864 snapshots) where the series
would dominate the file size.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

SCHEMA_VERSION = 1

# Bus carriers that mean "this is an electricity bus". The clustered networks
# label every bus "AC"; the coupled network also carries gas, H2 and heat buses,
# which have their own (quite different) shadow prices and must never be mixed
# into an electricity price average. An empty carrier is treated as AC, which is
# PyPSA's own default for a plain bus.
ELECTRICITY_BUS_CARRIERS = {"AC", "DC", "electricity", ""}

# Carriers whose output is weather-driven, so an availability profile
# (p_max_pu) is a real physical signal rather than a dispatch decision. Capture
# prices for anything else are reported from realised dispatch only.
VARIABLE_CARRIERS = {"solar", "wind", "ror", "run_of_river", "offwind", "onwind"}

# A corridor counts as congested in an hour when it carries at least this much
# of its rating. Not a hard binding test (that would need the line's own dual),
# but a transparent, reproducible utilisation threshold.
CONGESTION_UTILISATION_THRESHOLD = 0.90


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", required=True, help="Scenario case name, e.g. clustered_mid_2026_monthly_days")
    parser.add_argument("--network", default=None, help="Path to a solved network.nc (default: locate from --case)")
    parser.add_argument("--out", default=None, help="Output directory (default: apps/api/data/generated/hourly_market)")
    parser.add_argument("--no-series", action="store_true", help="Omit the hourly chart series")
    args = parser.parse_args(argv)

    network_path = Path(args.network) if args.network else locate_network(args.case)
    if network_path is None or not network_path.is_file():
        print(f"No solved network found for case '{args.case}'.", file=sys.stderr)
        return 2

    out_dir = Path(args.out) if args.out else default_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.case}.json"

    payload = extract(network_path, args.case, include_series=not args.no_series)
    out_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    size_kb = out_path.stat().st_size / 1024
    print(f"{args.case}: wrote {out_path} ({size_kb:.0f} KB)")
    return 0


# ---------------------------------------------------------------------------
# Locating the inputs
# ---------------------------------------------------------------------------


def project_root() -> Path:
    raw = os.environ.get("PYPSA_PROJECT_ROOT", "").strip()
    return Path(raw).expanduser() if raw else Path.home() / "PycharmProjects" / "pythonProject1"


def locate_network(case_name: str) -> Path | None:
    case_dir = project_root() / "data" / "processed" / "pypsa_scenarios" / case_name
    for relative in ("network.nc", Path("coupled_outputs") / "network.nc"):
        candidate = case_dir / relative
        if candidate.is_file():
            return candidate
    return None


def default_out_dir() -> Path:
    # <repo>/apps/api/pipeline/this_file.py -> <repo>/apps/api/data/generated/hourly_market
    return Path(__file__).resolve().parent.parent / "data" / "generated" / "hourly_market"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Network structure
# ---------------------------------------------------------------------------


def electricity_buses(network: pypsa.Network) -> list[str]:
    carriers = network.buses.get("carrier")
    if carriers is None:
        return list(network.buses.index)
    return [
        str(bus)
        for bus, carrier in carriers.items()
        if str(carrier) in ELECTRICITY_BUS_CARRIERS
    ]


def region_buses(network: pypsa.Network) -> list[str]:
    """The 13 modelled regions: the electricity buses that actually carry
    demand. In the clustered networks every generator sits on its own satellite
    bus (`Attica_solar_cluster_0`) wired to the region bus, so "has a load" is
    what separates a region from a generator stub; in the coupled network the
    generators sit on the region buses directly and the same test still holds."""
    electricity = set(electricity_buses(network))
    buses = [str(bus) for bus in network.loads.bus.unique() if str(bus) in electricity]
    return sorted(buses)


def generator_region_map(network: pypsa.Network, regions: list[str]) -> dict[str, str]:
    """Maps every generator to the region whose price it is paid at.

    A generator on a region bus maps to itself. A generator on a satellite bus
    maps by longest matching region-name prefix (`Attica_solar_cluster_0` ->
    `Attica`), and anything the prefix rule cannot place falls back to following
    the network's own lines out of that bus -- so a future naming change
    degrades into a slower lookup rather than a silently dropped generator."""
    by_length = sorted(regions, key=len, reverse=True)
    region_set = set(regions)
    mapping: dict[str, str] = {}

    for generator, bus in network.generators.bus.items():
        bus_name = str(bus)
        if bus_name in region_set:
            mapping[str(generator)] = bus_name
            continue
        match = next((region for region in by_length if bus_name.startswith(region)), None)
        if match is None:
            match = _region_through_lines(network, bus_name, region_set)
        if match is not None:
            mapping[str(generator)] = match
    return mapping


def _region_through_lines(network: pypsa.Network, bus_name: str, region_set: set[str]) -> str | None:
    for frame, left, right in ((network.lines, "bus0", "bus1"), (network.links, "bus0", "bus1")):
        if frame is None or len(frame) == 0:
            continue
        for _, row in frame.iterrows():
            if str(row[left]) == bus_name and str(row[right]) in region_set:
                return str(row[right])
            if str(row[right]) == bus_name and str(row[left]) in region_set:
                return str(row[left])
    return None


# ---------------------------------------------------------------------------
# Weighted statistics
# ---------------------------------------------------------------------------


def weighted_mean(values: pd.Series | np.ndarray, weights: np.ndarray) -> float | None:
    total_weight = float(np.sum(weights))
    if total_weight <= 0:
        return None
    return float(np.sum(np.asarray(values, dtype=float) * weights) / total_weight)


def weighted_capture_price(prices: np.ndarray, volumes: np.ndarray, weights: np.ndarray) -> float | None:
    """sum(w*lambda*q) / sum(w*q): the volume-weighted price a producer with
    profile `volumes` is paid. Returns None when the producer has no volume at
    all, which is a real answer ("this technology earns nothing here"), not a
    zero to be averaged into something else."""
    weighted_volume = float(np.sum(volumes * weights))
    if weighted_volume <= 0:
        return None
    return float(np.sum(prices * volumes * weights) / weighted_volume)


def availability_profile(network: pypsa.Network, generator: str) -> np.ndarray:
    """p_max_pu as a full per-snapshot array: the time-dependent column when the
    solver was given one, otherwise the generator's static value broadcast
    (PyPSA stores a constant availability statically, not as a column)."""
    varying = network.generators_t.p_max_pu
    if generator in varying.columns:
        return varying[generator].to_numpy(dtype=float)
    static = float(network.generators.at[generator, "p_max_pu"])
    return np.full(len(network.snapshots), static, dtype=float)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def extract(network_path: Path, case_name: str, *, include_series: bool = True) -> dict:
    network = pypsa.Network(str(network_path))

    weights = network.snapshot_weightings.objective.to_numpy(dtype=float)
    regions = region_buses(network)
    prices = network.buses_t.marginal_price
    generator_region = generator_region_map(network, regions)

    load_by_region = _load_by_region(network, regions)
    dispatch = network.generators_t.p

    by_region: dict[str, dict] = {}
    for region in regions:
        region_prices = prices[region].to_numpy(dtype=float) if region in prices.columns else None
        if region_prices is None:
            continue
        region_load = load_by_region.get(region)
        by_region[region] = {
            "time_weighted_price_eur_per_mwh": _round(weighted_mean(region_prices, weights)),
            "load_weighted_price_eur_per_mwh": _round(
                weighted_capture_price(region_prices, region_load, weights) if region_load is not None else None
            ),
            "load_mwh": _round(float(np.sum(region_load * weights)) if region_load is not None else None, 1),
            "peak_load_mw": _round(float(np.max(region_load)) if region_load is not None else None, 1),
            "carriers": _carrier_stats_for_region(
                network, region, region_prices, weights, generator_region, dispatch
            ),
        }

    national_price = _national_price_series(network, regions, prices, load_by_region)
    national_load = _national_load_series(load_by_region, len(network.snapshots))

    payload: dict = {
        "schema_version": SCHEMA_VERSION,
        "case_name": case_name,
        "network_path": str(network_path),
        "network_sha256": file_sha256(network_path),
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "snapshot_count": int(len(network.snapshots)),
        "weight_sum_hours": _round(float(np.sum(weights)), 1),
        "regions": regions,
        "national": _national_stats(national_price, national_load, weights, network, generator_region, prices),
        "by_region": by_region,
        "network_stress": _network_stress(network, weights, prices, regions),
    }

    if include_series:
        payload["series"] = _series(network, national_price, national_load, weights, prices, regions)

    return payload


def _load_by_region(network: pypsa.Network, regions: list[str]) -> dict[str, np.ndarray]:
    """Per-region demand in MW per snapshot, summed over every load on that bus.
    `loads_t.p_set` is the given demand; `loads_t.p` is the served demand, equal
    to it in every one of these solved networks (no load shedding), and p_set is
    present even in a network solved without storing per-load results."""
    series = network.loads_t.p_set if not network.loads_t.p_set.empty else network.loads_t.p
    if series.empty:
        return {}

    totals: dict[str, np.ndarray] = {}
    for load, bus in network.loads.bus.items():
        bus_name = str(bus)
        if bus_name not in regions or str(load) not in series.columns:
            continue
        values = series[str(load)].to_numpy(dtype=float)
        totals[bus_name] = totals.get(bus_name, np.zeros_like(values)) + values
    return totals


def _carrier_stats_for_region(
    network: pypsa.Network,
    region: str,
    region_prices: np.ndarray,
    weights: np.ndarray,
    generator_region: dict[str, str],
    dispatch: pd.DataFrame,
) -> dict[str, dict]:
    """Per-carrier economics at one region: what the fleet earned, what a new
    price-taking plant would earn, how much of the technology's potential the
    solver curtailed, and the capacity factors behind both."""
    generators = [
        str(name)
        for name in network.generators.index
        if generator_region.get(str(name)) == region
    ]
    if not generators:
        return {}

    stats: dict[str, dict] = {}
    carriers = {str(network.generators.at[name, "carrier"]) for name in generators}
    for carrier in sorted(carriers):
        members = [name for name in generators if str(network.generators.at[name, "carrier"]) == carrier]
        capacity_mw = float(sum(float(network.generators.at[name, "p_nom_opt"]) for name in members))
        if capacity_mw <= 0:
            continue

        potential = np.zeros(len(weights), dtype=float)
        produced = np.zeros(len(weights), dtype=float)
        for name in members:
            unit_capacity = float(network.generators.at[name, "p_nom_opt"])
            if unit_capacity <= 0:
                continue
            potential += unit_capacity * availability_profile(network, name)
            if name in dispatch.columns:
                produced += dispatch[name].to_numpy(dtype=float)

        weighted_potential = float(np.sum(potential * weights))
        weighted_produced = float(np.sum(produced * weights))
        is_variable = carrier in VARIABLE_CARRIERS

        time_weighted = weighted_mean(region_prices, weights) or 0.0
        availability_capture = (
            weighted_capture_price(region_prices, potential, weights) if is_variable else None
        )
        realised_capture = weighted_capture_price(region_prices, produced, weights)

        entry: dict = {
            "installed_capacity_mw": _round(capacity_mw, 1),
            "generation_mwh": _round(weighted_produced, 1),
            "realised_capacity_factor_pct": _round(
                100.0 * weighted_produced / (capacity_mw * float(np.sum(weights)))
            ),
            "realised_capture_price_eur_per_mwh": _round(realised_capture),
        }
        if is_variable:
            entry["availability_capacity_factor_pct"] = _round(
                100.0 * weighted_potential / (capacity_mw * float(np.sum(weights)))
            )
            entry["availability_capture_price_eur_per_mwh"] = _round(availability_capture)
            entry["curtailment_pct"] = _round(
                100.0 * (1.0 - weighted_produced / weighted_potential) if weighted_potential > 0 else None
            )
            if availability_capture is not None and time_weighted > 0:
                entry["capture_rate_pct"] = _round(100.0 * availability_capture / time_weighted)
        stats[carrier] = entry
    return stats


def _national_price_series(
    network: pypsa.Network,
    regions: list[str],
    prices: pd.DataFrame,
    load_by_region: dict[str, np.ndarray],
) -> np.ndarray:
    """One national price per snapshot: the load-weighted mean across regions,
    which is the only aggregation that keeps the national average consistent
    with what demand actually pays. With no load data it falls back to the
    plain mean across region buses."""
    columns = [region for region in regions if region in prices.columns]
    if not columns:
        return np.zeros(len(network.snapshots), dtype=float)

    matrix = prices[columns].to_numpy(dtype=float)
    if not load_by_region:
        return matrix.mean(axis=1)

    load_matrix = np.column_stack([load_by_region.get(region, np.zeros(matrix.shape[0])) for region in columns])
    totals = load_matrix.sum(axis=1)
    safe = np.where(totals > 0, totals, 1.0)
    weighted = (matrix * load_matrix).sum(axis=1) / safe
    return np.where(totals > 0, weighted, matrix.mean(axis=1))


def _national_load_series(load_by_region: dict[str, np.ndarray], snapshot_count: int) -> np.ndarray:
    if not load_by_region:
        return np.zeros(snapshot_count, dtype=float)
    return np.sum(np.column_stack(list(load_by_region.values())), axis=1)


def _national_stats(
    national_price: np.ndarray,
    national_load: np.ndarray,
    weights: np.ndarray,
    network: pypsa.Network,
    generator_region: dict[str, str],
    prices: pd.DataFrame,
) -> dict:
    """National aggregates, plus the price-duration shape. The duration
    percentiles are what separate "the average price is EUR 24" from "the price
    is near zero most hours and very high in a few" -- two systems with the same
    mean and completely different investment cases."""
    sorted_index = np.argsort(national_price)
    sorted_prices = national_price[sorted_index]
    sorted_weights = weights[sorted_index]
    cumulative = np.cumsum(sorted_weights) / float(np.sum(sorted_weights))

    def percentile(fraction: float) -> float | None:
        position = int(np.searchsorted(cumulative, fraction))
        position = min(position, len(sorted_prices) - 1)
        return float(sorted_prices[position]) if len(sorted_prices) else None

    zero_mask = national_price <= 0.01
    return {
        "time_weighted_price_eur_per_mwh": _round(weighted_mean(national_price, weights)),
        "load_weighted_price_eur_per_mwh": _round(weighted_capture_price(national_price, national_load, weights)),
        "total_load_mwh": _round(float(np.sum(national_load * weights)), 1),
        "peak_load_mw": _round(float(np.max(national_load)) if national_load.size else None, 1),
        "price_duration_eur_per_mwh": {
            "p5": _round(percentile(0.05)),
            "p25": _round(percentile(0.25)),
            "p50": _round(percentile(0.50)),
            "p75": _round(percentile(0.75)),
            "p95": _round(percentile(0.95)),
        },
        "near_zero_price_hours": _round(float(np.sum(weights[zero_mask])), 1),
        "carriers": _national_carrier_stats(network, weights, generator_region, prices),
    }


def _national_carrier_stats(
    network: pypsa.Network,
    weights: np.ndarray,
    generator_region: dict[str, str],
    prices: pd.DataFrame,
) -> dict[str, dict]:
    """The same capture arithmetic as per region, but each generator priced at
    ITS OWN region's price before aggregating -- never at a national average,
    which would smear away exactly the locational signal this layer exists to
    expose."""
    dispatch = network.generators_t.p
    totals: dict[str, dict[str, float]] = {}

    for name in network.generators.index:
        generator = str(name)
        region = generator_region.get(generator)
        if region is None or region not in prices.columns:
            continue
        carrier = str(network.generators.at[generator, "carrier"])
        capacity = float(network.generators.at[generator, "p_nom_opt"])
        if capacity <= 0:
            continue

        region_prices = prices[region].to_numpy(dtype=float)
        potential = capacity * availability_profile(network, generator)
        produced = dispatch[generator].to_numpy(dtype=float) if generator in dispatch.columns else np.zeros_like(potential)

        bucket = totals.setdefault(
            carrier,
            {"capacity_mw": 0.0, "potential_mwh": 0.0, "produced_mwh": 0.0, "potential_value": 0.0, "produced_value": 0.0},
        )
        bucket["capacity_mw"] += capacity
        bucket["potential_mwh"] += float(np.sum(potential * weights))
        bucket["produced_mwh"] += float(np.sum(produced * weights))
        bucket["potential_value"] += float(np.sum(potential * region_prices * weights))
        bucket["produced_value"] += float(np.sum(produced * region_prices * weights))

    hours = float(np.sum(weights))
    stats: dict[str, dict] = {}
    for carrier, bucket in sorted(totals.items()):
        entry: dict = {
            "installed_capacity_mw": _round(bucket["capacity_mw"], 1),
            "generation_mwh": _round(bucket["produced_mwh"], 1),
            "realised_capacity_factor_pct": _round(
                100.0 * bucket["produced_mwh"] / (bucket["capacity_mw"] * hours) if bucket["capacity_mw"] > 0 else None
            ),
            "realised_capture_price_eur_per_mwh": _round(
                bucket["produced_value"] / bucket["produced_mwh"] if bucket["produced_mwh"] > 0 else None
            ),
        }
        if carrier in VARIABLE_CARRIERS and bucket["potential_mwh"] > 0:
            entry["availability_capacity_factor_pct"] = _round(
                100.0 * bucket["potential_mwh"] / (bucket["capacity_mw"] * hours)
            )
            entry["availability_capture_price_eur_per_mwh"] = _round(
                bucket["potential_value"] / bucket["potential_mwh"]
            )
            entry["curtailment_pct"] = _round(100.0 * (1.0 - bucket["produced_mwh"] / bucket["potential_mwh"]))
        stats[carrier] = entry
    return stats


def _network_stress(
    network: pypsa.Network,
    weights: np.ndarray,
    prices: pd.DataFrame,
    regions: list[str],
) -> dict:
    """Corridor utilisation and the locational price spread -- the two signals
    that say whether the transmission system is actually constraining anything.
    A spread of ~0 everywhere means no corridor binds, which is itself a finding
    about the modelled topology rather than a property of the real grid."""
    columns = [region for region in regions if region in prices.columns]
    spread = (
        prices[columns].to_numpy(dtype=float).max(axis=1) - prices[columns].to_numpy(dtype=float).min(axis=1)
        if len(columns) > 1
        else np.zeros(len(weights))
    )

    stress: dict = {
        "mean_region_price_spread_eur_per_mwh": _round(weighted_mean(spread, weights), 4),
        "max_region_price_spread_eur_per_mwh": _round(float(np.max(spread)) if spread.size else None, 4),
        "line_count": int(len(network.lines)),
        "corridors": [],
    }

    flows = network.lines_t.p0
    if len(network.lines) == 0 or flows.empty:
        return stress

    total_hours = float(np.sum(weights))
    utilisations: list[float] = []
    congested_hours_total = 0.0
    corridors: list[dict] = []

    for line in network.lines.index:
        name = str(line)
        rating = float(network.lines.at[line, "s_nom"])
        if rating <= 0 or name not in flows.columns:
            continue
        utilisation = np.abs(flows[name].to_numpy(dtype=float)) / rating
        mean_utilisation = weighted_mean(utilisation, weights) or 0.0
        congested_hours = float(np.sum(weights[utilisation >= CONGESTION_UTILISATION_THRESHOLD]))
        utilisations.append(mean_utilisation)
        congested_hours_total += congested_hours
        corridors.append(
            {
                "line": name,
                "from": str(network.lines.at[line, "bus0"]),
                "to": str(network.lines.at[line, "bus1"]),
                "rating_mw": _round(rating, 1),
                "mean_utilisation_pct": _round(100.0 * mean_utilisation),
                "peak_utilisation_pct": _round(100.0 * float(np.max(utilisation))),
                "congested_hours": _round(congested_hours, 1),
            }
        )

    corridors.sort(key=lambda row: row["mean_utilisation_pct"] or 0.0, reverse=True)
    stress["mean_utilisation_pct"] = _round(100.0 * float(np.mean(utilisations)) if utilisations else None)
    stress["congested_corridor_hours"] = _round(congested_hours_total, 1)
    stress["total_transfer_capacity_mw"] = _round(
        float(network.lines.s_nom[network.lines.s_nom > 0].sum()), 1
    )
    stress["share_of_hours_with_a_congested_corridor_pct"] = _round(
        100.0 * congested_hours_total / (total_hours * max(len(corridors), 1))
    )
    # Only the corridors worth drawing: the top of the utilisation ranking.
    stress["corridors"] = corridors[:20]
    return stress


def _series(
    network: pypsa.Network,
    national_price: np.ndarray,
    national_load: np.ndarray,
    weights: np.ndarray,
    prices: pd.DataFrame,
    regions: list[str],
) -> dict:
    """The hourly series the UI charts. Deliberately a short list: national
    price, national demand and generation by carrier. Per-region price series
    are not included -- 13 x N floats would dominate the file, and the regional
    story is already told by the aggregates above."""
    dispatch = network.generators_t.p
    generation: dict[str, list[float]] = {}
    for carrier in sorted({str(c) for c in network.generators.carrier.unique()}):
        members = [str(name) for name in network.generators.index if str(network.generators.at[name, "carrier"]) == carrier]
        columns = [name for name in members if name in dispatch.columns]
        if not columns:
            continue
        total = dispatch[columns].to_numpy(dtype=float).sum(axis=1)
        if float(np.max(np.abs(total))) <= 0:
            continue
        generation[carrier] = [round(float(value), 1) for value in total]

    return {
        "timestamps": [str(stamp) for stamp in network.snapshots],
        "weights_hours": [round(float(value), 4) for value in weights],
        "national_price_eur_per_mwh": [round(float(value), 2) for value in national_price],
        "national_load_mw": [round(float(value), 1) for value in national_load],
        "generation_mw_by_carrier": generation,
    }


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    return round(float(value), digits)


if __name__ == "__main__":
    raise SystemExit(main())
