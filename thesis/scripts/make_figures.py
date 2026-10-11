"""Generate the thesis figures from the frozen result files.

Every figure is built from a file rather than from a transcribed number, so a
figure and the prose beside it cannot drift apart. Output is PNG at 300 dpi for
embedding and PDF for archival.

Style follows the master plan: one consistent carrier colour map, labelled axes
with units, readable ticks and legends, restrained styling, and a provenance line
carried in the caption rather than burned into the image.

Run with the MODEL interpreter (needs matplotlib, pandas, pypsa):
    ...\\pypsa-greece\\.venv314\\Scripts\\python.exe thesis/scripts/make_figures.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

THESIS = Path(__file__).resolve().parents[1]
MODEL = Path(r"C:\Users\megas\PycharmProjects\pythonProject1")
FIGURES = THESIS / "figures"
EVIDENCE = THESIS / "evidence"

CARRIER_COLOURS = {
    "solar": "#F2C300", "wind": "#3B8FD9", "hydro": "#1F5FA8",
    "gas": "#D9534F", "lignite": "#6B4E3D", "biomass": "#5E9E4B",
    "battery": "#8E6CC0", "pumped_hydro": "#2BA3A3", "oil": "#8A8A8A",
    "hydrogen": "#9AD0EC", "heat": "#E8883A", "unknown": "#BFBFBF",
}
NEUTRAL = "#4A4A4A"
ACCENT = "#B5342E"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.5,
    "legend.frameon": False,
    "figure.dpi": 300,
})

LEDGER: dict[str, dict] = {}


def load_ledger() -> None:
    path = THESIS / "numbers_ledger.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            LEDGER[row["claim_id"]] = row


def val(claim_id: str) -> float:
    return float(LEDGER[claim_id]["value"])


def save(fig, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(FIGURES / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    print(f"  + {name}")


# --------------------------------------------------------------------------
def fig_wind_benchmark() -> None:
    """Wind availability by run family against the observed benchmark."""
    benchmark = val("D0-benchmark-dapeep-cf")
    families = [
        ("Committed series\n(regional)", val("D0-corrected-profile-regional") * 100),
        ("Committed series\n(clustered)", val("D0-corrected-profile-clustered") * 100),
        ("Scenario A / B\n(investment basis)", val("SCA-wind-availability-cf")),
        ("Clustered runs\n(monthly days)",
         val("D0-run-availcf-clustered_mid_2026_monthly_days")),
        ("Stylised runs\n(monthly days)",
         val("D0-run-availcf-mid_2026_monthly_days")),
    ]
    labels = [f[0] for f in families]
    values = [f[1] for f in families]
    colours = [ACCENT if v > benchmark else CARRIER_COLOURS["wind"] for v in values]

    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    bars = ax.bar(labels, values, color=colours, width=0.62)
    ax.axhline(benchmark, color=NEUTRAL, linestyle="--", linewidth=1.1)
    ax.annotate(f"observed benchmark {benchmark:.2f} %",
                xy=(len(labels) - 0.45, benchmark), xytext=(0, 5),
                textcoords="offset points", ha="right", fontsize=8,
                color=NEUTRAL)
    for bar, v in zip(bars, values):
        ax.annotate(f"{v:.2f}", xy=(bar.get_x() + bar.get_width() / 2, v),
                    xytext=(0, 3), textcoords="offset points", ha="center",
                    fontsize=8)
    ax.set_ylabel("Wind availability capacity factor (%)")
    ax.set_ylim(0, max(values) * 1.18)
    ax.tick_params(axis="x", labelsize=8)
    save(fig, "F-wind-benchmark")


def fig_wind_duration() -> None:
    """Availability duration curves, post-correction (2026-10-02).

    Both series below are now derived from the corrected, DAPEEP-calibrated
    power curve (scripts/calibrate_wind_profiles.py, applied 2026-10-02 --
    see wind_calibration_report.json). Before that fix, the national
    committed series carried the uncorrected power-curve error (D0: cubed
    the normalised speed fraction, understating output) and the
    mid_2026_monthly_days case series was a stale artifact predating an
    earlier regeneration of the committed file and was not a power-curve
    output at all (no calm hours, floor 0.26). This figure now shows the two
    remaining real differences between them: national scope versus one
    specific case's resampling onto 288 representative-day snapshots
    (hour-of-day fallback where a timestamp is not directly covered).
    """
    import pandas as pd

    series = {}
    committed = MODEL / "pypsa-greece/data/timeseries/wind_pu_regional.csv"
    if committed.exists():
        df = pd.read_csv(committed, index_col=0).select_dtypes("number")
        series["National calibrated series (all regions, full year)"] = (
            np.sort(df.values.flatten())[::-1], CARRIER_COLOURS["wind"])
    stylised = (MODEL / "data/processed/pypsa_scenarios/mid_2026_monthly_days"
                / "inputs" / "wind_pu_regional.csv")
    if stylised.exists():
        df = pd.read_csv(stylised, index_col=0).select_dtypes("number")
        series["mid_2026_monthly_days case (288 representative snapshots)"] = (
            np.sort(df.values.flatten())[::-1], ACCENT)

    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    for label, (data, colour) in series.items():
        x = np.linspace(0, 100, len(data))
        ax.plot(x, data, color=colour, linewidth=1.4, label=label)
    ax.axhline(val("D0-benchmark-dapeep-cf") / 100, color=NEUTRAL,
               linestyle="--", linewidth=1.0,
               label=f"observed annual mean ({val('D0-benchmark-dapeep-cf'):.2f} %)")
    ax.set_xlabel("Share of modelled hours exceeded (%)")
    ax.set_ylabel("Wind availability (per unit)")
    ax.set_ylim(0, 1.02)
    ax.set_xlim(0, 100)
    ax.legend(loc="upper right", fontsize=8)
    save(fig, "F-wind-duration")


def fig_reconciliation() -> None:
    """Merged register capacity against calibrated operating capacity."""
    carriers = ["solar", "wind", "biomass"]
    derived = [val(f"R1-capacity_by_carrier-{c}-as_derived_mw") for c in carriers]
    calibrated = [val(f"R1-capacity_by_carrier-{c}-calibrated_mw") for c in carriers]
    factors = [val(f"R1-capacity_by_carrier-{c}-calibration_factor") for c in carriers]

    x = np.arange(len(carriers))
    fig, ax = plt.subplots(figsize=(6.0, 3.4))
    ax.bar(x - 0.19, derived, 0.36, label="Merged registers",
           color=[CARRIER_COLOURS[c] for c in carriers], alpha=0.55)
    ax.bar(x + 0.19, calibrated, 0.36, label="Calibrated to operating totals",
           color=[CARRIER_COLOURS[c] for c in carriers])
    for i, f in enumerate(factors):
        top = max(derived[i], calibrated[i])
        ax.annotate(f"x{f:.3f}", xy=(i, top), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=8,
                    color=NEUTRAL)
    ax.set_xticks(x, [c.title() for c in carriers])
    ax.set_ylabel("Capacity (MW)")
    ax.legend(fontsize=8)
    save(fig, "F-reconciliation")


def fig_scenario_comparison() -> None:
    """Generation unchanged while prices rise."""
    carriers = ["gas", "solar", "hydro", "battery", "wind", "biomass"]
    a = [val(f"SCA-gen-{c}") for c in carriers]
    b = [val(f"SCB-gen-{c}") for c in carriers]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.8, 3.2),
                                   gridspec_kw={"width_ratios": [2.1, 1]})
    x = np.arange(len(carriers))
    ax1.bar(x - 0.19, a, 0.36, label="Scenario A",
            color=[CARRIER_COLOURS[c] for c in carriers], alpha=0.55)
    ax1.bar(x + 0.19, b, 0.36, label="Scenario B",
            color=[CARRIER_COLOURS[c] for c in carriers])
    ax1.set_xticks(x, [c.replace("_", " ").title() for c in carriers],
                   fontsize=8, rotation=20)
    ax1.set_ylabel("Annual generation (TWh)")
    ax1.legend(fontsize=8)
    ax1.set_title("Generation: unchanged", fontsize=9)

    prices = [val("SCA-price-weighted-mean"), val("SCB-price-weighted-mean")]
    bars = ax2.bar(["Scenario A", "Scenario B"], prices,
                   color=[NEUTRAL, ACCENT], width=0.5)
    for bar, p in zip(bars, prices):
        ax2.annotate(f"{p:.2f}", xy=(bar.get_x() + bar.get_width() / 2, p),
                     xytext=(0, 3), textcoords="offset points", ha="center",
                     fontsize=8)
    ax2.set_ylabel("Weighted-mean shadow price (EUR/MWh)")
    ax2.set_title(f"Price: +{val('SCAB-price-change'):.2f} %", fontsize=9)
    save(fig, "F-scenario-comparison")


def fig_cannibalisation() -> None:
    """Captured price by carrier against the system average."""
    carriers = ["solar", "wind", "hydro", "biomass"]
    fig, ax = plt.subplots(figsize=(6.0, 3.3))
    width = 0.36
    x = np.arange(len(carriers))
    for offset, scen, alpha in ((-width / 2, "a", 0.55), (width / 2, "b", 1.0)):
        values = [val(f"R13-{c}-captured-price-{scen}") for c in carriers]
        ax.bar(x + offset, values, width,
               color=[CARRIER_COLOURS[c] for c in carriers], alpha=alpha,
               label=f"Scenario {scen.upper()}")
    for scen, style in (("A", "--"), ("B", ":")):
        mean = val(f"SC{scen}-price-weighted-mean")
        ax.axhline(mean, color=NEUTRAL, linestyle=style, linewidth=1.0)
        ax.annotate(f"system mean, Scenario {scen}: {mean:.2f}",
                    xy=(len(carriers) - 0.5, mean), xytext=(0, 3),
                    textcoords="offset points", ha="right", fontsize=7.5,
                    color=NEUTRAL)
    ax.set_xticks(x, [c.title() for c in carriers])
    ax.set_ylabel("Captured price (EUR/MWh)")
    ax.legend(fontsize=8, loc="upper left")
    save(fig, "F-cannibalisation")


def fig_tornado() -> None:
    """Sensitivity tornado charts for net present value."""
    path = EVIDENCE / "sensitivity.json"
    if not path.exists():
        print("  ! sensitivity.json missing; skipping tornado", file=sys.stderr)
        return
    data = json.loads(path.read_text(encoding="utf-8"))

    # Both panels use ONE ordering, taken from Scenario A. Sorting each panel
    # independently while sharing a y axis would label one panel with the
    # other's parameter order.
    order = [v["parameter"] for v in
             sorted(data["scenarios"]["A"]["variations"],
                    key=lambda v: v["npv_swing_eur"])]

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.4), sharey=True)
    for ax, scenario in zip(axes, ("A", "B")):
        scen = data["scenarios"][scenario]
        base = scen["base"]["npv_eur"]
        by_name = {v["parameter"]: v for v in scen["variations"]}
        variations = [by_name[name] for name in order]
        labels = order
        lows = [(v["npv_low_eur"] - base) / 1e6 for v in variations]
        highs = [(v["npv_high_eur"] - base) / 1e6 for v in variations]
        y = np.arange(len(labels))
        ax.barh(y, lows, color=ACCENT, height=0.56, label="Low setting")
        ax.barh(y, highs, color=CARRIER_COLOURS["solar"], height=0.56,
                label="High setting")
        ax.axvline(0, color=NEUTRAL, linewidth=0.9)
        ax.set_yticks(y, labels, fontsize=8)
        ax.set_xlabel("Change in net present value (million EUR)")
        ax.set_title(f"Scenario {scenario}  (base {base/1e6:,.0f} m EUR)",
                     fontsize=9)
    axes[0].legend(fontsize=8, loc="lower right")
    save(fig, "F-tornado-npv")


def fig_hydrogen() -> None:
    """Hydrogen output bounds against the national trajectory."""
    years = ["2030", "2040", "2050"]
    targets = [val(f"R9-target-greece_h2_final_energy_contribution-{y}")
               for y in years]
    base = val("R9-output-base")
    licensed = val("R9-output-licensed")

    x = np.arange(len(years))
    fig, ax = plt.subplots(figsize=(6.0, 3.3))
    ax.bar(x, targets, 0.5, color=NEUTRAL, alpha=0.3, label="National target")
    ax.axhline(licensed, color=CARRIER_COLOURS["hydrogen"], linewidth=1.6,
               label=f"Licensed register bound ({licensed:.3f} TWh)")
    ax.axhline(base, color=ACCENT, linewidth=1.6,
               label=f"Operational base ({base:.3f} TWh)")
    for i, t in enumerate(targets):
        ax.annotate(f"{t:g}", xy=(i, t), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=8)
    ax.set_xticks(x, years)
    ax.set_ylabel("Hydrogen contribution (TWh per year)")
    ax.legend(fontsize=8)
    save(fig, "F-hydrogen-feasibility")


# --------------------------------------------------------------------------
# Chapter 2
# --------------------------------------------------------------------------
def fig_wind_power_curve() -> None:
    """The defective interpolation against the correct power law (Section 2.4).

    The two curves differ because one cubes the normalised speed fraction while
    the other cubes the speed itself. Showing them together is the clearest
    statement of the first defect reported in Section 3.1.2.
    """
    cut_in = val("wind-curve-cut-in")
    rated = val("wind-curve-rated")
    cut_out = val("wind-curve-cut-out")

    v = np.linspace(0, cut_out + 3, 1400)
    correct = np.where(
        v < cut_in, 0.0,
        np.where(v >= rated, 1.0, (v ** 3 - cut_in ** 3) / (rated ** 3 - cut_in ** 3)))
    correct = np.where(v >= cut_out, 0.0, correct)
    legacy = np.where(
        v < cut_in, 0.0,
        np.where(v >= rated, 1.0, ((v - cut_in) / (rated - cut_in)) ** 3))
    legacy = np.where(v >= cut_out, 0.0, legacy)

    fig, ax = plt.subplots(figsize=(6.2, 3.5))
    ax.plot(v, correct, color=CARRIER_COLOURS["wind"], linewidth=1.8,
            label="Correct power law, cubic in wind speed")
    ax.plot(v, legacy, color=ACCENT, linewidth=1.6, linestyle="--",
            label="Implemented curve, cubic in the speed fraction")

    # The two differ most across the ordinary operating range.
    probe = 7.0
    hi = (probe ** 3 - cut_in ** 3) / (rated ** 3 - cut_in ** 3)
    lo = ((probe - cut_in) / (rated - cut_in)) ** 3
    ax.annotate("", xy=(probe, hi), xytext=(probe, lo),
                arrowprops=dict(arrowstyle="<->", color=NEUTRAL, linewidth=1.0))
    ax.annotate(f"at {probe:g} m/s:\n{hi:.3f} against {lo:.3f}",
                xy=(probe, (hi + lo) / 2), xytext=(10, -6),
                textcoords="offset points", fontsize=8, color=NEUTRAL)
    for x, label in ((cut_in, "cut-in"), (rated, "rated"), (cut_out, "cut-out")):
        ax.axvline(x, color=NEUTRAL, linewidth=0.6, alpha=0.45)
        ax.annotate(f"{label}\n{x:g} m/s", xy=(x, 1.04), ha="center",
                    fontsize=7.5, color=NEUTRAL)
    ax.set_xlabel("Wind speed at hub height (m/s)")
    ax.set_ylabel("Availability (per unit of installed capacity)")
    ax.set_xlim(0, cut_out + 3)
    ax.set_ylim(0, 1.16)
    ax.legend(loc="lower right", fontsize=8)
    save(fig, "F-wind-power-curve")


def _box(ax, xy, w, h, text, colour, fontsize=8, text_colour="black"):
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch(xy, w, h, boxstyle="round,pad=0.012",
                                linewidth=0.9, edgecolor=NEUTRAL,
                                facecolor=colour, alpha=0.9))
    ax.text(xy[0] + w / 2, xy[1] + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=text_colour, linespacing=1.35)


def fig_multicarrier_topology() -> None:
    """Carrier buses and the conversions between them (Section 2.8)."""
    fig, ax = plt.subplots(figsize=(6.6, 4.3))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.9, 6.2)
    ax.axis("off")

    n_ac = int(val("coupled-buses-AC"))
    n_heat = int(val("coupled-buses-heat"))
    e_ely = val("coupled-efficiency-electrolysis")
    e_hp = val("coupled-efficiency-heat_pump")
    e_gb = val("coupled-efficiency-gas_boiler")
    e_hb = val("coupled-efficiency-hydrogen_boiler")
    e_g2p = val("coupled-efficiency-gas_to_power")

    _box(ax, (0.3, 4.6), 2.5, 1.0,
         f"Gas bus\n1 national node\nMWh (HHV)", CARRIER_COLOURS["gas"])
    _box(ax, (3.8, 4.6), 2.6, 1.0,
         f"Electricity buses\n{n_ac} regional nodes\nMWh$_e$",
         CARRIER_COLOURS["solar"])
    _box(ax, (7.3, 4.6), 2.4, 1.0,
         f"Hydrogen bus\n1 national node\nMWh (LHV)", CARRIER_COLOURS["hydrogen"])
    _box(ax, (3.8, 0.4), 2.6, 1.0,
         f"Heat buses\n{n_heat} regional nodes\nMWh$_{{th}}$",
         CARRIER_COLOURS["heat"])

    arrows = [
        ((2.8, 5.1), (3.8, 5.1), f"gas to power\n$\\eta$ = {e_g2p:g}"),
        ((6.4, 5.1), (7.3, 5.1), f"electrolysis\n$\\eta$ = {e_ely:g}"),
        ((4.6, 4.6), (4.6, 1.4), f"heat pump\nCOP = {e_hp:g}"),
        ((1.5, 4.6), (4.0, 1.4), f"gas boiler\n$\\eta$ = {e_gb:g}"),
        ((8.5, 4.6), (6.2, 1.4), f"H$_2$ boiler\n$\\eta$ = {e_hb:g}"),
    ]
    positions = [0.5, 0.5, 0.30, 0.42, 0.42]
    for ((x0, y0), (x1, y1), label), f in zip(arrows, positions):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color=NEUTRAL, linewidth=1.1))
        ax.text(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, label, fontsize=7.4,
                ha="center", va="center", color=NEUTRAL,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none",
                          alpha=0.92))
    ax.text(5.0, -0.55,
            "Every link is capacity- and cost-rated on its input side:\n"
            r"$q = \eta f$,   $F^{in} = F^{out}/\eta$,   $c^{in} = \eta\, c^{out}$",
            ha="center", fontsize=8, color=NEUTRAL)
    save(fig, "F-multicarrier-topology")


def fig_architecture() -> None:
    """How the two repositories and the interface fit together (Section 2.10)."""
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8.4)
    ax.axis("off")

    layers = [
        (7.1, "Public data sources", "#DADADA",
         "system operator load  ·  transparency platform  ·  licence registers\n"
         "international trackers  ·  collaborative geography  ·  reanalysis weather"),
        (5.4, "Data products", "#CFE0F0",
         "reconciled generator inventory  ·  candidate cells  ·  regional features\n"
         "national and regional demand  ·  availability profiles"),
        (3.7, "Modelling engine", "#CBE3CE",
         "clustering  ·  scenario artifact with hashes and provenance\n"
         "electricity and multi-carrier planning problems  ·  validation  ·  metrics"),
        (2.0, "Programmatic interface", "#F3DCC4",
         "invoked as a separate process  ·  result files  ·  staleness checks"),
        (0.3, "Web application", "#E6D4EC",
         "map explorer  ·  candidate screening  ·  scenario configuration  ·  results"),
    ]
    for y, title, colour, detail in layers:
        _box(ax, (0.3, y), 9.4, 1.25, "", colour)
        ax.text(0.6, y + 0.88, title, fontsize=9, va="center")
        ax.text(0.6, y + 0.40, detail, fontsize=7.2, va="center", color="#333333",
                linespacing=1.4)
    for y in (6.95, 5.25, 3.55, 1.85):
        ax.annotate("", xy=(5.0, y - 0.28), xytext=(5.0, y),
                    arrowprops=dict(arrowstyle="-|>", color=NEUTRAL, linewidth=1.2))
    save(fig, "F-architecture")


def fig_fleet_map() -> None:
    """The reconciled and calibrated fleet in space (Section 2.5)."""
    import json as _json

    import pandas as pd

    clusters = MODEL / "pypsa-greece/data/processed/generator_clusters.csv"
    regions = (THESIS.parent / "apps/api/data/source/admin_regions.geojson")
    if not clusters.exists():
        print("  ! cluster file missing; skipping fleet map", file=sys.stderr)
        return
    df = pd.read_csv(clusters)

    fig, ax = plt.subplots(figsize=(5.6, 5.4))
    if regions.exists():
        gj = _json.loads(regions.read_text(encoding="utf-8"))
        for feat in gj.get("features", []):
            geom = feat.get("geometry") or {}
            polys = (geom.get("coordinates", []) if geom.get("type") == "Polygon"
                     else [c for part in geom.get("coordinates", []) for c in part])
            for ring in polys:
                xs = [p[0] for p in ring]
                ys = [p[1] for p in ring]
                ax.plot(xs, ys, color="#9A9A9A", linewidth=0.45)

    for carrier, group in df.groupby("carrier"):
        ax.scatter(group["centroid_longitude"], group["centroid_latitude"],
                   s=np.sqrt(group["p_nom_calibrated_mw"].clip(lower=1)) * 3.2,
                   color=CARRIER_COLOURS.get(carrier, CARRIER_COLOURS["unknown"]),
                   edgecolor="white", linewidth=0.35, alpha=0.85,
                   label=carrier.replace("_", " "))
    ax.set_xlabel("Longitude (degrees east)")
    ax.set_ylabel("Latitude (degrees north)")
    ax.set_aspect(1.28)
    ax.legend(fontsize=7.2, loc="upper right", markerscale=0.65,
              labelspacing=0.35)
    save(fig, "F-fleet-map")


def fig_load_series() -> None:
    """The quality-controlled national demand series (Section 2.2.1)."""
    import pandas as pd

    path = (THESIS.parent / "data/processed/national_load"
            / "ipto_system_load_hourly_2022_2026_model_ready.csv")
    if not path.exists():
        print("  ! load series missing; skipping", file=sys.stderr)
        return
    df = pd.read_csv(path)
    time_col = next((c for c in df.columns if "time" in c.lower()
                     or "date" in c.lower()), df.columns[0])
    load_col = next((c for c in df.columns
                     if "load" in c.lower() and df[c].dtype.kind in "fi"), None)
    if load_col is None:
        print("  ! no load column found; skipping", file=sys.stderr)
        return
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce", utc=True)
    df = df.dropna(subset=[time_col]).sort_values(time_col)

    fig, ax = plt.subplots(figsize=(6.6, 3.2))
    ax.plot(df[time_col], df[load_col] / 1000.0, color=NEUTRAL, linewidth=0.22,
            alpha=0.55, label="Hourly system load")
    monthly = df.set_index(time_col)[load_col].resample("MS").mean() / 1000.0
    ax.plot(monthly.index, monthly.values, color=ACCENT, linewidth=1.5,
            label="Monthly mean")
    ax.set_ylabel("System load (GW)")
    ax.set_xlabel("")
    ax.legend(fontsize=8, loc="upper right")
    save(fig, "F-load-series")


# --------------------------------------------------------------------------
# Chapter 4
# --------------------------------------------------------------------------
# All four technologies are reportable after Scenarios A and B were re-solved
# against the corrected, benchmark-calibrated wind series on 2026-10-02.
ECONOMIC_CARRIERS = ("wind", "solar", "hydro", "biomass")


def _cluster_economics():
    import pandas as pd

    evaluation = MODEL / "pypsa-greece/data/processed/cluster_investment_evaluation.csv"
    clusters = MODEL / "pypsa-greece/data/processed/generator_clusters.csv"
    if not evaluation.exists() or not clusters.exists():
        return None
    ev = pd.read_csv(evaluation)
    cl = pd.read_csv(clusters)[
        ["bus", "carrier", "cluster_index", "centroid_longitude", "centroid_latitude"]]
    df = ev.merge(cl, on=["bus", "carrier", "cluster_index"], how="left")
    return df[
        df["carrier"].isin(ECONOMIC_CARRIERS)
        & (df["p_nom_calibrated_mw"] > 0)
    ].copy()


def fig_cluster_npv_map() -> None:
    """Where the value sits, by cluster (Section 4.3)."""
    import json as _json

    df = _cluster_economics()
    if df is None or df.empty:
        print("  ! cluster economics unavailable; skipping NPV map", file=sys.stderr)
        return

    fig, ax = plt.subplots(figsize=(5.6, 5.2))
    regions = THESIS.parent / "apps/api/data/source/admin_regions.geojson"
    if regions.exists():
        for feat in _json.loads(regions.read_text(encoding="utf-8"))["features"]:
            geom = feat.get("geometry") or {}
            rings = (geom.get("coordinates", []) if geom.get("type") == "Polygon"
                     else [r for part in geom.get("coordinates", []) for r in part])
            for ring in rings:
                ax.plot([p[0] for p in ring], [p[1] for p in ring],
                        color="#9A9A9A", linewidth=0.45)

    # Colour carries value and marker shape carries carrier, so a reader can
    # tell a loss-making solar cluster from a loss-making hydro one.
    markers = {"wind": "P", "solar": "o", "hydro": "^", "biomass": "s"}
    npv_all = df["scenario_a_npv_eur"] / 1e6
    bound = abs(npv_all).max()
    sc = None
    for carrier, marker in markers.items():
        sub = df[df["carrier"] == carrier]
        if sub.empty:
            continue
        sc = ax.scatter(sub["centroid_longitude"], sub["centroid_latitude"],
                        s=np.sqrt(sub["p_nom_calibrated_mw"].clip(lower=1)) * 4.0,
                        c=sub["scenario_a_npv_eur"] / 1e6, cmap="RdYlGn",
                        vmin=-bound, vmax=bound, marker=marker,
                        edgecolor="#555555", linewidth=0.35, alpha=0.92)
    from matplotlib.lines import Line2D
    ax.legend(handles=[
        Line2D([], [], marker=m, linestyle="none", color="white",
               markeredgecolor="#555555", markersize=6, label=c.title())
        for c, m in markers.items() if c in set(df["carrier"])],
        fontsize=8, loc="lower left", title="Marker size: capacity",
        title_fontsize=7.5)
    cbar = fig.colorbar(sc, ax=ax, shrink=0.72, pad=0.02)
    cbar.set_label("Net present value, Scenario A (million EUR)", fontsize=8)
    cbar.ax.tick_params(labelsize=7.5)
    ax.set_xlabel("Longitude (degrees east)")
    ax.set_ylabel("Latitude (degrees north)")
    ax.set_aspect(1.28)
    ax.set_title("Positive-capacity generation clusters", fontsize=8.5)
    save(fig, "F-cluster-npv-map")


def fig_irr_distribution() -> None:
    """Returns by technology under both scenarios (Section 4.3).

    A small number of clusters return far above the rest. Rather than let
    them flatten the figure, the axis is clipped and every point above the
    cut is drawn on the cut line and labelled with its own value, so none is
    hidden.
    """
    from matplotlib.lines import Line2D

    df = _cluster_economics()
    if df is None or df.empty:
        return
    carriers = [c for c in ECONOMIC_CARRIERS if c in set(df["carrier"])]
    scenarios = ((-0.17, "a", 0.45, "Scenario A"), (0.17, "b", 1.0, "Scenario B"))

    everything = np.concatenate([
        df[f"scenario_{s}_irr_pct"].dropna().to_numpy() for _, s, _, _ in scenarios])
    cut = float(np.percentile(everything, 97))
    cut = float(np.ceil(cut / 5) * 5)
    floor = float(np.floor(min(everything.min(), 0) / 5) * 5)

    fig, ax = plt.subplots(figsize=(6.3, 3.5))
    rng = np.random.default_rng(42)
    for i, carrier in enumerate(carriers):
        sub = df[df["carrier"] == carrier]
        for offset, scen, alpha, label in scenarios:
            vals = sub[f"scenario_{scen}_irr_pct"].dropna().to_numpy()
            if not len(vals):
                continue
            x = i + offset + (rng.random(len(vals)) - 0.5) * 0.15
            inside = vals <= cut
            ax.scatter(x[inside], vals[inside], s=20,
                       color=CARRIER_COLOURS[carrier], alpha=alpha,
                       edgecolor="white", linewidth=0.3, zorder=3)
            above = vals[~inside]
            if len(above):
                ax.scatter(x[~inside], np.full(len(above), cut), s=26,
                           marker="^", color=CARRIER_COLOURS[carrier],
                           alpha=alpha, edgecolor=NEUTRAL, linewidth=0.4,
                           zorder=4, clip_on=False)
                ax.annotate(", ".join(f"{v:,.4g}" for v in sorted(above)),
                            xy=(i + offset, cut), xytext=(0, 7),
                            textcoords="offset points", ha="center",
                            fontsize=7, color=NEUTRAL)
            ax.hlines(np.median(vals), i + offset - 0.13, i + offset + 0.13,
                      color=NEUTRAL, linewidth=1.4, zorder=5)
    # The discount rate applied is carried per cluster; draw the reference
    # line only when every cluster shares one, rather than picking one.
    rates = df["discount_rate_pct"].dropna().unique()
    if len(rates) == 1:
        rate = float(rates[0])
        ax.axhline(rate, color=ACCENT, linestyle="--", linewidth=1.0, zorder=1)
        ax.annotate(f"discount rate, {rate:.4g} %", xy=(-0.5, rate),
                    xytext=(0, -11), textcoords="offset points", ha="left",
                    fontsize=7.5, color=ACCENT)
    ax.set_xticks(range(len(carriers)), [c.title() for c in carriers])
    ax.set_xlim(-0.55, len(carriers) - 0.45)
    ax.set_ylim(floor, cut)
    ax.set_ylabel("Internal rate of return (%)")
    ax.grid(axis="x", visible=False)
    ax.legend(handles=[
        Line2D([], [], marker="o", linestyle="none", color=NEUTRAL,
               alpha=a, markersize=5, label=lab)
        for _, _, a, lab in scenarios] + [
        Line2D([], [], marker="^", linestyle="none", color="white",
               markeredgecolor=NEUTRAL, markersize=6,
               label=f"above {cut:,.4g} %, value shown")],
        fontsize=7.5, loc="upper left", ncol=3)
    ax.set_title("Horizontal bars mark the median among defined IRRs",
                 fontsize=8.5, pad=22)
    save(fig, "F-irr-distribution")


def fig_ab_npv_scatter() -> None:
    """How the gas reprice moves each cluster's value (Section 4.3)."""
    df = _cluster_economics()
    if df is None or df.empty:
        return
    fig, ax = plt.subplots(figsize=(4.9, 4.6))
    a = df["scenario_a_npv_eur"] / 1e6
    b = df["scenario_b_npv_eur"] / 1e6
    # Equal, data-fitted limits: the 45-degree line keeps its meaning while
    # the points fill the panel.
    lo = min(a.min(), b.min())
    hi = max(a.max(), b.max())
    pad = (hi - lo) * 0.07
    lo, hi = lo - pad, hi + pad
    ax.plot([lo, hi], [lo, hi], color=NEUTRAL, linewidth=0.9,
            linestyle="--", label="unchanged")
    for carrier in [c for c in ECONOMIC_CARRIERS if c in set(df["carrier"])]:
        sub = df[df["carrier"] == carrier]
        ax.scatter(sub["scenario_a_npv_eur"] / 1e6, sub["scenario_b_npv_eur"] / 1e6,
                   s=26, color=CARRIER_COLOURS[carrier], alpha=0.85,
                   edgecolor="white", linewidth=0.3, label=carrier.title())
    ax.axhline(0, color="#BBBBBB", linewidth=0.7)
    ax.axvline(0, color="#BBBBBB", linewidth=0.7)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal")
    ax.set_xlabel("Net present value, Scenario A (million EUR)")
    ax.set_ylabel("Net present value, Scenario B (million EUR)")
    gained = int((b.to_numpy() > a.to_numpy()).sum())
    ax.set_title(f"{gained} of {len(a)} positive-capacity clusters gain "
                 "under Scenario B", fontsize=8.5)
    ax.legend(fontsize=8, loc="lower right")
    save(fig, "F-ab-npv-scatter")


