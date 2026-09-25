#!/usr/bin/env python3
"""item_age - deterministic risk, decision and action ageing engine.

Reads a ps.client-status-qbr.v1 payload and writes the same contract with aged_items
populated. The model may summarize the result, but it never sets age buckets or
client-action classification itself.

Constants mirror references/status-reporting-rules.md by section number. The user may
override the four ageing thresholds for one run via settings.thresholds, within the
bounds of #8.1; every override is disclosed as an escalation.
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

# The only ageing thresholds a user may change in conversation, with the bounds the
# contract enforces (#8.1). Re-checked here so an unvalidated payload cannot run on an
# out-of-range value.
OVERRIDABLE = {
    "risk_stale_days": ("RISK_STALE_DAYS", 7, 179, "#5.1"),
    "risk_critical_days": ("RISK_CRITICAL_DAYS", 14, 180, "#5.2"),
    "decision_overdue_days": ("DECISION_OVERDUE_DAYS", 1, 30, "#5.3"),
    "action_overdue_days": ("ACTION_OVERDUE_DAYS", 1, 30, "#5.4"),
}
PAIRS = [("risk_stale_days", "risk_critical_days")]


class SettingsError(ValueError):
    pass


def apply_settings(payload, escalations):
    """Merge user ageing thresholds over the published defaults and disclose every change.

    Returns (thresholds_applied, thresholds_source). Keys that belong to variance_calc
    are ignored here; that engine applies and discloses its own.
    """
    requested = (payload.get("settings") or {}).get("thresholds") or {}
    defaults = {key: globals()[name] for key, (name, _lo, _hi, _rule) in OVERRIDABLE.items()}
    applied = dict(defaults)
    for key, value in requested.items():
        if key not in OVERRIDABLE:
            continue
        _name, lo, hi, _rule = OVERRIDABLE[key]
        if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
            raise SettingsError(
                f"settings.thresholds.{key} = {value!r} must be a whole number of days in the "
                f"range {lo}-{hi} (status-reporting-rules.md #8.1)"
            )
        applied[key] = value
    for low, high in PAIRS:
        if applied[low] >= applied[high]:
            raise SettingsError(
                f"settings.thresholds: {low} ({applied[low]}) must be below {high} "
                f"({applied[high]}) (status-reporting-rules.md #8.1)"
            )
    source = "default"
    for key, (name, _lo, _hi, rule) in OVERRIDABLE.items():
        globals()[name] = applied[key]
        if applied[key] != defaults[key]:
            source = "user"
            add_escalation(
                escalations,
                f"settings: custom threshold {key} = {applied[key]} (published default "
                f"{defaults[key]}, {rule}) was set by the user for this run - this pack does not "
                "use the published thresholds, so state that before sharing it "
                "(status-reporting-rules.md #8.1)",
            )
    return applied, source


def parse_date(value):
    return date.fromisoformat(value)


def norm_date(value):
    """Normalise a date field to a real value or None.

    A blank or whitespace-only string is the shape that silently reads as "no date
    recorded" in one place and as "present" in another. Collapsing it to None here
    means every caller agrees, and the gap is escalated rather than swallowed.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def age_days(as_of, opened):
    """Returns None when the open date is missing so the caller must escalate
    rather than inventing an age."""
    opened = norm_date(opened)
    if not opened:
        return None
    return (parse_date(as_of) - parse_date(opened)).days


def days_past_due(as_of, due):
    """Returns None when no due date is recorded. A missing due date is not the
    same as "not overdue" and must never be reported as zero days past due."""
    due = norm_date(due)
    if not due:
        return None
    return max(0, (parse_date(as_of) - parse_date(due)).days)


def add_escalation(escalations, message):
    """Escalations are de-duplicated so re-running the engine on its own output
    is idempotent."""
    if message not in escalations:
        escalations.append(message)


