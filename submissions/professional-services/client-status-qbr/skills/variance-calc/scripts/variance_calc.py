#!/usr/bin/env python3
"""variance_calc - deterministic schedule, budget and scope variance engine.

Reads a ps.client-status-qbr.v1 payload and writes the same contract with
variance_summary populated. Same input, same output: no network, no model calls,
no randomness. The model quotes these values; it never computes RAG or variance.

Constants mirror references/status-reporting-rules.md by section number. The user may
override the schedule, budget and scope thresholds for one run via settings.thresholds,
within the bounds of #8.1; every override is disclosed as an escalation.
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

# The only thresholds a user may change in conversation, with the bounds the contract
# enforces (#8.1). The engine re-checks them so a payload that skipped validation
# still cannot run on an out-of-range value.
OVERRIDABLE = {
    "schedule_amber_days": ("SCHEDULE_AMBER_DAYS", 1, 29, "#2.1"),
    "schedule_red_days": ("SCHEDULE_RED_DAYS", 2, 30, "#2.2"),
    "budget_amber_pct": ("BUDGET_AMBER_PCT", 1, 24, "#3.1"),
    "budget_red_pct": ("BUDGET_RED_PCT", 2, 25, "#3.2"),
    "scope_amber_open_items": ("SCOPE_AMBER_OPEN_ITEMS", 1, 4, "#4.1"),
    "scope_red_open_items": ("SCOPE_RED_OPEN_ITEMS", 2, 5, "#4.2"),
}
PAIRS = [
    ("schedule_amber_days", "schedule_red_days"),
    ("budget_amber_pct", "budget_red_pct"),
    ("scope_amber_open_items", "scope_red_open_items"),
]


class SettingsError(ValueError):
    pass


def apply_settings(payload, escalations):
    """Merge user thresholds over the published defaults and disclose every change.

    Returns (thresholds_applied, thresholds_source). Keys that belong to item_age are
    ignored here; that engine applies and discloses its own.
    """
    requested = (payload.get("settings") or {}).get("thresholds") or {}
    defaults = {key: globals()[name] for key, (name, _lo, _hi, _rule) in OVERRIDABLE.items()}
    applied = dict(defaults)
    for key, value in requested.items():
        if key not in OVERRIDABLE:
            continue
        _name, lo, hi, rule = OVERRIDABLE[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
            raise SettingsError(
                f"settings.thresholds.{key} = {value!r} is outside the allowed range {lo}-{hi} "
                "(status-reporting-rules.md #8.1)"
            )
        applied[key] = value
    for amber, red in PAIRS:
        if applied[amber] >= applied[red]:
            raise SettingsError(
                f"settings.thresholds: {amber} ({applied[amber]}) must be below {red} "
                f"({applied[red]}) (status-reporting-rules.md #8.1)"
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


def days_between(later, earlier):
    return (parse_date(later) - parse_date(earlier)).days


def pct(numerator, denominator):
    """Returns None when the denominator is zero so the caller must escalate
    rather than silently reporting 0.0% (and therefore green)."""
    if denominator == 0:
        return None
    return round(100.0 * numerator / denominator, 2)


def add_escalation(escalations, message):
    """Escalations are de-duplicated so re-running the engine on its own output
    is idempotent."""
    if message not in escalations:
        escalations.append(message)


def rag_from_threshold(value, amber, red, strict=False):
    """strict=True applies "more than" (rules #2.1/#2.2, calendar days).
    strict=False applies "at least" (rules #3.1/#3.2, percentages).
    The two rule families genuinely differ; do not collapse them.
    """
    if (value > red) if strict else (value >= red):
        return "red"
    if (value > amber) if strict else (value >= amber):
        return "amber"
    return "green"


def worst(*rags):
    return max(rags, key=ROLLUP_ORDER.index)


def require(payload, path, hop):
    """Returns payload[path] or exits with an actionable message naming the hop
    to re-run. Never let a missing field surface as a raw KeyError traceback."""
    current = payload
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            raise SystemExit(
                f"variance_calc: missing required field '{path}' - run {hop} first to populate it."
            )
        current = current[key]
    return current


def require_milestone_field(milestone, key):
    if key not in milestone:
        raise SystemExit(
            f"variance_calc: milestone {milestone.get('id', '(unknown id)')} is missing "
            f"'{key}' - run plan-retrieve first to populate it."
        )
    return milestone[key]


def schedule_summary(payload, escalations):
    prior = {
        item["id"]: item for item in payload.get("prior_status", {}).get("milestones", [])
    }
    facts = []
    rag = "green"
    confidence = 1.0
    for milestone in require(payload, "plan.milestones", "plan-retrieve"):
        original_baseline = milestone.get("original_baseline_date") or None
        current_forecast = require_milestone_field(milestone, "current_forecast_date")
        baseline_known = original_baseline is not None
        stated_current_baseline = milestone.get("current_baseline_date") or None
        variance_vs_current_baseline_days = (
            days_between(current_forecast, stated_current_baseline)
            if stated_current_baseline
            else None
        )
        if baseline_known:
            original_variance_days = days_between(current_forecast, original_baseline)
        else:
            # One milestone without a first baseline must not halt the whole run and
            # suppress budget, scope and RAID reporting. Masked slippage cannot be
            # tested without it, so the milestone travels as at least amber, floored
            # on its slip against the current baseline.
            original_variance_days = None
            lower = variance_vs_current_baseline_days
            add_escalation(
                escalations,
                f"{milestone['id']}: original baseline not supplied - forecast is "
                f"{lower if lower is not None else 'an unknown number of'} days after the "
                "current baseline (a lower bound); masked slippage cannot be tested and the "
                "first committed date must be confirmed with the delivery lead "
                "(status-reporting-rules.md #2.3)",
            )
        prior_item = prior.get(milestone["id"])
        prior_forecast_date = prior_item.get("forecast_date") if prior_item else None
        if prior_forecast_date:
            period_delta_days = days_between(current_forecast, prior_forecast_date)
        else:
            period_delta_days = None
            reason = (
                "absent from the prior status pack"
                if prior_item is None
                else "present in the prior status pack but carries no forecast_date"
            )
            add_escalation(
                escalations,
                f"{milestone['id']}: {reason} - period-on-period movement cannot be computed "
                "and must be confirmed with the delivery lead "
                "(status-reporting-rules.md #2.4)",
            )
        current_baseline = stated_current_baseline or original_baseline
        if "rebaselined_last_period" in milestone:
            rebaselined = bool(milestone["rebaselined_last_period"])
        elif prior_item and prior_item.get("baseline_date"):
            rebaselined = prior_item["baseline_date"] != current_baseline
        else:
            rebaselined = False
        baseline_moved_since_original = (
            baseline_known and current_baseline != original_baseline
        )
        if baseline_known:
            milestone_rag = rag_from_threshold(
                max(original_variance_days, 0),
                SCHEDULE_AMBER_DAYS,
                SCHEDULE_RED_DAYS,
                strict=True,
            )
        else:
            # Slip against the current baseline is a lower bound on slip against the
            # original, so a large slip must still read red rather than being capped
            # at amber. At least amber either way (#2.3).
            milestone_rag = worst(
                "amber",
                rag_from_threshold(
                    max(variance_vs_current_baseline_days or 0, 0),
                    SCHEDULE_AMBER_DAYS,
                    SCHEDULE_RED_DAYS,
                    strict=True,
                ),
            )
        # Masked slippage: a green label sitting on top of real variance against the
        # ORIGINAL baseline, whether the move happened last period or earlier (#2.3).
        masked = (
            baseline_known
            and milestone.get("reported_rag") == "green"
            and milestone_rag != "green"
        )
        if REBASELINE_CHECK_REQUIRED and masked and rebaselined:
            add_escalation(
                escalations,
                f"{milestone['id']}: reported green after rebaseline, but forecast is "
                f"{original_variance_days} days against original baseline "
                "(status-reporting-rules.md #2.3)",
            )
        elif REBASELINE_CHECK_REQUIRED and masked and baseline_moved_since_original:
            add_escalation(
                escalations,
                f"{milestone['id']}: reported green against a moved baseline "
                f"({current_baseline}), but forecast is {original_variance_days} days against "
                f"original baseline {original_baseline} (status-reporting-rules.md #2.3)",
            )
        if milestone.get("confidence", 1.0) < CONFIDENCE_FLOOR:
            milestone_rag = worst(milestone_rag, "amber")
            add_escalation(
                escalations,
                f"{milestone['id']}: extraction confidence {milestone.get('confidence')} below "
                f"{CONFIDENCE_FLOOR} - schedule human review required "
                "(status-reporting-rules.md #1.3)",
            )
        confidence = min(confidence, milestone.get("confidence", 1.0))
        rag = worst(rag, milestone_rag)
        facts.append(
            {
                "id": milestone["id"],
                "name": milestone.get("name", "(untitled)"),
                "reported_rag": milestone.get("reported_rag"),
                "computed_rag": milestone_rag,
                "original_baseline_date": original_baseline,
                "original_baseline_known": baseline_known,
                "current_forecast_date": current_forecast,
                "original_variance_days": original_variance_days,
                "variance_vs_current_baseline_days": variance_vs_current_baseline_days,
                "period_delta_days": period_delta_days,
                "rebaselined_last_period": rebaselined,
                "baseline_moved_since_original": baseline_moved_since_original,
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
    budget = require(payload, "budget", "burn-pull")
    planned = require(payload, "budget.planned_burn_to_date", "burn-pull")
    billed = require(payload, "budget.actual_billed_to_date", "burn-pull")
    baseline_budget = require(payload, "budget.baseline_budget", "burn-pull")
    forecast_to_complete = require(payload, "budget.forecast_to_complete", "burn-pull")
    # The contract allows unbilled_wip to be null when the export genuinely has no WIP
    # line. Null means UNKNOWN, not zero: billed-only burn is then not authoritative.
    raw_wip = budget.get("unbilled_wip")
    wip_known = raw_wip is not None
    wip = float(raw_wip) if (wip_known and INCLUDE_UNBILLED_WIP) else 0.0
    actual_with_wip = billed + wip
    burn_variance_amount = actual_with_wip - planned
    burn_variance_pct = pct(burn_variance_amount, planned)
    burn_measurable = burn_variance_pct is not None
    if not burn_measurable:
        add_escalation(
            escalations,
            f"budget: planned burn to date is 0 but actual burn including WIP is {actual_with_wip} - "
            "burn variance cannot be computed and must be confirmed with the engagement "
            "financial analyst (status-reporting-rules.md #3.1)",
        )
    forecast_variance_amount = forecast_to_complete - baseline_budget
    forecast_variance_pct = pct(forecast_variance_amount, baseline_budget)
    forecast_measurable = forecast_variance_pct is not None
    if not forecast_measurable:
        add_escalation(
            escalations,
            "budget: baseline budget is 0 - forecast variance cannot be computed and must be "
            "confirmed with the engagement financial analyst (status-reporting-rules.md #3.2)",
        )
    prior_forecast = budget.get(
        "previous_forecast_to_complete",
        payload.get("prior_status", {}).get("budget", {}).get("forecast_to_complete"),
    )
    if prior_forecast is None:
        forecast_period_delta = None
        add_escalation(
            escalations,
            "budget: prior forecast-to-complete not supplied, so period-on-period forecast "
            "movement cannot be computed and must not be reported as zero "
            "(status-reporting-rules.md #3.4)",
        )
    else:
        forecast_period_delta = round(forecast_to_complete - prior_forecast, 2)
        if forecast_period_delta != 0:
            add_escalation(
                escalations,
                f"budget: forecast-to-complete moved {forecast_period_delta:+} since the prior "
                f"pack ({prior_forecast} -> {forecast_to_complete}) - include this movement in "
                "the draft (status-reporting-rules.md #3.4)",
            )
    # Percentages used for the RAG comparison only; unmeasurable values are reported as
    # null in the facts so a 0.0 is never mistaken for a real zero variance.
    burn_pct_for_rag = burn_variance_pct if burn_measurable else 0.0
    forecast_pct_for_rag = forecast_variance_pct if forecast_measurable else 0.0
    largest_variance_pct = max(abs(burn_pct_for_rag), abs(forecast_pct_for_rag))
    rag = rag_from_threshold(largest_variance_pct, BUDGET_AMBER_PCT, BUDGET_RED_PCT)
    if not (burn_measurable and forecast_measurable) and actual_with_wip > 0:
        rag = worst(rag, "amber")
    if not wip_known:
        rag = worst(rag, "amber")
        add_escalation(
            escalations,
            "budget: unbilled_wip is missing from the finance export - actual burn is "
            "billed-only and is NOT authoritative; confirm WIP with the engagement financial "
            "analyst before reporting (status-reporting-rules.md #3.3)",
        )
    # Rules #3.1/#3.2 measure variance in either direction, so an underspend can drive
    # amber or red. Name the direction so the RAG is never reported unexplained.
    for label, value, measurable in (
        ("burn", burn_variance_pct, burn_measurable),
        ("forecast", forecast_variance_pct, forecast_measurable),
    ):
        if measurable and value <= -BUDGET_AMBER_PCT:
            add_escalation(
                escalations,
                f"budget: {label} variance is {value}% - this is an UNDERSPEND against plan, not "
                "an overspend; confirm delivery is on track before reporting "
                "(status-reporting-rules.md #3.1,#3.2)",
            )
    confidence = budget.get("confidence", 1.0)
    if confidence < CONFIDENCE_FLOOR:
        rag = worst(rag, "amber")
        add_escalation(
            escalations,
            f"budget: extraction confidence {confidence} below {CONFIDENCE_FLOOR} - human review required "
            "(status-reporting-rules.md #1.3)",
        )
    if wip:
        billed_only_pct = pct(billed - planned, planned)
        add_escalation(
            escalations,
            f"budget: billed-only burn is {billed} "
            f"({'unmeasurable' if billed_only_pct is None else f'{billed_only_pct}%'} vs plan) but "
            f"unbilled WIP {wip} changes actual burn to {actual_with_wip} "
            f"({'unmeasurable' if not burn_measurable else f'{burn_variance_pct}%'} vs plan) - "
            "lead with the WIP-inclusive figure (status-reporting-rules.md #3.3)",
        )
    return {
        "rag": rag,
        "facts": [
            {
                "currency": budget.get("currency", "UNKNOWN"),
                "planned_burn_to_date": planned,
                "actual_billed_to_date": billed,
                "unbilled_wip": raw_wip,
                "unbilled_wip_known": wip_known,
                "actual_burn_including_wip": actual_with_wip,
                "burn_variance_amount": round(burn_variance_amount, 2),
                "burn_variance_pct": burn_variance_pct if burn_measurable else None,
                "burn_variance_measurable": burn_measurable,
                "baseline_budget": baseline_budget,
                "forecast_to_complete": forecast_to_complete,
                "forecast_variance_amount": round(forecast_variance_amount, 2),
                "forecast_variance_pct": forecast_variance_pct if forecast_measurable else None,
                "forecast_variance_measurable": forecast_measurable,
                "forecast_period_delta": forecast_period_delta,
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
    # Confidence is taken over OPEN changes only: an approved CR extracted at low
    # confidence must not drag current scope to amber (#4.3).
    confidence = min([c.get("confidence", 1.0) for c in open_changes], default=1.0)
    if confidence < CONFIDENCE_FLOOR:
        rag = worst(rag, "amber")
        add_escalation(
            escalations,
            f"scope: extraction confidence {confidence} below {CONFIDENCE_FLOOR} - human review required "
            "(status-reporting-rules.md #1.3,#4.3)",
        )
    for change in open_changes:
        if "client_facing_impact" not in change:
            add_escalation(
                escalations,
                f"{change.get('id', '(unknown id)')}: open scope change does not state whether it "
                "has client-facing impact - ambiguous scope must be confirmed with the "
                "engagement manager, not assumed absent (status-reporting-rules.md #4.3)",
            )
    facts = []
    for change in open_changes:
        facts.append(
            {
                "id": change["id"],
                "title": change.get("title", "(untitled)"),
                "status": change.get("status", "unknown"),
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
    found = payload.get("contract_version")
    if found != "ps.client-status-qbr.v1":
        print(
            f"variance_calc: expected contract_version 'ps.client-status-qbr.v1' but found "
            f"{found!r} in {args.input}. Run plan-retrieve first to build a valid payload.",
            file=sys.stderr,
        )
        return 2

    output = copy.deepcopy(payload)
    escalations = list(output.get("escalations", []))
    try:
        thresholds_applied, thresholds_source = apply_settings(output, escalations)
    except SettingsError as exc:
        print(
            f"variance_calc: {exc}. Ask the user for a value inside the range, then re-run. "
            "Do not compute the variance by hand.",
            file=sys.stderr,
        )
        return 2
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
        "thresholds_applied": thresholds_applied,
        "thresholds_source": thresholds_source,
    }
    output["escalations"] = escalations
    engines = output.setdefault("provenance", {}).setdefault("engines", [])
    if "variance_calc/1.0" not in engines:
        engines.append("variance_calc/1.0")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)
        handle.write("\n")
    print(
        "variance_calc: "
        f"schedule={schedule['rag']}, budget={budget['rag']}, scope={scope['rag']}, "
        f"overall={overall}, escalations={len(escalations)} -> {args.out}"
    )
    return 0


def _fatal(message):
    print(f"variance_calc: {message}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except FileNotFoundError as exc:
        sys.exit(_fatal(
            f"cannot open {exc.filename} - check --input and --out, and that SKILL_DIR points "
            "at this skill's folder. This is a path error, not a data error: fix the path and "
            "re-run. Do not compute the variance by hand."
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
            "field so it is populated from a source document. Do not compute the variance by hand."
        ))
    except (TypeError, ValueError) as exc:
        sys.exit(_fatal(
            f"the payload holds a value of the wrong type ({exc}). A numeric field most likely "
            "contains text, or a date is not ISO YYYY-MM-DD. Correct the source record and "
            "re-run. Do not compute the variance by hand."
        ))
