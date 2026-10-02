"""assertion_rules - shared assertion-support rules and input schemas.

Canonical copy: skills/assertion-map/scripts/assertion_rules.py. skills/gate-check/scripts/ ships a
byte-identical copy (verified by tests/check_shared_copies.py) so gate_check can recompute exactly what
assertion_map emits and never has to trust a self-declared source tag (quality-gate-criteria.md #8.4).

Type rule: a field of the wrong JSON type is a clean InputError; values are never coerced, so a string
"false" is never read as a boolean and a page label "iv" is never read as a page number."""

AM_ENGINE = "engine:assertion_map"
EVIDENCE_CONFIDENCE_FLOOR = 0.70  # severity-rules.md #2.2
QUANTIFIED_CONFIDENCE_FLOOR = 0.80  # severity-rules.md #2.3; quality-gate-criteria.md #1.2
FORWARD_LOOKING_CONFIDENCE_FLOOR = 0.55  # quality-gate-criteria.md #1.3
RECOMMENDATION_CONFIDENCE_FLOOR = 0.65  # quality-gate-criteria.md #1.4
MIN_RECOMMENDATION_SAMPLE_SIZE = 30  # quality-gate-criteria.md #1.4
MAX_INPUT_DEPTH = 64  # nesting deeper than any contract shape is rejected before any recursive processing
# Closed evidence-type vocabulary (contract evidence_set[].type). A missing or unrecognised type never supports an assertion.
EVIDENCE_TYPES = {
    "analysis_model", "financial_model", "system_export", "signed_client_data", "licensed_content_register",
    "internal_benchmark", "statement_of_work", "disclaimer_extract", "interview_summary", "workshop_note", "stakeholder_verbal",
}
# Per-class allowlists: support must come from a listed type (quality-gate-criteria.md #1.1-#1.4).
TRACEABLE_QUANTIFIED_TYPES = {"analysis_model", "financial_model", "system_export", "signed_client_data"}  # quality-gate-criteria.md #1.2
FACTUAL_SUPPORT_TYPES = {  # quality-gate-criteria.md #1.1: documented sources stronger than stakeholder recollection
    "analysis_model", "financial_model", "system_export", "signed_client_data", "licensed_content_register",
    "internal_benchmark", "statement_of_work", "disclaimer_extract",
}
FORWARD_LOOKING_SUPPORT_TYPES = EVIDENCE_TYPES - {"stakeholder_verbal"}  # quality-gate-criteria.md #1.3
RECOMMENDATION_SUPPORT_TYPES = EVIDENCE_TYPES - {"stakeholder_verbal", "disclaimer_extract", "licensed_content_register"}  # quality-gate-criteria.md #1.4
SUPPORT_TYPES_BY_CLASS = {
    "quantified": TRACEABLE_QUANTIFIED_TYPES,
    "factual": FACTUAL_SUPPORT_TYPES,
    "forward_looking": FORWARD_LOOKING_SUPPORT_TYPES,
    "recommendation": RECOMMENDATION_SUPPORT_TYPES,
}
RELEVANCE_BY_CLASS = {
    "quantified": {"analysis_model": 4, "financial_model": 4, "system_export": 4, "signed_client_data": 4, "stakeholder_verbal": 1},
    "factual": {"licensed_content_register": 4, "system_export": 4, "signed_client_data": 4, "analysis_model": 3, "financial_model": 3},
    "forward_looking": {"analysis_model": 4, "financial_model": 4, "workshop_note": 3, "interview_summary": 3},
    "recommendation": {"analysis_model": 4, "financial_model": 4, "signed_client_data": 4, "system_export": 4, "interview_summary": 3, "workshop_note": 2, "statement_of_work": 1},
}
# Recognised evidence provenance (quality-gate-criteria.md #1.5): deliverable-ingest records every evidence item as
# `connector:<slug>` or as extracted by an ingest skill. Any other value, including a self-declared tag, cannot
# establish support for any assertion class.
EVIDENCE_SOURCE_CONNECTOR_PREFIX = "connector:"
EVIDENCE_SOURCE_SKILLS = {"skill:deliverable-ingest", "skill:criteria-retrieve"}
CONNECTOR_SLUG_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-_.")
ASSERTION_BOOLEANS = ("hedging_present", "limitation_present", "stated_basis", "scope_aligned")
ASSERTION_COUNTS = ("sample_size", "population_size")
PAGE_LABEL_HINT = "record the physical page number and keep printed labels such as roman numerals in location.label"


