"""assertion_rules - shared assertion-support rules and input schemas.

Canonical copy: skills/assertion-map/scripts/assertion_rules.py. skills/gate-check/scripts/ ships a
byte-identical copy (verified by tests/check_shared_copies.py) so gate_check can recompute exactly what
assertion_map emits and never has to trust a self-declared source tag (quality-gate-criteria.md #8.4).

Type rule: a field of the wrong JSON type is a clean InputError; values are never coerced, so a string
"false" is never read as a boolean and a page label "iv" is never read as a page number.

Contract rule: every engine calls validate_contract at entry, which checks the whole payload against the
skill's own copy of contracts/ps.deliverable-review-quality-gate.v1.json (required fields, JSON types, closed
enums, ranges and provenance prefixes). A violation is an InputError raised before any output is written."""
import functools
import json
import math
import os
import re
import tempfile

import steering_guard as sg  # vendored shared detector; never edit (tests/check_shared_copies.py pins its SHA-256)

AM_ENGINE = "engine:assertion_map"
CONTRACT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "contracts", "ps.deliverable-review-quality-gate.v1.json")
# Top-level sections each engine needs beyond the contract's own required list (contract descriptions say which).
STAGE_REQUIRED = {
    "assertion_map": ("criteria", "evidence_set"),
    "gate_check": ("assertion_mappings",),
    "severity_rank": ("assertion_mappings", "gate_results", "findings", "escalations"),
}
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
    """A finite JSON number. NaN and +/-Infinity are not JSON numbers and never pass a range check."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return isinstance(value, int) or math.isfinite(value)


def _reject_constant(name):
    raise InputError(f"input JSON contains {name}, which is not a valid JSON number")


def describe(value):
    """A content-free description of an untrusted value for error messages: its JSON type and size, never its text
    (quality-gate-criteria.md #8.9), so a rejected value can never echo embedded instructions to stderr."""
    def plural(count, noun):
        return f"{count} {noun}{'' if count == 1 else 's'}"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, int):
        return "an integer"
    if isinstance(value, float):
        return "a number"
    if isinstance(value, str):
        return f"a {'' if value.strip() else 'blank '}string of {plural(len(value), 'character')}"
    if isinstance(value, list):
        return f"an array of {plural(len(value), 'item')}"
    if isinstance(value, dict):
        return f"an object with {plural(len(value), 'field')}"
    return f"a {type(value).__name__} value"


FIELD_NAME = re.compile(r"[a-z][a-z0-9_]{0,40}")


def path_key(key):
    """A field name shown in an error path only when it is a plain snake_case name that passes the screen; anything
    else is shown as <field>, so an untrusted member name is never echoed."""
    return key if isinstance(key, str) and FIELD_NAME.fullmatch(key) and not suspicious_instruction(key) else "<field>"


def format_path(parts):
    text = "$"
    for part in parts:
        text += f"[{part}]" if isinstance(part, int) else f".{path_key(part)}"
    return text


class _DuplicateFields(dict):
    """A JSON object with two member names that are equal exactly or after normalisation; rejected after loading."""


class _OverlongFieldName(dict):
    """A JSON object with a member name longer than MAX_FIELD_NAME_CHARS; rejected after loading."""


MAX_FIELD_NAME_CHARS = 512  # far above any contract field name or withheld marker (quality-gate-criteria.md #8.10)


@functools.lru_cache(maxsize=4096)
def field_name_key(name):
    """Comparison form of a member name: the detector's full fold (NFKC, format characters, confusables, case and
    separators), applied at every length. Names longer than MAX_FIELD_NAME_CHARS never get here; they are refused."""
    return sg.normalize(name)


def _object_pairs(pairs):
    if any(len(key) > MAX_FIELD_NAME_CHARS for key, _ in pairs):
        return _OverlongFieldName(pairs)
    seen, duplicate = set(), False
    for key, _ in pairs:
        folded = field_name_key(key)
        duplicate = duplicate or folded in seen
        seen.add(folded)
    return _DuplicateFields(pairs) if duplicate else dict(pairs)


