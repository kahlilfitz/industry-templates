#!/usr/bin/env python3
"""gate_check - deterministic quality-gate compliance engine."""
import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime

ENGINE = "engine:gate_check"
ENGINE_VERSION = "1.0.1"
CONTRACT_VERSION = "ps.deliverable-review-quality-gate.v1"
RELIANCE_RESTRICTION_REQUIRED_FOR_THIRD_PARTY = True  # quality-gate-criteria.md #2.2
CONFIDENTIALITY_MARK_REQUIRED = True  # quality-gate-criteria.md #4.1
LEGAL_MARK_DEFECT_BLOCKS = True  # quality-gate-criteria.md #5.2
LICENSED_ATTRIBUTION_REQUIRED = True  # quality-gate-criteria.md #6.1
PRIOR_FIX_MUST_LAND = True  # quality-gate-criteria.md #7.1-#7.2
EMBEDDED_INSTRUCTION_HOLD = True  # quality-gate-criteria.md #8.1-#8.3
RELEASE_BLOCKER = "release_blocker"  # severity-rules.md #1.1
MUST_FIX = "must_fix"  # severity-rules.md #1.2
ADVISORY = "advisory"  # severity-rules.md #1.3
SEVERITY_RANK = {ADVISORY: 1, MUST_FIX: 2, RELEASE_BLOCKER: 3}
VALID_SEVERITIES = set(SEVERITY_RANK)
GATES = {"G1": "Evidence support and substantiation", "G2": "Required disclaimer, limitation and reliance language", "G3": "Scope-of-work alignment", "G4": "Confidentiality marking and client-data handling", "G5": "Brand and formatting standards", "G6": "Third-party and licensed content attribution", "G7": "Prior-findings closure", "G8": "Data-as-data and embedded-instruction handling"}
THIRD_PARTY_TERMS = ("lender", "lenders", "regulator", "acquirer", "vendor", "bank", "auditor", "investor", "insurer", "rating agency")
AMBIGUOUS_RECIPIENT_TERMS = ("tbd", "to be confirmed", "external parties", "third parties", "stakeholders", "interested parties", "advisors", "advisers", "allowed users", "distribution list")
SCAN_KEYS = {"text", "title", "detail", "notes", "note", "content", "summary", "description", "comment"}
SAFE_STRING_KEYS = {"source", "citation", "criteria_section", "contract_version", "scenario_id", "engagement_id", "deliverable_id", "evidence_id", "finding_id", "assertion_id", "content_id", "check_id", "gate_id", "type", "class", "status", "severity"}
_AI = r"(?:ai|assistant|copilot|llm|chatbot|claude|bot|reviewer|review agent)"
_DOC = r"(?:deliverable|draft|report|document|section|packet|memo|deck|finding|findings|assertion|assertions|claim|claims)"
_CONTACT = (r"(?:[a-z0-9._%+-]+\s*(?:@|\(at\)|\[at\])\s*[a-z0-9-]+(?:\s*(?:\.|\(dot\)|\[dot\])\s*[a-z0-9-]+)+"
            r"|https?://|www\.)")
