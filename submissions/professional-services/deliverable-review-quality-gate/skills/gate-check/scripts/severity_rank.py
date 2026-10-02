#!/usr/bin/env python3
"""severity_rank - deterministic finding ranking and review-status verdict."""
import argparse
import json
import os
import sys
from datetime import datetime

ENGINE = "engine:severity_rank"
ENGINE_VERSION = "1.0.4"
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

MAX_INPUT_DEPTH = 64  # mirrors assertion_rules.MAX_INPUT_DEPTH


def check_depth(value, max_depth=MAX_INPUT_DEPTH):
    """Reject nesting deeper than max_depth iteratively, so hostile input can never reach a RecursionError."""
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, (dict, list)):
            if depth > max_depth:
                raise InputError(f"input is nested more than {max_depth} levels deep; the review contract never nests that deeply")
            stack.extend((child, depth + 1) for child in (item.values() if isinstance(item, dict) else item))
    return value


def load_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        raise InputError(f"could not read input JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON input: {exc}") from exc
    except RecursionError as exc:
        raise InputError("input JSON is nested too deeply to process safely") from exc
    return check_depth(payload)

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
    # gate_check always emits both arrays; an absent one means the gate run is missing, never "nothing found".
    for key in ("findings", "escalations"):
        if key not in payload:
            raise InputError(f"missing required array: {key} (run gate_check first; an empty run still emits [])")
        if not isinstance(payload[key], list):
            raise InputError(f"{key} must be an array")
    for index, item in enumerate(payload["escalations"]):
        if not (isinstance(item, dict) or (isinstance(item, str) and item.strip())):
            raise InputError(f"escalations[{index}] must be a non-blank string or an object, got {item!r}")

def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)

def validate_finding(index, item):
    """Fail closed with a clear message on values the ranking cannot order (severity-rules.md #3.2)."""
    if not isinstance(item, dict):
        raise InputError(f"findings[{index}] must be an object")
    label = f"findings[{index}] ({item.get('finding_id', '<unknown>')})"
    if not isinstance(item.get("finding_id"), str) or not item["finding_id"].strip():
        raise InputError(f"findings[{index}] missing required field: finding_id")
    if item.get("severity") not in SEVERITY_ORDER:
        raise InputError(f"{item.get('finding_id', '<unknown>')}: unknown severity {item.get('severity')!r}")
    if "confidence" in item and not is_number(item["confidence"]):
        raise InputError(f"{label}: confidence must be a number, got {item['confidence']!r}")
    location = item.get("location")
    if location is None:
        return
    if not isinstance(location, dict):
        raise InputError(f"{label}: location must be an object")
    for key in ("page", "paragraph"):
        value = location.get(key)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise InputError(f"{label}: location.{key} must be an integer or null, got {value!r}; record the physical "
                             f"page number and keep printed labels such as roman numerals in location.label")

def sort_key(item):
    # Findings without a page or paragraph (register- or field-level) rank after page-located findings
    # of the same severity and confidence.
    location = item.get("location") or {}
    page, paragraph = location.get("page"), location.get("paragraph")
    return (SEVERITY_ORDER[item["severity"]], -float(item.get("confidence", 0.0)), 9999 if page is None else page, 9999 if paragraph is None else paragraph, item.get("finding_id", ""))

def collapse_duplicates(findings):
    """Keep one finding per finding_id at the highest severity (first occurrence on a tie), so a duplicate is never
    counted twice and can never lower severity (severity-rules.md #3.1). Returns (kept, {finding_id: copies})."""
    kept, positions, copies = [], {}, {}
    for item in findings:
        finding_id = item["finding_id"]
        if finding_id not in positions:
            positions[finding_id] = len(kept)
            kept.append(item)
            continue
        copies[finding_id] = copies.get(finding_id, 1) + 1
        current = kept[positions[finding_id]]
        if SEVERITY_ORDER[item["severity"]] < SEVERITY_ORDER[current["severity"]]:
            kept[positions[finding_id]] = item
    return kept, copies

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
        for index, item in enumerate(payload["findings"]):
            validate_finding(index, item)
        findings, duplicates = collapse_duplicates(payload["findings"])
        payload["findings"] = findings
        escalations = payload["escalations"]
        for finding_id, count in duplicates.items():
            kept = next(item for item in findings if item["finding_id"] == finding_id)
            escalations.append(f"{finding_id}: {count} findings shared this finding_id; one was kept at the highest severity ({kept['severity']}) - reviewing partner/QRM to confirm (severity-rules.md #3.4)")
        for item in findings:
            if float(item.get("confidence", 1.0)) < CONFIDENCE_FLOOR:
                escalations.append(f"{item['finding_id']}: confidence {item.get('confidence')} below {CONFIDENCE_FLOOR} - human confirmation required (severity-rules.md #2.1)")
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
        elif escalations:
            # An escalation is a hold even without a finding: it can never end in the no-findings verdict.
            status = STATUS_WITH_BLOCKER
            summary = f"No engine findings, but {len(escalations)} escalation(s) hold release for reviewing-partner/QRM judgement before any client issue."
        else:
            status = STATUS_CLEAN
            summary = "No engine findings; partner/QRM judgement still required."
        if escalations and (blockers or must_fix or advisories):
            # The verdict follows the highest finding severity; the summary must still surface every escalation.
            count = len(escalations)
            summary += f" {count} escalation{' needs' if count == 1 else 's need'} partner/QRM confirmation before release."
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
    except RecursionError:
        print("severity_rank input error: input is nested too deeply to process safely", file=sys.stderr)
        return 1
    except (KeyError, TypeError, AttributeError, ValueError, IndexError) as exc:
        print(f"severity_rank input error: malformed input ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
