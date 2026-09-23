#!/usr/bin/env python3
"""fit_score - deterministic candidate fit scoring (ps.engagement-staffing-bench-match.v1).

Reads role requirements and bench candidates as JSON and writes JSON. No network, no model
calls, no side effects beyond the requested output file. The model quotes this output; it
never recomputes scores or utilisation figures.
"""
import argparse
import json
import sys
from datetime import date

ENGINE = "engine:fit_score"

WEIGHT_SKILLS = 0.40          # fit-scoring-rubric.md #1.1
WEIGHT_SENIORITY = 0.15       # fit-scoring-rubric.md #1.2
WEIGHT_AVAILABILITY = 0.20    # fit-scoring-rubric.md #1.3
WEIGHT_LOCATION_LANGUAGE = 0.10  # fit-scoring-rubric.md #1.4
WEIGHT_RATE = 0.10            # fit-scoring-rubric.md #1.5
WEIGHT_CONTINUITY = 0.05      # fit-scoring-rubric.md #1.6

REQUIRED_SKILL_WEIGHT = 0.70  # fit-scoring-rubric.md #2.1
PREFERRED_SKILL_WEIGHT = 0.20 # fit-scoring-rubric.md #2.2
CERT_WEIGHT = 0.10            # fit-scoring-rubric.md #2.3

SENIORITY_BANDS = ["associate", "consultant", "senior consultant", "manager", "senior manager", "director", "partner"]

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def overlap_pct(blocks, start):
    role_start = date.fromisoformat(start)
    total = 0.0
    for block in blocks or []:
        start_date = date.fromisoformat(block["start"])
        end_date = date.fromisoformat(block["end"])
        if start_date <= role_start <= end_date:
            total += float(block.get("allocation_pct", 100))
    return min(total, 100.0)

def coverage(required, actual):
    if not required:
        return 1.0
    actual_set = {x.lower() for x in actual or []}
    return len([x for x in required if x.lower() in actual_set]) / len(required)

def skill_score(role, cand):
    required = coverage(role.get("required_skills", []), cand.get("skills", []))
    preferred = coverage(role.get("preferred_skills", []), cand.get("skills", []))
    certs = coverage(role.get("required_certifications", []), cand.get("certifications", []))
    return required * REQUIRED_SKILL_WEIGHT + preferred * PREFERRED_SKILL_WEIGHT + certs * CERT_WEIGHT

def seniority_score(role_level, cand_level):
    try:
        diff = abs(SENIORITY_BANDS.index((role_level or "").lower()) - SENIORITY_BANDS.index((cand_level or "").lower()))
    except ValueError:
        return 0.0
    if diff == 0:
        return 1.0      # fit-scoring-rubric.md #3.1
    if diff == 1:
        return 0.75     # fit-scoring-rubric.md #3.2
    if diff == 2:
        return 0.40     # fit-scoring-rubric.md #3.3
    return 0.0          # fit-scoring-rubric.md #3.4

def availability_context(role, cand):
    leave = overlap_pct(cand.get("approved_leave", []), role["start_date"])
    soft = overlap_pct(cand.get("soft_bookings", []), role["start_date"])
    current = float(cand.get("current_allocation_pct", 0))
    requested = float(role["allocation_pct"])
    effective = max(0.0, 100.0 - current - leave - soft)  # fit-scoring-rubric.md #4.1,#4.2
    component = min(effective / requested, 1.0) if requested else 0.0
    return {
        "current_allocation_pct": round(current, 1),
        "approved_leave_overlap_pct": round(leave, 1),
        "soft_booking_overlap_pct": round(soft, 1),
        "effective_available_pct": round(effective, 1),
        "requested_allocation_pct": round(requested, 1),
        "utilization_after_staffing_pct": round(current + requested, 1),  # fit-scoring-rubric.md #4.3
        "component_score": round(component, 3)
    }

