"""Fail-closed redaction of untrusted staffing source text.

Detection is the shared steering_guard detector, vendored byte-for-byte next to this file and never
edited here; staffing vocabulary reaches it only through its documented hooks (STAFFING_HOOKS).
This module keeps the plugin's non-detection logic: which fields are free text, how a flagged value
is replaced by a neutral marker that never echoes it, record-level (split-field) and adjacent-entry
(list run) screening, already-redacted marker text supplied as input, the escalation that names the
field path, and one escalation per piece of text (ScreeningLog).
"""
import functools
import hashlib
import re

import steering_guard as sg
from input_guard import has_marker

STAFFING_HOOKS = {
    "extra_verdict_words": (
        "independent",
        "eligible",
        "recommended",
        "conflict free",
        "released",
    ),
    "extra_rule_nouns": (
        "independence rules",
        "independence check",
        "conflicts register",
        "score floor",
        "eligibility verdict",
    ),
}
OVERSIZE_REASON = "text too long to screen for embedded instructions; withheld for review"
STRUCTURAL_FIELDS = {
    "candidate_id",
    "role_id",
    "engagement_id",
    "contract_version",
    "start",
    "end",
    "start_date",
    "end_date",
    "resolved_date",
    "generated_at",
    "type",
    "status",
    "disposition",
    "verdict",
    "recommendation_status",
    "source",
    "currency",
}
AGGREGATE_ROLE_FIELDS = {
    "candidate_scores",
    "candidate_slate",
    "recommended_candidates",
}


RECORD_FIELDS = {"engagement", "provenance"}
HOLD_RULE = "independence-eligibility-rules.md #9.6"
HOLD_REASONS = {
    "instruction": "instruction-like text withheld",
    "oversize": "oversize text withheld",
    "marker": "already-redacted marker text withheld",
    "key": "instruction-like member name withheld",
}
ENGINE_MARKER = (
    r"\[FLAGGED: (?:instruction-like|oversize|already-redacted) source (?:citation|text|key) "
    r"(?:redacted|withheld); sha256=[0-9a-f]{12}\]"
)


class ScreeningLog(list):
    """An escalation list that also records every screening hit and keeps one escalation per text.

    One piece of text yields one escalation (B3): the key is the field path without its stage prefix
    (``roles_input.``, ``bench_input.`` ...) plus the redaction digest, so the same injected text in a
    copied field (for example ``engagement.citation`` in roles.json and bench.json) escalates once.
    ``hits`` keeps every (path, kind) so a caller can bind holds to the record that carried them.
    """

    def __init__(self, items=()):
        super().__init__(items)
        self.hits = []
        self.keys = set()

    def holds_under(self, prefix):
        """Hold lines (rule #9.6) for every hit at or below ``prefix``; paths drop the stage prefix."""
        holds = []
        for path, kind in self.hits:
            if path == prefix or path.startswith(prefix + ".") or path.startswith(prefix + "["):
                line = f"{_strip_stage(path)}: {HOLD_REASONS[kind]} ({HOLD_RULE})"
                if line not in holds:
                    holds.append(line)
        return holds


def _strip_stage(path):
    return path.split(".", 1)[1] if "." in path else path


def _digest(text):
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:12]


def _escalate(escalations, path, kind, digest, message):
    if isinstance(escalations, ScreeningLog):
        escalations.hits.append((path, kind))
        key = (_strip_stage(path), digest)
        if key in escalations.keys:
            return
        escalations.keys.add(key)
    escalations.append(message)


def _hooks(trusted_domains=()):
    return dict(STAFFING_HOOKS, trusted_domains=tuple(trusted_domains))


@functools.lru_cache(maxsize=8192)
def _families(text, trusted_domains):
    return tuple(hit.family for hit in sg.scan(text, **_hooks(trusted_domains)))


def hits(text, trusted_domains=()):
    """Family names of every steering_guard hit for one value (``oversize`` included)."""
    return list(_families(str(text), tuple(trusted_domains)))


def is_suspect(text, trusted_domains=()):
    return bool(hits(text, trusted_domains))


def is_oversize(text):
    return "oversize" in hits(text)


@functools.lru_cache(maxsize=8192)
def _record_families(values, trusted_domains):
    named = {str(index): value for index, value in enumerate(values)}
    found = [hit.family for hit in sg.scan_fields(named, **_hooks(trusted_domains))]
    if not found and len(values) > 1:
        found = ["split" for _ in sg.scan("".join(values), **_hooks(trusted_domains))][:1]
    return tuple(found)


def record_hits(fields, trusted_domains=()):
    """Split-field screening of one record's free-text values.

    steering_guard.scan_fields covers the spaced and " ; " joins; the fused join (no separator)
    also goes through the detector so an instruction split mid-word across fields still trips.
    """
    return list(_record_families(tuple(str(value) for value in fields), tuple(trusted_domains)))