def _check_loaded(value):
    """Reject objects with duplicate member names (a later value would overwrite an earlier one, quality-gate-criteria.md
    #8.10) and lone UTF-16 surrogates (for example "\\ud800": not Unicode text, cannot be written as UTF-8)."""
    stack = [(value, ())]
    while stack:
        item, parts = stack.pop()
        if isinstance(item, _OverlongFieldName):
            raise InputError(f"{format_path(parts)} has a field name longer than {MAX_FIELD_NAME_CHARS} characters, which no contract field needs and which cannot be checked for duplicates safely; the input is malformed")
        if isinstance(item, _DuplicateFields):
            raise InputError(f"{format_path(parts)} has duplicate field names (equal exactly or after Unicode, case and separator folding), so a later value could overwrite an earlier one; the input is malformed")
        if isinstance(item, dict):
            for key, child in item.items():
                _check_encodable_text(key, lambda parts=parts: f"{format_path(parts)} (a field name)")
                stack.append((child, parts + (key,)))
        elif isinstance(item, list):
            stack.extend((child, parts + (index,)) for index, child in enumerate(item))
        elif isinstance(item, str):
            _check_encodable_text(item, lambda parts=parts: format_path(parts))


def _check_encodable_text(text, path):
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise InputError(f"{path()} contains a lone surrogate code point, which is not valid Unicode text") from exc


def unique_entries(entries):
    """The entries in order without repeats (strings or objects), so re-running an engine on its own output never
    duplicates an escalation or finding it already carries."""
    seen, kept = set(), []
    for entry in entries:
        key = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            kept.append(entry)
    return kept


def record_engine(payload, tag):
    """Append the engine/version tag to provenance.engines unless this engine was the last to run (idempotent re-run)."""
    provenance = payload.setdefault("provenance", {})
    if not isinstance(provenance, dict):
        raise InputError("provenance must be an object when present")
    engines = provenance.setdefault("engines", [])
    if not isinstance(engines, list):
        raise InputError("provenance.engines must be an array when present")
    if engines[-1:] != [tag]:
        engines.append(tag)
    return provenance


