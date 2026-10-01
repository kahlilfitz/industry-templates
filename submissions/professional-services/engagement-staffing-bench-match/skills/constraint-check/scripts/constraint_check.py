#!/usr/bin/env python3
"""constraint_check - deterministic staffing eligibility Govern engine."""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from safety_text import is_suspect, safe_citation, safe_text, sanitize_free_text

ENGINE = "engine:constraint_check"
ENGINE_VERSION = "constraint_check/1.1.4"
CONTRACT = "ps.engagement-staffing-bench-match.v1"
CONFIDENCE_FLOOR = 0.75       # independence-eligibility-rules.md #8.1
PRIOR_ROLE_COOLING_DAYS = 365 # independence-eligibility-rules.md #2.1
PRIOR_ROLE_REVIEW_DAYS = 730  # independence-eligibility-rules.md #2.2
DIVEST_REVIEW_DAYS = 30       # independence-eligibility-rules.md #3.2
ADVERSE_REVIEW_DAYS = 180     # independence-eligibility-rules.md #4.2
ASSURANCE_LOOKBACK_DAYS = 730 # independence-eligibility-rules.md #5.1
CAPACITY_REVIEW_BAND = 10.0   # independence-eligibility-rules.md #6.2
MIN_RECOMMENDABLE_SCORE = 70.0 # fit-scoring-rubric.md #7.2
KNOWN_TYPES = {
    "clear",
    "financial_interest",
    "prior_client_role",
    "ethical_wall",
    "adverse_matter",
    "prior_assurance_role",
}
RESOLVED_FI_STATUSES = {"divested", "resolved", "cleared"}
RESOLVED_STATUSES = {"closed", "resolved", "cleared", "inactive"}

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

def safe_cite(text):
    return safe_citation(text)

def days_between(start, end):
    return (date.fromisoformat(start) - date.fromisoformat(end)).days

def timing_phrase(days, past_tense="ended"):
    if days < 0:
        return f"extends {-days} days beyond role start"
    return f"{past_tense} {days} days before start"

def normalize_candidate_id(value):
    return str(value or "").strip().casefold()

def candidate_constraints(constraints, candidate_id):
    normalized = normalize_candidate_id(candidate_id)
    return [
        item
        for item in constraints.get("constraints", [])
        if normalize_candidate_id(item.get("candidate_id")) == normalized
    ]

def unknown_constraint_ids(constraints, candidate_ids):
    known = {
        normalize_candidate_id(candidate_id)
        for candidate_id in candidate_ids
        if normalize_candidate_id(candidate_id)
    }
    return [
        item.get("candidate_id", "<blank>")
        for item in constraints.get("constraints", [])
        if not normalize_candidate_id(item.get("candidate_id"))
        or normalize_candidate_id(item.get("candidate_id")) not in known
    ]

