#!/usr/bin/env python3
"""fit_score - deterministic candidate fit scoring (ps.engagement-staffing-bench-match.v1).

Reads role requirements and bench candidates as JSON and writes JSON. No network, no model
calls, no side effects beyond the requested output file. The model quotes this output; it
never recomputes scores or utilisation figures.
"""
import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from safety_text import is_suspect, safe_citation, safe_text, sanitize_free_text

ENGINE = "engine:fit_score"
ENGINE_VERSION = "fit_score/1.1.5"
CONTRACT = "ps.engagement-staffing-bench-match.v1"
DEFAULT_DURATION_WEEKS = 52

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

def merge_unique(*groups):
    merged = []
    seen = set()
    for group in groups:
        for item in group or []:
            text = str(item)
            if text not in seen:
                seen.add(text)
                merged.append(text)
    return merged

def normalize_candidate_id(value):
    return str(value or "").strip().casefold()

def duration_window(role):
    raw = role.get("duration_weeks")
    if raw in (None, ""):
        return DEFAULT_DURATION_WEEKS, True, [
            f"duration_weeks missing - availability counted over a "
            f"{DEFAULT_DURATION_WEEKS}-week window; confirm duration"
        ]
    try:
        weeks = int(raw)
        if weeks < 1:
            raise ValueError
        return weeks, False, []
    except (TypeError, ValueError):
        return DEFAULT_DURATION_WEEKS, True, [
            f"duration_weeks {raw!r} is invalid - availability counted over a "
            f"{DEFAULT_DURATION_WEEKS}-week window; confirm duration"
        ]

def percent_value(value, default, label, warnings):
    try:
        return float(value)
    except (TypeError, ValueError):
        warnings.append(f"{label} is missing or invalid; used conservative {default}%")
        return float(default)

def overlap_pct(blocks, start, weeks):
    role_start = date.fromisoformat(start)
    role_end = role_start + timedelta(weeks=weeks) - timedelta(days=1)
    role_days = (role_end - role_start).days + 1
    weighted_total = 0.0
    warnings = []
    for index, block in enumerate(blocks or []):
        if not isinstance(block, dict):
            warnings.append(f"availability block {index + 1} is malformed; treated as full-role")
            weighted_total += 100.0
            continue
        allocation = percent_value(
            block.get("allocation_pct", 100),
            100,
            f"availability block {index + 1} allocation_pct",
            warnings,
        )
        raw_start = block.get("start")
        raw_end = block.get("end")
        if raw_start in (None, ""):
            warnings.append(
                f"availability block {index + 1} without start date treated as starting at role start"
            )
            block_start = role_start
        else:
            try:
                block_start = date.fromisoformat(str(raw_start))
            except ValueError:
                warnings.append(
                    f"availability block {index + 1} has invalid start date; treated as starting at role start"
                )
                block_start = role_start
        if raw_end in (None, ""):
            warnings.append(
                f"availability block {index + 1} without end date treated as open-ended"
            )
            block_end = role_end
        else:
            try:
                block_end = date.fromisoformat(str(raw_end))
            except ValueError:
                warnings.append(
                    f"availability block {index + 1} has invalid end date; treated as open-ended"
                )
                block_end = role_end
        if block_end < block_start:
            warnings.append(
                f"availability block {index + 1} ends before it starts; treated as full-role"
            )
            block_start, block_end = role_start, role_end
        overlap_start = max(block_start, role_start)
        overlap_end = min(block_end, role_end)
        if overlap_start <= overlap_end:
            overlap_days = (overlap_end - overlap_start).days + 1
            weighted_total += allocation * overlap_days / role_days
    return min(weighted_total, 100.0), warnings

def coverage(required, actual):
    if not required:
        return 1.0
    actual_set = {x.lower() for x in actual or []}
    return len([x for x in required if x.lower() in actual_set]) / len(required)

