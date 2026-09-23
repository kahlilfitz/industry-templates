#!/usr/bin/env python3
"""variance_calc - deterministic schedule, budget and scope variance engine.

Reads a ps.client-status-qbr.v1 payload and writes the same contract with
variance_summary populated. Same input, same output: no network, no model calls,
no randomness. The model quotes these values; it never computes RAG or variance.

Constants mirror references/status-reporting-rules.md by section number.
"""
import argparse
import copy
from datetime import date
import json
import sys

ENGINE = "engine:variance_calc"
CONFIDENCE_FLOOR = 0.75             # status-reporting-rules.md #1.3
SCHEDULE_AMBER_DAYS = 5             # status-reporting-rules.md #2.1
SCHEDULE_RED_DAYS = 10              # status-reporting-rules.md #2.2
REBASELINE_CHECK_REQUIRED = True     # status-reporting-rules.md #2.3
BUDGET_AMBER_PCT = 5.0              # status-reporting-rules.md #3.1
BUDGET_RED_PCT = 10.0               # status-reporting-rules.md #3.2
INCLUDE_UNBILLED_WIP = True          # status-reporting-rules.md #3.3
SCOPE_AMBER_OPEN_ITEMS = 1           # status-reporting-rules.md #4.1
SCOPE_RED_OPEN_ITEMS = 3             # status-reporting-rules.md #4.2
ROLLUP_ORDER = ["green", "amber", "red"]  # status-reporting-rules.md #6.1


def parse_date(value):
    return date.fromisoformat(value)


def days_between(later, earlier):
    return (parse_date(later) - parse_date(earlier)).days


def pct(numerator, denominator):
    if denominator == 0:
        return 0.0
    return round(100.0 * numerator / denominator, 2)


def rag_from_threshold(value, amber, red):
    if value >= red:
        return "red"
    if value >= amber:
        return "amber"
    return "green"


def worst(*rags):
    return max(rags, key=ROLLUP_ORDER.index)


def schedule_summary(payload, escalations):
    prior = {
        item["id"]: item for item in payload.get("prior_status", {}).get("milestones", [])
    }
    facts = []
    rag = "green"
    confidence = 1.0
    for milestone in payload["plan"]["milestones"]:
        original_variance_days = days_between(
            milestone["current_forecast_date"], milestone["original_baseline_date"]
        )
        prior_item = prior.get(milestone["id"])
        period_delta_days = (
            days_between(milestone["current_forecast_date"], prior_item["forecast_date"])
            if prior_item
            else 0
        )
        current_baseline = milestone.get("current_baseline_date", milestone["original_baseline_date"])
        rebaselined = bool(milestone.get("rebaselined_last_period")) or (
            current_baseline != milestone["original_baseline_date"]
        )
        milestone_rag = rag_from_threshold(
            max(original_variance_days, 0), SCHEDULE_AMBER_DAYS, SCHEDULE_RED_DAYS
        )
        if rebaselined and REBASELINE_CHECK_REQUIRED and milestone.get("reported_rag") == "green" and milestone_rag != "green":
            escalations.append(
                f"{milestone['id']}: reported green after rebaseline, but forecast is "
                f"{original_variance_days} days against original baseline "
                "(status-reporting-rules.md #2.3)"
            )
        if milestone.get("confidence", 1.0) < CONFIDENCE_FLOOR:
            milestone_rag = worst(milestone_rag, "amber")
            escalations.append(
                f"{milestone['id']}: extraction confidence {milestone.get('confidence')} below "
                f"{CONFIDENCE_FLOOR} - schedule human review required "
                "(status-reporting-rules.md #1.3)"
            )
        confidence = min(confidence, milestone.get("confidence", 1.0))
        rag = worst(rag, milestone_rag)
        facts.append(
            {
                "id": milestone["id"],
                "name": milestone["name"],
                "reported_rag": milestone.get("reported_rag"),
                "computed_rag": milestone_rag,
                "original_baseline_date": milestone["original_baseline_date"],
                "current_forecast_date": milestone["current_forecast_date"],
                "original_variance_days": original_variance_days,
                "period_delta_days": period_delta_days,
                "rebaselined_last_period": rebaselined,
                "source": ENGINE,
                "confidence": milestone.get("confidence", 1.0),
                "citation": (
                    "status-reporting-rules.md #2.1,#2.2,#2.3,#2.4; "
                    + milestone.get("citation", "UNCITED")
                ),
            }
        )
    return {
        "rag": rag,
        "facts": facts,
        "source": ENGINE,
        "confidence": round(confidence, 2),
        "citation": "status-reporting-rules.md #2.1-#2.4",
    }


