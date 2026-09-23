#!/usr/bin/env python3
"""guideline_check - deterministic billing-guideline compliance engine (Govern).

Constants mirror references/client-billing-guidelines.md section by section. The model
reports these flags; it never decides, suppresses or downgrades compliance verdicts.
"""
import argparse
import json
import re
import sys
from copy import deepcopy
from decimal import Decimal

ENGINE = "engine:guideline_check"
CONTRACT = "ps.time-expense-narrative-compliance.v1"
MIN_NARRATIVE_WORDS = 12  # client-billing-guidelines.md #1.1
REQUIRED_ELEMENTS = ("actor", "subject", "purpose")  # client-billing-guidelines.md #1.2
BLOCK_BILLING_HOURS = 2.0  # client-billing-guidelines.md #2.1
BLOCK_BILLING_CLASS_LIMIT = 1  # client-billing-guidelines.md #2.1
PROHIBITED_TERMS = ("attention to", "various matters", "miscellaneous", "work on file", "general follow up")  # client-billing-guidelines.md #3.1
VAGUE_PHRASES = ("review and revise", "work on", "handle", "follow up", "touch base")  # client-billing-guidelines.md #3.2
CODE_MISMATCH_REVIEW_CONFIDENCE = 0.80  # client-billing-guidelines.md #4.2
NON_BILLABLE_CLASSES = ("internal_admin", "billing_hygiene")  # client-billing-guidelines.md #5.1
ROUNDING_INCREMENT = Decimal("0.1")  # client-billing-guidelines.md #6.1
EVIDENCE_OVERRUN_HOURS = 0.2  # client-billing-guidelines.md #6.2
DUPLICATE_MEETING_THRESHOLD = 0.92  # client-billing-guidelines.md #7.1
MISSING_TIME_MIN_HOURS = 0.5  # client-billing-guidelines.md #8.1
CONFIDENCE_FLOOR = 0.75  # client-billing-guidelines.md #9.1
GENERATED_AT = "2026-09-23T00:00:00Z"


def normalize(text):
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def word_count(text):
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def rounded_to_increment(value):
    dec = Decimal(str(value))
    return (dec % ROUNDING_INCREMENT) == 0


def add_flag(flags, flag, severity, detail, citations, confidence=0.95):
    flags.append({
        "flag": flag,
        "severity": severity,
        "detail": detail,
        "source": ENGINE,
        "confidence": confidence,
        "citations": citations
    })