def fig_candidate_carving() -> None:
    """How the two technologies' exclusion rules carve a cell (Section 4.4).

    Solar is clipped by Natura 2000; wind is not, because protected-area
    status is conditional for wind licensing rather than prohibitive, and is
    clipped instead by banned regions, banned regional units and small
    islands. One cell of each makes the asymmetry visible.
    """
    from matplotlib.path import Path as MplPath
    from matplotlib.patches import PathPatch, Rectangle

    path = THESIS.parent / "apps/api/data/generated/candidate_cells.geojson"
    if not path.exists():
        return
    feats = json.loads(path.read_text(encoding="utf-8"))["features"]

    def rings_of(feature):
        geom = feature["geometry"]
        polys = ([geom["coordinates"]] if geom["type"] == "Polygon"
                 else geom["coordinates"])
        return [ring for poly in polys for ring in poly]

    def detail(feature):
        rings = rings_of(feature)
        return (len(rings), sum(len(r) for r in rings))

    def pick(keyword):
        pool = [f for f in feats
                if keyword in f["properties"].get("technology", "")
                and 0.25 < (f["properties"].get("buildable_fraction") or 1) < 0.85]
        return max(pool, key=detail) if pool else None

    panels = [("Solar", pick("Solar"), "a Natura 2000 site"),
              ("Onshore Wind", pick("Wind"), "a banned regional unit")]
    panels = [(lab, cell, rule) for lab, cell, rule in panels if cell is not None]
    if not panels:
        print("  ! no partially excluded cells found", file=sys.stderr)
        return

    step = val("candidate-grid-step")
    # The grid is laid from the screening region's bounding-box corner, not
    # from a round degree, so the original square is recovered by snapping to
    # that same lattice rather than to a multiple of the step.
    region = json.loads(
        (THESIS.parent / "apps/api/data/source/region_boundary.geojson")
        .read_text(encoding="utf-8"))
    ring0 = region["features"][0]["geometry"]["coordinates"][0]
    origin_x = min(pt[0] for pt in ring0)
    origin_y = min(pt[1] for pt in ring0)

    fig, axes = plt.subplots(1, len(panels), figsize=(6.4, 3.7))
    axes = np.atleast_1d(axes)
    for ax, (label, cell, rule) in zip(axes, panels):
        props = cell["properties"]
        rings = rings_of(cell)
        xs = [pt[0] for r in rings for pt in r]
        ys = [pt[1] for r in rings for pt in r]
        x0 = origin_x + np.floor((min(xs) - origin_x) / step + 1e-9) * step
        y0 = origin_y + np.floor((min(ys) - origin_y) / step + 1e-9) * step
        # A carved cell can start inside its square; step back if the
        # remainder does not fit within the reconstructed bounds.
        if max(xs) > x0 + step + 1e-9:
            x0 += step
        if max(ys) > y0 + step + 1e-9:
            y0 += step

        ax.add_patch(Rectangle((x0, y0), step, step, facecolor="#F2D7D5",
                               edgecolor=ACCENT, linewidth=1.0, linestyle="--",
                               zorder=1))
        verts, codes = [], []
        for ring in rings:
            verts.extend(ring)
            codes.extend([MplPath.MOVETO] + [MplPath.LINETO] * (len(ring) - 2)
                         + [MplPath.CLOSEPOLY])
        ax.add_patch(PathPatch(MplPath(verts, codes),
                               facecolor=CARRIER_COLOURS["biomass"], alpha=0.75,
                               edgecolor="#2F6B33", linewidth=0.7, zorder=2))
        ax.set_xlim(x0 - step * 0.08, x0 + step * 1.08)
        ax.set_ylim(y0 - step * 0.08, y0 + step * 1.08)
        ax.set_aspect(1 / np.cos(np.radians(y0 + step / 2)))
        ax.set_xlabel("Longitude (degrees east)", fontsize=8.5)
        ax.tick_params(labelsize=7.5)
        ax.set_title(f"{label}: {props.get('id')}" + "\n"
                     f"clipped by {rule}; buildable fraction "
                     f"{props.get('buildable_fraction'):.4g}",
                     fontsize=8.5, linespacing=1.4)
    axes[0].set_ylabel("Latitude (degrees north)", fontsize=8.5)

    from matplotlib.patches import Patch
    fig.legend(handles=[
        Patch(facecolor=CARRIER_COLOURS["biomass"], alpha=0.75,
              edgecolor="#2F6B33", label="Buildable area"),
        Patch(facecolor="#F2D7D5", edgecolor=ACCENT, linestyle="--",
              label="Carved out by the exclusion rule")],
        loc="lower center", ncol=2, fontsize=8, bbox_to_anchor=(0.5, -0.02))
    fig.subplots_adjust(bottom=0.26, wspace=0.30)
    save(fig, "F-candidate-carving")


