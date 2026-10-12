#!/usr/bin/env python3
"""slate_validate - deterministic secondary safety check before drafting.

``validate(governed_payload)`` is the pure engine (no file I/O). The CLI never trusts a supplied
governed.json: it re-derives the governed document from roles.json, bench.json and constraints.json
with the vendored fit_score, slate_rank and constraint_check engines and refuses any difference
(independence-eligibility-rules.md #9.8) before validating the re-derived document.
"""
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import constraint_check
from input_guard import ArgumentParser, InputError, load_json, need, run, same_document, write_json
from safety_text import sanitize_free_text

CONTRACT = "ps.engagement-staffing-bench-match.v1"
ENGINE = "engine:slate_validate"
ENGINE_VERSION = "slate_validate/1.1.5"
SAFE_DISPOSITIONS = {"clear", "resolved", "non_material", "not_applicable"}
BLOCKING_TYPES = {
    "financial_interest",
    "ethical_wall",
    "adverse_matter",
    "prior_client_role",
    "prior_assurance_role",
}
MIN_RECOMMENDABLE_SCORE = 70.0


def merge_unique(*groups):
    merged = []
    seen = set()
    for group in groups:
        for item in group or []:
            text = str(item)
            if text not in seen:
                seen.add(text)
                merged.append(text)
    return merged


def unsafe_sanitized_records(escalations):
    unsafe_roles = set()
    unsafe_candidates = set()
    for escalation in escalations:
        candidate = re.search(
            r"governed_input\.governed_roles\[(\d+)\]\.candidate_slate\[(\d+)\]",
            escalation,
        )
        if candidate:
            unsafe_candidates.add((int(candidate.group(1)), int(candidate.group(2))))
            continue
        role = re.search(
            r"governed_input\.governed_roles\[(\d+)\]",
            escalation,
        )
        if role:
            unsafe_roles.add(int(role.group(1)))
    return unsafe_roles, unsafe_candidates


def normalize_entity_name(name):
    text = re.sub(r"[^a-z0-9 ]", " ", str(name or "").casefold())
    suffixes = {"llc", "inc", "ltd", "plc", "corp", "corporation", "co", "company", "the"}
    return " ".join(word for word in text.split() if word not in suffixes)


def entity_names_match(left, right):
    left_name = normalize_entity_name(left)
    right_name = normalize_entity_name(right)
    if not left_name or not right_name:
        return None
    left_tokens = left_name.split()
    right_tokens = right_name.split()
    if left_tokens == right_tokens:
        return True
    shorter, longer = (
        (left_tokens, right_tokens)
        if len(left_tokens) <= len(right_tokens)
        else (right_tokens, left_tokens)
    )
    width = len(shorter)
    return any(longer[index:index + width] == shorter for index in range(len(longer) - width + 1))


def matches_engagement(item, engagement):
    record_name = item.get("client_name")
    if record_name in (None, ""):
        return None
    affiliates = engagement.get("affiliates", [])
    if isinstance(affiliates, str):
        affiliates = [affiliates]
    comparisons = [
        entity_names_match(record_name, target)
        for target in [engagement.get("client_name"), *affiliates]
    ]
    if any(value is True for value in comparisons):
        return True
    return None if comparisons and all(value is None for value in comparisons) else False


def unexplained_constraints(candidate, engagement=None):
    engagement = engagement or {}
    considered = candidate.get("constraints_considered")
    if not considered:
        return ["constraints_considered[] is missing"]
    problems = []
    register = [
        item
        for item in considered
        if item.get("type") not in {"availability", "availability_evidence"}
    ]
    if not register:
        problems.append("no conflicts-register record considered")
    for item in considered:
        kind = str(item.get("type", "")).strip().casefold()
        disposition = str(item.get("disposition", "")).strip().casefold()
        reason = item.get("reason") or kind or "unexplained constraint"
        if item.get("applies_to_engagement", True) and disposition not in SAFE_DISPOSITIONS:
            problems.append(reason)
        if kind == "conflicts_register_coverage":
            problems.append(reason)
        if kind in BLOCKING_TYPES and disposition == "clear":
            problems.append(f"{kind} cannot be dispositioned as clear")
        if disposition == "not_applicable":
            matched = matches_engagement(item, engagement)
            if matched is True:
                problems.append(f"{kind or 'conflict'} marked not_applicable but matches client or affiliate")
            elif matched is None:
                problems.append(f"{kind or 'conflict'} marked not_applicable cannot be independently verified")
    return merge_unique(problems)


def recommendation_problems(candidate, engagement):
    problems = unexplained_constraints(candidate, engagement)
    eligibility = candidate.get("eligibility", {})
    if eligibility.get("verdict") != "eligible":
        problems.append(
            f"eligibility verdict is {eligibility.get('verdict', '<missing>')}, not eligible"
        )
    try:
        fit_score = float(candidate.get("fit_score"))
    except (TypeError, ValueError):
        fit_score = None
    if fit_score is None:
        problems.append("fit_score is missing or invalid")
    elif fit_score < MIN_RECOMMENDABLE_SCORE:
        problems.append(
            f"fit_score {fit_score:g} is below the {MIN_RECOMMENDABLE_SCORE:g} recommendation floor"
        )
    return merge_unique(problems)