class InputError(ValueError):
    """Raised for malformed or unsafe engine input."""


def check_depth(value, label="input", max_depth=MAX_INPUT_DEPTH):
    """Reject nesting deeper than max_depth iteratively, so hostile input can never reach a RecursionError."""
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, (dict, list)):
            if depth > max_depth:
                raise InputError(f"{label} is nested more than {max_depth} levels deep; the review contract never nests that deeply")
            children = item.values() if isinstance(item, dict) else item
            stack.extend((child, depth + 1) for child in children)
    return value


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def require_text(container, key, label, required=True, allow_blank=False):
    """Return container[key] when it is a string; absent optional fields return None."""
    if key not in container or container[key] is None:
        if required:
            raise InputError(f"{label} missing required field: {key}")
        return None
    value = container[key]
    if not isinstance(value, str):
        raise InputError(f"{label}.{key} must be a string, got {value!r}")
    if not allow_blank and not value.strip():
        raise InputError(f"{label}.{key} must not be blank")
    return value


def require_boolean(container, key, label, required=True):
    """Booleans must be JSON true/false; "false", 0 and null are input errors, never coerced."""
    if key not in container:
        if required:
            raise InputError(f"{label} missing required boolean: {key}")
        return None
    value = container[key]
    if not isinstance(value, bool):
        raise InputError(f"{label}.{key} must be true or false, got {value!r}; omit optional flags instead of sending null or text")
    return value


def require_confidence(container, label, required=False):
    if "confidence" not in container:
        if required:
            raise InputError(f"{label} missing required field: confidence")
        return None
    value = container["confidence"]
    if not is_number(value) or not 0 <= value <= 1:
        raise InputError(f"{label}.confidence must be a number from 0 to 1, got {value!r}")
    return value


def validate_location(location, label, required=True):
    if location is None and not required:
        return None
    if not isinstance(location, dict):
        raise InputError(f"{label}.location must be an object")
    for key in ("section", "label"):
        if key in location and location[key] is not None and not isinstance(location[key], str):
            raise InputError(f"{label}.location.{key} must be a string, got {location[key]!r}")
    for key in ("page", "paragraph"):
        value = location.get(key)
        if value is not None and not is_integer(value):
            raise InputError(f"{label}: location.{key} must be an integer or null, got {value!r}; {PAGE_LABEL_HINT}")
    return location


def validate_assertion(assertion, index):
    if not isinstance(assertion, dict):
        raise InputError(f"assertions[{index}] must be an object")
    label = f"assertions[{index}]"
    require_text(assertion, "assertion_id", label)
    label = f"{label} ({assertion['assertion_id']})"
    require_text(assertion, "class", label)
    require_text(assertion, "text", label, allow_blank=True)
    require_text(assertion, "citation", label, allow_blank=True)
    require_text(assertion, "source", label, required=False, allow_blank=True)
    if "location" not in assertion:
        raise InputError(f"{label} missing required field: location")
    validate_location(assertion["location"], label)
    for key in ASSERTION_BOOLEANS:
        # scope_aligned is required for every class: G3 (quality-gate-criteria.md #3.1) applies to all claims and
        # recommendations, so an omitted flag is never read as "aligned".
        require_boolean(assertion, key, label, required=key == "scope_aligned")
    if assertion["class"] == "recommendation" and "sample_size" not in assertion:
        raise InputError(f"{label} missing required field for a recommendation: sample_size (use null only when the recommendation is not sample-based)")
    for key in ASSERTION_COUNTS:
        value = assertion.get(key)
        if value is not None and (not is_integer(value) or value < 0):
            raise InputError(f"{label}.{key} must be a non-negative integer or null, got {value!r}")
    require_confidence(assertion, label)
    evidence_ids = assertion.get("evidence_ids")
    if evidence_ids is not None:
        if not isinstance(evidence_ids, list):
            raise InputError(f"{label}.evidence_ids must be an array when present")
        for position, evidence_id in enumerate(evidence_ids):
            if not isinstance(evidence_id, str) or not evidence_id.strip():
                raise InputError(f"{label}.evidence_ids[{position}] must be a non-blank string, got {evidence_id!r}")


