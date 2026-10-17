#!/usr/bin/env python3
"""entity_resolve - deterministic entity matching and corporate-family expansion.

Reads intake JSON and a corporate-structure JSON export, writes the
ps.conflicts-independence-precheck.v1 resolved-entity hop. No network, no model calls,
no randomness. Constants mirror references/entity-resolution-rules.md by section.
"""
import argparse
import difflib
import json
import re
import sys

ENGINE = "engine:entity_resolve"
AUTO_MATCH_THRESHOLD = 0.92  # entity-resolution-rules.md #4.1
REVIEW_BAND_FLOOR = 0.78  # entity-resolution-rules.md #4.2
AFFILIATE_OWNERSHIP_THRESHOLD = 0.50  # entity-resolution-rules.md #5.1; conflicts-independence-rules.md #3.1
LEGAL_SUFFIXES = {
    "inc", "incorporated", "llc", "l.l.c", "ltd", "limited", "plc", "corp",
    "corporation", "co", "company", "gmbh", "sa", "s.a", "bv", "b.v"
}  # entity-resolution-rules.md #2.1


def normalize(name):
    value = name.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    tokens = [t for t in value.split() if t not in LEGAL_SUFFIXES]
    return " ".join(tokens)


def variants_for(name):
    base = normalize(name)
    variants = {name.strip(), base}
    if " dba " in name.lower():
        variants.add(name.lower().split(" dba ", 1)[1].strip())
    return [v for v in variants if v]


def candidate_names(entity):
    names = [entity["legal_name"]]
    names.extend(entity.get("aliases", []))
    names.extend(entity.get("trade_names", []))
    names.extend(entity.get("transliterations", []))
    return names


def score_name(given, candidate):
    ng, nc = normalize(given), normalize(candidate)
    if ng == nc:
        return 1.0
    ratio = difflib.SequenceMatcher(None, ng, nc).ratio()
    gt, ct = set(ng.split()), set(nc.split())
    if gt and ct:
        ratio = max(ratio, len(gt & ct) / len(gt | ct))
    return round(ratio, 4)


def best_match(name, entities):
    best = None
    for entity in entities:
        controlled = []
        for candidate in candidate_names(entity):
            score = score_name(name, candidate)
            controlled.append((score, candidate))
        score, matched_name = max(controlled, key=lambda x: x[0])
        if not best or score > best["score"]:
            best = {"entity": entity, "score": score, "matched_name": matched_name}
    return best


def family_for(entity, entities):
    family_id = entity.get("family_id")
    if not family_id:
        return []
    members = []
    for candidate in entities:
        if candidate.get("family_id") != family_id:
            continue
        ownership = float(candidate.get("ownership_pct", 1.0 if candidate.get("parent_id") is None else 0.0))
        if candidate["entity_id"] == entity["entity_id"] or ownership >= AFFILIATE_OWNERSHIP_THRESHOLD or candidate.get("parent_id") is None:
            members.append({
                "entity_id": candidate["entity_id"],
                "legal_name": candidate["legal_name"],
                "relationship": candidate.get("relationship", "family member"),
                "ownership_pct": ownership,
                "source": "connector:corporate-structure",
                "citation": candidate.get("citation", "corporate-structure extract"),
                "rule": "entity-resolution-rules.md #5.1"
            })
    return sorted(members, key=lambda m: (m["relationship"], m["legal_name"]))


def ultimate_parent(entity, entities):
    by_id = {e["entity_id"]: e for e in entities}
    current = entity
    seen = set()
    while current.get("parent_id") and current["parent_id"] not in seen and current["parent_id"] in by_id:
        seen.add(current["entity_id"])
        current = by_id[current["parent_id"]]
    return current