def matched_requirements(required, actual):
    actual_set = {str(value).casefold() for value in actual or []}
    seen = set()
    matches = []
    for requirement in required or []:
        normalized = str(requirement).casefold()
        if normalized in actual_set and normalized not in seen:
            seen.add(normalized)
            matches.append(requirement)
    return sorted(matches)

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
    weeks, duration_assumed, warnings = duration_window(role)
    leave, leave_warnings = overlap_pct(
        cand.get("approved_leave", []),
        role["start_date"],
        weeks,
    )
    soft, soft_warnings = overlap_pct(
        cand.get("soft_bookings", []),
        role["start_date"],
        weeks,
    )
    warnings.extend(f"approved leave: {warning}" for warning in leave_warnings)
    warnings.extend(f"soft booking: {warning}" for warning in soft_warnings)
    current = percent_value(
        cand.get("current_allocation_pct", 0),
        100,
        "current_allocation_pct",
        warnings,
    )
    requested = percent_value(
        role.get("allocation_pct"),
        100,
        "requested allocation_pct",
        warnings,
    )
    effective = max(0.0, 100.0 - current - leave - soft)  # fit-scoring-rubric.md #4.1,#4.2
    component = min(effective / requested, 1.0) if requested else 0.0
    return {
        "duration_weeks_used": weeks,
        "duration_assumed": duration_assumed,
        "current_allocation_pct": round(current, 1),
        "approved_leave_overlap_pct": round(leave, 1),
        "soft_booking_overlap_pct": round(soft, 1),
        "effective_available_pct": round(effective, 1),
        "requested_allocation_pct": round(requested, 1),
        "utilization_after_staffing_pct": round(current + requested, 1),  # fit-scoring-rubric.md #4.3
        "component_score": round(component, 3),
        "evidence_complete": not warnings,
        "calculation_warnings": warnings,
    }

def normalize_location(value):
    city = str(value or "").split(",", 1)[0]
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", city.casefold()).split())

def location_language_score(role, cand):
    role_location = normalize_location(role.get("location"))
    candidate_location = normalize_location(cand.get("location"))
    location = 1.0 if role.get("remote_ok") or (
        role_location and role_location == candidate_location
    ) else 0.0
    language = coverage(role.get("required_languages", []), cand.get("languages", []))
    return location * 0.60 + language * 0.40  # fit-scoring-rubric.md #5.1,#5.2

def rate_score(role, cand):
    band = role.get("rate_band", {})
    if cand.get("rate") in (None, ""):
        return 0.0
    rate = float(cand["rate"])
    min_rate = float(band.get("min", 0))
    max_rate = float(band.get("max", 0))
    if min_rate <= rate <= max_rate:
        return 1.0      # fit-scoring-rubric.md #6.1
    if rate < min_rate:
        return 0.90     # fit-scoring-rubric.md #6.4
    if max_rate and rate <= max_rate * 1.10:
        return 0.60     # fit-scoring-rubric.md #6.2
    return 0.20         # fit-scoring-rubric.md #6.3

def rate_rule(role, cand):
    band = role.get("rate_band", {})
    if cand.get("rate") in (None, ""):
        return "fit-scoring-rubric.md #6.5"
    rate = float(cand["rate"])
    min_rate = float(band.get("min", 0))
    max_rate = float(band.get("max", 0))
    if min_rate <= rate <= max_rate:
        return "fit-scoring-rubric.md #6.1"
    if rate < min_rate:
        return "fit-scoring-rubric.md #6.4"
    if max_rate and rate <= max_rate * 1.10:
        return "fit-scoring-rubric.md #6.2"
    return "fit-scoring-rubric.md #6.3"

