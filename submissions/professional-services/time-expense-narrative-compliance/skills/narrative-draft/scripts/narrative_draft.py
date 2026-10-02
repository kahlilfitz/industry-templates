#!/usr/bin/env python3
"""narrative_draft - deterministic narrative drafting engine (step 2 of 5).

Reads a ps.time-expense-narrative-compliance.v1 activity packet and writes the same contract
with draft narratives attached. The model may later improve prose, but this engine owns linked
evidence, confidence, provenance and citations.

v1.0.4 rules:
- Signals from disabled or unknown sources are dropped first (signal_policy.py,
  client-billing-guidelines.md #10.1); an entry that linked one is marked needs_review.
- Rows outside the recorded timekeeper scope are withheld before drafting (#12.1).
- Every free-text field of a linked signal (subject, deliverable, purpose, attendees, organizer,
  file name, citations) and of the entry (narrative, notes, citations) passes the shared
  embedded-instruction tripwire first (#11.1). Flagged text is never copied into a narrative, a suggested rewrite or the draft's
  citations (#11.2): the draft is withheld and marked needs_review_embedded_instruction.
- Calendar activity is "Attended" unless the calendar organizer is the timekeeper ("Led").
- Each activity becomes "<verb> <subject> [with <attendees>] to <purpose> [for the <deliverable>]."
  When the purpose already contains "for", the deliverable moves before it ("... for the
  <deliverable> to <purpose>."). Every word comes from cited metadata. No filler is added: a draft
  under 12 words stays short and is marked needs_review_insufficient_detail (#1.1).
- An entry linking several activities gets one clause per activity, so every linked activity is
  described (covered_activity_ids); it is marked needs_review for block-billing review (#2.1/#2.2).
- Sufficiency (#1.2) is NOT asserted here; guideline-check alone determines it (#1.3).
- Existing narratives are preserved for compliance review. Separately labeled suggested
  rewrites are generated only from cited enabled-source activity and never replace them.
"""
import argparse
import datetime
import os
import sys
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import signal_policy  # noqa: E402  (shared copy shipped next to each engine)

ENGINE = "engine:narrative_draft"
ENGINE_VERSION = "narrative_draft/1.0.4"
CONTRACT = "ps.time-expense-narrative-compliance.v1"
MIN_NARRATIVE_WORDS = 12  # client-billing-guidelines.md #1.1
EXISTING_NARRATIVE_CONFIDENCE = 0.94
NO_EVIDENCE_CONFIDENCE = 0.35
BLOCK_BILLING_CITATIONS = "client-billing-guidelines.md #2.1 / #2.2"
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
    payload = signal_policy.read_json(path, InputError)
    if not isinstance(payload, dict):
        raise InputError("input is not a JSON object")
    if payload.get("contract_version") != CONTRACT:
        raise InputError(f"expected contract {CONTRACT}, got {payload.get('contract_version')!r}")
    signal_policy.validate_packet(payload, "activity")
    return payload


def words(text):
    # Same whitespace word count as guideline_check (client-billing-guidelines.md #1.1).
    return (text or "").split()


def join_names(names):
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def is_calendar(activity):
    return (signal_policy.source_key(activity.get("source")) == "calendar" or bool(activity.get("meeting_id"))
            or activity.get("activity_class") == "client_meeting")


def flagged_activities(linked):
    """(IDs, hits) of linked activities whose free text trips the embedded-instruction tripwire or is
    too long to screen (#11.1)."""
    ids, hits = [], []
    for a in linked:
        found = signal_policy.screen(signal_policy.signal_texts(a))
        if a.get("embedded_instruction") is True or found:
            ids.append(a.get("activity_id"))
            hits += found
    return ids, hits


def clause(entry, activity):
    """One grounded clause for one activity. Returns (text without final period, reasons)."""
    person = entry.get("person")
    reasons = []
    if is_calendar(activity):
        verb = "Led" if activity.get("organizer") and signal_policy.same_person(activity.get("organizer"), person) else "Attended"
    else:
        verb = next((v for c, v in VERB_BY_CLASS if c == activity.get("activity_class")), "Prepared")
    subject, purpose, deliverable = (activity.get(k).strip() if isinstance(activity.get(k), str) else ""
                                     for k in ("subject", "purpose", "deliverable"))
    attendees = activity.get("attendees") if isinstance(activity.get("attendees"), list) else []
    others = [a for a in attendees if isinstance(a, str) and a.strip() and not signal_policy.same_person(a, person)]
    text = f"{verb} {subject}"
    if others:
        text += f" with {join_names(others)}"
    # Avoid "... for client decision for the X": put the deliverable first when the purpose has "for".
    deliverable_first = bool(deliverable and purpose and " for " in f" {purpose.lower()} ")
    if deliverable_first:
        text += f" for the {deliverable}"
    if purpose:
        text += f" to {purpose}"
    else:
        reasons.append(f"{activity.get('activity_id')} has no recorded purpose; purpose not invented")
    if deliverable and not deliverable_first:
        text += f" for the {deliverable}"
    return text, reasons


