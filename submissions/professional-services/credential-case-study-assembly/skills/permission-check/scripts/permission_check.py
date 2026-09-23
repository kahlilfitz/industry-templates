#!/usr/bin/env python3
"""permission_check - deterministic naming, reference and figure clearance engine.

Reads the credential draft hop plus engagement terms, reference register and request.
Writes the governed hop. The model may draft copy from cleared facts; it never decides
permission, figure clearance or anonymisation safety.

Constants mirror references/reference-naming-permission-rules.md by section number.
"""
import argparse
import json
import re
import sys
from datetime import date

ENGINE = "engine:permission_check"
CONTRACT_VERSION = "ps.credential-case-study-assembly.v1"
EXPRESS_WRITTEN = "express_written"  # reference-naming-permission-rules.md #1.1
EXPRESS_PROHIBITION = "express_prohibition"  # reference-naming-permission-rules.md #1.2
SILENCE_IS_NOT_CONSENT = True  # reference-naming-permission-rules.md #1.3
PITCH_ONLY_SCOPE = "pitch_only"  # reference-naming-permission-rules.md #2.1
PUBLIC_MARKETING_SCOPE = "public_marketing"  # reference-naming-permission-rules.md #2.2
PRESS_SCOPE = "press"  # reference-naming-permission-rules.md #2.3
EVENT_ONLY_SCOPE = "event_only"  # reference-naming-permission-rules.md #2.4
EXPIRY_REFUSES = True  # reference-naming-permission-rules.md #3.1
LOGO_SEPARATE_RIGHT = True  # reference-naming-permission-rules.md #4.1
TESTIMONIAL_SEPARATE_RIGHT = True  # reference-naming-permission-rules.md #5.1
CLEARED_EVIDENCE_TYPE = "verified_deliverable"  # reference-naming-permission-rules.md #6.1
UNCLEARED_EVIDENCE_TYPES = {"client_internal_estimate", "anecdotal", "draft"}  # reference-naming-permission-rules.md #6.2
SEPARATE_UNCLEARED_FIGURES = True  # reference-naming-permission-rules.md #6.4
REIDENTIFICATION_SIGNAL_THRESHOLD = 3  # reference-naming-permission-rules.md #7.1
DEFAULT_REFUSE_TO_NAME = True  # reference-naming-permission-rules.md #8.1


def parse_date(value):
    if not value:
        return None
    return date.fromisoformat(value)


def scope_allows(scope, requested_use):
    if requested_use == PITCH_ONLY_SCOPE:
        return scope in {PITCH_ONLY_SCOPE, PUBLIC_MARKETING_SCOPE, PRESS_SCOPE}
    if requested_use == PUBLIC_MARKETING_SCOPE:
        return scope == PUBLIC_MARKETING_SCOPE
    if requested_use == PRESS_SCOPE:
        return scope == PRESS_SCOPE
    return False


def active(record, requested_on):
    expires = parse_date(record.get("expires_on"))
    return expires is None or expires >= requested_on


def citation(record):
    return record.get("citation") or record.get("clause_id") or "reference register"


def governing_terms(terms):
    return terms.get("clauses", [])


def decide_naming(terms, register, requested_use, requested_on):
    clauses = governing_terms(terms)
    prohibitions = [c for c in clauses if c.get("type") == EXPRESS_PROHIBITION and c.get("applies_to") in ("name", "all")]
    if prohibitions:
        c = prohibitions[0]
        return {
            "status": "refuse_to_name",
            "rationale": f"Express prohibition in engagement terms: {c.get('summary', '')}",
            "clause": citation(c),
            "citations": [f"{citation(c)}; reference-naming-permission-rules.md #1.2,#8.1"],
        }

    candidates = []
    for record in register.get("permissions", []):
        if record.get("permission_type") == "name" and record.get("consent_type") == EXPRESS_WRITTEN:
            candidates.append(record)
    for record in candidates:
        if not active(record, requested_on):
            continue
        if scope_allows(record.get("scope"), requested_use):
            return {
                "status": "permit_to_name",
                "rationale": f"Express written consent permits {requested_use} within scope {record.get('scope')}.",
                "clause": citation(record),
                "citations": [f"{citation(record)}; reference-naming-permission-rules.md #1.1,#2"],
            }

    expired_or_wrong_scope = [r for r in candidates if r.get("scope") == EVENT_ONLY_SCOPE or not active(r, requested_on)]
    if expired_or_wrong_scope:
        r = expired_or_wrong_scope[0]
        return {
            "status": "refuse_to_name",
            "rationale": f"Only consent found is scope {r.get('scope')} expiring {r.get('expires_on')}; it does not permit {requested_use}.",
            "clause": citation(r),
            "citations": [f"{citation(r)}; reference-naming-permission-rules.md #2.4,#3.1,#8.1"],
        }

    return {
        "status": "refuse_to_name",
        "rationale": "No express written permission record for the requested use; silence is not consent.",
        "clause": "missing permission record",
        "citations": ["reference-naming-permission-rules.md #1.3,#8.1"],
    }


