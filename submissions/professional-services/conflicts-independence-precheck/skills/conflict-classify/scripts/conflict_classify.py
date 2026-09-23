#!/usr/bin/env python3
"""conflict_classify - deterministic conflicts and independence Govern engine.

Reads resolved entity scope and register exports, writes classification output under
ps.conflicts-independence-precheck.v1. The model drafts prose from this output and never
changes the classification or escalation posture.
"""
import argparse
import json
import sys
from datetime import date

ENGINE = "engine:conflict_classify"
CONFIDENCE_FLOOR = 0.75  # conflicts-independence-rules.md #9.1
FORMER_CLIENT_DUTY_MONTHS = 24  # conflicts-independence-rules.md #4.1
AFFILIATE_OWNERSHIP_THRESHOLD = 0.50  # conflicts-independence-rules.md #3.1
NON_WAIVABLE_CATEGORIES = {
    "audit_independence_prohibited_non_audit_service"
}  # conflicts-independence-rules.md #7.1,#10.2
# Registers this engine actually reads. The scope attestation is derived from this set,
# never copied from the input's own claim.  # conflicts-independence-rules.md #12.1
COVERED_REGISTERS = (
    "client_register",
    "matter_register",
    "adverse_party_register",
    "independence_register",
    "prior_clearance_decisions",
)
# Input keys that carry scope metadata rather than searchable records.
METADATA_KEYS = {"registers_searched", "date_range", "as_of", "citation"}


def parse_date(value):
    return date.fromisoformat(value)


def months_between(start, end):
    return (end.year - start.year) * 12 + (end.month - start.month) - (1 if end.day < start.day else 0)


def target_entities(resolved_entities):
    targets = {}
    for item in resolved_entities:
        if item["match_status"] not in ("controlled_match", "fuzzy_match"):
            continue
        for member in item.get("corporate_family", []):
            if float(member.get("ownership_pct", 0)) >= AFFILIATE_OWNERSHIP_THRESHOLD or member["entity_id"] == item["resolved_entity_id"]:
                targets[member["entity_id"]] = {
                    "entity_id": member["entity_id"],
                    "name": member["legal_name"],
                    "party_id": item["party_id"],
                    "party_name": item["given_name"],
                    "match_score": item["confidence"],
                    "family_relationship": member.get("relationship", "family member")
                }
    return targets


def service_overlap(proposed, prohibited):
    proposed_norm = {s.lower().replace("_", " ") for s in proposed}
    prohibited_norm = {s.lower().replace("_", " ") for s in prohibited}
    return sorted(proposed_norm & prohibited_norm)