def resolve_party(party, entities):
    best = best_match(party["given_name"], entities)
    score = best["score"] if best else 0.0
    entity = best["entity"] if best else None
    if score >= AUTO_MATCH_THRESHOLD:
        status = "controlled_match" if score == 1.0 else "fuzzy_match"
        parent = ultimate_parent(entity, entities)
        family = family_for(entity, entities)
        variants = set(variants_for(party["given_name"]))
        for name in candidate_names(entity):
            variants.add(name)
            variants.add(normalize(name))
        for member in family:
            variants.add(member["legal_name"])
            variants.add(normalize(member["legal_name"]))
        return {
            "party_id": party["party_id"],
            "given_name": party["given_name"],
            "role": party.get("role", ""),
            "match_status": status,
            "resolved_entity_id": entity["entity_id"],
            "resolved_legal_name": entity["legal_name"],
            "candidate_entity_id": entity["entity_id"],
            "candidate_legal_name": entity["legal_name"],
            "family_id": entity.get("family_id"),
            "ultimate_parent_id": parent["entity_id"],
            "ultimate_parent_name": parent["legal_name"],
            "entity_variants_tried": sorted(v for v in variants if v),
            "corporate_family": family,
            "confidence": score,
            "source": ENGINE,
            "citation": f"{entity.get('citation', 'corporate-structure extract')} matched '{best['matched_name']}'",
            "rule": "entity-resolution-rules.md #3.1,#4.1,#5.1"
        }
    if score >= REVIEW_BAND_FLOOR:
        return {
            "party_id": party["party_id"],
            "given_name": party["given_name"],
            "role": party.get("role", ""),
            "match_status": "human_review",
            "resolved_entity_id": None,
            "resolved_legal_name": None,
            "candidate_entity_id": entity["entity_id"],
            "candidate_legal_name": entity["legal_name"],
            "family_id": None,
            "ultimate_parent_id": None,
            "ultimate_parent_name": None,
            "entity_variants_tried": sorted(set(variants_for(party["given_name"]))),
            "corporate_family": [],
            "confidence": score,
            "source": ENGINE,
            "citation": f"candidate {entity['legal_name']} from {entity.get('citation', 'corporate-structure extract')}",
            "rule": "entity-resolution-rules.md #4.2,#7.2"
        }
    return {
        "party_id": party["party_id"],
        "given_name": party["given_name"],
        "role": party.get("role", ""),
        "match_status": "no_match",
        "resolved_entity_id": None,
        "resolved_legal_name": None,
        "candidate_entity_id": entity["entity_id"] if entity else None,
        "candidate_legal_name": entity["legal_name"] if entity else None,
        "family_id": None,
        "ultimate_parent_id": None,
        "ultimate_parent_name": None,
        "entity_variants_tried": sorted(set(variants_for(party["given_name"]))),
        "corporate_family": [],
        "confidence": score,
        "source": ENGINE,
        "citation": "no controlled match in corporate-structure extract",
        "rule": "entity-resolution-rules.md #4.3,#7.2"
    }


def main():
    parser = argparse.ArgumentParser(description="Resolve party names and corporate families for conflicts pre-check.")
    parser.add_argument("--intake", required=True)
    parser.add_argument("--corporate-structure", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    payload = json.load(open(args.intake, encoding="utf-8"))
    corp = json.load(open(args.corporate_structure, encoding="utf-8"))
    assert payload["contract_version"] == "ps.conflicts-independence-precheck.v1", "wrong contract version"
    entities = corp.get("entities", [])
    parties = [payload["prospective_client"]] + payload.get("parties", [])
    resolved = [resolve_party(p, entities) for p in parties]
    variants_by_party = {r["party_id"]: r["entity_variants_tried"] for r in resolved}
    family_ids = sorted({
        member["entity_id"]
        for r in resolved
        for member in r.get("corporate_family", [])
        if r["match_status"] in ("controlled_match", "fuzzy_match")
    })
    unresolved = [r["party_id"] for r in resolved if r["match_status"] in ("human_review", "no_match")]
    escalations = list(payload.get("escalations", []))
    for r in resolved:
        if r["match_status"] == "human_review":
            escalations.append(
                f"{r['given_name']}: candidate {r['candidate_legal_name']} scored {r['confidence']} in the forced human-review band; not treated as resolved (entity-resolution-rules.md #4.2)"
            )
    payload["resolved_entities"] = resolved
    payload["search_scope"] = {
        "registers_searched": [],
        "date_range": corp.get("date_range", {}),
        "entity_variants_by_party": variants_by_party,
        "corporate_family_entity_ids": family_ids,
        "unresolved_parties": unresolved,
        "source": ENGINE,
        "citation": corp.get("citation", "corporate-structure extract")
    }
    payload["escalations"] = escalations
    payload.setdefault("provenance", {}).setdefault("engines", []).append("entity_resolve/1.0")
    payload["provenance"]["generated_at"] = payload.get("analysis_as_of", "")
    json.dump(payload, open(args.out, "w", encoding="utf-8"), indent=2)
    print(f"entity_resolve: {len(resolved)} parties, {len(family_ids)} family entities, {len(unresolved)} unresolved -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
