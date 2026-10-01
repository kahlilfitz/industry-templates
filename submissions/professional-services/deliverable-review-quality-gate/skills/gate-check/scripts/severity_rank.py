#!/usr/bin/env python3
"""severity_rank - deterministic finding ranking and review-status verdict."""
import argparse
import json
import os
import sys
from datetime import datetime

ENGINE = "engine:severity_rank"
ENGINE_VERSION = "1.0.1"
CONTRACT_VERSION = "ps.deliverable-review-quality-gate.v1"
SEVERITY_ORDER = {"release_blocker": 0, "must_fix": 1, "advisory": 2}  # severity-rules.md #1.1-#1.3
CONFIDENCE_FLOOR = 0.72  # severity-rules.md #2.1
BLOCKER_NEVER_DOWNGRADE = True  # severity-rules.md #3.1
STATUS_WITH_BLOCKER = "not_ready_for_release"  # severity-rules.md #3.3
STATUS_WITH_MUST_FIX = "partner_review_required_must_fix"  # severity-rules.md #3.3
STATUS_WITH_ADVISORIES = "partner_review_required_advisories_only"  # severity-rules.md #3.3
STATUS_CLEAN = "partner_review_required_no_engine_findings"  # severity-rules.md #3.3


class InputError(ValueError):
    """Raised for malformed or unsafe engine input."""

def load_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise InputError(f"could not read input JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON input: {exc}") from exc

def validate_generated_at(value):
    if value is None:
        return None
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError("--generated-at must be an ISO-8601 timestamp") from exc
    return value

def require_contract(payload):
    if not isinstance(payload, dict):
        raise InputError("input must be a JSON object")
    if payload.get("contract_version") != CONTRACT_VERSION:
        raise InputError(f"expected contract {CONTRACT_VERSION}, got {payload.get('contract_version')!r}")
    if not isinstance(payload.get("findings", []), list):
        raise InputError("findings must be an array")

def sort_key(item):
    location = item.get("location", {})
    return (SEVERITY_ORDER[item["severity"]], -float(item.get("confidence", 0.0)), int(location.get("page", 9999)), int(location.get("paragraph", 9999)), item.get("finding_id", ""))

def main():
    parser = argparse.ArgumentParser(description="Rank gate findings and compute release-readiness status.")
    parser.add_argument("--gates", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args()
    try:
        generated_at = validate_generated_at(args.generated_at)
        payload = load_json(args.gates)
        require_contract(payload)
        findings = list(payload.get("findings", []))
        for index, item in enumerate(findings):
            if not isinstance(item, dict):
                raise InputError(f"findings[{index}] must be an object")
            if item.get("severity") not in SEVERITY_ORDER:
                raise InputError(f"{item.get('finding_id', '<unknown>')}: unknown severity {item.get('severity')!r}")
            if float(item.get("confidence", 1.0)) < CONFIDENCE_FLOOR:
                payload.setdefault("escalations", []).append(f"{item['finding_id']}: confidence {item.get('confidence')} below {CONFIDENCE_FLOOR} - human confirmation required (severity-rules.md #2.1)")
        ranked = []
        for index, item in enumerate(sorted(findings, key=sort_key), start=1):
            ranked_item = dict(item)
            ranked_item["rank"] = index
            ranked_item["ranking_basis"] = "severity, confidence, page, paragraph (severity-rules.md #3.2)"
            ranked.append(ranked_item)
        blockers = sum(1 for item in findings if item["severity"] == "release_blocker")
        must_fix = sum(1 for item in findings if item["severity"] == "must_fix")
        advisories = sum(1 for item in findings if item["severity"] == "advisory")
        if blockers:
            status = STATUS_WITH_BLOCKER
            summary = f"{blockers} release blocker(s) require reviewing-partner/QRM judgement before any client issue. Blockers cannot be auto-downgraded."
        elif must_fix:
            status = STATUS_WITH_MUST_FIX
            summary = f"{must_fix} must-fix item(s) remain before partner/QRM judgement."
        elif advisories:
            status = STATUS_WITH_ADVISORIES
            summary = "Only advisory items remain; partner/QRM judgement still required."
        else:
            status = STATUS_CLEAN
            summary = "No engine findings; partner/QRM judgement still required."
        payload["ranked_findings"] = ranked
        payload["release_readiness"] = {"status": status, "release_blockers": blockers, "must_fix": must_fix, "advisories": advisories, "summary": summary, "confidence": 0.96, "source": ENGINE, "citation": "severity-rules.md #3.1-#3.3; severity-rules.md #4.1-#4.2"}
        provenance = payload.setdefault("provenance", {})
        if generated_at:
            provenance["generated_at"] = generated_at
        provenance.setdefault("engines", []).append(f"severity_rank/{ENGINE_VERSION}")
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        print(f"severity_rank: status={status}, ranked_findings={len(ranked)} -> {os.path.basename(args.out)}")
        return 0
    except InputError as exc:
        print(f"severity_rank input error: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
