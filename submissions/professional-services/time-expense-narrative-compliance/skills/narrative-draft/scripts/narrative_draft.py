#!/usr/bin/env python3
"""narrative_draft - deterministic demo narrative drafting engine.

Reads a normalized ps.time-expense-narrative-compliance.v1 activity packet and writes the
same contract with draft narratives attached. The model may later improve prose, but this
engine owns linked evidence, confidence, provenance and citations for the demo scenarios.
"""
import argparse
import json
import sys
from copy import deepcopy

ENGINE = "engine:narrative_draft"
CONTRACT = "ps.time-expense-narrative-compliance.v1"
MIN_NARRATIVE_WORDS = 12  # client-billing-guidelines.md #1.1
REQUIRED_ELEMENTS = ("actor", "subject", "purpose")  # client-billing-guidelines.md #1.2
GENERATED_AT = "2026-09-23T00:00:00Z"


def words(text):
    return [w for w in text.replace("/", " ").replace("-", " ").split() if w.strip()]


def build_narrative(entry, by_id):
    linked = [by_id[a] for a in entry.get("activity_ids", []) if a in by_id]
    existing = (entry.get("narrative") or "").strip()
    if existing:
        return existing, "existing_timesheet_narrative", 0.94
    if not linked:
        return "Draft pending: no cited engagement activity signal was linked to this entry.", "needs_activity_evidence", 0.35
    subjects = []
    purposes = []
    classes = []
    for item in linked:
        if item.get("subject") not in subjects:
            subjects.append(item.get("subject", "engagement activity"))
        if item.get("purpose") not in purposes:
            purposes.append(item.get("purpose", "support client delivery"))
        if item.get("activity_class") not in classes:
            classes.append(item.get("activity_class"))
    person = entry.get("person", "Consultant")
    verb = "Prepared"
    if "client_meeting" in classes:
        verb = "Led"
    elif "document_analysis" in classes:
        verb = "Analyzed"
    elif "deliverable_drafting" in classes:
        verb = "Drafted"
    narrative = f"{verb} {subjects[0]} for {purposes[0]} with cited engagement activity support."
    if len(words(narrative)) < MIN_NARRATIVE_WORDS:
        narrative = f"{person} {narrative}"
    return narrative, "engine_generated_from_activity", round(min([a.get("confidence", 0.8) for a in linked] + [0.9]), 2)


def main():
    ap = argparse.ArgumentParser(description="Draft deterministic narrative candidates from activity signals.")
    ap.add_argument("--activity", required=True, help="Input contract JSON from activity-pull")
    ap.add_argument("--out", required=True, help="Output drafted contract JSON")
    args = ap.parse_args()

    payload = json.load(open(args.activity, encoding="utf-8"))
    assert payload["contract_version"] == CONTRACT, "wrong contract version"
    out = deepcopy(payload)
    by_id = {a["activity_id"]: a for a in out.get("activity_signals", [])}
    drafted_count = 0
    for entry in out.get("time_entries", []):
        narrative, status, confidence = build_narrative(entry, by_id)
        if status == "engine_generated_from_activity":
            drafted_count += 1
        linked = [by_id[a] for a in entry.get("activity_ids", []) if a in by_id]
        citations = []
        for item in linked:
            citations.extend(item.get("citations", []))
        entry["draft"] = {
            "narrative": narrative,
            "status": status,
            "word_count": len(words(narrative)),
            "required_elements": {"actor": bool(entry.get("person")), "subject": bool(linked), "purpose": bool(linked)},
            "linked_activity_ids": entry.get("activity_ids", []),
            "confidence": confidence,
            "source": ENGINE,
            "citations": sorted(set(citations)) or entry.get("citations", [])
        }
    out.setdefault("provenance", {}).setdefault("engines", []).append("narrative_draft/1.0")
    out["provenance"]["generated_at"] = GENERATED_AT
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)
    print(f"narrative_draft: {len(out.get('time_entries', []))} entries, {drafted_count} drafted -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