def validate_assertions(assertions):
    if not isinstance(assertions, list):
        raise InputError("assertions must be an array")
    seen = set()
    for index, assertion in enumerate(assertions):
        validate_assertion(assertion, index)
        if assertion["assertion_id"] in seen:
            raise InputError(f"assertions[{index}]: duplicate assertion_id {assertion['assertion_id']!r}")
        seen.add(assertion["assertion_id"])


def evidence_index(evidence_set):
    if not isinstance(evidence_set, list):
        raise InputError("evidence_set must be an array")
    by_id = {}
    for index, item in enumerate(evidence_set):
        if not isinstance(item, dict):
            raise InputError(f"evidence_set[{index}] must be an object with evidence_id")
        label = f"evidence_set[{index}]"
        require_text(item, "evidence_id", label)
        for key in ("type", "title", "citation", "source"):
            require_text(item, key, label, required=False, allow_blank=True)
        require_confidence(item, label)
        if item["evidence_id"] in by_id:
            raise InputError(f"{label}: duplicate evidence_id {item['evidence_id']!r}")
        by_id[item["evidence_id"]] = item
    return by_id


def linked_evidence(assertion, evidence_by_id):
    return [evidence_by_id[eid] for eid in assertion.get("evidence_ids") or [] if eid in evidence_by_id]


def evidence_relevance(assertion, evidence):
    by_type = RELEVANCE_BY_CLASS.get(assertion.get("class"), {})
    return by_type.get(evidence.get("type", "unknown"), 2)


def normalise_provenance(source):
    """Fold presentation differences a model-driven ingest may introduce: surrounding whitespace, case, and internal
    whitespace runs (to `-`), so `Connector:Engagement Workspace` reads as `connector:engagement-workspace`.
    Case adds no trust, because any lower-case slug is accepted. Returns None for a non-string."""
    if not isinstance(source, str):
        return None
    prefix, separator, slug = source.strip().partition(":")
    if not separator:
        return source.strip().lower()
    return f"{prefix.strip().lower()}:{'-'.join(slug.lower().split())}"


def recognised_provenance(evidence):
    """True only for ingest provenance after normalisation: `connector:<slug>` or an ingest skill tag (quality-gate-criteria.md #1.5)."""
    source = normalise_provenance(evidence.get("source"))
    if source is None:
        return False
    if source in EVIDENCE_SOURCE_SKILLS:
        return True
    slug = source[len(EVIDENCE_SOURCE_CONNECTOR_PREFIX):] if source.startswith(EVIDENCE_SOURCE_CONNECTOR_PREFIX) else ""
    return bool(slug) and slug[0].isalnum() and set(slug) <= CONNECTOR_SLUG_CHARS


def acceptable_support(assertion, evidence):
    return recognised_provenance(evidence) and evidence.get("type") in SUPPORT_TYPES_BY_CLASS.get(assertion.get("class"), ())


def evidence_type_label(ev_type):
    return ev_type if ev_type in EVIDENCE_TYPES else "a missing or unrecognised evidence type"


def best_evidence(assertion, linked_items):
    if not linked_items:
        return None
    return max(linked_items, key=lambda item: (acceptable_support(assertion, item), recognised_provenance(item), evidence_relevance(assertion, item), item.get("confidence", 0.0)))


