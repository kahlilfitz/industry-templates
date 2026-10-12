#!/usr/bin/env python3
"""constraint_check - deterministic staffing eligibility Govern engine.

``govern(ranked_payload, constraints_payload)`` is the pure engine (no file I/O). The CLI never
trusts a supplied ranked.json: it re-derives the ranked document from roles.json and bench.json with
the vendored fit_score and slate_rank engines and refuses any difference
(independence-eligibility-rules.md #9.8) before governing the re-derived document.

``govern`` validates both documents before anything is screened or evaluated: a malformed ranked
document or conflicts register is one clean input error that names a field path, never a value.
The ranked (role-intake) engagement is authoritative; constraints.json may add affiliates but never
move the client. Any screening hit on a candidate's bench, score or conflicts record holds the
candidate for review (#9.6); rules never read a withheld value. Rows for another client are
validated before they are scoped out (#9.9) and are emitted only by position and a fixed label.
"""
import functools
import re
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fit_score
import slate_rank
import steering_guard
from input_guard import (
    ArgumentParser,
    InputError,
    canonical,
    check_confidence,
    check_date,
    check_id,
    duplicate_keys,
    has_marker,
    id_key,
    is_num,
    is_reserved_label,
    load_json,
    need,
    run,
    same_document,
    write_json,
)
from safety_text import HOLD_RULE, ScreeningLog, is_suspect, safe_citation, safe_text, sanitize_free_text

ENGINE = "engine:constraint_check"
ENGINE_VERSION = "constraint_check/1.1.5"
CONTRACT = "ps.engagement-staffing-bench-match.v1"
RULES = "independence-eligibility-rules.md"
CONFIDENCE_FLOOR = 0.75       # independence-eligibility-rules.md #8.1
PRIOR_ROLE_COOLING_DAYS = 365 # independence-eligibility-rules.md #2.1
PRIOR_ROLE_REVIEW_DAYS = 730  # independence-eligibility-rules.md #2.2
DIVEST_REVIEW_DAYS = 30       # independence-eligibility-rules.md #3.2
ADVERSE_REVIEW_DAYS = 180     # independence-eligibility-rules.md #4.2
ASSURANCE_LOOKBACK_DAYS = 730 # independence-eligibility-rules.md #5.1
CAPACITY_REVIEW_BAND = 10.0   # independence-eligibility-rules.md #6.2
MIN_RECOMMENDABLE_SCORE = 70.0 # fit-scoring-rubric.md #7.2
ESCALATION_CAP = 25           # escalations kept per rule; the rest are counted in one summary line
KNOWN_TYPES = {
    "clear",
    "financial_interest",
    "prior_client_role",
    "ethical_wall",
    "adverse_matter",
    "prior_assurance_role",
}
RESOLVED_FI_STATUSES = {"divested", "resolved", "cleared"}
RESOLVED_STATUSES = {"closed", "resolved", "cleared", "inactive"}
CLEAR_STATUSES = {"clear", "cleared"}
FI_STATUSES = {"active"} | RESOLVED_FI_STATUSES
WALL_STATUSES = {"active"} | RESOLVED_STATUSES
DATED_STATUSES = {"active", "open", "closed", "resolved", "cleared", "inactive", "ended", "completed"}
ROLE_TYPES = {"employee", "officer", "board_member"}
# Register row members that are text when present (null reads as absent).
ROW_TEXT_FIELDS = (
    "type", "client_name", "status", "role_type", "process", "end_date", "resolved_date", "source", "citation",
)
# Members a rule reads. A screening hit on one of these means the row is not evaluated at all.
DECISION_FIELDS = {
    "candidate_id", "type", "client_name", "status", "material", "role_type", "process", "end_date",
    "resolved_date",
}
# The ranked slate members a governed slate row carries (B1); engine-owned members are never carried.
CARRIED_KEYS = (
    "candidate_id",
    "candidate_name",
    "fit_score",
    "component_scores",
    "component_citations",
    "availability_context",
    "matched_required_skills",
    "matched_preferred_skills",
    "source",
    "confidence",
    "citation",
    "screening_holds",
    "provisional_rank",
    "rank_source",
    "rank_citation",
)
FOREIGN_LABEL = "another client (name withheld)"
REVIEW_FALLBACK = "conflicts, screening or availability evidence requires independence review"
ENTITY_SUFFIXES = {"llc", "inc", "ltd", "plc", "corp", "corporation", "co", "company", "the"}
_ENGINE_MARKER_DIGEST = re.compile(r"\[FLAGGED: [^\]]*sha256=([0-9a-f]{12})\]")
_ROW_HIT = re.compile(r"^constraints_input\.constraints\[(\d+)\](?:\.([^.\[]+))?")


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

def safe_cite(text):
    return safe_citation(text)

def screened(text, fallback):
    """Composed text is screened before it is written (D22); a hit keeps contract vocabulary only."""
    text = str(text)
    return fallback if is_suspect(text) or has_marker(text) else text

def days_between(start, end):
    return (date.fromisoformat(start) - date.fromisoformat(end)).days

def timing_phrase(days, past_tense="ended"):
    if days < 0:
        return f"extends {-days} days beyond role start"
    return f"{past_tense} {days} days before start"

def normalize_candidate_id(value):
    """One canonical candidate key (rule 9.5); blank or non-string IDs are '' and never match."""
    return id_key(value) or ""

def candidate_register_rows(constraints, candidate_id):
    """(register index, row) for every conflicts-register row of one candidate."""
    key = id_key(candidate_id)
    if key is None:
        return []
    rows = constraints.get("constraints") or []
    return [
        (index, item)
        for index, item in enumerate(rows if isinstance(rows, list) else [])
        if isinstance(item, dict) and id_key(item.get("candidate_id")) == key
    ]

def candidate_constraints(constraints, candidate_id):
    return [item for _index, item in candidate_register_rows(constraints, candidate_id)]

def unknown_constraint_ids(constraints, candidate_ids):
    known = {id_key(candidate_id) for candidate_id in candidate_ids} - {None}
    return [
        item.get("candidate_id", "<blank>")
        for item in constraints.get("constraints", [])
        if id_key(item.get("candidate_id")) not in known
    ]

def unknown_constraint_rows(constraints, candidate_ids):
    """Register positions whose candidate_id is blank or names no ranked candidate (reported by position)."""
    known = {id_key(candidate_id) for candidate_id in candidate_ids} - {None}
    return [
        index
        for index, item in enumerate(constraints.get("constraints") or [])
        if not isinstance(item, dict) or id_key(item.get("candidate_id")) not in known
    ]

