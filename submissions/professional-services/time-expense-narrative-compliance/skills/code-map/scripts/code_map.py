#!/usr/bin/env python3
"""code_map - deterministic phase/task mapping for time-entry narratives (step 3 of 5).

Constants mirror references/task-phase-codes.md and references/client-billing-guidelines.md.

v1.0.2 rules:
- Signals from disabled or unknown sources are dropped first (signal_policy.py, #10.1).
- Linked signals whose activity classes point to more than one task code are CONFLICTING:
  they map to UNMAPPED at 0.40 and are held for review (task-phase-codes.md #5.3). The engine
  never majority-votes a code.
"""
import argparse
import datetime
import json
import os
import sys
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import signal_policy  # noqa: E402  (shared copy shipped next to each engine)

ENGINE = "engine:code_map"
ENGINE_VERSION = "code_map/1.0.2"
CONTRACT = "ps.time-expense-narrative-compliance.v1"
DIRECT_MATCH_CONFIDENCE = 0.92  # task-phase-codes.md #5.1
KEYWORD_MATCH_CONFIDENCE = 0.78  # task-phase-codes.md #5.2
UNKNOWN_CONFIDENCE = 0.40  # task-phase-codes.md #5.3
CODE_MISMATCH_REVIEW_CONFIDENCE = 0.80  # client-billing-guidelines.md #4.2
UNMAPPED = ("UNMAPPED", "UNMAPPED", "Unknown or conflicting activity", "task-phase-codes.md #5.3")

CLASS_MAP = {
    "client_meeting": ("DL", "DL300", "Client meeting or working session", "task-phase-codes.md #3.1"),
    "document_analysis": ("AN", "AN200", "Document analysis tied to a client deliverable", "task-phase-codes.md #2.1"),
    "research": ("AN", "AN220", "Research or options analysis", "task-phase-codes.md #2.2"),
    "deliverable_drafting": ("DL", "DL320", "Drafting or finalizing a client deliverable", "task-phase-codes.md #3.2"),
    "internal_admin": ("NB", "NB900", "Internal non-billable administration", "task-phase-codes.md #4.1"),
    "billing_hygiene": ("BH", "BH910", "Pre-bill and WIP hygiene", "task-phase-codes.md #4.2"),
}
KEYWORDS = [
    ("meeting", CLASS_MAP["client_meeting"]),
    ("workshop", CLASS_MAP["client_meeting"]),
    ("analy", CLASS_MAP["document_analysis"]),
    ("research", CLASS_MAP["research"]),
    ("draft", CLASS_MAP["deliverable_drafting"]),
    ("staffing", CLASS_MAP["internal_admin"]),
]


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
        if "entry_id" not in entry:
            raise InputError("a time entry is missing 'entry_id'")
        if "draft" not in entry:
            raise InputError(f"time entry {entry['entry_id']} has no draft; run narrative_draft.py first")
    return payload


def choose_mapping(entry, linked):
    """Return (mapping tuple, confidence, basis)."""
    if linked:
        classes = sorted({a.get("activity_class") for a in linked})
        if any(a.get("activity_class") == "internal_admin" or a.get("billable_signal") is False for a in linked):
            return CLASS_MAP["internal_admin"], DIRECT_MATCH_CONFIDENCE, "direct_activity_class"
        unknown = [c for c in classes if c not in CLASS_MAP]
        codes = {CLASS_MAP[c][1] for c in classes if c in CLASS_MAP}
        if not unknown and len(codes) == 1:
            return CLASS_MAP[classes[0]], DIRECT_MATCH_CONFIDENCE, "direct_activity_class"
        return UNMAPPED, UNKNOWN_CONFIDENCE, ("conflicting_activity_classes" if len(codes) > 1 else "unknown_activity_class")
    text = " ".join([entry.get("draft", {}).get("narrative", "") or "", entry.get("narrative", "") or ""]).lower()
    for token, mapping in KEYWORDS:
        if token in text:
            return mapping, KEYWORD_MATCH_CONFIDENCE, "keyword_inference"
    return UNMAPPED, UNKNOWN_CONFIDENCE, "unmapped"


def main():
    ap = argparse.ArgumentParser(description="Map drafted time entries to phase/task codes.")
    ap.add_argument("--drafted", required=True, help="Input drafted contract JSON")
    ap.add_argument("--out", required=True, help="Output coded contract JSON")
    ap.add_argument("--signal-config", help="Signal policy JSON (default: the plugin's config/signal-sources.json)")
    ap.add_argument("--generated-at", help="Fixed ISO-8601 UTC timestamp for reproducible golden files")
    args = ap.parse_args()

    try:
        stamp = generated_at(args.generated_at)
        out = deepcopy(load_packet(args.drafted))
        signal_policy.filter_packet(out, config_path=args.signal_config,
                                    script_dir=os.path.dirname(os.path.abspath(__file__)), engine=ENGINE)
    except (InputError, signal_policy.PolicyError) as exc:
        sys.exit(f"code_map: {exc}")

    by_id = {a["activity_id"]: a for a in out["activity_signals"]}
    mismatches = held = 0
    for entry in out["time_entries"]:
        linked = [by_id[a] for a in entry.get("activity_ids", []) if a in by_id]
        (phase, task, label, citation), confidence, basis = choose_mapping(entry, linked)
        submitted_task = entry.get("submitted_task_code")
        submitted_phase = entry.get("submitted_phase_code")
        flags = []
        if task == "UNMAPPED":
            held += 1
            classes = sorted({a.get("activity_class") for a in linked})
            detail = ("linked signals point to different codes (" + ", ".join(
                f"{c}->{CLASS_MAP[c][1] if c in CLASS_MAP else '?'}" for c in classes) + "); no code is recommended"
                      if basis == "conflicting_activity_classes" else "no activity class or keyword maps to a code")
            if submitted_task:
                detail += f"; submitted {submitted_task} cannot be confirmed"
            flags.append({
                "flag": "unmapped_code",
                "detail": detail,
                "severity": "hold_for_review",
                "source": ENGINE,
                "confidence": confidence,
                "citations": ["task-phase-codes.md #5.3", "client-billing-guidelines.md #4.1"],
            })
        elif submitted_task and submitted_task != task:
            mismatches += 1
            flags.append({
                "flag": "submitted_code_mismatch",
                "detail": f"submitted {submitted_task} does not match recommended {task}",
                "severity": "needs_review" if confidence >= CODE_MISMATCH_REVIEW_CONFIDENCE else "hold_for_review",
                "source": ENGINE,
                "confidence": confidence,
                "citations": [citation, "client-billing-guidelines.md #4.1", "client-billing-guidelines.md #4.2"],
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
            "citations": [citation],
        }
    out.setdefault("provenance", {}).setdefault("engines", []).append(ENGINE_VERSION)
    out["provenance"]["generated_at"] = stamp
    try:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(out, fh, indent=2)
            fh.write("\n")
    except OSError as exc:
        sys.exit(f"code_map: cannot write output: {exc}")
    print(f"code_map: {len(out['time_entries'])} entries, {mismatches} submitted-code mismatch(es), "
          f"{held} unmapped/held -> {os.path.basename(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