def linked_evidence_citation(assertion, evidence_by_id):
    citations = []
    for evidence_id in assertion.get("evidence_ids") or []:
        evidence = evidence_by_id.get(evidence_id)
        citations.append(evidence.get("citation", f"evidence {evidence_id}") if evidence else f"missing linked evidence {evidence_id}")
    return "; ".join(citations) if citations else "no linked evidence found"


def location_label(location):
    return f"p{location.get('page')}, {location.get('section')}, paragraph {location.get('paragraph')}"


def is_definitive_conclusion(assertion):
    if assertion.get("limitation_present") is True:
        return False
    text = assertion.get("text", "").lower()
    definitive_terms = (" should ", "we conclude", "will ", "all ", "full ", "estate-wide", "applies across", "national ")
    return (
        assertion.get("hedging_present") is not True
        or assertion.get("scope_aligned") is False
        or assertion.get("population_size") is not None
        or any(term in f" {text} " for term in definitive_terms)
    )


def classify(assertion, evidence, missing_ids=()):
    klass = assertion.get("class")
    if evidence is None:
        if not assertion.get("evidence_ids"):
            return "unsupported", 0.0, "No evidence IDs were linked to the assertion", "quality-gate-criteria.md #1.1"
        return "unsupported", 0.0, "No linked evidence item was found in the evidence index", "quality-gate-criteria.md #1.1"
    confidence = min(float(assertion.get("confidence", 0.0)), float(evidence.get("confidence", 0.0)))
    if missing_ids:
        # Declared support must exist: a dangling evidence reference is never ignored (quality-gate-criteria.md #1.1).
        return "unsupported", confidence, f"{len(missing_ids)} linked evidence ID(s) are not in the evidence index, so the declared support cannot be verified", "quality-gate-criteria.md #1.1"
    if not recognised_provenance(evidence):
        # A type or confidence the evidence item declares about itself proves nothing without ingest provenance.
        return "unsupported", confidence, "No linked evidence item has recognised provenance (connector:<slug>, skill:deliverable-ingest or skill:criteria-retrieve); missing, unrecognised or self-declared sources cannot establish support", "quality-gate-criteria.md #1.5"
    ev_type = evidence.get("type")
    if klass == "quantified":
        if ev_type not in TRACEABLE_QUANTIFIED_TYPES:
            return "unsupported", confidence, f"Quantified claim cites {evidence_type_label(ev_type)}, not traceable analysis or signed data", "quality-gate-criteria.md #1.2; severity-rules.md #2.3"
        if confidence < QUANTIFIED_CONFIDENCE_FLOOR:
            return "unsupported", confidence, f"Quantified support confidence {confidence:.2f} below {QUANTIFIED_CONFIDENCE_FLOOR:.2f}", "severity-rules.md #2.3"
        return "supported", confidence, "Quantified claim supported by traceable analytical evidence", "quality-gate-criteria.md #1.2"
    if klass == "factual":
        if ev_type not in FACTUAL_SUPPORT_TYPES or confidence < EVIDENCE_CONFIDENCE_FLOOR:
            return "unsupported", confidence, f"Factual claim support is {evidence_type_label(ev_type)} at confidence {confidence:.2f}; factual support must be a documented source type stronger than stakeholder recollection at or above {EVIDENCE_CONFIDENCE_FLOOR:.2f}", "quality-gate-criteria.md #1.1; severity-rules.md #2.2"
        return "supported", confidence, "Factual claim has cited evidence above the support floor", "quality-gate-criteria.md #1.1"
    if klass == "forward_looking":
        if assertion.get("hedging_present") is not True or assertion.get("limitation_present") is not True:
            return "limited", confidence, "Forward-looking statement lacks required hedging or limitation", "quality-gate-criteria.md #1.3"
        if ev_type not in FORWARD_LOOKING_SUPPORT_TYPES:
            return "limited", confidence, f"Forward-looking statement cites {evidence_type_label(ev_type)}, which is not accepted support", "quality-gate-criteria.md #1.3"
        if confidence < FORWARD_LOOKING_CONFIDENCE_FLOOR:
            return "limited", confidence, f"Forward-looking support confidence {confidence:.2f} below {FORWARD_LOOKING_CONFIDENCE_FLOOR:.2f}", "quality-gate-criteria.md #1.3"
        return "supported", confidence, "Forward-looking statement is hedged and limitation is stated", "quality-gate-criteria.md #1.3"
    if klass == "recommendation":
        sample_size = assertion.get("sample_size")
        if assertion.get("stated_basis") is not True:
            return "unsupported", confidence, "Recommendation has no stated basis", "quality-gate-criteria.md #1.4"
        if ev_type not in RECOMMENDATION_SUPPORT_TYPES:
            return "unsupported", confidence, f"Recommendation cites {evidence_type_label(ev_type)}, not evidence proportionate to a recommendation", "quality-gate-criteria.md #1.4"
        if sample_size is not None and sample_size < MIN_RECOMMENDATION_SAMPLE_SIZE and assertion.get("limitation_present") is not True:
            criteria = "quality-gate-criteria.md #1.4; quality-gate-criteria.md #3.2"
            rationale = f"Recommendation uses sample size {sample_size}, below {MIN_RECOMMENDATION_SAMPLE_SIZE}, without a limitation"
            if is_definitive_conclusion(assertion):
                criteria += "; severity-rules.md #1.1"
                rationale += " and is framed as a definitive conclusion"
            return "unsupported", confidence, rationale, criteria
        if confidence < RECOMMENDATION_CONFIDENCE_FLOOR:
            return "limited", confidence, f"Recommendation support confidence {confidence:.2f} below {RECOMMENDATION_CONFIDENCE_FLOOR:.2f}", "quality-gate-criteria.md #1.4"
        return "supported", confidence, "Recommendation has a stated basis and proportionate support", "quality-gate-criteria.md #1.4"
    return "unsupported", 0.0, f"Unknown assertion class {klass}", "severity-rules.md #2.1"


