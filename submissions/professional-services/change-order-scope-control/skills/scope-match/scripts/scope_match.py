#!/usr/bin/env python3
"""Deterministic SOW clause matcher for ps.change-order-scope-control.v1."""
import argparse
import json
import sys

ENGINE = "engine:scope_match"
CONFIDENCE_FLOOR = 0.75  # scope-classification-rules.md #4.1


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def shared_tags(request, clause):
    req_tags = {t.lower() for t in request.get("tags", [])}
    clause_tags = {t.lower() for t in clause.get("tags", [])}
    return sorted(req_tags & clause_tags)


def match_confidence(request, clause, tags):
    if not tags:
        return 0.0
    base = 0.70 + min(0.20, 0.05 * len(tags))
    if clause.get("type") in {"exclusion", "assumption", "deliverable", "change_control"}:
        base += 0.04
    return round(min(request.get("confidence", 0.0), clause.get("confidence", 0.0), base), 2)


def main():
    parser = argparse.ArgumentParser(description="Match requests to candidate SOW clauses.")
    parser.add_argument("--sow", required=True, help="SOW clause JSON from sow-retrieve")
    parser.add_argument("--requests", required=True, help="Structured request JSON from request-intake")
    parser.add_argument("--prior-change-orders", required=True, help="Prior change orders / accommodations JSON")
    parser.add_argument("--delivered-artifacts", required=True, help="Delivered-artifact inventory JSON")
    parser.add_argument("--out", required=True, help="Output matched.json path")
    args = parser.parse_args()

    sow = load(args.sow)
    requests = load(args.requests)
    prior = load(args.prior_change_orders)
    artifacts = load(args.delivered_artifacts)

    assert sow["contract_version"] == "ps.change-order-scope-control.v1", "wrong SOW contract version"
    assert requests["contract_version"] == "ps.change-order-scope-control.v1", "wrong request contract version"

    clauses = sow.get("sow", {}).get("clauses", [])
    matches = []
    escalations = []
    for request in requests.get("requests", []):
        candidates = []
        for clause in clauses:
            tags = shared_tags(request, clause)
            if not tags:
                continue
            confidence = match_confidence(request, clause, tags)
            candidates.append({
                "clause_id": clause["id"],
                "clause_type": clause["type"],
                "quote": clause["quote"],
                "citation": clause["citation"],
                "conflict_group": clause.get("conflict_group", ""),
                "match_reason": "shared tags: " + ", ".join(tags),
                "confidence": confidence,
                "source": ENGINE
            })
        candidates.sort(key=lambda c: (c["clause_type"], c["clause_id"]))
        confidence = min([request.get("confidence", 0.0)] + [c["confidence"] for c in candidates]) if candidates else 0.0
        if not candidates or confidence < CONFIDENCE_FLOOR:
            escalations.append(
                f"{request['request_id']}: no high-confidence SOW match; route to classification ambiguity "
                f"(scope-classification-rules.md #4.1,#4.3)"
            )
        matches.append({
            "request_id": request["request_id"],
            "summary": request["summary"],
            "request_text": request.get("request_text", ""),
            "estimate_hours": request.get("estimate_hours", {}),
            "estimate_basis": request.get("estimate_basis", ""),
            "material_similarity": request.get("material_similarity", 0.0),
            "failed_assumption": bool(request.get("failed_assumption", False)),
            "matched_clauses": candidates,
            "confidence": round(confidence, 2),
            "source": ENGINE,
            "citation": request["citation"]
        })

    payload = {
        "contract_version": "ps.change-order-scope-control.v1",
        "engagement": sow["engagement"],
        "sow": sow["sow"],
        "requests": requests["requests"],
        "matches": matches,
        "prior_change_orders": prior.get("prior_change_orders", []),
        "delivered_artifacts": artifacts.get("delivered_artifacts", []),
        "escalations": escalations,
        "provenance": {
            "engines": ["scope_match/1.0"],
            "generated_at": sow.get("provenance", {}).get("generated_at", "2026-09-23T00:00:00+00:00"),
            "demo_scenario": sow.get("provenance", {}).get("demo_scenario", "")
        }
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"scope_match: {len(matches)} request(s), {sum(len(m['matched_clauses']) for m in matches)} clause match(es), {len(escalations)} escalation(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
