#!/usr/bin/env python3
"""constraint_check - deterministic staffing eligibility Govern engine."""
import argparse
import json
import sys
from datetime import date

ENGINE = "engine:constraint_check"
CONFIDENCE_FLOOR = 0.75       # independence-eligibility-rules.md #8.1
PRIOR_ROLE_COOLING_DAYS = 365 # independence-eligibility-rules.md #2.1
PRIOR_ROLE_REVIEW_DAYS = 730  # independence-eligibility-rules.md #2.2
DIVEST_REVIEW_DAYS = 30       # independence-eligibility-rules.md #3.2
ADVERSE_REVIEW_DAYS = 180     # independence-eligibility-rules.md #4.2
ASSURANCE_LOOKBACK_DAYS = 730 # independence-eligibility-rules.md #5.1
CAPACITY_REVIEW_BAND = 10.0   # independence-eligibility-rules.md #6.2
MIN_RECOMMENDABLE_SCORE = 70.0 # fit-scoring-rubric.md #7.2

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def days_between(start, end):
    return (date.fromisoformat(start) - date.fromisoformat(end)).days

def candidate_constraints(constraints, candidate_id):
    return [c for c in constraints.get("constraints", []) if c.get("candidate_id") == candidate_id]

def verdict_for(role, row, constraints):
    verdict = "eligible"
    reasons = []
    citations = []
    start = next(r for r in constraints["roles"] if r["role_id"] == role["role_id"])["start_date"]
    client = constraints["engagement"]["client_name"]

    if row.get("confidence", 1.0) < CONFIDENCE_FLOOR:
        verdict = "needs_review"
        reasons.append(f"confidence {row.get('confidence')} below {CONFIDENCE_FLOOR}")
        citations.append("independence-eligibility-rules.md #8.1")

    for item in candidate_constraints(constraints, row["candidate_id"]):
        kind = item["type"]
        applies = item.get("client_name") in (None, "", client)
        if not applies:
            continue
        if kind == "financial_interest" and item.get("status") == "active" and item.get("material", False):
            verdict = "ineligible"
            reasons.append("unresolved material financial interest in client")
            citations.append("independence-eligibility-rules.md #3.1; " + item["citation"])
        elif kind == "financial_interest" and item.get("status") == "divested":
            days = days_between(start, item["resolved_date"])
            if days <= DIVEST_REVIEW_DAYS and verdict != "ineligible":
                verdict = "needs_review"
                reasons.append(f"material interest divested {days} days before role start")
                citations.append("independence-eligibility-rules.md #3.2; " + item["citation"])
        elif kind == "prior_client_role":
            days = days_between(start, item["end_date"])
            if item.get("role_type") in ("employee", "officer", "board_member") and days <= PRIOR_ROLE_COOLING_DAYS:
                verdict = "ineligible"
                reasons.append(f"prior {item.get('role_type')} role at client ended {days} days before start")
                citations.append("independence-eligibility-rules.md #2.1; " + item["citation"])
            elif days <= PRIOR_ROLE_REVIEW_DAYS and verdict != "ineligible":
                verdict = "needs_review"
                reasons.append(f"prior client role ended {days} days before start")
                citations.append("independence-eligibility-rules.md #2.2; " + item["citation"])
        elif kind == "ethical_wall" and item.get("status") == "active":
            verdict = "ineligible"
            reasons.append("active ethical wall or live adverse matter involving client")
            citations.append("independence-eligibility-rules.md #4.1; " + item["citation"])
        elif kind == "adverse_matter":
            days = days_between(start, item["end_date"])
            if days <= ADVERSE_REVIEW_DAYS and verdict != "ineligible":
                verdict = "needs_review"
                reasons.append(f"adverse matter support ended {days} days before start")
                citations.append("independence-eligibility-rules.md #4.2; " + item["citation"])
        elif kind == "prior_assurance_role":
            days = days_between(start, item["end_date"])
            if days <= ASSURANCE_LOOKBACK_DAYS and item.get("process", "").lower() in role.get("title", "").lower():
                verdict = "ineligible"
                reasons.append(f"prior assurance role over same process ended {days} days before start")
                citations.append("independence-eligibility-rules.md #5.1; " + item["citation"])

    effective = float(row["availability_context"]["effective_available_pct"])
    requested = float(row["availability_context"]["requested_allocation_pct"])
    if effective < requested:
        gap = requested - effective
        if gap > CAPACITY_REVIEW_BAND:
            verdict = "ineligible"
            reasons.append(f"effective available capacity {effective}% is below requested allocation {requested}%")
            citations.append("independence-eligibility-rules.md #6.1; " + row["citation"])
        elif verdict != "ineligible":
            verdict = "needs_review"
            reasons.append(f"effective capacity {effective}% is within {CAPACITY_REVIEW_BAND} points of requested {requested}%")
            citations.append("independence-eligibility-rules.md #6.2; " + row["citation"])

    if not reasons:
        reasons.append("no blocking independence, conflict or availability constraint found")
        citations.append("independence-eligibility-rules.md #1.1")

    return verdict, reasons, citations

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ranked", required=True)
    ap.add_argument("--constraints", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    payload = load(args.ranked)
    constraints = load(args.constraints)
    assert payload["contract_version"] == "ps.engagement-staffing-bench-match.v1", "wrong ranked contract"
    assert constraints["contract_version"] == "ps.engagement-staffing-bench-match.v1", "wrong constraints contract"

    roles_by_id = {r["role_id"]: r for r in payload["roles"]}
    governed_roles = []
    gaps = []
    escalations = list(payload.get("escalations", []))

    for ranked_role in payload.get("ranked_roles", []):
        role = roles_by_id[ranked_role["role_id"]]
        governed = []
        top_refused = False
        for row in ranked_role["candidate_slate"]:
            verdict, reasons, citations = verdict_for(role, row, constraints)
            recommendation_status = "not_recommended"
            if verdict == "eligible" and float(row["fit_score"]) >= MIN_RECOMMENDABLE_SCORE:
                recommendation_status = "recommended"
            elif verdict == "eligible":
                recommendation_status = "below_score_floor"
            if row["provisional_rank"] == 1 and verdict == "ineligible":
                top_refused = True
                escalations.append(
                    f"{role['role_id']}: refused top provisional candidate {row['candidate_name']} - {reasons[0]} "
                    "(independence-eligibility-rules.md #7.1)"
                )
            governed.append(dict(row, eligibility={
                "verdict": verdict,
                "recommendation_status": recommendation_status,
                "reasons": reasons,
                "source": ENGINE,
                "confidence": min(float(row.get("confidence", 1)), 0.99),
                "citation": "; ".join(citations)
            }))

        eligible = [c for c in governed if c["eligibility"]["recommendation_status"] == "recommended"]
        for i, candidate in enumerate(eligible, start=1):
            candidate["final_eligible_rank"] = i
        if not eligible:
            gap = {
                "role_id": role["role_id"],
                "role_title": role["title"],
                "gap_statement": f"No eligible candidate meets the {MIN_RECOMMENDABLE_SCORE} fit-score floor for {role['title']}; do not pad the slate.",
                "source": ENGINE,
                "confidence": 0.99,
                "citation": "fit-scoring-rubric.md #7.2; independence-eligibility-rules.md #7.2"
            }
            gaps.append(gap)
            escalations.append(f"{role['role_id']}: gap statement issued - no eligible candidate above score floor (independence-eligibility-rules.md #7.2)")

        governed_roles.append({
            "role_id": ranked_role["role_id"],
            "role_title": ranked_role["role_title"],
            "top_provisional_candidate_refused": top_refused,
            "candidate_slate": governed,
            "recommended_candidates": eligible,
            "source": ENGINE,
            "confidence": 0.99,
            "citation": "independence-eligibility-rules.md #1.1-#8.1"
        })

    payload["governed_roles"] = governed_roles
    payload["gaps"] = gaps
    payload["escalations"] = escalations
    payload.setdefault("provenance", {}).setdefault("engines", []).append("constraint_check/1.0")
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    refused = sum(1 for r in governed_roles if r["top_provisional_candidate_refused"])
    print(f"constraint_check: {len(governed_roles)} role(s), {refused} top-candidate refusal(s), {len(gaps)} gap(s) -> {args.out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