def seniority_rule(role_level, cand_level):
    try:
        diff = abs(
            SENIORITY_BANDS.index((role_level or "").lower())
            - SENIORITY_BANDS.index((cand_level or "").lower())
        )
    except ValueError:
        return "fit-scoring-rubric.md #3.4"
    return {
        0: "fit-scoring-rubric.md #3.1",
        1: "fit-scoring-rubric.md #3.2",
        2: "fit-scoring-rubric.md #3.3",
    }.get(diff, "fit-scoring-rubric.md #3.4")

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
    if roles_payload.get("contract_version") != CONTRACT:
        sys.exit("wrong roles contract")
    if bench_payload.get("contract_version") != CONTRACT:
        sys.exit("wrong bench contract")

    safety_escalations = []
    roles_payload = sanitize_free_text(roles_payload, "roles_input", safety_escalations)
    bench_payload = sanitize_free_text(bench_payload, "bench_input", safety_escalations)
    candidates = bench_payload.get("bench_candidates", [])
    candidate_ids = [
        normalize_candidate_id(candidate.get("candidate_id"))
        for candidate in candidates
    ]
    duplicate_ids = sorted({
        candidate_id for candidate_id in candidate_ids
        if candidate_id and candidate_ids.count(candidate_id) > 1
    })
    for candidate_id in duplicate_ids:
        safety_escalations.append(
            f"{candidate_id}: duplicate candidate ID in bench - resolve before governance"
        )
    for candidate in candidates:
        if candidate.get("rate") in (None, ""):
            safety_escalations.append(
                f"{candidate.get('candidate_id', 'unknown candidate')}: rate missing - "
                "rate-band component scored 0; confirm rate before scoring is relied on"
            )
    scored_roles = []
    for role in roles_payload["roles"]:
        candidate_scores = []
        for cand in candidates:
            availability = availability_context(role, cand)
            for warning in availability["calculation_warnings"]:
                safety_escalations.append(
                    f"{role.get('role_id', 'unknown role')}/"
                    f"{cand.get('candidate_id', 'unknown candidate')}: {warning}"
                )
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
                "component_citations": {
                    "skills": "fit-scoring-rubric.md #1.1,#2.1,#2.2,#2.3",
                    "seniority": seniority_rule(role.get("seniority"), cand.get("seniority")),
                    "availability": "fit-scoring-rubric.md #1.3,#4.1,#4.2,#4.3",
                    "location_language": "fit-scoring-rubric.md #1.4,#5.1,#5.2",
                    "rate_band": rate_rule(role, cand),
                    "continuity": "fit-scoring-rubric.md #1.6",
                },
                "availability_context": availability,
                "matched_required_skills": matched_requirements(
                    role.get("required_skills", []), cand.get("skills", [])
                ),
                "matched_preferred_skills": matched_requirements(
                    role.get("preferred_skills", []), cand.get("skills", [])
                ),
                "source": ENGINE,
                "confidence": min(float(role.get("confidence", 1)), float(cand.get("confidence", 1)), 0.99),
                "citation": "fit-scoring-rubric.md #7.3; "
                + safe_citation(cand.get("citation", "bench record")),
            })
        scored_roles.append({
            "role_id": role["role_id"],
            "role_title": role["title"],
            "candidate_scores": candidate_scores,
            "source": ENGINE,
            "confidence": min(float(role.get("confidence", 1)), 0.99),
            "citation": safe_citation(role.get("citation", "role record")),
        })

    out = dict(roles_payload)
    out["bench_candidates"] = candidates
    out["scored_roles"] = scored_roles
    out["escalations"] = merge_unique(
        roles_payload.get("escalations", []),
        bench_payload.get("escalations", []),
        safety_escalations,
    )
    provenance = dict(roles_payload.get("provenance", {}))
    for key, value in bench_payload.get("provenance", {}).items():
        provenance.setdefault(key, value)
    engines = merge_unique(
        roles_payload.get("provenance", {}).get("engines", []),
        bench_payload.get("provenance", {}).get("engines", []),
    )
    provenance["engines"] = [
        engine for engine in engines if not engine.startswith("fit_score/")
    ] + [ENGINE_VERSION]
    provenance.setdefault("generated_at", "2026-09-23T00:00:00Z")
    out["provenance"] = provenance
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2)
    print(f"fit_score: {len(scored_roles)} role(s), {len(candidates)} candidate(s) -> {args.out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