def confidence_value(value, default=0.0):
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def materiality_value(item):
    """Only a JSON true or false records materiality (A5a); anything else is not recorded."""
    value = item.get("material")
    return value if isinstance(value, bool) else None

def _text(item, key):
    value = item.get(key)
    return value if isinstance(value, str) else ""

def _valid_date(value):
    if not isinstance(value, str) or len(value) != 10:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True

@functools.lru_cache(maxsize=4096)
def _entity_key(text):
    folded = steering_guard.normalize(canonical(text))
    words = re.sub(r"[\W_]+", " ", folded).split()
    return " ".join(word for word in words if word not in ENTITY_SUFFIXES)

def normalize_entity_name(name):
    """Entity names compare in one canonical form: NFKC, format characters removed, confusables and
    diacritics folded, case-folded, separators and punctuation as spaces, corporate suffixes dropped."""
    if name is None or isinstance(name, bool) or not isinstance(name, (str, int, float)):
        return ""
    return _entity_key(str(name))

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

def _affiliates(engagement):
    affiliates = engagement.get("affiliates", [])
    if isinstance(affiliates, str):
        return [affiliates]
    return affiliates if isinstance(affiliates, list) else []

def applies_to_client(item, engagement):
    """True when the row names the client or a declared affiliate, False when it names another
    entity, None when that cannot be decided reliably. Withheld or blank names are never matched."""
    raw_name = item.get("client_name")
    if not isinstance(raw_name, str) or not raw_name.strip() or is_suspect(raw_name) or has_marker(raw_name):
        return None
    comparisons = [entity_names_match(raw_name, entity) for entity in [engagement.get("client_name"), *_affiliates(engagement)]]
    if any(value is True for value in comparisons):
        return True
    return None if not comparisons or any(value is None for value in comparisons) else False

def same_entity(left, right):
    """One entity after canonical folding; names that fold to nothing compare in canonical form."""
    left_key, right_key = normalize_entity_name(left), normalize_entity_name(right)
    if left_key or right_key:
        return left_key == right_key
    return isinstance(left, str) and isinstance(right, str) and canonical(left) == canonical(right) != ""

def engagement_entity_label(item, engagement):
    name = str(item.get("client_name") or "").strip()
    if not name:
        return "client or declared affiliate"
    if entity_names_match(name, engagement.get("client_name")) is True:
        return f"client '{name}'"
    return f"declared affiliate '{name}'"

def engagement_unsafe(engagement):
    """True when the client or an affiliate name was withheld by screening or is unreadable."""
    names = [engagement.get("client_name"), *_affiliates(engagement)]
    return any(
        not isinstance(name, str) or has_marker(name) or is_suspect(name)
        for name in names
        if name not in (None, "")
    )

def merge_engagement(payload, constraints, escalations):
    """The ranked (role-intake) engagement is authoritative (A18/C1). constraints.json only fills
    members the ranked engagement lacks and adds affiliates; a different client or engagement ID
    is refused, never merged."""
    ranked = payload.get("engagement") or {}
    constrained = constraints.get("engagement") or {}
    if not isinstance(ranked, dict) or not isinstance(constrained, dict):
        sys.exit("engagement context must be an object")
    for key, label in (("client_name", "client_name"), ("engagement_id", "engagement_id")):
        mine, theirs = ranked.get(key), constrained.get(key)
        if mine in (None, "") or theirs in (None, ""):
            continue
        same = (
            same_entity(mine, theirs)
            if key == "client_name"
            else id_key(mine) is not None and id_key(mine) == id_key(theirs)
        )
        if not same:
            sys.exit(
                f"constraints.json: engagement.{label} does not match the ranked (role-intake) engagement; "
                "the ranked engagement is authoritative (rule 9.10)"
            )
    merged = dict(ranked)
    for key, value in constrained.items():
        if value in (None, "", []) or key == "affiliates":
            continue
        if merged.get(key) in (None, ""):
            merged[key] = value
    ranked_affiliates = _affiliates(ranked)
    constrained_affiliates = _affiliates(constrained)
    merged["affiliates"] = merge_unique(ranked_affiliates, constrained_affiliates)
    if ranked_affiliates and not constrained_affiliates:
        escalations.append(
            "engagement affiliates restored from ranked role-intake context; "
            "bench-query must propagate the engagement block unchanged"
        )
    if not str(merged.get("client_name") or "").strip():
        sys.exit("engagement.client_name is required for fail-closed conflict governance")
    if not normalize_entity_name(merged["client_name"]):
        escalations.append(
            "engagement.client_name cannot be normalized to a matchable entity; "
            "all candidates require independence review"
        )
    payload["engagement"] = merged
    constraints["engagement"] = merged
    return merged

def elevate(current, proposed):
    priority = {"eligible": 0, "needs_review": 1, "ineligible": 2}
    return proposed if priority[proposed] > priority[current] else current

def considered_item(item, applies, disposition, reason, default_source="connector:conflicts-register"):
    return {
        "type": _text(item, "type"),
        "client_name": _text(item, "client_name"),
        "status": _text(item, "status"),
        "material": materiality_value(item),
        "role_type": _text(item, "role_type"),
        "process": _text(item, "process"),
        "end_date": _text(item, "end_date"),
        "resolved_date": _text(item, "resolved_date"),
        "applies_to_engagement": applies,
        "disposition": disposition,
        "reason": reason,
        "source": _text(item, "source") or default_source,
        "confidence": confidence_value(item.get("confidence", 1.0)),
        "citation": safe_cite(_text(item, "citation") or "conflicts record"),
    }

def _row_label(index):
    return f"conflicts register row {index + 1}"

def held_item(item, index, reason, rule, default_source):
    """A register row that is not evaluated: no supplied value is repeated, only position and rule."""
    kind = _text(item, "type").strip().casefold()
    return {
        "type": kind if kind in KNOWN_TYPES else "",
        "client_name": "",
        "status": "",
        "material": None,
        "role_type": "",
        "process": "",
        "end_date": "",
        "resolved_date": "",
        "applies_to_engagement": True,
        "disposition": "needs_review",
        "reason": reason,
        "source": default_source,
        "confidence": confidence_value(item.get("confidence", 1.0)),
        "citation": f"{_row_label(index)} ({RULES} {rule})",
    }