def validate(governed_payload):
    """Secondary safety check of a governed document; returns the validated document. No file I/O.

    The input is never mutated. ``governed_payload`` is expected to be a document this plugin's
    engines produced (the CLI passes the re-derived one), so whole engine markers in it are kept.
    """
    need(isinstance(governed_payload, dict) and governed_payload.get("contract_version") == CONTRACT,
         "governed.json: wrong governed contract (contract_version)")

    safety_escalations = []
    payload = sanitize_free_text(
        governed_payload, "governed_input", safety_escalations, engine_markers_ok=True
    )
    escalations = merge_unique(payload.get("escalations", []), safety_escalations)
    unsafe_roles, unsafe_candidates = unsafe_sanitized_records(safety_escalations)
    gaps = list(payload.get("gaps", []))
    existing_gap_roles = {gap.get("role_id") for gap in gaps}
    engagement = payload.get("engagement") or {}

    for role_index, role in enumerate(payload.get("governed_roles", [])):
        recommended = []
        for candidate_index, candidate in enumerate(role.get("candidate_slate", [])):
            eligibility = candidate.setdefault("eligibility", {})
            unsafe = recommendation_problems(candidate, engagement)
            if (
                role_index in unsafe_roles
                or (role_index, candidate_index) in unsafe_candidates
            ):
                unsafe.append(
                    "instruction-like, mixed-script or format-character text "
                    "was found in the source record"
                )
            if eligibility.get("recommendation_status") == "recommended" and unsafe:
                candidate.pop("final_eligible_rank", None)
                if eligibility.get("verdict") != "ineligible":
                    eligibility["verdict"] = "needs_review"
                eligibility["recommendation_status"] = "not_recommended"
                eligibility["blocking_rule"] = (
                    "independence-eligibility-rules.md #9.1"
                )
                eligibility["reasons"] = merge_unique(
                    eligibility.get("reasons", []),
                    ["secondary validation found inconsistent or unsafe recommendation evidence"],
                    unsafe,
                )
                eligibility["citation"] = (
                    str(eligibility.get("citation", "")).rstrip("; ")
                    + "; fit-scoring-rubric.md #7.2; "
                    "independence-eligibility-rules.md #1.2,#9.1,#9.4"
                ).lstrip("; ")
                candidate["secondary_validation"] = {
                    "status": "withheld",
                    "unresolved_constraints": unsafe,
                    "source": ENGINE,
                    "citation": (
                        "fit-scoring-rubric.md #7.2; "
                        "independence-eligibility-rules.md #1.2,#9.1,#9.4"
                    ),
                }
                escalations.append(
                    f"{role.get('role_id')}: secondary validation withheld "
                    f"{candidate.get('candidate_name', candidate.get('candidate_id'))} - "
                    + "; ".join(unsafe)
                )
                if candidate.get("provisional_rank") == 1:
                    role["top_provisional_candidate_withheld"] = True
            elif eligibility.get("recommendation_status") == "recommended":
                candidate["secondary_validation"] = {
                    "status": "passed",
                    "source": ENGINE,
                    "citation": "independence-eligibility-rules.md #1.2,#9.1",
                }
                recommended.append(candidate)

        for index, candidate in enumerate(recommended, start=1):
            candidate["final_eligible_rank"] = index
        role["recommended_candidates"] = recommended

        if not recommended and role.get("role_id") not in existing_gap_roles:
            gaps.append({
                "role_id": role.get("role_id"),
                "role_title": role.get("role_title"),
                "gap_statement": (
                    f"No candidate is safe to recommend at or above the "
                    f"{MIN_RECOMMENDABLE_SCORE} fit-score floor for {role.get('role_title')}; "
                    "do not pad the slate."
                ),
                "source": ENGINE,
                "confidence": 0.99,
                "citation": (
                    "fit-scoring-rubric.md #7.2; "
                    "independence-eligibility-rules.md #1.2,#7.2,#9.1"
                ),
            })
            existing_gap_roles.add(role.get("role_id"))

    payload["gaps"] = gaps
    payload["escalations"] = merge_unique(escalations)
    provenance = payload.setdefault("provenance", {})
    engines = [
        engine for engine in provenance.get("engines", [])
        if not engine.startswith("slate_validate/")
    ]
    provenance["engines"] = merge_unique(engines, [ENGINE_VERSION])
    return payload


def rederive_governed(roles_payload, bench_payload, constraints_payload):
    """The governed document the plugin's own engines derive from the three raw inputs."""
    ranked = constraint_check.rederive_ranked(roles_payload, bench_payload)
    try:
        return constraint_check.govern(ranked, constraints_payload)
    except SystemExit as error:
        if isinstance(error.code, str):
            raise InputError(error.code) from None
        raise


def _main(argv):
    parser = ArgumentParser(prog="slate_validate.py", description="Deterministic secondary slate validation.")
    parser.add_argument("--roles", required=True)
    parser.add_argument("--bench", required=True)
    parser.add_argument("--constraints", required=True)
    parser.add_argument("--governed", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    roles_payload = load_json(args.roles, "roles.json")
    bench_payload = load_json(args.bench, "bench.json")
    constraints_payload = load_json(args.constraints, "constraints.json")
    governed_payload = load_json(args.governed, "governed.json")
    need(governed_payload.get("contract_version") == CONTRACT,
         "governed.json: wrong governed contract (contract_version)")
    need(constraints_payload.get("contract_version") == CONTRACT,
         "constraints.json: wrong constraints contract (contract_version)")
    expected = rederive_governed(roles_payload, bench_payload, constraints_payload)
    need(same_document(governed_payload, expected),
         "governed.json does not re-derive from roles.json, bench.json and constraints.json "
         "(rule 9.8); re-run constraint-check")
    payload = validate(expected)
    write_json(args.out, payload)
    print(f"slate_validate: {len(payload.get('governed_roles', []))} role(s) -> validated output written")
    return 0


def main(argv=None):
    """CLI entry point: one clean ``error:`` line and exit 2 on any input error, no output file."""
    return run(lambda: _main(argv))


if __name__ == "__main__":
    sys.exit(main())