def note_missing_opened_date(item, kind, escalations):
    """Every kind of item escalates a missing open date, not just risks."""
    add_escalation(
        escalations,
        f"{item.get('id', '(unknown id)')}: open {kind} has no opened_date - age cannot be "
        "computed and the open date must be confirmed with the item owner "
        "(status-reporting-rules.md #1.1)",
    )


def is_open(item):
    return str(item.get("status") or "").lower() not in (
        "closed",
        "done",
        "cancelled",
        "approved",
    )


def base_record(item, as_of, bucket, reason, rule, client_action=False, kind="item"):
    age = age_days(as_of, item.get("opened_date"))
    return {
        "id": item["id"],
        "kind": kind,
        "title": item.get("title", "(untitled)"),
        "age_days": age,
        "days_past_due": days_past_due(as_of, item.get("due_date")),
        "due_date_known": norm_date(item.get("due_date")) is not None,
        "bucket": bucket,
        "owner_type": item.get("owner_type", "internal"),
        "client_action": bool(client_action),
        "reason": reason,
        "source": ENGINE,
        "confidence": item.get("confidence", 1.0),
        "citation": f"{rule}; {item.get('citation', 'UNCITED')}",
    }


def check_common(item, as_of, kind, escalations):
    """Data-quality checks that apply to risks, decisions and actions alike."""
    if "title" not in item:
        add_escalation(
            escalations,
            f"{item.get('id', '(unknown id)')}: open {kind} has no title - reported as "
            "'(untitled)' and must be labelled before the pack goes out "
            "(status-reporting-rules.md #1.1)",
        )
    age = age_days(as_of, item.get("opened_date"))
    if age is not None and age < 0:
        add_escalation(
            escalations,
            f"{item['id']}: open {kind} has an opened_date after the reporting period end "
            f"({item.get('opened_date')} > {as_of}), giving a negative age - this is a data "
            "error and must be corrected at source (status-reporting-rules.md #1.1)",
        )


def classify_risk(item, as_of, escalations):
    check_common(item, as_of, "risk", escalations)
    age = age_days(as_of, item.get("opened_date"))
    rule = "status-reporting-rules.md #5.1"
    if age is None:
        bucket = "unknown_age"
        reason = "open risk has no opened_date, so age cannot be computed"
        note_missing_opened_date(item, "risk", escalations)
    elif age >= RISK_CRITICAL_DAYS:
        bucket = "critical_age"
        reason = f"open risk aged {age} days, >= {RISK_CRITICAL_DAYS}-day escalation threshold"
        rule = "status-reporting-rules.md #5.2"
        add_escalation(
            escalations, f"{item['id']}: open risk aged {age} days - re-rate required ({rule})"
        )
    elif age >= RISK_STALE_DAYS:
        bucket = "stale"
        reason = f"open risk aged {age} days, >= {RISK_STALE_DAYS}-day stale threshold"
    else:
        bucket = "current"
        reason = f"open risk aged {age} days, below stale threshold"
    return base_record(item, as_of, bucket, reason, rule, kind="risk")


def classify_decision(item, as_of, escalations):
    check_common(item, as_of, "decision", escalations)
    if norm_date(item.get("opened_date")) is None:
        note_missing_opened_date(item, "decision", escalations)
    past_due = days_past_due(as_of, item.get("due_date"))
    rule = "status-reporting-rules.md #5.3"
    if past_due is None:
        bucket = "undated"
        reason = "decision pending with no due date recorded, so overdue status cannot be computed"
        add_escalation(
            escalations,
            f"{item['id']}: open decision has no due_date - overdue status cannot be computed and "
            f"the decision date must be confirmed with the owner ({rule})",
        )
    elif past_due >= DECISION_OVERDUE_DAYS:
        bucket = "overdue"
        reason = f"decision is {past_due} days past due, >= {DECISION_OVERDUE_DAYS}-day threshold"
        add_escalation(escalations, f"{item['id']}: decision {past_due} days overdue ({rule})")
    else:
        bucket = "pending"
        reason = f"decision pending, {past_due} days past due"
    return base_record(
        item,
        as_of,
        bucket,
        reason,
        rule,
        client_action=item.get("owner_type") == "client",
        kind="decision",
    )


