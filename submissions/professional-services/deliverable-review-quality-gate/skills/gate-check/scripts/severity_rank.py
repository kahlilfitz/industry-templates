#!/usr/bin/env python3
"""severity_rank - deterministic finding ranking and release-readiness verdict."""
import argparse, json, sys

ENGINE = "engine:severity_rank"
SEVERITY_ORDER = {"release_blocker": 0, "must_fix": 1, "advisory": 2}  # severity-rules.md #1.1-#1.3
CONFIDENCE_FLOOR = 0.72  # severity-rules.md #2.1
BLOCKER_NEVER_DOWNGRADE = True  # severity-rules.md #3.1
STATUS_WITH_BLOCKER = "not_ready_for_release"  # severity-rules.md #3.3
STATUS_WITH_MUST_FIX = "partner_review_required_must_fix"  # severity-rules.md #3.3
STATUS_WITH_ADVISORIES = "partner_review_ready_with_advisories"  # severity-rules.md #3.3
STATUS_CLEAN = "partner_review_ready_no_engine_findings"  # severity-rules.md #3.3

def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)

def sort_key(item):
    location = item.get("location", {})
    return (SEVERITY_ORDER[item["severity"]], -float(item.get("confidence", 0.0)), int(location.get("page", 9999)), int(location.get("paragraph", 9999)), item.get("finding_id", ""))

def main():
    parser = argparse.ArgumentParser(description="Rank gate findings and compute release-readiness status.")
    parser.add_argument("--gates", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    payload = load_json(args.gates)
    assert payload["contract_version"] == "ps.deliverable-review-quality-gate.v1", "wrong contract version"
    findings = list(payload.get("findings", []))
    for item in findings:
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
        summary = f"{blockers} release blocker(s) require reviewing-partner/QRM judgement before release. Blockers cannot be auto-downgraded."
    elif must_fix:
        status = STATUS_WITH_MUST_FIX
        summary = f"{must_fix} must-fix item(s) remain before partner release judgement."
    elif advisories:
        status = STATUS_WITH_ADVISORIES
        summary = "Only advisory items remain; partner judgement still required."
    else:
        status = STATUS_CLEAN
        summary = "No engine findings; partner judgement still required to clear the gate."
    payload["ranked_findings"] = ranked
    payload["release_readiness"] = {"status": status, "release_blockers": blockers, "must_fix": must_fix, "advisories": advisories, "summary": summary, "confidence": 0.96, "source": ENGINE, "citation": "severity-rules.md #3.1-#3.3; severity-rules.md #4.1-#4.2"}
    payload.setdefault("provenance", {}).setdefault("engines", []).append("severity_rank/1.0")
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    print(f"severity_rank: status={status}, ranked_findings={len(ranked)} -> {args.out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
