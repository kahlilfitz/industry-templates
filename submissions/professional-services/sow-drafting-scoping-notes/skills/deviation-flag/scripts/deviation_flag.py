#!/usr/bin/env python3
"""deviation_flag - deterministic QRM deviation engine.

Compares selected approved clauses with requested or inherited prior-SOW terms. The
model writes the narrative; it never approves, downgrades or suppresses the engine's
severity and review route.

Constants mirror references/qrm-deviation-rules.md by section number.
"""
import argparse
import json
import sys

ENGINE = "engine:deviation_flag"
CONTRACT = "ps.sow-drafting-scoping-notes.v1"

DEVIATION_IS_GOVERNANCE = True        # qrm-deviation-rules.md #1.1
ONE_OFF_NOT_PORTABLE = True           # qrm-deviation-rules.md #1.2
HIGH_SENSITIVITY = {                  # qrm-deviation-rules.md #2.1,#2.8
    "limitation_of_liability",
    "data_protection",
}
MEDIUM_SENSITIVITY = {                # qrm-deviation-rules.md #2.2,#2.3,#2.4,#2.5,#2.6
    "acceptance",
    "ip_ownership",
    "payment_terms",
    "termination",
    "warranty_disclaimer",
}
LOW_SENSITIVITY = {"change_control"}  # qrm-deviation-rules.md #2.7
CRITICAL_ROUTE = "QRM + legal + engagement partner"  # qrm-deviation-rules.md #3.1,#3.3
MAJOR_ROUTE = "engagement partner + QRM"             # qrm-deviation-rules.md #3.2
MINOR_ROUTE = "contract manager review"             # qrm-deviation-rules.md #3.4


def severity_for(term):
    family = term["family"]
    material = term.get("material_difference", "none")
    if term.get("one_off_approval") or term.get("client_specific"):
        return "critical", CRITICAL_ROUTE, "qrm-deviation-rules.md #1.2,#3.3"
    if family in HIGH_SENSITIVITY and material != "none":
        return "critical", CRITICAL_ROUTE, "qrm-deviation-rules.md #2.1,#2.8,#3.1"
    if family in MEDIUM_SENSITIVITY and material != "none":
        return "major", MAJOR_ROUTE, "qrm-deviation-rules.md #3.2"
    return "minor", MINOR_ROUTE, "qrm-deviation-rules.md #3.4"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clauses", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    payload = json.load(open(args.clauses, encoding="utf-8"))
    assert payload["contract_version"] == CONTRACT, "wrong contract version"

    selected_by_family = {clause["family"]: clause for clause in payload.get("selected_clauses", [])}
    deviations, escalations = [], list(payload.get("escalations", []))

    for term in payload.get("prior_sow_terms", []):
        if term.get("material_difference", "none") == "none" and not term.get("one_off_approval") and not term.get("client_specific"):
            continue
        clause = selected_by_family.get(term["family"])
        if not clause:
            continue
        severity, route, rule = severity_for(term)
        if clause["deviation_state"] != "thin_input_blocked":
            clause["deviation_state"] = "unapproved_deviation"
        deviations.append({
            "family": term["family"],
            "severity": severity,
            "route": route,
            "deviation_state": "unapproved_deviation",
            "library_id": clause["library_id"],
            "library_version": clause["library_version"],
            "approved_clause": clause["approved_clause"],
            "inherited_clause": term["summary"],
            "rationale": f"Prior SOW term is not portable to this pursuit; {term.get('material_difference', 'material difference from approved language')}.",
            "source": ENGINE,
            "citation": rule,
            "confidence": min(0.99, float(term.get("confidence", 0.99))),
        })
        escalations.append(f"{term['family']}: {severity} deviation inherited from prior SOW - route {route} ({rule})")

    for clause in payload.get("selected_clauses", []):
        if clause["deviation_state"] == "approved_language_selected":
            clause["deviation_state"] = "no_deviation"

    thin_blocks = payload.get("scope", {}).get("thin_input_report", [])
    payload["deviations"] = deviations
    payload["deviation_summary"] = {
        "critical": sum(1 for item in deviations if item["severity"] == "critical"),
        "major": sum(1 for item in deviations if item["severity"] == "major"),
        "minor": sum(1 for item in deviations if item["severity"] == "minor"),
        "thin_input_blocks": len(thin_blocks),
        "requires_qrm_review": any(item["severity"] in ("critical", "major") for item in deviations),
        "source": ENGINE,
        "citation": "qrm-deviation-rules.md #3.1-#3.4,#4.4",
        "confidence": 0.99,
    }
    payload["escalations"] = escalations
    payload.setdefault("provenance", {}).setdefault("engines", []).append("deviation_flag/1.0")
    payload["provenance"]["generated_at"] = payload.get("generated_at", "2026-09-23T21:27:10+00:00")

    json.dump(payload, open(args.out, "w", encoding="utf-8"), indent=2)
    print(f"deviation_flag: {len(deviations)} deviation(s), {len(thin_blocks)} thin-input block(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