def main():
    ap = argparse.ArgumentParser(description="Govern time-entry narratives against client billing guidelines.")
    ap.add_argument("--coded", required=True, help="Input coded contract JSON")
    ap.add_argument("--out", required=True, help="Output governed contract JSON")
    args = ap.parse_args()

    payload = json.load(open(args.coded, encoding="utf-8"))
    assert payload["contract_version"] == CONTRACT, "wrong contract version"
    out = deepcopy(payload)
    by_id = {a["activity_id"]: a for a in out.get("activity_signals", [])}
    used_activity_ids = set()
    meeting_seen = {}
    exception_list = []

    for entry in out.get("time_entries", []):
        narrative = entry.get("draft", {}).get("narrative") or entry.get("narrative", "")
        narrative_norm = normalize(narrative)
        linked = [by_id[a] for a in entry.get("activity_ids", []) if a in by_id]
        used_activity_ids.update([a["activity_id"] for a in linked])
        classes = sorted(set(a.get("activity_class") for a in linked if a.get("activity_class")))
        evidence_hours = round(sum(a.get("duration_hours", 0) for a in linked), 2)
        flags = []

        wc = word_count(narrative)
        if wc < MIN_NARRATIVE_WORDS:
            add_flag(flags, "minimum_detail", "needs_review", f"{wc} words < {MIN_NARRATIVE_WORDS} required words", ["client-billing-guidelines.md #1.1"], 0.9)

        missing_elements = []
        if not entry.get("person"):
            missing_elements.append("actor")
        if not linked and not any(a.get("subject", "").lower() in narrative_norm for a in out.get("activity_signals", [])):
            missing_elements.append("subject")
        if not linked and "for " not in narrative_norm and "to " not in narrative_norm:
            missing_elements.append("purpose")
        if narrative_norm.startswith("attention to"):
            missing_elements.append("actor")
        if len(set(missing_elements)) >= 2:
            add_flag(flags, "required_elements_missing", "reject", f"missing required elements: {', '.join(sorted(set(missing_elements)))}", ["client-billing-guidelines.md #1.2"], 0.88)
        elif missing_elements:
            add_flag(flags, "required_elements_missing", "needs_review", f"missing required element: {missing_elements[0]}", ["client-billing-guidelines.md #1.2"], 0.88)

        if entry.get("duration_hours", 0) > BLOCK_BILLING_HOURS and len(classes) > BLOCK_BILLING_CLASS_LIMIT:
            add_flag(flags, "block_billing", "reject", f"{entry['duration_hours']} hours combines {len(classes)} activity classes: {', '.join(classes)}", ["client-billing-guidelines.md #2.1"], 0.97)

        for term in PROHIBITED_TERMS:
            if term in narrative_norm:
                add_flag(flags, "prohibited_term", "reject", f"matched prohibited term '{term}'", ["client-billing-guidelines.md #3.1"], 0.99)
        for phrase in VAGUE_PHRASES:
            if phrase in narrative_norm:
                add_flag(flags, "vague_phrase", "needs_review", f"matched vague phrase '{phrase}'", ["client-billing-guidelines.md #3.2"], 0.93)

        if any(c in NON_BILLABLE_CLASSES for c in classes) or entry.get("code_mapping", {}).get("recommended_task_code") == "NB900":
            add_flag(flags, "non_billable_activity", "reject", "entry is linked to internal/non-billable activity", ["client-billing-guidelines.md #5.1", "task-phase-codes.md #4.1"], 0.96)

        if not rounded_to_increment(entry.get("duration_hours", 0)):
            add_flag(flags, "rounding_increment", "needs_review", f"{entry['duration_hours']} is not rounded to 0.1 hour", ["client-billing-guidelines.md #6.1"], 0.91)
        if linked and entry.get("duration_hours", 0) - evidence_hours > EVIDENCE_OVERRUN_HOURS:
            add_flag(flags, "evidence_overrun", "needs_review", f"{entry['duration_hours']} billed hours exceeds {evidence_hours} hours of linked evidence by more than {EVIDENCE_OVERRUN_HOURS}", ["client-billing-guidelines.md #6.2"], 0.86)

        for map_flag in entry.get("code_mapping", {}).get("flags", []):
            flags.append(map_flag)

        meeting_ids = sorted(set(a.get("meeting_id") for a in linked if a.get("meeting_id")))
        for meeting_id in meeting_ids:
            key = (meeting_id, normalize(narrative))
            if key in meeting_seen:
                add_flag(flags, "duplicate_meeting", "reject", f"near-duplicate meeting narrative for {meeting_id}; first seen on {meeting_seen[key]}", ["client-billing-guidelines.md #7.1"], DUPLICATE_MEETING_THRESHOLD)
            else:
                meeting_seen[key] = entry["entry_id"]

        lowest_conf = min([f.get("confidence", 1.0) for f in flags] + [entry.get("draft", {}).get("confidence", 1.0), entry.get("code_mapping", {}).get("confidence", 1.0)])
        if lowest_conf < CONFIDENCE_FLOOR:
            add_flag(flags, "confidence_floor", "hold_for_review", f"confidence {lowest_conf} below {CONFIDENCE_FLOOR}", ["client-billing-guidelines.md #9.1"], lowest_conf)

        severity_order = {"pass": 0, "needs_review": 1, "hold_for_review": 2, "reject": 3}
        verdict = "pass"
        for flag in flags:
            sev = flag.get("severity", "needs_review")
            if severity_order[sev] > severity_order[verdict]:
                verdict = sev
        entry["compliance"] = {
            "verdict": "compliant" if verdict == "pass" else verdict,
            "flags": flags,
            "confidence": round(lowest_conf if flags else 0.96, 2),
            "source": ENGINE,
            "citations": sorted(set(c for f in flags for c in f.get("citations", []))) or ["client-billing-guidelines.md #1.1", "client-billing-guidelines.md #1.2"]
        }
        if flags:
            exception_list.append({
                "entry_id": entry["entry_id"],
                "person": entry.get("person"),
                "date": entry.get("date"),
                "duration_hours": entry.get("duration_hours"),
                "verdict": entry["compliance"]["verdict"],
                "flags": [f["flag"] for f in flags],
                "recommended_action": "rewrite_or_remove_before_prebill" if verdict == "reject" else "billing_coordinator_review",
                "source": ENGINE,
                "confidence": entry["compliance"]["confidence"],
                "citations": entry["compliance"]["citations"]
            })

    missing = []
    for activity in out.get("activity_signals", []):
        if activity["activity_id"] in used_activity_ids:
            continue
        if activity.get("billable_signal") and activity.get("duration_hours", 0) >= MISSING_TIME_MIN_HOURS:
            missing.append({
                "activity_id": activity["activity_id"],
                "person": activity.get("person"),
                "date": activity.get("date"),
                "activity_class": activity.get("activity_class"),
                "duration_hours": activity.get("duration_hours"),
                "subject": activity.get("subject"),
                "finding": "engagement activity has no matching time entry",
                "source": ENGINE,
                "confidence": activity.get("confidence", 0.9),
                "citations": activity.get("citations", []) + ["client-billing-guidelines.md #8.1"]
            })
    if missing:
        exception_list.append({
            "entry_id": None,
            "person": "multiple" if len({m["person"] for m in missing}) > 1 else missing[0]["person"],
            "date": "multiple" if len({m["date"] for m in missing}) > 1 else missing[0]["date"],
            "duration_hours": round(sum(m["duration_hours"] for m in missing), 2),
            "verdict": "missing_time",
            "flags": ["missing_time"],
            "recommended_action": "review_activity_and_create_draft_entries_if_billable",
            "source": ENGINE,
            "confidence": min(m["confidence"] for m in missing),
            "citations": sorted(set(c for m in missing for c in m["citations"]))
        })

    out["missing_time_report"] = missing
    out["exception_list"] = exception_list
    counts = {}
    for entry in out.get("time_entries", []):
        verdict = entry.get("compliance", {}).get("verdict", "unknown")
        counts[verdict] = counts.get(verdict, 0) + 1
    out["prebill_summary"] = {
        "total_entries": len(out.get("time_entries", [])),
        "total_hours": round(sum(e.get("duration_hours", 0) for e in out.get("time_entries", [])), 2),
        "verdict_counts": counts,
        "missing_time_hours": round(sum(m["duration_hours"] for m in missing), 2),
        "exception_count": len(exception_list),
        "source": ENGINE,
        "confidence": 0.96,
        "citations": ["client-billing-guidelines.md #2.1", "client-billing-guidelines.md #3.1", "client-billing-guidelines.md #8.1", "client-billing-guidelines.md #9.2"]
    }
    out.setdefault("provenance", {}).setdefault("engines", []).append("guideline_check/1.0")
    out["provenance"]["generated_at"] = GENERATED_AT
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)
    print(f"guideline_check: {len(out.get('time_entries', []))} entries, {len(exception_list)} exception(s), {len(missing)} missing-time item(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
