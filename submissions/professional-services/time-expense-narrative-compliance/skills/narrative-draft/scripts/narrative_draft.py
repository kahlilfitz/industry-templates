#!/usr/bin/env python3
"""narrative_draft - deterministic narrative drafting engine (step 2 of 5).

Reads a ps.time-expense-narrative-compliance.v1 activity packet and writes the same contract
with draft narratives attached. The model may later improve prose, but this engine owns linked
evidence, confidence, provenance and citations.

v1.0.2 rules:
- Signals from disabled or unknown sources are dropped first (signal_policy.py,
  client-billing-guidelines.md #10.1); an entry that linked one is marked needs_review.
- Meetings are "Attended" unless the calendar organizer is the timekeeper ("Led").
- Narratives use "<verb> <subject> [with <attendees>] to <purpose> [for the <deliverable>]."
  Every word comes from cited metadata. No filler is added: a draft under 12 words stays short
  and is marked needs_review_insufficient_detail so guideline-check can flag it (#1.1).
- Sufficiency (#1.2) is NOT asserted here; guideline-check alone determines it (#1.3).
- Existing narratives are preserved for compliance review. Separately labeled suggested
  rewrites are generated only from cited enabled-source activity and never replace them.
"""
import argparse
import datetime
import json
import os
import sys
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import signal_policy  # noqa: E402  (shared copy shipped next to each engine)

ENGINE = "engine:narrative_draft"
ENGINE_VERSION = "narrative_draft/1.0.2"
CONTRACT = "ps.time-expense-narrative-compliance.v1"
MIN_NARRATIVE_WORDS = 12  # client-billing-guidelines.md #1.1
EXISTING_NARRATIVE_CONFIDENCE = 0.94
NO_EVIDENCE_CONFIDENCE = 0.35
VERB_BY_CLASS = (
    ("document_analysis", "Analyzed"),
    ("research", "Researched"),
    ("deliverable_drafting", "Drafted"),
    ("internal_admin", "Coordinated"),
    ("billing_hygiene", "Reviewed"),
)


class InputError(ValueError):
    pass