def classify_action(item, decisions_by_id, as_of, escalations):
    check_common(item, as_of, "action", escalations)
    if norm_date(item.get("opened_date")) is None:
        note_missing_opened_date(item, "action", escalations)
    past_due = days_past_due(as_of, item.get("due_date"))
    referenced = decisions_by_id.get(item.get("blocked_by_decision_id", ""))
    # Only an OPEN client decision still blocks. Once the client has decided, the
    # action is ours again and must not sit in pending client actions (#5.5).
    blocker_resolved = referenced is not None and not is_open(referenced)
    blocked_decision = referenced if (referenced is not None and is_open(referenced)) else None
    if blocker_resolved:
        add_escalation(
            escalations,
            f"{item['id']}: still open but its blocking decision "
            f"{referenced['id']} is {referenced.get('status', 'resolved')} - this is no longer a "
            "pending client action and the owner must be confirmed "
            "(status-reporting-rules.md #5.5)",
        )
    client_action = item.get("owner_type") == "client"
    if (
        CLIENT_BLOCKER_RECLASSIFIES
        and not blocker_resolved
        and (
            item.get("blocker_type") == "client_decision"
            or (blocked_decision and blocked_decision.get("owner_type") == "client")
        )
    ):
        client_action = True
    rule = "status-reporting-rules.md #5.4"
    if past_due is None:
        bucket = "undated"
        reason = "action open with no due date recorded, so overdue status cannot be computed"
        add_escalation(
            escalations,
            f"{item['id']}: open action has no due_date - overdue status cannot be computed and "
            f"the due date must be confirmed with the owner ({rule})",
        )
    elif past_due >= ACTION_OVERDUE_DAYS:
        bucket = "overdue"
        reason = f"action is {past_due} days past due, >= {ACTION_OVERDUE_DAYS}-day threshold"
        add_escalation(escalations, f"{item['id']}: action {past_due} days overdue ({rule})")
    else:
        bucket = "open"
        reason = f"action open, {past_due} days past due"
    if client_action and item.get("owner_type") != "client":
        rule += ",#5.5"
        reason += "; reclassified as pending client action because blocker is a client decision"
        add_escalation(
            escalations,
            f"{item['id']}: logged as {item.get('owner_type')} but blocked by client decision - "
            "classified as pending client action (status-reporting-rules.md #5.5)",
        )
    return base_record(item, as_of, bucket, reason, rule, client_action=client_action, kind="action")