def foreign_item(item, index, disposition, reason, default_source):
    """A row for another client: kept by position and a fixed label only (#9.9)."""
    kind = _text(item, "type").strip().casefold()
    status = _text(item, "status").strip().casefold()
    return {
        "type": kind if kind in KNOWN_TYPES else "",
        "client_name": FOREIGN_LABEL,
        "status": status if status in CLEAR_STATUSES | FI_STATUSES | WALL_STATUSES | DATED_STATUSES else "",
        "material": materiality_value(item),
        "role_type": "",
        "process": "",
        "end_date": _text(item, "end_date") if _valid_date(item.get("end_date")) else "",
        "resolved_date": _text(item, "resolved_date") if _valid_date(item.get("resolved_date")) else "",
        "applies_to_engagement": disposition != "not_applicable",
        "disposition": disposition,
        "reason": reason,
        "source": default_source,
        "confidence": confidence_value(item.get("confidence", 1.0)),
        "citation": f"{_row_label(index)} for another client; name and citation withheld ({RULES} #9.9)",
    }

def shape_problems(item):
    """Row members of the wrong JSON type (direct callers; govern() refuses these as input errors)."""
    return [key for key in ROW_TEXT_FIELDS if item.get(key) is not None and not isinstance(item.get(key), str)]

def foreign_row_problems(item):
    """A24/#9.9: a row for another client is validated before it is scoped out."""
    kind = _text(item, "type").strip().casefold()
    status = _text(item, "status").strip().casefold()
    if kind not in KNOWN_TYPES:
        return True
    for key in ("end_date", "resolved_date"):
        if item.get(key) not in (None, "") and not _valid_date(item.get(key)):
            return True
    if kind == "clear":
        return status not in CLEAR_STATUSES
    if kind == "financial_interest":
        if status not in FI_STATUSES or item.get("material") not in (None, True, False):
            return True
        return status == "divested" and not _valid_date(item.get("resolved_date"))
    if kind == "ethical_wall":
        return status not in WALL_STATUSES
    if status and status not in DATED_STATUSES:
        return True
    if kind == "prior_client_role":
        return not _valid_date(item.get("end_date")) or not normalize_role_type(item.get("role_type"))
    if kind == "prior_assurance_role":
        return not _valid_date(item.get("end_date")) or not _text(item, "process").strip()
    return not _valid_date(item.get("end_date"))

def normalize_role_type(value):
    normalized = re.sub(r"[\s-]+", "_", str(value or "").strip().casefold())
    aliases = {
        "board_member": "board_member",
        "board_director": "board_member",
        "director": "board_member",
    }
    return aliases.get(normalized, normalized)

def safe_days_between(start, end):
    try:
        return days_between(start, end)
    except (TypeError, ValueError):
        return None

def _role_start(role, constraints):
    key = id_key(role.get("role_id"))
    for item in constraints.get("roles") or []:
        if isinstance(item, dict) and key is not None and id_key(item.get("role_id")) == key and item.get("start_date"):
            return item.get("start_date")
    return role.get("start_date")


class _Verdict:
    def __init__(self):
        self.verdict = "eligible"
        self.reasons = []
        self.citations = []
        self.considered = []

    def add(self, level, reason, citation, item=None):
        reason = screened(reason, REVIEW_FALLBACK)
        if level != "eligible":
            self.verdict = elevate(self.verdict, level)
        self.reasons.append(reason)
        self.citations.append(citation)
        if item is not None:
            item["reason"] = reason
            self.considered.append(item)


def verdict_for(role, row, constraints, held_rows=None):
    """Evaluate one ranked candidate against the register. ``held_rows`` maps a register index to the
    set of member names a screening hit withheld (``None`` member: the row itself)."""
    held_rows = held_rows or {}
    acc = _Verdict()
    start = _role_start(role, constraints)
    if not start:
        raise ValueError(f"no start_date for role {role.get('role_id', '<unknown>')}")
    engagement = constraints.get("engagement") or {}
    rows = candidate_register_rows(constraints, row.get("candidate_id"))
    default_source = constraints.get("source") if isinstance(constraints.get("source"), str) else ""
    default_source = default_source or "connector:conflicts-register"

    confidence_values = [
        confidence_value(row.get("confidence", 1.0)),
        confidence_value(constraints.get("confidence", 1.0)),
        confidence_value(engagement.get("confidence", 1.0)),
        *[confidence_value(item.get("confidence", 1.0)) for _index, item in rows],
    ]
    lowest_confidence = min(confidence_values)
    if lowest_confidence < CONFIDENCE_FLOOR:
        acc.add("needs_review", f"evidence confidence {lowest_confidence} below {CONFIDENCE_FLOOR}", f"{RULES} #8.1")

    if not normalize_entity_name(engagement.get("client_name")):
        acc.add("needs_review", "engagement client name cannot be matched reliably", f"{RULES} #9.2")
    if engagement_unsafe(engagement):
        acc.add("needs_review", "engagement client or affiliate name was withheld by source screening",
                f"{RULES} #9.2,#9.6")

    if not rows:
        reason = "no conflicts-register record for candidate - clearance cannot be inferred"
        acc.add("needs_review", reason, f"{RULES} #9.4", {
            "type": "conflicts_register_coverage",
            "client_name": engagement.get("client_name", ""),
            "status": "",
            "material": None,
            "role_type": "",
            "process": "",
            "end_date": "",
            "resolved_date": "",
            "applies_to_engagement": True,
            "disposition": "needs_review",
            "reason": reason,
            "source": default_source,
            "confidence": confidence_value(constraints.get("confidence", 0.0)),
            "citation": safe_cite(constraints.get("citation") or "conflicts register"),
        })

    for index, item in rows:
        cite = safe_cite(_text(item, "citation") or "conflicts record")
        if index in held_rows:
            fields = held_rows[index]
            reason = "conflicts-register record carries text withheld by source screening"
            acc.add("needs_review", reason, f"{HOLD_RULE}; {_row_label(index)}", {
                "type": "source_screening",
                "applies_to_engagement": True,
                "disposition": "needs_review",
                "reason": reason,
                "citation": f"{_row_label(index)} ({HOLD_RULE})",
            })
            if None in fields or fields & DECISION_FIELDS:
                continue
        if shape_problems(item):
            reason = "conflicts record has a member of the wrong type"
            acc.add("needs_review", reason, f"{RULES} #9.1; {_row_label(index)}",
                    held_item(item, index, reason, "#9.1", default_source))
            continue
        name = _text(item, "client_name")
        if not name.strip():
            reason = "conflicts record does not name the client or affiliate it covers"
            acc.add("needs_review", reason, f"{RULES} #9.1,#9.2; {_row_label(index)}",
                    held_item(item, index, reason, "#9.1,#9.2", default_source))
            continue
        if is_reserved_label(name):
            reason = "conflicts record names an entity with a reserved label form"
            acc.add("needs_review", reason, f"{RULES} #9.7; {_row_label(index)}",
                    held_item(item, index, reason, "#9.7", default_source))
            continue
        applies = applies_to_client(item, engagement)
        if applies is False:
            if foreign_row_problems(item):
                reason = "conflicts-register row for another client is malformed - independence review required"
                acc.add("needs_review", reason, f"{RULES} #9.1,#9.9; {_row_label(index)}",
                        foreign_item(item, index, "needs_review", reason, default_source))
            else:
                acc.considered.append(foreign_item(
                    item, index, "not_applicable",
                    "recorded entity does not match the client or a declared affiliate", default_source,
                ))
            continue
        if applies is None:
            reason = "conflict entity cannot be matched reliably to the client or declared affiliates"
            acc.add("needs_review", reason, f"{RULES} #9.1,#9.2; " + cite,
                    considered_item(item, True, "needs_review", reason, default_source))
            continue
        _evaluate_row(acc, role, item, start, engagement, cite, default_source)

    _evaluate_availability(acc, row)

    holds = row.get("screening_holds")
    if isinstance(holds, list) and holds:
        reason = "bench or score record carries text withheld by source screening"
        acc.add("needs_review", reason, HOLD_RULE, {
            "type": "source_screening",
            "applies_to_engagement": True,
            "disposition": "needs_review",
            "reason": reason,
            "citation": HOLD_RULE,
        })

    if not acc.reasons:
        acc.reasons.append("no blocking independence, conflict or availability constraint found")
        acc.citations.append(f"{RULES} #1.1")

    return acc.verdict, acc.reasons, acc.citations, acc.considered