def fig_candidate_degeneracy() -> None:
    """Why the candidate appraisal cannot rank sites (Sections 4.5, 4.6).

    Panel (a) counts the cells that reach the assumed capacity cap; panel (b)
    shows how little the resulting solar appraisal then varies across them,
    each metric on its own scale. Wind is shown in the capacity-cap comparison;
    its corrected economic results are reported separately in the chapter.
    """
    data = json.loads((EVIDENCE / "candidate_economics.json").read_text(encoding="utf-8"))
    conc = data["capacity_concentration"]
    solar = data["scenarios"]["A"]["by_technology"]["solar"]

    fig = plt.figure(figsize=(6.5, 3.2))
    gs = fig.add_gridspec(3, 2, width_ratios=[1.0, 1.15], wspace=0.34,
                          hspace=0.95)
    ax1 = fig.add_subplot(gs[:, 0])

    techs = [t for t in ("solar", "wind") if t in conc]
    y = np.arange(len(techs))
    ax1.barh(y, [conc[t]["cells"] for t in techs], height=0.46,
             color="#E4E4E4", edgecolor=NEUTRAL, linewidth=0.5,
             label="cells evaluated")
    ax1.barh(y, [conc[t]["at_cap"] for t in techs], height=0.46,
             color=[CARRIER_COLOURS[t] for t in techs], edgecolor=NEUTRAL,
             linewidth=0.5, label="at the capacity cap")
    for i, t in enumerate(techs):
        ax1.annotate(f"{conc[t]['at_cap']} of {conc[t]['cells']}  "
                     f"({conc[t]['at_cap_share_pct']:.4g} %)",
                     xy=(conc[t]["cells"], i), xytext=(5, 0),
                     textcoords="offset points", va="center", fontsize=7.5)
    ax1.set_yticks(y, [t.title() for t in techs])
    ax1.set_ylim(-0.75, len(techs) - 0.25)
    ax1.set_xlabel("Candidate cells")
    ax1.set_xlim(0, max(conc[t]["cells"] for t in techs) * 1.72)
    ax1.legend(fontsize=7.5, loc="lower center", ncol=1,
               bbox_to_anchor=(0.5, -0.03))
    ax1.grid(axis="y", visible=False)
    ax1.set_title("(a) Cells reaching the capacity cap", fontsize=9, loc="left")

    metrics = [("npv", "Net present value (million EUR)", 1e-6),
               ("irr", "Internal rate of return (%)", 1.0),
               ("lcoe", "Levelised cost (EUR/MWh)", 1.0)]
    for row, (key, label, scale) in enumerate(metrics):
        ax = fig.add_subplot(gs[row, 1])
        stats = solar[key]
        lo, hi, med = (stats["min"] * scale, stats["max"] * scale,
                       stats["median"] * scale)
        pad = max(hi - lo, abs(hi) * 0.04) * 0.30
        ax.hlines(0, lo, hi, color=NEUTRAL, linewidth=1.4)
        ax.scatter([lo, hi], [0, 0], s=15, color=NEUTRAL, zorder=3)
        ax.scatter([med], [0], s=58, marker="D",
                   color=CARRIER_COLOURS["solar"], edgecolor=NEUTRAL,
                   linewidth=0.5, zorder=4, label="median")
        ax.set_xlim(lo - pad, hi + pad)
        ax.set_ylim(-1, 1)
        ax.set_yticks([])
        ax.grid(visible=False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.set_xticks([lo, hi] if hi != lo else [hi])
        ax.tick_params(axis="x", length=0, labelsize=7.5, pad=1)
        ax.annotate(label, xy=(0.5, 1.0), xycoords="axes fraction",
                    ha="center", va="bottom", fontsize=7.5)
        note = ("identical in every cell" if hi == lo
                else f"median {med:,.4g} = maximum")
        ax.annotate(note, xy=(1.0, -0.62), xycoords=("axes fraction", "data"),
                    ha="right", va="top", fontsize=7, style="italic",
                    color=ACCENT)
    fig.text(0.545, 0.985, f"(b) Spread across {solar['npv']['count']} solar "
             "cells, Scenario A", fontsize=9, ha="left", va="top")
    save(fig, "F-candidate-degeneracy")


def fig_network_topology() -> None:
    """The thirteen-region network and its corridors (Section 2.7)."""
    import pypsa
    import warnings
    from matplotlib.patches import Polygon as MplPolygon

    path = MODEL / "pypsa-greece/outputs/clustered/networks/greece_clustered.nc"
    regions_path = THESIS.parent / "apps/api/data/source/admin_regions.geojson"
    if not path.exists() or not regions_path.exists():
        print("  ! network or region boundaries missing; skipping", file=sys.stderr)
        return
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        n = pypsa.Network(str(path))

    feats = json.loads(regions_path.read_text(encoding="utf-8"))["features"]
    # Place each node on the largest part of its region, so an island region
    # is labelled on land rather than at sea between its islands.
    centroid, outlines = {}, {}
    for f in feats:
        geom = f["geometry"]
        polys = ([geom["coordinates"]] if geom["type"] == "Polygon"
                 else geom["coordinates"])
        rings = [poly[0] for poly in polys]
        outlines[f["properties"]["id"]] = rings
        biggest = max(rings, key=len)
        centroid[f["properties"]["id"]] = (
            float(np.mean([pt[0] for pt in biggest])),
            float(np.mean([pt[1] for pt in biggest])))

    buses = [b for b in n.buses.index if "_cluster_" not in b]
    lines = n.lines[n.lines.bus0.isin(buses) & n.lines.bus1.isin(buses)]

    fig, ax = plt.subplots(figsize=(6.0, 5.6))
    for rid, rings in outlines.items():
        for ring in rings:
            ax.add_patch(MplPolygon(ring, closed=True, facecolor="#F3F3F3",
                                    edgecolor="#BDBDBD", linewidth=0.45,
                                    zorder=1))
    widest = lines["s_nom"].max()
    for name, row in lines.iterrows():
        if row.bus0 not in centroid or row.bus1 not in centroid:
            continue
        x0, y0 = centroid[row.bus0]
        x1, y1 = centroid[row.bus1]
        ax.plot([x0, x1], [y0, y1], color=CARRIER_COLOURS["hydro"],
                linewidth=0.7 + 3.0 * row.s_nom / widest, alpha=0.75,
                solid_capstyle="round", zorder=2)
    for bus in buses:
        if bus not in centroid:
            continue
        x, y = centroid[bus]
        ax.scatter([x], [y], s=46, color="white", edgecolor=NEUTRAL,
                   linewidth=1.0, zorder=3)
        # Two nodes sit where a corridor would run through the label, so
        # their labels are placed below the node instead of above it.
        below = bus in ("Crete", "South_Aegean")
        ax.annotate(bus.replace("_", " "), xy=(x, y),
                    xytext=(0, -13 if below else 7),
                    textcoords="offset points", ha="center", fontsize=6.8,
                    color=NEUTRAL, zorder=4)

    xs = [c[0] for c in centroid.values()]
    ys = [c[1] for c in centroid.values()]
    ax.set_xlim(min(xs) - 1.4, max(xs) + 1.2)
    ax.set_ylim(min(ys) - 0.9, max(ys) + 1.0)
    ax.set_aspect(1 / np.cos(np.radians(float(np.mean(ys)))))
    ax.set_xlabel("Longitude (degrees east)")
    ax.set_ylabel("Latitude (degrees north)")
    ax.set_title(f"{len(buses)} regions, {len(lines)} corridors; "
                 "line width proportional to rating", fontsize=8.5)
    save(fig, "F-network-topology")


def fig_duration_curves() -> None:
    """What the representative-day reduction keeps of the load (Section 2.6).

    The reduced set is compared against the observed hourly series it is drawn
    from, not against a solved year, because no full-year solve exists. This
    isolates the effect of the temporal reduction itself.
    """
    import pandas as pd

    series = (THESIS.parent / "data/processed/national_load"
              / "ipto_system_load_hourly_2022_2026_model_ready.csv")
    days_path = MODEL / "pypsa-greece/data/processed/representative_days.json"
    if not series.exists() or not days_path.exists():
        print("  ! load series or representative days missing", file=sys.stderr)
        return
    days = json.loads(days_path.read_text(encoding="utf-8"))
    year = int(days[0]["date"][:4])

    df = pd.read_csv(series)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])
    # Representative days are calendar days in local time, so the series is
    # converted before it is grouped by date.
    local = df.set_index("timestamp").tz_convert("Europe/Athens")
    observed = local[local.index.year == year]["national_load_mw"].dropna()
    if observed.empty:
        print(f"  ! no observed hours in {year}", file=sys.stderr)
        return

    by_date = {d.date(): g for d, g in observed.groupby(observed.index.normalize())}
    picked, weights, missing = [], [], 0
    for entry in days:
        key = pd.Timestamp(entry["date"]).date()
        block = by_date.get(key)
        if block is None or len(block) == 0:
            missing += 1
            continue
        picked.append(block.to_numpy())
        weights.append(entry["weight_days"])
    if not picked:
        print("  ! no representative day matched the series", file=sys.stderr)
        return
    if missing:
        print(f"  ! {missing} representative day(s) absent from the series",
              file=sys.stderr)
    reduced = np.concatenate([np.repeat(block, w) for block, w in
                              zip(picked, weights)])

    fig, ax = plt.subplots(figsize=(6.3, 3.5))
    for data, colour, width, label in (
            (observed.to_numpy(), NEUTRAL, 1.5,
             f"Observed hourly series, {year}"),
            (reduced, ACCENT, 1.5,
             f"{len(picked)} representative days, weighted")):
        ordered = np.sort(data)[::-1]
        ax.plot(np.linspace(0, 100, len(ordered)), ordered / 1000.0,
                color=colour, linewidth=width, label=label)
    ax.set_xlabel("Share of the year exceeded (%)")
    ax.set_ylabel("System load (GW)")
    ax.set_xlim(0, 100)
    ax.legend(fontsize=8, loc="upper right")
    ax.set_title("The reduction preserves the body of the distribution and "
                 "truncates its tails", fontsize=8.5)
    save(fig, "F-duration-curves")


def main() -> int:
    load_ledger()
    builders = [fig_wind_power_curve, fig_multicarrier_topology, fig_architecture,
                fig_fleet_map, fig_load_series,
                fig_wind_benchmark, fig_wind_duration, fig_reconciliation,
                fig_scenario_comparison, fig_cannibalisation, fig_tornado,
                fig_hydrogen,
                fig_cluster_npv_map, fig_irr_distribution, fig_ab_npv_scatter,
                fig_candidate_carving, fig_candidate_degeneracy,
                fig_network_topology, fig_duration_curves]
    failures = 0
    for fn in builders:
        try:
            fn()
        except Exception as exc:
            print(f"  ! {fn.__name__} FAILED: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            failures += 1
    print(f"\nwrote {len(list(FIGURES.glob('*.png')))} figures to {FIGURES}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
