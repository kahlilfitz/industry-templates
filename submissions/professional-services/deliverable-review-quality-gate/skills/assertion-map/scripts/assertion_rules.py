"""assertion_rules - shared assertion-support rules and input schemas.

Canonical copy: skills/assertion-map/scripts/assertion_rules.py. skills/gate-check/scripts/ ships a
byte-identical copy (verified by tests/check_shared_copies.py) so gate_check can recompute exactly what
assertion_map emits and never has to trust a self-declared source tag (quality-gate-criteria.md #8.4).

Type rule: a field of the wrong JSON type is a clean InputError; values are never coerced, so a string
"false" is never read as a boolean and a page label "iv" is never read as a page number.

Contract rule: every engine calls validate_contract at entry, which checks the whole payload against the
skill's own copy of contracts/ps.deliverable-review-quality-gate.v1.json (required fields, JSON types, closed
enums, ranges and provenance prefixes). A violation is an InputError raised before any output is written."""
import argparse
import functools
import json
import math
import os
import re
import sys
import tempfile
from datetime import datetime, timezone

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
# Positions (location.page, location.paragraph) count from 1; counts (sample_size, population_size, finding_count)
# from 0 (quality-gate-criteria.md #8.12).
MIN_POSITION = 1
# The largest integer every JSON reader holds exactly (an IEEE double's 2^53 - 1). A larger integer is refused at
# load, so no engine or tool ever converts one to float (OverflowError) or prints one (Python's digit limit).
MAX_JSON_INTEGER = 2 ** 53 - 1
_MAX_JSON_INTEGER_DIGITS = len(str(MAX_JSON_INTEGER))


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


def _parse_int(text):
    """JSON integers are bounded to +/-MAX_JSON_INTEGER (quality-gate-criteria.md #8.12). The digit count is checked
    before conversion, so an integer of thousands of digits never reaches int() and the value is never echoed."""
    if len(text.lstrip("-")) > _MAX_JSON_INTEGER_DIGITS or abs(int(text)) > MAX_JSON_INTEGER:
        raise InputError(f"input JSON contains an integer of {len(text.lstrip('-'))} digits outside +/-{MAX_JSON_INTEGER}; "
                         "no contract number needs one, so the input is malformed")
    return int(text)


def _parse_float(text):
    """A JSON number written with a fraction or exponent must be finite: 1e400 overflows to infinity, which is not a
    JSON number (quality-gate-criteria.md #8.12)."""
    value = float(text)
    if not math.isfinite(value):
        raise InputError("input JSON contains a number too large to represent (it overflows to infinity), which is not a valid JSON number")
    return value


def is_position(value):
    """A location page or paragraph: an integer of 1 or more (quality-gate-criteria.md #8.12)."""
    return is_integer(value) and value >= MIN_POSITION


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
MAX_ID_CHARS = 512  # far above any contract ID, engine finding ID or withheld marker (quality-gate-criteria.md #8.11)

# Letters that render like Latin letters, folded before comparing names and identifiers (finding-ID spoofing #8.4,
# recipient classification #2.5, duplicate IDs and member names #8.10-#8.11). Embedded-instruction screening uses
# steering_guard's own fold. Upper/lower case partners are added automatically.
_CONFUSABLE_BASE = {
    # Cyrillic
    "А": "A", "В": "B", "Е": "E", "І": "I", "Ј": "J", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
    "С": "C", "Т": "T", "Х": "X", "У": "Y", "Ѕ": "S", "Ԁ": "D", "Ԛ": "Q", "Ԝ": "W",
    "а": "a", "в": "b", "е": "e", "і": "i", "ј": "j", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p",
    "с": "c", "т": "t", "х": "x", "у": "y", "ѕ": "s", "ԁ": "d", "һ": "h", "ӏ": "l", "ԛ": "q", "ԝ": "w",
    # Greek
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O",
    "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X", "Ϲ": "C",
    "α": "a", "β": "b", "ε": "e", "η": "n", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p", "τ": "t",
    "υ": "u", "χ": "x", "ω": "w", "ϲ": "c", "ϳ": "j",
    # Armenian
    "Օ": "O", "օ": "o", "Ս": "U", "ս": "u", "ո": "n", "հ": "h", "ց": "g", "զ": "q", "ա": "w", "Լ": "L",
    "Տ": "S", "ı": "i",
    # Cherokee (capitals; small forms are added below through str.lower)
    "Ꭰ": "D", "Ꭱ": "R", "Ꭲ": "T", "Ꭵ": "I", "Ꭹ": "Y", "Ꭺ": "A", "Ꭻ": "J", "Ꭼ": "E", "Ꮃ": "W", "Ꮇ": "M",
    "Ꮋ": "H", "Ꮍ": "Y", "Ꮐ": "G", "Ꮒ": "H", "Ꮓ": "Z", "Ꮏ": "B", "Ꮢ": "R", "Ꮤ": "W", "Ꮥ": "S", "Ꮩ": "V",
    "Ꮪ": "S", "Ꮮ": "L", "Ꮯ": "C", "Ꮲ": "P", "Ꮶ": "K", "Ᏼ": "B",
    # Lisu
    "ꓮ": "A", "ꓐ": "B", "ꓚ": "C", "ꓓ": "D", "ꓰ": "E", "ꓝ": "F", "ꓖ": "G", "ꓧ": "H", "ꓲ": "I", "ꓙ": "J",
    "ꓗ": "K", "ꓡ": "L", "ꓟ": "M", "ꓠ": "N", "ꓳ": "O", "ꓑ": "P", "ꓣ": "R", "ꓢ": "S", "ꓔ": "T", "ꓴ": "U",
    "ꓦ": "V", "ꓪ": "W", "ꓫ": "X", "ꓬ": "Y", "ꓜ": "Z",
    # Latin small capitals and IPA look-alikes (Latin script, so only folding catches them)
    "ᴀ": "a", "ʙ": "b", "ᴄ": "c", "ᴅ": "d", "ᴇ": "e", "ꜰ": "f", "ɢ": "g", "ʜ": "h", "ɪ": "i", "ᴊ": "j",
    "ᴋ": "k", "ʟ": "l", "ᴍ": "m", "ɴ": "n", "ᴏ": "o", "ᴘ": "p", "ʀ": "r", "ꜱ": "s", "ᴛ": "t", "ᴜ": "u",
    "ᴠ": "v", "ᴡ": "w", "ʏ": "y", "ᴢ": "z", "ɑ": "a", "ɡ": "g", "ɩ": "i", "ʋ": "u",
}


