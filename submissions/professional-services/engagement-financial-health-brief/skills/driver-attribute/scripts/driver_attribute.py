#!/usr/bin/env python3
"""driver_attribute - deterministic variance decomposition engine.

Reads health_calc output and decomposes the largest variance into arithmetic components.
The components must reconcile to the total variance; the model may only narrate the output.
"""
import argparse
import json
import sys

ENGINE = "engine:driver_attribute"
CONTRACT_VERSION = "ps.engagement-financial-health-brief.v1"
EAC_DECOMP_RULE = "engagement-financial-metric-definitions.md #6.1"
WIP_DECOMP_RULE = "engagement-financial-metric-definitions.md #6.2"
MODEL_BOUNDARY_RULE = "engagement-financial-metric-definitions.md #6.3"
ROUNDING_TOLERANCE = 0.01  # engagement-financial-metric-definitions.md #6.1


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def money(value):
    return round(float(value) + 0.0000001, 2)


def component_table(components):
    ranked = []
    for item in components:
        ranked.append({
            "name": item["name"],
            "amount": money(item["amount"]),
            "rank_basis": abs(money(item["amount"])),
            "source": ENGINE,
            "citation": item.get("citation", EAC_DECOMP_RULE),
            "confidence": 0.97
        })
    ranked.sort(key=lambda row: row["rank_basis"], reverse=True)
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx
    return ranked


def main():
    parser = argparse.ArgumentParser(description="Decompose the largest engagement financial variance.")
    parser.add_argument("--health", required=True, help="health.json from health_calc.py")
    parser.add_argument("--out", required=True, help="Output drivers.json path")
    args = parser.parse_args()

    payload = load(args.health)
    assert payload["contract_version"] == CONTRACT_VERSION, "wrong contract version"

    eac_total = money(payload["forecast"]["eac_variance_amount"])
    wip_total = money(payload["wip_ageing"]["collectability_reserve"])
    basis = payload.get("driver_basis", {})
    escalations = list(payload.get("escalations", []))

    if abs(eac_total) >= abs(wip_total):
        largest = "EAC cost variance to plan"
        total = eac_total
        components = component_table(basis.get("eac_components", []))
        citation = EAC_DECOMP_RULE
    else:
        largest = "WIP collectability reserve"
        total = wip_total
        components = component_table([
            {"name": "wip_reserve_" + row["bucket"].replace("+", "_plus").replace("-", "_"),
             "amount": row["reserve_amount"],
             "citation": row["citation"] + "; " + WIP_DECOMP_RULE}
            for row in basis.get("wip_reserve_components", [])
        ])
        citation = WIP_DECOMP_RULE

    component_sum = money(sum(row["amount"] for row in components))
    delta = money(component_sum - total)
    reconciles = abs(delta) <= ROUNDING_TOLERANCE
    if not reconciles:
        escalations.append(
            f"Driver attribution does not reconcile: components ${component_sum:,.2f} vs total ${total:,.2f}; "
            f"delta ${delta:,.2f} ({citation})"
        )

    payload["driver_attribution"] = {
        "largest_variance": largest,
        "total_variance": total,
        "component_sum": component_sum,
        "components": components,
        "reconciles": reconciles,
        "reconciliation_delta": delta,
        "source": ENGINE,
        "citation": citation + "; " + MODEL_BOUNDARY_RULE,
        "confidence": 0.97
    }
    payload["wip_reserve_decomposition"] = {
        "total_reserve": wip_total,
        "components": [
            {
                "bucket": row["bucket"],
                "amount": row["amount"],
                "reserve_pct": row["reserve_pct"],
                "reserve_amount": row["reserve_amount"],
                "source": ENGINE,
                "citation": row["citation"] + "; " + WIP_DECOMP_RULE,
                "confidence": 0.97
            }
            for row in basis.get("wip_reserve_components", [])
        ],
        "reconciles": money(sum(row["reserve_amount"] for row in basis.get("wip_reserve_components", []))) == wip_total,
        "source": ENGINE,
        "citation": WIP_DECOMP_RULE,
        "confidence": 0.97
    }
    payload["escalations"] = escalations
    payload.setdefault("provenance", {}).setdefault("engines", []).append("driver_attribute/1.0")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(
        f"driver_attribute: largest='{largest}', total=${total:,.2f}, "
        f"components=${component_sum:,.2f}, reconciles={reconciles} -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
