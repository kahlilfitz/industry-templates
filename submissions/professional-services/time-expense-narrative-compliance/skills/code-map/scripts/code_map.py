#!/usr/bin/env python3
"""code_map - deterministic phase/task mapping for time-entry narratives.

Constants mirror references/task-phase-codes.md and references/client-billing-guidelines.md.
"""
import argparse
import json
import sys
from copy import deepcopy

ENGINE = "engine:code_map"
CONTRACT = "ps.time-expense-narrative-compliance.v1"
DIRECT_MATCH_CONFIDENCE = 0.92  # task-phase-codes.md #5.1
KEYWORD_MATCH_CONFIDENCE = 0.78  # task-phase-codes.md #5.2
UNKNOWN_CONFIDENCE = 0.40  # task-phase-codes.md #5.3
CODE_MISMATCH_REVIEW_CONFIDENCE = 0.80  # client-billing-guidelines.md #4.2
GENERATED_AT = "2026-09-23T00:00:00Z"

CLASS_MAP = {
    "client_meeting": ("DL", "DL300", "Client meeting or working session", "task-phase-codes.md #3.1"),
    "document_analysis": ("AN", "AN200", "Document analysis tied to a client deliverable", "task-phase-codes.md #2.1"),
    "research": ("AN", "AN220", "Research or options analysis", "task-phase-codes.md #2.2"),
    "deliverable_drafting": ("DL", "DL320", "Drafting or finalizing a client deliverable", "task-phase-codes.md #3.2"),
    "internal_admin": ("NB", "NB900", "Internal non-billable administration", "task-phase-codes.md #4.1"),
    "billing_hygiene": ("BH", "BH910", "Pre-bill and WIP hygiene", "task-phase-codes.md #4.2")
}
KEYWORDS = [
    ("meeting", ("DL", "DL300", "Client meeting or working session", "task-phase-codes.md #3.1")),
    ("workshop", ("DL", "DL300", "Client meeting or working session", "task-phase-codes.md #3.1")),
    ("analy", ("AN", "AN200", "Document analysis tied to a client deliverable", "task-phase-codes.md #2.1")),
    ("research", ("AN", "AN220", "Research or options analysis", "task-phase-codes.md #2.2")),
    ("draft", ("DL", "DL320", "Drafting or finalizing a client deliverable", "task-phase-codes.md #3.2")),
    ("staffing", ("NB", "NB900", "Internal non-billable administration", "task-phase-codes.md #4.1"))
]


def choose_mapping(entry, by_id):
    linked = [by_id[a] for a in entry.get("activity_ids", []) if a in by_id]
    classes = [a.get("activity_class") for a in linked]
    billable = [a.get("billable_signal", True) for a in linked]
    if classes:
        if any(c == "internal_admin" or b is False for c, b in zip(classes, billable)):
            return CLASS_MAP["internal_admin"], DIRECT_MATCH_CONFIDENCE, "direct_activity_class"
        counts = {c: classes.count(c) for c in set(classes)}
        selected = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        if selected in CLASS_MAP:
            return CLASS_MAP[selected], DIRECT_MATCH_CONFIDENCE, "direct_activity_class"
    text = " ".join([entry.get("draft", {}).get("narrative", ""), entry.get("narrative", "")]).lower()
    for token, mapping in KEYWORDS:
        if token in text:
            return mapping, KEYWORD_MATCH_CONFIDENCE, "keyword_inference"
    return ("UNMAPPED", "UNMAPPED", "Unknown or conflicting activity", "task-phase-codes.md #5.3"), UNKNOWN_CONFIDENCE, "unmapped"


def main():
    ap = argparse.ArgumentParser(description="Map drafted time entries to phase/task codes.")
    ap.add_argument("--drafted", required=True, help="Input drafted contract JSON")
    ap.add_argument("--out", required=True, help="Output coded contract JSON")
    args = ap.parse_args()

    payload = json.load(open(args.drafted, encoding="utf-8"))
    assert payload["contract_version"] == CONTRACT, "wrong contract version"
    out = deepcopy(payload)
    by_id = {a["activity_id"]: a for a in out.get("activity_signals", [])}
    mismatches = 0
    for entry in out.get("time_entries", []):
        (phase, task, label, citation), confidence, basis = choose_mapping(entry, by_id)
        submitted_task = entry.get("submitted_task_code")
        submitted_phase = entry.get("submitted_phase_code")
        flags = []
        if submitted_task and submitted_task != task:
            mismatches += 1
            flags.append({
                "flag": "submitted_code_mismatch",
                "detail": f"submitted {submitted_task} does not match recommended {task}",
                "severity": "needs_review" if confidence >= CODE_MISMATCH_REVIEW_CONFIDENCE else "hold_for_review",
                "source": ENGINE,
                "confidence": confidence,
                "citations": [citation, "client-billing-guidelines.md #4.1", "client-billing-guidelines.md #4.2"]
            })
        entry["code_mapping"] = {
            "recommended_phase_code": phase,
            "recommended_task_code": task,
            "recommended_label": label,
            "submitted_phase_code": submitted_phase,
            "submitted_task_code": submitted_task,
            "basis": basis,
            "flags": flags,
            "confidence": confidence,
            "source": ENGINE,
            "citations": [citation]
        }
    out.setdefault("provenance", {}).setdefault("engines", []).append("code_map/1.0")
    out["provenance"]["generated_at"] = GENERATED_AT
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)
    print(f"code_map: {len(out.get('time_entries', []))} entries, {mismatches} submitted-code mismatch(es) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