def main():
    parser = argparse.ArgumentParser(description="Age risks, decisions and actions deterministically.")
    parser.add_argument("--input", required=True, help="ps.client-status-qbr.v1 JSON input")
    parser.add_argument("--out", required=True, help="output JSON path")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as handle:
        payload = json.load(handle)
    found = payload.get("contract_version")
    if found != "ps.client-status-qbr.v1":
        print(
            f"item_age: expected contract_version 'ps.client-status-qbr.v1' but found {found!r} "
            f"in {args.input}. Run plan-retrieve first to build a valid payload.",
            file=sys.stderr,
        )
        return 2

    output = copy.deepcopy(payload)
    if "reporting_period" not in output or "end" not in output.get("reporting_period", {}):
        print(
            "item_age: missing required field 'reporting_period.end' - run plan-retrieve first "
            "to populate it.",
            file=sys.stderr,
        )
        return 1
    as_of = output["reporting_period"]["end"]
    escalations = list(output.get("escalations", []))
    try:
        thresholds_applied, thresholds_source = apply_settings(output, escalations)
    except SettingsError as exc:
        print(
            f"item_age: {exc}. Ask the user for a value inside the range, then re-run. "
            "Do not age the items by hand.",
            file=sys.stderr,
        )
        return 2
    decisions_by_id = {item["id"]: item for item in output.get("decisions", [])}

    # An empty RAID register is almost always a retrieval failure, not a project
    # with no risks. It must never be reported as "no risks" (#5.1,#1.1).
    if not (output.get("risks") or output.get("decisions") or output.get("actions")):
        add_escalation(
            escalations,
            "RAID register is empty: no risks, decisions or actions were supplied. This is far "
            "more likely to be a retrieval gap than a project with none, so it must not be "
            "reported as 'no open risks' - confirm the register location with the delivery lead "
            "(status-reporting-rules.md #1.1,#5.1)",
        )

    risks = [classify_risk(item, as_of, escalations) for item in output.get("risks", []) if is_open(item)]
    decisions = [classify_decision(item, as_of, escalations) for item in output.get("decisions", []) if is_open(item)]
    actions = [
        classify_action(item, decisions_by_id, as_of, escalations)
        for item in output.get("actions", [])
        if is_open(item)
    ]
    # A pending client action is anything the client still owes us, whether it is
    # logged as an action or as an unmade client decision (#5.5).
    pending_client_actions = [item for item in actions + decisions if item["client_action"]]

    open_items = [
        item
        for item in output.get("risks", []) + output.get("decisions", []) + output.get("actions", [])
        if is_open(item)
    ]
    for item in open_items:
        if item.get("confidence", 1.0) < CONFIDENCE_FLOOR:
            add_escalation(
                escalations,
                f"{item['id']}: extraction confidence below {CONFIDENCE_FLOOR} - human review required "
                "(status-reporting-rules.md #1.3)",
            )

    confidence_values = [item.get("confidence", 1.0) for item in open_items]
    output["aged_items"] = {
        "risks": risks,
        "decisions": decisions,
        "actions": actions,
        "pending_client_actions": pending_client_actions,
        "source": ENGINE,
        "confidence": round(min(confidence_values), 2) if confidence_values else 1.0,
        "citation": "status-reporting-rules.md #5.1-#5.5",
        "thresholds_applied": thresholds_applied,
        "thresholds_source": thresholds_source,
    }
    output["escalations"] = escalations
    engines = output.setdefault("provenance", {}).setdefault("engines", [])
    if "item_age/1.0" not in engines:
        engines.append("item_age/1.0")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)
        handle.write("\n")
    print(
        "item_age: "
        f"{len(risks)} risk(s), {len(decisions)} decision(s), {len(actions)} action(s), "
        f"{len(pending_client_actions)} pending_client_action(s), escalations={len(escalations)} -> {args.out}"
    )
    return 0


def _fatal(message):
    print(f"item_age: {message}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except FileNotFoundError as exc:
        sys.exit(_fatal(
            f"cannot open {exc.filename} - check --input and --out, and that SKILL_DIR points "
            "at this skill's folder. This is a path error, not a data error: fix the path and "
            "re-run. Do not age the items by hand."
        ))
    except json.JSONDecodeError as exc:
        sys.exit(_fatal(
            f"{sys.argv[sys.argv.index('--input') + 1] if '--input' in sys.argv else 'the input'}"
            f" is not valid JSON ({exc}) - the previous step most likely wrote prose instead of "
            "a payload. Re-run the owning skill."
        ))
    except AttributeError:
        sys.exit(_fatal(
            "the payload is not a JSON object with the expected blocks - run "
            "validate_payload.py to see which block is wrong, then re-run the owning skill."
        ))
    except KeyError as exc:
        sys.exit(_fatal(
            f"the payload is missing the required key {exc}. Re-run the skill that owns that "
            "field so it is populated from a source document. Do not age the items by hand."
        ))
    except (TypeError, ValueError) as exc:
        sys.exit(_fatal(
            f"the payload holds a value of the wrong type ({exc}). A date field most likely is "
            "not ISO YYYY-MM-DD, or a count contains text. Correct the source record and "
            "re-run. Do not age the items by hand."
        ))