def _with_case_partners(base):
    table = dict(base)
    for source, target in base.items():
        for variant in (source.lower(), source.upper()):
            if len(variant) == 1 and variant != source and variant not in table and not variant.isascii():
                table[variant] = target.lower() if variant == source.lower() else target.upper()
    return table


CONFUSABLE_MAP = _with_case_partners(_CONFUSABLE_BASE)
CONFUSABLES = str.maketrans(CONFUSABLE_MAP)
_ID_SEPARATOR_RUN = re.compile(r"[\s\-_./\\]+")


@functools.lru_cache(maxsize=8192)
def canonical_name(value):
    """The one comparison form for names and free-text labels (quality-gate-criteria.md #8.11): the look-alike map
    above, then the detector's fold (NFKC, format-character (Cf) stripping, confusables, diacritics, casefold,
    whitespace collapsing). Applied at every length; there is no length-gated fast path. Compare only; outputs keep
    the original value."""
    return sg.normalize(str(value).translate(CONFUSABLES))


@functools.lru_cache(maxsize=8192)
def canonical_id(value):
    """canonical_name plus separator folding: every run of whitespace, -, _, ., / or \\ is one space, so `A-001`,
    `a_001` and `A .001` compare equal. Used for every ID and member-name comparison, at every length."""
    return _ID_SEPARATOR_RUN.sub(" ", canonical_name(value)).strip()


def key_of(value):
    """The join key of a stated ID or key: canonical_id, or None when the value is not a string or is blank after the
    fold (for example "", "-", "_" or a zero-width character). None never equals anything: a missing, null or blank key
    names nothing, so it cannot match another missing key in a join, ownership check or reconciliation
    (quality-gate-criteria.md #8.17)."""
    if not isinstance(value, str):
        return None
    return canonical_id(value) or None


def keys_match(left, right):
    """True only when both sides state a key and the keys are equal after the canonical fold (#8.11, #8.17)."""
    key = key_of(left)
    return key is not None and key == key_of(right)


def field_name_key(name):
    """Comparison form of a member name (canonical_id). Names longer than MAX_FIELD_NAME_CHARS are refused at load."""
    return canonical_id(name)


ENGINE_ID_PREFIXES = {"am": AM_ENGINE, "gc": "engine:gate_check", "sr": "engine:severity_rank"}


def engine_id_owner(finding_id):
    """The engine tag whose finding-ID prefix (AM-, GC-, SR-) finding_id carries after the canonical fold, so `gc_G8-x`,
    `ＧＣ-x` or a G and C split by a zero-width character is still engine-owned (quality-gate-criteria.md #8.4); None otherwise. Callers pass the raw
    ID, before any withholding, so a flagged ID keeps its owner."""
    if not isinstance(finding_id, str):
        return None
    head = re.match(r"[^\W_]+", canonical_id(finding_id))
    return ENGINE_ID_PREFIXES.get(head.group(0)) if head else None


AM_SPOOF_ID = "AM-G8-engine-id-spoof"
AM_SPOOF_ESCALATION = ("G8: a finding supplied with the review input reused a finding ID that assertion_map recomputes without "
                       "matching the recomputation and was replaced by the recomputed finding - hold for reviewing partner/QRM "
                       "(quality-gate-criteria.md #8.4)")


def am_spoof_finding():
    """The G8 release blocker assertion_map emits when a supplied finding collides with one it recomputes (#8.4). Fixed
    text, so gate_check and severity_rank can verify it exactly and a re-run reproduces it."""
    return {"finding_id": AM_SPOOF_ID, "gate_id": "G8", "severity": "release_blocker",
            "title": "Supplied finding reused an assertion_map finding ID",
            "detail": "A finding supplied with the review input used a finding ID that assertion_map recomputes from the assertions and evidence index but did not match the recomputation; it was replaced by the recomputed finding. Engine findings cannot be replaced, removed or downgraded by input data.",
            "location": {"section": "Upstream findings", "page": None, "paragraph": None, "label": "findings[] supplied with the review input"},
            "criteria_section": "quality-gate-criteria.md #8.4", "confidence": 0.99, "source": AM_ENGINE,
            "citation": "quality-gate-criteria.md #8.1, #8.4; severity-rules.md #1.1"}


def is_am_spoof_id(finding_id):
    return isinstance(finding_id, str) and canonical_id(finding_id) == canonical_id(AM_SPOOF_ID)


def merge_recomputed_findings(supplied, raw_supplied, recomputed):
    """Combine supplied findings with the AM- findings assertion_map recomputes (quality-gate-criteria.md #8.4).

    IDs are compared in canonical form (canonical_id). A supplied finding whose raw ID is assertion_map-owned and
    collides with a recomputed finding (or with the AM spoof hold) stands only when it is exactly that finding; any
    other copy is dropped, so the genuine finding replaces it and the ID is never duplicated. Every other supplied
    finding passes through for gate_check to screen. Missing recomputed findings are appended in assertion order, so a
    re-run on assertion_map's own output reproduces it. `raw_supplied[i]` is findings[i] before withholding, so a
    flagged ID keeps its owner. Returns (findings, number of supplied findings dropped as spoofed)."""
    reserved = {canonical_id(item["finding_id"]): item for item in recomputed}
    reserved[canonical_id(AM_SPOOF_ID)] = am_spoof_finding()
    kept, spoofed = [], 0
    for index, item in enumerate(supplied):
        raw = raw_supplied[index] if index < len(raw_supplied) and isinstance(raw_supplied[index], dict) else item
        raw_id = raw.get("finding_id") if isinstance(raw, dict) else None
        key = canonical_id(raw_id) if isinstance(raw_id, str) else None
        if key in reserved and engine_id_owner(raw_id) == AM_ENGINE and item != reserved[key]:
            spoofed += 1
            continue
        kept.append(item)
    present = {canonical_id(item["finding_id"]) for item in kept if isinstance(item, dict) and isinstance(item.get("finding_id"), str)}
    for item in recomputed:
        if canonical_id(item["finding_id"]) not in present:
            kept.append(item)
    if spoofed and canonical_id(AM_SPOOF_ID) not in present:
        kept.append(am_spoof_finding())
    return kept, spoofed


