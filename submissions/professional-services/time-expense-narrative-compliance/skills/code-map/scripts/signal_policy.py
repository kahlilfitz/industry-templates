#!/usr/bin/env python3
"""signal_policy - shared privacy, data-minimisation and injection controls for every engine.

1. Signal-source privacy (client-billing-guidelines.md #10.1). Every engine calls
   filter_packet() before it uses activity evidence, so a signal from a disabled or unknown
   source can never reach a narrative, a code mapping or a compliance verdict - even when a
   hand-built packet contains one. Policy resolution is most-restrictive-wins: a source is
   usable only when it is enabled in EVERY policy that is available. When the plugin-level
   policy is unavailable (for example, when a skill runs stand-alone), the documented narrow
   default is the mandatory floor and a packet policy may narrow it but can never enable
   mailbox access.
2. Timekeeper scope (client-billing-guidelines.md #12.1). A packet holds only the requesting
   timekeeper's rows unless it carries a valid engagement-manager team view: the requester is
   the engagement manager recorded in the engagement letter AND the explicit confirmation
   token "engagement-manager:<engagement_id>" was supplied. Role is never inferred from text.
3. Strict input validation. validate_packet() checks every field an engine reads: wrong JSON types
   (a "true" string for a boolean, {} or 123 in a list of strings, null where a value is required)
   and unrecognised enum values raise SchemaError - nothing is coerced through truthiness, and a
   string can never stand in for the boolean team-view confirmation.
4. Embedded-instruction tripwire (client-billing-guidelines.md #11.1). Free text is data.
   embedded_instruction()/screen() route every text through the shared steering_guard detector
   (intent families: addressee, verdict, suppression, rule override, authority, scope,
   exfiltration, mixed script) with the billing hooks in STEERING_HOOKS. signal_texts() and
   entry_texts() return multi-field records that go through steering_guard.scan_fields, so an
   instruction split across fields is caught. An 'oversize' result is never a pass: the item is
   held with OVERSIZE_REASON.

This file ships as identical copies next to each engine (skills are self-contained);
tests/check_shared_copies.py fails when the copies drift.
"""
import datetime
import functools
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import steering_guard  # noqa: E402  (shared detector, vendored byte-identically next to each engine)

POLICY_CITATION = "client-billing-guidelines.md #10.1"
INJECTION_CITATION = "client-billing-guidelines.md #11.1"
WITHHOLD_CITATION = "client-billing-guidelines.md #11.2"
SCOPE_CITATION = "client-billing-guidelines.md #12.1"
SIGNAL_POLICY_VERSION = "signal_policy/1.0.4"
TEAM_VIEW_PREFIX = "engagement-manager:"
TEAM_VIEW_TOKEN_RE = re.compile(r"engagement-manager:[A-Za-z0-9._-]+")
WITHHELD_TEXT = "[withheld: flagged as embedded_instruction - client-billing-guidelines.md #11.2]"

# Connector source prefix -> key in config/signal-sources.json "sources".
SOURCE_KEYS = (
    ("connector:m365-calendar", "calendar"),
    ("connector:engagement-document-activity", "document_activity"),
    ("connector:mailbox-metadata", "mailbox_metadata"),
    ("connector:mailbox-content", "mailbox_content"),
    ("connector:mailbox", "mailbox_content"),
)

# Documented default posture when no policy file or packet policy is available.
NARROW_DEFAULT = {
    "calendar": {"enabled": True},
    "document_activity": {"enabled": True},
    "mailbox_content": {"enabled": False},
    "mailbox_metadata": {"enabled": False},
}


class PolicyError(ValueError):
    """Raised when a signal policy file exists but cannot be read."""


def source_key(source):
    """Map a connector source string to its policy key; None means unknown (never allowed)."""
    source = source or ""
    for prefix, key in SOURCE_KEYS:
        if source.startswith(prefix):
            return key
    return None