# Deliverable prose about a client's business (AI adoption, reviews, reporting) is normal; these
# patterns target text that addresses the reviewer/assistant or tries to steer THIS review
# (quality-gate-criteria.md #8.1-#8.3). Scanned after Unicode Cf stripping and NFKC folding.
INSTRUCTION_PATTERNS = (
    re.compile(r"\b(?:note|message|instruction|instructions|reminder)s?\s+(?:to|for)\s+(?:the\s+)?" + _AI + r"\b"),
    re.compile(r"\b(?:hey|hi|dear|attention|attn)\s+(?:the\s+)?" + _AI + r"\b"),
    re.compile(r"\b" + _AI + r"\s*[:,]\s*(?:please\s+)?(?:treat|mark|approve|clear|pass|ignore|skip|accept|release|"
               r"consider|do not|don't|dont|this|these|it)\b"),
    re.compile(r"\b" + _AI + r"\s+(?:should|must|needs to|please|can|will)\s+(?:not\s+)?(?:flag|approve|clear|pass|ignore|"
               r"mark|treat|skip|release|accept)\s+(?:this|these|it|the\s+" + _DOC + r")\b"),
    re.compile(r"\b(?:ignore|disregard|override|bypass|skip)\b.{0,30}\b(?:previous instructions|prior instructions|"
               r"(?:the |these |your |all )?instructions|quality gate|gate criteria|qrm|quality review|this review|"
               r"review findings|the flags?)\b"),
    re.compile(r"\b(?:do not|don't|dont|must not|should not|never|no need to)\s+(?:flag|surface|escalate|hold|block|"
               r"review|check)\s+(?:this|these|it|the\s+" + _DOC + r")\b"),
    re.compile(r"\b(?:pre[- ]?approved|already (?:cleared|approved|reviewed|signed[- ]off)|approved for release|"
               r"cleared for release|release (?:is )?approved|no (?:further )?(?:review|qrm|sign[- ]?off|partner review)"
               r"(?: is)? (?:required|needed))\b"),
    re.compile(r"\b(?:waived?|waives|waiving|exempt(?:ed)?|suspended)\b.{0,40}\b(?:disclaimers?|reliance|limitation language|"
               r"quality gate|qrm|gate criteria|quality (?:rules|criteria|review))\b"),
    re.compile(r"\b(?:disclaimer|reliance|qrm|quality|gate)\s+(?:rules?|requirements?|criteria|language|review)?\s*"
               r"(?:are|is|were|was|have been|has been)\s+(?:waived|suspended|not required|not applicable)\b"),
    re.compile(r"\b(?:treat|mark|consider|record|classify)\s+(?:all|every|each|this|these|the)\s+" + _DOC +
               r"\s+(?:as\s+)?(?:supported|verified|substantiated|cleared|approved|resolved|closed|passed|release ready)\b"),
    re.compile(r"\b(?:forward|send|e-?mail|share|upload|transmit)\s+(?:this|these|it|a copy|the\s+(?:packet|draft|"
               r"deliverable|report|document|file|review))\b.{0,60}" + _CONTACT),
)


class InputError(ValueError):
    """Raised for malformed or unsafe engine input."""

def load_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise InputError(f"could not read input JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON input: {exc}") from exc

def validate_generated_at(value):
    if value is None:
        return None
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError("--generated-at must be an ISO-8601 timestamp") from exc
    return value

def require_contract(payload):
    if not isinstance(payload, dict):
        raise InputError("input must be a JSON object")
    if payload.get("contract_version") != CONTRACT_VERSION:
        raise InputError(f"expected contract {CONTRACT_VERSION}, got {payload.get('contract_version')!r}")
    if not isinstance(payload.get("deliverable"), dict):
        raise InputError("missing required object: deliverable")
    for key in ("assertions", "assertion_mappings", "findings"):
        if key in payload and not isinstance(payload[key], list):
            raise InputError(f"{key} must be an array")

def normalize_text(value):
    without_format = "".join(ch for ch in str(value) if unicodedata.category(ch) != "Cf")
    normalized = unicodedata.normalize("NFKC", without_format).lower()
    normalized = normalized.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", normalized)

def suspicious_instruction(value):
    text = normalize_text(value)
    return any(pattern.search(text) for pattern in INSTRUCTION_PATTERNS)