def load_json_file(path):
    """Load engine input. Strict JSON only: NaN/Infinity constants, lone surrogates, duplicate member names and
    over-deep nesting are input errors, so no engine ever processes or writes a value that is not valid JSON."""
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle, parse_constant=_reject_constant, object_pairs_hook=_object_pairs)
    except OSError as exc:
        raise InputError(f"could not read input JSON: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise InputError(f"input JSON is not valid UTF-8: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON input: {exc}") from exc
    except RecursionError as exc:
        raise InputError("input JSON is nested too deeply to process safely") from exc
    check_depth(payload)
    _check_loaded(payload)
    return payload


def write_json_atomic(path, payload):
    """Serialise the whole output first, then write it to a temporary file beside the target and os.replace it into
    place. On any error the output path is neither created nor truncated."""
    try:
        data = (json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    except ValueError as exc:  # includes UnicodeEncodeError and non-finite numbers
        raise InputError(f"output could not be serialised as valid JSON, so nothing was written: {exc}") from exc
    target = os.path.abspath(path)
    try:
        handle, temp = tempfile.mkstemp(dir=os.path.dirname(target), prefix=f".{os.path.basename(target)}.", suffix=".tmp")
    except OSError as exc:
        raise InputError(f"could not write output {path}: {exc}") from exc
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        if os.name != "nt":
            os.chmod(temp, 0o644)
        os.replace(temp, target)
    except BaseException as exc:
        try:
            os.remove(temp)
        except OSError:
            pass
        if isinstance(exc, OSError):
            raise InputError(f"could not write output {path}: {exc}") from exc
        raise


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
        raise InputError(f"{label}.{key} must be a string, got {describe(value)}")
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
        raise InputError(f"{label}.{key} must be true or false, got {describe(value)}; omit optional flags instead of sending null or text")
    return value


def require_confidence(container, label, required=False):
    if "confidence" not in container:
        if required:
            raise InputError(f"{label} missing required field: confidence")
        return None
    value = container["confidence"]
    if not is_number(value) or not 0 <= value <= 1:
        raise InputError(f"{label}.confidence must be a number from 0 to 1, got {describe(value)}")
    return value


def validate_location(location, label, required=True):
    if location is None and not required:
        return None
    if not isinstance(location, dict):
        raise InputError(f"{label}.location must be an object")
    for key in ("section", "label"):
        if key in location and location[key] is not None and not isinstance(location[key], str):
            raise InputError(f"{label}.location.{key} must be a string, got {describe(location[key])}")
    for key in ("page", "paragraph"):
        value = location.get(key)
        if value is not None and not is_integer(value):
            raise InputError(f"{label}: location.{key} must be an integer or null, got {describe(value)}; {PAGE_LABEL_HINT}")
    return location


def validate_assertion(assertion, index):
    if not isinstance(assertion, dict):
        raise InputError(f"assertions[{index}] must be an object")
    label = f"assertions[{index}]"
    require_text(assertion, "assertion_id", label)
    require_text(assertion, "class", label)
    require_text(assertion, "text", label, allow_blank=True)
    require_text(assertion, "citation", label, allow_blank=True)
    # Required provenance (contract: engine:/skill:/connector: prefix); the prefix itself is checked by validate_contract.
    require_text(assertion, "source", label)
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
            raise InputError(f"{label}.{key} must be a non-negative integer or null, got {describe(value)}")
    require_confidence(assertion, label)
    evidence_ids = assertion.get("evidence_ids")
    if evidence_ids is not None:
        if not isinstance(evidence_ids, list):
            raise InputError(f"{label}.evidence_ids must be an array when present")
        for position, evidence_id in enumerate(evidence_ids):
            if not isinstance(evidence_id, str) or not evidence_id.strip():
                raise InputError(f"{label}.evidence_ids[{position}] must be a non-blank string, got {describe(evidence_id)}")


def validate_assertions(assertions):
    if not isinstance(assertions, list):
        raise InputError("assertions must be an array")
    seen = {}
    for index, assertion in enumerate(assertions):
        validate_assertion(assertion, index)
        if assertion["assertion_id"] in seen:
            raise InputError(f"assertions[{index}].assertion_id duplicates assertions[{seen[assertion['assertion_id']]}].assertion_id; assertion IDs must be unique")
        seen[assertion["assertion_id"]] = index


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
            first = next(position for position, other in enumerate(evidence_set) if other is by_id[item["evidence_id"]])
            raise InputError(f"{label}.evidence_id duplicates evidence_set[{first}].evidence_id; evidence IDs must be unique")
        by_id[item["evidence_id"]] = item
    return by_id


_CONTRACT_SCHEMA = []
_JSON_TYPES = {
    "object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list), "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool), "null": lambda v: v is None, "number": is_number, "integer": is_integer,
}


def contract_schema():
    """The contract this skill ships (contracts/ next to scripts/), loaded once. A missing contract fails closed."""
    if not _CONTRACT_SCHEMA:
        try:
            with open(CONTRACT_PATH, encoding="utf-8") as handle:
                _CONTRACT_SCHEMA.append(json.load(handle))
        except (OSError, ValueError) as exc:
            raise InputError(f"contract schema could not be loaded from the skill's contracts folder: {exc}") from exc
    return _CONTRACT_SCHEMA[0]


def _contract_errors(value, node, path, root):
    """Yield the first violation of `node` (a draft-07 subset: $ref, const, oneOf, type, enum, required, properties,
    items, minLength, pattern, minimum, maximum). x-unrecognised: hold marks an enum the gates judge themselves: any
    string or null passes here and the gate holds on an unrecognised value. x-normalise: provenance compares a source
    after normalise_provenance, as the evidence rule does."""
    if "$ref" in node:
        node = root["definitions"][node["$ref"].rsplit("/", 1)[-1]]
    if "const" in node and value != node["const"]:
        yield f"{path} must be {node['const']!r}, got {describe(value)}"
        return
    if "oneOf" in node:
        if sum(1 for option in node["oneOf"] if next(_contract_errors(value, option, path, root), None) is None) != 1:
            yield f"{path} has the wrong shape (expected exactly one of {', '.join(str(option.get('type')) for option in node['oneOf'])}), got {describe(value)}"
        return
    types = node.get("type")
    if types is not None:
        types = [types] if isinstance(types, str) else types
        if not any(_JSON_TYPES[name](value) for name in types):
            yield f"{path} must be {' or '.join(types)}, got {describe(value)}"
            return
    if "enum" in node and value not in node["enum"]:
        if node.get("x-unrecognised") == "hold":
            if not (value is None or isinstance(value, str)):
                yield f"{path} must be a string or null, got {describe(value)}"
        else:
            yield f"{path} must be one of {', '.join(node['enum'])}, got {describe(value)}"
        return
    if isinstance(value, str):
        if is_withheld(value):
            # Withheld marker: the embedded-instruction screen replaced text that was validated raw before withholding.
            return
        if len(value.strip()) < node.get("minLength", 0):
            yield f"{path} must be a non-blank string"
        elif "pattern" in node:
            candidate = normalise_provenance(value) if node.get("x-normalise") == "provenance" else value
            if not re.search(node["pattern"], candidate):
                yield f"{path} ({describe(value)}) does not match the contract format {node['pattern']}"
    elif is_number(value):
        if value < node.get("minimum", value) or value > node.get("maximum", value):
            yield f"{path} must be between {node.get('minimum')} and {node.get('maximum')}, got a number outside that range"
    elif isinstance(value, dict):
        for key in node.get("required", ()):
            if key not in value:
                yield f"{path} is missing required field {key}"
                return
        for key, child in node.get("properties", {}).items():
            if key in value:
                yield from _contract_errors(value[key], child, f"{path}.{key}", root)
    elif isinstance(value, list) and "items" in node:
        for index, item in enumerate(value):
            yield from _contract_errors(item, node["items"], f"{path}[{index}]", root)


def validate_contract(payload, stage):
    """Check the whole payload against the contract at engine entry; raise InputError on the first violation."""
    schema = contract_schema()
    error = next(_contract_errors(payload, schema, "$", schema), None)
    if error is None:
        missing = [key for key in STAGE_REQUIRED[stage] if key not in payload]
        if missing:
            error = f"$ is missing {', '.join(missing)}, which {stage} requires (see the contract descriptions)"
    if error is not None:
        raise InputError(f"contract violation: {error}")
    validate_unique_ids(payload)
    return payload


# Every array an engine indexes or matches by ID (quality-gate-criteria.md #8.11). gate_results (one entry per gate) is
# checked by severity_rank's reconciliation; findings[] allows identical copies, which collapse (severity-rules.md #3.4).
ID_KEYED_ARRAYS = (
    (("assertions",), "assertion_id"),
    (("evidence_set",), "evidence_id"),
    (("assertion_mappings",), "assertion_id"),
    (("deliverable", "brand_checks"), "check_id"),
    (("deliverable", "licensed_content"), "content_id"),
    (("prior_findings",), "finding_id"),
    (("findings",), "finding_id"),
    (("ranked_findings",), "finding_id"),
)


def require_unique_ids(items, label, id_key, allow_identical=False, prefix=""):
    """Refuse two entries whose IDs are equal exactly or after the detector's fold (Unicode, case, separators), so a
    lookup keyed by ID can never let one entry overwrite or mask another. With allow_identical, entries that are equal
    in every field are not a conflict: nothing differs, so nothing can be hidden. The message names positions only."""
    seen = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not isinstance(item.get(id_key), str):
            continue
        key = field_name_key(item[id_key]) if len(item[id_key]) <= MAX_FIELD_NAME_CHARS else item[id_key]
        if key in seen:
            first = seen[key]
            if allow_identical and items[first] == item:
                continue
            raise InputError(f"{prefix}{label}[{index}].{id_key} duplicates {label}[{first}].{id_key} (equal exactly or after Unicode, case and separator folding); IDs must be unique so no entry can overwrite or mask another")
        seen[key] = index


def validate_unique_ids(payload):
    for path, id_key in ID_KEYED_ARRAYS:
        items = payload
        for part in path:
            items = items.get(part) if isinstance(items, dict) else None
        if isinstance(items, list):
            require_unique_ids(items, ".".join(path), id_key, allow_identical=path == ("findings",), prefix="contract violation: ")


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


# ---------------------------------------------------------------------------------------------------------------
# Embedded-instruction screening and withholding shared by every stage (quality-gate-criteria.md #8.1-#8.7).
# G8 screening runs through the vendored shared detector. DRQG vocabulary reaches it only through the hooks. The
# contract carries no client or firm e-mail/web domains, so trusted_domains stays empty and any send/forward verb
# aimed at an address or URL holds.
STEERING_HOOKS = dict(
    extra_verdict_words=("release ready", "ready for issue", "ready for release", "cleared for release", "quality gate passed"),
    extra_rule_nouns=("disclaimer requirement", "citation rules", "reliance clause", "reliance language", "disclaimer", "qrm",
                      "quality gate", "gate criteria", "g1", "g2", "g3", "g4", "g5", "g6", "g7", "g8"),
    trusted_domains=(),
)
OVERSIZE = "oversize"
SPLIT = "split"
INSTRUCTION = "instruction"
# Untrusted sections scanned verbatim. Every other section (assertion_mappings, findings, escalations,
# provenance) is derived from them and is scanned only for text that is not a copy of a primary field.
PRIMARY_SECTIONS = ("deliverable", "criteria", "assertions", "evidence_set", "prior_findings")
UNSCANNED_KEYS = {"contract_version"}  # validated against the contract version before any scan
SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_.:#/ -]{1,80}$")
AGGREGATE_LABEL = "(combined text, citation, evidence titles and location label)"
# Withheld markers (quality-gate-criteria.md #8.7). Numbered per distinct withheld text, so two different withheld
# identifiers never collide and every copy of one text carries the same marker at every stage.
WITHHELD_WORDING = {
    INSTRUCTION: "flagged by the embedded-instruction screen",
    OVERSIZE: "too long to screen for embedded instructions",
    SPLIT: "flagged with neighbouring fields by the embedded-instruction screen",
}
WITHHELD_PATTERN = re.compile(r"\[withheld (\d+)(?: \((oversize|split)\))?: [a-z -]+; see the G8 finding\]")


def withheld_marker(number, kind=INSTRUCTION):
    qualifier = "" if kind == INSTRUCTION else f" ({kind})"
    return f"[withheld {number}{qualifier}: {WITHHELD_WORDING[kind]}; see the G8 finding]"


def withheld_kind(value):
    """INSTRUCTION, OVERSIZE or SPLIT when value is exactly a withheld marker, otherwise None."""
    match = WITHHELD_PATTERN.fullmatch(value) if isinstance(value, str) else None
    return (match.group(2) or INSTRUCTION) if match else None


def is_withheld(value):
    return withheld_kind(value) is not None


@functools.lru_cache(maxsize=4096)
def _screen_cached(value):
    return tuple(sg.scan(value, **STEERING_HOOKS))


def screen_text(value):
    """steering_guard hits for one untrusted string, with the DRQG hooks (cached: keys and IDs repeat)."""
    return list(_screen_cached(value)) if isinstance(value, str) else []


@functools.lru_cache(maxsize=4096)
def _screen_fields_cached(items):
    return tuple(sg.scan_fields(dict(items), **STEERING_HOOKS))


def screen_fields(fields):
    """steering_guard hits for a multi-field record; a 'split' hit means only the joined fields trip (cached: every
    stage re-screens the same assertions)."""
    return list(_screen_fields_cached(tuple(fields.items())))


def hit_reason(found):
    """OVERSIZE when the text was too long to screen, which is a hold (quality-gate-criteria.md #8.6), else INSTRUCTION."""
    return OVERSIZE if any(hit.family == OVERSIZE for hit in found) else INSTRUCTION


def suspicious_instruction(value):
    """True when the text trips the shared detector or is too long to screen (an oversize result is a hold)."""
    return bool(screen_text(value))


def safe_token(value, fallback):
    text = str(value)
    return text if SAFE_TOKEN.match(text) and not suspicious_instruction(text) else fallback


KEY_SUFFIX = " (field name)"
PAIR_SUFFIX = " (adjacent entries)"


def iter_strings(value, path):
    """Yield (path, text) for every string in value, member names included: a name is untrusted text too
    (quality-gate-criteria.md #8.5). Nothing below the top level is skipped, whatever its key (metadata, provenance or a
    nested contract_version alike)."""
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{safe_token(key, '<field>')}"
            yield child_path + KEY_SUFFIX, key
            yield from iter_strings(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_strings(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def iter_arrays(value, path):
    """Yield (path, list) for every array in value, at any depth."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield from iter_arrays(child, f"{path}.{safe_token(key, '<field>')}")
    elif isinstance(value, list):
        yield path, value
        for index, child in enumerate(value):
            yield from iter_arrays(child, f"{path}[{index}]")


def top_level_sections(payload):
    """Yield (key, path, child, derived) for each top-level member except the validated contract_version."""
    for key, child in payload.items():
        if key in UNSCANNED_KEYS:
            continue
        yield key, f"$.{safe_token(key, '<field>')}", child, not (key in PRIMARY_SECTIONS or not isinstance(child, (dict, list)))


def scan_sections(payload):
    """(primary, derived): lists of (path, text) for every untrusted string and member name, primary sections and
    top-level scalars first."""
    primary, derived = [], []
    for key, path, child, is_derived in top_level_sections(payload):
        target = derived if is_derived else primary
        target.append((path + KEY_SUFFIX, key))
        target.extend(iter_strings(child, path))
    return primary, derived


def array_pairs(payload):
    """Yield (path, fields, refs, derived) for each pair of adjacent non-blank string entries in any array, so prose
    split across array entries is screened joined (quality-gate-criteria.md #8.5), as an assertion's fields are."""
    for _, path, child, derived in top_level_sections(payload):
        for list_path, items in iter_arrays(child, path):
            for index in range(len(items) - 1):
                first, second = items[index], items[index + 1]
                if isinstance(first, str) and isinstance(second, str) and first.strip() and second.strip():
                    names = (f"entry {index}", f"entry {index + 1}")
                    yield (f"{list_path}[{index}]+[{index + 1}]{PAIR_SUFFIX}", dict(zip(names, (first, second))),
                           dict(zip(names, ((items, index), (items, index + 1)))), derived)


def collect_scan_text(payload):
    """Yield (path, text, derived) for every untrusted string, primary sections first.

    Every string is yielded verbatim, including citation fields; nothing is stripped before screening
    (quality-gate-criteria.md #8.5). A derived string that is exactly equal to a primary string is a copy
    (for example assertion_mappings[].text) and is not yielded again."""
    primary, derived = scan_sections(payload)
    for path, text in primary:
        yield path, text, False
    copies = {text for _, text in primary}
    for path, text in derived:
        if text not in copies:
            yield path, text, True


def assertion_records(payload):
    """Yield (path, fields, refs) per assertion: fields maps text, citation, linked evidence titles and the location
    label (in reading order, non-blank strings only) to their values, and refs maps the same names to the
    (container, key) holding each value. Only assertions with more than one such field are yielded."""
    evidence = {item["evidence_id"]: item for item in payload.get("evidence_set") or [] if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)}
    for index, assertion in enumerate(payload.get("assertions") or []):
        if not isinstance(assertion, dict):
            continue
        refs = {"text": (assertion, "text"), "citation": (assertion, "citation")}
        for position, evidence_id in enumerate(assertion.get("evidence_ids") or []):
            linked = evidence.get(evidence_id) if isinstance(evidence_id, str) else None
            if isinstance(linked, dict):
                refs[f"evidence title {position + 1}"] = (linked, "title")
        location = assertion.get("location")
        if isinstance(location, dict):
            refs["location label"] = (location, "label")
        fields = {}
        for name, (container, key) in list(refs.items()):
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                fields[name] = value
            else:
                del refs[name]
        if len(fields) > 1:
            yield f"$.assertions[{index}] {AGGREGATE_LABEL}", fields, refs


def assertion_fields(payload):
    """Yield (path, fields) per assertion: text, citation, linked evidence titles and the location label in reading
    order. scan_fields screens them together so steering split across fields (quality-gate-criteria.md #8.5) that no
    single field contains is caught."""
    for path, fields, _ in assertion_records(payload):
        yield path, fields


def instruction_hits(payload):
    """(path, reason) for every untrusted string or member name that trips the detector or carries a withheld marker,
    then for each assertion whose fields trip only when joined, then for each run of adjacent array entries that trip
    only when joined (so one note is never counted twice).

    Text withheld at an earlier stage stays a hit: a primary instruction/oversize marker is a field hit, a split marker
    on any of an assertion's fields is that assertion's combined hit, a run of split-marked array entries is one hit,
    any other split marker is a hit of its own, and a derived string that is exactly a marker (and not a copy of a
    primary string) is a hit. A derived string that merely contains a marker or embeds tripped primary text is the same
    note and is not counted again (quality-gate-criteria.md #8.1-#8.7)."""
    hits, tripped, pending_split = [], set(), []
    for path, text, derived in collect_scan_text(payload):
        kind = withheld_kind(text)
        if kind == SPLIT and (not derived or path.endswith("]")):
            pending_split.append((path, text))
            continue
        if kind:
            reason = OVERSIZE if kind == OVERSIZE else INSTRUCTION
        else:
            found = screen_text(text)
            if not found:
                continue
            # De-duplication happens only after the whole derived string has tripped: it is the same note when it
            # embeds a primary field that already raised a G8 hit, so the run is held either way.
            if derived and any(source in text for source in tripped):
                continue
            reason = hit_reason(found)
        hits.append((path, reason))
        if not derived:
            tripped.add(text)
    covered = set()
    for path, fields in assertion_fields(payload):
        if tripped.intersection(fields.values()):
            continue
        splits = [value for value in fields.values() if withheld_kind(value) == SPLIT]
        if splits:
            covered.update(splits)
            hits.append((path, INSTRUCTION))
            continue
        found = screen_fields(fields)
        if found:
            hits.append((path, hit_reason(found)))
    hits.extend(_array_hits(payload, tripped, covered))
    hits.extend((path, INSTRUCTION) for path, text in pending_split if text not in covered)
    return hits


def _array_hits(payload, tripped, covered):
    """Hits for runs of split-marked adjacent array entries, then for adjacent unmarked entries that trip only joined."""
    hits = []
    for _, path, child, _ in top_level_sections(payload):
        for list_path, items in iter_arrays(child, path):
            index = 0
            while index < len(items):
                if withheld_kind(items[index]) != SPLIT:
                    index += 1
                    continue
                last = index
                while last + 1 < len(items) and withheld_kind(items[last + 1]) == SPLIT:
                    last += 1
                covered.update(items[index:last + 1])
                hits.append((f"{list_path}[{index}]+[{last}]{PAIR_SUFFIX}" if last > index else f"{list_path}[{index}]", INSTRUCTION))
                index = last + 1
    used = set()
    for path, fields, refs, _ in array_pairs(payload):
        values = list(fields.values())
        slots = {(id(container), key) for container, key in refs.values()}
        if used & slots or any(is_withheld(value) or value in tripped or screen_text(value) or any(source in value for source in tripped) for value in values):
            continue
        found = screen_fields(fields)
        if found:
            used |= slots
            hits.append((path, hit_reason(found)))
    return hits


def _next_marker_number(payload):
    highest = 0
    for _, text in iter_strings(payload, "$"):
        for match in WITHHELD_PATTERN.finditer(text):
            highest = max(highest, int(match.group(1)))
    return highest + 1


def _replace_text(value, exact, embedded):
    if is_withheld(value):
        return value
    if value in exact:
        return exact[value]
    for source, marker in embedded:
        if source in value:
            value = value.replace(source, marker)
    return value


def _renamed(items, exact, embedded):
    """Rebuild an object with every flagged member name replaced by its marker, in the original order. Marker numbers
    are unique per text, so two names never collapse into one; if they ever would, the input is refused."""
    renamed = {}
    for key, child in items:
        new_key = _replace_text(key, exact, embedded)
        if new_key in renamed:
            raise InputError("withholding flagged field names would merge two fields of one object; the input is malformed")
        renamed[new_key] = _replace_withheld(child, exact, embedded)
    return renamed


def _replace_withheld(value, exact, embedded):
    if isinstance(value, dict):
        renamed = _renamed(list(value.items()), exact, embedded)
        value.clear()
        value.update(renamed)
        return value
    if isinstance(value, list):
        for index, child in enumerate(value):
            value[index] = _replace_withheld(child, exact, embedded)
        return value
    return _replace_text(value, exact, embedded) if isinstance(value, str) else value


def withhold_untrusted(payload):
    """Screen the whole payload and replace every string that trips the detector with a numbered withheld marker,
    everywhere that text appears, so no stage, output or review packet repeats it (quality-gate-criteria.md #8.7).

    Detection runs on the original text first; nothing is stripped or rewritten before screening. Then:
    - a tripped primary or derived string is replaced wherever it appears exactly, and wherever it is embedded in a
      longer string (for example the assertion citation inside assertion_mappings[].citation);
    - when only an assertion's joined fields trip, each of those fields gets a split marker wherever it appears exactly;
    - when only two adjacent array entries trip joined, both get split markers;
    - member names are screened like values, and a flagged name is replaced by its marker in place (order kept).
    Markers already present are left alone and are not new hits. The payload is updated in place. Returns
    (path, reason, derived) for each newly withheld hit, in the order instruction_hits reports them."""
    primary, derived = scan_sections(payload)
    number = [_next_marker_number(payload)]
    markers, embedded, new = {}, [], []

    def mark(text, kind):
        if text not in markers:
            markers[text] = withheld_marker(number[0], kind)
            number[0] += 1
            if kind != SPLIT:
                embedded.append(text)

    tripped = set()
    for path, text in primary:
        if is_withheld(text):
            continue
        found = screen_text(text)
        if found:
            mark(text, hit_reason(found))
            tripped.add(text)
            new.append((path, hit_reason(found), False))
    primary_texts = {text for _, text in primary}
    derived_new = []
    for path, text in derived:
        if is_withheld(text) or text in primary_texts or any(source in text for source in tripped):
            continue
        found = screen_text(text)
        if found:
            mark(text, hit_reason(found))
            derived_new.append((path, hit_reason(found), True))
    combined, split_refs = [], []
    for path, fields, refs in assertion_records(payload):
        values = list(fields.values())
        if tripped.intersection(values) or any(is_withheld(value) for value in values):
            continue
        found = screen_fields(fields)
        if found:
            # Mark the fields the note needs (removing one stops the hit), or every field when none is needed alone;
            # evidence titles are shared between assertions, so they are marked only when the note needs no field of
            # the assertion's own. No field trips alone, so identical text elsewhere in the primary sections is not
            # this note and is left as it is.
            needed = [name for name in fields if not screen_fields({other: value for other, value in fields.items() if other != name})] or list(fields)
            own = [name for name in needed if not name.startswith("evidence title")]
            split_refs.extend(refs[name] for name in (own or needed))
            combined.append((path, hit_reason(found), False))
    # Prose split across adjacent array entries: each entry passes alone, the joined pair trips. Both entries are
    # withheld with split markers; an entry already part of a flagged pair is not paired again.
    paired = set()
    for path, fields, refs, is_derived in array_pairs(payload):
        values = list(fields.values())
        slots = {(id(container), key) for container, key in refs.values()}
        if paired & slots or any(value in markers or is_withheld(value) or any(source in value for source in embedded) for value in values):
            continue
        found = screen_fields(fields)
        if found:
            paired |= slots
            split_refs.extend(refs.values())
            combined.append((path, hit_reason(found), is_derived))
    split_exact = {}
    for container, key in split_refs:
        value = container[key]
        if not is_withheld(value):
            mark(value, SPLIT)
            split_exact[value] = markers[value]
            container[key] = markers[value]
    exact = {text: marker for text, marker in markers.items() if text not in split_exact}
    ordered = sorted(((text, markers[text]) for text in embedded), key=lambda pair: -len(pair[0]))
    if exact or split_exact:
        primary_keys = {key for key, _, _, is_derived in top_level_sections(payload) if not is_derived}
        renamed = {}
        for key, child in payload.items():
            if key in UNSCANNED_KEYS:
                renamed[key] = child
                continue
            # Derived copies of split fields (for example assertion_mappings[].text) are withheld with them.
            mapping = exact if key in primary_keys else {**exact, **split_exact}
            new_key = _replace_text(key, mapping, ordered)
            if new_key in renamed:
                raise InputError("withholding flagged field names would merge two top-level fields; the input is malformed")
            renamed[new_key] = _replace_withheld(child, mapping, ordered)
        payload.clear()
        payload.update(renamed)
    return new + derived_new + combined
