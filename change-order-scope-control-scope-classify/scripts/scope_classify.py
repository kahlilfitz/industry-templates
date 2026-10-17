#!/usr/bin/env python3
"""Deterministic scope classifier for ps.change-order-scope-control.v1."""
import argparse
import json
import sys

ENGINE = "engine:scope_classify"
EXPLICIT_EXCLUSION_PRECEDENCE = True  # scope-classification-rules.md #2.1
FAILED_ASSUMPTION_IS_OUT_OF_SCOPE = True  # scope-classification-rules.md #2.2
MATERIAL_SIMILARITY_FLOOR = 0.82  # scope-classification-rules.md #3.1
CONFIDENCE_FLOOR = 0.75  # scope-classification-rules.md #4.1


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def clauses_of(match, *types):
    return [c for c in match.get("matched_clauses", []) if c.get("clause_type") in types]


def citation_for(*clauses):
    return "; ".join(c["citation"] for c in clauses if c)


def quote_for(*clauses):
    return " | ".join(f"{c['clause_id']}: {c['quote']}" for c in clauses if c)


def has_direct_conflict(supports, exclusions):
    support_groups = {c.get("conflict_group") for c in supports if c.get("conflict_group")}
    exclusion_groups = {c.get("conflict_group") for c in exclusions if c.get("conflict_group")}
    return bool(support_groups & exclusion_groups)


def classify(match):
    supports = clauses_of(match, "scope", "deliverable")
    exclusions = clauses_of(match, "exclusion")
    assumptions = clauses_of(match, "assumption")
    change_controls = clauses_of(match, "change_control")

    if match.get("confidence", 0.0) < CONFIDENCE_FLOOR or not match.get("matched_clauses"):
        return {
            "classification": "AMBIGUOUS",
            "rule": "scope-classification-rules.md #4.1,#4.3",
            "rationale": f"match confidence {match.get('confidence', 0.0)} is below {CONFIDENCE_FLOOR} or missing cited SOW support",
            "clauses": match.get("matched_clauses", []),
            "confidence": match.get("confidence", 0.0)
        }

    if has_direct_conflict(supports, exclusions):
        involved = supports + exclusions
        return {
            "classification": "AMBIGUOUS",
            "rule": "scope-classification-rules.md #4.2",
            "rationale": "the SOW deliverable list and exclusion list directly contradict each other for this request; human commercial review required",
            "clauses": involved,
            "confidence": min(0.74, match.get("confidence", 0.0))
        }

    if FAILED_ASSUMPTION_IS_OUT_OF_SCOPE and match.get("failed_assumption") and assumptions:
        involved = assumptions + change_controls[:1]
        return {
            "classification": "OUT_OF_SCOPE",
            "rule": "scope-classification-rules.md #2.2",
            "rationale": "request is caused by a failed SOW assumption; change-control route applies",
            "clauses": involved,
            "confidence": min(match.get("confidence", 0.0), 0.9)
        }

    if EXPLICIT_EXCLUSION_PRECEDENCE and exclusions:
        return {
            "classification": "OUT_OF_SCOPE",
            "rule": "scope-classification-rules.md #2.1",
            "rationale": "request matches an explicit SOW exclusion; explicit exclusion beats implied inclusion",
            "clauses": exclusions,
            "confidence": min(match.get("confidence", 0.0), 0.91)
        }

    if supports and match.get("material_similarity", 0.0) >= MATERIAL_SIMILARITY_FLOOR:
        return {
            "classification": "IN_SCOPE",
            "rule": "scope-classification-rules.md #3.1,#3.2",
            "rationale": f"request is materially similar to a listed deliverable ({match.get('material_similarity', 0.0)} >= {MATERIAL_SIMILARITY_FLOOR}) and no explicit exclusion applies",
            "clauses": supports[:1],
            "confidence": min(match.get("confidence", 0.0), 0.93)
        }

    return {
        "classification": "OUT_OF_SCOPE",
        "rule": "scope-classification-rules.md #2.3",
        "rationale": "request is not listed in the closed deliverable list and is not materially similar to a listed deliverable",
        "clauses": supports or match.get("matched_clauses", []),
        "confidence": min(match.get("confidence", 0.0), 0.84)
    }


def main():
    parser = argparse.ArgumentParser(description="Classify matched requests as IN_SCOPE, OUT_OF_SCOPE or AMBIGUOUS.")
    parser.add_argument("--matched", required=True, help="matched.json from scope_match.py")
    parser.add_argument("--out", required=True, help="Output classified.json path")
    args = parser.parse_args()

    payload = load(args.matched)
    assert payload["contract_version"] == "ps.change-order-scope-control.v1", "wrong contract version"

    classifications = []
    ambiguity_list = []
    escalations = list(payload.get("escalations", []))
    for match in payload.get("matches", []):
        result = classify(match)
        clauses = result["clauses"]
        item = {
            "request_id": match["request_id"],
            "summary": match["summary"],
            "classification": result["classification"],
            "rule": result["rule"],
            "rationale": result["rationale"],
            "governing_clause_quote": quote_for(*clauses) if clauses else "NO CITED SOW CLAUSE",
            "citation": citation_for(*clauses) if clauses else match["citation"],
            "confidence": round(result["confidence"], 2),
            "source": ENGINE
        }
        classifications.append(item)
        if result["classification"] == "AMBIGUOUS":
            ambiguity = {
                "request_id": match["request_id"],
                "summary": match["summary"],
                "reason": result["rationale"],
                "citations": item["citation"],
                "required_human_role": "engagement partner or contract manager",
                "source": ENGINE,
                "confidence": item["confidence"]
            }
            ambiguity_list.append(ambiguity)
            escalations.append(f"{match['request_id']}: AMBIGUOUS - {result['rationale']} ({result['rule']})")

    payload["classifications"] = classifications
    payload["ambiguity_list"] = ambiguity_list
    payload["escalations"] = escalations
    payload.setdefault("provenance", {}).setdefault("engines", []).append("scope_classify/1.0")
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    counts = {name: sum(1 for c in classifications if c["classification"] == name) for name in ["IN_SCOPE", "OUT_OF_SCOPE", "AMBIGUOUS"]}
    print(f"scope_classify: {counts['IN_SCOPE']} in_scope, {counts['OUT_OF_SCOPE']} out_of_scope, {counts['AMBIGUOUS']} ambiguous -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