def _status_check(acc, item, status, cite, default_source):
    """Dated rows decide on dates; a supplied status must still be recognised (A5)."""
    if status and status not in DATED_STATUSES:
        reason = "conflicts record status is not recognised"
        acc.add("needs_review", reason, f"{RULES} #9.1; " + cite,
                considered_item(item, True, "needs_review", reason, default_source))


def _evaluate_row(acc, role, item, start, engagement, cite, default_source):
    kind = _text(item, "type").strip().casefold()
    status = _text(item, "status").strip().casefold()
    materiality = materiality_value(item)

    def review(reason, rules):
        acc.add("needs_review", reason, f"{RULES} {rules}; " + cite,
                considered_item(item, True, "needs_review", reason, default_source))

    def block(reason, rules):
        acc.add("ineligible", reason, f"{RULES} {rules}; " + cite,
                considered_item(item, True, "ineligible", reason, default_source))

    def settle(disposition, reason):
        acc.considered.append(considered_item(item, True, disposition, reason, default_source))

    if kind not in KNOWN_TYPES:
        review("unrecognised conflicts record type - route to independence review", "#1.1,#8.1,#9.1")
    elif kind == "clear":
        if status in CLEAR_STATUSES:
            settle("clear", "conflicts register marks candidate clear")
        else:
            review("clear record status is missing or not recognised", "#9.1")
    elif kind == "financial_interest":
        if status not in RESOLVED_FI_STATUSES and materiality is None:
            review("financial interest materiality not recorded as true or false", "#3.1,#8.1,#9.1")
        elif status not in RESOLVED_FI_STATUSES and materiality:
            block("unresolved material financial interest in " + engagement_entity_label(item, engagement), "#3.1")
        elif status == "divested":
            resolved = item.get("resolved_date")
            if not resolved:
                review("divested financial interest has no resolved_date", "#3.2,#8.1")
            else:
                days = safe_days_between(start, resolved)
                if days is None:
                    review("divested financial interest has an invalid resolved_date", "#3.2,#9.1")
                elif days <= DIVEST_REVIEW_DAYS:
                    review(f"material interest divestment {timing_phrase(days, 'completed')}", "#3.2")
                else:
                    settle("resolved", "divestment completed outside the review window")
        elif status in RESOLVED_FI_STATUSES:
            settle("resolved", "financial interest is resolved or explicitly non-material")
        elif status == "active":
            settle("non_material", "financial interest is resolved or explicitly non-material")
        else:
            review("financial interest status is missing or not recognised", "#9.1,#9.3")
    elif kind == "prior_client_role":
        _status_check(acc, item, status, cite, default_source)
        role_type = normalize_role_type(item.get("role_type"))
        if not item.get("end_date") or not role_type:
            review("prior client role is missing role_type or end_date", "#2.2,#8.1")
        else:
            days = safe_days_between(start, item["end_date"])
            if days is None:
                review("prior client role has an invalid end_date", "#2.2,#9.1")
            elif role_type in ROLE_TYPES and days <= PRIOR_ROLE_COOLING_DAYS:
                block(f"prior {role_type} role at client {timing_phrase(days)}", "#2.1")
            elif days <= PRIOR_ROLE_REVIEW_DAYS:
                review(f"prior client role {timing_phrase(days)}", "#2.2")
            else:
                settle("resolved", "prior role falls outside the review window")
    elif kind == "ethical_wall":
        if status == "active":
            block("active ethical wall involving client", "#4.1")
        elif status in RESOLVED_STATUSES:
            settle("resolved", "ethical wall is recorded as resolved")
        else:
            review("ethical wall status is missing or not recognised", "#4.1,#8.1,#9.1")
    elif kind == "adverse_matter":
        _status_check(acc, item, status, cite, default_source)
        if not item.get("end_date"):
            review("adverse matter has no end_date", "#4.2,#8.1")
        else:
            days = safe_days_between(start, item["end_date"])
            if days is None:
                review("adverse matter has an invalid end_date", "#4.2,#9.1")
            elif days < 0:
                block("adverse matter remains active at role start", "#4.1")
            elif days <= ADVERSE_REVIEW_DAYS:
                review(f"adverse matter support {timing_phrase(days)}", "#4.2")
            else:
                settle("resolved", "adverse matter falls outside the review window")
    elif kind == "prior_assurance_role":
        _status_check(acc, item, status, cite, default_source)
        process = _text(item, "process").strip()
        if not process or not item.get("end_date"):
            review("prior assurance role process or end_date is missing or ambiguous", "#5.2")
        else:
            days = safe_days_between(start, item["end_date"])
            same_process = normalize_entity_name(process) in normalize_entity_name(role.get("title", ""))
            if days is None:
                review("prior assurance role has an invalid end_date", "#5.2,#9.1")
            elif days <= ASSURANCE_LOOKBACK_DAYS and same_process:
                block(f"prior assurance role over same process {timing_phrase(days)}", "#5.1")
            elif days <= ASSURANCE_LOOKBACK_DAYS:
                review(
                    f"prior assurance role over '{process}' {timing_phrase(days)}; "
                    "overlap with role scope not determinable",
                    "#5.2",
                )
            else:
                settle("resolved", "prior assurance role falls outside the lookback window")