def is_engine_marker(text):
    """True when every marker in ``text`` is in the exact form this module emits."""
    return isinstance(text, str) and not has_marker(re.sub(ENGINE_MARKER, "", text))


def _redacted(text, label):
    digest = _digest(text)
    if is_oversize(text):
        return f"[FLAGGED: oversize source {label} withheld; sha256={digest}]"
    return f"[FLAGGED: instruction-like source {label} redacted; sha256={digest}]"


def _marker_withheld(text, label):
    return f"[FLAGGED: already-redacted source {label} withheld; sha256={_digest(text)}]"


def safe_citation(text):
    text = str(text).strip()
    return _redacted(text, "citation") if is_suspect(text) else text


def safe_text(text):
    text = str(text).strip()
    return _redacted(text, "text") if is_suspect(text) else text


def _record_texts(value, field_name=None):
    if isinstance(value, dict):
        for key, item in value.items():
            if key not in STRUCTURAL_FIELDS:
                yield from _record_texts(item, key)
    elif isinstance(value, list):
        for item in value:
            yield from _record_texts(item, field_name)
    elif isinstance(value, str):
        yield value


def _record_is_suspect(value):
    """True when only a join of the record's free-text values trips (single values redact themselves)."""
    texts = [text for text in _record_texts(value) if text.strip()]
    if len(texts) < 2 or any(is_suspect(text) for text in texts):
        return False
    return bool(record_hits(texts))


def _is_scan_record(value, field_name=None):
    if field_name in RECORD_FIELDS:
        return True
    if "candidate_id" in value:
        return True
    return "role_id" in value and not AGGREGATE_ROLE_FIELDS.intersection(value)


def _run_trips(values):
    return any(family != "oversize" for family in record_hits(values))


def list_run_indices(items):
    """Indices of list entries withheld because adjacent clean strings trip only when joined (D18).

    Every pair of neighbouring clean string entries is screened, then the whole list in order; a run
    that trips withholds every entry in it. Entries that trip (or carry a marker) on their own are
    handled individually and never join a run.
    """
    clean = [
        index for index, item in enumerate(items)
        if isinstance(item, str) and item.strip() and not has_marker(item) and not is_suspect(item)
    ]
    flagged = set()
    for first, second in zip(clean, clean[1:]):
        if second == first + 1 and _run_trips([items[first], items[second]]):
            flagged.update((first, second))
    if not flagged and len(clean) > 2 and _run_trips([items[index] for index in clean]):
        flagged.update(clean)
    return flagged


def _safe_key(key, path, escalations):
    if isinstance(key, str) and is_suspect(key):
        marker = _redacted(key, "key")
        _escalate(
            escalations, f"{path}.{marker}", "key", _digest(key),
            f"{path}.{marker}: instruction-like member name withheld; review source record",
        )
        return marker
    return key


def sanitize_free_text(
    value,
    path,
    escalations,
    field_name=None,
    force_redact=False,
    engine_markers_ok=False,
):
    """Return a screened copy of ``value``; every withheld value escalates once by field path.

    ``engine_markers_ok`` is only for a document this plugin's engines have just re-derived: a whole
    marker in the exact engine form is kept. Anywhere else, input text carrying the ``[FLAGGED:``
    marker is withheld and held under independence-eligibility-rules.md #9.6 (D20).
    """
    if isinstance(value, dict):
        redact_record = force_redact or (
            _is_scan_record(value, field_name) and _record_is_suspect(value)
        )
        sanitized = {}
        for key, item in value.items():
            safe_key = _safe_key(key, path, escalations)
            sanitized[safe_key] = sanitize_free_text(
                item,
                f"{path}.{safe_key}",
                escalations,
                safe_key,
                redact_record and key not in STRUCTURAL_FIELDS,
                engine_markers_ok,
            )
        return sanitized
    if isinstance(value, list):
        runs = set() if force_redact else list_run_indices(value)
        return [
            sanitize_free_text(
                item,
                f"{path}[{index}]",
                escalations,
                field_name,
                force_redact or index in runs,
                engine_markers_ok,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, str):
        text = value.strip()
        label = "citation" if field_name == "citation" else "text"
        if not text:
            return text
        if force_redact:
            safe = _redacted(text, label)
        elif has_marker(text) and not (engine_markers_ok and is_engine_marker(text)):
            safe = _marker_withheld(text, label)
            _escalate(
                escalations, path, "marker", _digest(text),
                f"{path}: already-redacted marker text withheld; review source record ({HOLD_RULE})",
            )
            return safe
        else:
            safe = safe_citation(text) if field_name == "citation" else safe_text(text)
        if safe != text:
            if is_oversize(text):
                _escalate(escalations, path, "oversize", _digest(text), f"{path}: {OVERSIZE_REASON}")
            else:
                _escalate(
                    escalations, path, "instruction", _digest(text),
                    f"{path}: instruction-like text redacted; review source record",
                )
        return safe
    return value