def map_assertion(assertion, evidence_by_id):
    """Return (mapping, AM finding or None, escalation or None) exactly as assertion_map emits them."""
    evidence = best_evidence(assertion, linked_evidence(assertion, evidence_by_id))
    missing_ids = [eid for eid in assertion.get("evidence_ids") or [] if eid not in evidence_by_id]
    status, support_score, rationale, criteria_section = classify(assertion, evidence, missing_ids)
    mapping = {
        "assertion_id": assertion["assertion_id"], "class": assertion["class"], "text": assertion["text"],
        "location": assertion["location"], "evidence_ids": assertion.get("evidence_ids") or [],
        "best_evidence_id": evidence.get("evidence_id") if evidence else None, "support_status": status,
        "support_score": round(support_score, 2), "rationale": rationale, "criteria_section": criteria_section,
        "confidence": round(support_score, 2), "source": AM_ENGINE,
        "citation": f"{assertion['citation']}; {linked_evidence_citation(assertion, evidence_by_id)}; {criteria_section}"
    }
    if status not in {"unsupported", "limited"}:
        return mapping, None, None
    severity = "release_blocker" if (
        status == "unsupported"
        and (assertion["class"] == "quantified" or is_definitive_conclusion(assertion))
    ) else "must_fix" if status == "unsupported" else "advisory"
    finding = {"finding_id": f"AM-{assertion['assertion_id']}", "gate_id": "G1", "severity": severity,
        "title": f"{assertion['class'].replace('_', ' ').title()} assertion is {status}", "detail": rationale,
        "location": assertion["location"], "criteria_section": criteria_section, "confidence": round(support_score, 2),
        "source": AM_ENGINE, "citation": mapping["citation"]}
    escalation = f"{assertion['assertion_id']} at {location_label(assertion['location'])}: {status} - {rationale} ({criteria_section})"
    return mapping, finding, escalation
