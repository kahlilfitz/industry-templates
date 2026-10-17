#!/usr/bin/env python3
"""credential_draft - deterministic taxonomy match engine.

Reads a closeout knowledge record and writes the structured credential draft hop for
ps.credential-case-study-assembly.v1. The model drafts copy from this structure; it
never computes the taxonomy match.

Constants mirror references/credential-taxonomy.md by section number.
"""
import argparse
import json
import sys

ENGINE = "engine:credential_draft"
CONTRACT_VERSION = "ps.credential-case-study-assembly.v1"
TAXONOMY_CONFIDENCE_FLOOR = 0.72  # credential-taxonomy.md #6.1
AMBIGUITY_DELTA = 0.05  # credential-taxonomy.md #6.3
SIZE_SMALL_MAX_FEES = 250000  # credential-taxonomy.md #4.1
SIZE_MEDIUM_MAX_FEES = 1000000  # credential-taxonomy.md #4.2
SIZE_LARGE_MAX_FEES = 5000000  # credential-taxonomy.md #4.3
SIZE_STRATEGIC_MIN_WEEKS = 52  # credential-taxonomy.md #4.4

SECTOR_HINTS = {
    "financial-services": ["bank", "insurance", "insurer", "assurance", "payments", "wealth"],  # credential-taxonomy.md #1
    "public-sector": ["government", "agency", "municipality", "public service"],  # credential-taxonomy.md #1
    "healthcare": ["provider", "payer", "hospital", "clinical"],  # credential-taxonomy.md #1
    "industrial": ["manufacturing", "energy", "logistics", "field"],  # credential-taxonomy.md #1
    "technology-media-telecom": ["software", "platform", "media", "telecom"],  # credential-taxonomy.md #1
    "cross-industry": ["corporate", "shared service", "horizontal"],  # credential-taxonomy.md #1
}
SERVICE_LINE_HINTS = {
    "strategy-advisory": ["strategy", "operating model", "roadmap", "business case"],  # credential-taxonomy.md #2
    "technology-transformation": ["platform", "migration", "implementation", "integration"],  # credential-taxonomy.md #2
    "data-ai-analytics": ["data", "analytics", "ai", "automation", "insights"],  # credential-taxonomy.md #2
    "risk-regulatory": ["compliance", "controls", "audit", "regulatory"],  # credential-taxonomy.md #2
    "managed-services": ["managed service", "operate", "run", "support"],  # credential-taxonomy.md #2
}
CAPABILITY_HINTS = {
    "process-redesign": ["process", "workflow", "standardisation", "operating model"],  # credential-taxonomy.md #3
    "platform-migration": ["migration", "core platform", "legacy replacement"],  # credential-taxonomy.md #3
    "ai-automation": ["automation", "ai", "copilot", "intelligent workflow"],  # credential-taxonomy.md #3
    "data-modernisation": ["lakehouse", "warehouse", "data foundation", "reporting"],  # credential-taxonomy.md #3
    "change-enablement": ["adoption", "training", "communications", "stakeholder"],  # credential-taxonomy.md #3
}
OUTCOME_HINTS = {
    "cost-reduction": ["cost", "spend", "savings", "productivity"],  # credential-taxonomy.md #5
    "cycle-time": ["time", "speed", "throughput", "processing time", "cycle"],  # credential-taxonomy.md #5
    "risk-reduction": ["risk", "control", "compliance", "audit"],  # credential-taxonomy.md #5
    "revenue-growth": ["revenue", "conversion", "sales", "retention"],  # credential-taxonomy.md #5
    "experience-improvement": ["customer", "employee", "satisfaction", "nps"],  # credential-taxonomy.md #5
    "resilience-quality": ["resilience", "quality", "defect", "reliability"],  # credential-taxonomy.md #5
}


def text_blob(payload):
    parts = [
        payload.get("engagement", {}).get("name", ""),
        payload.get("client", {}).get("sector", ""),
        payload.get("client", {}).get("size_descriptor", ""),
    ]
    for item in payload.get("deliverables", []):
        parts.append(item.get("title", ""))
        parts.append(item.get("summary", ""))
    for item in payload.get("outcomes", []):
        parts.append(item.get("metric", ""))
        parts.append(str(item.get("value", "")))
        parts.append(item.get("unit", ""))
    return " ".join(parts).lower()


def score_hints(blob, hints, preferred=None):
    scores = {}
    for value, words in hints.items():
        score = sum(1 for word in words if word in blob)
        if preferred and preferred == value:
            score += 2
        scores[value] = score
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    best, best_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0
    confidence = 0.55 + min(best_score, 5) * 0.09
    if best_score == 0:
        best, confidence = "cross-industry", 0.55
    confidence = round(min(confidence, 0.97), 2)
    ambiguous = best_score > 0 and best_score == second_score and second_score > 0
    return {
        "value": best,
        "confidence": confidence,
        "source": ENGINE,
        "citation": "credential-taxonomy.md",
        "ambiguous": ambiguous,
        "scores": scores,
    }