def location_language_score(role, cand):
    location = 1.0 if role.get("remote_ok") or role.get("location", "").lower() == cand.get("location", "").lower() else 0.0
    language = coverage(role.get("required_languages", []), cand.get("languages", []))
    return location * 0.60 + language * 0.40  # fit-scoring-rubric.md #5.1,#5.2

def rate_score(role, cand):
    band = role.get("rate_band", {})
    rate = float(cand.get("rate", 0))
    min_rate = float(band.get("min", 0))
    max_rate = float(band.get("max", 0))
    if min_rate <= rate <= max_rate:
        return 1.0      # fit-scoring-rubric.md #6.1
    if rate < min_rate:
        return 0.90     # fit-scoring-rubric.md #6.4
    if max_rate and rate <= max_rate * 1.10:
        return 0.60     # fit-scoring-rubric.md #6.2
    return 0.20         # fit-scoring-rubric.md #6.3

def continuity_score(role, cand):
    practice = role.get("industry_context", "").lower()
    industries = {x.lower() for x in cand.get("industry_experience", [])}
    return 1.0 if practice and practice in industries else 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roles", required=True)
    ap.add_argument("--bench", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    roles_payload = load(args.roles)
    bench_payload = load(args.bench)
    assert roles_payload["contract_version"] == "ps.engagement-staffing-bench-match.v1", "wrong roles contract"
    assert bench_payload["contract_version"] == "ps.engagement-staffing-bench-match.v1", "wrong bench contract"

    candidates = bench_payload.get("bench_candidates", [])
    scored_roles = []
    for role in roles_payload["roles"]:
        candidate_scores = []
        for cand in candidates:
            availability = availability_context(role, cand)
            components = {
                "skills": round(skill_score(role, cand), 3),
                "seniority": round(seniority_score(role.get("seniority"), cand.get("seniority")), 3),
                "availability": availability["component_score"],
                "location_language": round(location_language_score(role, cand), 3),
                "rate_band": round(rate_score(role, cand), 3),
                "continuity": round(continuity_score(role, cand), 3)
            }
            total = (
                components["skills"] * WEIGHT_SKILLS +
                components["seniority"] * WEIGHT_SENIORITY +
                components["availability"] * WEIGHT_AVAILABILITY +
                components["location_language"] * WEIGHT_LOCATION_LANGUAGE +
                components["rate_band"] * WEIGHT_RATE +
                components["continuity"] * WEIGHT_CONTINUITY
            )
            candidate_scores.append({
                "candidate_id": cand["candidate_id"],
                "candidate_name": cand["name"],
                "fit_score": round(total * 100, 1),
                "component_scores": components,
                "availability_context": availability,
                "matched_required_skills": sorted(set(role.get("required_skills", [])) & set(cand.get("skills", []))),
                "matched_preferred_skills": sorted(set(role.get("preferred_skills", [])) & set(cand.get("skills", []))),
                "source": ENGINE,
                "confidence": min(float(role.get("confidence", 1)), float(cand.get("confidence", 1)), 0.99),
                "citation": "fit-scoring-rubric.md #1.1-#7.3; " + cand.get("citation", "bench record")
            })
        scored_roles.append({
            "role_id": role["role_id"],
            "role_title": role["title"],
            "candidate_scores": candidate_scores,
            "source": ENGINE,
            "confidence": min(float(role.get("confidence", 1)), 0.99),
            "citation": role.get("citation", "role record")
        })

    out = dict(roles_payload)
    out["bench_candidates"] = candidates
    out["scored_roles"] = scored_roles
    out.setdefault("provenance", {})
    out["provenance"]["engines"] = ["fit_score/1.0"]
    out["provenance"]["generated_at"] = roles_payload.get("provenance", {}).get("generated_at", "2026-09-23T00:00:00Z")
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"fit_score: {len(scored_roles)} role(s), {len(candidates)} candidate(s) -> {args.out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
