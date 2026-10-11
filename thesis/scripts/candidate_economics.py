"""Candidate-level economics against Scenario A and B.

Step 2 of the derivation begun in scenario_metrics_export.py. The platform's
frozen API only derives candidate economics for cases matching
`future_electricity_YYYY`, all of which decision D1 excludes. This script calls
the platform's OWN investment functions directly, supplying Scenario A and B
metrics instead, so the result is consistent with the dispatch reported in
Chapter 3 rather than with an excluded case.

Nothing here reimplements the finance. Capacity assumptions, capital costs,
degradation, net present value, internal rate of return, levelised cost and
payback all come from apps/api/app/investment_analysis.py unchanged; this script
only supplies inputs and aggregates outputs.

Two limitations are inherited from that module and are stated in the thesis
wherever these numbers appear:
  * the captured price is the candidate's region's solved average marginal price
    across all technologies, not a technology-specific captured price;
  * annual generation uses the scenario's national capacity factor for the
    carrier, not a site-specific resource estimate.

Run with the API interpreter (it needs pydantic and shapely):
    apps/api/.venv/Scripts/python.exe thesis/scripts/candidate_economics.py
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

THESIS = Path(__file__).resolve().parents[1]
REPO = THESIS.parent
sys.path.insert(0, str(REPO / "apps" / "api"))

from app.evaluation import load_candidate_cells  # noqa: E402
from app.investment_analysis import (  # noqa: E402
    candidate_carrier,
    combine_cash_flows,
    evaluate_candidate_with_cash_flows,
    irr,
    load_technology_costs,
    payback_period_years,
)
from app.network_topology import get_candidate_region_ids  # noqa: E402
from app.scenario_models import ScenarioMetrics  # noqa: E402

EVIDENCE = THESIS / "evidence"
TOP_N = 50


def summarise(values: list[float]) -> dict:
    if not values:
        return {}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "min": round(ordered[0], 4),
        "median": round(statistics.median(ordered), 4),
        "mean": round(statistics.fmean(ordered), 4),
        "max": round(ordered[-1], 4),
        "positive": sum(1 for v in ordered if v > 0),
    }


def run_scenario(label: str, cells, region_ids, costs) -> dict:
    metrics_path = EVIDENCE / f"scenario_metrics_{label}.json"
    raw = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics = ScenarioMetrics.model_validate(raw)

    per_tech: dict[str, dict[str, list[float]]] = {}
    flows_by_tech: dict[str, list[list[float]]] = {}
    evaluated = 0
    skipped: dict[str, int] = {}

    for cell in cells:
        region = region_ids.get(cell.id)
        analysis, flows = evaluate_candidate_with_cash_flows(
            cell, region, metrics, costs)
        carrier = candidate_carrier(cell.technology) or "unknown"
        if analysis.npv_eur is None:
            reason = (analysis.message or "no result")[:60]
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        evaluated += 1
        bucket = per_tech.setdefault(carrier, {"npv": [], "irr": [], "lcoe": [],
                                               "capacity": [], "payback": []})
        bucket["npv"].append(analysis.npv_eur)
        if analysis.irr_pct is not None:
            bucket["irr"].append(analysis.irr_pct)
        if getattr(analysis, "lcoe_eur_per_mwh", None) is not None:
            bucket["lcoe"].append(analysis.lcoe_eur_per_mwh)
        if analysis.assumed_capacity_mw is not None:
            bucket["capacity"].append(analysis.assumed_capacity_mw)
        if getattr(analysis, "payback_period_years", None) is not None:
            bucket["payback"].append(analysis.payback_period_years)
        if flows:
            flows_by_tech.setdefault(carrier, []).append(flows)

    result = {
        "scenario": label,
        "scenario_name": raw["scenario_name"],
        "candidates_evaluated": evaluated,
        "candidates_skipped": skipped,
        "by_technology": {},
        "portfolio": {},
    }

    for carrier, bucket in sorted(per_tech.items()):
        result["by_technology"][carrier] = {
            metric: summarise(values) for metric, values in bucket.items()
        }

    # Portfolio returns on combined cash flows, which is how a return across
    # investments actually combines -- not an average of individual rates.
    # irr() returns a rate, while the per-candidate analysis reports a
    # percentage. Both are converted to percent here so the two can never be
    # compared across a factor of 100.
    def portfolio_entry(flows_list: list[list[float]]) -> dict:
        combined = combine_cash_flows(flows_list)
        rate = irr(combined)
        return {
            "candidates": len(flows_list),
            "irr_pct": round(rate * 100, 4) if rate is not None else None,
            "payback_years": (round(payback_period_years(combined), 4)
                              if payback_period_years(combined) is not None else None),
            "total_initial_outlay_eur": round(combined[0], 2) if combined else None,
        }

    for carrier, flows_list in sorted(flows_by_tech.items()):
        result["portfolio"][carrier] = portfolio_entry(flows_list)

    all_flows = [f for fl in flows_by_tech.values() for f in fl]
    if all_flows:
        result["portfolio"]["all_technologies"] = portfolio_entry(all_flows)
    return result


def main() -> int:
    cells = load_candidate_cells()
    region_ids = get_candidate_region_ids()
    costs = load_technology_costs()
    print(f"loaded {len(cells)} candidate cells, "
          f"{sum(1 for v in region_ids.values() if v)} joined to a region, "
          f"{len(costs)} cost rows")

    # How many cells reach the assumed capacity cap. If most do, their
    # appraisals are identical and the screening cannot rank between them.
    from app.investment_analysis import assumed_capacity_mw
    concentration: dict[str, dict] = {}
    by_carrier: dict[str, list[float]] = {}
    for cell in cells:
        carrier = candidate_carrier(cell.technology)
        if not carrier:
            continue
        mw = assumed_capacity_mw(cell, carrier)
        if mw is not None:
            by_carrier.setdefault(carrier, []).append(round(mw, 3))
    for carrier, caps in sorted(by_carrier.items()):
        cap_value = max(caps)
        at_cap = sum(1 for v in caps if abs(v - cap_value) < 1e-6)
        concentration[carrier] = {
            "cells": len(caps),
            "capacity_cap_mw": cap_value,
            "at_cap": at_cap,
            "at_cap_share_pct": round(100 * at_cap / len(caps), 1),
        }
        print(f"  + {carrier}: {at_cap}/{len(caps)} cells "
              f"({concentration[carrier]['at_cap_share_pct']} %) at the "
              f"{cap_value:g} MW cap")

    payload = {"top_n_rule": f"all non-excluded candidates; top-{TOP_N} by "
                             f"investment score reported separately",
               "capacity_concentration": concentration,
               "scenarios": {}}
    for label in ("A", "B"):
        if not (EVIDENCE / f"scenario_metrics_{label}.json").exists():
            print(f"  ! no metrics for Scenario {label}; run "
                  f"scenario_metrics_export.py first", file=sys.stderr)
            continue
        res = run_scenario(label, cells, region_ids, costs)
        payload["scenarios"][label] = res
        print(f"  + Scenario {label}: {res['candidates_evaluated']} evaluated, "
              f"{sum(res['candidates_skipped'].values())} skipped, "
              f"technologies {list(res['by_technology'])}")
        for reason, n in res["candidates_skipped"].items():
            print(f"      skipped {n}: {reason}")

    out = EVIDENCE / "candidate_economics.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
