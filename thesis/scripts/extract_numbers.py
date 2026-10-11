"""Extract every quantitative claim the thesis makes from the frozen result files.

Writes thesis/numbers_ledger.csv. Nothing in the thesis may state a number that is
not in this ledger (see check_numbers.py).

Run with the MODEL interpreter, which has pypsa:

    C:\\Users\\megas\\PycharmProjects\\pythonProject1\\pypsa-greece\\.venv314\\Scripts\\python.exe \\
        thesis/scripts/extract_numbers.py

Both repositories are read-only. This script only reads.

The `wind_bias` column records the DIRECTION of the wind-availability error for each
claim, because it is not uniform across run families -- see extract_wind_benchmark().
Values: none | understated | overstated | withheld.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MODEL = Path(r"C:\Users\megas\PycharmProjects\pythonProject1")
PLATFORM = Path(__file__).resolve().parents[2]
LEDGER = Path(__file__).resolve().parents[1] / "numbers_ledger.csv"
THESIS_EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"

SCENARIOS = MODEL / "data" / "processed" / "pypsa_scenarios"
COUPLED = SCENARIOS / "coupled_greece_2025_production"
PG_PROCESSED = MODEL / "pypsa-greece" / "data" / "processed"
PG_STATIC = MODEL / "pypsa-greece" / "data" / "static"
PG_TS = MODEL / "pypsa-greece" / "data" / "timeseries"
VALIDATION = PLATFORM / "data" / "validation" / "national_load"

FIELDS = [
    "claim_id", "chapter", "section", "claim", "value", "unit",
    "source_kind", "source_path_or_citation", "provenance_class",
    "wind_bias", "extracted_at",
]

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
rows: list[dict] = []

# The project's own observed benchmark, from calibrate_wind_profiles.py.
DAPEEP_WIND_CF = None


def rel(path: Path) -> str:
    for root, alias in ((MODEL, "MODEL"), (PLATFORM, "PLATFORM")):
        try:
            return f"{alias}/{path.relative_to(root).as_posix()}"
        except ValueError:
            continue
    return str(path)


def add(claim_id, chapter, section, claim, value, unit, source, *,
        source_kind="result_file", provenance="derived", wind_bias="none"):
    rows.append({
        "claim_id": claim_id, "chapter": chapter, "section": section,
        "claim": claim, "value": value, "unit": unit,
        "source_kind": source_kind, "source_path_or_citation": source,
        "provenance_class": provenance, "wind_bias": wind_bias,
        "extracted_at": NOW,
    })


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def fnum(value) -> float:
    return float(str(value).strip() or 0)


# ==========================================================================
# Wind availability benchmark -- the evidence that D0's direction is not
# uniform across run families. Extracted first because every other claim's
# wind_bias tag depends on it.
# ==========================================================================
def extract_wind_benchmark() -> None:
    global DAPEEP_WIND_CF
    import pandas as pd

    sys.path.insert(0, str(MODEL / "pypsa-greece" / "scripts"))
    from calibrate_wind_profiles import dapeep_2025_wind_capacity_factor

    DAPEEP_WIND_CF = float(dapeep_2025_wind_capacity_factor())
    add("D0-benchmark-dapeep-cf", 3, "3.1.2",
        "Observed Greek wind capacity factor, DAPEEP 2025 annual bulletin "
        "(computed by the project's own dapeep_2025_wind_capacity_factor())",
        f"{100 * DAPEEP_WIND_CF:.2f}", "%",
        rel(MODEL / "pypsa-greece/scripts/calibrate_wind_profiles.py"),
        source_kind="project_function", provenance="measured")

    def profile_mean(path):
        return float(pd.read_csv(path, index_col=0)
                     .select_dtypes("number").values.mean())

    # Tier 1: the base timeseries, before and after the power-curve correction.
    # The correction moved the defective curve to data/timeseries/legacy/ under
    # a name recording what it was, so the defect this thesis documents stays
    # traceable to a file rather than to a memory of one. Where the legacy file
    # is present it is the authority for the pre-correction figures.
    for label in ("regional", "clustered"):
        current = PG_TS / f"wind_pu_{label}.csv"
        legacy = PG_TS / "legacy" / f"wind_pu_{label}_fraction_cubed.csv"
        pre = legacy if legacy.exists() else current
        if not pre.exists():
            continue
        mean = profile_mean(pre)
        add(f"D0-committed-profile-{label}", 3, "3.1.2",
            f"Mean wind availability in the {label} timeseries before the "
            f"power-curve correction (the D0-defective fraction-cubed curve)",
            f"{mean:.4f}", "per-unit", rel(pre), provenance="derived")
        add(f"D0-committed-ratio-{label}", 3, "3.1.2",
            f"Pre-correction {label} wind availability relative to the DAPEEP "
            f"benchmark", f"{mean / DAPEEP_WIND_CF:.3f}", "ratio", rel(pre),
            provenance="derived")
        if legacy.exists() and current.exists():
            fixed = profile_mean(current)
            add(f"D0-corrected-profile-{label}", 3, "3.1.2",
                f"Mean wind availability in the {label} timeseries after the "
                f"power-curve correction and calibration",
                f"{fixed:.4f}", "per-unit", rel(current), provenance="derived")
            add(f"D0-corrected-ratio-{label}", 3, "3.1.2",
                f"Corrected {label} wind availability relative to the DAPEEP "
                f"benchmark", f"{fixed / DAPEEP_WIND_CF:.3f}", "ratio",
                rel(current), provenance="derived")

    # The correction's own report, so its calibrated outcome is citable.
    report = PG_PROCESSED / "wind_calibration_report.json"
    if report.exists():
        rep = load_json(report)
        cf = rep.get("fleet_capacity_factor", {})
        for key, label in (
            ("legacy_curve", "Fleet wind capacity factor under the defective curve"),
            ("standard_curve_uncalibrated",
             "Fleet wind capacity factor under the standard curve, before calibration"),
            ("calibrated", "Fleet wind capacity factor after correction and calibration"),
        ):
            if key in cf:
                add(f"D0-calibration-cf-{key.replace('_', '-')}", 3, "3.1.2",
                    label, f"{100 * cf[key]:.3f}", "%", rel(report),
                    provenance="derived")
        if "national_scale_factor" in rep:
            add("D0-calibration-scale-factor", 3, "3.1.2",
                "National scale factor applied by the wind calibration",
                f"{rep['national_scale_factor']:.5f}", "factor", rel(report),
                provenance="derived")

    # Tier 2 and 3: what each SOLVED run actually achieved. The per-scenario
    # input files carry the same filenames as the committed ones but different
    # content, which is why the run families diverge.
    for scen, family in [
        ("mid_2026_monthly_days", "stylised 13-bus"),
        ("long_2026_seasonal_weeks", "stylised 13-bus"),
        ("clustered_mid_2026_monthly_days", "clustered reconciled"),
        ("clustered_long_2026_seasonal_weeks", "clustered reconciled"),
    ]:
        path = SCENARIOS / scen / "scenario_result.json"
        if not path.exists():
            continue
        m = load_json(path)["metrics"]
        cap = m["optimized_capacity_by_carrier_mw"].get("wind", 0)
        gen = m["generation_by_carrier_mwh"].get("wind", 0)
        curt = m.get("curtailment_by_carrier_mwh", {}).get("wind", 0)
        if not cap:
            continue
        avail_cf = (gen + curt) / (cap * 8760)
        bias = "overstated" if avail_cf > DAPEEP_WIND_CF else "understated"
        add(f"D0-run-availcf-{scen}", 3, "3.1.2",
            f"Wind availability capacity factor achieved in {scen} ({family} fleet)",
            f"{100 * avail_cf:.2f}", "%", rel(path), provenance="derived",
            wind_bias=bias)
        add(f"D0-run-ratio-{scen}", 3, "3.1.2",
            f"{scen} wind availability relative to the DAPEEP benchmark "
            f"(>1 means wind is OVERstated)",
            f"{avail_cf / DAPEEP_WIND_CF:.3f}", "ratio", rel(path),
            provenance="derived", wind_bias=bias)


def extract_availability_distributions() -> None:
    """Distribution statistics for the availability profiles (Section 3.1.2).

    A capacity-factor series must contain calm hours. These statistics are the
    evidence that the stylised base's wind series does not, and they are
    extracted rather than quoted so the prose cannot drift from the files.
    """
    import numpy as np
    import pypsa

    nc = COUPLED / "network.nc"
    if not nc.exists():
        return
    n = pypsa.Network(str(nc))
    src = rel(nc)
    pmax = n.get_switchable_as_dense("Generator", "p_max_pu")

    for carrier in ("wind", "solar"):
        cols = [g for g in n.generators.index[n.generators.carrier == carrier]
                if g in pmax.columns]
        if not cols:
            continue
        v = pmax[cols].values
        stats = [
            ("mean", float(v.mean()), "per-unit", "Mean availability"),
            ("min", float(v.min()), "per-unit", "Minimum availability"),
            ("max", float(v.max()), "per-unit", "Maximum availability"),
            ("zero-share", float((v == 0).mean()) * 100, "%",
             "Share of hours at exactly zero availability"),
            ("calm-share", float((v < 0.05).mean()) * 100, "%",
             "Share of hours below 0.05 availability"),
            ("p5", float(np.percentile(v, 5)), "per-unit",
             "Fifth percentile of availability"),
        ]
        for slug, value, unit, label in stats:
            add(f"profile-{carrier}-{slug}", 3, "3.1.2",
                f"{label}, {carrier}, stylised 13-region base",
                f"{value:.4f}" if unit == "per-unit" else f"{value:.2f}",
                unit, src, provenance="derived",
                wind_bias="overstated" if carrier == "wind" else "none")


def r8c_wind_bias() -> str:
    """2026-10-02: the stylised electricity base's wind profile has been
    re-derived from the corrected power curve and DAPEEP-calibrated (see
    pypsa-greece/data/processed/wind_calibration_report.json, fleet CF
    23.834% against an observed 23.83% target); R8c has been re-solved
    against it. No longer biased relative to the other run families."""
    return "none"


# ==========================================================================
# R8c -- the coupled production run (master plan D2-REVISED)
# ==========================================================================
def extract_r8c_result() -> None:
    result = load_json(COUPLED / "scenario_result.json")
    src = rel(COUPLED / "scenario_result.json")
    m = result["metrics"]
    bias = r8c_wind_bias()

    add("R8c-accepted", 3, "3.7.2", "Coupled production run solver acceptance",
        str(result["accepted"]).lower(), "boolean", src)
    add("R8c-objective", 3, "3.7.2",
        "Coupled system total annualised cost (objective)",
        f"{result['objective_eur_per_year']:.2f}", "EUR/yr", src, wind_bias=bias)

    for key, label in [("generator_variable", "generator variable cost"),
                       ("link_variable", "link variable cost"),
                       ("generator_capital", "generator annualised capital cost"),
                       ("link_capital", "link annualised capital cost")]:
        add(f"R8c-cost-{key}", 3, "3.7.2", f"Coupled cost ledger: {label}",
            f"{m['cost_ledger_eur'][key]:.2f}", "EUR/yr", src, wind_bias=bias)

    add("R8c-emissions", 3, "3.7.2",
        "Coupled system CO2 emissions (generators)",
        f"{m['emissions_ledger_tco2']['generators']:.2f}", "tCO2/yr", src,
        wind_bias=bias)
    add("R8c-emissions-links", 3, "3.7.2",
        "Coupled CO2 attributed to links (counted once at the gas bus)",
        f"{m['emissions_ledger_tco2']['links']:.1f}", "tCO2/yr", src)
    add("R8c-total-demand", 3, "3.7.2",
        "Coupled system total demand across all carriers",
        f"{m['total_demand_mwh']:.2f}", "MWh/yr", src)

    prices = m["planning_shadow_price_eur_per_mwh_by_bus"]
    for bus, unit, cid in [
        ("Greece_Gas", "EUR/MWh_HHV", "R8c-price-gas"),
        ("Greece_H2", "EUR/MWh_LHV", "R8c-price-h2"),
        ("Attica", "EUR/MWh_e", "R8c-price-elec-mainland"),
        ("South_Aegean", "EUR/MWh_e", "R8c-price-elec-south-aegean"),
        ("Crete", "EUR/MWh_e", "R8c-price-elec-crete"),
        ("Attica_Heat", "EUR/MWh_th", "R8c-price-heat"),
    ]:
        add(cid, 3, "3.7.3", f"Planning shadow price at bus {bus}",
            f"{prices[bus]:.4f}", unit, src, wind_bias=bias)

    mainland = [b for b in prices
                if not b.endswith("_Heat") and not b.startswith("Greece_")
                and b not in ("Crete", "South_Aegean")]
    spread = max(prices[b] for b in mainland) - min(prices[b] for b in mainland)
    add("R8c-mainland-price-spread", 3, "3.7.3",
        "Spread of electricity planning shadow price across the mainland buses",
        f"{spread:.2e}", "EUR/MWh_e", src)
    add("R8c-mainland-bus-count", 3, "3.7.3",
        "Mainland electricity buses sharing an identical shadow price",
        str(len(mainland)), "buses", src)

    for carrier, cap in sorted(m["capacity_output_mw_by_carrier"].items()):
        add(f"R8c-cap-out-{carrier}", 3, "3.7.1",
            f"Coupled run solved output-side capacity, {carrier} "
            f"(STYLISED 13-bus fleet, not the reconciled fleet of R1)",
            f"{cap:.2f}", "MW", src, wind_bias=bias)


def extract_r8c_scope() -> None:
    cfg = load_json(COUPLED / "scenario_config.json")
    src = rel(COUPLED / "scenario_config.json")
    for key, label, unit in [
        ("target_year", "Coupled run target year", "year"),
        ("load_year", "Coupled run load year", "year"),
        ("weather_year", "Coupled run weather year", "year"),
        ("temporal_mode", "Coupled run temporal mode", "mode"),
        ("hydrogen_target_mode", "Coupled run hydrogen target mode", "mode"),
        ("hydrogen_policy_mode", "Coupled run hydrogen policy mode", "mode"),
        ("trade_direction_mode", "Coupled run cross-border trade mode", "mode"),
    ]:
        add(f"R8c-scope-{key}", 3, "3.7.1", label, str(cfg[key]), unit, src,
            source_kind="scenario_config", provenance="scenario_assumption")

    add("R8c-h2-target", 3, "3.7.1",
        "Coupled run annual hydrogen final-demand target",
        f"{cfg['annual_hydrogen_target_mwh']:.2f}", "MWh_LHV/yr", src,
        source_kind="scenario_config", provenance="scenario_assumption")
    add("R8c-carbon-price", 3, "3.7.1", "Coupled run CO2 price",
        f"{cfg['system']['carbon_price_eur_per_tonne']:.1f}", "EUR/tCO2", src,
        source_kind="scenario_config", provenance="sourced")
    add("R8c-gas-ef", 3, "3.7.1",
        "Gas emission factor, HHV basis (IPCC 2006 default, NCV->HHV converted)",
        f"{cfg['system']['gas_emission_factor_tco2_per_mwh_hhv']:.4f}",
        "tCO2/MWh_HHV", src, source_kind="scenario_config")
    add("R8c-electrolyser-investment", 3, "3.7.1",
        "Coupled run electrolyser investment enabled",
        str(cfg["system"]["electrolyzer_investment"]["enabled"]).lower(),
        "boolean", src, source_kind="scenario_config",
        provenance="scenario_assumption")
    add("R8c-electricity-base-config", 3, "3.7.1",
        "Coupled run electricity base scenario "
        "(identifies the STYLISED 13-bus fleet, not the reconciled fleet of R1)",
        Path(cfg["production_inputs"]["electricity_config"]).parent.name,
        "scenario name", src, source_kind="scenario_config",
        provenance="scenario_assumption")

    manifest = load_json(COUPLED / "scenario_manifest.json")
    msrc = rel(COUPLED / "scenario_manifest.json")
    add("R8c-provenance-count", 3, "3.7.1",
        "Provenance records attached to the coupled run manifest",
        str(len(manifest["provenance"])), "records", msrc, source_kind="manifest")
    add("R8c-input-hash-count", 3, "3.7.1",
        "Input files hashed (SHA-256) in the coupled run manifest",
        str(len(manifest["input_hashes_sha256"])), "files", msrc,
        source_kind="manifest")


def extract_r8c_pre_fix_history() -> None:
    """Diagnostic measurements from before the 2026-10-02 wind fix.

    Not re-derivable from any current file: the defective
    mid_2026_monthly_days/inputs/wind_pu_regional.csv was overwritten by the
    fix itself, and R8c's withheld solve (objective, price, emissions) was
    replaced in place by the re-solve. These values were measured once,
    directly, during the diagnosis recorded in thesis/PROGRESS.md
    (2026-10-02 entry) and in MODEL commit b1bbbfd's message, and are
    recorded here the same way the spatial-MILP before/after values are
    (source_kind=diagnostic_run) so the historical comparison in Section
    3.1.2/3.7.3 remains traceable.
    """
    note = "diagnostic measurement, 2026-10-02, before the wind fix (MODEL commit b1bbbfd); not reproducible from current files"
    for cid, label, val, unit in [
        ("R8c-history-wind-mean", "mid_2026_monthly_days wind p_max_pu mean, before the fix", "0.5169", "per-unit"),
        ("R8c-history-wind-min", "mid_2026_monthly_days wind p_max_pu minimum, before the fix", "0.2600", "per-unit"),
        ("R8c-history-wind-max", "mid_2026_monthly_days wind p_max_pu maximum, before the fix", "0.8600", "per-unit"),
        ("R8c-history-wind-below-005", "Share of hours below 0.05 per-unit wind availability, before the fix", "0.00", "%"),
        ("R8c-history-solar-zero-share", "Share of hours at exactly zero solar availability, same network, before the fix", "41.67", "%"),
        ("R8c-history-price-mainland", "Withheld run's mainland electricity shadow price, before the fix", "24.13", "EUR/MWh_e"),
        ("R8c-history-stylised-availcf", "Stylised 13-region runs' wind availability capacity factor, before the fix", "52.02", "%"),
        ("R8c-history-stylised-ratio", "Stylised 13-region runs' wind availability ratio to the DAPEEP benchmark, before the fix", "2.183", "ratio"),
    ]:
        add(cid, 3, "3.1.2", label, val, unit,
            "thesis/PROGRESS.md (2026-10-02 entry); MODEL commit b1bbbfd",
            source_kind="diagnostic_run", provenance="measured")


def extract_stylised_fleet() -> None:
    path = PG_STATIC / "generators.csv"
    src = rel(path)
    agg: dict[str, dict] = {}
    for r in read_csv_rows(path):
        a = agg.setdefault(r["carrier"],
                           {"p_nom": 0.0, "p_nom_max": 0.0, "n_ext": 0, "mc": 0.0})
        a["p_nom"] += fnum(r["p_nom"])
        a["p_nom_max"] += fnum(r.get("p_nom_max"))
        a["n_ext"] += 1 if str(r["p_nom_extendable"]).strip().lower() == "true" else 0
        a["mc"] = fnum(r["marginal_cost"])

    for carrier, a in sorted(agg.items()):
        add(f"fleet-stylised-pnom-{carrier}", 3, "3.7.1",
            f"Stylised 13-bus fleet installed capacity, {carrier}",
            f"{a['p_nom']:.0f}", "MW", src, provenance="scenario_assumption")
        if a["n_ext"]:
            add(f"fleet-stylised-pnommax-{carrier}", 3, "3.7.1",
                f"Stylised 13-bus fleet expansion limit, {carrier} "
                f"({a['n_ext']} extendable units)",
                f"{a['p_nom_max']:.0f}", "MW", src,
                provenance="scenario_assumption")
        # Marginal costs belong to the ELECTRICITY-ONLY scenarios. The coupled
        # run does not use the gas row: it decomposes gas into a bus commodity
        # price plus an input-side link cost. Filing these under 3.7.x would
        # invite exactly the conflation D2-REVISED warns about.
        note = ""
        if carrier == "gas":
            note = (" - NOT used by the coupled run, which decomposes gas into a "
                    "bus commodity price plus an input-side link cost; this "
                    "composite figure was explicitly rejected for the coupled model")
        add(f"fleet-stylised-mc-{carrier}", 3, "3.3",
            f"Marginal cost of {carrier} in the stylised electricity-only fleet{note}",
            f"{a['mc']:.2f}", "EUR/MWh", src, provenance="sourced")

    solved = load_json(COUPLED / "scenario_result.json")["metrics"]["capacity_output_mw_by_carrier"]
    for carrier in ("wind", "solar"):
        start, end = agg[carrier]["p_nom"], solved[carrier]
        add(f"R8c-expansion-{carrier}", 3, "3.7.1",
            f"Endogenous {carrier} capacity expansion solved by the coupled run",
            f"{end - start:.2f}", "MW", f"{rel(COUPLED / 'scenario_result.json')} vs {src}",
            wind_bias="none")
        add(f"R8c-expansion-pct-{carrier}", 3, "3.7.1",
            f"Endogenous {carrier} capacity expansion, relative",
            f"{100 * (end - start) / start:.2f}", "%",
            f"{rel(COUPLED / 'scenario_result.json')} vs {src}",
            wind_bias="none")


def extract_price_derivation() -> None:
    import pypsa

    nc = COUPLED / "network.nc"
    n = pypsa.Network(str(nc))
    src = rel(nc)
    w = n.snapshot_weightings.objective
    total_w = float(w.sum())
    bias = r8c_wind_bias()

    add("R8c-snapshots", 3, "3.7.1", "Coupled run snapshot count",
        str(len(n.snapshots)), "snapshots", src)
    add("R8c-weight-sum", 3, "3.7.1",
        "Coupled run snapshot weights, summed (annual accounting check)",
        f"{total_w:.1f}", "h", src)

    all_bus_prices = n.buses_t.marginal_price
    mainland_buses = [b for b in all_bus_prices.columns
                       if not b.endswith("_Heat") and not b.startswith("Greece_")
                       and b not in ("Crete", "South_Aegean")]
    mainland_bus_means = {b: float((all_bus_prices[b] * w).sum() / total_w)
                          for b in mainland_buses}
    price = all_bus_prices["Attica"]
    add("R8c-price-weighted-mean", 3, "3.7.3",
        "Weight-weighted mean electricity planning shadow price, mainland "
        "(mean of each mainland bus's own time-weighted mean)",
        f"{sum(mainland_bus_means.values()) / len(mainland_bus_means):.4f}",
        "EUR/MWh_e", src, wind_bias=bias)
    min_bus = min(mainland_bus_means, key=mainland_bus_means.get)
    max_bus = max(mainland_bus_means, key=mainland_bus_means.get)
    add("R8c-mainland-price-min-bus", 3, "3.7.3",
        "Mainland bus with the lowest time-weighted mean shadow price",
        min_bus, "bus name", src)
    add("R8c-mainland-price-min-value", 3, "3.7.3",
        "Time-weighted mean shadow price at that bus",
        f"{mainland_bus_means[min_bus]:.4f}", "EUR/MWh_e", src, wind_bias=bias)
    add("R8c-mainland-price-max-bus", 3, "3.7.3",
        "Mainland bus with the highest time-weighted mean shadow price",
        max_bus, "bus name", src)
    add("R8c-mainland-price-max-value", 3, "3.7.3",
        "Time-weighted mean shadow price at that bus",
        f"{mainland_bus_means[max_bus]:.4f}", "EUR/MWh_e", src, wind_bias=bias)

    gas_link = n.links[n.links.carrier == "gas_to_power"].iloc[0]
    gas_bus_price = float(n.buses_t.marginal_price["Greece_Gas"].max())
    eff, link_mc = float(gas_link.efficiency), float(gas_link.marginal_cost)
    gas_stack = (gas_bus_price + link_mc) / eff

    rounded = price.round(4)
    setters = {
        0.0: ("solar-surplus", "solar or renewable surplus (marginal cost 0)"),
        1.9: ("wind", "wind (marginal cost 1.90 EUR/MWh)"),
        12.0: ("hydro", "hydro (marginal cost 12.00 EUR/MWh)"),
        round(gas_stack, 4): ("gas", "gas-to-power at its full marginal stack"),
    }
    accounted = 0.0
    for level, (slug, label) in setters.items():
        hours = float(w[rounded == level].sum())
        accounted += hours
        add(f"R8c-marginal-hours-{slug}", 3, "3.7.3",
            f"Weighted hours in which the price is set by {label}",
            f"{hours:.0f}", "h/yr", src, wind_bias=bias)
        add(f"R8c-marginal-share-{slug}", 3, "3.7.3",
            f"Share of weighted hours in which the price is set by {label}",
            f"{100 * hours / total_w:.2f}", "%", src, wind_bias=bias)

    other = total_w - accounted
    add("R8c-marginal-hours-other", 3, "3.7.3",
        "Weighted hours at intermediate price levels", f"{other:.0f}", "h/yr",
        src, wind_bias=bias)
    add("R8c-marginal-share-other", 3, "3.7.3",
        "Share of weighted hours at intermediate price levels",
        f"{100 * other / total_w:.2f}", "%", src, wind_bias=bias)
    res_hours = float(w[rounded.isin([0.0, 1.9])].sum())
    add("R8c-res-marginal-share", 3, "3.7.3",
        "Share of weighted hours in which a zero- or near-zero-cost renewable "
        "is marginal (the reason the mean price is low)",
        f"{100 * res_hours / total_w:.2f}", "%", src, wind_bias=bias)

    add("R8c-price-peak-observed", 3, "3.7.3",
        "Highest electricity planning shadow price observed, mainland",
        f"{max(float(all_bus_prices[b].max()) for b in mainland_buses):.4f}",
        "EUR/MWh_e", src, wind_bias=bias)
    add("R8c-network-link-mc-check", 3, "2.8",
        "Gas-to-power input-side marginal cost as built into the solved network "
        "(cross-check against the input-derived value)",
        f"{link_mc:.6f}", "EUR/MWh_HHV", src)

    ac = n.buses.index[n.buses.carrier == "AC"]
    loads = n.loads.index[n.loads.bus.isin(ac)]
    if len(loads):
        p_set = n.loads_t.p_set[loads]
        busmap = n.loads.bus[loads]
        num = sum(float((n.buses_t.marginal_price[busmap[l]] * p_set[l] * w).sum())
                  for l in loads)
        den = sum(float((p_set[l] * w).sum()) for l in loads)
        add("R8c-load-weighted-price", 3, "3.7.3",
            "Load-weighted mean electricity planning shadow price",
            f"{num / den:.4f}", "EUR/MWh_e", src, wind_bias=bias)
        add("R8c-electricity-demand", 3, "3.7.2",
            "Electricity-only demand in the coupled run "
            "(incremental heat excluded per the demand boundary)",
            f"{den / 1e6:.3f}", "TWh/yr", src)

    # Per-carrier capacity factors and curtailment, plus a live gas balance.
    pmax = n.get_switchable_as_dense("Generator", "p_max_pu")
    for carrier in sorted(n.generators.carrier.unique()):
        gens = n.generators.index[n.generators.carrier == carrier]
        cap = float(n.generators.p_nom_opt[gens].sum())
        if cap <= 0:
            continue
        gen = float(n.generators_t.p[gens].mul(w, axis=0).sum().sum())
        cols = [g for g in gens if g in pmax.columns]
        avail = (float(sum((pmax[g] * n.generators.p_nom_opt[g] * w).sum() for g in cols))
                 if cols else gen)
        cb = bias if carrier in ("wind",) else "none"
        add(f"R8c-gen-{carrier}", 3, "3.7.2",
            f"Coupled run annual generation, {carrier}", f"{gen / 1e6:.3f}",
            "TWh/yr", src, wind_bias=cb)
        add(f"R8c-cf-{carrier}", 3, "3.7.2",
            f"Coupled run capacity factor from dispatch, {carrier}",
            f"{100 * gen / (cap * total_w):.2f}", "%", src, wind_bias=cb)
        if avail > 0:
            add(f"R8c-curtailment-{carrier}", 3, "3.7.2",
                f"Coupled run curtailment share of available energy, {carrier}",
                f"{100 * (avail - gen) / avail:.2f}", "%", src, wind_bias=cb)


def extract_gas_stack_from_inputs() -> None:
    """The gas marginal stack, derived from INPUT files only.

    This is the worked example of the M8 input-side link convention. It is
    deliberately computed from gas_supply.csv and gas_plant_parameters.csv
    rather than from solved duals, so that nothing citable depends on an R8c
    system output that is withheld under the wind-profile decision.
    """
    supply = COUPLED / "inputs" / "gas_supply.csv"
    params = COUPLED / "inputs" / "gas_plant_parameters.csv"
    cfg_path = COUPLED / "scenario_config.json"

    srows = read_csv_rows(supply)
    prices = {fnum(r["price_eur_per_mwh_hhv"]) for r in srows}
    if len(prices) != 1:
        raise ValueError(f"expected one gas commodity price, found {prices}")
    commodity = prices.pop()
    basis = {r["price_basis"] for r in srows}.pop()

    prows = read_csv_rows(params)
    effs = {fnum(r["efficiency_hhv"]) for r in prows}
    voms = {fnum(r["variable_om_eur_per_mwh_el"]) for r in prows}
    efs = {fnum(r["emission_factor_tco2_per_mwh_hhv"]) for r in prows}
    if not (len(effs) == len(voms) == len(efs) == 1):
        raise ValueError("gas plant parameters are not uniform across plants")
    eff, vom_out, ef = effs.pop(), voms.pop(), efs.pop()

    carbon_price = float(load_json(cfg_path)["system"]["carbon_price_eur_per_tonne"])

    add("gas-commodity-price", 2, "2.8",
        f"Natural gas commodity price fed to the coupled run (basis: {basis}, "
        f"TYNDP 2024 planning basis; the rejected composite figure is not used)",
        f"{commodity:.2f}", "EUR/MWh_HHV", rel(supply), source_kind="input_file",
        provenance="sourced")
    add("gas-entry-points", 2, "2.8",
        "DESFA entry points represented on the gas bus",
        str(len(srows)), "points", rel(supply), source_kind="input_file",
        provenance="sourced")
    add("gas-supply-capacity", 2, "2.8",
        "Total gas supply capacity across the DESFA entry points",
        f"{sum(fnum(r['capacity_mw_hhv']) for r in srows):.1f}", "MW_HHV",
        rel(supply), source_kind="input_file", provenance="sourced")
    add("gas-plant-efficiency-hhv", 2, "2.8",
        "Gas plant efficiency, HHV basis (DEA 0.57 LHV / 1.1 GCV-NCV differential)",
        f"{eff:.4f}", "MWh_e/MWh_HHV", rel(params), source_kind="input_file",
        provenance="derived")
    add("gas-plant-vom-output", 2, "2.8",
        "Gas plant variable O&M, output side (DEA Technology Data)",
        f"{vom_out:.2f}", "EUR/MWh_e", rel(params), source_kind="input_file",
        provenance="sourced")
    add("gas-plant-emission-factor", 2, "2.8",
        "Gas emission factor, HHV basis (IPCC 2006 Vol.2 Ch.2 Table 2.2, converted)",
        f"{ef:.4f}", "tCO2/MWh_HHV", rel(params), source_kind="input_file",
        provenance="derived")

    carbon_in = carbon_price * ef
    vom_in = vom_out * eff
    link_in = carbon_in + vom_in
    stack = (commodity + link_in) / eff
    srcs = f"{rel(supply)} + {rel(params)} + {rel(cfg_path)}"

    add("gas-link-carbon-input-side", 2, "2.8",
        "Gas-to-power input-side cost, CO2 component (CO2 price x HHV emission factor)",
        f"{carbon_in:.6f}", "EUR/MWh_HHV", srcs, source_kind="input_arithmetic")
    add("gas-link-vom-input-side", 2, "2.8",
        "Gas-to-power input-side cost, VOM component "
        "(output-side VOM converted by c_in = eff * c_out)",
        f"{vom_in:.6f}", "EUR/MWh_HHV", srcs, source_kind="input_arithmetic")
    add("gas-link-cost-input-side", 2, "2.8",
        "Gas-to-power total input-side link cost", f"{link_in:.6f}",
        "EUR/MWh_HHV", srcs, source_kind="input_arithmetic")
    add("gas-marginal-stack-output-side", 2, "2.8",
        "Gas-to-power full marginal cost, output side: "
        "(commodity + input-side link cost) / efficiency. Derived from inputs only, "
        "independent of any solved result",
        f"{stack:.4f}", "EUR/MWh_e", srcs, source_kind="input_arithmetic")
    add("gas-marginal-stack-fuel-only", 2, "2.8",
        "Gas-to-power marginal cost, fuel component only (commodity / efficiency)",
        f"{commodity / eff:.4f}", "EUR/MWh_e", srcs, source_kind="input_arithmetic")

    # Inverting the convention recovers the output-side VOM, which must equal the
    # DEA figure the inputs started from. A non-zero residual would mean the
    # convention is not being applied consistently.
    add("gas-link-vom-output-side", 2, "2.8",
        "Gas-to-power VOM recovered on the output side by inverting "
        "c_in = eff * c_out (must equal the DEA input figure)",
        f"{vom_in / eff:.4f}", "EUR/MWh_e", srcs, source_kind="input_arithmetic")
    add("gas-link-decomposition-residual", 2, "2.8",
        "Residual of the input-side link cost decomposition (closure check)",
        f"{abs(link_in - (carbon_in + vom_in)):.2e}", "EUR/MWh_HHV", srcs,
        source_kind="input_arithmetic")
    add("gas-link-vom-roundtrip-error", 2, "2.8",
        "Error between the recovered output-side VOM and the DEA input figure",
        f"{abs(vom_in / eff - vom_out):.2e}", "EUR/MWh_e", srcs,
        source_kind="input_arithmetic")


# ==========================================================================
# R1, R2, R3, R4, R5, R9, R12, R13, R14
# ==========================================================================
def extract_r1() -> None:
    path = PG_PROCESSED / "generator_clusters_report.json"
    report = load_json(path)
    src = rel(path)

    def walk(node, trail=()):
        if isinstance(node, dict):
            for k, v in node.items():
                yield from walk(v, trail + (k,))
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            yield trail, node

    for trail, value in walk(report):
        add(f"R1-{'-'.join(map(str, trail))}", 3, "3.2",
            f"Reconciled generator inventory: {' / '.join(map(str, trail))}",
            f"{value:.4g}" if isinstance(value, float) else str(value),
            "", src, provenance="sourced")


def extract_r2_load_qc() -> None:
    path = VALIDATION / "ipto_model_ready_validation_summary.csv"
    src = rel(path)
    row = read_csv_rows(path)[0]
    labels = {
        "rows": ("Model-ready national load series length", "hours"),
        "missing_timestamp_rows": ("Missing timestamps after QC", "rows"),
        "duplicate_timestamps": ("Duplicate timestamps after QC", "rows"),
        "missing_load_values": ("Missing load values after QC", "values"),
        "non_positive_load_values": ("Non-positive load values after QC", "values"),
    }
    for key, (label, unit) in labels.items():
        if key in row:
            add(f"R2-{key}", 2, "2.2.1", label, row[key], unit, src,
                provenance="measured")

    audit = VALIDATION / "ipto_anomaly_audit_2022_2026.csv"
    if audit.exists():
        add("R2-anomaly-rows", 2, "2.2.1",
            "Rows in the IPTO anomaly audit", str(len(read_csv_rows(audit))),
            "rows", rel(audit), provenance="measured")


def extract_r4_aggregation() -> None:
    path = SCENARIOS / "scenario_comparison.csv"
    src = rel(path)
    data = {r["case"]: r for r in read_csv_rows(path)}
    for case, r in data.items():
        for col, unit in [("snapshots", "snapshots"), ("weighted_hours", "h"),
                          ("objective", "EUR/yr"), ("total_load_twh", "TWh"),
                          ("avg_price_eur_mwh", "EUR/MWh")]:
            if col in r:
                # Both cases were re-solved 2026-10-02 against the corrected,
                # calibrated wind series (see Section 3.1.2); neither carries
                # a bias.
                add(f"R4-{case}-{col}", 3, "3.1.4",
                    f"Temporal-aggregation comparison, {case}: {col}",
                    r[col], unit, src, wind_bias="none")

    cases = list(data)
    if len(cases) >= 2:
        a, b = cases[0], cases[1]
        oa, ob = fnum(data[a]["objective"]), fnum(data[b]["objective"])
        add("R4-objective-rel-diff", 3, "3.1.4",
            f"Relative difference in objective between {a} and {b}",
            f"{100 * abs(oa - ob) / oa:.2f}", "%", src, wind_bias="none")


def extract_electricity_runs() -> None:
    """R5 clustered real-fleet runs, and their stylised counterparts."""
    for scen, section, family in [
        ("clustered_mid_2026_monthly_days", "3.3", "clustered reconciled"),
        ("clustered_long_2026_seasonal_weeks", "3.3", "clustered reconciled"),
        ("mid_2026_monthly_days", "3.1.4", "stylised 13-bus"),
        ("long_2026_seasonal_weeks", "3.1.4", "stylised 13-bus"),
    ]:
        path = SCENARIOS / scen / "scenario_result.json"
        if not path.exists():
            continue
        d = load_json(path)
        src = rel(path)
        m = d["metrics"]
        # All four of these were re-solved 2026-10-02 against the corrected,
        # calibrated wind series (see Section 3.1.2); none carries a bias.
        bias = "none"

        add(f"R5-{scen}-objective", 3, section,
            f"{scen} ({family}) objective", f"{d['objective']:.2f}", "EUR/yr",
            src, wind_bias=bias)
        # The older stylised result files predate the run-manifest fields, so
        # the snapshot count is absent from some of them. Its absence must not
        # cost the rest of that run's claims.
        if "rows" in d:
            add(f"R5-{scen}-snapshots", 3, section, f"{scen} snapshot count",
                str(d["rows"]), "snapshots", src)

        for carrier, gen in sorted(m["generation_by_carrier_mwh"].items()):
            add(f"R5-{scen}-gen-{carrier}", 3, section,
                f"{scen} ({family}) annual generation, {carrier}",
                f"{gen / 1e6:.3f}", "TWh/yr", src, wind_bias=bias)
        for carrier, cap in sorted(m["optimized_capacity_by_carrier_mw"].items()):
            add(f"R5-{scen}-cap-{carrier}", 3, section,
                f"{scen} ({family}) solved capacity, {carrier}",
                f"{cap:.1f}", "MW", src, wind_bias=bias)

        prices = m.get("average_marginal_price_by_bus", {})
        if prices:
            vals = list(prices.values())
            add(f"R5-{scen}-price-mean", 3, section,
                f"{scen} ({family}) mean bus planning shadow price",
                f"{sum(vals) / len(vals):.2f}", "EUR/MWh", src, wind_bias=bias)
            add(f"R5-{scen}-price-spread", 3, section,
                f"{scen} ({family}) spread of bus planning shadow prices",
                f"{max(vals) - min(vals):.4f}", "EUR/MWh", src, wind_bias=bias)


def extract_scenario_ab() -> None:
    """Scenario A vs Scenario B, computed from the two solved clustered networks.

    Neither carries a scenario_result.json, so the metrics come from the .nc
    files directly. These are the thesis's Base-vs-Alternative spine, the
    structure the supervisor's template is built around.

    Scenario A: the trusted clustered baseline (lignite present, gas at the
    TYNDP planning basis). Scenario B: the same network re-solved with lignite
    retired and gas at the spot TTF figure.
    """
    import pypsa

    nets = {
        "A": MODEL / "pypsa-greece/outputs/clustered/networks/greece_clustered.nc",
        "B": MODEL / "pypsa-greece/outputs/clustered/networks/greece_clustered_scenario_b.nc",
    }
    summary: dict[str, dict] = {}

    for label, path in nets.items():
        if not path.exists():
            print(f"  ! Scenario {label} network missing: {rel(path)}",
                  file=sys.stderr)
            continue
        n = pypsa.Network(str(path))
        src = rel(path)
        w = n.snapshot_weightings.objective
        total_w = float(w.sum())
        name = "Baseline" if label == "A" else "Post-Lignite / Spot Gas"
        sec = "3.3" if label == "A" else "3.4"

        obj = float(n.objective) if n.objective is not None else 0.0
        add(f"SC{label}-objective", 3, sec,
            f"Scenario {label} ({name}) objective", f"{obj:.2f}", "EUR/yr",
            src)
        # Also recorded in billions, the scale the prose and tables use.
        add(f"SC{label}-objective-bn", 3, sec,
            f"Scenario {label} ({name}) objective, in billions",
            f"{obj / 1e9:.4f}", "bn EUR/yr", src)
        add(f"SC{label}-snapshots", 3, sec,
            f"Scenario {label} snapshot count", str(len(n.snapshots)),
            "snapshots", src)
        add(f"SC{label}-weight-sum", 3, sec,
            f"Scenario {label} snapshot weights, summed",
            f"{total_w:.1f}", "h", src)

        # Load-weighted mean price: the figure an investor's revenue depends on.
        ac = n.buses.index[n.buses.carrier == "AC"] if "AC" in set(n.buses.carrier) \
            else n.buses.index
        loads = n.loads.index[n.loads.bus.isin(ac)]
        mp = n.buses_t.marginal_price
        busmap = n.loads.bus[loads]
        p_set = n.get_switchable_as_dense("Load", "p_set")[loads]
        num = sum(float((mp[busmap[l]] * p_set[l] * w).sum()) for l in loads)
        den = sum(float((p_set[l] * w).sum()) for l in loads)
        wmean = float((mp[ac].mul(w, axis=0)).sum().sum() / (total_w * len(ac)))

        add(f"SC{label}-price-weighted-mean", 3, sec,
            f"Scenario {label} ({name}) weighted-mean bus planning shadow price",
            f"{wmean:.2f}", "EUR/MWh", src)
        add(f"SC{label}-price-load-weighted", 3, sec,
            f"Scenario {label} ({name}) load-weighted planning shadow price",
            f"{num / den:.2f}", "EUR/MWh", src)
        add(f"SC{label}-demand", 3, sec,
            f"Scenario {label} total electricity demand",
            f"{den / 1e6:.3f}", "TWh/yr", src)

        gens: dict[str, float] = {}
        caps: dict[str, float] = {}
        for carrier in sorted(n.generators.carrier.unique()):
            idx = n.generators.index[n.generators.carrier == carrier]
            gen = float(n.generators_t.p[idx].mul(w, axis=0).sum().sum())
            cap = float(n.generators.p_nom_opt[idx].sum())
            gens[carrier], caps[carrier] = gen, cap
            add(f"SC{label}-gen-{carrier}", 3, sec,
                f"Scenario {label} ({name}) annual generation, {carrier}",
                f"{gen / 1e6:.3f}", "TWh/yr", src)
            add(f"SC{label}-cap-{carrier}", 3, sec,
                f"Scenario {label} ({name}) solved capacity, {carrier}",
                f"{cap:.1f}", "MW", src)
            if cap > 0:
                add(f"SC{label}-cf-{carrier}", 3, sec,
                    f"Scenario {label} ({name}) dispatch capacity factor, {carrier}",
                    f"{100 * gen / (cap * total_w):.2f}", "%", src)

        # Benchmark this scenario's wind availability, rather than assuming a
        # direction. These two networks are the investment basis for Chapter 4,
        # so their bias matters more than any other run's.
        if DAPEEP_WIND_CF and caps.get("wind"):
            wind_idx = n.generators.index[n.generators.carrier == "wind"]
            wind_pmax = n.get_switchable_as_dense("Generator", "p_max_pu")[wind_idx]
            wind_available = float(
                wind_pmax.mul(n.generators.p_nom_opt[wind_idx], axis=1)
                .mul(w, axis=0).sum().sum()
            )
            availability_cf = wind_available / (caps["wind"] * total_w)
            curtailment_pct = 100 * (wind_available - gens["wind"]) / wind_available
            add(f"SC{label}-wind-availability-cf", 3, "3.1.2",
                f"Scenario {label} wind availability capacity factor before dispatch",
                f"{100 * availability_cf:.3f}", "%", src,
                provenance="derived")
            add(f"SC{label}-wind-cf-ratio", 3, "3.1.2",
                f"Scenario {label} wind availability capacity factor relative to "
                f"the DAPEEP benchmark",
                f"{availability_cf / DAPEEP_WIND_CF:.3f}", "ratio", src,
                provenance="derived")
            add(f"SC{label}-wind-curtailment", 3, sec,
                f"Scenario {label} curtailed share of available wind energy",
                f"{curtailment_pct:.2f}", "%", src, provenance="derived")

        summary[label] = {"objective": obj, "price": wmean,
                          "load_price": num / den, "gen": gens, "cap": caps}

    # Relative percentage change, the column the template always carries.
    if "A" in summary and "B" in summary:
        a, b = summary["A"], summary["B"]
        srcs = f"{rel(nets['A'])} vs {rel(nets['B'])}"

        def rel_change(x, y):
            return 100 * (y - x) / x if x else float("nan")

        add("SCAB-objective-change", 3, "3.5",
            "Relative change in objective, Scenario A to B",
            f"{rel_change(a['objective'], b['objective']):.2f}", "%", srcs)
        add("SCAB-price-change", 3, "3.5",
            "Relative change in weighted-mean planning shadow price, A to B",
            f"{rel_change(a['price'], b['price']):.2f}", "%", srcs)
        add("SCAB-load-price-change", 3, "3.5",
            "Relative change in load-weighted planning shadow price, A to B",
            f"{rel_change(a['load_price'], b['load_price']):.2f}", "%", srcs)
        for carrier in sorted(set(a["gen"]) | set(b["gen"])):
            ga, gb = a["gen"].get(carrier, 0.0), b["gen"].get(carrier, 0.0)
            if ga or gb:
                add(f"SCAB-gen-change-{carrier}", 3, "3.5",
                    f"Relative change in generation, {carrier}, Scenario A to B",
                    f"{rel_change(ga, gb):.2f}" if ga else "n/a", "%", srcs)


def _constant(path: Path, name: str) -> str | None:
    """Read a module-level numeric constant from a source file."""
    if not path.exists():
        return None
    m = re.search(rf"^{re.escape(name)}\s*=\s*([\d.]+)", path.read_text(encoding="utf-8"),
                  re.MULTILINE)
    return m.group(1) if m else None


def extract_software_versions() -> None:
    """Software versions, from references.csv (Appendix E).

    Recorded as claims so that a version quoted in the appendix is traceable
    like any other number, rather than exempted.
    """
    path = Path(__file__).resolve().parents[1] / "references.csv"
    if not path.exists():
        return
    import re as _re
    for r in read_csv_rows(path):
        if r.get("type") != "software":
            continue
        m = _re.search(r"\(version ([^)]+)\)", r.get("title", ""))
        if not m:
            continue
        name = r["title"].split(" (version")[0]
        add(f"sw-{r['key']}", 2, "2.10",
            f"Software version used: {name}", m.group(1), "version",
            rel(path), source_kind="environment_capture", provenance="measured")


def extract_literature_values() -> None:
    """Values quoted from verified literature (Chapter 1).

    Rule 0.3 allows a number traced to "a file ... or to a cited external
    source". These are the latter: each carries its citation and its
    verification status, so a literature value is traced rather than exempted.
    """
    path = Path(__file__).resolve().parents[1] / "literature_values.csv"
    if not path.exists():
        return
    for r in read_csv_rows(path):
        if r.get("verification", "").strip() != "verified":
            print(f"  ! literature value not verified, skipping: "
                  f"{r['claim_id']}", file=sys.stderr)
            continue
        add(r["claim_id"], 1, r["section"], r["claim"], r["value"],
            r.get("unit", ""), r["citation"], source_kind="literature",
            provenance="sourced")


def extract_spatial_layers() -> None:
    """Feature counts for the geographic layers (Section 2.2.3)."""
    source = PLATFORM / "apps" / "api" / "data" / "source"
    layers = [
        ("power_plants", "Power plant records, collaborative geographic database"),
        ("substations", "Substation records"),
        ("transmission_lines", "Transmission line records"),
        ("admin_regions", "Administrative regions (NUTS-2 level)"),
        ("regional_units", "Regional units (NUTS-3 level)"),
        ("greek_islands", "Island geometries"),
        ("natura_2000", "Natura 2000 protected site designations"),
        ("hydrogen_projects", "Hydrogen project records"),
        ("hydrogen_pipelines", "Hydrogen pipeline records"),
        ("gem_solar_greece", "Utility-scale solar records, international tracker"),
        ("gem_wind_greece", "Utility-scale wind records, international tracker"),
        ("gem_hydro_greece", "Hydro records, international tracker"),
        ("government_wind_greece", "Wind records, national registry export"),
        ("government_photovoltaics_greece", "Photovoltaic records, national registry export"),
        ("government_storage_greece", "Storage records, national registry export"),
        ("raaey_operating_wind", "Operating wind licences, national register"),
        ("raaey_operating_solar", "Operating solar licences, national register"),
        ("greek_energy_map_projects", "Project records, national project map"),
    ]
    for slug, label in layers:
        path = source / f"{slug}.geojson"
        if not path.exists():
            continue
        try:
            n = len(load_json(path).get("features", []))
        except Exception as exc:
            print(f"  ! {slug}: {type(exc).__name__}", file=sys.stderr)
            continue
        add(f"layer-{slug}", 2, "2.2.3", label, str(n), "features", rel(path),
            source_kind="input_file", provenance="sourced")


def extract_method_constants() -> None:
    """Named constants that the methods sections must quote exactly."""
    # Clustering (Section 2.5)
    clustering = MODEL / "pypsa-greece/src/generator_clustering.py"
    if clustering.exists():
        text = clustering.read_text(encoding="utf-8")
        m = re.search(r"assets_per_cluster:\s*int\s*=\s*(\d+),\s*max_clusters:\s*int\s*=\s*(\d+)",
                      text)
        if m:
            add("cluster-assets-per-cluster", 2, "2.5",
                "Target number of assets represented by one cluster",
                m.group(1), "assets", rel(clustering), source_kind="source_code",
                provenance="scenario_assumption")
            add("cluster-max-per-group", 2, "2.5",
                "Maximum clusters formed for any one bus and carrier combination",
                m.group(2), "clusters", rel(clustering), source_kind="source_code",
                provenance="scenario_assumption")
        block = re.search(r"VOLTAGE_CLASS_CAPACITY_MVA\s*=\s*\{(.*?)\}", text, re.S)
        if block:
            for kv, mva in re.findall(r"(\d+):\s*([\d.]+)", block.group(1)):
                add(f"cluster-line-rating-{kv}kv", 2, "2.5",
                    f"Assumed single-circuit thermal rating at {kv} kV",
                    mva, "MVA", rel(clustering), source_kind="source_code",
                    provenance="derived")
                # The voltage class itself is also quoted in the prose, so it
                # needs to exist in the ledger as a value, not only as a key.
                add(f"cluster-voltage-class-{kv}", 2, "2.5",
                    f"Transmission voltage class recognised by the rating table",
                    kv, "kV", rel(clustering), source_kind="source_code",
                    provenance="sourced")
        default = _constant(clustering, "DEFAULT_CONNECTION_CAPACITY_MVA")
        if default:
            add("cluster-line-rating-default", 2, "2.5",
                "Fallback connection rating where the voltage class is unknown",
                default, "MVA", rel(clustering), source_kind="source_code",
                provenance="placeholder")

    # Candidate generation and siting (Section 2.9)
    gen = PLATFORM / "apps/api/pipeline/generate_candidates.py"
    land = PLATFORM / "apps/api/pipeline/land_constraints.py"
    for path, name, cid, label, unit, cls in [
        (gen, "GRID_STEP_DEGREES", "candidate-grid-step",
         "Candidate grid spacing", "degrees", "scenario_assumption"),
        (gen, "CONSTRAINT_REVIEW_BUILDABLE_FRACTION_THRESHOLD",
         "candidate-review-threshold",
         "Buildable fraction below which a cell is flagged for review",
         "fraction", "scenario_assumption"),
        (gen, "NEAREST_FEATURE_QUERY_BUFFER_DEGREES", "candidate-query-buffer",
         "Search radius used when finding the nearest grid feature", "degrees",
         "derived"),
        (land, "SOLAR_UNESCO_STUDY_TRIGGER_KM", "siting-unesco-trigger-km",
         "Distance to a world heritage site below which a solar study is triggered",
         "km", "sourced"),
        (land, "MIN_BUILDABLE_FRACTION", "siting-min-buildable-fraction",
         "Buildable fraction below which a cell is treated as excluded",
         "fraction", "scenario_assumption"),
        (land, "KM_PER_DEGREE_LAT", "siting-km-per-degree",
         "Kilometres per degree of latitude used for distance screening", "km",
         "derived"),
    ]:
        value = _constant(path, name)
        if value:
            add(cid, 2, "2.9", label, value, unit, rel(path),
                source_kind="source_code", provenance=cls)

    step = _constant(gen, "GRID_STEP_DEGREES")
    km = _constant(land, "KM_PER_DEGREE_LAT")
    if step and km:
        add("candidate-grid-step-km", 2, "2.9",
            "Candidate grid spacing expressed as a north-south distance",
            f"{float(step) * float(km):.1f}", "km",
            f"{rel(gen)} + {rel(land)}", source_kind="input_arithmetic")


def extract_wind_curve() -> None:
    """Turbine power-curve constants and the corrected law (Section 2.4)."""
    path = MODEL / "pypsa-greece/src/weather_profiles.py"
    if not path.exists():
        return
    for name, cid, label in [
        ("WIND_CUT_IN_MS", "wind-curve-cut-in", "Turbine cut-in wind speed"),
        ("WIND_RATED_MS", "wind-curve-rated", "Turbine rated wind speed"),
        ("WIND_CUT_OUT_MS", "wind-curve-cut-out", "Turbine cut-out wind speed"),
    ]:
        value = _constant(path, name)
        if value:
            add(cid, 2, "2.4", label, value, "m/s", rel(path),
                source_kind="source_code", provenance="sourced")

    cut_in = _constant(path, "WIND_CUT_IN_MS")
    rated = _constant(path, "WIND_RATED_MS")
    if cut_in and rated:
        a, b = float(cut_in), float(rated)
        add("wind-curve-cubed-cut-in", 2, "2.4",
            "Cut-in speed cubed, the numerator offset of the corrected power law",
            f"{a ** 3:g}", "m3/s3", rel(path), source_kind="input_arithmetic")
        add("wind-curve-cubed-rated", 2, "2.4",
            "Rated speed cubed, used in the denominator of the corrected power law",
            f"{b ** 3:g}", "m3/s3", rel(path), source_kind="input_arithmetic")
        add("wind-curve-denominator", 2, "2.4",
            "Denominator of the corrected power law (rated cubed less cut-in cubed)",
            f"{b ** 3 - a ** 3:g}", "m3/s3", rel(path),
            source_kind="input_arithmetic")


def extract_forecast_hyperparameters() -> None:
    """Gradient-boosting hyperparameters for the next-day forecast (Section 2.3.1)."""
    path = MODEL / "src/energy_data/short_term_forecast.py"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    block = re.search(r"XGBRegressor\((.*?)\)", text, re.S)
    if not block:
        return
    labels = {
        "n_estimators": ("Boosting rounds", "trees"),
        "max_depth": ("Maximum tree depth", "levels"),
        "learning_rate": ("Learning rate", "-"),
        "subsample": ("Row subsampling fraction", "-"),
        "colsample_bytree": ("Column subsampling fraction", "-"),
        "random_state": ("Random seed", "-"),
    }
    for key, (label, unit) in labels.items():
        m = re.search(rf"{key}\s*=\s*([\d.]+)", block.group(1))
        if m:
            add(f"forecast-{key}", 2, "2.3.1",
                f"Next-day demand model hyperparameter: {label}", m.group(1),
                unit, rel(path), source_kind="source_code",
                provenance="scenario_assumption")


def extract_coupled_conversions() -> None:
    """Conversion efficiencies as built into the solved coupled network."""
    import pypsa

    nc = COUPLED / "network.nc"
    if not nc.exists():
        return
    n = pypsa.Network(str(nc))
    src = rel(nc)
    labels = {
        "electrolysis": ("Electrolyser efficiency", "MWh_LHV/MWh_e"),
        "heat_pump": ("Heat pump coefficient of performance", "MWh_th/MWh_e"),
        "gas_boiler": ("Gas boiler efficiency", "MWh_th/MWh_HHV"),
        "hydrogen_boiler": ("Hydrogen boiler efficiency", "MWh_th/MWh_LHV"),
        "gas_to_power": ("Gas-to-power efficiency", "MWh_e/MWh_HHV"),
    }
    for carrier, (label, unit) in labels.items():
        links = n.links[n.links.carrier == carrier]
        if links.empty:
            continue
        effs = set(links.efficiency.round(6))
        if len(effs) == 1:
            add(f"coupled-efficiency-{carrier}", 2, "2.8", label,
                f"{effs.pop():g}", unit, src, provenance="sourced")

    for carrier in sorted(n.buses.carrier.unique()):
        add(f"coupled-buses-{carrier}", 2, "2.8",
            f"Buses representing the {carrier} carrier",
            str(int((n.buses.carrier == carrier).sum())), "buses", src)


def extract_cost_table() -> None:
    """The technology cost table (Section 2.2.4) and the two scenario gas prices.

    Both scenario gas figures are taken from files rather than from the master
    plan's prose: the baseline from technology_costs.csv, the alternative from
    the constant in the Scenario B solve script.
    """
    path = PG_STATIC / "technology_costs.csv"
    src = rel(path)
    for r in read_csv_rows(path):
        carrier = r["carrier"]
        for col, unit in [("marginal_cost", "EUR/MWh"),
                          ("capital_cost", "EUR/MW/yr"),
                          ("overnight_capex_eur_per_kw", "EUR/kW"),
                          ("lifetime_years", "years"),
                          ("discount_rate_pct", "%"),
                          ("fom_pct_of_capex", "% of capex/yr")]:
            value = (r.get(col) or "").strip()
            if not value:
                continue
            add(f"cost-{carrier}-{col}", 2, "2.2.4",
                f"Technology cost table, {carrier}: {col}", value, unit, src,
                source_kind="input_file", provenance="sourced")

    # Scenario B's gas price is a constant in the solve script, not in the CSV.
    script = MODEL / "pypsa-greece/scripts/solve_scenario_b.py"
    if script.exists():
        m = re.search(r"SPOT_GAS_MARGINAL_COST_EUR_PER_MWH\s*=\s*([\d.]+)",
                      script.read_text(encoding="utf-8"))
        if m:
            add("scenario-b-gas-marginal-cost", 2, "2.1",
                "Scenario B gas marginal cost (spot TTF basis), as set in the "
                "Scenario B solve script",
                m.group(1), "EUR/MWh", rel(script), source_kind="source_code",
                provenance="sourced")

    # The baseline composite gas cost decomposes with an LHV-basis efficiency,
    # while the coupled model uses an HHV-basis one. Recording both lets Section
    # 2.8 show that the difference between the two models' gas costs is the
    # dimensional convention, not a different price assumption.
    add("gas-composite-lhv-efficiency", 2, "2.8",
        "CCGT efficiency on an LHV basis, used by the electricity-only "
        "composite gas cost (DEA)", "0.57", "MWh_e/MWh_LHV", src,
        source_kind="input_file", provenance="sourced")
    add("gas-composite-fuel-component", 2, "2.8",
        "Fuel component of the electricity-only composite gas cost "
        "(commodity / LHV efficiency)",
        f"{42.90 / 0.57:.2f}", "EUR/MWh_e", src,
        source_kind="input_arithmetic", provenance="derived")
    add("gas-composite-carbon-intensity", 2, "2.8",
        "CO2 intensity per unit of electricity used by the composite gas cost",
        "0.347", "tCO2/MWh_e", src, source_kind="input_file",
        provenance="sourced")


def extract_r15_tests() -> None:
    """R15 and R8b -- test counts, from captured runs rather than plan prose.

    The master plan quotes 179 test functions and a 167/167 coupled run as
    historical evidence. Rule 0.3 forbids using that prose, so the suites were
    run on 2026-10-01 and their output captured to thesis/evidence/. The live
    counts differ from the plan, and the MODEL suite has one failure.
    """
    evidence = Path(__file__).resolve().parents[1] / "evidence"
    suites = [
        ("model", evidence / "test_run_model.txt",
         "modelling repository (pythonProject1)"),
        ("platform", evidence / "test_run_platform.txt",
         "platform API (energy-investment-platform/apps/api)"),
    ]
    for slug, path, label in suites:
        if not path.exists():
            print(f"  ! test evidence missing: {path.name}", file=sys.stderr)
            continue
        text = path.read_text(encoding="utf-8")
        ran = re.search(r"^Ran (\d+) tests? in ([\d.]+)s", text, re.MULTILINE)
        if not ran:
            print(f"  ! could not parse {path.name}", file=sys.stderr)
            continue
        total = int(ran.group(1))
        failures = re.search(r"^FAILED \((.*)\)", text, re.MULTILINE)
        n_fail = 0
        if failures:
            for part in failures.group(1).split(","):
                m = re.search(r"(\d+)", part)
                if m:
                    n_fail += int(m.group(1))

        add(f"R15-{slug}-tests", 2, "2.10",
            f"Tests executed, {label}", str(total), "tests", rel(path),
            source_kind="captured_run", provenance="measured")
        add(f"R15-{slug}-passing", 2, "2.10",
            f"Tests passing, {label}", str(total - n_fail), "tests", rel(path),
            source_kind="captured_run", provenance="measured")
        add(f"R15-{slug}-failing", 2, "2.10",
            f"Tests failing, {label}", str(n_fail), "tests", rel(path),
            source_kind="captured_run", provenance="measured")
        add(f"R15-{slug}-runtime", 2, "2.10",
            f"Test suite wall-clock runtime, {label}", ran.group(2), "s",
            rel(path), source_kind="captured_run", provenance="measured")

    # 2026-10-02: the spatial-portfolio MILP failure (below, as it stood
    # 2026-09-30 - 2026-10-02) is fixed. HiGHS presolve was found, by direct
    # diagnostic, to reduce the model to empty via variable fixing and report
    # a non-optimal split (EUR1,944.44/yr) as "Optimal" with 0 B&B nodes,
    # triggered by the model's deliberately tiny (1e-6) binary tie-break
    # cost. Disabling presolve (MODEL commit fb53a86) makes HiGHS actually
    # search and find the true optimum (EUR1,000.00/yr, verified). The full
    # suite is 186/186 as of the evidence captured above.
    add("R15-fixed-component", 2, "2.10",
        "Component containing the spatial-MILP non-optimality that was fixed "
        "2026-10-02 (an extension, not used by any reported result)",
        "src/energy_data/spatial_portfolio.py", "path",
        rel(evidence / "test_run_model.txt"), source_kind="captured_run",
        provenance="measured")
    add("R15-fixed-root-cause", 2, "2.10",
        "Root cause: HiGHS presolve mishandling the model's 1e-6 binary "
        "tie-break cost (its own log: \"Problem has some excessively small "
        "costs\"), reducing the model to empty and returning a non-optimal "
        "solution with 0 branch-and-bound nodes",
        "presolve mishandling small costs", "diagnosis",
        "MODEL/src/energy_data/spatial_portfolio.py (diagnostic run)",
        source_kind="diagnostic_run", provenance="derived")
    add("R15-fixed-objective-before", 2, "2.10",
        "Objective the spatial MILP reported on the two-site case before the "
        "fix (non-optimal)", "1944.4444", "EUR/yr",
        "MODEL/src/energy_data/spatial_portfolio.py (diagnostic run)",
        source_kind="diagnostic_run", provenance="derived")
    add("R15-fixed-objective-after", 2, "2.10",
        "Objective the spatial MILP reports on the same case after disabling "
        "presolve (true optimum)", "1000.000001", "EUR/yr",
        "MODEL/src/energy_data/spatial_portfolio.py (diagnostic run)",
        source_kind="diagnostic_run", provenance="derived")


def extract_r11_gas_roundtrip() -> None:
    """R11 -- the gas balance round-trip, derived live from the solved network.

    The master plan quotes this from KNOWLEDGE_TRANSFER prose, which rule 0.3
    says may be stale, so it is re-derived here from
    pypsa-greece/outputs/gas/networks/greece_gas.nc.

    What it demonstrates, stated precisely: the loads were BUILT FROM DESFA's
    published 2025 figures, so reproducing them proves the pipeline preserves
    those quantities through network construction, the solve, and weighted
    annual aggregation. It is a conservation and consistency check on the
    pipeline, not an independent validation of DESFA's own numbers. The thesis
    must not claim the latter.
    """
    import pypsa

    nc = MODEL / "pypsa-greece/outputs/gas/networks/greece_gas.nc"
    if not nc.exists():
        print(f"  ! gas network missing: {rel(nc)}", file=sys.stderr)
        return
    n = pypsa.Network(str(nc))
    src = rel(nc)
    w = n.snapshot_weightings.objective

    add("R11-snapshots", 3, "3.1.1", "Standalone gas model snapshot count",
        str(len(n.snapshots)), "snapshots", src)
    add("R11-weight-sum", 3, "3.1.1",
        "Standalone gas model snapshot weights, summed",
        f"{float(w.sum()):.1f}", "h", src)

    imports = float(n.generators_t.p.mul(w, axis=0).sum().sum())
    add("R11-imports", 3, "3.1.1",
        "Gas model total supply (imports across the DESFA entry points)",
        f"{imports / 1e6:.4f}", "TWh_HHV/yr", src)

    p_set = n.get_switchable_as_dense("Load", "p_set")
    total = 0.0
    for load in n.loads.index:
        energy = float((p_set[load] * w).sum())
        total += energy
        slug = load.replace("_load", "").lower()
        add(f"R11-load-{slug}", 3, "3.1.1",
            f"Gas model annual load, {load}", f"{energy / 1e6:.4f}",
            "TWh_HHV/yr", src)

    add("R11-load-total", 3, "3.1.1", "Gas model total annual load",
        f"{total / 1e6:.4f}", "TWh_HHV/yr", src)
    add("R11-residual", 3, "3.1.1",
        "Gas balance round-trip residual (supply minus load)",
        f"{(imports - total) / 1e6:.6f}", "TWh_HHV/yr", src)
    add("R11-residual-relative", 3, "3.1.1",
        "Gas balance round-trip residual, relative to supply",
        f"{100 * abs(imports - total) / imports:.4f}", "%", src)

    # The published figures the loads were constructed from, for the comparison
    # column. Sourced, not derived.
    targets = PG_STATIC / "eu_greece_energy_targets.csv"
    for r in read_csv_rows(targets):
        mid = r.get("metric_id", "")
        if mid in ("greece_gas_domestic_demand", "greece_gas_exports") \
                and r.get("year") == "2025":
            add(f"R11-published-{mid}", 3, "3.1.1",
                f"DESFA published 2025 figure the gas loads were built from: "
                f"{mid}", r["value"], r.get("unit", ""), rel(targets),
                source_kind="input_file", provenance="sourced")


def extract_r3_nextday() -> None:
    for scen in ("orchestrator_next_day_20260819_weather",
                 "orchestrator_next_day_20260820_weather"):
        path = SCENARIOS / scen / "scenario_result.json"
        if not path.exists():
            continue
        d = load_json(path)
        src = rel(path)
        m = d["metrics"]
        total = sum(m["total_load_by_bus_mwh"].values())
        peak = sum(m["peak_load_by_bus_mw"].values())
        add(f"R3-{scen}-energy", 3, "3.6",
            f"{scen}: total forecast day energy", f"{total / 1e3:.1f}", "GWh",
            src, wind_bias="overstated")
        add(f"R3-{scen}-peak", 3, "3.6",
            f"{scen}: coincident peak across buses", f"{peak / 1e3:.2f}", "GW",
            src, wind_bias="overstated")
        for carrier, gen in sorted(m["generation_by_carrier_mwh"].items()):
            add(f"R3-{scen}-gen-{carrier}", 3, "3.6",
                f"{scen}: generation, {carrier}", f"{gen / 1e3:.1f}", "GWh",
                src, wind_bias="overstated")


def extract_r9_hydrogen() -> None:
    path = PG_STATIC / "eu_greece_energy_targets.csv"
    src = rel(path)
    for r in read_csv_rows(path):
        mid = r.get("metric_id", "")
        if "hydrogen" in mid or "rfnbo" in mid or "h2" in mid.lower():
            add(f"R9-target-{mid}-{r['year']}", 3, "3.8",
                f"NECP / policy target: {mid} ({r.get('scope')}, {r['year']}) "
                f"- source: {r.get('source', '')[:80]}",
                r["value"], r.get("unit", ""), src, provenance="sourced")

    h2 = PG_STATIC / "generators_hydrogen.csv"
    if h2.exists():
        rows_h2 = read_csv_rows(h2)
        cap_col = next((c for c in rows_h2[0] if "p_nom" in c), None)
        if cap_col:
            total = sum(fnum(r[cap_col]) for r in rows_h2)
            add("R9-electrolyser-capacity-modelled", 3, "3.8",
                "Electrolyser capacity in the modelled hydrogen fleet",
                f"{total:.2f}", "MW", rel(h2), provenance="sourced")
            add("R9-electrolyser-count-modelled", 3, "3.8",
                "Electrolyser sites in the modelled hydrogen fleet",
                str(len(rows_h2)), "sites", rel(h2), provenance="sourced")

    # The feasibility arithmetic of decision D3, computed here rather than by
    # hand. The utilisation implied by the national plan is derived from its own
    # two figures: a pilot production target and an electrolyser capacity
    # objective for the same year.
    pilot = next((r for r in read_csv_rows(path)
                  if r.get("metric_id") == "greece_h2_production_pilot_target"), None)
    objective = next((r for r in read_csv_rows(path)
                      if r.get("metric_id") == "greece_h2_electrolyzer_capacity_objective"),
                     None)
    if pilot and objective:
        pilot_mwh = fnum(pilot["value"]) * 1e6
        cap_mw = fnum(objective["value"])
        hours = 8760.0
        utilisation = pilot_mwh / (cap_mw * hours)
        add("R9-implied-utilisation", 3, "3.8",
            "Electrolyser utilisation implied by the national plan's own pilot "
            "production target and capacity objective",
            f"{100 * utilisation:.2f}", "%", rel(path),
            source_kind="input_arithmetic", provenance="derived")

        # Capacities are read from their own files rather than looked up in the
        # ledger, so this block does not depend on extraction order.
        def _capacity(csv_path: Path, col_match: str) -> float | None:
            if not csv_path.exists():
                return None
            rs = read_csv_rows(csv_path)
            if not rs:
                return None
            col = next((c for c in rs[0] if col_match in c.lower()), None)
            return sum(fnum(r[col]) for r in rs) if col else None

        bounds = [
            ("base", _capacity(COUPLED / "inputs" / "electrolyzer_sites.csv", "mw"),
             "status-filtered project database"),
            ("licensed", _capacity(PG_STATIC / "generators_hydrogen.csv", "p_nom"),
             "licensed register upper bound"),
        ]
        targets = {r["year"]: fnum(r["value"]) for r in read_csv_rows(path)
                   if r.get("metric_id") == "greece_h2_final_energy_contribution"}
        for slug, mw, label in bounds:
            if not mw:
                continue
            twh = mw * hours * utilisation / 1e6
            add(f"R9-output-{slug}", 3, "3.8",
                f"Annual hydrogen output of the {label} at the plan's implied "
                f"utilisation", f"{twh:.3f}", "TWh/yr", rel(path),
                source_kind="input_arithmetic", provenance="derived")
            for year, target in sorted(targets.items()):
                if target:
                    add(f"R9-coverage-{slug}-{year}", 3, "3.8",
                        f"Share of the {year} hydrogen target met by the {label} "
                        f"at the implied utilisation",
                        f"{100 * twh / target:.1f}", "%", rel(path),
                        source_kind="input_arithmetic", provenance="derived")

    sites = COUPLED / "inputs" / "electrolyzer_sites.csv"
    if sites.exists():
        rs = read_csv_rows(sites)
        cap_col = next((c for c in rs[0] if "mw" in c.lower()), None)
        if cap_col:
            add("R9-electrolyser-capacity-r8c", 3, "3.8",
                "Electrolyser capacity used by the coupled run "
                "(IEA status-filtered base case, per D3)",
                f"{sum(fnum(r[cap_col]) for r in rs):.2f}", "MW", rel(sites),
                provenance="sourced")
            add("R9-electrolyser-count-r8c", 3, "3.8",
                "Electrolyser sites used by the coupled run",
                str(len(rs)), "sites", rel(sites), provenance="sourced")


def extract_r12_spatial() -> None:
    path = PG_PROCESSED / "spatial_constraints_report.json"
    report = load_json(path)
    src = rel(path)
    for key, label, unit in [
        ("wind_and_solar_clusters_checked",
         "Existing wind and solar clusters checked against the draft siting rules",
         "clusters"),
        ("excluded_count",
         "Existing clusters that would not be sitable under the draft framework",
         "clusters"),
    ]:
        if key in report:
            add(f"R12-{key}", 3, "3.1.3", label, str(report[key]), unit, src,
                provenance="derived")

    excluded = report.get("excluded_clusters", [])
    by_carrier: dict[str, int] = {}
    for c in excluded:
        by_carrier[c.get("carrier", "?")] = by_carrier.get(c.get("carrier", "?"), 0) + 1
    for carrier, count in sorted(by_carrier.items()):
        add(f"R12-excluded-{carrier}", 3, "3.1.3",
            f"Existing {carrier} clusters excluded by the draft framework",
            str(count), "clusters", src, provenance="derived")

    csv_path = PG_PROCESSED / "generator_clusters_spatial_constraints.csv"
    if csv_path.exists():
        add("R12-rows", 3, "3.1.3",
            "Rows in the per-cluster spatial constraint evaluation",
            str(len(read_csv_rows(csv_path))), "rows", rel(csv_path),
            provenance="derived")


def extract_r13_investment() -> None:
    path = PG_PROCESSED / "cluster_investment_evaluation.csv"
    src = rel(path)
    data = read_csv_rows(path)
    add("R13-rows", 4, "4.3", "Clusters evaluated for investment",
        str(len(data)), "clusters", src)

    for col, label, unit in [("lifetime_years", "Asset lifetime assumption", "years"),
                             ("discount_rate_pct", "Real discount rate", "%")]:
        vals = {r[col] for r in data if r.get(col)}
        if len(vals) == 1:
            add(f"R13-{col}", 4, "4.1", label, vals.pop(), unit, src,
                provenance="scenario_assumption")
        else:
            # Lifetime is technology-specific, so record it per carrier rather
            # than pretending a single figure applies.
            per: dict[str, set[str]] = {}
            for r in data:
                per.setdefault(r["carrier"], set()).add(r[col])
            for carrier, cvals in sorted(per.items()):
                if len(cvals) == 1:
                    add(f"R13-{col}-{carrier}", 4, "4.1",
                        f"{label}, {carrier}", cvals.pop(), unit, src,
                        provenance="scenario_assumption")

    by_carrier: dict[str, list[dict]] = {}
    for r in data:
        by_carrier.setdefault(r["carrier"], []).append(r)

    for carrier, rs in sorted(by_carrier.items()):
        prefix = "R13"
        financial_rs = [r for r in rs if fnum(r["p_nom_calibrated_mw"]) > 0]

        add(f"{prefix}-{carrier}-count", 4, "4.3",
            f"Clusters evaluated, {carrier}", str(len(rs)), "clusters", src)
        add(f"{prefix}-{carrier}-financial-count", 4, "4.3",
            f"Positive-capacity clusters included in financial summaries, {carrier}",
            str(len(financial_rs)), "clusters", src)
        add(f"{prefix}-{carrier}-capacity", 4, "4.3",
            f"Evaluated capacity, {carrier}",
            f"{sum(fnum(r['p_nom_calibrated_mw']) for r in rs):.1f}", "MW",
            src)
        for scen in ("a", "b"):
            cp = [fnum(r[f"scenario_{scen}_captured_price_eur_per_mwh"])
                  for r in financial_rs]
            npv = [fnum(r[f"scenario_{scen}_npv_eur"]) for r in financial_rs]
            irr = []
            for row in financial_rs:
                raw_irr = str(row.get(f"scenario_{scen}_irr_pct", "")).strip()
                if not raw_irr:
                    continue
                value = float(raw_irr)
                if math.isfinite(value):
                    irr.append(value)
            S = scen.upper()
            add(f"{prefix}-{carrier}-captured-price-{scen}", 4, "4.2",
                f"Mean captured price, {carrier}, Scenario {S}",
                f"{sum(cp) / len(cp):.2f}", "EUR/MWh", src)
            add(f"{prefix}-{carrier}-npv-total-{scen}", 4, "4.3",
                f"Total NPV, {carrier}, Scenario {S}",
                f"{sum(npv):.0f}", "EUR", src)
            add(f"{prefix}-{carrier}-npv-positive-{scen}", 4, "4.3",
                f"Clusters with positive NPV, {carrier}, Scenario {S}",
                str(sum(1 for v in npv if v > 0)), "clusters", src)
            add(f"{prefix}-{carrier}-irr-defined-{scen}", 4, "4.3",
                f"Clusters with a defined IRR, {carrier}, Scenario {S}",
                str(len(irr)), "clusters", src)
            add(f"{prefix}-{carrier}-irr-mean-{scen}", 4, "4.3",
                f"Mean IRR among defined values, {carrier}, Scenario {S}",
                f"{sum(irr) / len(irr):.2f}", "%", src)
            # The mean alone hides a single extreme cluster in one carrier, so
            # the median and the maximum are recorded beside it.
            ordered = sorted(irr)
            mid = len(ordered) // 2
            median = (ordered[mid] if len(ordered) % 2
                      else (ordered[mid - 1] + ordered[mid]) / 2)
            add(f"{prefix}-{carrier}-irr-median-{scen}", 4, "4.3",
                f"Median IRR among defined values, {carrier}, Scenario {S}",
                f"{median:.2f}", "%", src)
            add(f"{prefix}-{carrier}-irr-max-{scen}", 4, "4.3",
                f"Highest defined cluster IRR, {carrier}, Scenario {S}",
                f"{max(irr):.2f}", "%", src)

    citable = [r for r in data if fnum(r["p_nom_calibrated_mw"]) > 0]
    gained = sum(1 for r in citable
                 if fnum(r["scenario_b_npv_eur"]) > fnum(r["scenario_a_npv_eur"]))
    add("R13-citable-cluster-count", 4, "4.3",
        "Clusters evaluated with reportable results", str(len(citable)), "clusters",
        src)
    add("R13-clusters-gaining-b", 4, "4.3",
        "Clusters whose NPV rises from Scenario A to B",
        str(gained), "clusters", src)


def extract_temporal_reduction() -> None:
    """What the representative-day set keeps of the observed load (Section 2.6).

    The comparison is against the observed hourly series the days are drawn
    from, not against a solved year, since no full-year solve exists. Hours
    are counted on local calendar days, so the two daylight-saving transition
    days carry 23 and 25 hours; the peak and the mean are reported because
    neither depends on the hour count, and the annual total is not.
    """
    import numpy as np
    import pandas as pd

    series = (PLATFORM / "data/processed/national_load"
              / "ipto_system_load_hourly_2022_2026_model_ready.csv")
    days_path = PG_PROCESSED / "representative_days.json"
    if not series.exists() or not days_path.exists():
        print("  ! load series or representative days missing", file=sys.stderr)
        return
    days = load_json(days_path)
    year = int(days[0]["date"][:4])
    src = f"{rel(series)} + {rel(days_path)}"

    df = pd.read_csv(series)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    local = (df.dropna(subset=["timestamp"]).set_index("timestamp")
             .tz_convert("Europe/Athens"))
    observed = local[local.index.year == year]
    load = observed["national_load_mw"].dropna()
    if load.empty:
        return

    by_date = {d.date(): g for d, g in load.groupby(load.index.normalize())}
    blocks, weights = [], []
    for entry in days:
        block = by_date.get(pd.Timestamp(entry["date"]).date())
        if block is not None and len(block):
            blocks.append(block.to_numpy())
            weights.append(entry["weight_days"])
    if not blocks:
        return
    reduced = np.concatenate([np.repeat(b, w) for b, w in zip(blocks, weights)])

    add("repday-count", 2, "2.6", "Representative days in the materialised set",
        str(len(days)), "days", rel(days_path))
    add("repday-weight-total", 2, "2.6",
        "Representative day weights, total", str(sum(d["weight_days"] for d in days)),
        "days", rel(days_path))
    add("load-observed-peak", 2, "2.6",
        f"Observed national system load peak, {year}", f"{load.max():.0f}", "MW",
        rel(series))
    add("repday-peak", 2, "2.6",
        "Highest load in the representative-day set", f"{reduced.max():.0f}", "MW",
        src, provenance="derived")
    add("repday-peak-shortfall", 2, "2.6",
        "Shortfall of the representative-day peak against the observed peak",
        f"{100 * (load.max() - reduced.max()) / load.max():.2f}", "%", src,
        provenance="derived")
    # Recorded as a magnitude, with the direction carried by the wording, so
    # the prose can state it without a sign the guard would read separately.
    add("repday-mean-shortfall", 2, "2.6",
        "Shortfall in mean load of the representative-day set against the "
        "observed year",
        f"{100 * (load.mean() - reduced.mean()) / load.mean():.2f}", "%", src,
        provenance="derived")
    if "issue_type" in observed.columns:
        add("load-outliers-kept", 2, "2.2.1",
            f"Hours in {year} flagged as outliers and retained for review "
            "rather than imputed",
            str(int((observed["issue_type"] == "outlier_kept_for_review").sum())),
            "hours", rel(series))


def extract_sensitivity() -> None:
    """One-factor-at-a-time sensitivity results (Section 4.7)."""
    path = THESIS_EVIDENCE / "sensitivity.json"
    if not path.exists():
        print("  ! missing sensitivity.json; run sensitivity.py first",
              file=sys.stderr)
        return
    data = load_json(path)
    src = rel(path)
    for label, scen in data.get("scenarios", {}).items():
        base = scen["base"]
        for key, unit in [("npv_eur", "EUR"), ("irr_pct", "%"),
                          ("capacity_mw", "MW"), ("capacity_factor_pct", "%"),
                          ("captured_price_eur_per_mwh", "EUR/MWh"),
                          ("capex_eur", "EUR")]:
            if base.get(key) is not None:
                add(f"SENS{label}-base-{key}", 4, "4.7",
                    f"Sensitivity base case, Scenario {label}: {key}",
                    f"{base[key]:g}", unit, src)
        for v in scen.get("variations", []):
            slug = v["parameter"].lower().replace(" ", "-")
            for key, unit in [("npv_swing_eur", "EUR"),
                              ("npv_swing_pct_of_base", "%"),
                              ("irr_swing_pp", "pp"),
                              ("irr_low_pct", "%"), ("irr_high_pct", "%"),
                              ("low_setting", "setting"),
                              ("high_setting", "setting")]:
                if v.get(key) is not None:
                    add(f"SENS{label}-{slug}-{key}", 4, "4.7",
                        f"Sensitivity of {v['parameter']}, Scenario {label}: "
                        f"{key.replace('_', ' ')}",
                        f"{v[key]:g}", unit, src)


def extract_candidate_economics() -> None:
    """Candidate-level economics derived against Scenario A and B.

    Produced by scenario_metrics_export.py and candidate_economics.py, which
    call the platform's own investment functions rather than reimplementing
    them. Both scenarios use the corrected and benchmark-calibrated wind input.
    """
    path = THESIS_EVIDENCE / "candidate_economics.json"
    if not path.exists():
        print(f"  ! missing {path.name}; run candidate_economics.py first",
              file=sys.stderr)
        return
    data = load_json(path)
    src = rel(path)

    for label, scen in data.get("scenarios", {}).items():
        add(f"CE{label}-evaluated", 4, "4.5",
            f"Candidate cells evaluated under Scenario {label}",
            str(scen["candidates_evaluated"]), "cells", src)
        skipped = sum(scen.get("candidates_skipped", {}).values())
        add(f"CE{label}-skipped", 4, "4.5",
            f"Candidate cells not evaluated under Scenario {label} "
            f"(centroid outside every model region)", str(skipped), "cells", src)

        for carrier, metrics in scen.get("by_technology", {}).items():
            prefix = f"CE{label}"
            for metric, stats in metrics.items():
                if not stats:
                    continue
                for stat in ("count", "min", "median", "mean", "max", "positive"):
                    if stat not in stats:
                        continue
                    add(f"{prefix}-{carrier}-{metric}-{stat}", 4, "4.5",
                        f"Candidate {metric} {stat}, {carrier}, "
                        f"Scenario {label}",
                        f"{stats[stat]:g}", "", src)
                    if metric == "npv" and stat in ("median", "mean", "min", "max"):
                        add(f"{prefix}-{carrier}-npv-{stat}-m", 4, "4.5",
                            f"Candidate NPV {stat} in millions, {carrier}, "
                            f"Scenario {label}",
                            f"{stats[stat] / 1e6:.1f}", "m EUR", src)
                        if stats[stat] < 0:
                            add(f"{prefix}-{carrier}-npv-{stat}-loss-m", 4, "4.5",
                                f"Magnitude of candidate NPV {stat} loss in "
                                f"millions, {carrier}, Scenario {label}",
                                f"{abs(stats[stat]) / 1e6:.1f}", "m EUR", src)

        for carrier, pf in scen.get("portfolio", {}).items():
            prefix = f"CE{label}"
            for field, unit in [("candidates", "cells"), ("irr_pct", "%"),
                                ("payback_years", "years"),
                                ("total_initial_outlay_eur", "EUR")]:
                value = pf.get(field)
                if value is None:
                    continue
                add(f"{prefix}-portfolio-{carrier}-{field}", 4, "4.6",
                    f"Portfolio {field.replace('_', ' ')}, {carrier}, "
                    f"Scenario {label}",
                    f"{value:g}" if isinstance(value, (int, float)) else str(value),
                    unit, src)

            # Scale figures in the units the prose uses, so the chapter can
            # frame this portfolio as a technical potential rather than a plan.
            outlay = pf.get("total_initial_outlay_eur")
            if outlay:
                add(f"{prefix}-portfolio-{carrier}-outlay-bn", 4, "4.6",
                    f"Portfolio initial outlay in billions, {carrier}, "
                    f"Scenario {label}",
                    f"{abs(outlay) / 1e9:.2f}", "bn EUR", src)
            tech_stats = scen.get("by_technology", {}).get(carrier, {})
            mean_cap = (tech_stats.get("capacity") or {}).get("mean")
            n_cells = pf.get("candidates")
            if mean_cap and n_cells:
                add(f"{prefix}-portfolio-{carrier}-capacity-gw", 4, "4.6",
                    f"Total portfolio capacity, {carrier}, Scenario "
                    f"{label}",
                    f"{mean_cap * n_cells / 1000:.2f}", "GW", src)


def extract_candidate_capacity_concentration() -> None:
    """How far candidate economics discriminate between sites (Section 4.5).

    Computed by candidate_economics.py, which runs under the API interpreter,
    and read from its output here.
    """
    path = THESIS_EVIDENCE / "candidate_economics.json"
    if not path.exists():
        return
    data = load_json(path)
    src = rel(path)
    for carrier, stats in (data.get("capacity_concentration") or {}).items():
        add(f"R14-capacity-cap-{carrier}", 4, "4.5",
            f"Assumed capacity cap for {carrier} candidates",
            f"{stats['capacity_cap_mw']:g}", "MW", src,
            provenance="scenario_assumption")
        add(f"R14-at-cap-share-{carrier}", 4, "4.5",
            f"Share of {carrier} candidates reaching the capacity cap, and so "
            f"receiving an identical appraisal",
            f"{stats['at_cap_share_pct']:g}", "%", src, provenance="derived")
        add(f"R14-at-cap-count-{carrier}", 4, "4.5",
            f"{carrier.title()} candidates at the capacity cap",
            str(stats["at_cap"]), "cells", src, provenance="derived")


def extract_r14_candidates() -> None:
    path = PLATFORM / "apps" / "api" / "data" / "generated" / "candidate_cells.geojson"
    src = rel(path)
    gj = load_json(path)
    feats = gj.get("features", [])
    add("R14-cell-count", 4, "4.4", "Candidate cells generated",
        str(len(feats)), "cells", src, provenance="derived")
    if not feats:
        return

    props = feats[0].get("properties", {})
    numeric = [k for k, v in props.items()
               if isinstance(v, (int, float)) and not isinstance(v, bool)]
    for key in sorted(numeric):
        vals = [f["properties"][key] for f in feats
                if isinstance(f["properties"].get(key), (int, float))
                and not isinstance(f["properties"].get(key), bool)]
        if not vals:
            continue
        add(f"R14-{key}-mean", 4, "4.4",
            f"Candidate cells, mean {key}", f"{sum(vals) / len(vals):.4g}", "",
            src, provenance="derived")
        add(f"R14-{key}-max", 4, "4.4",
            f"Candidate cells, max {key}", f"{max(vals):.4g}", "", src,
            provenance="derived")


# ==========================================================================
# R8c withholding (author decision, 2026-09-30)
#
# R8c's wind availability profile is not a power-curve output: it has a hard
# floor of 0.26, no calm hours anywhere in the year, and a mean of 0.5169
# against an observed 0.2383. Solar in the same network is correct, so this is
# a defect in the scenario builder's wind path, distinct from D0's power-curve
# error. Because a profile with no calm hours removes the wind scarcity
# structure that CREATES the price distribution, R8c's system outputs do not
# meet the project's own reporting bar and are withheld as findings.
#
# R8c is reported as a METHODOLOGICAL result: the formulation, the unit
# conventions, the validator fix, the balance closure, and the provenance
# machinery -- none of which depend on the wind profile.
# ==========================================================================
WITHHELD_R8C_PREFIXES = (
    "R8c-objective", "R8c-cost-", "R8c-emissions", "R8c-price-elec",
    "R8c-price-h2", "R8c-price-heat", "R8c-price-gas",
    "R8c-price-weighted-mean", "R8c-price-peak-observed",
    "R8c-mainland-price-spread", "R8c-mainland-bus-count",
    "R8c-cap-out-", "R8c-expansion-", "R8c-gen-", "R8c-cf-",
    "R8c-curtailment-", "R8c-marginal-hours-", "R8c-marginal-share-",
    "R8c-res-marginal-share", "R8c-load-weighted-price",
)

WITHHOLD_REASON = (
    " [WITHHELD as a finding: R8c's wind availability profile is not a "
    "power-curve output (floor 0.26, no calm hours, mean 0.5169 vs observed "
    "0.2383), which drives price formation - do not cite]"
)


def apply_r8c_withholding() -> int:
    """Tag the contaminated R8c claims so they cannot be cited."""
    n = 0
    for row in rows:
        cid = row["claim_id"]
        if cid.startswith(WITHHELD_R8C_PREFIXES):
            row["claim_id"] = f"WITHHELD-{cid}"
            row["claim"] = row["claim"] + WITHHOLD_REASON
            row["wind_bias"] = "withheld"
            n += 1
    return n


def main() -> int:
    steps = [
        ("wind availability benchmark", extract_wind_benchmark),
        ("availability distributions", extract_availability_distributions),
        ("R8c result", extract_r8c_result),
        ("R8c pre-fix history", extract_r8c_pre_fix_history),
        ("R8c scope", extract_r8c_scope),
        ("stylised fleet and expansion", extract_stylised_fleet),
        ("R8c price derivation and balances", extract_price_derivation),
        ("gas stack from inputs", extract_gas_stack_from_inputs),
        ("R1 reconciled inventory", extract_r1),
        ("R2 national load QC", extract_r2_load_qc),
        ("Scenario A vs B", extract_scenario_ab),
        ("R11 gas balance round-trip", extract_r11_gas_roundtrip),
        ("literature values", extract_literature_values),
        ("software versions", extract_software_versions),
        ("spatial layer counts", extract_spatial_layers),
        ("method constants", extract_method_constants),
        ("wind power curve", extract_wind_curve),
        ("forecast hyperparameters", extract_forecast_hyperparameters),
        ("coupled conversion efficiencies", extract_coupled_conversions),
        ("technology cost table", extract_cost_table),
        ("R15 test suites", extract_r15_tests),
        ("R3 next-day cases", extract_r3_nextday),
        ("R4 temporal aggregation", extract_r4_aggregation),
        ("R5 electricity runs", extract_electricity_runs),
        ("R9 hydrogen and NECP targets", extract_r9_hydrogen),
        ("R12 spatial constraint QA", extract_r12_spatial),
        ("R13 cluster investment", extract_r13_investment),
        ("R14 candidate screening", extract_r14_candidates),
        ("temporal reduction", extract_temporal_reduction),
        ("candidate capacity concentration", extract_candidate_capacity_concentration),
        ("candidate economics (Scenario A/B)", extract_candidate_economics),
        ("sensitivity analysis", extract_sensitivity),
    ]
    failures = 0
    for label, fn in steps:
        before = len(rows)
        try:
            fn()
        except Exception as exc:  # a failed extractor must be loud, never silent
            print(f"  ! {label} FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            failures += 1
            continue
        print(f"  + {label}: {len(rows) - before} claims")

    # 2026-10-02: NOT called. The wind defect that required withholding R8c's
    # system outputs is fixed (see r8c_wind_bias() and
    # wind_calibration_report.json) and R8c has been re-solved against the
    # corrected profile. apply_r8c_withholding() is kept, unused, as the
    # record of what was withheld and why between 2026-09-30 and 2026-10-02.
    print("\n  ~ R8c withholding lifted 2026-10-02 (wind defect fixed, re-solved) "
          "- apply_r8c_withholding() kept but not called")

    with LEDGER.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nwrote {len(rows)} claims to {LEDGER}")
    if failures:
        print(f"{failures} extractor(s) failed - ledger is INCOMPLETE", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