def grounded_narrative(entry, linked):
    """Return (narrative, status, confidence, reasons, covered_ids) grounded only in linked activity."""
    if not linked:
        return ("", "needs_activity_evidence", NO_EVIDENCE_CONFIDENCE,
                ["no cited activity signal from an enabled source is linked; nothing to draft from"], [])
    flagged, hits = flagged_activities(linked)
    if flagged:
        why = signal_policy.hold_reason(hits, "linked activity text flagged as embedded_instruction")
        return ("", "needs_review_embedded_instruction", NO_EVIDENCE_CONFIDENCE,
                [f"{why} ({', '.join(flagged)}); "
                 "treated as data and withheld - no narrative drafted from it (client-billing-guidelines.md #11.1, #11.2)"],
                [])
    ordered = sorted(linked, key=lambda a: 0 if a.get("activity_class") == "client_meeting" else 1)
    parts, reasons = [], []
    for activity in ordered:
        text, why = clause(entry, activity)
        parts.append(text if not parts else text[0].lower() + text[1:])
        reasons.extend(why)
    narrative = "; ".join(parts[:-1]) + ("; and " if len(parts) > 1 else "") + parts[-1] + "."
    if len(parts) == 1:
        narrative = parts[0] + "."
    if len(linked) > 1:
        reasons.append(f"entry links {len(linked)} activities; each is described, review for block billing "
                       f"({BLOCK_BILLING_CITATIONS})")
    status = "engine_generated_from_activity"
    if len(words(narrative)) < MIN_NARRATIVE_WORDS:
        status = "needs_review_insufficient_detail"
        reasons.append(f"{len(words(narrative))} words from cited metadata; left short rather than padded (client-billing-guidelines.md #1.1)")
    elif reasons:
        status = "needs_review"
    confidence = round(min([a.get("confidence", 0.8) for a in linked] + [0.9]), 2)
    return narrative, status, confidence, reasons, [a.get("activity_id") for a in ordered]


def build_narrative(entry, linked):
    """Return (narrative, status, confidence, review_reasons, suggested_rewrites, covered_ids)."""
    existing = (entry.get("narrative") or "").strip()
    if not existing:
        narrative, status, confidence, reasons, covered = grounded_narrative(entry, linked)
        return narrative, status, confidence, reasons, [], covered

    reasons = []
    hits = signal_policy.screen(signal_policy.entry_texts(entry, linked))
    existing_flagged = entry.get("embedded_instruction") is True or bool(hits)
    if existing_flagged:
        reasons.append(signal_policy.hold_reason(hits, "existing narrative flagged as embedded_instruction")
                       + "; withheld from the "
                       "draft and left in the source entry only as evidence for guideline-check, never obeyed "
                       "(client-billing-guidelines.md #11.1, #11.2)")
    suggestions = []
    for activity in linked:
        narrative, status, confidence, why, covered = grounded_narrative(entry, [activity])
        if status == "needs_review_embedded_instruction":
            reasons.extend(why)
            continue
        if not narrative or signal_policy.embedded_instruction(narrative):
            continue
        if len(linked) > 1:
            why = why + [f"covers {activity.get('activity_id')} only; this entry also links "
                         + ", ".join(a.get("activity_id") for a in linked if a is not activity)
                         + f" - use with the other rewrites or split the entry ({BLOCK_BILLING_CITATIONS})"]
            if status == "engine_generated_from_activity":
                status = "needs_review"
        suggestions.append({
            "narrative": narrative,
            "status": status,
            "review_reasons": why,
            "linked_activity_ids": [activity.get("activity_id")],
            "confidence": confidence,
            "source": ENGINE,
            "citations": sorted(set(signal_policy.safe_citations(activity.get("citations", []))[0])),
        })
    covered = [a for s_ in suggestions for a in s_["linked_activity_ids"]]
    if existing_flagged:
        return "", "needs_review_embedded_instruction", NO_EVIDENCE_CONFIDENCE, reasons, suggestions, covered
    return existing, "existing_timesheet_narrative", EXISTING_NARRATIVE_CONFIDENCE, reasons, suggestions, covered