def find_plugin_config(start_dir):
    """Walk up from start_dir looking for config/signal-sources.json (the plugin root copy)."""
    current = os.path.abspath(start_dir)
    for _ in range(6):
        candidate = os.path.join(current, "config", "signal-sources.json")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def load_policy_file(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PolicyError(f"cannot read signal policy {os.path.basename(path)}: {exc}") from exc
    sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(sources, dict):
        raise PolicyError(f"signal policy {os.path.basename(path)} has no 'sources' object")
    check_sources(sources, f"signal policy {os.path.basename(path)} sources")
    return sources


def effective_sources(packet, config_path=None, script_dir=None):
    """Return ({source_key: enabled}, [policy names used]); most restrictive wins.

    The plugin config (or, stand-alone, the narrow default floor) is ALWAYS applied. A
    --signal-config file and a packet signal_config are additional policies: they can narrow
    the allowed sources but never widen or replace the plugin config.
    """
    policies = []
    found = find_plugin_config(script_dir) if script_dir else None
    if found:
        policies.append(("config/signal-sources.json", load_policy_file(found)))
    else:
        policies.append(("narrow default", NARROW_DEFAULT))
    if config_path:
        same = found and os.path.normcase(os.path.realpath(config_path)) == os.path.normcase(os.path.realpath(found))
        if not same:
            policies.append((f"--signal-config {os.path.basename(config_path)} (additional)",
                             load_policy_file(config_path)))
    packet_sources = (packet.get("signal_config") or {}).get("sources")
    if isinstance(packet_sources, dict):
        policies.append(("packet signal_config", packet_sources))
    keys = set(NARROW_DEFAULT)
    for _, sources in policies:
        keys.update(sources)
    enabled = {}
    for key in sorted(keys):
        # A key missing from any policy counts as disabled in that policy (fail closed).
        enabled[key] = all((sources.get(key) or {}).get("enabled") is True for _, sources in policies)
    return enabled, [name for name, _ in policies]


def filter_packet(packet, config_path=None, script_dir=None, engine="engine:unknown"):
    """Drop disabled/unknown-source signals in place and record every exclusion.

    - packet["activity_signals"] keeps only signals from enabled sources.
    - packet["provenance"]["excluded_signals"] lists each dropped signal (merged, de-duplicated).
    - a time entry's links to excluded or unresolvable signals move from activity_ids to
      excluded_activity_ids, so no engine can count them as evidence.
    Returns the set of excluded activity IDs.
    """
    enabled, used = effective_sources(packet, config_path, script_dir)
    provenance = packet.setdefault("provenance", {})
    excluded = list(provenance.get("excluded_signals", []))
    seen = {e.get("activity_id") for e in excluded}
    kept = []
    for signal in packet.get("activity_signals", []):
        key = source_key(signal.get("source"))
        if key is not None and enabled.get(key) is True:
            kept.append(signal)
            continue
        if signal.get("activity_id") not in seen:
            reason = (f"source '{key}' is disabled in the signal policy" if key
                      else "unknown or unapproved signal source")
            excluded.append({
                "activity_id": signal.get("activity_id"),
                "source": signal.get("source"),
                "policy_key": key,
                "reason": reason,
                "excluded_by": engine,
                "citations": [POLICY_CITATION],
            })
            seen.add(signal.get("activity_id"))
    packet["activity_signals"] = kept
    kept_ids = {s.get("activity_id") for s in kept}
    for entry in packet.get("time_entries", []):
        links = entry.get("activity_ids") or []
        dropped = [a for a in links if a not in kept_ids]
        if not dropped:
            continue
        entry["activity_ids"] = [a for a in links if a in kept_ids]
        prior = entry.get("excluded_activity_ids") or []
        entry["excluded_activity_ids"] = prior + [a for a in dropped if a not in prior]
        for activity_id in dropped:
            if activity_id not in seen:
                excluded.append({
                    "activity_id": activity_id,
                    "source": None,
                    "policy_key": None,
                    "reason": f"linked from {entry.get('entry_id')} but not present in any enabled source",
                    "excluded_by": engine,
                    "citations": [POLICY_CITATION],
                })
                seen.add(activity_id)
    provenance["excluded_signals"] = excluded
    provenance["signal_policy"] = {
        "enabled_sources": sorted(k for k, v in enabled.items() if v),
        "disabled_sources": sorted(k for k, v in enabled.items() if not v),
        "policies_applied": used,
        "rule": "most_restrictive_wins",
        "engine": SIGNAL_POLICY_VERSION,
        "citations": [POLICY_CITATION],
    }
    return {e.get("activity_id") for e in excluded}


# --- Timekeeper scope / data minimisation (client-billing-guidelines.md #12.1) -------------

def same_person(a, b):
    """Exact name match after whitespace and case folding; never a fuzzy or inferred match."""
    fa, fb = person_key(a), person_key(b)
    return bool(fa) and fa == fb


def person_key(name):
    return " ".join(name.split()).casefold() if isinstance(name, str) else ""


def team_view_token(engagement_id):
    return TEAM_VIEW_PREFIX + str(engagement_id or "")


def team_view_valid(packet):
    """True only for a structurally valid engagement-manager team view recorded by activity_pull."""
    scope = (packet.get("provenance") or {}).get("timekeeper_scope")
    engagement = packet.get("engagement") if isinstance(packet.get("engagement"), dict) else {}
    if not isinstance(scope, dict) or scope.get("mode") != "team":
        return False
    view = scope.get("team_view")
    engagement_id = engagement.get("engagement_id")
    return (isinstance(view, dict) and view.get("confirmed") is True and view.get("role") == "engagement_manager"
            and isinstance(engagement_id, str) and bool(engagement_id)
            and view.get("confirmation") == team_view_token(engagement_id)
            and same_person(scope.get("requester"), engagement.get("engagement_manager")))


def enforce_timekeeper_scope(packet, engine="engine:unknown", strict=False):
    """Keep only rows the recorded timekeeper scope allows; return the number of rows withheld.

    - valid engagement-manager team view: every timekeeper (or the listed people) is allowed;
    - otherwise only provenance.timekeeper_scope.requester's rows are allowed;
    - no recorded requester (and no valid team view): PolicyError, whatever the packet holds (fail closed).
    strict=True (used on governed output) raises instead of silently dropping rows.
    """
    provenance = packet.setdefault("provenance", {})
    scope = provenance.get("timekeeper_scope")
    keys = ("activity_signals", "time_entries", "missing_time_report")
    if team_view_valid(packet):
        listed = scope.get("people")
        if listed is None:
            return 0
        if not isinstance(listed, list):
            raise PolicyError("timekeeper_scope.people must be a list or null")
        allowed = {person_key(n) for n in listed}
    else:
        requester = scope.get("requester") if isinstance(scope, dict) else None
        if not person_key(requester):
            raise PolicyError("packet records no requesting timekeeper and no valid engagement-manager team view "
                              f"({SCOPE_CITATION}); re-run activity_pull with --requester")
        allowed = {person_key(requester)}
    withheld = 0
    for key in keys:
        items = packet.get(key)
        if not isinstance(items, list):
            continue
        keep = [r for r in items if isinstance(r, dict) and person_key(r.get("person")) in allowed]
        withheld += len(items) - len(keep)
        if not strict:
            packet[key] = keep
    if withheld and strict:
        raise PolicyError(f"{withheld} row(s) fall outside the recorded timekeeper scope ({SCOPE_CITATION}); "
                          "re-run the chain from activity_pull")
    if withheld:
        if not isinstance(scope, dict):
            scope = provenance["timekeeper_scope"] = {}
        scope.setdefault("withheld_by_engines", []).append({
            "engine": engine,
            "rows_withheld": withheld,
            "reason": "rows for other timekeepers withheld: no valid engagement-manager team view",
            "citations": [SCOPE_CITATION],
        })
    return withheld


# --- Embedded-instruction tripwire (client-billing-guidelines.md #11.1 / #11.2) -------------
# The detector is the shared steering_guard module, vendored byte-identically next to each engine
# (tests/check_shared_copies.py pins its SHA-256). Plugin vocabulary goes only through its hooks.

STEERING_HOOKS = {
    "extra_verdict_words": ("billable", "compliant", "no write down", "approved for billing"),
    "extra_rule_nouns": ("ocg", "ocgs", "billing guidelines", "phase code"),
    # Time narratives, activity subjects, file names and attendee lists never legitimately carry
    # an e-mail address or URL, so any address is held (client-billing-guidelines.md #11.1).
    "contact_is_steering": True,
}
OVERSIZE_REASON = (f"too long to screen for embedded instructions (over {steering_guard.MAX_TOTAL_CHARS:,} "
                   "characters, alone or joined with its related fields); not scanned, held for human review")


PAIR_KEYS = ("subject", "purpose", "deliverable", "file_name")
OWN_KEYS = ("narrative", "notes")
CACHE_MAX_CHARS = 20000  # longer texts are scanned every time rather than held in the cache


def _fields(mapping):
    return {str(k): v for k, v in mapping.items() if isinstance(v, str) and v.strip()}


@functools.lru_cache(maxsize=8192)
def _scan_cached(text):
    return tuple(steering_guard.scan(text, **STEERING_HOOKS))


@functools.lru_cache(maxsize=8192)
def _scan_fields_cached(items):
    return tuple(steering_guard.scan_fields(dict(items), **STEERING_HOOKS))


def _scan_text(text):
    return list(_scan_cached(text)) if len(text) <= CACHE_MAX_CHARS else steering_guard.scan(text, **STEERING_HOOKS)


def _scan_record(fields):
    items = tuple(fields.items())
    if sum(len(v) for v in fields.values()) <= CACHE_MAX_CHARS:
        return list(_scan_fields_cached(items))
    return steering_guard.scan_fields(fields, **STEERING_HOOKS)


def _pairs(fields):
    """Ordered field pairs that are also joined: a two-field split ("Mark this" + "entry compliant")
    can be diluted by the record's other fields in the full join, so it is scanned on its own."""
    own = [k for k in fields if k in OWN_KEYS]
    if own:  # entry record: its own text against every other field, both orders
        return [(a, b) for a in own for b in fields if b != a] + [(b, a) for a in own for b in fields if b not in own]
    prose = [k for k in fields if k in PAIR_KEYS]
    return [(a, b) for a in prose for b in prose if a != b]


def screen_record(record):
    """steering_guard.scan_fields on the whole record, then on each ordered pair of its prose fields."""
    fields = _fields(record)
    if not fields:
        return []
    hits = _scan_record(fields)
    if hits:
        return hits
    for a, b in _pairs(fields):
        hits = _scan_record({a: fields[a], b: fields[b]})
        if hits:
            return hits
    return []


def screen(*texts):
    """steering_guard hits for every text. A str is scanned alone; a dict is one multi-field record
    (screen_record: each field, the joins, and its prose-field pairs, so a split instruction is
    caught); a list or tuple is scanned item by item. An 'oversize' hit means the text was NOT
    scanned: hold it."""
    hits = []
    for text in texts:
        if isinstance(text, dict):
            hits += screen_record(text)
        elif isinstance(text, (list, tuple)):
            hits += screen(*text)
        elif isinstance(text, str) and text.strip():
            hits += _scan_text(text)
    return hits


def is_oversize(hits):
    return any(h.family == "oversize" for h in hits)


def embedded_instruction(*texts):
    """True when any text (or any multi-field record) is steering, or too long to screen (#11.1)."""
    return bool(screen(*texts))


def hold_reason(hits, default):
    """The review reason for a held item: the oversize reason when it was not scanned."""
    return OVERSIZE_REASON if is_oversize(hits) else default


def _joined(values):
    items = [v if isinstance(v, str) else json.dumps(v, default=str) for v in values]
    return "; ".join(i for i in items if i.strip())


def signal_texts(signal):
    """One multi-field record holding every free-text field of an activity signal that can reach a
    draft, a table or a report (file names are read as words by steering_guard.normalize)."""
    if not isinstance(signal, dict):
        return {}
    record = {k: signal.get(k) for k in ("subject", "purpose", "deliverable", "file_name", "organizer",
                                          "activity_class", "meeting_id")}
    attendees = signal.get("attendees")
    if isinstance(attendees, list):
        record["attendees"] = _joined(attendees)
    elif attendees is not None:
        record["attendees"] = json.dumps(attendees, default=str)  # wrong type: scan everything it holds
    return record


def entry_texts(entry, linked=()):
    """One multi-field record: an entry's own free text (narrative, notes) and, when it has any, the
    subject/purpose/deliverable of its linked activities, so an instruction split between the entry
    and its activity is caught."""
    if not isinstance(entry, dict):
        return {}
    record = {"narrative": entry.get("narrative"), "notes": entry.get("notes")}
    if any(isinstance(v, str) and v.strip() for v in record.values()):
        for n, signal in enumerate(linked):
            if isinstance(signal, dict):
                for key in ("subject", "purpose", "deliverable"):
                    record[f"linked{n}_{key}"] = signal.get(key)
    return record


def redact(text):
    """Return WITHHELD_TEXT when text trips the wire or is too long to screen (#11.2)."""
    return WITHHELD_TEXT if embedded_instruction(text) else text


# --- Strict input validation (wrong JSON types and unknown enum values fail closed) --------

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
SCOPE_MODES = ("self", "team")
TEAM_VIEW_ROLES = ("engagement_manager",)
SEVERITY_RANK = {"compliant": 0, "needs_review": 1, "hold_for_review": 2, "reject": 3}
SEVERITIES = ("needs_review", "hold_for_review", "reject")
VERDICTS = tuple(SEVERITY_RANK)
EXCEPTION_VERDICTS = VERDICTS + ("missing_time",)
DRAFT_STATUSES = ("engine_generated_from_activity", "existing_timesheet_narrative", "needs_review",
                  "needs_review_insufficient_detail", "needs_review_embedded_instruction", "needs_activity_evidence")
REWRITE_STATUSES = ("engine_generated_from_activity", "needs_review", "needs_review_insufficient_detail",
                    "withheld_embedded_instruction")
MAPPING_BASES = ("direct_activity_class", "conflicting_activity_classes", "unknown_activity_class",
                 "keyword_inference", "unmapped")
STAGES = ("activity", "drafted", "coded", "governed")
STAGE_HINT = {"draft": "run narrative_draft.py first", "code_mapping": "run code_map.py first",
              "compliance": "run guideline_check.py first"}
JSON_TYPES = {bool: "boolean", str: "string", int: "number", float: "number", dict: "object", list: "array",
              type(None): "null"}


class SchemaError(PolicyError):
    """A field has the wrong JSON type or an unrecognised enum value (fail closed; never coerced)."""


def _type(value):
    return JSON_TYPES.get(type(value), type(value).__name__)


def _bad(where, rule, value):
    # Only the JSON type is echoed, never the value: field text is untrusted (#11.1).
    raise SchemaError(f"invalid input: {where} must be {rule}, got {_type(value)} "
                      "(wrong types and unknown values are rejected, never coerced)")


def check_text(value, where, null=True):
    if not (isinstance(value, str) or (null and value is None)):
        _bad(where, "a string" + (" or null" if null else ""), value)
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            _bad(where, "valid Unicode text (no lone surrogates)", value)


def check_id(value, where):
    if not isinstance(value, str) or not value.strip():
        _bad(where, "a non-empty string", value)


def check_bool(value, where):
    if type(value) is not bool:
        _bad(where, "a JSON boolean (true or false; strings such as \"true\" or \"yes\" are rejected)", value)


def check_number(value, where, low=None, high=None, integer=False):
    kinds = (int,) if integer else (int, float)
    if (type(value) not in kinds or not math.isfinite(value)
            or (low is not None and value < low) or (high is not None and value > high)):
        span = f" in [{low if low is not None else '-inf'}, {high if high is not None else 'inf'}]"
        _bad(where, ("an integer" if integer else "a finite number") + span, value)


def check_date(value, where, null=False):
    if null and value is None:
        return
    ok = isinstance(value, str) and DATE_RE.fullmatch(value)
    if ok:
        try:
            datetime.date.fromisoformat(value)
        except ValueError:
            ok = False
    if not ok:
        _bad(where, "a YYYY-MM-DD date" + (" or null" if null else ""), value)


def check_strings(value, where, null=False):
    if null and value is None:
        return
    if not isinstance(value, list):
        _bad(where, "an array of strings", value)
    for i, item in enumerate(value):
        check_text(item, f"{where}[{i}]", null=False)


def check_enum(value, allowed, where):
    if not isinstance(value, str) or value not in allowed:
        raise SchemaError(f"invalid input: {where} must be one of {', '.join(allowed)}; an unrecognised "
                          f"{_type(value)} value is rejected (fail closed)")


def check_object(value, where, null=False):
    if null and value is None:
        return {}
    if not isinstance(value, dict):
        _bad(where, "an object" + (" or null" if null else ""), value)
    return value


KINDS = {
    "text": check_text,
    "str": lambda v, w: check_text(v, w, null=False),
    "id": check_id,
    "bool": check_bool,
    "hours": lambda v, w: check_number(v, w, low=0),
    "confidence": lambda v, w: check_number(v, w, low=0, high=1),
    "count": lambda v, w: check_number(v, w, low=0, integer=True),
    "date": check_date,
    "date?": lambda v, w: check_date(v, w, null=True),
    "strings": check_strings,
    "strings?": lambda v, w: check_strings(v, w, null=True),
    "object": check_object,
    "object?": lambda v, w: check_object(v, w, null=True),
}


def check_fields(obj, where, spec):
    """spec: (key, kind or enum tuple, required). Absent optional keys are fine; present ones are typed."""
    obj = check_object(obj, where)
    for key, kind, required in spec:
        if key not in obj:
            if required:
                hint = f"; {STAGE_HINT[key]}" if key in STAGE_HINT else ""
                raise SchemaError(f"invalid input: {where} is missing required field '{key}'{hint}")
            continue
        if isinstance(kind, tuple):
            check_enum(obj[key], kind, f"{where}.{key}")
        else:
            KINDS[kind](obj[key], f"{where}.{key}")
    return obj


def check_list(value, where, spec):
    if not isinstance(value, list):
        _bad(where, "an array of objects", value)
    return [check_fields(item, f"{where}[{i}]", spec) for i, item in enumerate(value)]


def check_sources(sources, where):
    check_object(sources, where)
    for key, value in sources.items():
        check_fields(value, f"{where}.{key}", (("enabled", "bool", True),))


ENGAGEMENT_SPEC = (("engagement_id", "id", True), ("client_name", "text", False), ("matter_name", "text", False),
                   ("billing_guidelines_id", "text", False), ("engagement_manager", "text", False))
PERIOD_SPEC = (("start", "date?", False), ("end", "date?", False))
SCOPE_SPEC = (("mode", SCOPE_MODES, True), ("requester", "text", False), ("people", "strings?", False),
              ("team_view", "object?", False), ("withheld", "object?", False))
TEAM_VIEW_SPEC = (("confirmed", "bool", True), ("role", TEAM_VIEW_ROLES, True), ("confirmation", "str", True))
EXCLUDED_SPEC = (("activity_id", "text", False), ("source", "text", False), ("policy_key", "text", False),
                 ("reason", "text", False), ("citations", "strings", False))
SIGNAL_SPEC = (("activity_id", "id", True), ("person", "id", True), ("date", "date", True),
               ("duration_hours", "hours", True), ("source", "str", True), ("billable_signal", "bool", True),
               ("activity_class", "text", False), ("subject", "text", False), ("purpose", "text", False),
               ("deliverable", "text", False), ("meeting_id", "text", False), ("organizer", "text", False),
               ("file_name", "text", False), ("attendees", "strings", False), ("confidence", "confidence", False),
               ("citations", "strings", False), ("embedded_instruction", "bool", False),
               ("needs_review", "bool", False), ("review_reason", "text", False))
ENTRY_SPEC = (("entry_id", "id", True), ("person", "id", True), ("date", "date", True),
              ("duration_hours", "hours", True), ("narrative", "text", False), ("notes", "text", False),
              ("activity_ids", "strings", False), ("excluded_activity_ids", "strings", False),
              ("submitted_phase_code", "text", False), ("submitted_task_code", "text", False),
              ("embedded_instruction", "bool", False), ("source", "str", False),
              ("confidence", "confidence", False), ("citations", "strings", False))
DRAFT_SPEC = (("narrative", "str", True), ("status", DRAFT_STATUSES, True), ("needs_review", "bool", True),
              ("confidence", "confidence", True), ("citations", "strings", True), ("review_reasons", "strings", False),
              ("linked_activity_ids", "strings", False), ("covered_activity_ids", "strings", False),
              ("excluded_activity_ids", "strings", False))
REWRITE_SPEC = (("narrative", "str", True), ("status", REWRITE_STATUSES, True), ("review_reasons", "strings", False),
                ("linked_activity_ids", "strings", False), ("confidence", "confidence", False),
                ("citations", "strings", False))
FLAG_SPEC = (("flag", "id", True), ("severity", SEVERITIES, True), ("detail", "str", True),
             ("confidence", "confidence", False), ("citations", "strings", False), ("source", "text", False))
MAPPING_SPEC = (("recommended_phase_code", "id", True), ("recommended_task_code", "id", True),
                ("recommended_label", "text", False), ("submitted_phase_code", "text", False),
                ("submitted_task_code", "text", False), ("basis", MAPPING_BASES, True),
                ("confidence", "confidence", True), ("citations", "strings", False))
COMPLIANCE_SPEC = (("verdict", VERDICTS, True), ("confidence", "confidence", True), ("citations", "strings", False),
                   ("evidence_hours_same_date", "hours", False), ("required_elements", "object?", False))
MISSING_SPEC = (("activity_id", "id", True), ("person", "id", True), ("date", "date", True),
                ("duration_hours", "hours", True), ("activity_class", "text", False), ("subject", "text", False),
                ("finding", "text", False), ("confidence", "confidence", False), ("citations", "strings", False),
                ("embedded_instruction", "bool", False))
EXCEPTION_SPEC = (("verdict", EXCEPTION_VERDICTS, True), ("flags", "strings", True))
SUMMARY_SPEC = (("total_entries", "count", True), ("total_hours", "hours", True), ("verdict_counts", "object", True),
                ("missing_time_hours", "hours", True), ("excluded_signal_ids", "strings", False),
                ("exception_count", "count", False), ("period", "object?", False))


def _check_flags(value, where):
    flags = check_list(value, where, FLAG_SPEC)
    return max([SEVERITY_RANK[f["severity"]] for f in flags] + [0])


def validate_packet(packet, stage):
    """Validate every field the engines read, for a packet at `stage` (activity, drafted, coded, governed).

    Raises SchemaError on a wrong JSON type, a missing required field, an unrecognised enum value, or a
    governed verdict that does not match the severity of its flags. Returns the packet unchanged.
    """
    level = STAGES.index(stage)
    check_object(packet, "packet")
    check_text(packet.get("contract_version"), "contract_version", null=False)
    check_fields(packet.get("engagement"), "engagement", ENGAGEMENT_SPEC)
    if "period" in packet:
        check_fields(check_object(packet["period"], "period", null=True), "period", PERIOD_SPEC)
    if "signal_config" in packet:
        # Present means a real policy: null or a policy without sources would silently lift its restrictions.
        config = check_fields(packet["signal_config"], "signal_config", (("sources", "object", True),))
        check_sources(config["sources"], "signal_config.sources")
    provenance = check_fields(packet.get("provenance"), "provenance", ())
    if "timekeeper_scope" in provenance:
        scope = check_fields(provenance["timekeeper_scope"], "provenance.timekeeper_scope", SCOPE_SPEC)
        if scope.get("team_view") is not None:
            view = check_fields(scope["team_view"], "provenance.timekeeper_scope.team_view", TEAM_VIEW_SPEC)
            if not TEAM_VIEW_TOKEN_RE.fullmatch(view["confirmation"]):
                raise SchemaError("invalid input: provenance.timekeeper_scope.team_view.confirmation must be "
                                  "exactly 'engagement-manager:<engagement_id>'")
        if "withheld_by_engines" in scope:
            check_list(scope["withheld_by_engines"], "provenance.timekeeper_scope.withheld_by_engines", ())
    if "excluded_signals" in provenance:
        check_list(provenance["excluded_signals"], "provenance.excluded_signals", EXCLUDED_SPEC)
    if "engines" in provenance:
        check_strings(provenance["engines"], "provenance.engines")
    check_list(packet.get("activity_signals"), "activity_signals", SIGNAL_SPEC)
    for i, entry in enumerate(check_list(packet.get("time_entries"), "time_entries", ENTRY_SPEC)):
        where = f"time_entries[{i}]"
        if level >= 1:
            check_fields(entry, where, (("draft", "object?", True),))
            draft = check_fields(entry["draft"], f"{where}.draft", DRAFT_SPEC)
            if "suggested_rewrites" in draft:
                check_list(draft["suggested_rewrites"], f"{where}.draft.suggested_rewrites", REWRITE_SPEC)
        if level >= 2:
            check_fields(entry, where, (("code_mapping", "object?", True),))
            mapping = check_fields(entry["code_mapping"], f"{where}.code_mapping", MAPPING_SPEC)
            _check_flags(mapping.get("flags", []), f"{where}.code_mapping.flags")
        if level >= 3:
            check_fields(entry, where, (("compliance", "object?", True),))
            compliance = check_fields(entry["compliance"], f"{where}.compliance", COMPLIANCE_SPEC)
            worst = _check_flags(compliance.get("flags", []), f"{where}.compliance.flags")
            if SEVERITY_RANK[compliance["verdict"]] != worst:
                raise SchemaError(f"invalid input: {where}.compliance.verdict does not match the most severe of its "
                                  "flags; re-run guideline_check.py (fail closed)")
    if level >= 3:
        for key in ("missing_time_report", "exception_list", "prebill_summary"):
            if key not in packet:
                raise SchemaError(f"invalid input: '{key}' missing; {STAGE_HINT['compliance']}")
        check_list(packet["missing_time_report"], "missing_time_report", MISSING_SPEC)
        check_list(packet["exception_list"], "exception_list", EXCEPTION_SPEC)
        summary = check_fields(packet["prebill_summary"], "prebill_summary", SUMMARY_SPEC)
        for verdict, count in summary["verdict_counts"].items():
            check_enum(verdict, VERDICTS, "prebill_summary.verdict_counts key")
            check_number(count, f"prebill_summary.verdict_counts.{verdict}", low=0, integer=True)
    return packet