def collect_scan_text(value, path="$"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in SAFE_STRING_KEYS:
                continue
            if isinstance(child, str) and (key in SCAN_KEYS or path.startswith("$.deliverable") or path.startswith("$.assertions") or path.startswith("$.evidence_set") or path.startswith("$.prior_findings")):
                yield child_path, child
            elif isinstance(child, (dict, list)):
                yield from collect_scan_text(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from collect_scan_text(child, f"{path}[{index}]")

def loc(section="Cover", page=1, paragraph=1, label="Document-level"):
    return {"section": section, "page": page, "paragraph": paragraph, "label": label}

def add_finding(findings, finding_id, gate_id, severity, title, detail, location, criteria_section, confidence, citation):
    if any(existing.get("finding_id") == finding_id for existing in findings):
        return
    if severity not in VALID_SEVERITIES:
        raise InputError(f"{finding_id}: unknown severity {severity!r}")
    findings.append({"finding_id": finding_id, "gate_id": gate_id, "severity": severity, "title": title, "detail": detail, "location": location, "criteria_section": criteria_section, "confidence": confidence, "source": ENGINE, "citation": citation})

def highest_for_gate(findings, gate_id):
    gated = [item for item in findings if item.get("gate_id") == gate_id]
    return "none" if not gated else max((item["severity"] for item in gated), key=lambda sev: SEVERITY_RANK[sev])

def is_third_party_context(deliverable):
    if deliverable.get("third_party_recipient_named"):
        return True
    recipients = " ".join(str(item) for item in deliverable.get("intended_recipients", [])).lower()
    return any(term in recipients for term in THIRD_PARTY_TERMS)

def recipient_list_problem(deliverable):
    if "intended_recipients" not in deliverable:
        return "recipient list is missing"
    recipients = deliverable.get("intended_recipients")
    if not isinstance(recipients, list) or not recipients:
        return "recipient list is empty or malformed"
    joined = " | ".join(str(item) for item in recipients).lower()
    if any(term in joined for term in AMBIGUOUS_RECIPIENT_TERMS):
        return "recipient list is ambiguous"
    return None

def main():
    parser = argparse.ArgumentParser(description="Apply quality-gate compliance checks deterministically.")
    parser.add_argument("--mapped", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args()
    try:
        generated_at = validate_generated_at(args.generated_at)
        payload = load_json(args.mapped)
        require_contract(payload)
        deliverable = payload["deliverable"]
        findings, escalations = list(payload.get("findings", [])), list(payload.get("escalations", []))
        for item in findings:
            if item.get("severity") not in VALID_SEVERITIES:
                raise InputError(f"{item.get('finding_id', '<unknown>')}: unknown severity {item.get('severity')!r}")
        if "criteria_sections" not in payload.get("criteria", {}):
            add_finding(findings, "GC-G1-criteria-register-missing", "G1", RELEASE_BLOCKER, "Criteria register is missing", "The applicable criteria list is absent, so the gate cannot be treated as having no findings.", loc("Criteria register", 1, 1, "Missing criteria"), "quality-gate-criteria.md #1-#8; severity-rules.md #1.1", 0.99, "quality-gate-criteria.md #1-#8; severity-rules.md #1.1")
        if "evidence_set" not in payload:
            add_finding(findings, "GC-G1-evidence-index-missing", "G1", RELEASE_BLOCKER, "Evidence index is missing", "The evidence index is absent, so assertions cannot be treated as supported.", loc("Evidence index", 1, 1, "Missing evidence"), "quality-gate-criteria.md #1.1", 0.99, "quality-gate-criteria.md #1.1; severity-rules.md #1.1")
        if "required_language" not in deliverable:
            add_finding(findings, "GC-G2-required-language-register-missing", "G2", RELEASE_BLOCKER, "Required-language register is missing", "The required-language list is absent; missing is not the same as explicitly empty.", loc("Limitations and reliance", 2, 4, "Required language"), "quality-gate-criteria.md #2.1-#2.3", 0.99, "quality-gate-criteria.md #2.1-#2.3; severity-rules.md #1.1")
        recipient_problem = recipient_list_problem(deliverable)
        if recipient_problem:
            add_finding(findings, "GC-G2-recipient-ambiguity", "G2", RELEASE_BLOCKER, "Recipient list is missing or ambiguous", f"{recipient_problem}; reliance language cannot be confirmed until the allowed recipient set is explicit.", loc("Limitations and reliance", 2, 4, "Recipient list"), "quality-gate-criteria.md #2.2", 0.98, "quality-gate-criteria.md #2.2; severity-rules.md #1.1")
        present_disclaimers = deliverable.get("present_disclaimer_types", [])
        if present_disclaimers is None:
            present_disclaimers = []
        if not isinstance(present_disclaimers, list):
            raise InputError("deliverable.present_disclaimer_types must be an array")
        if is_third_party_context(deliverable) and RELIANCE_RESTRICTION_REQUIRED_FOR_THIRD_PARTY:
            if deliverable.get("required_disclaimer_type") != "reliance_restriction":
                add_finding(findings, "GC-G2-required-disclaimer-wrong", "G2", RELEASE_BLOCKER, "Required disclaimer type is wrong for third-party context", "A third-party recipient or allowed user requires reliance-restriction language.", loc("Limitations and reliance", 2, 4, "Disclaimer block"), "quality-gate-criteria.md #2.2", 0.98, "quality-gate-criteria.md #2.2; severity-rules.md #1.1")
            if "reliance_restriction" not in present_disclaimers:
                add_finding(findings, "GC-G2-reliance-language", "G2", RELEASE_BLOCKER, "Wrong disclaimer for third-party recipient", "A third-party recipient or allowed user is named but reliance-restriction language is absent; a general-advice disclaimer does not satisfy this gate.", loc("Limitations and reliance", 2, 4, "Disclaimer block"), "quality-gate-criteria.md #2.2", 0.98, "quality-gate-criteria.md #2.2; severity-rules.md #1.1")
                escalations.append("G2: third-party recipient context and reliance-restriction language absent - release blocker (quality-gate-criteria.md #2.2)")
        required_language = deliverable.get("required_language", [])
        present_language = deliverable.get("present_language", [])
        if required_language is None:
            required_language = []
        if present_language is None:
            present_language = []
        if not isinstance(required_language, list) or not isinstance(present_language, list):
            raise InputError("deliverable.required_language and deliverable.present_language must be arrays when present")
        for required in required_language:
            if required not in present_language:
                severity = RELEASE_BLOCKER if required == "reliance_restriction" else MUST_FIX
                add_finding(findings, f"GC-G2-missing-{required}", "G2", severity, f"Missing required language: {required}", f"Required language `{required}` is not present in the deliverable.", loc("Limitations and reliance", 2, 4, "Required language"), "quality-gate-criteria.md #2.1-#2.3", 0.94, "quality-gate-criteria.md #2.1-#2.3")
        if CONFIDENTIALITY_MARK_REQUIRED and deliverable.get("confidentiality_marking") != "client confidential":
            add_finding(findings, "GC-G4-confidentiality", "G4", RELEASE_BLOCKER, "Missing client-confidential marking", "Required client-confidential marking is absent from cover/footer.", loc("Cover", 1, 1, "Confidentiality mark"), "quality-gate-criteria.md #4.1", 0.97, "quality-gate-criteria.md #4.1; severity-rules.md #1.1")
        if deliverable.get("client_data_handling") in {"breach", "unknown"}:
            add_finding(findings, "GC-G4-client-data", "G4", RELEASE_BLOCKER, "Client-data handling cannot be confirmed", "Client data handling is breach or unknown.", loc("Appendix", 12, 1, "Client data handling"), "quality-gate-criteria.md #4.2", 0.95, "quality-gate-criteria.md #4.2")
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
        if EMBEDDED_INSTRUCTION_HOLD:
            for hit_index, (path, text) in enumerate((item for item in collect_scan_text(payload) if suspicious_instruction(item[1])), start=1):
                add_finding(findings, f"GC-G8-embedded-instruction-{hit_index}", "G8", RELEASE_BLOCKER, "Embedded instruction or forwarding request found in deliverable data", f"Untrusted field {path} contains instruction-like or forwarding text; it must be treated as data and held for human review.", loc("Embedded instruction", 1, 1, "Data-as-data tripwire"), "quality-gate-criteria.md #8.1-#8.3", 0.99, "quality-gate-criteria.md #8.1-#8.3; severity-rules.md #1.1")
                escalations.append(f"G8: embedded-instruction tripwire in {path} - hold for reviewing partner/QRM (quality-gate-criteria.md #8.1-#8.3)")
                if hit_index >= 5:
                    break
        gate_results = []
        for gate_id, name in GATES.items():
            highest = highest_for_gate(findings, gate_id)
            status = "no_engine_findings" if highest == "none" else "blocked" if highest == RELEASE_BLOCKER else "attention_required"
            gate_results.append({"gate_id": gate_id, "name": name, "status": status, "highest_severity": highest, "finding_count": sum(1 for item in findings if item.get("gate_id") == gate_id), "confidence": 0.95, "source": ENGINE, "citation": f"quality-gate-criteria.md #{gate_id[1]}"})
        payload["findings"], payload["gate_results"], payload["escalations"] = findings, gate_results, escalations
        provenance = payload.setdefault("provenance", {})
        if generated_at:
            provenance["generated_at"] = generated_at
        provenance.setdefault("engines", []).append(f"gate_check/{ENGINE_VERSION}")
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        blockers = sum(1 for item in findings if item["severity"] == RELEASE_BLOCKER)
        must_fix = sum(1 for item in findings if item["severity"] == MUST_FIX)
        advisory = sum(1 for item in findings if item["severity"] == ADVISORY)
        print(f"gate_check: {len(gate_results)} gate(s), blockers={blockers}, must_fix={must_fix}, advisory={advisory} -> {os.path.basename(args.out)}")
        return 0
    except InputError as exc:
        print(f"gate_check input error: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
