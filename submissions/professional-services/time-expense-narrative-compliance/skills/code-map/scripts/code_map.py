#!/usr/bin/env python3
"""code_map - deterministic phase/task mapping for time-entry narratives (step 3 of 5).

The rules live in the shared billing_rules.py (identical copies next to guideline_check.py and
exception_report.py), whose constants mirror references/task-phase-codes.md and
references/client-billing-guidelines.md. guideline_check.py recomputes the same mapping and holds
an entry whose supplied code_mapping disagrees (client-billing-guidelines.md #13.1).

v1.0.4 rules:
- Signals from disabled or unknown sources are dropped first (signal_policy.py, #10.1), and rows
  outside the recorded timekeeper scope are withheld (#12.1).
- Activity-class text that trips the embedded-instruction tripwire is never echoed in a flag (#11.2).
- Linked signals whose activity classes point to more than one task code are CONFLICTING:
  they map to UNMAPPED at 0.40 and are held for review (task-phase-codes.md #5.3). The engine
  never majority-votes a code. Every linked signal is mapped BEFORE any non-billable decision,
  so a client meeting plus an internal call is a conflict, not NB900 (#4.1 vs #3.1).
- A non-billable signal maps to NB900 (#4.1) unless its class is billing_hygiene -> BH910 (#4.2).
"""
import argparse
import datetime
import json
import os
import sys
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import billing_rules  # noqa: E402  (shared rules, identical copies next to guideline_check.py and exception_report.py)
import signal_policy  # noqa: E402  (shared copy shipped next to each engine)

ENGINE = billing_rules.CODE_MAP_ENGINE
ENGINE_VERSION = "code_map/1.0.4"
CONTRACT = "ps.time-expense-narrative-compliance.v1"


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
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputError(f"cannot read {os.path.basename(path)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise InputError("input is not a JSON object")
    if payload.get("contract_version") != CONTRACT:
        raise InputError(f"expected contract {CONTRACT}, got {payload.get('contract_version')!r}")
    signal_policy.validate_packet(payload, "drafted")
    return payload


def main():
    ap = argparse.ArgumentParser(description="Map drafted time entries to phase/task codes.")
    ap.add_argument("--drafted", required=True, help="Input drafted contract JSON")
    ap.add_argument("--out", required=True, help="Output coded contract JSON")
    ap.add_argument("--signal-config", help="Additional signal policy JSON; it can only narrow the plugin's config/signal-sources.json, which is always applied (most restrictive wins)")
    ap.add_argument("--generated-at", help="Fixed ISO-8601 UTC timestamp for reproducible golden files")
    args = ap.parse_args()

    try:
        stamp = generated_at(args.generated_at)
        out = deepcopy(load_packet(args.drafted))
        signal_policy.enforce_timekeeper_scope(out, engine=ENGINE)
        signal_policy.filter_packet(out, config_path=args.signal_config,
                                    script_dir=os.path.dirname(os.path.abspath(__file__)), engine=ENGINE)
    except (InputError, signal_policy.PolicyError) as exc:
        sys.exit(f"code_map: {exc}")

    by_id = {a["activity_id"]: a for a in out["activity_signals"]}
    mismatches = held = 0
    for entry in out["time_entries"]:
        linked = [by_id[a] for a in entry.get("activity_ids", []) if a in by_id]
        entry["code_mapping"] = mapping = billing_rules.code_mapping(entry, linked)
        held += mapping["recommended_task_code"] == "UNMAPPED"
        mismatches += any(f["flag"] == "submitted_code_mismatch" for f in mapping["flags"])
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