def confidence_value(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def materiality_value(item):
    value = item.get("material")
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().casefold()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    return None

def normalize_entity_name(name):
    text = re.sub(r"[^a-z0-9 ]", " ", str(name or "").casefold())
    suffixes = {"llc", "inc", "ltd", "plc", "corp", "corporation", "co", "company", "the"}
    return " ".join(word for word in text.split() if word not in suffixes)

def entity_names_match(left, right):
    left_name = normalize_entity_name(left)
    right_name = normalize_entity_name(right)
    if not left_name or not right_name:
        return None
    left_tokens = left_name.split()
    right_tokens = right_name.split()
    if left_tokens == right_tokens:
        return True
    shorter, longer = (
        (left_tokens, right_tokens)
        if len(left_tokens) <= len(right_tokens)
        else (right_tokens, left_tokens)
    )
    width = len(shorter)
    return any(longer[index:index + width] == shorter for index in range(len(longer) - width + 1))

def applies_to_client(item, engagement):
    raw_name = item.get("client_name")
    if raw_name in (None, "") or is_suspect(raw_name) or str(raw_name).startswith("[FLAGGED:"):
        return True
    affiliates = engagement.get("affiliates", [])
    if isinstance(affiliates, str):
        affiliates = [affiliates]
    targets = [engagement.get("client_name"), *affiliates]
    comparisons = []
    for entity in targets:
        matched = entity_names_match(raw_name, entity)
        if matched is True:
            return True
        comparisons.append(matched)
    return None if comparisons and all(value is None for value in comparisons) else False

def engagement_entity_label(item, engagement):
    name = str(item.get("client_name") or "").strip()
    if not name:
        return "client or declared affiliate"
    if entity_names_match(name, engagement.get("client_name")) is True:
        return f"client '{name}'"
    return f"declared affiliate '{name}'"

def merge_engagement(payload, constraints, escalations):
    ranked = payload.get("engagement") or {}
    constrained = constraints.get("engagement") or {}
    if not isinstance(ranked, dict) or not isinstance(constrained, dict):
        sys.exit("engagement context must be an object")
    merged = dict(ranked)
    for key, value in constrained.items():
        if value in (None, "", []):
            continue
        if key in {"source", "confidence", "citation"} and ranked.get(key) not in (None, ""):
            continue
        merged[key] = value
    ranked_affiliates = ranked.get("affiliates", [])
    constrained_affiliates = constrained.get("affiliates", [])
    if isinstance(ranked_affiliates, str):
        ranked_affiliates = [ranked_affiliates]
    if isinstance(constrained_affiliates, str):
        constrained_affiliates = [constrained_affiliates]
    merged["affiliates"] = merge_unique(ranked_affiliates, constrained_affiliates)
    if ranked_affiliates and not constrained_affiliates:
        escalations.append(
            "engagement affiliates restored from ranked role-intake context; "
            "bench-query must propagate the engagement block unchanged"
        )
    if not str(merged.get("client_name") or "").strip():
        sys.exit("engagement.client_name is required for fail-closed conflict governance")
    if not normalize_entity_name(merged["client_name"]):
        escalations.append(
            "engagement.client_name cannot be normalized to a matchable entity; "
            "all candidates require independence review"
        )
    payload["engagement"] = merged
    constraints["engagement"] = merged
    return merged

def elevate(current, proposed):
    priority = {"eligible": 0, "needs_review": 1, "ineligible": 2}
    return proposed if priority[proposed] > priority[current] else current

def considered_item(item, applies, disposition, reason, default_source="connector:conflicts-register"):
    return {
        "type": item.get("type", ""),
        "client_name": item.get("client_name", ""),
        "status": item.get("status", ""),
        "material": materiality_value(item),
        "role_type": item.get("role_type", ""),
        "process": item.get("process", ""),
        "end_date": item.get("end_date", ""),
        "resolved_date": item.get("resolved_date", ""),
        "applies_to_engagement": applies,
        "disposition": disposition,
        "reason": reason,
        "source": item.get("source") or default_source,
        "confidence": confidence_value(item.get("confidence", 1.0)),
        "citation": safe_cite(item.get("citation", "conflicts record")),
    }

def normalize_role_type(value):
    normalized = re.sub(r"[\s-]+", "_", str(value or "").strip().casefold())
    aliases = {
        "board_member": "board_member",
        "board_director": "board_member",
        "director": "board_member",
    }
    return aliases.get(normalized, normalized)

def safe_days_between(start, end):
    try:
        return days_between(start, end)
    except (TypeError, ValueError):
        return None

def verdict_for(role, row, constraints):
    verdict = "eligible"
    reasons = []
    citations = []
    considered = []
    start = next(
        (
            item.get("start_date")
            for item in constraints.get("roles", [])
            if item.get("role_id") == role.get("role_id")
        ),
        role.get("start_date"),
    )
    if not start:
        raise ValueError(f"no start_date for role {role.get('role_id', '<unknown>')}")
    engagement = constraints.get("engagement", {})
    items = candidate_constraints(constraints, row["candidate_id"])
    default_source = constraints.get("source", "connector:conflicts-register")

    confidence_values = [
        confidence_value(row.get("confidence", 1.0)),
        confidence_value(constraints.get("confidence", 1.0)),
        confidence_value(constraints.get("engagement", {}).get("confidence", 1.0)),
        *[confidence_value(item.get("confidence", 1.0)) for item in items],
    ]
    lowest_confidence = min(confidence_values)
    if lowest_confidence < CONFIDENCE_FLOOR:
        verdict = elevate(verdict, "needs_review")
        reasons.append(f"evidence confidence {lowest_confidence} below {CONFIDENCE_FLOOR}")
        citations.append("independence-eligibility-rules.md #8.1")

    if not normalize_entity_name(engagement.get("client_name")):
        verdict = elevate(verdict, "needs_review")
        reasons.append("engagement client name cannot be matched reliably")
        citations.append("independence-eligibility-rules.md #9.2")

    if not items:
        verdict = elevate(verdict, "needs_review")
        reason = "no conflicts-register record for candidate - clearance cannot be inferred"
        reasons.append(reason)
        citations.append("independence-eligibility-rules.md #9.4")
        considered.append({
            "type": "conflicts_register_coverage",
            "client_name": engagement.get("client_name", ""),
            "status": "",
            "material": None,
            "role_type": "",
            "process": "",
            "end_date": "",
            "resolved_date": "",
            "applies_to_engagement": True,
            "disposition": "needs_review",
            "reason": reason,
            "source": default_source,
            "confidence": confidence_value(constraints.get("confidence", 0.0)),
            "citation": safe_cite(constraints.get("citation", "conflicts register")),
        })

    for item in items:
        kind = str(item.get("type", "")).strip().casefold()
        status = str(item.get("status", "")).strip().casefold()
        materiality = materiality_value(item)
        applies = applies_to_client(item, engagement)
        if applies is None:
            verdict = elevate(verdict, "needs_review")
            reason = "conflict entity cannot be matched reliably to the client or declared affiliates"
            reasons.append(reason)
            citations.append(
                "independence-eligibility-rules.md #9.1,#9.2; "
                + safe_cite(item.get("citation", ""))
            )
            considered.append(
                considered_item(item, True, "needs_review", reason, default_source)
            )
            continue
        if not applies:
            considered.append(considered_item(
                item,
                False,
                "not_applicable",
                "recorded entity does not match the client or a declared affiliate",
                default_source,
            ))
            continue

        if kind not in KNOWN_TYPES:
            verdict = elevate(verdict, "needs_review")
            reason = f"unrecognised conflicts record type '{kind or '<blank>'}' - route to independence review"
            reasons.append(reason)
            citations.append("independence-eligibility-rules.md #1.1,#8.1; " + safe_cite(item.get("citation", "")))
            considered.append(considered_item(item, True, "needs_review", reason, default_source))
        elif kind == "clear":
            if status in ("", "clear", "cleared", "resolved", "closed"):
                considered.append(considered_item(
                    item, True, "clear", "conflicts register marks candidate clear", default_source
                ))
            else:
                verdict = elevate(verdict, "needs_review")
                reason = f"clear record has unrecognised status '{status}'"
                reasons.append(reason)
                citations.append("independence-eligibility-rules.md #9.1; " + safe_cite(item.get("citation", "")))
                considered.append(considered_item(item, True, "needs_review", reason, default_source))
        elif kind == "financial_interest" and status not in RESOLVED_FI_STATUSES and materiality is None:
            verdict = elevate(verdict, "needs_review")
            reason = f"financial interest with status '{status or '<blank>'}' and materiality not recorded"
            reasons.append(reason)
            citations.append("independence-eligibility-rules.md #3.1,#8.1; " + safe_cite(item.get("citation", "")))
            considered.append(considered_item(item, True, "needs_review", reason, default_source))
        elif kind == "financial_interest" and status not in RESOLVED_FI_STATUSES and materiality:
            verdict = elevate(verdict, "ineligible")
            reason = (
                "unresolved material financial interest in "
                + engagement_entity_label(item, engagement)
            )
            reasons.append(reason)
            citations.append("independence-eligibility-rules.md #3.1; " + safe_cite(item.get("citation", "")))
            considered.append(considered_item(
                item, True, "ineligible", reason, default_source
            ))
        elif kind == "financial_interest" and status == "divested":
            if not item.get("resolved_date"):
                verdict = elevate(verdict, "needs_review")
                reason = "divested financial interest has no resolved_date"
                reasons.append(reason)
                citations.append("independence-eligibility-rules.md #3.2,#8.1; " + safe_cite(item.get("citation", "")))
                considered.append(considered_item(item, True, "needs_review", reason, default_source))
            else:
                days = safe_days_between(start, item["resolved_date"])
                if days is None:
                    verdict = elevate(verdict, "needs_review")
                    reason = "divested financial interest has an invalid resolved_date"
                    reasons.append(reason)
                    citations.append(
                        "independence-eligibility-rules.md #3.2,#9.1; "
                        + safe_cite(item.get("citation", ""))
                    )
                    considered.append(
                        considered_item(item, True, "needs_review", reason, default_source)
                    )
                elif days <= DIVEST_REVIEW_DAYS:
                    verdict = elevate(verdict, "needs_review")
                    reason = f"material interest divestment {timing_phrase(days, 'completed')}"
                    reasons.append(reason)
                    citations.append("independence-eligibility-rules.md #3.2; " + safe_cite(item.get("citation", "")))
                    considered.append(considered_item(item, True, "needs_review", reason, default_source))
                else:
                    considered.append(considered_item(
                        item, True, "resolved", "divestment completed outside the review window", default_source
                    ))
        elif kind == "financial_interest":
            considered.append(considered_item(
                item,
                True,
                "resolved" if status in RESOLVED_FI_STATUSES else "non_material",
                "financial interest is resolved or explicitly non-material",
                default_source,
            ))
        elif kind == "prior_client_role":
            role_type = normalize_role_type(item.get("role_type"))
            if not item.get("end_date") or not role_type:
                verdict = elevate(verdict, "needs_review")
                reason = "prior client role is missing role_type or end_date"
                reasons.append(reason)
                citations.append("independence-eligibility-rules.md #2.2,#8.1; " + safe_cite(item.get("citation", "")))
                considered.append(considered_item(item, True, "needs_review", reason, default_source))
            else:
                days = safe_days_between(start, item["end_date"])
                if days is None:
                    verdict = elevate(verdict, "needs_review")
                    reason = "prior client role has an invalid end_date"
                    reasons.append(reason)
                    citations.append(
                        "independence-eligibility-rules.md #2.2,#9.1; "
                        + safe_cite(item.get("citation", ""))
                    )
                    considered.append(
                        considered_item(item, True, "needs_review", reason, default_source)
                    )
                elif role_type in ("employee", "officer", "board_member") and days <= PRIOR_ROLE_COOLING_DAYS:
                    verdict = elevate(verdict, "ineligible")
                    reason = f"prior {role_type} role at client {timing_phrase(days)}"
                    reasons.append(reason)
                    citations.append("independence-eligibility-rules.md #2.1; " + safe_cite(item.get("citation", "")))
                    considered.append(considered_item(item, True, "ineligible", reason, default_source))
                elif days <= PRIOR_ROLE_REVIEW_DAYS:
                    verdict = elevate(verdict, "needs_review")
                    reason = f"prior client role {timing_phrase(days)}"
                    reasons.append(reason)
                    citations.append("independence-eligibility-rules.md #2.2; " + safe_cite(item.get("citation", "")))
                    considered.append(considered_item(item, True, "needs_review", reason, default_source))
                else:
                    considered.append(considered_item(
                        item, True, "resolved", "prior role falls outside the review window", default_source
                    ))
        elif kind == "ethical_wall":
            if status == "active":
                verdict = elevate(verdict, "ineligible")
                reason = "active ethical wall involving client"
                reasons.append(reason)
                citations.append("independence-eligibility-rules.md #4.1; " + safe_cite(item.get("citation", "")))
                considered.append(considered_item(item, True, "ineligible", reason, default_source))
            elif status in RESOLVED_STATUSES:
                considered.append(considered_item(
                    item, True, "resolved", "ethical wall is recorded as resolved", default_source
                ))
            else:
                verdict = elevate(verdict, "needs_review")
                reason = f"ethical wall status '{status or '<blank>'}' is not clear"
                reasons.append(reason)
                citations.append("independence-eligibility-rules.md #4.1,#8.1; " + safe_cite(item.get("citation", "")))
                considered.append(considered_item(item, True, "needs_review", reason, default_source))
        elif kind == "adverse_matter":
            if not item.get("end_date"):
                verdict = elevate(verdict, "needs_review")
                reason = "adverse matter has no end_date"
                reasons.append(reason)
                citations.append("independence-eligibility-rules.md #4.2,#8.1; " + safe_cite(item.get("citation", "")))
                considered.append(considered_item(item, True, "needs_review", reason, default_source))
            else:
                days = safe_days_between(start, item["end_date"])
                if days is None:
                    verdict = elevate(verdict, "needs_review")
                    reason = "adverse matter has an invalid end_date"
                    reasons.append(reason)
                    citations.append(
                        "independence-eligibility-rules.md #4.2,#9.1; "
                        + safe_cite(item.get("citation", ""))
                    )
                    considered.append(
                        considered_item(item, True, "needs_review", reason, default_source)
                    )
                elif days < 0:
                    verdict = elevate(verdict, "ineligible")
                    reason = "adverse matter remains active at role start"
                    reasons.append(reason)
                    citations.append("independence-eligibility-rules.md #4.1; " + safe_cite(item.get("citation", "")))
                    considered.append(considered_item(item, True, "ineligible", reason, default_source))
                elif days <= ADVERSE_REVIEW_DAYS:
                    verdict = elevate(verdict, "needs_review")
                    reason = f"adverse matter support {timing_phrase(days)}"
                    reasons.append(reason)
                    citations.append("independence-eligibility-rules.md #4.2; " + safe_cite(item.get("citation", "")))
                    considered.append(considered_item(item, True, "needs_review", reason, default_source))
                else:
                    considered.append(considered_item(
                        item, True, "resolved", "adverse matter falls outside the review window", default_source
                    ))
        elif kind == "prior_assurance_role":
            process = str(item.get("process") or "").strip()
            if not process or not item.get("end_date"):
                verdict = elevate(verdict, "needs_review")
                reason = "prior assurance role process or end_date is missing or ambiguous"
                reasons.append(reason)
                citations.append("independence-eligibility-rules.md #5.2; " + safe_cite(item.get("citation", "")))
                considered.append(considered_item(item, True, "needs_review", reason, default_source))
            else:
                days = safe_days_between(start, item["end_date"])
                if days is None:
                    verdict = elevate(verdict, "needs_review")
                    reason = "prior assurance role has an invalid end_date"
                    reasons.append(reason)
                    citations.append(
                        "independence-eligibility-rules.md #5.2,#9.1; "
                        + safe_cite(item.get("citation", ""))
                    )
                    considered.append(
                        considered_item(item, True, "needs_review", reason, default_source)
                    )
                elif days <= ASSURANCE_LOOKBACK_DAYS and normalize_entity_name(process) in normalize_entity_name(role.get("title", "")):
                    verdict = elevate(verdict, "ineligible")
                    reason = f"prior assurance role over same process {timing_phrase(days)}"
                    reasons.append(reason)
                    citations.append("independence-eligibility-rules.md #5.1; " + safe_cite(item.get("citation", "")))
                    considered.append(considered_item(item, True, "ineligible", reason, default_source))
                elif days <= ASSURANCE_LOOKBACK_DAYS:
                    verdict = elevate(verdict, "needs_review")
                    reason = (
                        f"prior assurance role over '{process}' {timing_phrase(days)}; "
                        "overlap with role scope not determinable"
                    )
                    reasons.append(reason)
                    citations.append("independence-eligibility-rules.md #5.2; " + safe_cite(item.get("citation", "")))
                    considered.append(considered_item(item, True, "needs_review", reason, default_source))
                else:
                    considered.append(considered_item(
                        item, True, "resolved", "prior assurance role falls outside the lookback window", default_source
                    ))

    availability = row.get("availability_context")
    if not isinstance(availability, dict):
        availability = {}
    effective = confidence_value(availability.get("effective_available_pct"), None)
    requested = confidence_value(availability.get("requested_allocation_pct"), None)
    warnings = availability.get("calculation_warnings", [])
    if availability.get("evidence_complete") is False or warnings:
        verdict = elevate(verdict, "needs_review")
        reason = "availability evidence is incomplete or uses a conservative assumption"
        reasons.append(reason)
        citations.append("independence-eligibility-rules.md #6.3,#8.1")
        considered.append({
            "type": "availability_evidence",
            "applies_to_engagement": True,
            "disposition": "needs_review",
            "reason": reason,
            "source": row.get("source", "engine:fit_score"),
            "confidence": confidence_value(row.get("confidence", 0.0)),
            "citation": "independence-eligibility-rules.md #6.3,#8.1",
        })
    if effective is None or requested is None:
        verdict = elevate(verdict, "needs_review")
        reason = "availability calculation is missing effective or requested capacity"
        reasons.append(reason)
        citations.append("independence-eligibility-rules.md #6.3,#9.1")
        considered.append({
            "type": "availability",
            "applies_to_engagement": True,
            "disposition": "needs_review",
            "reason": reason,
            "citation": safe_cite(row.get("citation", "fit score record")),
        })
    elif effective < requested:
        gap = requested - effective
        if gap > CAPACITY_REVIEW_BAND:
            verdict = elevate(verdict, "ineligible")
            reason = f"effective available capacity {effective}% is below requested allocation {requested}%"
            reasons.append(reason)
            citations.append(
                "independence-eligibility-rules.md #6.1; "
                + safe_cite(row.get("citation", "fit score record"))
            )
            considered.append({
                "type": "availability",
                "applies_to_engagement": True,
                "disposition": "ineligible",
                "reason": reason,
                "citation": safe_cite(row.get("citation", "fit score record")),
            })
        else:
            verdict = elevate(verdict, "needs_review")
            reason = f"effective capacity {effective}% is within {CAPACITY_REVIEW_BAND} points of requested {requested}%"
            reasons.append(reason)
            citations.append(
                "independence-eligibility-rules.md #6.2; "
                + safe_cite(row.get("citation", "fit score record"))
            )
            considered.append({
                "type": "availability",
                "applies_to_engagement": True,
                "disposition": "needs_review",
                "reason": reason,
                "citation": safe_cite(row.get("citation", "fit score record")),
            })
    else:
        considered.append({
            "type": "availability",
            "applies_to_engagement": True,
            "disposition": "clear",
            "reason": "effective available capacity meets requested allocation",
            "citation": safe_cite(row.get("citation", "fit score record")),
        })

    if not reasons:
        reasons.append("no blocking independence, conflict or availability constraint found")
        citations.append("independence-eligibility-rules.md #1.1")

    return verdict, reasons, citations, considered

def blocking_reason(reasons, citations):
    blocking_rules = ("#2.1", "#3.1", "#4.1", "#5.1", "#6.1")
    for reason, citation in zip(reasons, citations):
        if any(rule in citation for rule in blocking_rules):
            return reason, citation.split(";", 1)[0]
    return reasons[0], citations[0].split(";", 1)[0]

def review_reason(reasons, citations):
    review_rules = (
        "#2.2",
        "#3.2",
        "#4.2",
        "#5.2",
        "#6.2",
        "#6.3",
        "#9.1",
        "#9.2",
        "#9.4",
        "#8.1",
    )
    for rule in review_rules:
        for reason, citation in zip(reasons, citations):
            if rule in citation:
                return reason, citation.split(";", 1)[0]
    return reasons[0], citations[0].split(";", 1)[0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ranked", required=True)
    ap.add_argument("--constraints", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    payload = load(args.ranked)
    constraints = load(args.constraints)
    if payload.get("contract_version") != CONTRACT:
        sys.exit("wrong ranked contract")
    if constraints.get("contract_version") != CONTRACT:
        sys.exit("wrong constraints contract")

    safety_escalations = []
    payload = sanitize_free_text(payload, "ranked_input", safety_escalations)
    constraints = sanitize_free_text(constraints, "constraints_input", safety_escalations)
    escalations = merge_unique(
        payload.get("escalations", []),
        constraints.get("escalations", []),
        safety_escalations,
    )
    merge_engagement(payload, constraints, escalations)
    roles_by_id = {r["role_id"]: r for r in payload["roles"]}
    governed_roles = []
    gaps = []
    ranked_candidate_ids = {
        normalize_candidate_id(candidate.get("candidate_id"))
        for ranked_role in payload.get("ranked_roles", [])
        for candidate in ranked_role.get("candidate_slate", [])
        if normalize_candidate_id(candidate.get("candidate_id"))
    }
    for candidate_id in unknown_constraint_ids(constraints, ranked_candidate_ids):
        escalations.append(
            f"conflicts-register row for unknown candidate_id "
            f"{candidate_id!r} - check candidate ID mapping"
        )

    for ranked_role in payload.get("ranked_roles", []):
        role_id = ranked_role.get("role_id")
        if role_id not in roles_by_id:
            sys.exit(f"ranked role {role_id!r} is missing from payload roles")
        role = roles_by_id[role_id]
        governed = []
        top_refused = False
        for row in ranked_role["candidate_slate"]:
            try:
                verdict, reasons, citations, considered = verdict_for(role, row, constraints)
            except (KeyError, TypeError, ValueError) as error:
                sys.exit(f"cannot evaluate {role_id}/{row.get('candidate_id', '<unknown>')}: {error}")
            recommendation_status = "not_recommended"
            if verdict == "eligible" and float(row["fit_score"]) >= MIN_RECOMMENDABLE_SCORE:
                recommendation_status = "recommended"
            elif verdict == "eligible":
                recommendation_status = "below_score_floor"
            if row["provisional_rank"] == 1 and verdict == "ineligible":
                top_refused = True
                reason, rule = blocking_reason(reasons, citations)
                escalations.append(
                    f"{role['role_id']}: refused top provisional candidate {row['candidate_name']} - {reason} "
                    f"({rule}; independence-eligibility-rules.md #7.1)"
                )
            elif row["provisional_rank"] == 1 and verdict == "needs_review":
                reason, rule = review_reason(reasons, citations)
                escalations.append(
                    f"{role['role_id']}: withheld top provisional candidate {row['candidate_name']} "
                    f"- {reason} ({rule}; independence-eligibility-rules.md #1.2)"
                )
            if verdict == "ineligible":
                _, blocking_rule = blocking_reason(reasons, citations)
            elif verdict == "needs_review":
                _, blocking_rule = review_reason(reasons, citations)
            else:
                blocking_rule = None
            governed.append(dict(row, constraints_considered=considered, eligibility={
                "verdict": verdict,
                "recommendation_status": recommendation_status,
                "blocking_rule": blocking_rule,
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
    payload["escalations"] = merge_unique(escalations)
    provenance = payload.setdefault("provenance", {})
    engines = [
        engine for engine in provenance.get("engines", [])
        if not engine.startswith("constraint_check/")
    ]
    provenance["engines"] = merge_unique(engines, [ENGINE_VERSION])
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    refused = sum(1 for r in governed_roles if r["top_provisional_candidate_refused"])
    print(f"constraint_check: {len(governed_roles)} role(s), {refused} top-candidate refusal(s), {len(gaps)} gap(s) -> {args.out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
