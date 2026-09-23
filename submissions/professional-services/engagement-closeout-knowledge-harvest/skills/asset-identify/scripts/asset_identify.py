#!/usr/bin/env python3
"""asset_identify - deterministic closeout deliverable and reuse scoring engine.

Reads ps.engagement-closeout-knowledge-harvest.v1 JSON and writes JSON. No network,
no model calls, no side effects beyond --out. Constants mirror references/reuse-asset-rubric.md.
"""
import argparse
import json
import sys

ENGINE = "engine:asset_identify"
GENERALISABILITY_WEIGHT = 0.35  # reuse-asset-rubric.md #1.1
EFFORT_WEIGHT = 0.25             # reuse-asset-rubric.md #2.1
SHELF_LIFE_WEIGHT = 0.20         # reuse-asset-rubric.md #3.1
DEPENDENCY_WEIGHT = 0.20         # reuse-asset-rubric.md #4.1
SHORTLIST_SCORE = 70             # reuse-asset-rubric.md #5.1
RETAIN_SCORE = 50                # reuse-asset-rubric.md #5.2
SCORING_CONFIDENCE_FLOOR = 0.70  # reuse-asset-rubric.md #5.1

def shelf_score(months):
    if months >= 18:
        return 100
    if months >= 12:
        return 80
    if months >= 6:
        return 50
    return 20

def asset_score(asset):
    general = asset.get("generalisability", 0) / 5 * 100
    effort = asset.get("effort_to_recreate", 0) / 5 * 100
    shelf = shelf_score(asset.get("shelf_life_months", 0))
    dependency = (5 - asset.get("client_dependency", 5)) / 5 * 100
    return round(
        general * GENERALISABILITY_WEIGHT
        + effort * EFFORT_WEIGHT
        + shelf * SHELF_LIFE_WEIGHT
        + dependency * DEPENDENCY_WEIGHT,
        1,
    )

def recommendation(score, confidence):
    if score >= SHORTLIST_SCORE and confidence >= SCORING_CONFIDENCE_FLOOR:
        return "shortlist"
    if score >= RETAIN_SCORE:
        return "retain_for_internal_reference"
    return "archive_with_engagement"

def main():
    parser = argparse.ArgumentParser(description="Score reusable closeout assets and index final deliverables.")
    parser.add_argument("--input", required=True, help="ps.engagement-closeout-knowledge-harvest.v1 JSON input")
    parser.add_argument("--out", required=True, help="output JSON path")
    args = parser.parse_args()

    payload = json.load(open(args.input, encoding="utf-8"))
    assert payload["contract_version"] == "ps.engagement-closeout-knowledge-harvest.v1", "wrong contract version"

    escalations = list(payload.get("escalations", []))
    deliverable_index = []
    for artifact in payload.get("artifacts", []):
        complete = artifact.get("status") == "complete"
        gap = artifact.get("required", False) and not complete
        if gap:
            escalations.append(
                f"{artifact['artifact_id']}: required deliverable '{artifact['title']}' is {artifact.get('status')} "
                "- closeout gap (reuse-asset-rubric.md #6.1)"
            )
        deliverable_index.append({
            "artifact_id": artifact["artifact_id"],
            "title": artifact["title"],
            "artifact_type": artifact.get("artifact_type", "artifact"),
            "required": bool(artifact.get("required")),
            "status": artifact.get("status"),
            "completeness_gap": gap,
            "owner": artifact.get("owner", ""),
            "confidence": min(float(artifact.get("confidence", 0.0)), 0.99),
            "source": ENGINE,
            "citation": f"{artifact.get('citation', 'UNCITED')}; reuse-asset-rubric.md #6.1",
        })

    shortlist = []
    for asset in payload.get("candidate_assets", []):
        score = asset_score(asset)
        conf = min(float(asset.get("confidence", 0.0)), 0.94)
        rec = recommendation(score, conf)
        rationale = (
            f"generalisability {asset.get('generalisability', 0)}/5; "
            f"effort_to_recreate {asset.get('effort_to_recreate', 0)}/5; "
            f"shelf_life {asset.get('shelf_life_months', 0)} months; "
            f"client_dependency {asset.get('client_dependency', 0)}/5"
        )
        shortlist.append({
            "asset_id": asset["asset_id"],
            "title": asset["title"],
            "asset_type": asset.get("asset_type", "asset"),
            "description": asset.get("description", ""),
            "reuse_score": score,
            "recommendation": rec,
            "reuse_rationale": rationale,
            "confidentiality_markers": asset.get("confidentiality_markers", []),
            "aggregation_tokens": asset.get("aggregation_tokens", []),
            "confidence": conf,
            "source": ENGINE,
            "citation": f"{asset.get('citation', 'UNCITED')}; reuse-asset-rubric.md #1.1,#2.1,#3.1,#4.1,#5.1",
        })

    payload["deliverable_index"] = deliverable_index
    payload["reusable_asset_shortlist"] = shortlist
    payload["escalations"] = escalations
    payload.setdefault("provenance", {})["engines"] = payload.setdefault("provenance", {}).get("engines", []) + ["asset_identify/1.0"]
    payload["provenance"]["generated_at"] = payload.get("run_metadata", {}).get("generated_at", "2026-09-23T00:00:00Z")
    payload["provenance"]["demo_scenario"] = payload.get("run_metadata", {}).get("demo_scenario", "")

    json.dump(payload, open(args.out, "w", encoding="utf-8"), indent=2)
    gaps = sum(1 for d in deliverable_index if d["completeness_gap"])
    shortlisted = sum(1 for a in shortlist if a["recommendation"] == "shortlist")
    print(f"asset_identify: {len(shortlist)} assets scored, {shortlisted} shortlisted, {gaps} deliverable gap(s)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
