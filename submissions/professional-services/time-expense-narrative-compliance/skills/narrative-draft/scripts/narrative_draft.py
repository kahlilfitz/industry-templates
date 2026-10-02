#!/usr/bin/env python3
"""narrative_draft - deterministic narrative drafting engine (step 2 of 5).

Reads a ps.time-expense-narrative-compliance.v1 activity packet and writes the same contract
with draft narratives attached. The model may offer improved prose beside the packet, but this engine
owns every draft, linked evidence, confidence, provenance and citations; later stages re-derive each
draft and refuse one that differs (client-billing-guidelines.md #13.5).

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
- The drafting rules live in the shared signal_policy.py (derive_draft), so every later stage
  re-derives each draft from the same evidence and refuses a carried draft that differs (#13.5).
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

ENGINE = signal_policy.DRAFT_ENGINE  # "engine:narrative_draft"
ENGINE_VERSION = "narrative_draft/1.0.4"
CONTRACT = "ps.time-expense-narrative-compliance.v1"


class InputError(ValueError):
    pass


def generated_at(override):
    if override:
        if not signal_policy.contract_check.valid_timestamp(override):
            raise InputError(f"--generated-at must be an ISO-8601 timestamp with seconds and an offset (for example 2026-09-23T00:00:00Z), got a string of {len(override)} character(s)")
        return override
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_packet(path):
    payload = signal_policy.read_json(path, InputError, "activity input")
    if not isinstance(payload, dict):
        raise InputError("input is not a JSON object")
    if payload.get("contract_version") != CONTRACT:
        raise InputError(f"expected a {CONTRACT} object (contract_version must be the contract constant)")
    signal_policy.validate_packet(payload, "activity")
    return payload


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
        sys.exit(f"narrative_draft: {signal_policy.error_text(exc)}")

    # The drafting rules are shared (signal_policy.derive_draft) so that every later stage re-derives the same
    # draft from the same evidence and refuses a carried draft that differs (#13.5).
    signal_policy.derive_drafts(out)
    drafted_count = sum(e["draft"]["status"] in signal_policy.GROUNDED_STATUSES for e in out["time_entries"])
    out.setdefault("provenance", {}).setdefault("engines", []).append(ENGINE_VERSION)
    out["provenance"]["generated_at"] = stamp
    # #11.4: the ledgers describe the packet as written (the stamp replaces a withheld generated_at).
    signal_policy.write_ledgers(out)
    try:
        signal_policy.write_output(args.out, signal_policy.dump_json(out))
    except (OSError, ValueError) as exc:  # ValueError covers NaN in dump_json and UnicodeEncodeError
        sys.exit(f"narrative_draft: cannot write output: {signal_policy.error_text(exc)}")
    print(f"narrative_draft: {len(out['time_entries'])} entries, {drafted_count} drafted, "
          f"{len(out['provenance'].get('excluded_signals', []))} excluded signal(s) -> drafted packet written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
