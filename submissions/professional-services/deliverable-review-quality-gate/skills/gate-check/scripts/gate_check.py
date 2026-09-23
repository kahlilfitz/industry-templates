#!/usr/bin/env python3
"""gate_check - deterministic quality-gate compliance engine."""
import argparse, json, sys

ENGINE = "engine:gate_check"
RELIANCE_RESTRICTION_REQUIRED_FOR_THIRD_PARTY = True  # quality-gate-criteria.md #2.2
CONFIDENTIALITY_MARK_REQUIRED = True  # quality-gate-criteria.md #4.1
LEGAL_MARK_DEFECT_BLOCKS = True  # quality-gate-criteria.md #5.2
LICENSED_ATTRIBUTION_REQUIRED = True  # quality-gate-criteria.md #6.1
PRIOR_FIX_MUST_LAND = True  # quality-gate-criteria.md #7.1-#7.2
RELEASE_BLOCKER = "release_blocker"  # severity-rules.md #1.1
MUST_FIX = "must_fix"  # severity-rules.md #1.2
ADVISORY = "advisory"  # severity-rules.md #1.3
SEVERITY_RANK = {ADVISORY: 1, MUST_FIX: 2, RELEASE_BLOCKER: 3}
GATES = {"G1": "Evidence support and substantiation", "G2": "Required disclaimer, limitation and reliance language", "G3": "Scope-of-work alignment", "G4": "Confidentiality marking and client-data handling", "G5": "Brand and formatting standards", "G6": "Third-party and licensed content attribution", "G7": "Prior-findings closure"}

def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)

def loc(section="Cover", page=1, paragraph=1, label="Document-level"):
    return {"section": section, "page": page, "paragraph": paragraph, "label": label}

def add_finding(findings, finding_id, gate_id, severity, title, detail, location, criteria_section, confidence, citation):
    if any(existing.get("finding_id") == finding_id for existing in findings):
        return
    findings.append({"finding_id": finding_id, "gate_id": gate_id, "severity": severity, "title": title, "detail": detail, "location": location, "criteria_section": criteria_section, "confidence": confidence, "source": ENGINE, "citation": citation})

def highest_for_gate(findings, gate_id):
    gated = [item for item in findings if item.get("gate_id") == gate_id]
    return "none" if not gated else max((item["severity"] for item in gated), key=lambda sev: SEVERITY_RANK[sev])