def decide_logo(register, naming_status, requested_use, requested_on):
    if naming_status != "permit_to_name":
        return "refuse_logo", "Logo cannot be used because client naming is not permitted.", ["reference-naming-permission-rules.md #4.2"]
    for record in register.get("permissions", []):
        if record.get("permission_type") == "logo" and record.get("consent_type") == EXPRESS_WRITTEN:
            if active(record, requested_on) and scope_allows(record.get("scope"), requested_use):
                return "permit_logo", f"Logo consent permits {requested_use}.", [f"{citation(record)}; reference-naming-permission-rules.md #4.1"]
    return "refuse_logo", "No separate logo-use consent for the requested use.", ["reference-naming-permission-rules.md #4.1"]


def decide_testimonial(register, requested_quote, requested_use, requested_on):
    if not requested_quote:
        return "not_requested", "No named-individual quote requested.", ["reference-naming-permission-rules.md #5"]
    for record in register.get("permissions", []):
        if record.get("permission_type") == "testimonial" and record.get("person") == requested_quote.get("person"):
            if active(record, requested_on) and scope_allows(record.get("scope"), requested_use):
                return "permit_testimonial", "Separate named-individual testimonial consent found.", [f"{citation(record)}; reference-naming-permission-rules.md #5.1"]
    return "refuse_testimonial", "No separate consent record for the named individual testimonial.", ["reference-naming-permission-rules.md #5.2"]


def classify_figures(outcomes, requested_use):
    cleared = []
    uncleared = []
    for outcome in outcomes:
        state = "uncleared"
        reason = "Figure is not verified deliverable evidence."
        rule = "reference-naming-permission-rules.md #6.2"
        scope = outcome.get("clearance_scope", "uncleared")
        if outcome.get("evidence_type") == CLEARED_EVIDENCE_TYPE and scope_allows(scope, requested_use):
            state = "cleared"
            reason = f"Verified deliverable evidence cleared for {scope}."
            rule = "reference-naming-permission-rules.md #6.1"
        elif outcome.get("evidence_type") == CLEARED_EVIDENCE_TYPE:
            state = "restricted"
            reason = f"Verified figure is cleared for {scope}, not {requested_use}."
            rule = "reference-naming-permission-rules.md #6.3"
        item = dict(outcome)
        item["clearance_state"] = state
        item["governing_clause"] = outcome.get("governing_clause", rule)
        item["clearance_rationale"] = reason
        item["citation"] = f"{'; '.join(outcome.get('citations', []))}; {rule}"
        if state == "cleared":
            cleared.append(item)
        else:
            uncleared.append(item)
    return cleared, uncleared


def descriptor_signals(descriptor):
    text = descriptor.lower()
    signals = []
    if re.search(r"\b(top[- ]?\d+|largest|leading|global|fortune)\b", text):
        signals.append("size_or_rank")
    if any(word in text for word in ["insurer", "bank", "payer", "hospital", "manufacturer", "telecom"]):
        signals.append("sector")
    if any(word in text for word in ["european", "north american", "asia", "emea", "uk", "us"]):
        signals.append("geography")
    if re.search(r"\b20\d{2}\b", text):
        signals.append("date")
    if any(word in text for word in ["core platform", "migration", "claims", "policy", "merger", "divestiture"]):
        signals.append("unique_programme")
    return signals


def descriptor_status(descriptor):
    if not descriptor:
        return "not_provided", [], "No anonymised descriptor was provided."
    signals = descriptor_signals(descriptor)
    if len(signals) >= REIDENTIFICATION_SIGNAL_THRESHOLD:
        return "reidentifying", signals, f"Descriptor combines {len(signals)} identifying signals: {', '.join(signals)}."
    return "safe", signals, "Descriptor does not cross the re-identification threshold."