def main():
    ap = argparse.ArgumentParser(description="Draft deterministic narrative candidates from activity signals.")
    ap.add_argument("--activity", required=True, help="Input contract JSON from activity-pull")
    ap.add_argument("--out", required=True, help="Output drafted contract JSON")
    ap.add_argument("--signal-config", help="Additional signal policy JSON; it can only narrow the plugin's config/signal-sources.json, which is always applied (most restrictive wins)")
    ap.add_argument("--generated-at", help="Fixed ISO-8601 UTC timestamp for reproducible golden files")
    args = ap.parse_args()

    try:
        stamp = generated_at(args.generated_at)
        out = deepcopy(load_packet(args.activity))
        signal_policy.enforce_timekeeper_scope(out, engine=ENGINE)
        signal_policy.filter_packet(out, config_path=args.signal_config,
                                    script_dir=os.path.dirname(os.path.abspath(__file__)), engine=ENGINE)
    except (InputError, signal_policy.PolicyError) as exc:
        sys.exit(f"narrative_draft: {exc}")

    by_id = {a["activity_id"]: a for a in out["activity_signals"]}
    drafted_count = 0
    for entry in out["time_entries"]:
        linked = [by_id[a] for a in entry.get("activity_ids", []) if a in by_id]
        narrative, status, confidence, reasons, suggestions, covered = build_narrative(entry, linked)
        # The entry's own text, citations included, is screened like signal text (#11.1): when it trips, the
        # draft is withheld and no flagged entry citation is copied (#11.2).
        entry_hits = signal_policy.screen(signal_policy.entry_texts(entry))
        entry_flagged = entry.get("embedded_instruction") is True or bool(entry_hits)
        entry_citations, entry_citations_dropped = signal_policy.safe_citations(entry.get("citations", []), entry_flagged)
        if (entry_flagged or entry_citations_dropped) and status != "needs_review_embedded_instruction":
            narrative, status, confidence = "", "needs_review_embedded_instruction", NO_EVIDENCE_CONFIDENCE
            reasons.append(signal_policy.hold_reason(entry_hits, "time entry text or citation flagged as embedded_instruction")
                           + "; draft withheld and the flagged text never copied or obeyed "
                           "(client-billing-guidelines.md #11.1, #11.2)")
        excluded_links = entry.get("excluded_activity_ids") or []
        if excluded_links:
            reasons.append("linked signal(s) from a disabled or unresolvable source were excluded from evidence: "
                           + signal_policy.describe_excluded(excluded_links, out) + " (client-billing-guidelines.md #10.1)")
        uncovered = [a.get("activity_id") for a in linked if a.get("activity_id") not in covered]
        if uncovered and status != "needs_review_embedded_instruction":
            reasons.append("linked activity not described in any draft or suggested rewrite: " + ", ".join(uncovered))
        if any(signal_policy.INJECTION_CITATION in r for r in reasons):
            citations_extra = [signal_policy.INJECTION_CITATION, signal_policy.WITHHOLD_CITATION]
        else:
            citations_extra = []
        if status in ("engine_generated_from_activity", "needs_review", "needs_review_insufficient_detail"):
            drafted_count += 1
        citations = []
        for item in linked:
            # Citations are signal text too: flagged citation text is never copied into the draft (#11.2).
            item_flagged = (item.get("embedded_instruction") is True
                            or signal_policy.embedded_instruction(signal_policy.signal_texts(item)))
            kept, dropped = signal_policy.safe_citations(item.get("citations", []), item_flagged)
            citations.extend(kept)
            if dropped:
                citations_extra = sorted(set(citations_extra + [signal_policy.INJECTION_CITATION,
                                                                signal_policy.WITHHOLD_CITATION]))
        if excluded_links:
            citations.append(signal_policy.POLICY_CITATION)
        citations.extend(citations_extra)
        entry["draft"] = {
            "narrative": narrative,
            "status": status,
            "needs_review": bool(reasons) or status not in ("engine_generated_from_activity", "existing_timesheet_narrative"),
            "review_reasons": reasons,
            "word_count": len(words(narrative)),
            "sufficiency": "determined_by_guideline_check (client-billing-guidelines.md #1.3)",
            "linked_activity_ids": list(entry.get("activity_ids", [])),
            "covered_activity_ids": covered,
            "excluded_activity_ids": list(excluded_links),
            "confidence": confidence,
            "source": ENGINE,
            "citations": sorted(set(citations)) or entry_citations,
        }
        if suggestions:
            entry["draft"]["suggested_rewrites"] = suggestions
    out.setdefault("provenance", {}).setdefault("engines", []).append(ENGINE_VERSION)
    out["provenance"]["generated_at"] = stamp
    try:
        signal_policy.write_output(args.out, signal_policy.dump_json(out))
    except (OSError, ValueError) as exc:  # ValueError covers NaN in dump_json and UnicodeEncodeError
        sys.exit(f"narrative_draft: cannot write output: {exc}")
    print(f"narrative_draft: {len(out['time_entries'])} entries, {drafted_count} drafted, "
          f"{len(out['provenance'].get('excluded_signals', []))} excluded signal(s) -> {os.path.basename(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