def classify(resolved, registers):
    as_of = parse_date(resolved.get("analysis_as_of", registers.get("as_of")))
    services = resolved.get("matter", {}).get("services", [])
    targets = target_entities(resolved.get("resolved_entities", []))
    hits = []
    escalations = list(resolved.get("escalations", []))
    direct_adverse_entity_ids = set()
    hit_no = 1

    for matter in registers.get("matter_register", []):
        if matter.get("status") != "live":
            continue
        adverse_ids = set(matter.get("adverse_party_entity_ids", []))
        for entity_id in sorted(adverse_ids & set(targets)):
            target = targets[entity_id]
            direct_adverse_entity_ids.add(entity_id)
            hits.append({
                "hit_id": f"H{hit_no:03d}",
                "register": "matter_register",
                "record_id": matter["matter_id"],
                "conflict_type": "direct_adverse_representation",
                "matched_entity": target["name"],
                "matched_entity_id": entity_id,
                "match_score": target["match_score"],
                "relationship": f"{target['party_name']} family member {target['name']} is adverse to client {matter['client_name']} in live matter {matter['matter_id']}",
                "governing_rule": "direct adverse live matter",
                "waiver_posture": "required_consent_or_qrm_refusal_position",
                "ethical_wall_recommendation": "wall_not_sufficient_for_active_direct_adversity",
                "required_action": "escalate_to_qrm_before_any_pursuit_commitment",
                "confidence": min(0.97, target["match_score"]),
                "source": ENGINE,
                "citation": matter["citation"],
                "rule": "conflicts-independence-rules.md #2.1,#3.1,#8.2,#10.1"
            })
            hit_no += 1

    for adverse in registers.get("adverse_party_register", []):
        entity_id = adverse.get("entity_id")
        if entity_id not in targets or entity_id in direct_adverse_entity_ids:
            continue
        target = targets[entity_id]
        matter_ref = adverse.get("matter_id")
        hits.append({
            "hit_id": f"H{hit_no:03d}",
            "register": "adverse_party_register",
            "record_id": adverse["adverse_record_id"],
            "conflict_type": "adverse_party_register_listing",
            "matched_entity": target["name"],
            "matched_entity_id": entity_id,
            "match_score": target["match_score"],
            "relationship": (
                f"{target['party_name']} family member {target['name']} is recorded on the adverse-party register"
                + (f" in connection with matter {matter_ref}" if matter_ref else " with no live matter linked")
            ),
            "governing_rule": "adverse-party register listing",
            "waiver_posture": "qrm_review_required; posture depends on the duty recorded against the listing",
            "ethical_wall_recommendation": "wall_only_if_qrm_confirms_no_shared_confidential_information",
            "required_action": "escalate_to_qrm_before_any_pursuit_commitment",
            "confidence": min(0.92, target["match_score"]),
            "source": ENGINE,
            "citation": adverse["citation"],
            "rule": "conflicts-independence-rules.md #2.1,#3.1,#12.3"
        })
        hit_no += 1

    for client in registers.get("client_register", []):
        entity_id = client.get("entity_id")
        if entity_id not in targets or client.get("status") != "former":
            continue
        closed = parse_date(client["closed_on"])
        age_months = months_between(closed, as_of)
        if age_months <= FORMER_CLIENT_DUTY_MONTHS:
            target = targets[entity_id]
            hits.append({
                "hit_id": f"H{hit_no:03d}",
                "register": "client_register",
                "record_id": client["client_record_id"],
                "conflict_type": "former_client_duty_window",
                "matched_entity": target["name"],
                "matched_entity_id": entity_id,
                "match_score": target["match_score"],
                "relationship": f"former-client matter closed {age_months} months before analysis date and is marked substantially related",
                "governing_rule": "former-client duty window",
                "waiver_posture": "qrm_review_required; consent may be required if policy permits",
                "ethical_wall_recommendation": "wall_only_if_qrm_confirms_no_shared_confidential_information",
                "required_action": "hold_for_former_client_review",
                "confidence": min(0.9, target["match_score"]),
                "source": ENGINE,
                "citation": client["citation"],
                "rule": "conflicts-independence-rules.md #4.1,#4.2,#10.1"
            })
            hit_no += 1

    for independence in registers.get("independence_register", []):
        entity_id = independence.get("entity_id")
        if entity_id not in targets:
            continue
        overlap = service_overlap(services, independence.get("prohibited_services", []))
        if independence.get("restriction_type") == "audit_client" and overlap:
            target = targets[entity_id]
            hits.append({
                "hit_id": f"H{hit_no:03d}",
                "register": "independence_register",
                "record_id": independence["restriction_id"],
                "conflict_type": "audit_independence_prohibited_non_audit_service",
                "matched_entity": target["name"],
                "matched_entity_id": entity_id,
                "match_score": target["match_score"],
                "relationship": f"proposed service(s) {', '.join(overlap)} overlap prohibited-service list for audit client family",
                "governing_rule": "audit independence prohibited non-audit service",
                "waiver_posture": "non_waivable_in_illustrative_ruleset",
                "ethical_wall_recommendation": "wall_not_sufficient_for_audit_independence_restriction",
                "required_action": "escalation_packet_with_refusal_position_for_human_qrm_review",
                "confidence": min(0.96, target["match_score"]),
                "source": ENGINE,
                "citation": independence["citation"],
                "rule": "conflicts-independence-rules.md #7.1,#7.2,#8.2,#10.2"
            })
            hit_no += 1

    for item in resolved.get("resolved_entities", []):
        if item["match_status"] == "human_review":
            hits.append({
                "hit_id": f"H{hit_no:03d}",
                "register": "entity_resolution",
                "record_id": item.get("candidate_entity_id") or "unresolved",
                "conflict_type": "ambiguous_entity_identity",
                "matched_entity": item.get("candidate_legal_name") or item["given_name"],
                "matched_entity_id": item.get("candidate_entity_id"),
                "match_score": item["confidence"],
                "relationship": f"{item['given_name']} resembles {item.get('candidate_legal_name')} but is inside the forced human-review band",
                "governing_rule": "entity identity below automatic threshold",
                "waiver_posture": "not_classified_until_identity_review",
                "ethical_wall_recommendation": "not_available_until_identity_review",
                "required_action": "hold_for_entity_resolution_review",
                "confidence": item["confidence"],
                "source": ENGINE,
                "citation": item["citation"],
                "rule": "entity-resolution-rules.md #4.2; conflicts-independence-rules.md #9.1,#9.2"
            })
            hit_no += 1

    # Prior clearance decisions are surfaced as context only and never downgrade a hit.
    # conflicts-independence-rules.md #12.4
    prior_context = []
    target_ids = set(targets)
    for decision in registers.get("prior_clearance_decisions", []):
        if decision.get("entity_id") not in target_ids:
            continue
        prior_context.append({
            "decision_id": decision["decision_id"],
            "entity_id": decision["entity_id"],
            "summary": decision.get("summary", ""),
            "effect": "non_controlling_context_only",
            "source": ENGINE,
            "citation": decision["citation"],
            "rule": "conflicts-independence-rules.md #12.4"
        })

    for hit in hits:
        if hit["confidence"] < CONFIDENCE_FLOOR:
            hit["required_action"] = "hold_for_human_review"
            escalations.append(f"{hit['hit_id']}: confidence {hit['confidence']} below {CONFIDENCE_FLOOR}; human review required (conflicts-independence-rules.md #9.1)")
        if hit["conflict_type"] in NON_WAIVABLE_CATEGORIES:
            escalations.append(f"{hit['hit_id']}: non-waivable/prohibited-service category; model cannot downgrade (conflicts-independence-rules.md #10.2)")

    # Scope attestation is derived from what this engine actually read, never from the
    # input's own claim. An uncovered register forces human review.
    # conflicts-independence-rules.md #12.1,#12.2
    supplied = [k for k in registers if k not in METADATA_KEYS and isinstance(registers.get(k), list)]
    searched = [r for r in COVERED_REGISTERS if r in supplied]
    not_searched = sorted(r for r in supplied if r not in COVERED_REGISTERS)
    for register_name in not_searched:
        escalations.append(
            f"scope: register '{register_name}' was supplied but is not covered by this engine; "
            f"treat the search as incomplete (conflicts-independence-rules.md #12.2)"
        )

    if hits:
        min_conf = min(h["confidence"] for h in hits)
        position = {
            "position": "escalate_to_qrm" if min_conf >= CONFIDENCE_FLOOR and not not_searched else "hold_for_human_review",
            "human_clearance_required": True,
            "draft_output": "escalation_packet",
            "summary": f"{len(hits)} hit(s) found; prepare escalation packet for human QRM review. This is not a clearance.",
            "confidence": round(min_conf, 4),
            "source": ENGINE,
            "citation": "conflicts-independence-rules.md #1.1,#9.1,#10.2,#11.1"
        }
    elif not_searched:
        position = {
            "position": "hold_for_human_review",
            "human_clearance_required": True,
            "draft_output": "escalation_packet",
            "summary": (
                "No hits found in the registers searched, but "
                f"{len(not_searched)} supplied register(s) were not searched; the search is incomplete "
                "and must not be read as a clean result."
            ),
            "confidence": 0.5,
            "source": ENGINE,
            "citation": "conflicts-independence-rules.md #11.2,#12.2"
        }
    else:
        position = {
            "position": "no_hits_found_subject_to_review",
            "human_clearance_required": True,
            "draft_output": "proposed_clearance_memo",
            "summary": "No hits found in the registers searched, subject to human review and the stated search scope.",
            "confidence": 0.88,
            "source": ENGINE,
            "citation": "conflicts-independence-rules.md #1.2,#11.1,#11.2"
        }

    scope = resolved.get("search_scope", {})
    scope["registers_searched"] = searched
    scope["registers_not_searched"] = not_searched
    scope["date_range"] = registers.get("date_range", scope.get("date_range", {}))
    scope["source"] = ENGINE
    scope["citation"] = registers.get("citation", "register exports")

    resolved["search_scope"] = scope
    resolved["conflict_hits"] = hits
    resolved["prior_clearance_context"] = prior_context
    resolved["precheck_position"] = position
    resolved["escalations"] = escalations
    resolved.setdefault("provenance", {}).setdefault("engines", []).append("conflict_classify/1.0")
    resolved["provenance"]["generated_at"] = resolved.get("analysis_as_of", "")
    return resolved


def main():
    parser = argparse.ArgumentParser(description="Classify conflicts and independence hits deterministically.")
    parser.add_argument("--resolved", required=True)
    parser.add_argument("--registers", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    resolved = json.load(open(args.resolved, encoding="utf-8"))
    registers = json.load(open(args.registers, encoding="utf-8"))
    assert resolved["contract_version"] == "ps.conflicts-independence-precheck.v1", "wrong contract version"
    output = classify(resolved, registers)
    json.dump(output, open(args.out, "w", encoding="utf-8"), indent=2)
    print(f"conflict_classify: {len(output.get('conflict_hits', []))} hit(s), position={output['precheck_position']['position']} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
