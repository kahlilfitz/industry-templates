#!/usr/bin/env python3
"""clause_select - deterministic approved clause selector.

Reads scope.json plus a versioned approved clause library and writes selected clauses.
If the library is absent, unversioned or not approved, the engine stops in degraded mode
instead of inventing approved language.

Constants mirror references/approved-clause-library.md and qrm-deviation-rules.md.
"""
import argparse
import json
import sys

ENGINE = "engine:clause_select"
CONTRACT = "ps.sow-drafting-scoping-notes.v1"

APPROVED_LIBRARY_REQUIRED = True     # approved-clause-library.md #1.1
SELECT_BY_LIBRARY_ID_VERSION = True  # approved-clause-library.md #1.2
THIN_BLOCK_STAYS_BLOCKED = True      # qrm-deviation-rules.md #4.4

ALWAYS_INCLUDE = [
    "limitation_of_liability",  # approved-clause-library.md #3.1
    "ip_ownership",             # approved-clause-library.md #3.1
    "payment_terms",            # approved-clause-library.md #3.1
    "termination",              # approved-clause-library.md #3.1
    "warranty_disclaimer",      # approved-clause-library.md #3.1
    "change_control",           # approved-clause-library.md #3.1
]


def degraded(payload, out, reason):
    payload["governance_mode"] = "degraded_extraction_only"
    payload["selected_clauses"] = []
    payload.setdefault("escalations", []).append(reason)
    payload.setdefault("provenance", {}).setdefault("engines", []).append("clause_select/1.0")
    payload["provenance"]["generated_at"] = payload.get("generated_at", "2026-09-23T21:27:10+00:00")
    json.dump(payload, open(out, "w", encoding="utf-8"), indent=2)
    print(f"clause_select: degraded extraction-only - {reason} -> {out}", file=sys.stderr)
    return 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", required=True)
    ap.add_argument("--library", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    payload = json.load(open(args.scope, encoding="utf-8"))
    assert payload["contract_version"] == CONTRACT, "wrong contract version"

    try:
        library = json.load(open(args.library, encoding="utf-8"))
    except OSError:
        return degraded(payload, args.out, "approved clause library absent - Govern step disabled (approved-clause-library.md #1.1)")

    if not library.get("version") or library.get("approval_status") != "approved":
        return degraded(payload, args.out, "approved clause library absent, unversioned or not approved - Govern step disabled (approved-clause-library.md #1.1)")

    by_family = {clause["family"]: clause for clause in library.get("clauses", [])}
    families = list(ALWAYS_INCLUDE)
    if payload.get("scope", {}).get("deliverables"):
        families.append("acceptance")  # approved-clause-library.md #3.2
    thin_commitments = {item["commitment"] for item in payload.get("scope", {}).get("thin_input_report", [])}
    data_present = (
        any("data" in item.get("key", "") for item in payload.get("evidence", []))
        or any(term.get("family") == "data_protection" for term in payload.get("prior_sow_terms", []))
        or "client_test_data" in thin_commitments
    )
    if data_present:
        families.append("data_protection")  # approved-clause-library.md #3.3

    selected = []
    for family in families:
        clause = by_family.get(family)
        if not clause:
            return degraded(payload, args.out, f"approved clause missing for {family} - Govern step disabled (approved-clause-library.md #1.2)")
        blocked = (
            family == "acceptance" and "acceptance" in thin_commitments
        ) or (
            family == "data_protection" and "client_test_data" in thin_commitments
        )
        selected.append({
            "family": family,
            "library_id": clause["library_id"],
            "library_version": library["version"],
            "title": clause["title"],
            "risk_tier": clause["risk_tier"],
            "approved_clause": clause["approved_clause"],
            "draft_allowed": not blocked,
            "deviation_state": "thin_input_blocked" if blocked else "approved_language_selected",
            "source": ENGINE,
            "citation": clause["citation"],
            "confidence": 0.99,
        })

    payload["clause_library"] = {
        "library_id": library.get("library_id", ""),
        "version": library["version"],
        "approval_status": library["approval_status"],
        "source": ENGINE,
        "citation": library.get("citation", "approved-clause-library.md #1.1"),
        "confidence": 0.99,
    }
    payload["selected_clauses"] = selected
    payload.setdefault("provenance", {}).setdefault("engines", []).append("clause_select/1.0")
    payload["provenance"]["generated_at"] = payload.get("generated_at", "2026-09-23T21:27:10+00:00")

    json.dump(payload, open(args.out, "w", encoding="utf-8"), indent=2)
    blocked_count = sum(1 for clause in selected if not clause["draft_allowed"])
    print(f"clause_select: {len(selected)} approved clause(s), {blocked_count} thin-input block(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