def _evaluate_availability(acc, row):
    availability = row.get("availability_context")
    if not isinstance(availability, dict):
        availability = {}
    effective = confidence_value(availability.get("effective_available_pct"), None)
    requested = confidence_value(availability.get("requested_allocation_pct"), None)
    warnings = availability.get("calculation_warnings", [])
    row_cite = safe_cite(row.get("citation") or "fit score record")
    if availability.get("evidence_complete") is False or warnings:
        reason = "availability evidence is incomplete or uses a conservative assumption"
        acc.add("needs_review", reason, f"{RULES} #6.3,#8.1", {
            "type": "availability_evidence",
            "applies_to_engagement": True,
            "disposition": "needs_review",
            "reason": reason,
            "source": row.get("source", "engine:fit_score"),
            "confidence": confidence_value(row.get("confidence", 0.0)),
            "citation": f"{RULES} #6.3,#8.1",
        })
    if effective is None or requested is None:
        reason = "availability calculation is missing effective or requested capacity"
        acc.add("needs_review", reason, f"{RULES} #6.3,#9.1", {
            "type": "availability",
            "applies_to_engagement": True,
            "disposition": "needs_review",
            "reason": reason,
            "citation": row_cite,
        })
    elif effective < requested:
        gap = requested - effective
        if gap > CAPACITY_REVIEW_BAND:
            reason = f"effective available capacity {effective}% is below requested allocation {requested}%"
            acc.add("ineligible", reason, f"{RULES} #6.1; " + row_cite, {
                "type": "availability",
                "applies_to_engagement": True,
                "disposition": "ineligible",
                "reason": reason,
                "citation": row_cite,
            })
        else:
            reason = f"effective capacity {effective}% is within {CAPACITY_REVIEW_BAND} points of requested {requested}%"
            acc.add("needs_review", reason, f"{RULES} #6.2; " + row_cite, {
                "type": "availability",
                "applies_to_engagement": True,
                "disposition": "needs_review",
                "reason": reason,
                "citation": row_cite,
            })
    else:
        acc.considered.append({
            "type": "availability",
            "applies_to_engagement": True,
            "disposition": "clear",
            "reason": "effective available capacity meets requested allocation",
            "citation": row_cite,
        })


def blocking_reason(reasons, citations):
    blocking_rules = ("#2.1", "#3.1", "#4.1", "#5.1", "#6.1")
    for reason, citation in zip(reasons, citations):
        if any(rule in citation.split(";", 1)[0] for rule in blocking_rules):
            return reason, citation.split(";", 1)[0]
    return reasons[0], citations[0].split(";", 1)[0]

def review_reason(reasons, citations):
    review_rules = (
        "#9.6",
        "#9.7",
        "#2.2",
        "#3.2",
        "#4.2",
        "#5.2",
        "#6.2",
        "#6.3",
        "#9.1",
        "#9.2",
        "#9.9",
        "#9.4",
        "#8.1",
    )
    for rule in review_rules:
        for reason, citation in zip(reasons, citations):
            if rule in citation.split(";", 1)[0]:
                return reason, citation.split(";", 1)[0]
    return reasons[0], citations[0].split(";", 1)[0]


# ---------------------------------------------------------------------------------------------
# Input validation (A1/A2/A7/A12/A18/A21/C1/C5/D17/D20/D23/D25; rules 9.5, 9.7, 9.8).
# Messages name field paths only; values and file paths are never echoed.
# ---------------------------------------------------------------------------------------------
def _join(where, key):
    return f"{where} {key}" if where.endswith(":") else f"{where}.{key}"

def _obj(value, path):
    need(isinstance(value, dict), f"{path} must be an object")
    return value

def _list(value, path):
    need(value is not None, f"{path} must not be null")
    need(isinstance(value, list), f"{path} must be an array")
    return value

def _member(obj, key, where, required=True):
    if key not in obj:
        need(not required, f"{_join(where, key)} is required")
        return None
    return obj[key]

def _opt_text(obj, key, where):
    value = obj.get(key)
    need(value is None or isinstance(value, str), f"{_join(where, key)} must be a string")
    return value

def _ident(value, path):
    check_id(value, path)
    need(not is_suspect(value), f"{path} carries instruction-like text (rule 9.7)")
    return value

def _label(value, path, markers_ok=False):
    """A name: a non-blank string that is not a reserved label (an engine marker only when allowed)."""
    need(isinstance(value, str) and value.strip(), f"{path} must be a non-blank string")
    need(not is_reserved_label(value) or (markers_ok and has_marker(value)), f"{path} uses a reserved label form")
    return value

def _escalation_items(document, where, objects_ok):
    if "escalations" not in document:
        return
    items = _list(document["escalations"], _join(where, "escalations"))
    for index, item in enumerate(items):
        need(isinstance(item, str) or (objects_ok and isinstance(item, dict)),
             f"{_join(where, 'escalations')}[{index}] must be a string" + (" or an object" if objects_ok else ""))