def main():
    parser = argparse.ArgumentParser(description="Apply quality-gate compliance checks deterministically.")
    parser.add_argument("--mapped", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    payload = load_json(args.mapped)
    assert payload["contract_version"] == "ps.deliverable-review-quality-gate.v1", "wrong contract version"
    deliverable = payload["deliverable"]
    findings, escalations = list(payload.get("findings", [])), list(payload.get("escalations", []))
    if deliverable.get("third_party_recipient_named") and RELIANCE_RESTRICTION_REQUIRED_FOR_THIRD_PARTY:
        if "reliance_restriction" not in deliverable.get("present_disclaimer_types", []):
            add_finding(findings, "GC-G2-reliance-language", "G2", RELEASE_BLOCKER, "Wrong disclaimer for third-party recipient", "A third-party recipient is named but reliance-restriction language is absent; a general-advice disclaimer does not satisfy this gate.", loc("Limitations and reliance", 2, 4, "Disclaimer block"), "quality-gate-criteria.md #2.2", 0.98, "quality-gate-criteria.md #2.2; severity-rules.md #1.1")
            escalations.append("G2: third-party recipient named and reliance-restriction language absent - release blocker (quality-gate-criteria.md #2.2)")
    for required in deliverable.get("required_language", []):
        if required not in deliverable.get("present_language", []):
            severity = RELEASE_BLOCKER if required == "reliance_restriction" else MUST_FIX
            add_finding(findings, f"GC-G2-missing-{required}", "G2", severity, f"Missing required language: {required}", f"Required language `{required}` is not present in the deliverable.", loc("Limitations and reliance", 2, 4, "Required language"), "quality-gate-criteria.md #2.1-#2.3", 0.94, "quality-gate-criteria.md #2.1-#2.3")
    if CONFIDENTIALITY_MARK_REQUIRED and deliverable.get("confidentiality_marking") != "client confidential":
        add_finding(findings, "GC-G4-confidentiality", "G4", RELEASE_BLOCKER, "Missing client-confidential marking", "Required client-confidential marking is absent from cover/footer.", loc("Cover", 1, 1, "Confidentiality mark"), "quality-gate-criteria.md #4.1", 0.97, "quality-gate-criteria.md #4.1; severity-rules.md #1.1")
    if deliverable.get("client_data_handling") in {"breach", "unknown"}:
        add_finding(findings, "GC-G4-client-data", "G4", RELEASE_BLOCKER, "Client-data handling is not release-ready", "Client data handling is breach or unknown.", loc("Appendix", 12, 1, "Client data handling"), "quality-gate-criteria.md #4.2", 0.95, "quality-gate-criteria.md #4.2")
    for check in deliverable.get("brand_checks", []):
        if check.get("status") == "fail":
            severity = MUST_FIX if check.get("legal_or_release_control") and LEGAL_MARK_DEFECT_BLOCKS else ADVISORY
            add_finding(findings, f"GC-G5-{check['check_id']}", "G5", severity, check.get("title", "Brand or formatting defect"), check.get("detail", "Brand check failed"), check.get("location", loc("Document", 1, 1, "Brand check")), "quality-gate-criteria.md #5.1-#5.2", check.get("confidence", 0.9), check.get("citation", "quality-gate-criteria.md #5.1-#5.2"))
    for item in deliverable.get("licensed_content", []):
        if LICENSED_ATTRIBUTION_REQUIRED and not item.get("attribution_present"):
            severity = RELEASE_BLOCKER if item.get("license_status") == "unknown" else MUST_FIX
            add_finding(findings, f"GC-G6-{item['content_id']}", "G6", severity, "Licensed content lacks attribution", item.get("detail", "Third-party content requires attribution."), item.get("location", loc("Document", 1, 1, "Licensed content")), "quality-gate-criteria.md #6.1-#6.2", item.get("confidence", 0.93), item.get("citation", "quality-gate-criteria.md #6.1-#6.2"))
    for prior in payload.get("prior_findings", []):
        if prior.get("claimed_closed") and not prior.get("document_fix_present") and PRIOR_FIX_MUST_LAND:
            add_finding(findings, f"GC-G7-{prior['finding_id']}", "G7", MUST_FIX, "Prior finding marked closed but fix is absent", prior.get("detail", "Tracker closure is not supported by the current document."), prior.get("location", loc("Document", 1, 1, "Prior finding")), "quality-gate-criteria.md #7.1-#7.2", prior.get("confidence", 0.96), prior.get("citation", "quality-gate-criteria.md #7.1-#7.2"))
    for mapping in payload.get("assertion_mappings", []):
        if mapping.get("support_status") in {"unsupported", "limited"} and "#3.2" in mapping.get("criteria_section", ""):
            add_finding(findings, f"GC-G3-{mapping['assertion_id']}", "G3", MUST_FIX, "Scope or sample limitation missing at point of recommendation", mapping.get("rationale", "Recommendation requires limitation."), mapping["location"], "quality-gate-criteria.md #3.2", mapping.get("confidence", 0.8), mapping.get("citation", "quality-gate-criteria.md #3.2"))
    gate_results = []
    for gate_id, name in GATES.items():
        highest = highest_for_gate(findings, gate_id)
        status = "cleared" if highest == "none" else "blocked" if highest == RELEASE_BLOCKER else "attention_required"
        gate_results.append({"gate_id": gate_id, "name": name, "status": status, "highest_severity": highest, "finding_count": sum(1 for item in findings if item.get("gate_id") == gate_id), "confidence": 0.95, "source": ENGINE, "citation": f"quality-gate-criteria.md #{gate_id[1]}"})
    payload["findings"], payload["gate_results"], payload["escalations"] = findings, gate_results, escalations
    payload.setdefault("provenance", {}).setdefault("engines", []).append("gate_check/1.0")
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    blockers = sum(1 for item in findings if item["severity"] == RELEASE_BLOCKER)
    must_fix = sum(1 for item in findings if item["severity"] == MUST_FIX)
    advisory = sum(1 for item in findings if item["severity"] == ADVISORY)
    print(f"gate_check: {len(gate_results)} gate(s), blockers={blockers}, must_fix={must_fix}, advisory={advisory} -> {args.out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
