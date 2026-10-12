"""Fail-closed redaction of untrusted staffing source text.

Detection is the shared steering_guard detector, vendored byte-for-byte next to this file and never
edited here; staffing vocabulary reaches it only through its documented hooks (STAFFING_HOOKS).
This module keeps the plugin's non-detection logic: which fields are free text, how a flagged value
is replaced by a neutral marker that never echoes it, record-level (split-field) screening, and the
escalation that names the field path.
"""
import hashlib

import steering_guard as sg


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


def _hooks(trusted_domains=()):
    return dict(STAFFING_HOOKS, trusted_domains=tuple(trusted_domains))


def hits(text, trusted_domains=()):
    """Family names of every steering_guard hit for one value (``oversize`` included)."""
    return [hit.family for hit in sg.scan(str(text), **_hooks(trusted_domains))]


def is_suspect(text, trusted_domains=()):
    return bool(hits(text, trusted_domains))


def is_oversize(text):
    return "oversize" in hits(text)


def record_hits(fields, trusted_domains=()):
    """Split-field screening of one record's free-text values.

    steering_guard.scan_fields covers the spaced and " ; " joins; the fused join (no separator)
    also goes through the detector so an instruction split mid-word across fields still trips.
    """
    values = [str(value) for value in fields]
    named = {str(index): value for index, value in enumerate(values)}
    found = [hit.family for hit in sg.scan_fields(named, **_hooks(trusted_domains))]
    if not found and len(values) > 1:
        found = ["split" for _ in sg.scan("".join(values), **_hooks(trusted_domains))][:1]
    return found


def _redacted(text, label):
    digest = hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:12]
    if is_oversize(text):
        return f"[FLAGGED: oversize source {label} withheld; sha256={digest}]"
    return f"[FLAGGED: instruction-like source {label} redacted; sha256={digest}]"


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


def _is_scan_record(value):
    if "candidate_id" in value:
        return True
    return "role_id" in value and not AGGREGATE_ROLE_FIELDS.intersection(value)


def _safe_key(key, path, escalations):
    if isinstance(key, str) and is_suspect(key):
        marker = _redacted(key, "key")
        escalations.append(f"{path}.{marker}: instruction-like member name withheld; review source record")
        return marker
    return key


def sanitize_free_text(
    value,
    path,
    escalations,
    field_name=None,
    force_redact=False,
):
    if isinstance(value, dict):
        redact_record = force_redact or (
            _is_scan_record(value) and _record_is_suspect(value)
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
            )
        return sanitized
    if isinstance(value, list):
        return [
            sanitize_free_text(
                item,
                f"{path}[{index}]",
                escalations,
                field_name,
                force_redact,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, str):
        if force_redact and value.strip():
            label = "citation" if field_name == "citation" else "text"
            safe = _redacted(value.strip(), label)
        else:
            safe = safe_citation(value) if field_name == "citation" else safe_text(value)
        if safe != value.strip():
            if is_oversize(value):
                escalations.append(f"{path}: {OVERSIZE_REASON}")
            else:
                escalations.append(
                    f"{path}: instruction-like text redacted; review source record"
                )
        return safe
    return value