def size_band(engagement):
    fees = float(engagement.get("fees_usd") or 0)
    weeks = int(engagement.get("duration_weeks") or 0)
    board_visible = bool(engagement.get("board_visible", False))
    if fees >= SIZE_LARGE_MAX_FEES or weeks >= SIZE_STRATEGIC_MIN_WEEKS or board_visible:
        value, citation = "strategic", "credential-taxonomy.md #4.4"
    elif fees >= SIZE_MEDIUM_MAX_FEES or weeks >= 26:
        value, citation = "large", "credential-taxonomy.md #4.3"
    elif fees >= SIZE_SMALL_MAX_FEES or weeks >= 8:
        value, citation = "medium", "credential-taxonomy.md #4.2"
    else:
        value, citation = "small", "credential-taxonomy.md #4.1"
    return {
        "value": value,
        "confidence": 0.96,
        "source": ENGINE,
        "citation": citation,
        "fees_usd": fees,
        "duration_weeks": weeks,
    }


def enrich_match(match, section):
    match["citation"] = f"credential-taxonomy.md #{section}"
    return match


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--closeout", required=True, help="closeout knowledge record JSON")
    parser.add_argument("--out", required=True, help="output draft JSON")
    args = parser.parse_args()

    payload = json.load(open(args.closeout, encoding="utf-8"))
    if payload.get("contract_version") != CONTRACT_VERSION:
        raise AssertionError("wrong contract version")

    blob = text_blob(payload)
    preferred_sector = payload.get("client", {}).get("sector")
    taxonomy = {
        "sector": enrich_match(score_hints(blob, SECTOR_HINTS, preferred_sector), "1"),
        "service_line": enrich_match(score_hints(blob, SERVICE_LINE_HINTS), "2"),
        "capability": enrich_match(score_hints(blob, CAPABILITY_HINTS), "3"),
        "engagement_size_band": size_band(payload.get("engagement", {})),
        "outcome_type": enrich_match(score_hints(blob, OUTCOME_HINTS), "5"),
        "source": ENGINE,
        "citations": ["credential-taxonomy.md #1-#6"],
    }

    confidences = [
        taxonomy["sector"]["confidence"],
        taxonomy["service_line"]["confidence"],
        taxonomy["capability"]["confidence"],
        taxonomy["engagement_size_band"]["confidence"],
        taxonomy["outcome_type"]["confidence"],
    ]
    taxonomy["confidence"] = round(min(confidences), 2)
    escalations = []
    for key in ["sector", "service_line", "capability", "outcome_type"]:
        if taxonomy[key]["confidence"] < TAXONOMY_CONFIDENCE_FLOOR:
            escalations.append(
                f"{key}: confidence {taxonomy[key]['confidence']} below {TAXONOMY_CONFIDENCE_FLOOR}; taxonomy owner review required (credential-taxonomy.md #6.2)"
            )
        if taxonomy[key].get("ambiguous"):
            escalations.append(
                f"{key}: competing taxonomy hints within ambiguity band {AMBIGUITY_DELTA}; confirm match (credential-taxonomy.md #6.3)"
            )
    taxonomy["escalations"] = escalations

    payload["taxonomy_match"] = taxonomy
    payload.setdefault("draft_assets", {})
    payload["draft_assets"].update({
        "credential_entry": {
            "title_seed": payload.get("engagement", {}).get("name", ""),
            "client_name_seed": payload.get("client", {}).get("name", ""),
            "taxonomy": {
                "sector": taxonomy["sector"]["value"],
                "service_line": taxonomy["service_line"]["value"],
                "capability": taxonomy["capability"]["value"],
                "engagement_size_band": taxonomy["engagement_size_band"]["value"],
                "outcome_type": taxonomy["outcome_type"]["value"],
            },
            "source": ENGINE,
            "confidence": taxonomy["confidence"],
            "citations": ["credential-taxonomy.md #1-#6"],
        },
        "case_study": {
            "forms_required": ["short", "medium", "long"],
            "copy_instruction": "Model drafts copy only after permission_check separates cleared and uncleared figures.",
            "source": ENGINE,
            "confidence": taxonomy["confidence"],
            "citations": ["credential-taxonomy.md #6.1"],
        },
        "source": ENGINE,
        "confidence": taxonomy["confidence"],
        "citations": ["credential-taxonomy.md #1-#6"],
    })
    payload.setdefault("provenance", {}).setdefault("engines", []).append("credential_draft/1.0")
    payload["provenance"]["generated_at"] = payload.get("request", {}).get("requested_on", payload["provenance"].get("generated_at", ""))

    json.dump(payload, open(args.out, "w", encoding="utf-8"), indent=2)
    print(
        "credential_draft: "
        f"sector={taxonomy['sector']['value']}, service_line={taxonomy['service_line']['value']}, "
        f"capability={taxonomy['capability']['value']}, size={taxonomy['engagement_size_band']['value']}, "
        f"outcome={taxonomy['outcome_type']['value']} -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
