#!/usr/bin/env python3
"""assertion_map - deterministic assertion-to-evidence support engine."""
import argparse
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import assertion_rules as rules  # noqa: E402  shared byte-identical with gate-check (tests/check_shared_copies.py)

ENGINE = rules.AM_ENGINE
ENGINE_VERSION = "1.0.4"
CONTRACT_VERSION = "ps.deliverable-review-quality-gate.v1"
InputError = rules.InputError


def load_json(path):
    return rules.load_json_file(path)


def validate_generated_at(value):
    if value is None:
        return None
    candidate = value.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise InputError("--generated-at must be an ISO-8601 timestamp") from exc
    return value


def require_contract(payload):
    if not isinstance(payload, dict):
        raise InputError("input must be a JSON object")
    if payload.get("contract_version") != CONTRACT_VERSION:
        raise InputError(f"expected contract {CONTRACT_VERSION}, got {rules.describe(payload.get('contract_version'))}")
    for key in ("deliverable", "criteria"):
        if not isinstance(payload.get(key), dict):
            raise InputError(f"missing required object: {key}")
    for key in ("assertions", "evidence_set"):
        if key not in payload:
            raise InputError(f"missing required array: {key}")
        if not isinstance(payload[key], list):
            raise InputError(f"{key} must be an array")
    criteria_sections = payload["criteria"].get("criteria_sections")
    if criteria_sections is None:
        raise InputError("missing required criteria list: criteria.criteria_sections")
    if not isinstance(criteria_sections, list):
        raise InputError("criteria.criteria_sections must be an array")
    for index, section in enumerate(criteria_sections):
        if not isinstance(section, str) or not section.strip():
            raise InputError(f"criteria.criteria_sections[{index}] must be a non-blank string, got {rules.describe(section)}")
    for key in ("findings", "escalations"):
        if key in payload and not isinstance(payload[key], list):
            raise InputError(f"{key} must be an array")

def main():
    parser = argparse.ArgumentParser(description="Map assertions to evidence support deterministically.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args()
    try:
        generated_at = validate_generated_at(args.generated_at)
        payload = load_json(args.input)
        require_contract(payload)
        evidence_by_id = rules.evidence_index(payload["evidence_set"])
        rules.validate_assertions(payload["assertions"])
        rules.validate_contract(payload, "assertion_map")
        # Flagged text is withheld before mapping, so no mapping, finding or later stage repeats it
        # (quality-gate-criteria.md #8.7); gate_check raises the G8 hold for every marker.
        rules.withhold_untrusted(payload)
        evidence_by_id = rules.evidence_index(payload["evidence_set"])
        findings = list(payload.get("findings", []))
        escalations = list(payload.get("escalations", []))
        mappings = []
        for assertion in payload["assertions"]:
            mapping, finding, escalation = rules.map_assertion(assertion, evidence_by_id)
            mappings.append(mapping)
            # Appended once: re-running assertion_map on its own output reproduces it instead of duplicating findings.
            if finding and finding not in findings:
                findings.append(finding)
            if finding and escalation not in escalations:
                escalations.append(escalation)
        payload["assertion_mappings"], payload["findings"], payload["escalations"] = mappings, findings, escalations
        provenance = payload.setdefault("provenance", {})
        if generated_at and isinstance(provenance, dict):
            provenance["generated_at"] = generated_at
        rules.record_engine(payload, f"assertion_map/{ENGINE_VERSION}")
        rules.write_json_atomic(args.out, payload)
        unsupported = sum(1 for item in mappings if item["support_status"] == "unsupported")
        limited = sum(1 for item in mappings if item["support_status"] == "limited")
        print(f"assertion_map: {len(mappings)} assertion(s), {unsupported} unsupported, {limited} limited -> {os.path.basename(args.out)}")
        return 0
    except InputError as exc:
        print(f"assertion_map input error: {exc}", file=sys.stderr)
        return 1
    except RecursionError:
        print("assertion_map input error: input is nested too deeply to process safely", file=sys.stderr)
        return 1
    except (KeyError, TypeError, AttributeError, ValueError, IndexError) as exc:
        print(f"assertion_map input error: malformed input ({type(exc).__name__}; details withheld because they may quote untrusted text)", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
