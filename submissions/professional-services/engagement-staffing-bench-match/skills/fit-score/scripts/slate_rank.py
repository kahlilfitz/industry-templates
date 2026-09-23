#!/usr/bin/env python3
"""slate_rank - deterministic provisional ranking for staffing slates."""
import argparse
import json
import sys

ENGINE = "engine:slate_rank"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scored", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.scored, encoding="utf-8") as f:
        payload = json.load(f)
    assert payload["contract_version"] == "ps.engagement-staffing-bench-match.v1", "wrong contract version"

    ranked_roles = []
    for role in payload.get("scored_roles", []):
        ranked = sorted(
            role["candidate_scores"],
            key=lambda c: (-float(c["fit_score"]), c["candidate_id"])  # fit-scoring-rubric.md #7.1
        )
        for i, candidate in enumerate(ranked, start=1):
            candidate["provisional_rank"] = i
            candidate["rank_source"] = ENGINE
            candidate["rank_citation"] = "fit-scoring-rubric.md #7.1,#7.3"
        ranked_roles.append({
            "role_id": role["role_id"],
            "role_title": role["role_title"],
            "candidate_slate": ranked,
            "source": ENGINE,
            "confidence": role.get("confidence", 0.99),
            "citation": "fit-scoring-rubric.md #7.1,#7.3"
        })

    payload["ranked_roles"] = ranked_roles
    payload.setdefault("provenance", {}).setdefault("engines", []).append("slate_rank/1.0")
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"slate_rank: {len(ranked_roles)} role(s) ranked -> {args.out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