def safe_descriptor(client, taxonomy):
    sector = taxonomy.get("sector", {}).get("value", client.get("sector", "cross-industry"))
    if sector == "financial-services":
        return "a regulated financial-services organisation"
    if sector == "healthcare":
        return "a regional healthcare organisation"
    if sector == "public-sector":
        return "a public-sector organisation"
    return "an enterprise client"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", required=True, help="credential_draft output JSON")
    parser.add_argument("--terms", required=True, help="engagement terms JSON")
    parser.add_argument("--register", required=True, help="reference register JSON")
    parser.add_argument("--request", required=True, help="BD request JSON")
    parser.add_argument("--out", required=True, help="governed output JSON")
    args = parser.parse_args()

    payload = json.load(open(args.draft, encoding="utf-8"))
    terms = json.load(open(args.terms, encoding="utf-8"))
    register = json.load(open(args.register, encoding="utf-8"))
    request = json.load(open(args.request, encoding="utf-8"))
    if payload.get("contract_version") != CONTRACT_VERSION:
        raise AssertionError("wrong contract version")

    requested_use = request["requested_use"]
    requested_on = parse_date(request["requested_on"])
    payload["request"] = request
    payload["terms"] = terms
    payload["reference_register"] = register

    naming = decide_naming(terms, register, requested_use, requested_on)
    logo_status, logo_rationale, logo_citations = decide_logo(register, naming["status"], requested_use, requested_on)
    testimonial_status, testimonial_rationale, testimonial_citations = decide_testimonial(
        register, request.get("requested_quote"), requested_use, requested_on
    )
    cleared, uncleared = classify_figures(payload.get("outcomes", []), requested_use)
    desc_status, desc_signals, desc_rationale = descriptor_status(request.get("proposed_anonymised_descriptor", ""))
    anonymised_required = naming["status"] != "permit_to_name"
    safe = safe_descriptor(payload.get("client", {}), payload.get("taxonomy_match", {}))

    escalations = list(payload.get("taxonomy_match", {}).get("escalations", []))
    if naming["status"] != "permit_to_name":
        escalations.append(f"Naming refused: {naming['rationale']} ({naming['clause']})")
    if logo_status == "refuse_logo":
        escalations.append(f"Logo refused: {logo_rationale}")
    if testimonial_status == "refuse_testimonial":
        escalations.append(f"Testimonial refused: {testimonial_rationale}")
    if uncleared:
        escalations.append(f"{len(uncleared)} outcome figure(s) must stay out of publishable copy (reference-naming-permission-rules.md #6.4)")
    if desc_status == "reidentifying":
        escalations.append(f"Proposed anonymised descriptor blocked: {desc_rationale} (reference-naming-permission-rules.md #7.1)")

    verdict = {
        "naming_status": naming["status"],
        "naming_rationale": naming["rationale"],
        "name_governing_clause": naming["clause"],
        "logo_status": logo_status,
        "logo_rationale": logo_rationale,
        "testimonial_status": testimonial_status,
        "testimonial_rationale": testimonial_rationale,
        "anonymised_variant_required": anonymised_required,
        "proposed_descriptor": request.get("proposed_anonymised_descriptor", ""),
        "proposed_descriptor_status": desc_status,
        "proposed_descriptor_signals": desc_signals,
        "proposed_descriptor_rationale": desc_rationale,
        "safe_descriptor": safe,
        "cleared_figures": cleared,
        "uncleared_figures": uncleared,
        "escalations": escalations,
        "source": ENGINE,
        "confidence": 0.97,
        "citations": naming["citations"] + logo_citations + testimonial_citations + ["reference-naming-permission-rules.md #6-#8"],
    }
    payload["permission_verdict"] = verdict
    payload.setdefault("draft_assets", {}).setdefault("anonymised_variant", {})
    payload["draft_assets"]["anonymised_variant"].update({
        "required": anonymised_required,
        "safe_descriptor": safe,
        "blocked_descriptor": request.get("proposed_anonymised_descriptor", "") if desc_status == "reidentifying" else "",
        "instruction": "Use only the safe_descriptor when naming is refused; do not include uncleared figures.",
        "source": ENGINE,
        "confidence": 0.97,
        "citations": ["reference-naming-permission-rules.md #7.1,#7.3"],
    })
    payload.setdefault("provenance", {}).setdefault("engines", []).append("permission_check/1.0")
    payload["provenance"]["generated_at"] = request["requested_on"]

    json.dump(payload, open(args.out, "w", encoding="utf-8"), indent=2)
    print(
        f"permission_check: naming={verdict['naming_status']}, logo={logo_status}, "
        f"testimonial={testimonial_status}, cleared_figures={len(cleared)}, "
        f"uncleared_figures={len(uncleared)}, descriptor={desc_status} -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
