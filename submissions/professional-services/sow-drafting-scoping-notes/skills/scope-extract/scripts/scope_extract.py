#!/usr/bin/env python3
"""scope_extract - deterministic scope and thin-input engine.

Reads normalized pursuit evidence produced by notes-ingest and writes the
ps.sow-drafting-scoping-notes.v1 contract hop. The model may extract messy notes into
evidence, but thin-input calls, assumptions and exclusions are computed here.

Constants mirror references/qrm-deviation-rules.md by section number.
"""
import argparse
import json
import sys

ENGINE = "engine:scope_extract"
CONTRACT = "ps.sow-drafting-scoping-notes.v1"

THIN_INPUT_CONFIDENCE_FLOOR = 0.72  # qrm-deviation-rules.md #4.1
MISSING_FACT_REFUSAL = True         # qrm-deviation-rules.md #4.2
VERBAL_DATE_REFUSAL = True          # qrm-deviation-rules.md #4.3

REQUIRED_FACTS = {
    "acceptance.criteria": ("acceptance criteria", "acceptance"),
    "acceptance.review_period": ("acceptance review period", "acceptance"),
    "data.supplier": ("client test-data supplier", "client_test_data"),
    "data.quality_standard": ("test-data quality standard", "client_test_data"),
}

GAP_TEXT = {
    "acceptance.criteria": {
        "assumption": "Acceptance criteria will be confirmed in writing before the related deliverable is baselined.",
        "exclusion": "The draft does not commit to objective acceptance or deemed acceptance until criteria are documented.",
    },
    "acceptance.review_period": {
        "assumption": "The parties will agree the acceptance review period before issuing the SOW.",
        "exclusion": "No deemed acceptance timeline is drafted without an agreed review period.",
    },
    "data.supplier": {
        "assumption": "The client will name an accountable owner for test data before build or validation activities begin.",
        "exclusion": "The provider does not warrant completeness, accuracy or timeliness of test data not supplied by the client.",
    },
    "data.quality_standard": {
        "assumption": "The client will provide test data that meets documented quality and privacy requirements.",
        "exclusion": "Rework caused by incomplete, masked, late or non-compliant test data is excluded from the draft scope.",
    },
}


def evidence_by_key(payload):
    return {item["key"]: item for item in payload.get("evidence", [])}


def grounded_item(item, status="draftable"):
    return {
        "id": item["id"],
        "text": item["text"],
        "status": status,
        "source": ENGINE,
        "citation": item["citation"],
        "confidence": round(float(item.get("confidence", 0.0)), 2),
    }


def thin_item(commitment, missing_fact, effect, citation, confidence, rule):
    return {
        "commitment": commitment,
        "missing_fact": missing_fact,
        "effect": effect,
        "rule": rule,
        "source": ENGINE,
        "citation": citation,
        "confidence": round(float(confidence), 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    payload = json.load(open(args.input, encoding="utf-8"))
    assert payload["contract_version"] == CONTRACT, "wrong contract version"

    facts = evidence_by_key(payload)
    thin, assumptions, exclusions, escalations = [], [], [], list(payload.get("escalations", []))

    for key, (label, commitment) in REQUIRED_FACTS.items():
        fact = facts.get(key)
        confidence = float(fact.get("confidence", 0.0)) if fact else 0.0
        if fact is None or confidence < THIN_INPUT_CONFIDENCE_FLOOR:
            citation = fact.get("citation", "missing from scoping notes") if fact else "missing from scoping notes"
            missing = label if fact is None else f"{label} below confidence floor {THIN_INPUT_CONFIDENCE_FLOOR}"
            thin.append(thin_item(
                commitment,
                missing,
                f"Do not draft a {commitment.replace('_', ' ')} commitment; convert the gap into assumptions and exclusions.",
                citation,
                confidence,
                "qrm-deviation-rules.md #4.1,#4.2",
            ))
            assumptions.append({
                "id": f"asm-{key.replace('.', '-')}",
                "text": GAP_TEXT[key]["assumption"],
                "status": "draftable",
                "source": ENGINE,
                "citation": "qrm-deviation-rules.md #4.2",
                "confidence": 0.99,
            })
            exclusions.append({
                "id": f"exc-{key.replace('.', '-')}",
                "text": GAP_TEXT[key]["exclusion"],
                "status": "draftable",
                "source": ENGINE,
                "citation": "qrm-deviation-rules.md #4.2",
                "confidence": 0.99,
            })
            escalations.append(f"{commitment}: {missing} - commitment blocked (qrm-deviation-rules.md #4.1,#4.2)")

    deliverables = [
        grounded_item(d, "draftable" if float(d.get("confidence", 0.0)) >= THIN_INPUT_CONFIDENCE_FLOOR else "blocked_thin_input")
        for d in payload.get("candidate_deliverables", [])
    ]

    acceptance = []
    if not any(t["commitment"] == "acceptance" for t in thin):
        for item in payload.get("candidate_acceptance_criteria", []):
            acceptance.append(grounded_item(item))

    milestones = []
    for item in payload.get("candidate_milestones", []):
        confidence = float(item.get("confidence", 0.0))
        basis_type = item.get("basis_type", "")
        status = "draftable"
        if confidence < THIN_INPUT_CONFIDENCE_FLOOR or basis_type in ("verbal_only", "aspirational"):
            status = "planning_target_only"
            thin.append(thin_item(
                item["name"],
                "delivery-date basis is verbal or not supported by an integrated plan",
                "Treat as a planning target only; do not draft as a committed delivery date.",
                item.get("citation", "scoping notes"),
                confidence,
                "qrm-deviation-rules.md #4.1,#4.3",
            ))
            assumptions.append({
                "id": f"asm-{item['id']}-planning-target",
                "text": f"{item['name']} is a planning target until the parties approve an integrated plan and dependency owners.",
                "status": "draftable",
                "source": ENGINE,
                "citation": "qrm-deviation-rules.md #4.3",
                "confidence": 0.99,
            })
            exclusions.append({
                "id": f"exc-{item['id']}-committed-date",
                "text": f"The draft does not commit to {item['name']} on {item['timing']} absent approved plan evidence.",
                "status": "draftable",
                "source": ENGINE,
                "citation": "qrm-deviation-rules.md #4.3",
                "confidence": 0.99,
            })
            escalations.append(f"{item['name']}: verbal or unsupported date - planning target only (qrm-deviation-rules.md #4.3)")
        milestones.append({
            "id": item["id"],
            "name": item["name"],
            "timing": item["timing"],
            "commitment_status": status,
            "source": ENGINE,
            "citation": item.get("citation", "scoping notes"),
            "confidence": round(confidence, 2),
        })

    scope = {
        "summary": payload.get("scope_summary", ""),
        "deliverables": deliverables,
        "milestones": milestones,
        "acceptance_criteria": acceptance,
        "assumptions": assumptions + [grounded_item(a) for a in payload.get("candidate_assumptions", [])],
        "exclusions": exclusions + [grounded_item(e) for e in payload.get("candidate_exclusions", [])],
        "thin_input_report": thin,
    }

    payload["scope"] = scope
    payload["escalations"] = escalations
    payload.setdefault("provenance", {}).setdefault("engines", []).append("scope_extract/1.0")
    payload["provenance"]["generated_at"] = payload.get("generated_at", "2026-09-23T21:27:10+00:00")

    json.dump(payload, open(args.out, "w", encoding="utf-8"), indent=2)
    print(f"scope_extract: {len(deliverables)} deliverable(s), {len(milestones)} milestone(s), {len(thin)} thin-input item(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