def validate_ranked(ranked):
    label = "ranked.json"
    need(isinstance(ranked, dict) and ranked.get("contract_version") == CONTRACT,
         f"{label}: wrong ranked contract (contract_version)")
    engagement = _obj(_member(ranked, "engagement", f"{label}:"), f"{label}: engagement")
    _label(_member(engagement, "client_name", f"{label}: engagement"), f"{label}: engagement.client_name", True)
    if engagement.get("engagement_id") is not None:
        _ident(engagement["engagement_id"], f"{label}: engagement.engagement_id")
    if "affiliates" in engagement:
        for index, affiliate in enumerate(_list(engagement["affiliates"], f"{label}: engagement.affiliates")):
            _label(affiliate, f"{label}: engagement.affiliates[{index}]", True)
    if "confidence" in engagement:
        check_confidence(engagement["confidence"], f"{label}: engagement.confidence")
    roles = _list(_member(ranked, "roles", f"{label}:"), f"{label}: roles")
    need(roles, f"{label}: roles must not be empty")
    for index, role in enumerate(roles):
        where = f"{label}: roles[{index}]"
        _obj(role, where)
        _ident(_member(role, "role_id", where), f"{where}.role_id")
        _label(_member(role, "title", where), f"{where}.title", True)
        check_date(_member(role, "start_date", where), f"{where}.start_date")
    need(not duplicate_keys([role["role_id"] for role in roles]),
         f"{label}: roles repeat a role_id after canonical folding (rule 9.7)")
    role_keys = {id_key(role["role_id"]) for role in roles}
    ranked_roles = _list(_member(ranked, "ranked_roles", f"{label}:"), f"{label}: ranked_roles")
    for r_index, ranked_role in enumerate(ranked_roles):
        where = f"{label}: ranked_roles[{r_index}]"
        _obj(ranked_role, where)
        role_id = _ident(_member(ranked_role, "role_id", where), f"{where}.role_id")
        need(id_key(role_id) in role_keys, f"{where}.role_id is missing from roles")
        _label(_member(ranked_role, "role_title", where), f"{where}.role_title", True)
        slate = _list(_member(ranked_role, "candidate_slate", where), f"{where}.candidate_slate")
        for c_index, candidate in enumerate(slate):
            path = f"{where}.candidate_slate[{c_index}]"
            _obj(candidate, path)
            _ident(_member(candidate, "candidate_id", path), f"{path}.candidate_id")
            _label(_member(candidate, "candidate_name", path), f"{path}.candidate_name", True)
            need(is_num(_member(candidate, "fit_score", path)), f"{path}.fit_score must be a number")
            rank = _member(candidate, "provisional_rank", path)
            need(isinstance(rank, int) and not isinstance(rank, bool) and rank >= 1,
                 f"{path}.provisional_rank must be a positive integer")
            check_confidence(_member(candidate, "confidence", path), f"{path}.confidence")
            if "availability_context" in candidate:
                _obj(candidate["availability_context"], f"{path}.availability_context")
            if "screening_holds" in candidate:
                for h_index, hold in enumerate(_list(candidate["screening_holds"], f"{path}.screening_holds")):
                    need(isinstance(hold, str), f"{path}.screening_holds[{h_index}] must be a string")
            for key in ("source", "citation"):
                _opt_text(candidate, key, path)
        need(not duplicate_keys([candidate["candidate_id"] for candidate in slate]),
             f"{where}.candidate_slate repeats a candidate_id after canonical folding (rule 9.7)")
    need(not duplicate_keys([ranked_role["role_id"] for ranked_role in ranked_roles]),
         f"{label}: ranked_roles repeat a role_id after canonical folding (rule 9.7)")
    _escalation_items(ranked, f"{label}:", objects_ok=False)
    if "provenance" in ranked:
        provenance = _obj(ranked["provenance"], f"{label}: provenance")
        if "engines" in provenance:
            for index, engine in enumerate(_list(provenance["engines"], f"{label}: provenance.engines")):
                need(isinstance(engine, str), f"{label}: provenance.engines[{index}] must be a string")

def validate_constraints(constraints, ranked):
    label = "constraints.json"
    need(isinstance(constraints, dict) and constraints.get("contract_version") == CONTRACT,
         f"{label}: wrong constraints contract (contract_version)")
    ranked_engagement = ranked["engagement"]
    if "engagement" in constraints:
        engagement = _obj(constraints["engagement"], f"{label}: engagement")
        client = _opt_text(engagement, "client_name", f"{label}: engagement")
        if client not in (None, ""):
            _label(client, f"{label}: engagement.client_name")
            need(
                same_entity(client, ranked_engagement["client_name"]),
                f"{label}: engagement.client_name does not match the ranked (role-intake) engagement; "
                "the ranked engagement is authoritative (rule 9.10)",
            )
        engagement_id = engagement.get("engagement_id")
        if engagement_id not in (None, ""):
            _ident(engagement_id, f"{label}: engagement.engagement_id")
            need(id_key(engagement_id) == id_key(ranked_engagement.get("engagement_id")),
                 f"{label}: engagement.engagement_id does not match the ranked (role-intake) engagement; "
                 "the ranked engagement is authoritative (rule 9.10)")
        if "affiliates" in engagement:
            for index, affiliate in enumerate(_list(engagement["affiliates"], f"{label}: engagement.affiliates")):
                _label(affiliate, f"{label}: engagement.affiliates[{index}]")
        if engagement.get("confidence") is not None:
            check_confidence(engagement["confidence"], f"{label}: engagement.confidence")
        for key in ("source", "citation"):
            _opt_text(engagement, key, f"{label}: engagement")
    ranked_starts = {id_key(role["role_id"]): role["start_date"] for role in ranked["roles"]}
    if "roles" in constraints:
        roles = _list(constraints["roles"], f"{label}: roles")
        for index, role in enumerate(roles):
            where = f"{label}: roles[{index}]"
            _obj(role, where)
            role_id = _ident(_member(role, "role_id", where), f"{where}.role_id")
            if role.get("start_date") is not None:
                check_date(role["start_date"], f"{where}.start_date")
                expected = ranked_starts.get(id_key(role_id))
                need(expected is None or expected == role["start_date"],
                     f"{where}.start_date does not match the ranked role start_date (rule 9.10)")
        need(not duplicate_keys([role["role_id"] for role in roles]),
             f"{label}: roles repeat a role_id after canonical folding (rule 9.7)")
    register = _member(constraints, "constraints", f"{label}:")
    need(register is not None, f"{label}: constraints must not be null (an absent register is never clearance)")
    need(isinstance(register, list), f"{label}: constraints must be an array of register rows")
    for index, item in enumerate(register):
        where = f"{label}: constraints[{index}]"
        _obj(item, where)
        _ident(_member(item, "candidate_id", where), f"{where}.candidate_id")
        for key in ROW_TEXT_FIELDS:
            _opt_text(item, key, where)
        if item.get("confidence") is not None:
            check_confidence(item["confidence"], f"{where}.confidence")
    if constraints.get("confidence") is not None:
        check_confidence(constraints["confidence"], f"{label}: confidence")
    for key in ("source", "citation"):
        _opt_text(constraints, key, f"{label}:")
    _escalation_items(constraints, f"{label}:", objects_ok=True)


