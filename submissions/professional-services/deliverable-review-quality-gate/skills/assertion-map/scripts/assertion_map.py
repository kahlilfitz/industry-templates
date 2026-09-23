#!/usr/bin/env python3
"""assertion_map - deterministic assertion-to-evidence support engine."""
import argparse, json, sys

ENGINE = "engine:assertion_map"
EVIDENCE_CONFIDENCE_FLOOR = 0.70  # severity-rules.md #2.2
QUANTIFIED_CONFIDENCE_FLOOR = 0.80  # severity-rules.md #2.3; quality-gate-criteria.md #1.2
FORWARD_LOOKING_CONFIDENCE_FLOOR = 0.55  # quality-gate-criteria.md #1.3
RECOMMENDATION_CONFIDENCE_FLOOR = 0.65  # quality-gate-criteria.md #1.4
MIN_RECOMMENDATION_SAMPLE_SIZE = 30  # quality-gate-criteria.md #1.4
TRACEABLE_QUANTIFIED_TYPES = {"analysis_model", "financial_model", "system_export", "signed_client_data"}  # quality-gate-criteria.md #1.2
WEAK_EVIDENCE_TYPES = {"stakeholder_verbal", "workshop_note"}  # quality-gate-criteria.md #1.1

def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)

def best_evidence(assertion, evidence_by_id):
    candidates = [evidence_by_id[eid] for eid in assertion.get("evidence_ids", []) if eid in evidence_by_id]
    return max(candidates, key=lambda item: item.get("confidence", 0.0)) if candidates else None

def location_label(location):
    return f"p{location.get('page')}, {location.get('section')}, paragraph {location.get('paragraph')}"

def classify(assertion, evidence):
    klass = assertion["class"]
    if evidence is None:
        return "unsupported", 0.0, "No cited evidence item was found in the support pack", "quality-gate-criteria.md #1.1"
    confidence = min(float(assertion.get("confidence", 0.0)), float(evidence.get("confidence", 0.0)))
    ev_type = evidence.get("type", "unknown")
    if klass == "quantified":
        if ev_type not in TRACEABLE_QUANTIFIED_TYPES:
            return "unsupported", confidence, f"Quantified claim cites {ev_type}, not traceable analysis or signed data", "quality-gate-criteria.md #1.2; severity-rules.md #2.3"
        if confidence < QUANTIFIED_CONFIDENCE_FLOOR:
            return "unsupported", confidence, f"Quantified support confidence {confidence:.2f} below {QUANTIFIED_CONFIDENCE_FLOOR:.2f}", "severity-rules.md #2.3"
        return "supported", confidence, "Quantified claim supported by traceable analytical evidence", "quality-gate-criteria.md #1.2"
    if klass == "factual":
        if ev_type in WEAK_EVIDENCE_TYPES or confidence < EVIDENCE_CONFIDENCE_FLOOR:
            return "unsupported", confidence, f"Factual claim support is {ev_type} at confidence {confidence:.2f}", "quality-gate-criteria.md #1.1; severity-rules.md #2.2"
        return "supported", confidence, "Factual claim has cited evidence above the support floor", "quality-gate-criteria.md #1.1"
    if klass == "forward_looking":
        if not assertion.get("hedging_present") or not assertion.get("limitation_present"):
            return "limited", confidence, "Forward-looking statement lacks required hedging or limitation", "quality-gate-criteria.md #1.3"
        if confidence < FORWARD_LOOKING_CONFIDENCE_FLOOR:
            return "limited", confidence, f"Forward-looking support confidence {confidence:.2f} below {FORWARD_LOOKING_CONFIDENCE_FLOOR:.2f}", "quality-gate-criteria.md #1.3"
        return "supported", confidence, "Forward-looking statement is hedged and limitation is stated", "quality-gate-criteria.md #1.3"
    if klass == "recommendation":
        sample_size = assertion.get("sample_size")
        if not assertion.get("stated_basis"):
            return "unsupported", confidence, "Recommendation has no stated basis", "quality-gate-criteria.md #1.4"
        if sample_size is not None and sample_size < MIN_RECOMMENDATION_SAMPLE_SIZE and not assertion.get("limitation_present"):
            return "unsupported", confidence, f"Recommendation uses sample size {sample_size}, below {MIN_RECOMMENDATION_SAMPLE_SIZE}, without a limitation", "quality-gate-criteria.md #1.4; quality-gate-criteria.md #3.2"
        if confidence < RECOMMENDATION_CONFIDENCE_FLOOR:
            return "limited", confidence, f"Recommendation support confidence {confidence:.2f} below {RECOMMENDATION_CONFIDENCE_FLOOR:.2f}", "quality-gate-criteria.md #1.4"
        return "supported", confidence, "Recommendation has a stated basis and proportionate support", "quality-gate-criteria.md #1.4"
    return "unsupported", 0.0, f"Unknown assertion class {klass}", "severity-rules.md #2.1"

def main():
    parser = argparse.ArgumentParser(description="Map assertions to evidence support deterministically.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    payload = load_json(args.input)
    assert payload["contract_version"] == "ps.deliverable-review-quality-gate.v1", "wrong contract version"
    evidence_by_id = {item["evidence_id"]: item for item in payload.get("evidence_set", [])}
    findings, escalations, mappings = list(payload.get("findings", [])), list(payload.get("escalations", [])), []
    for assertion in payload.get("assertions", []):
        evidence = best_evidence(assertion, evidence_by_id)
        status, support_score, rationale, criteria_section = classify(assertion, evidence)
        mapping = {
            "assertion_id": assertion["assertion_id"], "class": assertion["class"], "text": assertion["text"],
            "location": assertion["location"], "evidence_ids": assertion.get("evidence_ids", []),
            "best_evidence_id": evidence.get("evidence_id") if evidence else None, "support_status": status,
            "support_score": round(support_score, 2), "rationale": rationale, "criteria_section": criteria_section,
            "confidence": round(support_score, 2), "source": ENGINE,
            "citation": f"{assertion['citation']}; {evidence.get('citation') if evidence else 'no evidence found'}; {criteria_section}"
        }
        mappings.append(mapping)
        if status in {"unsupported", "limited"}:
            severity = "release_blocker" if assertion["class"] == "quantified" and status == "unsupported" else "must_fix" if status == "unsupported" else "advisory"
            findings.append({"finding_id": f"AM-{assertion['assertion_id']}", "gate_id": "G1", "severity": severity,
                "title": f"{assertion['class'].replace('_', ' ').title()} assertion is {status}", "detail": rationale,
                "location": assertion["location"], "criteria_section": criteria_section, "confidence": round(support_score, 2),
                "source": ENGINE, "citation": mapping["citation"]})
            escalations.append(f"{assertion['assertion_id']} at {location_label(assertion['location'])}: {status} - {rationale} ({criteria_section})")
    payload["assertion_mappings"], payload["findings"], payload["escalations"] = mappings, findings, escalations
    payload.setdefault("provenance", {}).setdefault("engines", []).append("assertion_map/1.0")
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    unsupported = sum(1 for item in mappings if item["support_status"] == "unsupported")
    limited = sum(1 for item in mappings if item["support_status"] == "limited")
    print(f"assertion_map: {len(mappings)} assertion(s), {unsupported} unsupported, {limited} limited -> {args.out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