def budget_summary(payload, escalations):
    budget = payload["budget"]
    planned = budget["planned_burn_to_date"]
    billed = budget["actual_billed_to_date"]
    wip = budget.get("unbilled_wip", 0.0) if INCLUDE_UNBILLED_WIP else 0.0
    actual_with_wip = billed + wip
    burn_variance_amount = actual_with_wip - planned
    burn_variance_pct = pct(burn_variance_amount, planned)
    forecast_variance_amount = budget["forecast_to_complete"] - budget["baseline_budget"]
    forecast_variance_pct = pct(forecast_variance_amount, budget["baseline_budget"])
    prior_forecast = budget.get(
        "previous_forecast_to_complete",
        payload.get("prior_status", {}).get("budget", {}).get("forecast_to_complete", budget["forecast_to_complete"]),
    )
    forecast_period_delta = budget["forecast_to_complete"] - prior_forecast
    largest_variance_pct = max(abs(burn_variance_pct), abs(forecast_variance_pct))
    rag = rag_from_threshold(largest_variance_pct, BUDGET_AMBER_PCT, BUDGET_RED_PCT)
    confidence = budget.get("confidence", 1.0)
    if confidence < CONFIDENCE_FLOOR:
        rag = worst(rag, "amber")
        escalations.append(
            f"budget: extraction confidence {confidence} below {CONFIDENCE_FLOOR} - human review required "
            "(status-reporting-rules.md #1.3)"
        )
    if wip and abs(burn_variance_pct) >= BUDGET_AMBER_PCT:
        escalations.append(
            f"budget: billed-only burn is {billed} but unbilled WIP {wip} changes actual burn to "
            f"{actual_with_wip} ({burn_variance_pct}% vs plan) (status-reporting-rules.md #3.3)"
        )
    return {
        "rag": rag,
        "facts": [
            {
                "currency": budget["currency"],
                "planned_burn_to_date": planned,
                "actual_billed_to_date": billed,
                "unbilled_wip": wip,
                "actual_burn_including_wip": actual_with_wip,
                "burn_variance_amount": round(burn_variance_amount, 2),
                "burn_variance_pct": burn_variance_pct,
                "baseline_budget": budget["baseline_budget"],
                "forecast_to_complete": budget["forecast_to_complete"],
                "forecast_variance_amount": round(forecast_variance_amount, 2),
                "forecast_variance_pct": forecast_variance_pct,
                "forecast_period_delta": round(forecast_period_delta, 2),
                "source": ENGINE,
                "confidence": confidence,
                "citation": (
                    "status-reporting-rules.md #3.1,#3.2,#3.3,#3.4; "
                    + budget.get("citation", "UNCITED")
                ),
            }
        ],
        "source": ENGINE,
        "confidence": round(confidence, 2),
        "citation": "status-reporting-rules.md #3.1-#3.4",
    }


def scope_summary(payload, escalations):
    changes = payload.get("plan", {}).get("scope_changes", [])
    open_changes = [c for c in changes if c.get("status", "").lower() not in ("approved", "closed", "cancelled")]
    client_facing = [c for c in open_changes if c.get("client_facing_impact")]
    rag = "green"
    if len(open_changes) >= SCOPE_RED_OPEN_ITEMS or client_facing:
        rag = "red"
    elif len(open_changes) >= SCOPE_AMBER_OPEN_ITEMS:
        rag = "amber"
    confidence = min([c.get("confidence", 1.0) for c in changes], default=1.0)
    if confidence < CONFIDENCE_FLOOR:
        rag = worst(rag, "amber")
        escalations.append(
            f"scope: extraction confidence {confidence} below {CONFIDENCE_FLOOR} - human review required "
            "(status-reporting-rules.md #1.3,#4.3)"
        )
    facts = []
    for change in open_changes:
        facts.append(
            {
                "id": change["id"],
                "title": change["title"],
                "status": change["status"],
                "client_facing_impact": bool(change.get("client_facing_impact")),
                "impact_days": change.get("impact_days", 0),
                "source": ENGINE,
                "confidence": change.get("confidence", 1.0),
                "citation": (
                    "status-reporting-rules.md #4.1,#4.2; "
                    + change.get("citation", "UNCITED")
                ),
            }
        )
    return {
        "rag": rag,
        "facts": facts,
        "source": ENGINE,
        "confidence": round(confidence, 2),
        "citation": "status-reporting-rules.md #4.1-#4.3",
    }


def main():
    parser = argparse.ArgumentParser(description="Compute deterministic status/QBR variance.")
    parser.add_argument("--input", required=True, help="ps.client-status-qbr.v1 JSON input")
    parser.add_argument("--out", required=True, help="output JSON path")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("contract_version") != "ps.client-status-qbr.v1":
        raise ValueError("wrong contract version")

    output = copy.deepcopy(payload)
    escalations = list(output.get("escalations", []))
    schedule = schedule_summary(output, escalations)
    budget = budget_summary(output, escalations)
    scope = scope_summary(output, escalations)
    overall = worst(schedule["rag"], budget["rag"], scope["rag"])
    output["variance_summary"] = {
        "schedule": schedule,
        "budget": budget,
        "scope": scope,
        "overall_rag": overall,
        "source": ENGINE,
        "confidence": round(min(schedule["confidence"], budget["confidence"], scope["confidence"]), 2),
        "citation": "status-reporting-rules.md #6.1",
    }
    output["escalations"] = escalations
    output.setdefault("provenance", {}).setdefault("engines", []).append("variance_calc/1.0")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)
        handle.write("\n")
    print(
        "variance_calc: "
        f"schedule={schedule['rag']}, budget={budget['rag']}, scope={scope['rag']}, "
        f"overall={overall}, escalations={len(escalations)} -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
