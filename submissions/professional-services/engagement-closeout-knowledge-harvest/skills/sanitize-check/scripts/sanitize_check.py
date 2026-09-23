#!/usr/bin/env python3
"""sanitize_check - deterministic confidentiality Govern engine.

Reads and writes ps.engagement-closeout-knowledge-harvest.v1 JSON. The engine decides
HOLD vs release-candidate states; the model may only draft from the governed result.
"""
import argparse
import json
import sys

ENGINE = "engine:sanitize_check"
DIRECT_IDENTIFIER_MARKERS = {"client_name", "client_logo", "client_domain", "site_name", "project_codename"}  # confidentiality-sanitisation-rules.md #1.1
NAMED_PERSON_MARKERS = {"named_individual", "named_person_blame"}  # confidentiality-sanitisation-rules.md #2.1,#2.2
COMMERCIAL_MARKERS = {"pricing", "contract_value", "revenue", "margin", "precise_headcount", "implementation_date"}  # confidentiality-sanitisation-rules.md #3.1
LICENSED_MARKERS = {"licensed_third_party_content", "vendor_screenshot", "benchmark_excerpt"}  # confidentiality-sanitisation-rules.md #4.1
PRODUCT_AGGREGATION_MARKERS = {"third_party_product", "named_vendor"}  # confidentiality-sanitisation-rules.md #4.2
AGGREGATION_MIN_TOKENS = 4  # confidentiality-sanitisation-rules.md #5.1
SANITISATION_CONFIDENCE_FLOOR = 0.80  # confidentiality-sanitisation-rules.md #6.1
DEFAULT_REVIEW_REQUIRED = True  # confidentiality-sanitisation-rules.md #6.2

def marker_set(asset):
    return set(asset.get("confidentiality_markers", [])) | set(asset.get("aggregation_tokens", []))

def finding(target_type, target_id, disposition, clearance_state, reason, citation, confidence):
    return {
        "target_type": target_type,
        "target_id": target_id,
        "disposition": disposition,
        "clearance_state": clearance_state,
        "reason": reason,
        "confidence": confidence,
        "source": ENGINE,
        "citation": citation,
    }

