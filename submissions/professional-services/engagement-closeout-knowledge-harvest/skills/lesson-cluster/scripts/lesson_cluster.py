#!/usr/bin/env python3
"""lesson_cluster - deterministic lesson clustering engine.

Reads and writes ps.engagement-closeout-knowledge-harvest.v1 JSON. Constants mirror
references/lesson-taxonomy.md. The model drafts prose later; it does not decide clusters.
"""
import argparse
import json
import re
import sys

ENGINE = "engine:lesson_cluster"
ENGINE_VERSION = "lesson_cluster/1.0.3"
CONTRACT = "ps.engagement-closeout-knowledge-harvest.v1"
CLUSTER_KEYWORDS = {
    "delivery-governance": ["governance", "sign-off", "signoff", "decision", "escalation", "scope", "steerco", "owner"],
    "adoption-change": ["training", "adoption", "champion", "communications", "readiness", "change"],
    "data-integration": ["data", "migration", "integration", "environment", "api", "cutover", "defect"],
    "commercial-staffing": ["staffing", "budget", "contract", "margin", "partner", "resourcing"],
}
CATEGORY_CITATIONS = {
    "delivery-governance": "lesson-taxonomy.md #1.1",
    "adoption-change": "lesson-taxonomy.md #1.2",
    "data-integration": "lesson-taxonomy.md #1.3",
    "commercial-staffing": "lesson-taxonomy.md #1.4",
    "unclassified": "lesson-taxonomy.md #1.5",
}
HIGH_IMPACT_TERMS = ["blocker", "critical", "delayed", "rework", "executive", "go-live", "golive"]  # lesson-taxonomy.md #2.1
MIN_CLUSTER_CONFIDENCE = 0.70  # lesson-taxonomy.md #3.1
BLAME_PATTERN = re.compile(r"\b(failed|blamed|fault|caused|missed)\b", re.IGNORECASE)  # confidentiality-sanitisation-rules.md #2.2

def category_for(text):
    low = text.lower()
    best = ("unclassified", 0)
    for category, words in CLUSTER_KEYWORDS.items():
        hits = sum(1 for word in words if word in low)
        if hits > best[1]:
            best = (category, hits)
    return best

def main():
    parser = argparse.ArgumentParser(description="Cluster closeout decisions and retrospective lessons.")
    parser.add_argument("--input", required=True, help="asset_identify JSON output")
    parser.add_argument("--out", required=True, help="output JSON path")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as input_file:
        payload = json.load(input_file)
    if payload.get("contract_version") != CONTRACT:
        raise ValueError("wrong contract version")
    for field in ("decision_log", "retrospective_inputs"):
        if not isinstance(payload.get(field), list):
            raise ValueError(f"missing or invalid required array: {field}")

    evidence = []
    for item in payload.get("decision_log", []):
        evidence.append({
            "id": item["decision_id"],
            "kind": "decision",
            "text": item.get("summary", "") + " " + item.get("impact", ""),
            "confidence": item.get("confidence", 0.0),
            "citation": item.get("citation", "UNCITED"),
            "source": item.get("source", "skill:artifact-assemble"),
            "named_people": [],
        })
    for item in payload.get("retrospective_inputs", []):
        evidence.append({
            "id": item["input_id"],
            "kind": "retrospective",
            "text": item.get("text", ""),
            "confidence": item.get("confidence", 0.0),
            "citation": item.get("citation", "UNCITED"),
            "source": item.get("source", "skill:artifact-assemble"),
            "named_people": item.get("named_people", []),
        })

    grouped = {}
    for ev in evidence:
        category, hits = category_for(ev["text"])
        grouped.setdefault(category, []).append((ev, hits))

    clusters = []
    for category in sorted(grouped):
        members = grouped[category]
        member_items = [m[0] for m in members]
        text_blob = " ".join(m["text"] for m in member_items).lower()
        impact_hits = sum(1 for term in HIGH_IMPACT_TERMS if term in text_blob)
        priority = min(100, 45 + 10 * impact_hits + 5 * len(member_items))
        keyword_hits = sum(h for _, h in members)
        confidence = round(min(0.95, 0.62 + 0.06 * keyword_hits + 0.03 * len(member_items)), 2)
        sensitivity = []
        for ev in member_items:
            if ev.get("named_people"):
                sensitivity.append({"evidence_id": ev["id"], "signal": "named_person", "citation": "confidentiality-sanitisation-rules.md #2.1"})
            if ev.get("named_people") and BLAME_PATTERN.search(ev["text"]):
                sensitivity.append({"evidence_id": ev["id"], "signal": "named_person_blame", "citation": "confidentiality-sanitisation-rules.md #2.2"})
        clusters.append({
            "category": category,
            "priority_score": priority,
            "review_candidate": confidence < MIN_CLUSTER_CONFIDENCE,
            "evidence_ids": [ev["id"] for ev in member_items],
            "evidence_citations": list(dict.fromkeys(ev["citation"] for ev in member_items)),
            "summary_seed": member_items[0]["text"][:220],
            "sensitivity_signals": sensitivity,
            "confidence": confidence,
            "source": ENGINE,
            "citation": (
                f"{CATEGORY_CITATIONS[category]}; "
                "lesson-taxonomy.md #2.1,#2.2,#3.1"
            ),
        })

    clusters.sort(key=lambda cluster: (-cluster["priority_score"], cluster["category"]))
    for index, cluster in enumerate(clusters, start=1):
        cluster["cluster_id"] = f"LC-{index:03d}"

    payload["lesson_clusters"] = clusters
    payload.setdefault("provenance", {})["engines"] = payload.setdefault("provenance", {}).get("engines", []) + [ENGINE_VERSION]
    payload["provenance"]["generated_at"] = payload.get("run_metadata", {}).get("generated_at", "2026-09-23T00:00:00Z")
    with open(args.out, "w", encoding="utf-8", newline="\n") as output_file:
        json.dump(payload, output_file, indent=2)
    review = sum(1 for c in clusters if c["review_candidate"])
    print(f"lesson_cluster: {len(clusters)} cluster(s), {review} review candidate(s)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
