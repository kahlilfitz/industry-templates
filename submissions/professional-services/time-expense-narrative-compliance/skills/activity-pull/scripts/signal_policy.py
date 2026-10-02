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
   held with OVERSIZE_REASON. Signal citations are screened with the rest of the signal, and
   safe_citations() keeps flagged citation text out of every output.
5. Contract and engagement identity (client-billing-guidelines.md #13.3). validate_packet() walks the
   whole packet against the shipped contract JSON (contract_check.py) and refuses a packet whose engagement
   header differs from provenance.engagement_identity, which activity_pull records once from the
   engagement letter. filter_packet() drops signals and time entries whose source scope or engagement_id
   names another engagement; they are recorded in provenance and never rendered.
6. Strict JSON in, atomic output out. read_json() parses every JSON input with contract_check.strict_load
   (NaN, Infinity, -Infinity, 1e999 and integers beyond +/-2**53 are input errors). Every engine serialises
   its whole output first (dump_json refuses NaN; text is encoded to UTF-8, so a lone surrogate fails here)
   and write_output() then writes a temp file in the output folder and os.replace()s it: on any error the
   output path is neither created nor truncated. A member name repeated in one JSON object is refused while parsing.
7. Member names and metadata are data (client-billing-guidelines.md #11.3). filter_packet() ends with sweep_packet():
   every member name the contract does not fix, and every string no other screen covers (engagement, period, signal
   policy, provenance, code structure, guidelines and summary text, and undeclared members anywhere), is screened -
   alone, as adjacent array entries and as one record per object. A hit is replaced by a marker; inside an activity
   signal or time entry it sets that record's embedded_instruction, anywhere else packet_held() holds every entry.

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
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contract_check  # noqa: E402  (shared contract walker, identical copies next to each engine)
import steering_guard  # noqa: E402  (shared detector, vendored byte-identically next to each engine)

POLICY_CITATION = "client-billing-guidelines.md #10.1"
INJECTION_CITATION = "client-billing-guidelines.md #11.1"
WITHHOLD_CITATION = "client-billing-guidelines.md #11.2"
SCOPE_CITATION = "client-billing-guidelines.md #12.1"
ENGAGEMENT_CITATION = "client-billing-guidelines.md #13.3"
IDENTITY_KEYS = ("engagement_id", "client_name", "matter_name", "engagement_manager")
OTHER_ENGAGEMENT_REASON = "source or engagement scope names another engagement; excluded and never rendered"
OTHER_ENGAGEMENT_ENTRY_REASON = "engagement scope names another engagement; excluded and never rendered"
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
    """Map a connector source string to its policy key; None means unknown (never allowed).

    The connector name must match exactly ("connector:m365-calendar"), optionally followed by an
    engagement scope (":ENG-..."); a look-alike name such as "connector:m365-calendar-x" is unknown."""
    source = source if isinstance(source, str) else ""
    for name, key in SOURCE_KEYS:
        if source == name or source.startswith(name + ":"):
            return key
    return None


def engagement_scopes(record):
    """The engagement scopes a signal or time entry declares: the third ':'-separated segment of its
    source ("connector:m365-calendar:ENG-SYN-042") and its engagement_id field, when present."""
    scopes = []
    source = record.get("source")
    if isinstance(source, str) and source.count(":") >= 2:
        scopes.append(source.split(":", 2)[2])
    if "engagement_id" in record:
        scopes.append(record.get("engagement_id"))
    return scopes


def other_engagement(record, engagement_id):
    """True when the record's source scope or engagement_id names a different engagement (#13.3)."""
    return any(scope != engagement_id for scope in engagement_scopes(record))


def engagement_identity(engagement, citations):
    """provenance.engagement_identity as activity_pull records it from the engagement letter (#13.3)."""
    return dict({k: engagement.get(k) for k in IDENTITY_KEYS}, recorded_by="engine:activity_pull",
                citations=list(citations) + [ENGAGEMENT_CITATION])


def other_engagement_ids(packet):
    """Activity IDs excluded because they belong to another engagement (never rendered, #13.3)."""
    return {e.get("activity_id") for e in (packet.get("provenance") or {}).get("excluded_signals", [])
            if isinstance(e, dict) and e.get("reason") == OTHER_ENGAGEMENT_REASON}


def describe_excluded(links, packet):
    """Excluded link IDs for a reason or flag detail: other engagements' IDs are counted, never named."""
    other = other_engagement_ids(packet)
    shown = [a for a in links if a not in other]
    hidden = len(links) - len(shown)
    return ", ".join(shown) + (f"{'; ' if shown else ''}{hidden} from another engagement (not shown, "
                               f"{ENGAGEMENT_CITATION})" if hidden else "")


# Exclusion wording (#10.1). activity_pull and filter_packet write exactly these texts, and exception_report
# prints an exclusion only when its reason and citations equal one of them (exclusion_texts, #13.2).

def disabled_source_reason(key):
    return f"source '{key}' is disabled in the signal policy" if key else "unknown or unapproved signal source"


def unlinked_reason(entry_id):
    return f"linked from {entry_id} but not present in any enabled source"


def pull_disabled_reason(entry_id, cite, key):
    return (f"linked from {entry_id} ({cite}); the ID belongs to the '{key}' source, which is disabled "
            "in config/signal-sources.json, so that source was not read and the link is not evidence")


def pull_missing_reason(entry_id, cite):
    return f"linked from {entry_id} ({cite}) but not found in any enabled, engagement-scoped export"


def exclusion_texts(record, packet):
    """Every (reason, citations) the engines can write for this exclusion record, rebuilt from the packet."""
    key = record.get("policy_key")
    out = [(OTHER_ENGAGEMENT_REASON, [ENGAGEMENT_CITATION]), (disabled_source_reason(key), [POLICY_CITATION])]
    for entry in packet.get("time_entries", []):
        if record.get("activity_id") not in (entry.get("excluded_activity_ids") or []):
            continue
        out.append((unlinked_reason(entry.get("entry_id")), [POLICY_CITATION]))
        cites = entry.get("citations") or []
        if cites:
            if key:
                out.append((pull_disabled_reason(entry.get("entry_id"), cites[0], key), [cites[0], POLICY_CITATION]))
            out.append((pull_missing_reason(entry.get("entry_id"), cites[0]), [cites[0], POLICY_CITATION]))
    return out


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


def read_json(path, error, label=None):
    """Parse a JSON input strictly (contract_check.strict_load); any failure is raised as error(...)."""
    try:
        with open(path, encoding="utf-8") as fh:
            return contract_check.strict_load(fh)
    except (OSError, ValueError) as exc:  # ValueError covers JSONDecodeError, UnicodeDecodeError and strict_load
        raise error(f"cannot read {label or os.path.basename(path)}: {exc}") from exc


def dump_json(packet):
    """Serialise an output packet completely before anything is written (NaN/Infinity are refused)."""
    return json.dumps(packet, indent=2, allow_nan=False) + "\n"


def write_output(path, text):
    """Write text atomically: encode first, write a temp file in the same folder, then os.replace().

    On any error (a lone surrogate, a full disk, a directory at the output path) the temp file is removed and
    the output path is neither created nor truncated."""
    data = text.encode("utf-8")
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=f".{os.path.basename(path)}.", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(tmp, 0o666 & ~umask)  # mkstemp creates 0600; give the output the usual default mode
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_policy_file(path):
    data = read_json(path, PolicyError, label=f"signal policy {os.path.basename(path)}")
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
    engagement_id = (packet.get("engagement") or {}).get("engagement_id")
    # #13.3: another engagement's time entries are dropped first and recorded without their text.
    entries = packet.get("time_entries", [])
    foreign = [e for e in entries if other_engagement(e, engagement_id)]
    if foreign:
        packet["time_entries"] = [e for e in entries if not other_engagement(e, engagement_id)]
        recorded = provenance.setdefault("excluded_entries", [])
        known = {e.get("entry_id") for e in recorded}
        recorded += [{"entry_id": e.get("entry_id"), "reason": OTHER_ENGAGEMENT_ENTRY_REASON, "excluded_by": engine,
                      "citations": [ENGAGEMENT_CITATION]} for e in foreign if e.get("entry_id") not in known]
    excluded = list(provenance.get("excluded_signals", []))
    seen = {e.get("activity_id") for e in excluded}
    kept = []
    for signal in packet.get("activity_signals", []):
        key = source_key(signal.get("source"))
        foreign = other_engagement(signal, engagement_id)
        if key is not None and enabled.get(key) is True and not foreign:
            kept.append(signal)
            continue
        if signal.get("activity_id") not in seen:
            excluded.append({
                "activity_id": signal.get("activity_id"),
                # Another engagement's source label is not kept either: nothing of it is rendered (#13.3).
                "source": None if foreign else signal.get("source"),
                "policy_key": key,
                "reason": OTHER_ENGAGEMENT_REASON if foreign else disabled_source_reason(key),
                "excluded_by": engine,
                "citations": [ENGAGEMENT_CITATION] if foreign else [POLICY_CITATION],
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
                    "reason": unlinked_reason(entry.get("entry_id")),
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
    sweep_packet(packet)  # last: screens member names and metadata, including what this function recorded (#11.3)
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


PAIR_KEYS = ("subject", "purpose", "deliverable", "file_name", "citations")
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


def _pairs(fields, pair_keys=None):
    """Ordered field pairs that are also joined: a two-field split ("Mark this" + "entry compliant")
    can be diluted by the record's other fields in the full join, so it is scanned on its own.
    pair_keys, when given, names the fields to pair (for example a report header)."""
    if pair_keys is not None:
        keys = [k for k in fields if k in pair_keys]
        return [(a, b) for a in keys for b in keys if a != b]
    own = [k for k in fields if k in OWN_KEYS]
    if own:  # entry record: its own text against every other field, both orders
        return [(a, b) for a in own for b in fields if b != a] + [(b, a) for a in own for b in fields if b not in own]
    prose = [k for k in fields if k in PAIR_KEYS]
    return [(a, b) for a in prose for b in prose if a != b]


def screen_record(record, pair_keys=None):
    """steering_guard.scan_fields on the whole record, then on each ordered pair of its prose fields
    (or of the fields named in pair_keys)."""
    fields = _fields(record)
    if not fields:
        return []
    hits = _scan_record(fields)
    if hits:
        return hits
    for a, b in _pairs(fields, pair_keys):
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
    """List items (attendees, citations) for screening. Joined by newline, not "; ": steering_guard
    reads "; " as a clause boundary, so an instruction split across two items would be missed."""
    items = [v if isinstance(v, str) else json.dumps(v, default=str) for v in values]
    return "\n".join(i for i in items if i.strip())


# Every free-text field of a signal or entry that an engine can copy into a draft, a flag detail or the report.
# tests/run_tests.py inventory_tests asserts every contract string field is in one of these, closed, re-derived
# or reconciled, or never rendered (#13.2).
SIGNAL_TEXT_KEYS = ("subject", "purpose", "deliverable", "file_name", "organizer", "activity_class", "meeting_id",
                    "source", "review_reason", "engagement_id", "activity_id", "person", "attendees", "citations")
SIGNAL_LIST_KEYS = ("attendees", "citations")
ENTRY_TEXT_KEYS = ("narrative", "notes", "source", "engagement_id", "entry_id", "person", "submitted_phase_code",
                   "submitted_task_code", "activity_ids", "excluded_activity_ids", "citations")
DRAFT_TEXT_KEYS = ("review_reasons", "citations")
REWRITE_TEXT_KEYS = ("narrative", "review_reasons", "citations")


def signal_texts(signal):
    """One multi-field record holding every free-text field of an activity signal that can reach a
    draft, a table or a report, citations included (file names are read as words by
    steering_guard.normalize)."""
    if not isinstance(signal, dict):
        return {}
    record = {k: signal.get(k) for k in SIGNAL_TEXT_KEYS if k not in SIGNAL_LIST_KEYS}
    for key in SIGNAL_LIST_KEYS:
        values = signal.get(key)
        if isinstance(values, list):
            record[key] = _joined(values)
        elif values is not None:
            record[key] = json.dumps(values, default=str)  # wrong type: scan everything it holds
    return record


# A plain source-row or reference-section citation: "raw/calendar-export.csv row 2",
# "client-billing-guidelines.md #10.1".
CITATION_RE = re.compile(r"[A-Za-z0-9_./-]+\.(?:csv|md|json|xlsx|docx)(?: row \d+| #\d+(?:\.\d+)*)?")


def safe_citations(citations, flagged=False):
    """(citations that may be copied into output, whether any was withheld) (#11.2).

    Each citation must pass the tripwire on its own. When the record it came from is flagged, or the
    citations trip together, only plain source-row or reference-section citations are kept, so an
    instruction split across several citations cannot survive as fragments."""
    kept, withheld = [], False
    citations = citations if isinstance(citations, list) else []
    flagged = flagged or embedded_instruction(_joined([c for c in citations if isinstance(c, str)]))
    for citation in citations:
        if not isinstance(citation, str):
            continue
        if embedded_instruction(citation) or (flagged and not CITATION_RE.fullmatch(citation)):
            withheld = True
        else:
            kept.append(citation)
    return kept, withheld


def entry_texts(entry, linked=()):
    """One multi-field record: an entry's own free text (narrative, notes, citations) and, when it has
    a narrative or notes, the subject/purpose/deliverable of its linked activities, so an instruction
    split between the entry and its activity is caught."""
    if not isinstance(entry, dict):
        return {}
    record = {"narrative": entry.get("narrative"), "notes": entry.get("notes")}
    if any(isinstance(v, str) and v.strip() for v in record.values()):
        for n, signal in enumerate(linked):
            if isinstance(signal, dict):
                for key in ("subject", "purpose", "deliverable"):
                    record[f"linked{n}_{key}"] = signal.get(key)
    for key in ENTRY_TEXT_KEYS[2:]:
        value = entry.get(key)
        if isinstance(value, list):
            record[key] = _joined(value)
        elif value is not None:
            record[key] = value if isinstance(value, str) else json.dumps(value, default=str)
    return record


def _list_text(values):
    return _joined(values) if isinstance(values, list) else (None if values is None else json.dumps(values, default=str))


def draft_records(draft):
    """The draft's other free text as multi-field records (#11.1): its review reasons and citations, then
    each suggested rewrite (narrative, review reasons, citations). The main draft narrative is screened
    with the entry by guideline_check."""
    if not isinstance(draft, dict):
        return []
    records = [{k: _list_text(draft.get(k)) for k in DRAFT_TEXT_KEYS}]
    for rewrite in draft.get("suggested_rewrites") or []:
        if isinstance(rewrite, dict):
            records.append({k: (rewrite.get(k) if k == "narrative" else _list_text(rewrite.get(k)))
                            for k in REWRITE_TEXT_KEYS})
    return records


def redact(text):
    """Return WITHHELD_TEXT when text trips the wire or is too long to screen (#11.2)."""
    return WITHHELD_TEXT if embedded_instruction(text) else text


# --- Whole-packet sweep: member names and metadata are data too (client-billing-guidelines.md #11.3) --------
# The contract leaves most objects open, so a packet can carry members it does not declare, and its engagement,
# period, policy, provenance and summary text is copied from stage to stage. sweep_packet() (run by filter_packet in
# every engine) screens all of it: every member name the contract does not fix, and every string that no other screen
# covers. The fields signal_texts(), entry_texts() and draft_records() screen, and the re-derived missing-time and
# exception items, are left to those screens. Strings in an array are also screened as adjacent pairs, and an
# object's strings as one record, so text split across entries or fields is caught (#11.1).

METADATA_CITATION = "client-billing-guidelines.md #11.3"
MEMBER_MARKER = "[withheld member {n}: flagged as embedded_instruction - client-billing-guidelines.md #11.3]"
MEMBER_MARKER_RE = re.compile(r"\[withheld member \d+: flagged as embedded_instruction - "
                              r"client-billing-guidelines\.md #11\.3\]")
PACKET_HOLD_REASON = ("packet metadata (a member name, or engagement, period, policy, provenance or summary text) "
                      "flagged as embedded_instruction; withheld from every output and never followed")
COVERED_ALL = "*"
# Strings at these positions are screened elsewhere (or re-derived and compared); the sweep skips them.
COVERED_KEYS = {
    "signal": set(SIGNAL_TEXT_KEYS),
    "entry": set(ENTRY_TEXT_KEYS),
    "draft": set(DRAFT_TEXT_KEYS) | {"narrative"},
    "rewrite": set(REWRITE_TEXT_KEYS),
    "item": COVERED_ALL,
    "exclusion": {"activity_id", "reason", "citations"},
    "excluded_entry": {"reason", "citations"},
    "summary": {"excluded_signal_ids"},
}
LINE_ITEMS = ("activity_signals", "time_entries", "missing_time_report", "exception_list")
# The only exemptions: the engines' own origin labels. "engine:code_map" reads to the detector like a vocative
# ("engine, code ..."), and these exact values are written by the engines, never by a user.
ENGINE_LABELS = frozenset({"engine:activity_pull", "engine:narrative_draft", "engine:code_map",
                           "engine:guideline_check", "engine:exception_report", "engine:unknown"})


def _contract_root():
    return contract_check.load_contract(contract_check.contract_path(os.path.dirname(os.path.abspath(__file__))))


def _role(path):
    n = len(path)
    if n == 2 and path[0] == "activity_signals":
        return "signal"
    if n == 2 and path[0] == "time_entries":
        return "entry"
    if n == 3 and path[0] == "time_entries" and path[2] == "draft":
        return "draft"
    if n == 5 and path[0] == "time_entries" and path[2:4] == ("draft", "suggested_rewrites"):
        return "rewrite"
    # Re-derived and compared: missing-time and exception items (exception_report re-runs the rules), and an entry's
    # code mapping (guideline_check recomputes and compares it whole) and compliance (re-run; only re-derived detail
    # is printed). Their member names are still swept.
    if n >= 2 and path[0] in ("missing_time_report", "exception_list"):
        return "item"
    if n >= 3 and path[0] == "time_entries" and path[2] in ("code_mapping", "compliance"):
        return "item"
    # Exclusion records: the engines' own reason wording, reconciled exactly by exception_report (#13.2); the IDs and
    # citations it quotes are screened with the time entry that links them (entry_texts).
    if n == 3 and path[:2] == ("provenance", "excluded_signals"):
        return "exclusion"
    if n == 3 and path[:2] == ("provenance", "excluded_entries"):
        return "excluded_entry"
    # excluded_signal_ids is written by guideline_check from provenance.excluded_signals (already swept) and
    # reconciled against it exactly by exception_report.
    if path == ("prebill_summary",):
        return "summary"
    return None


def _member_texts(key, value):
    """A member's name and every member name and string under its value, in document order."""
    out = [key]
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            out += _member_texts(str(k), v)
    elif isinstance(value, list):
        for v in value:
            out += [v] if isinstance(v, str) else _member_texts("", v)
    return [t for t in out if isinstance(t, str) and t.strip()]


def _tripping_seq(texts):
    """Indices to withhold in a sequence of strings: each alone, then each adjacent pair (an instruction split
    across neighbouring array entries), then the whole sequence (every index when only the whole trips)."""
    live = [i for i, t in enumerate(texts) if isinstance(t, str) and t.strip()]
    bad = {i for i in live if _scan_text(texts[i])}
    for a, b in zip(live, live[1:]):
        if a not in bad and b not in bad and _scan_record({"a": texts[a], "b": texts[b]}):
            bad |= {a, b}
    rest = [i for i in live if i not in bad]
    if not bad and len(rest) > 2 and _scan_record({str(i): texts[i] for i in rest}):
        bad = set(rest)
    return bad


PAIR_LIMIT = 40  # more strings than this in one object are withheld whole: too many to pair-screen (fail closed)


def _tripping_fields(fields):
    """Keys to withhold in one object's strings: each alone, then every ordered pair (both members of a tripping
    pair; a pair can be diluted in the whole join), then the whole record (every field when only it trips)."""
    bad = {k for k, t in fields.items() if _scan_text(t)}
    rest = {k: t for k, t in fields.items() if k not in bad}
    if len(rest) < 2:
        return bad
    keys = list(rest)
    if len(keys) > PAIR_LIMIT:
        return bad | set(keys)
    pairs = {k for a in keys for b in keys if a != b and _scan_record({a: rest[a], b: rest[b]}) for k in (a, b)}
    if not pairs and _scan_record(rest):
        pairs = set(keys)
    return bad | pairs


def _context_trips(fields, context):
    """Undeclared fields to withhold because they trip with a covered member's string (an instruction split between
    a covered array such as citations and an undeclared sibling): each ordered pair, then the whole join. More
    strings than PAIR_LIMIT is a hold on every field (fail closed)."""
    context = [t for t in context if isinstance(t, str) and t.strip()]
    if not fields or not context:
        return set()
    if len(fields) + len(context) > PAIR_LIMIT:
        return set(fields)
    bad = {k for k, t in fields.items() for c in context
           if _scan_record({"a": c, "b": t}) or _scan_record({"a": t, "b": c})}
    if not bad and _scan_record({**{f"c{i}": c for i, c in enumerate(context)}, **fields}):
        bad = set(fields)
    return bad


class _Sweep:
    def __init__(self, root):
        self.root = root
        self.owners = set()

    def hold(self, path):
        self.owners.add((path[0], path[1]) if len(path) >= 2 and path[0] in ("activity_signals", "time_entries")
                        else "packet")

    def walk(self, value, schema, path, covered=False):
        schema = contract_check._resolve(schema, self.root) if isinstance(schema, dict) else {}
        if isinstance(value, dict):
            self.object(value, schema, path)
        elif isinstance(value, list):
            self.array(value, schema, path, covered)

    def array(self, items, schema, path, covered):
        sub = schema.get("items") if isinstance(schema.get("items"), dict) else {}
        closed = _closed(contract_check._resolve(sub, self.root)) if sub else False
        if not covered and not closed:
            for i in _tripping_seq([v if isinstance(v, str) and v not in ENGINE_LABELS else "" for v in items]):
                items[i] = WITHHELD_TEXT
                self.hold(path + (i,))
        for i, item in enumerate(items):
            if isinstance(item, (dict, list)):
                self.walk(item, sub, path + (i,), covered)

    def object(self, obj, schema, path):
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        cover = COVERED_KEYS.get(_role(path), ())
        siblings = None
        rebuilt, swept, changed, used = [], {}, False, set(obj)
        undeclared = {}  # record field name -> undeclared member key, for the whole-object screen below
        context = []  # strings of covered members (#11.3): paired with the undeclared members below
        for key, item in obj.items():
            if key not in props and not isinstance(extra, dict):
                # A member the contract does not define: its name and content are screened as one record and with
                # the object's own strings; a hit (or an earlier marker) renames it to a marker and withholds it.
                if siblings is None:
                    siblings = {k: v for k, v in obj.items()
                                if k in props and isinstance(v, str) and v.strip() and not _scan_text(v)}
                if MEMBER_MARKER_RE.fullmatch(key) or self.member_trips(key, item, siblings):
                    self.hold(path)
                    if not MEMBER_MARKER_RE.fullmatch(key):
                        key, item, changed = self.marker(used), WITHHELD_TEXT, True
                else:
                    # Kept for the whole-object screen, so two undeclared siblings are paired with each other too.
                    for j, text in enumerate(_member_texts(str(key), item)):
                        if text not in ENGINE_LABELS:
                            name = f"{key}\x00{j}"
                            swept[name], undeclared[name] = text, key
                rebuilt.append((key, item))
                continue
            sub = props.get(key, extra)
            if key not in props and "propertyNames" not in schema and _scan_text(key):
                # An open-map member name (signal_config.sources) is input text: renamed, its object kept.
                self.hold(path)
                key, changed = self.marker(used), True
            resolved = contract_check._resolve(sub, self.root) if isinstance(sub, dict) else {}
            covered = cover == COVERED_ALL or key in cover
            if covered:
                # Screened elsewhere on its own, but never with this object's undeclared members: kept as context.
                context += [t for t in _member_texts("", item) if t not in ENGINE_LABELS]
            if isinstance(item, str):
                if not covered and not _closed(resolved) and item.strip() and item not in ENGINE_LABELS:
                    swept[key] = item
            else:
                self.walk(item, resolved, path + (key,), covered)
            rebuilt.append((key, item))
        bad = _tripping_fields(swept) if swept else set()
        bad |= _context_trips({k: swept[k] for k in undeclared if k not in bad}, context)
        if bad:
            self.hold(path)
            members = {undeclared[k] for k in bad if k in undeclared}
            out = []
            for k, v in rebuilt:
                if k in members:
                    out.append((self.marker(used), WITHHELD_TEXT))
                else:
                    out.append((k, WITHHELD_TEXT if k in bad else v))
            rebuilt, changed = out, True
        if changed:
            obj.clear()
            obj.update(rebuilt)

    def member_trips(self, key, item, siblings):
        texts = _member_texts(str(key), item)
        if _tripping_seq(texts) or (len(texts) > 1 and _scan_record({str(i): t for i, t in enumerate(texts)})):
            return True
        return any(_scan_record({"a": a, "b": b}) for s in siblings.values() for t in texts for a, b in ((s, t), (t, s)))

    def marker(self, used):
        n = 1
        while MEMBER_MARKER.format(n=n) in used:
            n += 1
        name = MEMBER_MARKER.format(n=n)
        used.add(name)
        return name


def _closed(schema):
    return "enum" in schema or "const" in schema


def sweep_packet(packet):
    """Screen every member name and uncovered string in the packet in place (#11.3). A hit is replaced by a marker
    (a member name by a unique MEMBER_MARKER, a value by WITHHELD_TEXT). A hit inside an activity signal or time
    entry sets that record's embedded_instruction, so every engine holds it and withholds its text; any other hit
    is a packet-level hold (packet_held). Idempotent: an earlier stage's markers are kept and still hold."""
    if not isinstance(packet, dict):
        return
    sweep = _Sweep(_contract_root())
    sweep.walk(packet, sweep.root, ())
    # An excluded signal's ID that no time entry links is screened by nothing else: screen it here.
    linked = {a for e in packet.get("time_entries") or [] if isinstance(e, dict)
              for key in ("activity_ids", "excluded_activity_ids") for a in (e.get(key) or []) if isinstance(a, str)}
    for record in (packet.get("provenance") or {}).get("excluded_signals") or []:
        activity_id = record.get("activity_id") if isinstance(record, dict) else None
        if isinstance(activity_id, str) and activity_id not in linked and activity_id != WITHHELD_TEXT \
                and _scan_text(activity_id):
            record["activity_id"] = WITHHELD_TEXT
            sweep.owners.add("packet")
    for owner in sweep.owners - {"packet"}:
        records = packet.get(owner[0])
        if isinstance(records, list) and isinstance(owner[1], int) and owner[1] < len(records) \
                and isinstance(records[owner[1]], dict):
            records[owner[1]]["embedded_instruction"] = True
    # Engagement identity stays in step with the header, so a withheld name is withheld in both (#13.3).
    header = packet.get("engagement")
    identity = (packet.get("provenance") or {}).get("engagement_identity")
    if isinstance(header, dict) and isinstance(identity, dict):
        for key in IDENTITY_KEYS:
            if WITHHELD_TEXT in (header.get(key), identity.get(key)):
                header[key] = identity[key] = WITHHELD_TEXT


def _holds_marker(value):
    if isinstance(value, str):
        return value == WITHHELD_TEXT
    if isinstance(value, dict):
        return any(MEMBER_MARKER_RE.fullmatch(str(k)) or _holds_marker(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_holds_marker(v) for v in value)
    return False


def packet_held(packet):
    """True when packet metadata (anything outside the line items) carries a withheld marker (#11.3): every entry
    is held for review. A marker-named member inside a line item holds the packet too."""
    if not isinstance(packet, dict):
        return False
    for key, value in packet.items():
        if MEMBER_MARKER_RE.fullmatch(str(key)):
            return True
        if key in LINE_ITEMS:
            if key in ("missing_time_report", "exception_list") and isinstance(value, list) and any(
                    isinstance(item, dict) and any(MEMBER_MARKER_RE.fullmatch(str(k)) for k in item) for item in value):
                return True
            continue
        if _holds_marker(value):
            return True
    return False


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


class IdentityError(SchemaError):
    """The engagement header differs from the identity activity_pull recorded (#13.3)."""


def check_engagement_identity(packet):
    """Refuse a packet whose engagement header differs from provenance.engagement_identity (#13.3)."""
    identity = packet["provenance"]["engagement_identity"]
    header = packet["engagement"]
    for key in IDENTITY_KEYS:
        if header.get(key) != identity.get(key):
            raise IdentityError(f"invalid input: engagement.{key} does not match provenance.engagement_identity, which "
                                f"activity_pull recorded from the engagement letter ({ENGAGEMENT_CITATION}); no output "
                                "was written - re-run the chain from activity_pull")


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
    if (type(value) not in kinds or (type(value) is float and not math.isfinite(value))
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
    known = {key for _, key in SOURCE_KEYS}
    for n, (key, value) in enumerate(sources.items(), start=1):
        # Only the documented source names are echoed; any other key is input text and named by position.
        check_fields(value, f"{where}.{key}" if key in known else f"{where}.<member #{n}>", (("enabled", "bool", True),))


ENGAGEMENT_SPEC = (("engagement_id", "id", True), ("client_name", "text", False), ("matter_name", "text", False),
                   ("billing_guidelines_id", "text", False), ("engagement_manager", "text", False))
PERIOD_SPEC = (("start", "date?", True), ("end", "date?", True))
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


def _first_repeat(values):
    seen = {}
    for i, value in enumerate(values):
        if value in seen:
            return seen[value], i
        seen[value] = i
    return None


def check_unique_ids(packet):
    """IDs the engines index by must be unique (#13.2): an index keyed by a repeated ID would keep one record and
    silently drop the other (a hidden signal, missing time or entry). The error names positions, never the ID."""
    provenance = packet.get("provenance") or {}
    lists = (("activity_signals", packet.get("activity_signals") or [], "activity_id"),
             ("time_entries", packet.get("time_entries") or [], "entry_id"),
             ("provenance.excluded_signals", provenance.get("excluded_signals") or [], "activity_id"),
             ("provenance.excluded_entries", provenance.get("excluded_entries") or [], "entry_id"))
    for where, records, key in lists:
        # Withheld excluded IDs (#11.3) are all the same marker and are never used as an index key.
        exempt = WITHHELD_TEXT if where.startswith("provenance.") else None
        repeat = _first_repeat([object() if exempt and r.get(key) == exempt else r.get(key) for r in records])
        if repeat:
            raise SchemaError(f"invalid input: {where}[{repeat[1]}].{key} repeats {where}[{repeat[0]}].{key}; "
                              "duplicate IDs are malformed (one record would silently replace the other)")
    # A record is active or excluded, never both: an active record listed as excluded would be rendered while the
    # report says it was excluded (or the exclusion would be silently ignored).
    for (active, records, key), (excluded, dropped, _) in ((lists[0], lists[2]), (lists[1], lists[3])):
        gone = {r.get(key): j for j, r in enumerate(dropped) if r.get(key) != WITHHELD_TEXT}
        for i, record in enumerate(records):
            if record.get(key) in gone:
                raise SchemaError(f"invalid input: {active}[{i}].{key} is also listed in {excluded}"
                                  f"[{gone[record.get(key)]}]; a record is either active or excluded, never both")
    for i, entry in enumerate(packet.get("time_entries") or []):
        for key in ("activity_ids", "excluded_activity_ids"):
            repeat = _first_repeat(entry.get(key) or [])
            if repeat:
                raise SchemaError(f"invalid input: time_entries[{i}].{key}[{repeat[1]}] repeats "
                                  f"time_entries[{i}].{key}[{repeat[0]}]; a link is listed once")
        both = [j for j, a in enumerate(entry.get("activity_ids") or []) if a in (entry.get("excluded_activity_ids") or [])]
        if both:
            raise SchemaError(f"invalid input: time_entries[{i}].activity_ids[{both[0]}] is also in "
                              f"time_entries[{i}].excluded_activity_ids; a link is either active or excluded")


def validate_packet(packet, stage):
    """Validate every field the engines read, for a packet at `stage` (activity, drafted, coded, governed).

    Raises SchemaError on a wrong JSON type, a missing required field, an unrecognised enum value, or a
    governed verdict that does not match the severity of its flags. Returns the packet unchanged.
    """
    level = STAGES.index(stage)
    check_object(packet, "packet")
    check_text(packet.get("contract_version"), "contract_version", null=False)
    check_fields(packet.get("engagement"), "engagement", ENGAGEMENT_SPEC)
    # period is required by the contract: a missing or null period is an input error, never "no period".
    check_fields(packet, "packet", (("period", "object", True),))
    check_fields(packet["period"], "period", PERIOD_SPEC)
    start, end = packet["period"]["start"], packet["period"]["end"]
    if start is not None and end is not None and start > end:
        raise SchemaError("invalid input: period.start is after period.end")
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
    try:
        contract_check.validate_packet(packet, os.path.dirname(os.path.abspath(__file__)))
    except contract_check.ContractError as exc:
        raise SchemaError(str(exc)) from exc
    check_engagement_identity(packet)
    check_unique_ids(packet)
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