def main():
    parser = argparse.ArgumentParser(description="Govern closeout assets and lessons for confidentiality and aggregation risk.")
    parser.add_argument("--input", required=True, help="lesson_cluster JSON output")
    parser.add_argument("--out", required=True, help="output JSON path")
    args = parser.parse_args()

    payload = json.load(open(args.input, encoding="utf-8"))
    assert payload["contract_version"] == "ps.engagement-closeout-knowledge-harvest.v1", "wrong contract version"

    findings = []
    released_assets = []
    held_assets = []
    candidate_assets = []
    escalations = list(payload.get("escalations", []))

    for asset in payload.get("reusable_asset_shortlist", []):
        markers = marker_set(asset)
        confidence = min(float(asset.get("confidence", 0.0)), 0.93)
        state = "HOLD_NOT_SHORTLISTED"
        disposition = "hold"
        reasons = []
        citations = []

        if asset.get("recommendation") != "shortlist":
            reasons.append("reuse score did not reach shortlist band")
            citations.append("reuse-asset-rubric.md #5.2,#5.3")
        else:
            candidate_assets.append(asset)
            state = "RELEASE_CANDIDATE_SANITISED"
            disposition = "release_candidate"
            citations.append("confidentiality-sanitisation-rules.md #6.2,#7.1")

        if confidence < SANITISATION_CONFIDENCE_FLOOR:
            state = "HOLD_LOW_CONFIDENCE"
            disposition = "hold"
            reasons.append(f"confidence {confidence} below {SANITISATION_CONFIDENCE_FLOOR}")
            citations.append("confidentiality-sanitisation-rules.md #6.1")
        if markers & DIRECT_IDENTIFIER_MARKERS:
            state = "HOLD_REDACTION_REQUIRED"
            disposition = "hold"
            reasons.append("direct client-identifying material present: " + ", ".join(sorted(markers & DIRECT_IDENTIFIER_MARKERS)))
            citations.append("confidentiality-sanitisation-rules.md #1.1")
        if markers & LICENSED_MARKERS:
            state = "HOLD_RIGHTS_UNKNOWN"
            disposition = "hold"
            reasons.append("third-party or licensed material requires rights evidence: " + ", ".join(sorted(markers & LICENSED_MARKERS)))
            citations.append("confidentiality-sanitisation-rules.md #4.1")
        if markers & COMMERCIAL_MARKERS and disposition != "hold":
            state = "RELEASE_CANDIDATE_SANITISED"
            disposition = "release_candidate"
            reasons.append("commercial figures must be banded or removed before review: " + ", ".join(sorted(markers & COMMERCIAL_MARKERS)))
            citations.append("confidentiality-sanitisation-rules.md #3.1")
        if markers & PRODUCT_AGGREGATION_MARKERS and disposition != "hold":
            reasons.append("named product/vendor contributes to aggregation review")
            citations.append("confidentiality-sanitisation-rules.md #4.2")

        if not reasons and disposition == "release_candidate":
            reasons.append("no individual hold marker detected; candidate still requires human review")

        rec = {
            "asset_id": asset["asset_id"],
            "title": asset["title"],
            "reuse_score": asset.get("reuse_score"),
            "clearance_state": state,
            "review_required": DEFAULT_REVIEW_REQUIRED,
            "reason": "; ".join(reasons),
            "confidence": confidence,
            "source": ENGINE,
            "citation": "; ".join(dict.fromkeys(citations)) or "confidentiality-sanitisation-rules.md #6.2",
        }
        findings.append(finding("asset", asset["asset_id"], disposition, state, rec["reason"], rec["citation"], confidence))
        if disposition == "hold":
            held_assets.append(rec)
        elif asset.get("recommendation") == "shortlist":
            released_assets.append(rec)

    aggregation_categories = set()
    aggregation_asset_ids = set()
    for asset in candidate_assets:
        for token in asset.get("aggregation_tokens", []):
            aggregation_categories.add(token)
            aggregation_asset_ids.add(asset["asset_id"])
    if len(aggregation_categories) >= AGGREGATION_MIN_TOKENS:
        reason = (
            f"aggregation risk: {len(aggregation_categories)} identifying token categories across candidate assets "
            f"({', '.join(sorted(aggregation_categories))})"
        )
        citation = "confidentiality-sanitisation-rules.md #5.1,#5.2"
        escalations.append(reason + " - group HOLD (" + citation + ")")
        new_released = []
        for asset in released_assets:
            if asset["asset_id"] in aggregation_asset_ids:
                held = dict(asset)
                held["clearance_state"] = "HOLD_AGGREGATION_RISK"
                held["reason"] = reason
                held["citation"] = citation
                held_assets.append(held)
                findings.append(finding("asset_group", asset["asset_id"], "hold", "HOLD_AGGREGATION_RISK", reason, citation, asset["confidence"]))
            else:
                new_released.append(asset)
        released_assets = new_released

    lessons_for_draft = []
    for item in payload.get("retrospective_inputs", []):
        named = item.get("named_people", [])
        text_lower = item.get("text", "").lower()
        blame = bool(named and any(term in text_lower for term in ["failed", "fault", "blamed", "missed", "caused"]))
        rewrite_required = bool(named or blame)
        guidance = None
        citation = "confidentiality-sanitisation-rules.md #2.1"
        if blame:
            guidance = "Rewrite at role/process level; remove named person and blame attribution."
            citation = "confidentiality-sanitisation-rules.md #2.1,#2.2"
            findings.append(finding("lesson", item["input_id"], "rewrite", "HOLD_PERSONAL_DATA_REWRITE", guidance, citation, min(item.get("confidence", 0.0), 0.91)))
        elif named:
            guidance = "Remove named person; use role-level description."
            findings.append(finding("lesson", item["input_id"], "rewrite", "HOLD_PERSONAL_DATA_REWRITE", guidance, citation, min(item.get("confidence", 0.0), 0.91)))
        lessons_for_draft.append({
            "input_id": item["input_id"],
            "rewrite_required": rewrite_required,
            "rewrite_guidance": guidance,
            "source_text_citation": item.get("citation", "UNCITED"),
            "confidence": min(item.get("confidence", 0.0), 0.91),
            "source": ENGINE,
            "citation": citation if rewrite_required else "lesson-taxonomy.md #4.1",
        })

    overall = "HOLD" if held_assets or any(f["disposition"] in ("hold", "rewrite") for f in findings) else "RELEASE_CANDIDATE_SANITISED"
    payload["sanitisation_report"] = {
        "overall_disposition": overall,
        "findings": findings,
        "governance_note": "Release candidates require human practice review; the engine never clears publication or external use.",
        "source": ENGINE,
        "citation": "confidentiality-sanitisation-rules.md #6.2,#7.1,#7.2",
    }
    payload["released_assets"] = released_assets
    payload["held_assets"] = held_assets
    payload["lessons_for_draft"] = lessons_for_draft
    payload["escalations"] = escalations
    payload["knowledge_record"] = {
        "record_id": f"{payload['engagement']['engagement_id']}-KR-DRAFT",
        "status": "draft_pending_practice_review",
        "title": f"Knowledge record - {payload['engagement']['title']}",
        "engagement_summary_seed": payload["engagement"].get("client_descriptor", "Engagement summary requires review."),
        "reusable_assets": released_assets,
        "held_assets_summary": [{"asset_id": a["asset_id"], "clearance_state": a["clearance_state"], "reason": a["reason"], "citation": a["citation"]} for a in held_assets],
        "lessons": payload.get("lesson_clusters", []),
        "sanitisation_summary": f"{len(released_assets)} release candidate asset(s), {len(held_assets)} held asset(s), {sum(1 for l in lessons_for_draft if l['rewrite_required'])} lesson rewrite(s).",
        "downstream_handoff": {
            "consumer_template": "credential-case-study-assembly",
            "contract_fields": [
                "knowledge_record.reusable_assets",
                "knowledge_record.held_assets_summary",
                "knowledge_record.lessons",
                "sanitisation_report.findings",
                "released_assets[].clearance_state"
            ],
            "handoff_note": "Credential & Case Study Assembly may consume only release-candidate fields and inherits no permission to publish, identify the client, use logos or waive client terms."
        },
        "clearance_state": "DRAFT_NOT_PUBLISHED",
        "confidence": 0.9 if overall != "HOLD" else 0.86,
        "source": ENGINE,
        "citation": "confidentiality-sanitisation-rules.md #6.2; downstream handoff contract"
    }
    payload.setdefault("provenance", {})["engines"] = payload.setdefault("provenance", {}).get("engines", []) + ["sanitize_check/1.0"]
    payload["provenance"]["generated_at"] = payload.get("run_metadata", {}).get("generated_at", "2026-09-23T00:00:00Z")

    json.dump(payload, open(args.out, "w", encoding="utf-8"), indent=2)
    print(f"sanitize_check: {len(released_assets)} release candidate(s), {len(held_assets)} held asset(s), overall={overall}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
