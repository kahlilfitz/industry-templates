#!/usr/bin/env python3
"""item_age - deterministic risk, decision and action ageing engine.

Reads a ps.client-status-qbr.v1 payload and writes the same contract with aged_items
populated. The model may summarize the result, but it never sets age buckets or
client-action classification itself.

Constants mirror references/status-reporting-rules.md by section number.
"""
import argparse
import copy
from datetime import date
import json
import sys

ENGINE = "engine:item_age"
CONFIDENCE_FLOOR = 0.75          # status-reporting-rules.md #1.3
RISK_STALE_DAYS = 45             # status-reporting-rules.md #5.1
RISK_CRITICAL_DAYS = 90          # status-reporting-rules.md #5.2
DECISION_OVERDUE_DAYS = 7        # status-reporting-rules.md #5.3
ACTION_OVERDUE_DAYS = 7          # status-reporting-rules.md #5.4
CLIENT_BLOCKER_RECLASSIFIES = True  # status-reporting-rules.md #5.5


def parse_date(value):
    return date.fromisoformat(value)


def age_days(as_of, opened):
    return (parse_date(as_of) - parse_date(opened)).days


def days_past_due(as_of, due):
    if not due:
        return 0
    return max(0, (parse_date(as_of) - parse_date(due)).days)


def is_open(item):
    return item.get("status", "").lower() not in ("closed", "done", "cancelled", "approved")


def base_record(item, as_of, bucket, reason, rule, client_action=False):
    return {
        "id": item["id"],
        "title": item["title"],
        "age_days": age_days(as_of, item["opened_date"]),
        "days_past_due": days_past_due(as_of, item.get("due_date")),
        "bucket": bucket,
        "owner_type": item.get("owner_type", "internal"),
        "client_action": bool(client_action),
        "reason": reason,
        "source": ENGINE,
        "confidence": item.get("confidence", 1.0),
        "citation": f"{rule}; {item.get('citation', 'UNCITED')}",
    }


def classify_risk(item, as_of, escalations):
    age = age_days(as_of, item["opened_date"])
    if age >= RISK_CRITICAL_DAYS:
        bucket = "critical_age"
        reason = f"open risk aged {age} days, >= {RISK_CRITICAL_DAYS}-day escalation threshold"
        rule = "status-reporting-rules.md #5.2"
        escalations.append(f"{item['id']}: open risk aged {age} days - re-rate required ({rule})")
    elif age >= RISK_STALE_DAYS:
        bucket = "stale"
        reason = f"open risk aged {age} days, >= {RISK_STALE_DAYS}-day stale threshold"
        rule = "status-reporting-rules.md #5.1"
    else:
        bucket = "current"
        reason = f"open risk aged {age} days, below stale threshold"
        rule = "status-reporting-rules.md #5.1"
    return base_record(item, as_of, bucket, reason, rule)


def classify_decision(item, as_of, escalations):
    past_due = days_past_due(as_of, item.get("due_date"))
    if past_due >= DECISION_OVERDUE_DAYS:
        bucket = "overdue"
        reason = f"decision is {past_due} days past due, >= {DECISION_OVERDUE_DAYS}-day threshold"
        rule = "status-reporting-rules.md #5.3"
        escalations.append(f"{item['id']}: decision {past_due} days overdue ({rule})")
    else:
        bucket = "pending"
        reason = f"decision pending, {past_due} days past due"
        rule = "status-reporting-rules.md #5.3"
    return base_record(item, as_of, bucket, reason, rule, client_action=item.get("owner_type") == "client")


def classify_action(item, decisions_by_id, as_of, escalations):
    past_due = days_past_due(as_of, item.get("due_date"))
    blocked_decision = decisions_by_id.get(item.get("blocked_by_decision_id", ""))
    client_action = item.get("owner_type") == "client"
    if CLIENT_BLOCKER_RECLASSIFIES and (
        item.get("blocker_type") == "client_decision" or (blocked_decision and blocked_decision.get("owner_type") == "client")
    ):
        client_action = True
    if past_due >= ACTION_OVERDUE_DAYS:
        bucket = "overdue"
        rule = "status-reporting-rules.md #5.4"
        reason = f"action is {past_due} days past due, >= {ACTION_OVERDUE_DAYS}-day threshold"
        escalations.append(f"{item['id']}: action {past_due} days overdue ({rule})")
    else:
        bucket = "open"
        rule = "status-reporting-rules.md #5.4"
        reason = f"action open, {past_due} days past due"
    if client_action and item.get("owner_type") != "client":
        rule += ",#5.5"
        reason += "; reclassified as pending client action because blocker is a client decision"
        escalations.append(
            f"{item['id']}: logged as {item.get('owner_type')} but blocked by client decision - "
            "classified as pending client action (status-reporting-rules.md #5.5)"
        )
    return base_record(item, as_of, bucket, reason, rule, client_action=client_action)


def main():
    parser = argparse.ArgumentParser(description="Age risks, decisions and actions deterministically.")
    parser.add_argument("--input", required=True, help="ps.client-status-qbr.v1 JSON input")
    parser.add_argument("--out", required=True, help="output JSON path")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("contract_version") != "ps.client-status-qbr.v1":
        raise ValueError("wrong contract version")

    output = copy.deepcopy(payload)
    as_of = output["reporting_period"]["end"]
    escalations = list(output.get("escalations", []))
    decisions_by_id = {item["id"]: item for item in output.get("decisions", [])}

    risks = [classify_risk(item, as_of, escalations) for item in output.get("risks", []) if is_open(item)]
    decisions = [classify_decision(item, as_of, escalations) for item in output.get("decisions", []) if is_open(item)]
    actions = [
        classify_action(item, decisions_by_id, as_of, escalations)
        for item in output.get("actions", [])
        if is_open(item)
    ]
    pending_client_actions = [item for item in actions if item["client_action"]]

    low_confidence = [
        item["id"]
        for item in output.get("risks", []) + output.get("decisions", []) + output.get("actions", [])
        if item.get("confidence", 1.0) < CONFIDENCE_FLOOR
    ]
    for item_id in low_confidence:
        escalations.append(
            f"{item_id}: extraction confidence below {CONFIDENCE_FLOOR} - human review required "
            "(status-reporting-rules.md #1.3)"
        )

    confidence_values = [
        item.get("confidence", 1.0)
        for item in output.get("risks", []) + output.get("decisions", []) + output.get("actions", [])
    ]
    output["aged_items"] = {
        "risks": risks,
        "decisions": decisions,
        "actions": actions,
        "pending_client_actions": pending_client_actions,
        "source": ENGINE,
        "confidence": round(min(confidence_values), 2) if confidence_values else 1.0,
        "citation": "status-reporting-rules.md #5.1-#5.5",
    }
    output["escalations"] = escalations
    output.setdefault("provenance", {}).setdefault("engines", []).append("item_age/1.0")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)
        handle.write("\n")
    print(
        "item_age: "
        f"{len(risks)} risk(s), {len(decisions)} decision(s), {len(actions)} action(s), "
        f"{len(pending_client_actions)} pending_client_action(s), escalations={len(escalations)} -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
