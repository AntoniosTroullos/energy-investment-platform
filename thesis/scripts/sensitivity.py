"""One-factor-at-a-time sensitivity of candidate economics (Section 4.7).

The template thesis this work follows presents a sensitivity analysis with
tornado charts, and this script produces the underlying data. Each parameter is
varied in isolation between a low and a high value while every other parameter
is held at its base value, and the resulting swing in net present value and
internal rate of return is recorded.

The discounted cash-flow calculation is the platform's own, imported unchanged
from apps/api/app/investment_analysis.py. Only the inputs are varied here.

Degradation is a module-level constant rather than an argument, so it is patched
for the duration of a single evaluation and restored immediately afterwards. The
repository files are not modified.

Run with the API interpreter:
    apps/api/.venv/Scripts/python.exe thesis/scripts/sensitivity.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

THESIS = Path(__file__).resolve().parents[1]
REPO = THESIS.parent
sys.path.insert(0, str(REPO / "apps" / "api"))

from app import investment_analysis as ia  # noqa: E402

EVIDENCE = THESIS / "evidence"
CARRIER = "solar"
HOURS = 8760.0

# Ranges, each with the reason it was chosen. These are screening ranges, not
# fitted distributions, and the thesis says so.
VARIATIONS = [
    ("Discount rate", "discount_rate_pct", 5.0, 9.0,
     "spans the plausible real cost of capital either side of the 7 % base"),
    ("Capital cost", "capex_eur", 0.8, 1.2,
     "plus or minus a fifth, a conventional screening range for capital cost"),
    ("Captured price", "captured_price_eur_per_mwh", 0.8, 1.2,
     "plus or minus a fifth of the solved regional price"),
    ("Capacity factor", "generation_year0_mwh", 0.8, 1.2,
     "plus or minus a fifth of the national capacity factor"),
    ("Asset lifetime", "lifetime_years", 30.0, 45.0,
     "either side of the 37.5-year base assumption"),
    ("Degradation rate", "degradation_pct", 0.25, 1.0,
     "spans the published range for photovoltaic output decline"),
]

MULTIPLICATIVE = {"capex_eur", "captured_price_eur_per_mwh",
                  "generation_year0_mwh"}


def evaluate(base: dict, override_key: str | None = None,
             override_value: float | None = None) -> tuple[float, float | None]:
    params = dict(base)
    degradation = None
    if override_key == "degradation_pct":
        degradation = override_value
    elif override_key is not None:
        if override_key in MULTIPLICATIVE:
            params[override_key] = base[override_key] * override_value
        else:
            params[override_key] = override_value

    original = ia.DEGRADATION_PCT_PER_YEAR.get(CARRIER)
    if degradation is not None:
        ia.DEGRADATION_PCT_PER_YEAR[CARRIER] = degradation
    try:
        npv = ia.npv_eur(
            capex_eur=params["capex_eur"],
            generation_year0_mwh=params["generation_year0_mwh"],
            captured_price_eur_per_mwh=params["captured_price_eur_per_mwh"],
            marginal_cost_eur_per_mwh=params["marginal_cost_eur_per_mwh"],
            carrier=CARRIER,
            lifetime_years=params["lifetime_years"],
            discount_rate_pct=params["discount_rate_pct"],
            fom_pct_of_capex=params["fom_pct_of_capex"],
        )
        flows = ia.annual_net_cash_flows(
            capex_eur=params["capex_eur"],
            generation_year0_mwh=params["generation_year0_mwh"],
            captured_price_eur_per_mwh=params["captured_price_eur_per_mwh"],
            marginal_cost_eur_per_mwh=params["marginal_cost_eur_per_mwh"],
            carrier=CARRIER,
            lifetime_years=params["lifetime_years"],
            fom_pct_of_capex=params["fom_pct_of_capex"],
        )
        rate = ia.irr(flows)
    finally:
        if degradation is not None:
            if original is None:
                ia.DEGRADATION_PCT_PER_YEAR.pop(CARRIER, None)
            else:
                ia.DEGRADATION_PCT_PER_YEAR[CARRIER] = original
    return npv, (rate * 100 if rate is not None else None)


def base_case(scenario: str) -> dict:
    metrics = json.loads((EVIDENCE / f"scenario_metrics_{scenario}.json")
                         .read_text(encoding="utf-8"))
    costs = ia.load_technology_costs()
    row = costs[CARRIER]

    capacity_mw = 200.0  # the cap that 96 % of solar candidates reach
    generation = metrics["generation_by_carrier_mwh"][CARRIER]
    installed = metrics["installed_capacity_by_carrier_mw"][CARRIER]
    cf = generation / (installed * HOURS)
    prices = metrics["average_marginal_price_by_bus"]
    price = sum(prices.values()) / len(prices)

    return {
        "capex_eur": row.overnight_capex_eur_per_kw * 1000.0 * capacity_mw,
        "generation_year0_mwh": capacity_mw * cf * HOURS,
        "captured_price_eur_per_mwh": price,
        "marginal_cost_eur_per_mwh": row.marginal_cost_eur_per_mwh or 0.0,
        "lifetime_years": row.lifetime_years,
        "discount_rate_pct": row.discount_rate_pct,
        "fom_pct_of_capex": row.fom_pct_of_capex,
        "_capacity_mw": capacity_mw,
        "_capacity_factor": cf,
    }


def main() -> int:
    out: dict = {"carrier": CARRIER, "method": "one-factor-at-a-time",
                 "scenarios": {}}
    for scenario in ("A", "B"):
        path = EVIDENCE / f"scenario_metrics_{scenario}.json"
        if not path.exists():
            continue
        base = base_case(scenario)
        base_npv, base_irr = evaluate(base)
        entry = {
            "base": {
                "capacity_mw": base["_capacity_mw"],
                "capacity_factor_pct": round(base["_capacity_factor"] * 100, 4),
                "captured_price_eur_per_mwh": round(base["captured_price_eur_per_mwh"], 4),
                "capex_eur": round(base["capex_eur"], 2),
                "lifetime_years": base["lifetime_years"],
                "discount_rate_pct": base["discount_rate_pct"],
                "npv_eur": round(base_npv, 2),
                "irr_pct": round(base_irr, 4) if base_irr else None,
            },
            "variations": [],
        }
        for label, key, low, high, reason in VARIATIONS:
            low_npv, low_irr = evaluate(base, key, low)
            high_npv, high_irr = evaluate(base, key, high)
            entry["variations"].append({
                "parameter": label,
                "reason": reason,
                "low_setting": low,
                "high_setting": high,
                "npv_low_eur": round(low_npv, 2),
                "npv_high_eur": round(high_npv, 2),
                "npv_swing_eur": round(abs(high_npv - low_npv), 2),
                "npv_swing_pct_of_base": round(
                    100 * abs(high_npv - low_npv) / abs(base_npv), 2) if base_npv else None,
                "irr_low_pct": round(low_irr, 4) if low_irr else None,
                "irr_high_pct": round(high_irr, 4) if high_irr else None,
                "irr_swing_pp": (round(abs(high_irr - low_irr), 4)
                                 if low_irr is not None and high_irr is not None else None),
            })
        entry["variations"].sort(key=lambda v: v["npv_swing_eur"], reverse=True)
        out["scenarios"][scenario] = entry
        print(f"  + Scenario {scenario}: base NPV "
              f"{base_npv/1e6:,.1f} m EUR, IRR {base_irr:.2f} %")
        for v in entry["variations"]:
            print(f"      {v['parameter']:<18} NPV swing "
                  f"{v['npv_swing_eur']/1e6:>8,.1f} m EUR "
                  f"({v['npv_swing_pct_of_base']:>6.1f} % of base), "
                  f"IRR swing {v['irr_swing_pp']} pp")

    path = EVIDENCE / "sensitivity.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