# ---------------------------------------------------------------------------------------------
# Escalations (A8, B3, D17, D22)
# ---------------------------------------------------------------------------------------------
_HEAD_KEYS = ("id", "escalation_id", "rule", "code")
_BODY_KEYS = ("message", "reason", "text", "summary", "detail")


def normalise_escalation(item, index):
    """A string, or an object rendered as ``head: body`` from its known members (A8). Unknown
    members are never dumped; an object with no readable message is reported by position."""
    if isinstance(item, str):
        return item.strip(), None
    head = next((item[key].strip() for key in _HEAD_KEYS if isinstance(item.get(key), str) and item[key].strip()), "")
    body = next((item[key].strip() for key in _BODY_KEYS if isinstance(item.get(key), str) and item[key].strip()), "")
    if not body:
        return f"constraints escalations[{index}]: escalation object has no readable message; review source record", head or None
    return (f"{head}: {body}" if head else body), head or None


class _Escalations:
    """Escalations in order, de-duplicated, capped per rule key with one summary line each (A8)."""

    def __init__(self):
        self.items = []

    def add(self, text, rule=None):
        self.items.append((str(text), rule))

    def extend(self, texts):
        for text in texts:
            self.add(text)

    def render(self):
        counts, kept, dropped, seen = {}, [], {}, set()
        for text, rule in self.items:
            if text in seen or not text:
                continue
            seen.add(text)
            if rule is not None:
                counts[rule] = counts.get(rule, 0) + 1
                if counts[rule] > ESCALATION_CAP:
                    dropped[rule] = dropped.get(rule, 0) + 1
                    continue
            kept.append(text)
        for rule, count in dropped.items():
            kept.append(
                f"{count} further escalation(s) under {screened(rule, 'one rule')} not listed (cap {ESCALATION_CAP}); "
                "see each candidate's eligibility record"
            )
        return kept