def generated_at(override):
    if override:
        try:
            datetime.datetime.fromisoformat(override.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InputError(f"--generated-at is not an ISO-8601 timestamp: {override!r}") from exc
        return override
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_packet(path):
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"cannot read {os.path.basename(path)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise InputError("input is not a JSON object")
    if payload.get("contract_version") != CONTRACT:
        raise InputError(f"expected contract {CONTRACT}, got {payload.get('contract_version')!r}")
    for key in ("activity_signals", "time_entries"):
        if not isinstance(payload.get(key), list):
            raise InputError(f"'{key}' must be a list")
    for entry in payload["time_entries"]:
        for key in ("entry_id", "person", "date", "duration_hours"):
            if key not in entry:
                raise InputError(f"time entry {entry.get('entry_id', '?')} is missing '{key}'")
    return payload


def words(text):
    # Same whitespace word count as guideline_check (client-billing-guidelines.md #1.1).
    return (text or "").split()


def join_names(names):
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def grounded_narrative(entry, linked):
    """Return a narrative candidate grounded only in linked activity."""
    if not linked:
        return ("", "needs_activity_evidence", NO_EVIDENCE_CONFIDENCE,
                ["no cited activity signal from an enabled source is linked; nothing to draft from"])
    person = entry.get("person")
    lead = linked[0]
    classes = [a.get("activity_class") for a in linked]
    reasons = []
    if "client_meeting" in classes:
        meeting = next(a for a in linked if a.get("activity_class") == "client_meeting")
        lead = meeting
        verb = "Led" if meeting.get("organizer") and meeting.get("organizer") == person else "Attended"
    else:
        verb = next((v for c, v in VERB_BY_CLASS if c in classes), "Prepared")
    subject = (lead.get("subject") or "").strip()
    purpose = (lead.get("purpose") or "").strip()
    deliverable = (lead.get("deliverable") or "").strip()
    others = [a for a in (lead.get("attendees") or []) if a and a != person]
    narrative = f"{verb} {subject}"
    if others:
        narrative += f" with {join_names(others)}"
    if purpose:
        narrative += f" to {purpose}"
    else:
        reasons.append(f"{lead.get('activity_id')} has no recorded purpose; purpose not invented")
    if deliverable:
        narrative += f" for the {deliverable}"
    narrative += "."
    if len(linked) > 1:
        reasons.append("entry links more than one activity; only the first is described - review for block billing")
    status = "engine_generated_from_activity"
    if len(words(narrative)) < MIN_NARRATIVE_WORDS:
        status = "needs_review_insufficient_detail"
        reasons.append(f"{len(words(narrative))} words from cited metadata; left short rather than padded (client-billing-guidelines.md #1.1)")
    elif reasons:
        status = "needs_review"
    confidence = round(min([a.get("confidence", 0.8) for a in linked] + [0.9]), 2)
    return narrative, status, confidence, reasons


def build_narrative(entry, linked):
    """Return (narrative, status, confidence, review_reasons, suggested_rewrites)."""
    existing = (entry.get("narrative") or "").strip()
    if not existing:
        narrative, status, confidence, reasons = grounded_narrative(entry, linked)
        return narrative, status, confidence, reasons, []

    suggestions = []
    for activity in linked:
        narrative, status, confidence, reasons = grounded_narrative(entry, [activity])
        if not narrative:
            continue
        suggestions.append({
            "narrative": narrative,
            "status": status,
            "review_reasons": reasons,
            "linked_activity_ids": [activity.get("activity_id")],
            "confidence": confidence,
            "source": ENGINE,
            "citations": sorted(set(activity.get("citations", []))),
        })
    return existing, "existing_timesheet_narrative", EXISTING_NARRATIVE_CONFIDENCE, [], suggestions


def main():
    ap = argparse.ArgumentParser(description="Draft deterministic narrative candidates from activity signals.")
    ap.add_argument("--activity", required=True, help="Input contract JSON from activity-pull")
    ap.add_argument("--out", required=True, help="Output drafted contract JSON")
    ap.add_argument("--signal-config", help="Signal policy JSON (default: the plugin's config/signal-sources.json)")
    ap.add_argument("--generated-at", help="Fixed ISO-8601 UTC timestamp for reproducible golden files")
    args = ap.parse_args()

    try:
        stamp = generated_at(args.generated_at)
        out = deepcopy(load_packet(args.activity))
        signal_policy.filter_packet(out, config_path=args.signal_config,
                                    script_dir=os.path.dirname(os.path.abspath(__file__)), engine=ENGINE)
    except (InputError, signal_policy.PolicyError) as exc:
        sys.exit(f"narrative_draft: {exc}")

    by_id = {a["activity_id"]: a for a in out["activity_signals"]}
    drafted_count = 0
    for entry in out["time_entries"]:
        linked = [by_id[a] for a in entry.get("activity_ids", []) if a in by_id]
        narrative, status, confidence, reasons, suggestions = build_narrative(entry, linked)
        excluded_links = entry.get("excluded_activity_ids") or []
        if excluded_links:
            reasons.append("linked signal(s) from a disabled or unresolvable source were excluded from evidence: "
                           + ", ".join(excluded_links) + " (client-billing-guidelines.md #10.1)")
        if status in ("engine_generated_from_activity", "needs_review", "needs_review_insufficient_detail"):
            drafted_count += 1
        citations = []
        for item in linked:
            citations.extend(item.get("citations", []))
        if excluded_links:
            citations.append(signal_policy.POLICY_CITATION)
        entry["draft"] = {
            "narrative": narrative,
            "status": status,
            "needs_review": bool(reasons) or status not in ("engine_generated_from_activity", "existing_timesheet_narrative"),
            "review_reasons": reasons,
            "word_count": len(words(narrative)),
            "sufficiency": "determined_by_guideline_check (client-billing-guidelines.md #1.3)",
            "linked_activity_ids": list(entry.get("activity_ids", [])),
            "excluded_activity_ids": list(excluded_links),
            "confidence": confidence,
            "source": ENGINE,
            "citations": sorted(set(citations)) or entry.get("citations", []),
        }
        if suggestions:
            entry["draft"]["suggested_rewrites"] = suggestions
    out.setdefault("provenance", {}).setdefault("engines", []).append(ENGINE_VERSION)
    out["provenance"]["generated_at"] = stamp
    try:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(out, fh, indent=2)
            fh.write("\n")
    except OSError as exc:
        sys.exit(f"narrative_draft: cannot write output: {exc}")
    print(f"narrative_draft: {len(out['time_entries'])} entries, {drafted_count} drafted, "
          f"{len(out['provenance'].get('excluded_signals', []))} excluded signal(s) -> {os.path.basename(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
