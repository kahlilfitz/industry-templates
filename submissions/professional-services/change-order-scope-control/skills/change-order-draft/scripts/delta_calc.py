#!/usr/bin/env python3
"""Deterministic effort, cost and cumulative drift calculator."""
import argparse
import json
import sys

ENGINE = "engine:delta_calc"
CONTINGENCY_PCT = 0.15  # effort-cost-delta-method.md #3.2
DRIFT_ESCALATION_MIN_AMOUNT = 10000.0  # effort-cost-delta-method.md #4.1
DRIFT_ESCALATION_THRESHOLD_PCT = 2.0  # effort-cost-delta-method.md #4.1


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def money(value):
    return round(float(value) + 0.0000001, 2)


def rate_map(rate_card):
    return {r["role"]: r["hourly_rate"] for r in rate_card.get("rates", [])}


def request_by_id(payload):
    return {r["request_id"]: r for r in payload.get("requests", [])}


def class_by_id(payload):
    return {c["request_id"]: c for c in payload.get("classifications", [])}


def calc_line(request, classification, rates, rate_citation):
    parts = []
    base = 0.0
    missing = []
    for role, hours in request.get("estimate_hours", {}).items():
        if role not in rates:
            missing.append(role)
            continue
        cost = hours * rates[role]
        base += cost
        parts.append(f"{hours:g}h {role} x ${rates[role]:g} = ${money(cost):,.2f}")
    if missing:
        raise ValueError(f"{request['request_id']}: missing rate-card role(s): {', '.join(sorted(missing))}")
    base = money(base)
    contingency = money(base * CONTINGENCY_PCT) if classification["classification"] in {"OUT_OF_SCOPE", "AMBIGUOUS"} else 0.0
    total = money(base + contingency) if classification["classification"] in {"OUT_OF_SCOPE", "AMBIGUOUS"} else 0.0
    included = classification["classification"] == "OUT_OF_SCOPE"
    calculation = "; ".join(parts)
    if classification["classification"] in {"OUT_OF_SCOPE", "AMBIGUOUS"}:
        calculation += f"; contingency {CONTINGENCY_PCT:.0%} = ${contingency:,.2f}"
    else:
        calculation += "; covered by SOW, no change-order amount"
    return {
        "request_id": request["request_id"],
        "summary": request["summary"],
        "classification": classification["classification"],
        "base_cost": base,
        "contingency": contingency,
        "total_cost": total,
        "included_in_change_order": included,
        "calculation": calculation,
        "source": ENGINE,
        "citation": f"{classification['citation']}; {rate_citation}; {classification['rule']}; effort-cost-delta-method.md #2.1,#3.1,#3.2",
        "confidence": min(request.get("confidence", 0.0), classification.get("confidence", 0.0))
    }


def main():
    parser = argparse.ArgumentParser(description="Calculate effort/cost delta and cumulative scope drift.")
    parser.add_argument("--classified", required=True, help="classified.json from scope_classify.py")
    parser.add_argument("--rate-card", required=True, help="Rate-card JSON")
    parser.add_argument("--out", required=True, help="Output change-order.json path")
    args = parser.parse_args()

    payload = load(args.classified)
    rate_card = load(args.rate_card)
    assert payload["contract_version"] == "ps.change-order-scope-control.v1", "wrong contract version"
    assert rate_card["contract_version"] == "ps.change-order-scope-control.v1", "wrong rate-card contract version"

    rates = rate_map(rate_card)
    requests = request_by_id(payload)
    classes = class_by_id(payload)
    deltas = []
    escalations = list(payload.get("escalations", []))
    for request_id, classification in classes.items():
        deltas.append(calc_line(requests[request_id], classification, rates, rate_card["rate_card"]["citation"]))

    current_base = money(sum(d["base_cost"] for d in deltas if d["included_in_change_order"]))
    current_contingency = money(sum(d["contingency"] for d in deltas if d["included_in_change_order"]))
    current_total = money(sum(d["total_cost"] for d in deltas if d["included_in_change_order"]))
    ambiguous_exposure = money(sum(d["total_cost"] for d in deltas if d["classification"] == "AMBIGUOUS"))
    prior_no_charge = money(sum(co.get("internal_cost", 0.0) for co in payload.get("prior_change_orders", []) if co.get("commercial_disposition") == "no_charge_accommodation"))
    contract_value = payload.get("engagement", {}).get("contract_value", 0.0)
    drift_threshold = money(max(DRIFT_ESCALATION_MIN_AMOUNT, contract_value * DRIFT_ESCALATION_THRESHOLD_PCT / 100.0))
    cumulative = money(prior_no_charge + current_total)
    escalated = cumulative > drift_threshold
    if escalated:
        escalations.append(
            f"Cumulative scope drift ${cumulative:,.2f} exceeds threshold ${drift_threshold:,.2f} "
            f"(effort-cost-delta-method.md #4.1)"
        )

    payload["deltas"] = deltas
    payload["change_order_draft"] = {
        "draft_status": "DRAFT - human review required; not issued to client",
        "title": f"Draft Change Order - {payload['engagement']['project_name']}",
        "included_request_ids": [d["request_id"] for d in deltas if d["included_in_change_order"]],
        "excluded_ambiguous_request_ids": [d["request_id"] for d in deltas if d["classification"] == "AMBIGUOUS"],
        "subtotal_before_contingency": current_base,
        "contingency": current_contingency,
        "total_change_order_amount": current_total,
        "boundary": "Determination and drafting only. Does not accept a change, commit effort, reprice the engagement or issue the change order."
    }
    payload["cumulative_drift"] = {
        "prior_no_charge_accommodation": prior_no_charge,
        "current_out_of_scope_total": current_total,
        "ambiguous_potential_exposure": ambiguous_exposure,
        "cumulative_margin_erosion_at_risk": cumulative,
        "contract_value": contract_value,
        "drift_threshold_amount": drift_threshold,
        "escalation_required": escalated,
        "citation": "effort-cost-delta-method.md #4.1,#4.2,#4.3",
        "source": ENGINE,
        "confidence": min((d["confidence"] for d in deltas), default=1.0)
    }
    payload["escalations"] = escalations
    payload.setdefault("provenance", {}).setdefault("engines", []).append("delta_calc/1.0")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"delta_calc: change_order_total=${current_total:,.2f}, cumulative_drift=${cumulative:,.2f}, escalated={escalated} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