def _seed_engine_markers(log, value, path):
    """B3: text an upstream engine already redacted (the marker carries its digest) is not escalated
    again when the same text arrives at the same field of constraints.json."""
    if isinstance(value, dict):
        for key, item in value.items():
            _seed_engine_markers(log, item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _seed_engine_markers(log, item, f"{path}[{index}]")
    elif isinstance(value, str):
        for match in _ENGINE_MARKER_DIGEST.finditer(value):
            log.keys.add((path, match.group(1)))


def _held_rows(log):
    """Register index -> member names a screening hit withheld (None: the row or a member name)."""
    held = {}
    for path, _kind in log.hits:
        match = _ROW_HIT.match(path)
        if match:
            held.setdefault(int(match.group(1)), set()).add(match.group(2))
    return held


def _foreign_names(raw_constraints, engagement):
    """A16/D12: the other-client names in the raw register, harvested before anything is screened."""
    names = set()
    for item in raw_constraints.get("constraints") or []:
        name = item.get("client_name") if isinstance(item, dict) else None
        if isinstance(name, str) and name.strip() and applies_to_client(item, engagement) is False:
            key = normalize_entity_name(name)
            if key:
                names.add(key)
    return names


def _names_foreign(text, foreign):
    if not foreign or not isinstance(text, str):
        return False
    words = f" {normalize_entity_name(text)} "
    return any(f" {name} " in words for name in foreign)


def govern(ranked_payload, constraints_payload):
    """Apply the independence and eligibility rules; returns the governed document. No file I/O.

    The inputs are never mutated. ``ranked_payload`` is expected to be a document this plugin's
    engines produced (the CLI passes the re-derived one), so whole engine markers in it are kept.
    Both documents are validated first; any malformed member is an InputError naming its path.
    """
    validate_ranked(ranked_payload)
    validate_constraints(constraints_payload, ranked_payload)

    target_engagement = dict(ranked_payload["engagement"])
    if isinstance(constraints_payload.get("engagement"), dict):
        target_engagement["affiliates"] = merge_unique(
            _affiliates(ranked_payload["engagement"]), _affiliates(constraints_payload["engagement"]))
    foreign = _foreign_names(constraints_payload, target_engagement)

    log = ScreeningLog()
    _seed_engine_markers(log, ranked_payload, "")
    payload = sanitize_free_text(ranked_payload, "ranked_input", log, engine_markers_ok=True)
    constraints = sanitize_free_text(constraints_payload, "constraints_input", log)

    escalations = _Escalations()
    escalations.extend(payload.get("escalations", []))
    for index, item in enumerate(constraints.get("escalations", [])):
        text, head = normalise_escalation(item, index)
        if _names_foreign(text, foreign):
            text = f"constraints escalations[{index}]: escalation names another client; withheld ({RULES} #9.9)"
        escalations.add(text, head)
    escalations.extend(log)
    merge_notes = []
    try:
        merge_engagement(payload, constraints, merge_notes)
    except SystemExit as error:
        raise InputError(str(error.code)) from None
    escalations.extend(merge_notes)

    held_rows = _held_rows(log)
    row_holds = {index: log.holds_under(f"constraints_input.constraints[{index}]") for index in held_rows}
    register = constraints["constraints"]
    if not register:
        escalations.add(
            f"conflicts register supplied no rows - every candidate requires independence review ({RULES} #9.4)")

    roles_by_key = {id_key(role["role_id"]): role for role in payload["roles"]}
    ranked_ids = [
        candidate["candidate_id"]
        for ranked_role in payload["ranked_roles"]
        for candidate in ranked_role["candidate_slate"]
    ]
    for index in unknown_constraint_rows(constraints, ranked_ids):
        escalations.add(
            f"constraints[{index}]: conflicts-register row names a candidate_id that is not on the ranked slate "
            f"- check candidate ID mapping ({RULES} #9.5)",
            f"{RULES} #9.5",
        )
    missing_reported = set()
    governed_roles = []
    gaps = []

    for r_index, ranked_role in enumerate(payload["ranked_roles"]):
        role = roles_by_key[id_key(ranked_role["role_id"])]
        role_id = role["role_id"]
        governed = []
        top_refused = False
        for c_index, row in enumerate(ranked_role["candidate_slate"]):
            register_rows = candidate_register_rows(constraints, row["candidate_id"])
            candidate_held = {index: held_rows[index] for index, _item in register_rows if index in held_rows}
            ranked_holds = log.holds_under(f"ranked_input.ranked_roles[{r_index}].candidate_slate[{c_index}]")
            holds = merge_unique(row.get("screening_holds") or [], ranked_holds)
            verdict_row = dict(row, screening_holds=holds)
            verdict, reasons, citations, considered = verdict_for(role, verdict_row, constraints, candidate_held)
            for item in considered:
                if "client_name" in item and item.get("applies_to_engagement") is not False \
                        and _names_foreign(item.get("citation"), foreign):
                    item["citation"] = f"conflicts register citation withheld: names another client ({RULES} #9.9)"
            fit = float(row["fit_score"])
            recommendation_status = "not_recommended"
            if verdict == "eligible" and fit >= MIN_RECOMMENDABLE_SCORE:
                recommendation_status = "recommended"
            elif verdict == "eligible":
                recommendation_status = "below_score_floor"
            top = row["provisional_rank"] == 1
            if verdict == "ineligible":
                reason, blocking_rule = blocking_reason(reasons, citations)
                if top:
                    top_refused = True
                    escalations.add(screened(
                        f"{role_id}: refused top provisional candidate {row['candidate_name']} - {reason} "
                        f"({blocking_rule}; {RULES} #7.1)",
                        f"{role_id}: refused top provisional candidate at provisional rank 1 "
                        f"({blocking_rule}; {RULES} #7.1)",
                    ))
            elif verdict == "needs_review":
                reason, blocking_rule = review_reason(reasons, citations)
                if top:
                    escalations.add(screened(
                        f"{role_id}: withheld top provisional candidate {row['candidate_name']} "
                        f"- {reason} ({blocking_rule}; {RULES} #1.2)",
                        f"{role_id}: withheld top provisional candidate at provisional rank 1 "
                        f"({blocking_rule}; {RULES} #1.2)",
                    ))
            else:
                blocking_rule = None
            key = id_key(row["candidate_id"])
            if not register_rows and key not in missing_reported:
                missing_reported.add(key)
                escalations.add(
                    f"{row['candidate_id']}: no conflicts-register row - clearance cannot be inferred; "
                    f"independence review required ({RULES} #9.4)",
                    f"{RULES} #9.4",
                )
            citation = "; ".join(citations)
            if is_suspect(citation):
                citation = "; ".join(item.split(";", 1)[0] for item in citations)
            out = {key: row[key] for key in row if key in CARRIED_KEYS}
            all_holds = merge_unique(holds, *[row_holds[index] for index in candidate_held])
            if all_holds or "screening_holds" in row:
                out["screening_holds"] = all_holds
            out["constraints_considered"] = considered
            out["eligibility"] = {
                "verdict": verdict,
                "recommendation_status": recommendation_status,
                "blocking_rule": blocking_rule,
                "reasons": reasons,
                "source": ENGINE,
                "confidence": min(float(row["confidence"]), 0.99),
                "citation": citation,
            }
            governed.append(out)

        eligible = [c for c in governed if c["eligibility"]["recommendation_status"] == "recommended"]
        for i, candidate in enumerate(eligible, start=1):
            candidate["final_eligible_rank"] = i
        title = screened(role["title"], "this role")
        if not eligible:
            gaps.append({
                "role_id": role_id,
                "role_title": role["title"],
                "gap_statement": f"No eligible candidate meets the {MIN_RECOMMENDABLE_SCORE} fit-score floor for {title}; do not pad the slate.",
                "source": ENGINE,
                "confidence": 0.99,
                "citation": f"fit-scoring-rubric.md #7.2; {RULES} #7.2",
            })
            escalations.add(f"{role_id}: gap statement issued - no eligible candidate above score floor ({RULES} #7.2)")

        governed_roles.append({
            "role_id": ranked_role["role_id"],
            "role_title": ranked_role["role_title"],
            "top_provisional_candidate_refused": top_refused,
            "candidate_slate": governed,
            "recommended_candidates": eligible,
            "source": ENGINE,
            "confidence": 0.99,
            "citation": f"{RULES} #1.1-#8.1",
        })

    payload["governed_roles"] = governed_roles
    payload["gaps"] = gaps
    payload["escalations"] = escalations.render()
    provenance = payload.setdefault("provenance", {})
    engines = [
        engine for engine in provenance.get("engines", [])
        if not engine.startswith("constraint_check/")
    ]
    provenance["engines"] = merge_unique(engines, [ENGINE_VERSION])
    return payload


def rederive_ranked(roles_payload, bench_payload):
    """The ranked document the plugin's own engines derive from roles.json and bench.json."""
    return slate_rank.rank(fit_score.score(roles_payload, bench_payload))


def _main(argv):
    parser = ArgumentParser(prog="constraint_check.py", description="Deterministic eligibility governance.")
    parser.add_argument("--roles", required=True)
    parser.add_argument("--bench", required=True)
    parser.add_argument("--ranked", required=True)
    parser.add_argument("--constraints", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    roles_payload = load_json(args.roles, "roles.json")
    bench_payload = load_json(args.bench, "bench.json")
    ranked_payload = load_json(args.ranked, "ranked.json")
    constraints_payload = load_json(args.constraints, "constraints.json")
    need(ranked_payload.get("contract_version") == CONTRACT,
         "ranked.json: wrong ranked contract (contract_version)")
    need(constraints_payload.get("contract_version") == CONTRACT,
         "constraints.json: wrong constraints contract (contract_version)")
    expected = rederive_ranked(roles_payload, bench_payload)
    need(same_document(ranked_payload, expected),
         "ranked.json does not re-derive from roles.json and bench.json (rule 9.8); re-run fit-score")
    try:
        payload = govern(expected, constraints_payload)
    except SystemExit as error:
        if isinstance(error.code, str):
            raise InputError(error.code) from None
        raise
    write_json(args.out, payload)
    governed_roles = payload["governed_roles"]
    refused = sum(1 for r in governed_roles if r["top_provisional_candidate_refused"])
    print(f"constraint_check: {len(governed_roles)} role(s), {refused} top-candidate refusal(s), "
          f"{len(payload['gaps'])} gap(s) -> governed output written")
    return 0


def main(argv=None):
    """CLI entry point: one clean ``error:`` line and exit 2 on any input error, no output file."""
    return run(lambda: _main(argv))


if __name__ == "__main__":
    sys.exit(main())