def canonical_tag(source):
    """Comparison form of a `prefix:slug` source tag: canonical_id on each side of the first colon (after NFKC, so a
    fullwidth colon counts), so `Engine :gate_check`, `ENGINE:gate-check` and a tag split by a zero-width character all
    read as `engine:gate check` (quality-gate-criteria.md #8.4, #8.11). None for a non-string."""
    if not isinstance(source, str):
        return None
    prefix, separator, slug = canonical_name(source).partition(":")
    return f"{canonical_id(prefix)}:{canonical_id(slug)}" if separator else canonical_id(prefix)


def is_engine_tag(source):
    """True when a source claims to be an engine (`engine:<anything>` in canonical form)."""
    tag = canonical_tag(source)
    return tag is not None and tag.startswith("engine:")


def is_id_field(parts):
    """True when the path ends at an ID: a member named *_id, or an entry of a member named *_ids."""
    if parts and isinstance(parts[-1], str):
        return canonical_id(parts[-1]).endswith(" id")
    return len(parts) > 1 and isinstance(parts[-1], int) and isinstance(parts[-2], str) and canonical_id(parts[-2]).endswith(" ids")


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
    #8.10), identifiers longer than MAX_ID_CHARS (#8.11: no ID needs that length, so none is ever compared at it), and
    lone UTF-16 surrogates (for example "\\ud800": not Unicode text, cannot be written as UTF-8)."""
    stack = [(value, ())]
    while stack:
        item, parts = stack.pop()
        if isinstance(item, _OverlongFieldName):
            raise InputError(f"{format_path(parts)} has a field name longer than {MAX_FIELD_NAME_CHARS} characters; no contract field needs one, so the input is malformed")
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
            if len(item) > MAX_ID_CHARS and is_id_field(parts):
                raise InputError(f"{format_path(parts)} is an identifier longer than {MAX_ID_CHARS} characters; no contract ID needs one, so the input is malformed")


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


# RFC 3339 date-time (the contract's "format": "date-time"), ASCII digits only: 2026-10-01T00:00:00Z or with an offset.
TIMESTAMP = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.[0-9]{1,9})?(?:Z|[+-]([0-9]{2}):([0-9]{2}))")


def is_timestamp(value):
    """True when value is an RFC 3339 date-time with a real calendar date and time and a Z or +/-HH:MM offset
    (quality-gate-criteria.md #8.14). Dates alone, free text and impossible dates such as month 13 are not."""
    match = TIMESTAMP.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        return False
    try:
        datetime(*(int(part) for part in match.group(1, 2, 3, 4, 5, 6)))
    except ValueError:
        return False
    return match.group(7) is None or (int(match.group(7)) < 24 and int(match.group(8)) < 60)


def validate_generated_at(value):
    """The --generated-at flag, checked exactly as the contract checks provenance.generated_at."""
    if value is not None and not is_timestamp(value):
        raise InputError("--generated-at must be an ISO-8601 (RFC 3339) date-time such as 2026-10-01T00:00:00Z")
    return value


def record_engine(payload, tag, generated_at=None):
    """Append the engine/version tag to provenance.engines unless this engine was the last to run (idempotent re-run),
    and stamp generated_at: the --generated-at value, else the value already present, else the current UTC time. The
    review packet renders both, so no engine output ever lacks them (quality-gate-criteria.md #8.14)."""
    provenance = payload.setdefault("provenance", {})
    if not isinstance(provenance, dict):
        raise InputError("provenance must be an object when present")
    engines = provenance.setdefault("engines", [])
    if not isinstance(engines, list):
        raise InputError("provenance.engines must be an array when present")
    if engines[-1:] != [tag]:
        engines.append(tag)
    if generated_at:
        provenance["generated_at"] = generated_at
    elif not (isinstance(provenance.get("generated_at"), str) and provenance["generated_at"].strip()):
        provenance["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return provenance


def os_reason(exc):
    """An OS error without its file name: the exception type and the OS reason text only. str(exc) repeats the path,
    and a file name is untrusted input (quality-gate-criteria.md #8.9)."""
    reason = getattr(exc, "strerror", None)
    return f"{type(exc).__name__}: {reason}" if isinstance(reason, str) and reason else type(exc).__name__


def load_json_file(path, label="input JSON"):
    """Load engine input. Strict JSON only: NaN/Infinity constants, numbers that overflow to infinity, integers outside
    +/-MAX_JSON_INTEGER, lone surrogates, duplicate member names and over-deep nesting are input errors, so no engine
    ever processes or writes a value that is not valid JSON. Errors name the input by the fixed, trusted `label`
    (for example "review input"), never by its path or file name (#8.9)."""
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle, parse_constant=_reject_constant, parse_int=_parse_int, parse_float=_parse_float,
                                object_pairs_hook=_object_pairs)
    except OSError as exc:
        raise InputError(f"could not read the {label} ({os_reason(exc)})") from None
    except UnicodeDecodeError as exc:
        raise InputError(f"the {label} is not valid UTF-8 (first bad byte at offset {exc.start})") from None
    except json.JSONDecodeError as exc:
        raise InputError(f"the {label} is not valid JSON ({exc.msg} at line {exc.lineno}, column {exc.colno})") from None
    except RecursionError as exc:
        raise InputError(f"the {label} is nested too deeply to process safely") from exc
    check_depth(payload)
    _check_loaded(payload)
    return payload


def write_json_atomic(path, payload, label="output"):
    """Serialise the whole output first, then write it to a temporary file beside the target and os.replace it into
    place. On any error the output path is neither created nor truncated. Errors name the output by the fixed `label`,
    never by its path or file name (#8.9)."""
    try:
        data = (json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    except ValueError as exc:  # includes UnicodeEncodeError and non-finite numbers
        raise InputError(f"the {label} could not be serialised as valid JSON ({type(exc).__name__}), so nothing was written") from None
    target = os.path.abspath(path)
    try:
        handle, temp = tempfile.mkstemp(dir=os.path.dirname(target), prefix=f".{os.path.basename(target)}.", suffix=".tmp")
    except OSError as exc:
        raise InputError(f"could not write the {label} ({os_reason(exc)})") from None
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
            raise InputError(f"could not write the {label} ({os_reason(exc)})") from None
        raise


class EngineArgumentParser(argparse.ArgumentParser):
    """argparse that never repeats a command-line value, such as a file name, in an error (#8.9). Only argparse's own
    content-free messages (a missing required flag, a flag with no value) pass; anything else, such as an unrecognised
    argument or an ambiguous abbreviation, is reported without the text that was typed. `prog` is the engine's fixed
    script name, never sys.argv[0]."""

    SAFE_ERROR = re.compile(r"the following arguments are required: --[a-z-]+(?:, --[a-z-]+)*|argument --[a-z-]+: expected one argument")

    def error(self, message):
        if not self.SAFE_ERROR.fullmatch(message):
            message = "unrecognised or malformed command-line arguments (the values are not repeated; see --help)"
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")


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
        if value is not None and not is_position(value):
            raise InputError(f"{label}: location.{key} must be an integer of {MIN_POSITION} or more, or null, got "
                             f"{describe(value) if not is_integer(value) else 'an integer below ' + str(MIN_POSITION)}; {PAGE_LABEL_HINT}")
    return location


def validate_assertion(assertion, index):
    if not isinstance(assertion, dict):
        raise InputError(f"assertions[{index}] must be an object")
    label = f"assertions[{index}]"
    require_text(assertion, "assertion_id", label)
    if is_am_spoof_id(f"AM-{assertion['assertion_id']}"):
        raise InputError(f"{label}.assertion_id is reserved: its assertion_map finding ID would be the engine's own spoof hold ({AM_SPOOF_ID}); choose another assertion ID")
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
    for index, assertion in enumerate(assertions):
        validate_assertion(assertion, index)
    require_unique_ids(assertions, "assertions", "assertion_id")


def evidence_index(evidence_set):
    """Evidence items keyed by canonical_id(evidence_id), so a reference spelled `ev_001` finds `EV-001`; the items
    keep their original IDs. Duplicate IDs (exact or after the fold) are refused (quality-gate-criteria.md #8.11)."""
    if not isinstance(evidence_set, list):
        raise InputError("evidence_set must be an array")
    for index, item in enumerate(evidence_set):
        if not isinstance(item, dict):
            raise InputError(f"evidence_set[{index}] must be an object with evidence_id")
        label = f"evidence_set[{index}]"
        require_text(item, "evidence_id", label)
        for key in ("type", "title", "citation", "source"):
            require_text(item, key, label, required=False, allow_blank=True)
        require_confidence(item, label)
    require_unique_ids(evidence_set, "evidence_set", "evidence_id")
    return {canonical_id(item["evidence_id"]): item for item in evidence_set}


def evidence_for(evidence_by_id, evidence_id):
    """The evidence item an assertion's evidence_ids entry names, compared in canonical form; None when absent."""
    key = key_of(evidence_id)
    return evidence_by_id.get(key) if key is not None else None


SUBJECT_FIELDS = ("engagement_id", "deliverable_id")


def review_subject(payload):
    """The subject every linked record must share: the review's engagement_id and deliverable.deliverable_id, as given
    (quality-gate-criteria.md #8.15)."""
    payload = payload if isinstance(payload, dict) else {}
    deliverable = payload.get("deliverable") if isinstance(payload.get("deliverable"), dict) else {}
    return {"engagement_id": payload.get("engagement_id"), "deliverable_id": deliverable.get("deliverable_id")}


def foreign_subject(record, subject):
    """The subject fields (engagement_id, deliverable_id) on which a linked record names another engagement or
    deliverable than the review (#8.15); [] when it shares the subject. An absent or null field names no subject, so the
    record is the review's own. Values are compared by keys_match (#8.11): a value blank after the fold on either side
    states no subject to compare, so it never matches and counts as foreign (#8.17). A value that is withheld on either side
    cannot be verified, and every copy of one flagged text carries the same marker, so a withheld value never matches:
    it counts as foreign and holds (#8.13)."""
    if not isinstance(record, dict) or not isinstance(subject, dict):
        return []
    fields = []
    for key in SUBJECT_FIELDS:
        value, own = record.get(key), subject.get(key)
        if value is None:
            continue
        if (not isinstance(value, str) or not isinstance(own, str) or contains_withheld(value) or contains_withheld(own)
                or not keys_match(value, own)):
            fields.append(key)
    return fields


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
        except OSError as exc:
            raise InputError(f"contract schema could not be loaded from the skill's contracts folder ({os_reason(exc)})") from None
        except ValueError as exc:
            raise InputError(f"contract schema in the skill's contracts folder is not valid JSON ({type(exc).__name__})") from None
    return _CONTRACT_SCHEMA[0]


_TYPE_PHRASES = {"object": "an object", "array": "an array", "string": "a string", "boolean": "true or false", "null": "null", "number": "a number", "integer": "an integer"}


def _type_phrase(types, node):
    """Plain-English expected type for a contract message, e.g. `an integer of 1 or more, or null`."""
    phrases = [f"an integer of {node['minimum']} or more" if name == "integer" and "minimum" in node else _TYPE_PHRASES[name] for name in types]
    if len(phrases) == 1:
        return phrases[0]
    joiner = ", or " if any(" or " in phrase for phrase in phrases) else " or "
    return joiner.join(phrases)


_ID_PATH = re.compile(r"_id$|_ids\[[0-9]+\]$")


def _is_position_path(path):
    return path.endswith((".location.page", ".location.paragraph"))


def _contract_errors(value, node, path, root):
    """Yield the first violation of `node` (a draft-07 subset: $ref, const, oneOf, type, enum, required, properties,
    items, minLength, pattern, minimum, maximum, and format: date-time checked by is_timestamp). x-unrecognised: hold marks an enum the gates judge themselves: any
    string or null passes here and the gate holds on an unrecognised value. x-normalise: provenance compares a source
    after normalise_provenance, as the evidence rule does."""
    if "$ref" in node:
        node = root["definitions"][node["$ref"].rsplit("/", 1)[-1]]
    if "const" in node and value != node["const"]:
        yield f"{path} must be the constant {node['const']}, got {describe(value)}"
        return
    if "oneOf" in node:
        if sum(1 for option in node["oneOf"] if next(_contract_errors(value, option, path, root), None) is None) != 1:
            yield f"{path} has the wrong shape (expected exactly one of {', '.join(str(option.get('type')) for option in node['oneOf'])}), got {describe(value)}"
        return
    types = node.get("type")
    if types is not None:
        types = [types] if isinstance(types, str) else types
        if not any(_JSON_TYPES[name](value) for name in types):
            yield f"{path} must be {_type_phrase(types, node)}, got {describe(value)}" + (f"; {PAGE_LABEL_HINT}" if _is_position_path(path) else "")
            return
    if "enum" in node and value not in node["enum"]:
        if node.get("x-unrecognised") == "hold":
            if not (value is None or isinstance(value, str)):
                yield f"{path} must be a string or null, got {describe(value)}"
        else:
            yield f"{path} must be one of {', '.join(node['enum'])}, got {describe(value)}"
        return
    if isinstance(value, str):
        if node.get("format") == "date-time":
            # Checked before the withheld skip: a genuine timestamp never trips the screen, so a marker here is not one.
            if not is_timestamp(value):
                yield f"{path} must be an ISO-8601 (RFC 3339) date-time such as 2026-10-01T00:00:00Z, got {describe(value)}"
            return
        if is_withheld(value):
            # Withheld marker: the embedded-instruction screen replaced text that was validated raw before withholding.
            return
        if len(value.strip()) < node.get("minLength", 0):
            yield f"{path} must be a non-blank string"
        elif node.get("minLength") and _ID_PATH.search(path) and key_of(value) is None:
            # A blank key names nothing and must never equal another blank key in a join (#8.17).
            yield f"{path} is blank after Unicode, case and separator folding; IDs must state a value"
        elif "pattern" in node:
            candidate = normalise_provenance(value) if node.get("x-normalise") == "provenance" else value
            if not re.search(node["pattern"], candidate):
                yield f"{path} ({describe(value)}) does not match the contract format {node['pattern']}"
    elif is_number(value):
        if value < node.get("minimum", value) or value > node.get("maximum", value):
            if "maximum" not in node:
                yield f"{path} must be {node['minimum']} or more, got a number below that"
            else:
                yield f"{path} must be between {node.get('minimum')} and {node.get('maximum')}, got a number outside that range"
    elif isinstance(value, dict):
        for field in node.get("required", ()):
            if field not in value:
                yield f"{path} is missing required field {field}"
                return
        properties = node.get("properties", {})
        if properties:
            # A member that differs from a contract field only in case, Unicode form or separators would be ignored
            # by every exact lookup while looking like that field to a reader (quality-gate-criteria.md #8.11).
            canonical = {canonical_id(name): name for name in properties}
            for member in value:
                if member not in properties and canonical_id(member) in canonical:
                    yield f"{path}.{path_key(member)} is a variant spelling of the contract field {canonical[canonical_id(member)]}; use the exact field name"
                    return
        for field, child in properties.items():
            if field in value:
                yield from _contract_errors(value[field], child, f"{path}.{field}", root)
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


def require_unique_ids(items, label, id_key, allow_identical=False, prefix="", skip=None):
    """Refuse two entries whose IDs are equal exactly or after the detector's fold (Unicode, case, separators), so a
    lookup keyed by ID can never let one entry overwrite or mask another. With allow_identical, entries that are equal
    in every field are not a conflict: nothing differs, so nothing can be hidden. The message names positions only."""
    positions = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not isinstance(item.get(id_key), str) or (skip and skip(item)):
            continue
        key = canonical_id(item[id_key])
        if key in positions:
            first = positions[key]
            if allow_identical and items[first] == item:
                continue
            raise InputError(f"{prefix}{label}[{index}].{id_key} duplicates {label}[{first}].{id_key} (equal exactly or after Unicode, case and separator folding); IDs must be unique so no entry can overwrite or mask another")
        positions[key] = index


# Lists of keys an engine matches entries against (quality-gate-criteria.md #8.11, #8.17). A repeat is refused like a
# repeated ID, so one key can never count twice or stand in for another: evidence_ids within each assertion and
# mapping, and these deliverable lists.
EVIDENCE_REFERENCE_SECTIONS = ("assertions", "assertion_mappings")
DELIVERABLE_KEY_LISTS = ("required_language", "present_language", "present_disclaimer_types", "client_aliases")


def require_unique_keys(values, label):
    """Refuse two entries of a key list that are equal exactly or after the canonical fold. Withheld markers are
    skipped: every copy of one flagged text carries the same marker, and the screen already holds it (#8.13)."""
    positions = {}
    for index, value in enumerate(values):
        if contains_withheld(value):
            continue
        key = key_of(value)
        if key is None:
            continue
        if key in positions:
            raise InputError(f"contract violation: {label}[{index}] duplicates {label}[{positions[key]}] (equal exactly or after Unicode, case and separator folding); each entry must be unique so none can count twice or mask another")
        positions[key] = index


def validate_unique_keys(payload):
    for field in EVIDENCE_REFERENCE_SECTIONS:
        items = payload.get(field)
        for index, item in enumerate(items if isinstance(items, list) else []):
            if isinstance(item, dict) and isinstance(item.get("evidence_ids"), list):
                require_unique_keys(item["evidence_ids"], f"{field}[{index}].evidence_ids")
    deliverable = payload.get("deliverable")
    for field in DELIVERABLE_KEY_LISTS:
        if isinstance(deliverable, dict) and isinstance(deliverable.get(field), list):
            require_unique_keys(deliverable[field], f"deliverable.{field}")


def validate_unique_ids(payload):
    validate_unique_keys(payload)
    for path, id_key in ID_KEYED_ARRAYS:
        items = payload
        for part in path:
            items = items.get(part) if isinstance(items, dict) else None
        if isinstance(items, list):
            # An engine-owned finding ID (AM-, GC-, SR-) is not refused for colliding: every stage recomputes engine
            # findings, keeps the genuine one and holds any other copy as a spoof (quality-gate-criteria.md #8.4).
            skip = (lambda item: engine_id_owner(item.get(id_key)) is not None) if path == ("findings",) else None
            require_unique_ids(items, ".".join(path), id_key, allow_identical=path == ("findings",), prefix="contract violation: ", skip=skip)


def contains_withheld(value):
    """True when value is a string carrying a withheld marker. Withheld text decides nothing
    (quality-gate-criteria.md #8.13): no rule reads it to match evidence, satisfy a requirement, identify the client,
    place a finding or set a severity. It produces the G8 hold and nothing else. This is the one predicate for both
    sides: every rule that sets text aside uses it, and instruction_hits raises a G8 hit for every string it is true of
    (an exact marker, a forged marker, or an embedded marker whose exact twin is itself a hit), so setting text aside
    can never lower a verdict without a G8 release blocker (#8.7)."""
    return isinstance(value, str) and WITHHELD_PATTERN.search(value) is not None


def marker_texts(value):
    """Every marker-shaped substring of value, in order."""
    return [match.group(0) for match in WITHHELD_PATTERN.finditer(value)] if isinstance(value, str) else []


def exact_markers(payload):
    """Every string in payload (member names included) that is exactly a withheld marker."""
    return {text for _, text in iter_strings(payload, "$") if is_withheld(text)}


def forged_marker(value, emitted):
    """True when value carries a marker-shaped substring the engines cannot have produced (quality-gate-criteria.md
    #8.7). In the raw review input (emitted is None) every marker, exact or embedded, is forged: only an engine
    withholds text. At a later stage an exact marker is accepted as an engine marker (and is itself a G8 hit), and a
    marker inside a longer string is genuine only when the same marker also stands alone in the payload (`emitted`, from
    exact_markers), as the engines' embedded replacement always leaves it. Anything else is tampering and a G8 hold."""
    if not contains_withheld(value):
        return False
    if emitted is None:
        return True
    return not is_withheld(value) and any(marker not in emitted for marker in marker_texts(value))


def is_withheld_reference(evidence_by_id, evidence_id):
    """True when an evidence_ids entry, or the evidence_id it resolves to, was withheld (#8.13). Every copy of one
    flagged text carries the same marker, so without this a withheld reference would still link to withheld evidence."""
    if contains_withheld(evidence_id):
        return True
    item = evidence_for(evidence_by_id, evidence_id)
    return item is not None and contains_withheld(item.get("evidence_id"))


def withheld_references(assertion, evidence_by_id):
    return [eid for eid in assertion.get("evidence_ids") or [] if is_withheld_reference(evidence_by_id, eid)]


def is_foreign_reference(evidence_by_id, evidence_id, subject):
    """True when an evidence_ids entry resolves to an evidence item that names another engagement or deliverable (#8.15)."""
    if is_withheld_reference(evidence_by_id, evidence_id):
        return False
    return bool(foreign_subject(evidence_for(evidence_by_id, evidence_id), subject))


def foreign_references(assertion, evidence_by_id, subject):
    return [eid for eid in assertion.get("evidence_ids") or [] if is_foreign_reference(evidence_by_id, eid, subject)]


def linked_evidence(assertion, evidence_by_id, subject=None):
    """The evidence items an assertion's references resolve to. A withheld reference never links (#8.13), and neither
    does evidence of another engagement or deliverable (#8.15); either makes the declared support unverifiable (classify)."""
    found = (evidence_for(evidence_by_id, eid) for eid in assertion.get("evidence_ids") or []
             if not is_withheld_reference(evidence_by_id, eid) and not is_foreign_reference(evidence_by_id, eid, subject))
    return [item for item in found if item is not None]


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


def linked_evidence_citation(assertion, evidence_by_id, subject=None):
    citations = []
    for evidence_id in assertion.get("evidence_ids") or []:
        if is_withheld_reference(evidence_by_id, evidence_id):
            citations.append("withheld linked evidence reference (not used)")
            continue
        if is_foreign_reference(evidence_by_id, evidence_id, subject):
            citations.append("linked evidence of another engagement or deliverable (not used)")
            continue
        evidence = evidence_for(evidence_by_id, evidence_id)
        citations.append(evidence.get("citation", f"evidence {evidence_id}") if evidence else f"missing linked evidence {evidence_id}")
    return "; ".join(citations) if citations else "no linked evidence found"


def location_label(location):
    return f"p{location.get('page')}, {location.get('section')}, paragraph {location.get('paragraph')}"


def is_definitive_conclusion(assertion):
    if assertion.get("limitation_present") is True:
        return False
    text = assertion.get("text", "")
    # Withheld text is never read for keywords (#8.13); only the structured flags decide.
    text = "" if contains_withheld(text) or not isinstance(text, str) else text.lower()
    definitive_terms = (" should ", "we conclude", "will ", "all ", "full ", "estate-wide", "applies across", "national ")
    return (
        assertion.get("hedging_present") is not True
        or assertion.get("scope_aligned") is False
        or assertion.get("population_size") is not None
        or any(term in f" {text} " for term in definitive_terms)
    )


FOREIGN_SUPPORT_SECTION = "quality-gate-criteria.md #1.1; quality-gate-criteria.md #8.15"


def foreign_rationale(foreign_ids):
    return (f"{len(foreign_ids)} linked evidence item(s) name another engagement or deliverable (engagement_id or "
            "deliverable_id differs from this review's, or cannot be verified), so they are not used and the declared "
            "support cannot be verified; hold for reviewing partner/QRM")


def classify(assertion, evidence, missing_ids=(), withheld_ids=(), foreign_ids=()):
    klass = assertion.get("class")
    if foreign_ids:
        # Evidence of another engagement or deliverable is never a basis for this review (quality-gate-criteria.md #8.15).
        confidence = 0.0 if evidence is None else min(float(assertion.get("confidence", 0.0)), float(evidence.get("confidence", 0.0)))
        return "unsupported", confidence, foreign_rationale(foreign_ids), FOREIGN_SUPPORT_SECTION
    if evidence is None:
        if not assertion.get("evidence_ids"):
            return "unsupported", 0.0, "No evidence IDs were linked to the assertion", "quality-gate-criteria.md #1.1"
        if withheld_ids:
            # A withheld reference is never matched (quality-gate-criteria.md #8.13), so the declared support cannot be verified.
            return "unsupported", 0.0, f"{len(withheld_ids)} linked evidence ID(s) were withheld by the embedded-instruction screen and no other linked evidence was found, so the declared support cannot be verified", "quality-gate-criteria.md #1.1; quality-gate-criteria.md #8.13"
        return "unsupported", 0.0, "No linked evidence item was found in the evidence index", "quality-gate-criteria.md #1.1"
    confidence = min(float(assertion.get("confidence", 0.0)), float(evidence.get("confidence", 0.0)))
    if missing_ids:
        # Declared support must exist: a dangling evidence reference is never ignored (quality-gate-criteria.md #1.1).
        return "unsupported", confidence, f"{len(missing_ids)} linked evidence ID(s) are not in the evidence index, so the declared support cannot be verified", "quality-gate-criteria.md #1.1"
    if withheld_ids:
        # Like a dangling reference, a withheld one is never ignored and never matched (#1.1, #8.13).
        return "unsupported", confidence, f"{len(withheld_ids)} linked evidence ID(s) were withheld by the embedded-instruction screen, so the declared support cannot be verified", "quality-gate-criteria.md #1.1; quality-gate-criteria.md #8.13"
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


def map_assertion(assertion, evidence_by_id, subject=None):
    """Return (mapping, AM finding or None, escalation or None) exactly as assertion_map emits them. `subject` is
    review_subject(payload): linked evidence of another engagement or deliverable is not used and holds (#8.15)."""
    evidence = best_evidence(assertion, linked_evidence(assertion, evidence_by_id, subject))
    withheld_ids = withheld_references(assertion, evidence_by_id)
    foreign_ids = foreign_references(assertion, evidence_by_id, subject)
    missing_ids = [eid for eid in assertion.get("evidence_ids") or [] if evidence_for(evidence_by_id, eid) is None and eid not in withheld_ids]
    status, support_score, rationale, criteria_section = classify(assertion, evidence, missing_ids, withheld_ids, foreign_ids)
    mapping = {
        "assertion_id": assertion["assertion_id"], "class": assertion["class"], "text": assertion["text"],
        "location": assertion["location"], "evidence_ids": assertion.get("evidence_ids") or [],
        "best_evidence_id": evidence.get("evidence_id") if evidence else None, "support_status": status,
        "support_score": round(support_score, 2), "rationale": rationale, "criteria_section": criteria_section,
        "confidence": round(support_score, 2), "source": AM_ENGINE,
        "citation": f"{assertion['citation']}; {linked_evidence_citation(assertion, evidence_by_id, subject)}; {criteria_section}"
    }
    if status not in {"unsupported", "limited"}:
        return mapping, None, None
    severity = "release_blocker" if foreign_ids or (
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
# Marker numbers are 1 to 9 digits, so reading one back (int) is always bounded; a longer number is not a marker.
WITHHELD_PATTERN = re.compile(r"\[withheld ([1-9][0-9]{0,8})(?: \((oversize|split)\))?: [a-z -]+; see the G8 finding\]")
MAX_MARKER_NUMBER = 999_999_999


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


ARRAY_WINDOW = 8


def _entries(items, first, last):
    """(fields, refs) for items[first..last]: fields maps 'entry N' to the text, refs to the (container, index)."""
    names = [f"entry {index}" for index in range(first, last + 1)]
    return dict(zip(names, items[first:last + 1])), dict(zip(names, ((items, index) for index in range(first, last + 1))))


def _run_trips(items, first, last):
    return screen_fields(_entries(items, first, last)[0])


def array_runs(payload, breaks):
    """Yield (path, fields, refs, derived, found) for each run of adjacent array entries that trips only when joined, so
    prose split across any number of entries is screened as one text (quality-gate-criteria.md #8.5).

    Entries for which breaks(value) is true (non-strings, blanks, and text already flagged or withheld) split an array
    into runs. Each run is screened in sliding windows of up to ARRAY_WINDOW entries, and, when it is longer than that,
    joined whole, so the cost stays linear in the array. A tripping window is narrowed to the entries the note needs
    (dropping an end entry stops the hit); a whole-run hit that no window shows withholds the whole run."""
    for _, path, child, derived in top_level_sections(payload):
        for list_path, items in iter_arrays(child, path):
            start = 0
            while start < len(items):
                if breaks(items[start]):
                    start += 1
                    continue
                end = start
                while end + 1 < len(items) and not breaks(items[end + 1]):
                    end += 1
                yield from _run_hits(list_path, items, start, end, derived)
                start = end + 1


def _run_hits(list_path, items, start, end, derived):
    if end == start:
        return
    first, flagged = start, False
    while first < end:
        last = min(first + ARRAY_WINDOW - 1, end)
        if _run_trips(items, first, last):
            low, high = first, last
            while high - low > 1 and _run_trips(items, low + 1, high):
                low += 1
            while high - low > 1 and _run_trips(items, low, high - 1):
                high -= 1
            fields, refs = _entries(items, low, high)
            flagged = True
            yield f"{list_path}[{low}]+[{high}]{PAIR_SUFFIX}", fields, refs, derived, screen_fields(fields)
            first = high + 1
            continue
        if last == end:
            break
        first += 1
    if not flagged and end - start + 1 > ARRAY_WINDOW:
        fields, refs = _entries(items, start, end)
        found = screen_fields(fields)
        if found:
            yield f"{list_path}[{start}]+[{end}]{PAIR_SUFFIX}", fields, refs, derived, found


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
    evidence = {key_of(item["evidence_id"]): item for item in payload.get("evidence_set") or [] if isinstance(item, dict) and key_of(item.get("evidence_id")) is not None}
    for index, assertion in enumerate(payload.get("assertions") or []):
        if not isinstance(assertion, dict):
            continue
        refs = {"text": (assertion, "text"), "citation": (assertion, "citation")}
        for position, evidence_id in enumerate(assertion.get("evidence_ids") or []):
            # The same canonical lookup map_assertion uses, so every title that can support a claim is screened with it.
            linked = evidence_for(evidence, evidence_id)
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
    emitted = exact_markers(payload)
    for path, text, derived in collect_scan_text(payload):
        kind = withheld_kind(text)
        if kind == SPLIT and (not derived or path.endswith("]")):
            pending_split.append((path, text))
            continue
        if kind:
            reason = OVERSIZE if kind == OVERSIZE else INSTRUCTION
        elif forged_marker(text, emitted):
            # A marker the engines cannot have produced (embedded with no exact twin): tampering, held under G8 (#8.7).
            reason = INSTRUCTION
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


# Top-level sections every stage rebuilds from recomputation (assertion_mappings, gate_results) or regenerates
# (ranked_findings, release_readiness); a placeholder there is bound by that recomputation, not by a hold.
ENGINE_REBUILT_SECTIONS = ("assertion_mappings", "gate_results", "ranked_findings", "release_readiness")


def placeholder_paths(payload, engine_finding, engine_escalation):
    """Paths of every string (member names included) carrying a withheld marker in a position no stage recomputes:
    findings that are not engine findings (`engine_finding(index, item)` false), escalations no engine derived
    (`engine_escalation(entry)` false), provenance and any other top-level note. Primary sections and top-level scalars
    are screened as primary text, and engine positions are bound by recomputation (quality-gate-criteria.md #8.18)."""
    paths = []

    def collect(value, path):
        paths.extend(found for found, text in iter_strings(value, path) if contains_withheld(text))

    for index, item in enumerate(payload.get("findings") or []):
        if not engine_finding(index, item):
            collect(item, f"$.findings[{index}]")
    for index, entry in enumerate(payload.get("escalations") or []):
        if not engine_escalation(entry):
            collect(entry, f"$.escalations[{index}]")
    for key, path, child, is_derived in top_level_sections(payload):
        if is_derived and key not in ("findings", "escalations") and key not in ENGINE_REBUILT_SECTIONS:
            collect(child, path)
    return paths


def unbound_placeholder_hits(paths, holds):
    """(path, INSTRUCTION) for each placeholder path no hold names exactly (`holds(path)` false), in order and once.
    A hold elsewhere in the document never binds a newly placed placeholder: each needs its own (#8.18)."""
    hits = []
    for path in paths:
        if not holds(path) and (path, INSTRUCTION) not in hits:
            hits.append((path, INSTRUCTION))
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
    for path, fields, refs, _, found in array_runs(payload, lambda value: not (isinstance(value, str) and value.strip()) or contains_withheld(value) or value in tripped or bool(screen_text(value)) or any(source in value for source in tripped)):
        slots = {(id(container), key) for container, key in refs.values()}
        if used & slots:
            continue
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
    # Exact first: in the raw input a forged marker is itself the text being withheld.
    if value in exact:
        return exact[value]
    if is_withheld(value):
        return value
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


def withhold_untrusted(payload, raw_input=False):
    """Screen the whole payload and replace every string that trips the detector with a numbered withheld marker,
    everywhere that text appears, so no stage, output or review packet repeats it (quality-gate-criteria.md #8.7).

    Detection runs on the original text first; nothing is stripped or rewritten before screening. Then:
    - a tripped primary or derived string is replaced wherever it appears exactly, and wherever it is embedded in a
      longer string (for example the assertion citation inside assertion_mappings[].citation);
    - a string carrying a forged marker (forged_marker: any marker at all in the raw review input, raw_input=True, or
      at a later stage a marker inside a longer string with no exact twin) is tampering: it is withheld whole under a
      new marker and is a G8 hit, so input can never supply a marker that sets text aside without a hold;
    - when only an assertion's joined fields trip, each of those fields gets a split marker wherever it appears exactly;
    - when only a run of adjacent array entries trips joined (array_runs), every entry of the run gets a split marker;
    - member names are screened like values, and a flagged name is replaced by its marker in place (order kept).
    Engine markers already present are left alone and are not new hits. The payload is updated in place. Returns
    (path, reason, derived) for each newly withheld hit, in the order instruction_hits reports them."""
    primary, derived = scan_sections(payload)
    emitted = None if raw_input else exact_markers(payload)
    # In the raw input every marker is forged and is replaced, so numbering starts at 1.
    number = [1 if raw_input else _next_marker_number(payload)]
    markers, embedded, new = {}, [], []

    def mark(text, kind):
        if text not in markers:
            if number[0] > MAX_MARKER_NUMBER:
                raise InputError("the input carries more withheld markers than can be numbered; it is malformed")
            markers[text] = withheld_marker(number[0], kind)
            number[0] += 1
            if kind != SPLIT:
                embedded.append(text)

    tripped = set()
    for path, text in primary:
        if forged_marker(text, emitted):
            mark(text, INSTRUCTION)
            tripped.add(text)
            new.append((path, INSTRUCTION, False))
            continue
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
        if forged_marker(text, emitted) and text not in primary_texts:
            mark(text, INSTRUCTION)
            derived_new.append((path, INSTRUCTION, True))
            continue
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
    # Prose split across adjacent array entries: each entry passes alone, a run of them trips joined (array_runs). Every
    # entry of the run is withheld with a split marker; an entry already flagged or withheld splits the array into runs.
    def breaks(value):
        return not (isinstance(value, str) and value.strip()) or value in markers or contains_withheld(value) or any(source in value for source in embedded)

    for path, fields, refs, is_derived, found in array_runs(payload, breaks):
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
