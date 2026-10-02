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
   output path is neither created nor truncated. A member name repeated in one JSON object is refused while parsing,
   and so is nesting deeper than contract_check.MAX_DEPTH (64) levels (A14).
7. Member names and metadata are data (client-billing-guidelines.md #11.3). filter_packet() ends with sweep_packet():
   every member name the contract does not fix, and every string no other screen covers (engagement, period, signal
   policy, provenance, code structure, guidelines and summary text, and undeclared members anywhere), is screened -
   alone, as adjacent array entries and as one record per object. A hit is replaced by a marker; inside an activity
   signal or time entry it sets that record's embedded_instruction, anywhere else packet_held() holds every entry.
   The excluded signal and entry IDs are screened as one sequence each, as the report prints them.
8. Withheld text decides nothing (D19, #11.2). signal_flagged() and field_withheld() name the text the rules may
   not read: a flagged narrative infers no code, credits no element, matches no term and is compared with nothing.
9. Every placeholder has its own hold (D21, client-billing-guidelines.md #11.4). sweep_packet() records the path of
   every marker it places or keeps in a withheld_fields ledger: on the activity signal or time entry that carries it
   (relative path), else in provenance.withheld_fields. validate_packet() refuses a marker that is not listed at its
   exact path, a listed path that holds no marker, and a record with markers that is not held. Re-derived sections
   (drafts, code mappings, compliance, missing time, exception list, summary IDs) are compared with their
   re-derivation instead.
10. Exclusions hold in every section and blank keys never match (A20, A21, client-billing-guidelines.md #13.6).

This file ships as identical copies next to each engine (skills are self-contained);
tests/check_shared_copies.py fails when the copies drift.
"""
import datetime
import functools
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import unicodedata

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
# D20: only the engines write markers. Input text shaped like one - exact or embedded, in any spelling that NFKC and
# case folding bring to "[withheld" - is refused at activity_pull (supplied_marker). A later stage accepts only the
# exact markers the engines emit, and every record that carries one is held (sweep_packet). is_withheld() is the one
# predicate for "this text is withheld".
MARKER_SHAPE_RE = re.compile(r"\[\s*withheld\b")


def is_withheld(value):
    """True only for the exact withheld marker an engine wrote (never a padded or embedded copy)."""
    return isinstance(value, str) and value == WITHHELD_TEXT


def marker_shaped(text):
    return isinstance(text, str) and bool(MARKER_SHAPE_RE.search(canon_text(text)))

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
    """True when the record's source scope or engagement_id names a different engagement (#13.3). Engagement IDs
    compare in canonical form (canon_id), so a variant spelling of this engagement's ID is this engagement."""
    return any(canon_id(scope) != canon_id(engagement_id) or not canon_id(scope)
               for scope in engagement_scopes(record))


def engagement_identity(engagement, citations):
    """provenance.engagement_identity as activity_pull records it from the engagement letter (#13.3)."""
    return dict({k: engagement.get(k) for k in IDENTITY_KEYS}, recorded_by="engine:activity_pull",
                citations=list(citations) + [ENGAGEMENT_CITATION])


def other_engagement_ids(packet):
    """Activity IDs excluded because they belong to another engagement (never rendered, #13.3)."""
    return {e.get("activity_id") for e in (packet.get("provenance") or {}).get("excluded_signals", [])
            if isinstance(e, dict) and e.get("reason") == OTHER_ENGAGEMENT_REASON}


def describe_excluded(links, packet):
    """Excluded link IDs for a reason or flag detail: other engagements' IDs are counted, never named (a variant
    spelling of such an ID is the same ID, canon_id)."""
    other = {canon_id(a) for a in other_engagement_ids(packet) if isinstance(a, str)}
    shown = [a for a in links if not is_withheld(a) and canon_id(a) not in other]
    withheld = sum(1 for a in links if is_withheld(a))
    hidden = len(links) - len(shown) - withheld
    # A withheld ID is counted, never quoted: prose never embeds a marker, so a later stage can refuse any embedded
    # marker as supplied (D20).
    parts = ([", ".join(shown)] if shown else []) \
        + ([f"{withheld} withheld ID(s) (flagged as embedded_instruction, {METADATA_CITATION})"] if withheld else []) \
        + ([f"{hidden} from another engagement (not shown, {ENGAGEMENT_CITATION})"] if hidden else [])
    return "; ".join(parts)


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


def error_text(exc):
    """An error message that never echoes a path or a value taken from input (A18): the engines' own messages as
    written, an OS error as its reason only (str(OSError) embeds the file name), and a Unicode error as its kind."""
    if isinstance(exc, OSError):
        return exc.strerror or type(exc).__name__
    if isinstance(exc, UnicodeError):
        return f"text is not valid UTF-8 or cannot be encoded ({type(exc).__name__})"
    if isinstance(exc, json.JSONDecodeError):
        return f"{exc.msg}: line {exc.lineno} column {exc.colno}"
    return str(exc)


def read_json(path, error, label):
    """Parse a JSON input strictly (contract_check.strict_load); any failure is raised as error(...). label is a
    fixed, trusted name for the input ("activity input" and so on), never its file name or path (A18)."""
    try:
        with open(path, encoding="utf-8") as fh:
            return contract_check.strict_load(fh)
    except (OSError, ValueError) as exc:  # ValueError covers JSONDecodeError, UnicodeDecodeError and strict_load
        raise error(f"cannot read {label}: {error_text(exc)}") from exc


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


def load_policy_file(path, label):
    """label is fixed by the caller ("config/signal-sources.json" or "--signal-config"), never the file name."""
    data = read_json(path, PolicyError, label=f"signal policy {label}")
    sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(sources, dict):
        raise PolicyError(f"signal policy {label} has no 'sources' object")
    check_sources(sources, f"signal policy {label} sources")
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
        policies.append(("config/signal-sources.json", load_policy_file(found, "config/signal-sources.json")))
    else:
        policies.append(("narrow default", NARROW_DEFAULT))
    if config_path:
        same = found and os.path.normcase(os.path.realpath(config_path)) == os.path.normcase(os.path.realpath(found))
        if not same:
            policies.append(("--signal-config (additional)", load_policy_file(config_path, "--signal-config")))
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
    moved = set()
    for n, entry in enumerate(packet.get("time_entries", [])):
        links = entry.get("activity_ids") or []
        dropped = [a for a in links if a not in kept_ids]
        if not dropped:
            continue
        moved.add(n)
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
    sweep_packet(packet)  # screens member names and metadata, including what this function recorded (#11.3)
    # A drafted entry whose links this policy moved is re-drafted from its remaining evidence, so no draft built from
    # now-excluded activity is carried on and every later stage re-derives the same draft (#13.4, #13.5).
    redraft = {n for n in moved if isinstance(packet["time_entries"][n].get("draft"), dict)}
    if redraft:
        derive_drafts(packet, only=redraft)
    return {e.get("activity_id") for e in excluded}


# --- Timekeeper scope / data minimisation (client-billing-guidelines.md #12.1) -------------

CROSS_PERSON_CITATION = "client-billing-guidelines.md #12.2"


def same_person(a, b):
    """Exact name match after whitespace and case folding; never a fuzzy or inferred match."""
    fa, fb = person_key(a), person_key(b)
    return bool(fa) and fa == fb


def person_key(name):
    return canon_text(name)


# --- Canonical comparison forms (plugin-hardening-checklist A13) ---------------------------
# Every name, ID, code-key and CSV-header comparison goes through one of these two functions;
# original values are kept for output. No length cap and no fast path.

def _strip_cf(text):
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def canon_text(value):
    """NFKC, format-character strip, casefold, whitespace collapse."""
    return _canon_text(value) if isinstance(value, str) else ""


@functools.lru_cache(maxsize=8192)
def _canon_text(value):
    text = _strip_cf(unicodedata.normalize("NFKC", _strip_cf(value))).casefold()
    return " ".join(unicodedata.normalize("NFKC", text).split())


def canon_id(value):
    """canon_text plus separator folding (- _ . and whitespace are equivalent)."""
    return _canon_id(value) if isinstance(value, str) else ""


@functools.lru_cache(maxsize=8192)
def _canon_id(value):
    return " ".join(re.sub(r"[\s\-_.]+", " ", _canon_text(value)).split())


def class_in(value, names):
    """True when an activity class names one of `names` in canonical form ("Internal_Admin" is internal_admin)."""
    key = canon_id(value)
    return bool(key) and any(key == canon_id(n) for n in names)


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
        allowed = {person_key(n) for n in listed} - {""}
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
    items = [i for i in items if i.strip()]
    # D18: a run of up to RUN_WINDOW items that trips is screened on its own, so the rest of a long list cannot
    # dilute an instruction split across three or more of its entries.
    run = _tripping_seq(items) if len(items) > 1 else set()
    return "\n".join(items[i] for i in sorted(run)) if run else "\n".join(items)


# Every free-text field of a signal or entry that an engine can copy into a draft, a flag detail or the report.
# tests/run_tests.py inventory_tests asserts every contract string field is in one of these, closed, re-derived
# or reconciled, or never rendered (#13.2).
SIGNAL_TEXT_KEYS = ("subject", "purpose", "deliverable", "file_name", "organizer", "activity_class", "meeting_id",
                    "source", "review_reason", "engagement_id", "activity_id", "person", "attendees", "citations")
SIGNAL_LIST_KEYS = ("attendees", "citations")
ENTRY_TEXT_KEYS = ("narrative", "notes", "source", "engagement_id", "entry_id", "person", "submitted_phase_code",
                   "submitted_task_code", "activity_ids", "excluded_activity_ids", "cross_person_activity_ids",
                   "citations")
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


# --- Withheld text decides nothing (D19, client-billing-guidelines.md #11.2) --------------------------------------
# Text that trips the wire produces the hold and nothing else: no rule reads it to infer a code, credit a required
# element, match a term or compare narratives. billing_rules reads only the fields these helpers clear.

def signal_flagged(signal):
    """True when an activity signal's free text trips the wire, or an earlier stage marked it: none of its text
    is read by a rule (its subject or deliverable never credits a narrative)."""
    return isinstance(signal, dict) and (signal.get("embedded_instruction") is True
                                         or embedded_instruction(signal_texts(signal)))


def field_withheld(record, key):
    """True when record[key] is withheld text: the marker, text that trips alone, one half of a pair that trips
    with another field of the record that is clean on its own (both halves of a split are withheld), or part of a
    join of the clean fields that trips only with it."""
    fields = _fields(record)
    text = fields.get(key)
    if text is None:
        return False
    if is_withheld(text) or _scan_text(text):
        return True
    rest = {k: t for k, t in fields.items() if k != key and not _scan_text(t)}
    if any(_scan_record({key: text, k: t}) or _scan_record({k: t, key: text}) for k, t in rest.items()):
        return True
    return bool(rest) and bool(_scan_record({key: text, **rest})) and not _scan_record(rest)


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
PLAIN_KEY_RE = re.compile(r"[a-z_]{1,40}")


def supplied_marker(packet, exact_ok):
    """The path (never the text) of the first member name or string shaped like a withheld marker, or None (D20).
    exact_ok accepts the exact markers the engines emit (WITHHELD_TEXT as a value, MEMBER_MARKER as a member name);
    activity_pull passes False, since raw input never carries an engine's marker."""
    stack = [(packet, "packet")]
    while stack:
        value, where = stack.pop()
        if isinstance(value, dict):
            for n, (key, item) in enumerate(value.items(), start=1):
                plain = isinstance(key, str) and PLAIN_KEY_RE.fullmatch(key)
                if marker_shaped(key) and not (exact_ok and MEMBER_MARKER_RE.fullmatch(key)):
                    return f"{where} member #{n} name"
                stack.append((item, f"{where}.{key}" if plain else f"{where}.<member #{n}>"))
        elif isinstance(value, list):
            stack += [(item, f"{where}[{i}]") for i, item in enumerate(value)]
        elif marker_shaped(value) and not (exact_ok and is_withheld(value)):
            return where
    return None


def refuse_supplied_markers(packet, exact_ok):
    where = supplied_marker(packet, exact_ok)
    if where:
        raise SchemaError(f"invalid input: {where} carries text shaped like the engines' withheld marker; only the "
                          "engines write markers, so input that imitates one is refused (client-billing-guidelines.md "
                          "#11.2) - no output was written")
PACKET_HOLD_REASON = ("packet metadata (a member name, or engagement, period, policy, provenance or summary text) "
                      "flagged as embedded_instruction; withheld from every output and never followed")
COVERED_ALL = "*"
# Strings at these positions are screened elsewhere (or re-derived and compared); the sweep skips them.
COVERED_KEYS = {
    "signal": set(SIGNAL_TEXT_KEYS) | {"withheld_fields"},
    "entry": set(ENTRY_TEXT_KEYS) | {"withheld_fields"},
    "draft": set(DRAFT_TEXT_KEYS) | {"narrative"},
    "rewrite": set(REWRITE_TEXT_KEYS),
    "item": COVERED_ALL,
    "exclusion": {"activity_id", "reason", "citations"},
    "excluded_entry": {"reason", "citations"},
    "summary": {"excluded_signal_ids"},
    # The placeholder ledgers (D21) are engine-written paths, reconciled exactly against the markers they bind.
    "provenance": {"withheld_fields"},
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
    if path == ("provenance",):
        return "provenance"
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


RUN_WINDOW = 8  # contiguous runs of up to this many entries are screened on their own (D18)


def _tripping_seq(texts):
    """Indices to withhold in a sequence of strings: each alone, then every contiguous run of 2 to RUN_WINDOW
    entries, shortest first (an instruction split across neighbouring array entries, which the rest of a long array
    would dilute), then the whole sequence (every index when only the whole trips). Every entry of a run that trips
    is withheld; a run that holds an entry already withheld is not screened again."""
    live = [i for i, t in enumerate(texts) if isinstance(t, str) and t.strip()]
    bad = {i for i in live if _scan_text(texts[i])}
    for size in range(2, min(RUN_WINDOW, len(live)) + 1):
        for start in range(len(live) - size + 1):
            run = live[start:start + size]
            if not bad.intersection(run) and _scan_record({str(n): texts[i] for n, i in enumerate(run)}):
                bad.update(run)
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


def _sweep_excluded_ids(packet, owners):
    """Excluded IDs are printed as one list ("Excluded by signal policy: A, B, C") and copied as lists, so each list
    is screened as a sequence - each ID alone, adjacent pairs, then the whole list - never one ID at a time: "Mark
    this" and "entry compliant" as two excluded IDs are one instruction (#11.3). A hit is withheld in provenance and
    in every entry that links it (those entries are held); an ID no entry links holds the packet. Earlier markers
    stay in the sequence, so a later stage screens the same neighbours."""
    provenance = packet.get("provenance")
    if not isinstance(provenance, dict):
        return
    for name, key in (("excluded_signals", "activity_id"), ("excluded_entries", "entry_id")):
        records = [r for r in provenance.get(name) or [] if isinstance(r, dict) and isinstance(r.get(key), str)]
        for i in sorted(_tripping_seq([r[key] for r in records])):
            old = records[i][key]
            if old == WITHHELD_TEXT:
                continue
            records[i][key] = WITHHELD_TEXT
            linking = []
            if name == "excluded_signals":
                for n, entry in enumerate(packet.get("time_entries") or []):
                    links = entry.get("excluded_activity_ids") if isinstance(entry, dict) else None
                    if isinstance(links, list) and old in links:
                        entry["excluded_activity_ids"] = [WITHHELD_TEXT if a == old else a for a in links]
                        linking.append(("time_entries", n))
            # A linked ID holds the entries that link it; an ID no entry links holds the packet.
            owners.update(linking or ["packet"])


def _name_slots(packet):
    """(holder, key) for every field that holds a timekeeper or manager name compared by name later (timekeeper scope,
    team-view check, rows): the line items' person, the scope's requester, people and requested colleagues, and the
    engagement manager in the header and the recorded identity."""
    slots = []
    for name in ("time_entries", "activity_signals", "missing_time_report", "exception_list"):
        records = packet.get(name)
        for record in records if isinstance(records, list) else []:
            if isinstance(record, dict) and isinstance(record.get("person"), str):
                slots.append((record, "person"))
    provenance = packet.get("provenance") if isinstance(packet.get("provenance"), dict) else {}
    scope = provenance.get("timekeeper_scope")
    if isinstance(scope, dict):
        holders = [(scope, "requester"), (scope, "people")]
        if isinstance(scope.get("withheld"), dict):
            holders.append((scope["withheld"], "requested"))
        for holder, key in holders:
            value = holder.get(key)
            if isinstance(value, str):
                slots.append((holder, key))
            elif isinstance(value, list):
                slots += [(value, i) for i, v in enumerate(value) if isinstance(v, str)]
    for holder in (packet.get("engagement"), provenance.get("engagement_identity")):
        if isinstance(holder, dict) and isinstance(holder.get("engagement_manager"), str):
            slots.append((holder, "engagement_manager"))
    return slots


def _withhold_names(packet, originals, owners):
    """Names are harvested before the sweep and withheld consistently after it: a name withheld in any slot (for
    example a scope list whose adjacent names read as an instruction) is withheld in every slot, so the scope check
    still matches the rows and the team-view check still matches the manager. A row whose person is withheld is held,
    never dropped as another timekeeper's."""
    names = {canon_text(old) for holder, key, old in originals
             if old != WITHHELD_TEXT and holder[key] == WITHHELD_TEXT} - {""}
    if not names:
        return
    for holder, key, old in originals:
        if holder[key] != WITHHELD_TEXT and canon_text(old) in names:
            holder[key] = WITHHELD_TEXT
    for name in ("time_entries", "activity_signals"):
        for n, record in enumerate(packet.get(name) or []):
            if isinstance(record, dict) and record.get("person") == WITHHELD_TEXT:
                owners.add((name, n))


def sweep_packet(packet):
    """Screen every member name and uncovered string in the packet in place (#11.3). A hit is replaced by a marker
    (a member name by a unique MEMBER_MARKER, a value by WITHHELD_TEXT). A hit inside an activity signal or time
    entry sets that record's embedded_instruction, so every engine holds it and withholds its text; any other hit
    is a packet-level hold (packet_held). Idempotent: an earlier stage's markers are kept and still hold."""
    if not isinstance(packet, dict):
        return
    originals = [(holder, key, holder[key]) for holder, key in _name_slots(packet)]
    sweep = _Sweep(_contract_root())
    sweep.walk(packet, sweep.root, ())
    _sweep_excluded_ids(packet, sweep.owners)
    _withhold_names(packet, originals, sweep.owners)
    # D20: a record that carries an exact marker (written by an earlier stage, or supplied) is always held.
    for name in ("time_entries", "activity_signals"):
        for n, record in enumerate(packet.get(name) or []):
            if isinstance(record, dict) and _holds_marker(record):
                sweep.owners.add((name, n))
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
    write_ledgers(packet)


# --- Placeholder ledger (D21, client-billing-guidelines.md #11.4) ----------------------------------------------
LEDGER_KEY = "withheld_fields"
LEDGER_CITATION = "client-billing-guidelines.md #11.4"
LEDGER_RECORDS = ("activity_signals", "time_entries")
RECORD_DERIVED = ("draft", "code_mapping", "compliance")  # re-derived and compared whole (#13.2, #13.5)
# Packet-level sections that are re-derived and compared exactly at the report (#13.2), or ledgered per record.
PACKET_DERIVED = (("activity_signals",), ("time_entries",), ("missing_time_report",), ("exception_list",),
                  ("prebill_summary", "excluded_signal_ids"), ("provenance", LEDGER_KEY))
LEDGER_PATH_RE = re.compile(r"(?:/(?:[a-z_]{1,40}|[0-9]+|@member[0-9]+|@key[0-9a-f]{16}))+")


def _ledger_segment(key):
    """One path segment: an index, a plain member name, @member<n> for a member marker, else @key<hash> - a ledger
    path never carries supplied text or a marker-shaped string."""
    if isinstance(key, int):
        return str(key)
    if MEMBER_MARKER_RE.fullmatch(key):
        return "@member" + re.search(r"[0-9]+", key).group()
    if PLAIN_KEY_RE.fullmatch(key):
        return key
    return "@key" + hashlib.sha256(key.encode("utf-8", "surrogatepass")).hexdigest()[:16]


def _marker_paths(value, skip):
    """Ledger paths of every exact marker (a WITHHELD_TEXT value or a MEMBER_MARKER member name) under value; paths
    in `skip` (tuples) are not entered. Iterative: nesting is bounded at load (A14)."""
    found, stack = set(), [(value, ())]
    while stack:
        item, path = stack.pop()
        if isinstance(item, dict):
            for key, child in item.items():
                sub = path + (key,)
                if sub in skip:
                    continue
                if isinstance(key, str) and MEMBER_MARKER_RE.fullmatch(key):
                    found.add(sub)
                stack.append((child, sub))
        elif isinstance(item, list):
            stack += [(child, path + (i,)) for i, child in enumerate(item)]
        elif is_withheld(item) and path:
            found.add(path)
    return {"/" + "/".join(_ledger_segment(s) for s in p) for p in found}


def record_marker_paths(record):
    return _marker_paths(record, {(k,) for k in RECORD_DERIVED + (LEDGER_KEY,)})


def packet_marker_paths(packet):
    return _marker_paths(packet, set(PACKET_DERIVED))


def write_ledgers(packet):
    """Record every marker the sweep placed or kept (D21). Run at the end of sweep_packet, after validate_packet has
    bound every input marker to its listed path, so only bound markers and this stage's own are recorded. An empty
    ledger is left out."""
    for name in LEDGER_RECORDS:
        for record in packet.get(name) or []:
            if isinstance(record, dict):
                paths = sorted(record_marker_paths(record))
                if paths:
                    record[LEDGER_KEY] = paths
                else:
                    record.pop(LEDGER_KEY, None)
    provenance = packet.get("provenance")
    if isinstance(provenance, dict):
        paths = sorted(packet_marker_paths(packet))
        if paths:
            provenance[LEDGER_KEY] = paths
        else:
            provenance.pop(LEDGER_KEY, None)


def _check_ledger(where, listed, have):
    if listed is None:
        listed = []
    if not all(isinstance(p, str) and LEDGER_PATH_RE.fullmatch(p) for p in listed):
        raise SchemaError(f"invalid input: {where}.{LEDGER_KEY} must list ledger paths ({LEDGER_CITATION})")
    if len(set(listed)) != len(listed):
        raise SchemaError(f"invalid input: {where}.{LEDGER_KEY} lists a path twice ({LEDGER_CITATION})")
    unbound, empty = len(have - set(listed)), len(set(listed) - have)
    if unbound or empty:
        raise SchemaError(f"invalid input: {where}: {unbound} withheld placeholder(s) not listed in {LEDGER_KEY} and "
                          f"{empty} listed path(s) holding no placeholder; every placeholder is bound to its own "
                          f"hold at its exact path, and an engine writes both ({LEDGER_CITATION}) - no output was "
                          "written")


def check_withheld_bindings(packet):
    """D21: every exact marker outside the re-derived sections is listed at its exact path in its record's ledger
    (or the packet's), every listed path holds a marker, and a signal or entry that carries one is held
    (embedded_instruction). A hold elsewhere never makes a newly placed marker valid."""
    for name in LEDGER_RECORDS:
        for i, record in enumerate(packet.get(name) or []):
            have = record_marker_paths(record)
            _check_ledger(f"{name}[{i}]", record.get(LEDGER_KEY), have)
            if have and record.get("embedded_instruction") is not True:
                raise SchemaError(f"invalid input: {name}[{i}] carries a withheld placeholder but is not held "
                                  f"(embedded_instruction) ({LEDGER_CITATION})")
    _check_ledger("provenance", (packet.get("provenance") or {}).get(LEDGER_KEY), packet_marker_paths(packet))


def _holds_marker(value):
    if isinstance(value, str):
        return is_withheld(value)
    if isinstance(value, dict):
        return any(MEMBER_MARKER_RE.fullmatch(str(k)) or _holds_marker(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_holds_marker(v) for v in value)
    return False


def _owned_exclusion(record, packet):
    """A withheld excluded-signal ID whose engine-written reason names a linking entry that carries the marker and
    is itself held: that entry owns the hold (_sweep_excluded_ids), so the marker does not hold the packet."""
    reason = record.get("reason")
    if record.get("activity_id") != WITHHELD_TEXT or not isinstance(reason, str) or not reason.startswith("linked from ") \
            or _holds_marker({k: v for k, v in record.items() if k != "activity_id"}):
        return False
    return any(isinstance(e, dict) and e.get("embedded_instruction") is True and isinstance(e.get("entry_id"), str)
               and isinstance(e.get("excluded_activity_ids"), list) and WITHHELD_TEXT in e["excluded_activity_ids"]
               and reason.startswith(f"linked from {e['entry_id']} ") for e in packet.get("time_entries") or [])


def _without_owned_exclusions(packet):
    """Packet metadata minus entry-owned excluded-ID markers (in provenance, and the same count in the summary
    list derived from it)."""
    provenance, summary = packet.get("provenance"), packet.get("prebill_summary")
    if not isinstance(provenance, dict) or not isinstance(provenance.get("excluded_signals"), list):
        return packet
    owned = [r for r in provenance["excluded_signals"] if isinstance(r, dict) and _owned_exclusion(r, packet)]
    if not owned:
        return packet
    packet = dict(packet, provenance=dict(provenance, excluded_signals=[
        r for r in provenance["excluded_signals"] if not any(r is o for o in owned)]))
    if isinstance(summary, dict) and isinstance(summary.get("excluded_signal_ids"), list):
        ids, drop = [], len(owned)
        for value in summary["excluded_signal_ids"]:
            if value == WITHHELD_TEXT and drop:
                drop -= 1
                continue
            ids.append(value)
        packet["prebill_summary"] = dict(summary, excluded_signal_ids=ids)
    return packet


def packet_held(packet):
    """True when packet metadata (anything outside the line items) carries a withheld marker (#11.3): every entry
    is held for review. A marker-named member inside a line item holds the packet too. A withheld excluded-signal
    ID that a held entry links is that entry's hold, not the packet's (_owned_exclusion)."""
    if not isinstance(packet, dict):
        return False
    packet = _without_owned_exclusions(packet)
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
    # A21: an ID that folds to nothing ("-", "_", a format character) is blank and could equal another blank key.
    if not isinstance(value, str) or not canon_id(value):
        _bad(where, "a non-empty string that names something (not only separators or format characters)", value)


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
    # A11: source keys are unique in canonical form - "Calendar" next to "calendar" is one source named twice.
    repeat = _first_repeat([_id_key(key) for key in sources])
    if repeat:
        raise SchemaError(f"invalid input: {where} names one source twice in canonical form (member #{repeat[0] + 1} "
                          f"and member #{repeat[1] + 1}); duplicate keys are malformed")
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
              ("activity_ids", "strings", True), ("excluded_activity_ids", "strings", True),
              ("cross_person_activity_ids", "strings", True),
              ("submitted_phase_code", "text", False), ("submitted_task_code", "text", False),
              ("embedded_instruction", "bool", False), ("source", "str", False),
              ("confidence", "confidence", False), ("citations", "strings", False))
DRAFT_SPEC = (("narrative", "str", True), ("status", DRAFT_STATUSES, True), ("needs_review", "bool", True),
              ("confidence", "confidence", True), ("citations", "strings", True), ("review_reasons", "strings", False),
              ("linked_activity_ids", "strings", True), ("covered_activity_ids", "strings", True),
              ("excluded_activity_ids", "strings", True))
REWRITE_SPEC = (("narrative", "str", True), ("status", REWRITE_STATUSES, True), ("review_reasons", "strings", False),
                ("linked_activity_ids", "strings", True), ("confidence", "confidence", False),
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


def _id_key(value):
    """The canonical join key of an ID. A21: a missing, null or blank ID gets a fresh key that equals nothing, so two
    blank keys never match in a join, link, ownership check or reconciliation."""
    key = canon_id(value)
    return key if key else object()


def check_unique_ids(packet):
    """IDs the engines index by must be unique (#13.2): an index keyed by a repeated ID would keep one record and
    silently drop the other (a hidden signal, missing time or entry). The error names positions, never the ID.
    IDs compare in canonical form (canon_id: NFKC, case, format characters and - _ . separators folded), so a
    variant spelling of an ID is the same ID, never a second record that escapes a duplicate or overlap rule."""
    provenance = packet.get("provenance") or {}
    lists = (("activity_signals", packet.get("activity_signals") or [], "activity_id"),
             ("time_entries", packet.get("time_entries") or [], "entry_id"),
             ("provenance.excluded_signals", provenance.get("excluded_signals") or [], "activity_id"),
             ("provenance.excluded_entries", provenance.get("excluded_entries") or [], "entry_id"))
    for where, records, key in lists:
        # Withheld excluded IDs (#11.3) are all the same marker and are never used as an index key.
        exempt = WITHHELD_TEXT if where.startswith("provenance.") else None
        repeat = _first_repeat([object() if exempt and r.get(key) == exempt else _id_key(r.get(key)) for r in records])
        if repeat:
            raise SchemaError(f"invalid input: {where}[{repeat[1]}].{key} repeats {where}[{repeat[0]}].{key}; "
                              "duplicate IDs are malformed (one record would silently replace the other)")
    # A record is active or excluded, never both: an active record listed as excluded would be rendered while the
    # report says it was excluded (or the exclusion would be silently ignored).
    for (active, records, key), (excluded, dropped, _) in ((lists[0], lists[2]), (lists[1], lists[3])):
        gone = {_id_key(r.get(key)): j for j, r in enumerate(dropped) if r.get(key) != WITHHELD_TEXT}
        for i, record in enumerate(records):
            if _id_key(record.get(key)) in gone:
                raise SchemaError(f"invalid input: {active}[{i}].{key} is also listed in {excluded}"
                                  f"[{gone[_id_key(record.get(key))]}]; a record is either active or excluded, never both")
    # Links are looked up by exact ID downstream, so a link may name a known activity only by its exact spelling;
    # a link that matches one only after canonical folding would silently miss it (activity_pull resolves them).
    known = {}
    for records in (lists[0][1], lists[2][1]):
        for r in records:
            if isinstance(r.get("activity_id"), str) and r.get("activity_id") != WITHHELD_TEXT:
                known.setdefault(canon_id(r["activity_id"]), r["activity_id"])
    owners = {_id_key(s.get("activity_id")): s.get("person") for s in lists[0][1]
              if isinstance(s, dict) and s.get("activity_id") != WITHHELD_TEXT}
    for i, entry in enumerate(packet.get("time_entries") or []):
        for key in ("activity_ids", "excluded_activity_ids", "cross_person_activity_ids"):
            links = entry.get(key) or []
            # A withheld link (#11.3) is the shared marker, never an index key: repeats of it are not duplicates.
            repeat = _first_repeat([object() if a == WITHHELD_TEXT else _id_key(a) for a in links])
            if repeat:
                raise SchemaError(f"invalid input: time_entries[{i}].{key}[{repeat[1]}] repeats "
                                  f"time_entries[{i}].{key}[{repeat[0]}]; a link is listed once")
            for j, link in enumerate(links):
                if not isinstance(link, str) or (link != WITHHELD_TEXT and not canon_id(link)):
                    raise SchemaError(f"invalid input: time_entries[{i}].{key}[{j}] is blank; a link names an activity "
                                      "ID (a blank key never matches another, client-billing-guidelines.md #13.6)")
                if isinstance(link, str) and link != WITHHELD_TEXT and known.get(canon_id(link), link) != link:
                    raise SchemaError(f"invalid input: time_entries[{i}].{key}[{j}] names a known activity ID "
                                      "in a variant spelling; links must use the activity's exact ID")
        lists_of = {key: [_id_key(a) for a in entry.get(key) or [] if a != WITHHELD_TEXT]
                    for key in ("activity_ids", "excluded_activity_ids", "cross_person_activity_ids")}
        for one, other in (("activity_ids", "excluded_activity_ids"), ("activity_ids", "cross_person_activity_ids"),
                           ("excluded_activity_ids", "cross_person_activity_ids")):
            both = [j for j, a in enumerate(lists_of[one]) if a in set(lists_of[other])]
            if both:
                rule = ("a link is either active or excluded" if other == "excluded_activity_ids" and one == "activity_ids"
                        else "a link is listed in one place only")
                raise SchemaError(f"invalid input: time_entries[{i}].{one}[{both[0]}] is also in "
                                  f"time_entries[{i}].{other}; {rule}")
        # #12.2: an active link is evidence only for the same timekeeper. A link to another person's activity is
        # malformed at every stage (activity_pull records it in cross_person_activity_ids instead). A withheld name
        # is not compared: the entry or signal carrying it is already held.
        person = entry.get("person")
        for j, link in enumerate(entry.get("activity_ids") or []):
            owner = owners.get(_id_key(link)) if link != WITHHELD_TEXT else None
            if (isinstance(owner, str) and isinstance(person, str) and not is_withheld(owner)
                    and not is_withheld(person) and not same_person(owner, person)):
                raise SchemaError(f"invalid input: time_entries[{i}].activity_ids[{j}] links an activity recorded for "
                                  "another timekeeper; a linked activity is evidence only for its own timekeeper "
                                  f"({CROSS_PERSON_CITATION})")


# --- Exclusions hold in every section; blank keys never match (client-billing-guidelines.md #13.6) -----------
# Whatever activity_pull or the signal policy marks excluded - an excluded or out-of-scope activity, a skipped source,
# an excluded entry, a withheld colleague - is refused, in canonical form, in every other section that names it, at
# every stage (A20). Every keyed collection is checked for canonical duplicates before anything is joined on it, and
# a blank key is never a key (A11, A21). Messages name sections and positions only.
EXCLUSION_CITATION = "client-billing-guidelines.md #13.6"


def _keys(values):
    return [_id_key(v) for v in values if v != WITHHELD_TEXT]


def _refuse_repeat(where, values, key=_id_key):
    repeat = _first_repeat([object() if v == WITHHELD_TEXT else key(v) for v in values])
    if repeat:
        raise SchemaError(f"invalid input: {where}[{repeat[1]}] repeats {where}[{repeat[0]}] in canonical form; "
                          f"duplicate keys are malformed ({EXCLUSION_CITATION})")


def _person_key(name):
    key = person_key(name)
    return key if key else object()


def check_scope_state(packet):
    """provenance.timekeeper_scope agrees with itself (#12.1, A20): a self-scope lists only the requester and no team
    view; a team scope lists the requester among its people and withholds no one; a withheld colleague is never the
    requester or a listed person; names are unique in canonical form. A withheld name is not compared."""
    scope = (packet.get("provenance") or {}).get("timekeeper_scope")
    if not isinstance(scope, dict):
        return
    where = "provenance.timekeeper_scope"
    requester, people, withheld = scope.get("requester"), scope.get("people"), scope.get("withheld")
    if isinstance(people, list):
        _refuse_repeat(f"{where}.people", people, key=_person_key)
    named = lambda v: isinstance(v, str) and not is_withheld(v)  # noqa: E731
    if scope.get("mode") == "self":
        if scope.get("team_view") is not None:
            raise SchemaError(f"invalid input: {where}.team_view is set on a self scope ({SCOPE_CITATION})")
        if not isinstance(people, list) or len(people) != 1 or (
                named(people[0]) and named(requester) and not same_person(people[0], requester)):
            raise SchemaError(f"invalid input: {where}.people must list exactly the requester on a self scope "
                              f"({SCOPE_CITATION}, {EXCLUSION_CITATION})")
    elif scope.get("mode") == "team":
        if withheld is not None:
            raise SchemaError(f"invalid input: {where}.withheld is set on a team scope ({SCOPE_CITATION}, "
                              f"{EXCLUSION_CITATION})")
        if isinstance(people, list) and named(requester) and not any(
                is_withheld(p) or same_person(p, requester) for p in people):
            raise SchemaError(f"invalid input: {where}.people does not list the requester ({SCOPE_CITATION}, "
                              f"{EXCLUSION_CITATION})")
    if isinstance(withheld, dict) and isinstance(withheld.get("requested"), list):
        requested = withheld["requested"]
        _refuse_repeat(f"{where}.withheld.requested", requested, key=_person_key)
        listed = [p for p in (people if isinstance(people, list) else []) + [requester] if named(p)]
        for n, name in enumerate(requested):
            if named(name) and any(same_person(name, p) for p in listed):
                raise SchemaError(f"invalid input: {where}.withheld.requested[{n}] names a person the scope allows; a "
                                  f"withheld colleague is never in scope ({SCOPE_CITATION}, {EXCLUSION_CITATION})")


def check_exclusions(packet, level):
    """A20/A21 across sections. Excluded activity IDs (provenance.excluded_signals) and out-of-scope rows are never an
    active signal or an evidence link; an out-of-scope row is never a cross-person link either; a source activity_pull
    skipped is never read and no signal claims it; secondary keyed collections are unique; on governed data a
    missing-time item names a present, unlinked signal and an exception item a present entry (never an excluded one)."""
    provenance = packet.get("provenance") or {}
    signals = packet.get("activity_signals") or []
    entries = packet.get("time_entries") or []
    excluded = set(_keys(r.get("activity_id") for r in provenance.get("excluded_signals") or []))
    rows = provenance.get("out_of_scope_rows") or []
    _refuse_repeat("provenance.out_of_scope_rows", [r.get("activity_id") for r in rows])
    out_of_scope = set(_keys(r.get("activity_id") for r in rows))
    for i, signal in enumerate(signals):
        if _id_key(signal.get("activity_id")) in out_of_scope:
            raise SchemaError(f"invalid input: activity_signals[{i}] is listed in provenance.out_of_scope_rows; an "
                              f"out-of-scope row is never a signal ({EXCLUSION_CITATION})")
    for i, entry in enumerate(entries):
        for key, barred in (("activity_ids", excluded | out_of_scope), ("cross_person_activity_ids", out_of_scope)):
            for j, link in enumerate(entry.get(key) or []):
                if link != WITHHELD_TEXT and _id_key(link) in barred:
                    raise SchemaError(f"invalid input: time_entries[{i}].{key}[{j}] names an excluded or out-of-scope "
                                      f"activity; an excluded activity is never evidence ({EXCLUSION_CITATION})")
    read = provenance.get("sources_read") or []
    skipped = [s.get("policy_key") for s in provenance.get("skipped_sources") or [] if s.get("policy_key")]
    _refuse_repeat("provenance.sources_read", read)
    _refuse_repeat("provenance.skipped_sources (policy_key)", skipped)
    if set(_keys(read)) & set(_keys(skipped)):
        raise SchemaError(f"invalid input: provenance.skipped_sources names a source in provenance.sources_read; a "
                          f"source is read or skipped, never both ({EXCLUSION_CITATION})")
    skipped_keys = set(_keys(skipped))
    for i, signal in enumerate(signals):
        if _id_key(source_key(signal.get("source")) or "") in skipped_keys:
            raise SchemaError(f"invalid input: activity_signals[{i}] comes from a source activity_pull skipped (not "
                              f"read); a skipped source supplies no signal ({EXCLUSION_CITATION})")
    if level < 3:
        return
    present = {_id_key(s.get("activity_id")) for s in signals}
    linked = {_id_key(a) for e in entries for a in e.get("activity_ids") or [] if a != WITHHELD_TEXT}
    missing = packet.get("missing_time_report") or []
    _refuse_repeat("missing_time_report (activity_id)", [m.get("activity_id") for m in missing])
    for n, item in enumerate(missing):
        key = _id_key(item.get("activity_id"))
        if item.get("activity_id") != WITHHELD_TEXT and (key not in present or key in linked or key in excluded):
            raise SchemaError(f"invalid input: missing_time_report[{n}] does not name a present, unlinked activity "
                              f"signal ({EXCLUSION_CITATION})")
    active = {_id_key(e.get("entry_id")) for e in entries}
    dropped = set(_keys(r.get("entry_id") for r in provenance.get("excluded_entries") or []))
    items = packet.get("exception_list") or []
    ids = [x.get("entry_id") for x in items if x.get("entry_id") is not None]
    _refuse_repeat("exception_list (entry_id)", ids)
    if sum(1 for x in items if x.get("entry_id") is None) > 1:
        raise SchemaError(f"invalid input: exception_list has more than one missing-time item ({EXCLUSION_CITATION})")
    for n, item in enumerate(items):
        entry_id = item.get("entry_id")
        if entry_id is not None and entry_id != WITHHELD_TEXT and (
                _id_key(entry_id) not in active or _id_key(entry_id) in dropped):
            raise SchemaError(f"invalid input: exception_list[{n}] does not name a present time entry; an excluded "
                              f"entry is never listed ({EXCLUSION_CITATION})")


# Link state (#13.4). activity_pull resolves each entry's links once into three disjoint, required lists
# (activity_ids, excluded_activity_ids, cross_person_activity_ids); narrative_draft copies them into the draft and words
# its link reasons with these templates; guideline_check derives its link flags from them. check_link_state reconciles
# every copy exactly at every later stage.
LINK_STATE_CITATION = "client-billing-guidelines.md #13.4"
LINK_BLOCK_CITATIONS = "client-billing-guidelines.md #2.1 / #2.2"
EXCLUDED_LINKS_PREFIX = "linked signal(s) from a disabled or unresolvable source were excluded from evidence: "
CROSS_PERSON_REASON_RE = re.compile(r"\d+ linked activit(?:y|ies) recorded for another timekeeper; ")
UNCOVERED_PREFIX = "linked activity not described in any draft or suggested rewrite: "
MULTI_LINK_RE = re.compile(r"entry links \d+ activities; ")
REWRITE_SCOPE_PREFIX = "covers "
GROUNDED_STATUSES = ("engine_generated_from_activity", "needs_review", "needs_review_insufficient_detail")


def excluded_links_reason(links, packet):
    return EXCLUDED_LINKS_PREFIX + describe_excluded(links, packet) + " (client-billing-guidelines.md #10.1)"


def cross_person_reason(count):
    return (f"{count} linked activit{'y' if count == 1 else 'ies'} recorded for another timekeeper; not drafted from "
            f"or counted as evidence ({CROSS_PERSON_CITATION})")


def uncovered_reason(ids):
    return UNCOVERED_PREFIX + ", ".join(ids)


def multi_link_reason(count):
    return f"entry links {count} activities; each is described, review for block billing ({LINK_BLOCK_CITATIONS})"


def rewrite_scope_reason(activity_id, others):
    return (f"{REWRITE_SCOPE_PREFIX}{activity_id} only; this entry also links " + ", ".join(others)
            + f" - use with the other rewrites or split the entry ({LINK_BLOCK_CITATIONS})")


def _is_link_reason(text):
    return isinstance(text, str) and (text.startswith((EXCLUDED_LINKS_PREFIX, UNCOVERED_PREFIX))
                                      or bool(CROSS_PERSON_REASON_RE.match(text)) or bool(MULTI_LINK_RE.match(text)))


def _link_keys(links):
    return [WITHHELD_TEXT if a == WITHHELD_TEXT else _id_key(a) for a in links]


def _same_reasons(got, want):
    return sorted(got) == sorted(want)


def _check_moved_links(where, active, excluded, linked, drafted_excluded):
    """The only change a later stage makes to an entry's links: its narrower signal policy moves an active link to
    excluded_activity_ids (filter_packet), appending it. So activity_ids is draft.linked_activity_ids minus the moved
    links (in order), and excluded_activity_ids is draft.excluded_activity_ids followed by exactly the moved links. A
    withheld excluded ID (#11.3) stands for the ID it replaced."""
    a, x, dl, dx = (_link_keys(v) for v in (active, excluded, linked, drafted_excluded))
    position = 0
    moved = []
    for key in dl:
        if position < len(a) and a[position] == key:
            position += 1
        else:
            moved.append(key)
    if position != len(a):
        raise SchemaError(f"invalid input: {where}.activity_ids does not match {where}.draft.linked_activity_ids; "
                          f"link state is reconciled exactly at every stage ({LINK_STATE_CITATION})")
    if len(x) < len(dx) or any(have != want and have != WITHHELD_TEXT for have, want in zip(x, dx)):
        raise SchemaError(f"invalid input: {where}.excluded_activity_ids does not match "
                          f"{where}.draft.excluded_activity_ids; link state is reconciled exactly at every stage "
                          f"({LINK_STATE_CITATION})")
    rest = x[len(dx):]
    for key in moved:
        if key in rest:
            rest.remove(key)
        elif WITHHELD_TEXT in rest:
            rest.remove(WITHHELD_TEXT)
        else:
            rest.append(None)
            break
    if rest:
        raise SchemaError(f"invalid input: {where}: the links in draft.linked_activity_ids but not in activity_ids are "
                          "not exactly the links a later signal policy moved to excluded_activity_ids; link state is "
                          f"reconciled exactly at every stage ({LINK_STATE_CITATION})")


def _check_draft_links(where, entry, draft, packet):
    """The draft's link lists and every link-derived review reason, against the entry's link state."""
    dl, dx, covered = draft["linked_activity_ids"], draft["excluded_activity_ids"], draft["covered_activity_ids"]
    _check_moved_links(where, entry["activity_ids"], entry["excluded_activity_ids"], dl, dx)
    keys, cov = _link_keys(dl), _link_keys(covered)
    if len(set(keys)) != len(keys) or len(set(cov)) != len(cov) or not set(cov) <= set(keys):
        raise SchemaError(f"invalid input: {where}.draft.covered_activity_ids must list draft.linked_activity_ids, each "
                          f"once ({LINK_STATE_CITATION})")
    rewrites = draft.get("suggested_rewrites") or []
    for n, rewrite in enumerate(rewrites):
        if len(rewrite["linked_activity_ids"]) != 1 or _link_keys(rewrite["linked_activity_ids"])[0] not in keys:
            raise SchemaError(f"invalid input: {where}.draft.suggested_rewrites[{n}].linked_activity_ids must name one "
                              f"activity in draft.linked_activity_ids ({LINK_STATE_CITATION})")
    status = draft["status"]
    if rewrites:
        if cov != [k for r in rewrites for k in _link_keys(r["linked_activity_ids"])]:
            raise SchemaError(f"invalid input: {where}.draft.covered_activity_ids does not match the suggested rewrites' "
                              f"linked_activity_ids ({LINK_STATE_CITATION})")
    elif cov and sorted(cov, key=str) != sorted(keys, key=str):
        raise SchemaError(f"invalid input: {where}.draft.covered_activity_ids must be empty or cover every linked "
                          f"activity of a drafted narrative ({LINK_STATE_CITATION})")
    if (status == "needs_activity_evidence" and dl) or (status in GROUNDED_STATUSES and not dl):
        raise SchemaError(f"invalid input: {where}.draft.status {status} does not match draft.linked_activity_ids "
                          f"({LINK_STATE_CITATION})")
    reasons = draft.get("review_reasons") or []
    # needs_review is derived from the reasons and the status (narrative_draft; guideline_check only adds a reason and
    # sets it), so removing a link list together with its reason still leaves a mismatch here.
    if draft["needs_review"] != (bool(reasons) or status not in ("engine_generated_from_activity",
                                                                  "existing_timesheet_narrative")):
        raise SchemaError(f"invalid input: {where}.draft.needs_review does not match its review reasons and status "
                          f"({LINK_STATE_CITATION})")
    if WITHHELD_TEXT in reasons:
        return  # a withheld reason holds the entry (D20); the lists above are still reconciled
    want = [excluded_links_reason(dx, packet)] if dx else []
    if entry["cross_person_activity_ids"]:
        want.append(cross_person_reason(len(entry["cross_person_activity_ids"])))
    uncovered = [a for a, k in zip(dl, keys) if k not in set(cov)]
    if uncovered and status != "needs_review_embedded_instruction":
        want.append(uncovered_reason(uncovered))
    multi = [r for r in reasons if isinstance(r, str) and MULTI_LINK_RE.match(r)]
    if status in GROUNDED_STATUSES and len(dl) > 1:
        want.append(multi_link_reason(len(dl)))
    elif status == "needs_review_embedded_instruction" and multi == [multi_link_reason(len(dl))] and len(dl) > 1:
        want.append(multi[0])  # drafted, then withheld for the entry's own text: the reason is kept
    if not _same_reasons([r for r in reasons if _is_link_reason(r)], want):
        raise SchemaError(f"invalid input: {where}.draft.review_reasons do not match the entry's link state; link "
                          f"state is reconciled exactly at every stage ({LINK_STATE_CITATION})")
    for n, rewrite in enumerate(rewrites):
        got = [r for r in rewrite.get("review_reasons") or [] if isinstance(r, str) and r.startswith(REWRITE_SCOPE_PREFIX)]
        if WITHHELD_TEXT in (rewrite.get("review_reasons") or []):
            continue
        one = rewrite["linked_activity_ids"][0]
        want = ([rewrite_scope_reason(one, [a for a, k in zip(dl, keys) if k != _link_keys([one])[0]])]
                if len(dl) > 1 else [])
        if got != want:
            raise SchemaError(f"invalid input: {where}.draft.suggested_rewrites[{n}].review_reasons do not match the "
                              f"entry's links ({LINK_STATE_CITATION})")


def check_link_state(packet, level):
    """Every copy of an entry's link state agrees exactly (#13.4, B5): a partial edit that deletes or changes one
    copy is refused with no output, never governed on the copy that was left. Messages name fields and positions only.

    - every stage: every evidence link names a signal in the packet; excluded links are recorded in
      provenance.excluded_signals, and an exclusion record that names a
      present entry as its linker is listed in that entry's excluded_activity_ids; a cross-person link never names
      the timekeeper's own activity;
    - drafted on: the draft's linked, excluded and covered lists, the rewrites' links, the draft status and every
      link-derived review reason (excluded, cross-person, uncovered, multi-link, rewrite scope) and needs_review
      against the entry;
    - governed: the link flags (disabled_source_signal, cross_person_link), the exception list's excluded links and
      evidence_hours_same_date against the entry's links."""
    provenance = packet.get("provenance") or {}
    records = provenance.get("excluded_signals") or []
    recorded = {_id_key(r.get("activity_id")) for r in records if r.get("activity_id") != WITHHELD_TEXT}
    signals = {_id_key(s.get("activity_id")): s for s in packet.get("activity_signals") or []}
    exceptions = {_id_key(x.get("entry_id")): x for x in packet.get("exception_list") or []
                  if isinstance(x.get("entry_id"), str) and x.get("entry_id") != WITHHELD_TEXT}
    renamed = any(is_withheld(s.get("activity_id")) for s in packet.get("activity_signals") or [])
    for i, entry in enumerate(packet.get("time_entries") or []):
        where = f"time_entries[{i}]"
        # An evidence link always names a signal in the packet (activity-pull keeps only resolved links, and a link
        # to an excluded signal is moved to excluded_activity_ids); a dangling link means one copy was edited.
        for j, link in enumerate(entry["activity_ids"]):
            if not renamed and not is_withheld(link) and _id_key(link) not in signals:
                raise SchemaError(f"invalid input: {where}.activity_ids[{j}] does not name an activity signal in the "
                                  f"packet ({LINK_STATE_CITATION})")
        for j, link in enumerate(entry["excluded_activity_ids"]):
            if link != WITHHELD_TEXT and _id_key(link) not in recorded:
                raise SchemaError(f"invalid input: {where}.excluded_activity_ids[{j}] is not recorded in "
                                  f"provenance.excluded_signals ({LINK_STATE_CITATION})")
        entry_id = entry.get("entry_id")
        if isinstance(entry_id, str) and entry_id != WITHHELD_TEXT:
            listed = set(_link_keys(entry["excluded_activity_ids"]))
            for n, record in enumerate(records):
                reason = record.get("reason")
                if (isinstance(reason, str) and reason.startswith(f"linked from {entry_id} ")
                        and _link_keys([record.get("activity_id")])[0] not in listed):
                    raise SchemaError(f"invalid input: provenance.excluded_signals[{n}] records a link from {where} "
                                      f"that {where}.excluded_activity_ids does not list ({LINK_STATE_CITATION})")
        person = entry.get("person")
        for j, link in enumerate(entry["cross_person_activity_ids"]):
            owner = (signals.get(_id_key(link)) or {}).get("person") if link != WITHHELD_TEXT else None
            if (isinstance(owner, str) and isinstance(person, str) and not is_withheld(owner)
                    and not is_withheld(person) and same_person(owner, person)):
                raise SchemaError(f"invalid input: {where}.cross_person_activity_ids[{j}] names the timekeeper's own "
                                  f"activity ({CROSS_PERSON_CITATION}, {LINK_STATE_CITATION})")
        if level >= 1:
            _check_draft_links(where, entry, entry["draft"], packet)
        if level >= 3:
            have = {f.get("flag") for f in entry["compliance"].get("flags") or []}
            for flag, links in (("disabled_source_signal", entry["excluded_activity_ids"]),
                                ("cross_person_link", entry["cross_person_activity_ids"])):
                if (flag in have) != bool(links):
                    raise SchemaError(f"invalid input: {where}.compliance flag {flag} does not match the entry's "
                                      f"links ({LINK_STATE_CITATION})")
            item = exceptions.get(_id_key(entry_id)) if isinstance(entry_id, str) else None
            if item is not None and _link_keys(item.get("excluded_activity_ids") or []) != _link_keys(
                    entry["excluded_activity_ids"]):
                raise SchemaError(f"invalid input: exception_list excluded_activity_ids for {where} do not match "
                                  f"{where}.excluded_activity_ids ({LINK_STATE_CITATION})")
            linked = [signals.get(_id_key(a)) for a in entry["activity_ids"] if a != WITHHELD_TEXT]
            hours = round(sum(s.get("duration_hours", 0) for s in linked
                              if isinstance(s, dict) and s.get("date") == entry.get("date")), 2)
            if entry["compliance"].get("evidence_hours_same_date", hours) != hours:
                raise SchemaError(f"invalid input: {where}.compliance.evidence_hours_same_date does not match the "
                                  f"entry's linked activity ({LINK_STATE_CITATION})")



# --- Engine-derived values are re-derived at every stage (client-billing-guidelines.md #13.5) ----------------
# A value an engine derives from the packet is never trusted as carried: every later stage derives it again from the
# screened fields it came from and refuses a packet whose carried copy differs (B5). That covers the signal
# annotations activity-pull derives (billable_signal from the activity class, confidence from the workplan match)
# and every draft narrative-draft builds (narrative, status, confidence, review reasons, links, citations and the
# suggested rewrites). The drafting rules live here so that narrative-draft and every later stage run the same code.

DERIVED_CITATION = "client-billing-guidelines.md #13.5"
DRAFT_ENGINE = "engine:narrative_draft"
NON_BILLABLE_CLASSES = ("internal_admin", "billing_hygiene")  # client-billing-guidelines.md #5.1
MATCHED_CONFIDENCE = {"calendar": 0.96, "document_activity": 0.94}  # a workplan row states the purpose
UNMATCHED_CONFIDENCE = 0.70  # below the client-billing-guidelines.md #9.1 floor -> held for review
DRAFT_MIN_WORDS = 12  # client-billing-guidelines.md #1.1
EXISTING_NARRATIVE_CONFIDENCE = 0.94
NO_EVIDENCE_CONFIDENCE = 0.35
VERB_BY_CLASS = (
    ("document_analysis", "Analyzed"),
    ("research", "Researched"),
    ("deliverable_drafting", "Drafted"),
    ("internal_admin", "Coordinated"),
    ("billing_hygiene", "Reviewed"),
)
DRAFT_ONLY_SECTIONS = ("prebill_summary", "missing_time_report", "exception_list")  # written after drafting


def billable_class(activity_class):
    """billable_signal as activity-pull derives it from the activity class (#5.1)."""
    return not class_in(activity_class, NON_BILLABLE_CLASSES)


def signal_confidence(key, purpose):
    """A signal's confidence as activity-pull derives it: a workplan row that states the purpose, or the floor."""
    return MATCHED_CONFIDENCE[key] if purpose is not None else UNMATCHED_CONFIDENCE


def check_signal_annotations(packet):
    """billable_signal and confidence on every signal from an activity-pull source equal their derivation (#13.5).
    A signal from any other source is excluded by the signal policy before any rule reads it."""
    for i, signal in enumerate(packet.get("activity_signals") or []):
        key = source_key(signal.get("source"))
        if key not in MATCHED_CONFIDENCE:
            continue
        if signal["billable_signal"] is not billable_class(signal.get("activity_class")):
            raise SchemaError(f"invalid input: activity_signals[{i}].billable_signal does not match its activity "
                              f"class ({DERIVED_CITATION})")
        if signal["confidence"] != signal_confidence(key, signal.get("purpose")):
            raise SchemaError(f"invalid input: activity_signals[{i}].confidence does not match its workplan match "
                              f"({DERIVED_CITATION})")


def draft_words(text):
    # Same whitespace word count as guideline_check (client-billing-guidelines.md #1.1).
    return (text or "").split()


def join_names(names):
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def is_calendar(activity):
    return (source_key(activity.get("source")) == "calendar" or bool(activity.get("meeting_id"))
            or class_in(activity.get("activity_class"), ("client_meeting",)))


def flagged_activities(linked):
    """(IDs, hits) of linked activities whose free text trips the embedded-instruction tripwire or is
    too long to screen (#11.1)."""
    ids, hits = [], []
    for a in linked:
        found = screen(signal_texts(a))
        if a.get("embedded_instruction") is True or found:
            ids.append(a.get("activity_id"))
            hits += found
    return ids, hits


def clause(entry, activity):
    """One grounded clause for one activity. Returns (text without final period, reasons)."""
    person = entry.get("person")
    reasons = []
    if is_calendar(activity):
        verb = "Led" if activity.get("organizer") and same_person(activity.get("organizer"), person) else "Attended"
    else:
        verb = next((v for c, v in VERB_BY_CLASS if class_in(activity.get("activity_class"), (c,))), "Prepared")
    subject, purpose, deliverable = (activity.get(k).strip() if isinstance(activity.get(k), str) else ""
                                     for k in ("subject", "purpose", "deliverable"))
    attendees = activity.get("attendees") if isinstance(activity.get("attendees"), list) else []
    others = [a for a in attendees if isinstance(a, str) and a.strip() and not same_person(a, person)]
    text = f"{verb} {subject}"
    if others:
        text += f" with {join_names(others)}"
    # Avoid "... for client decision for the X": put the deliverable first when the purpose has "for".
    deliverable_first = bool(deliverable and purpose and " for " in f" {purpose.lower()} ")
    if deliverable_first:
        text += f" for the {deliverable}"
    if purpose:
        text += f" to {purpose}"
    else:
        reasons.append(f"{activity.get('activity_id')} has no recorded purpose; purpose not invented")
    if deliverable and not deliverable_first:
        text += f" for the {deliverable}"
    return text, reasons


def grounded_narrative(entry, linked):
    """Return (narrative, status, confidence, reasons, covered_ids) grounded only in linked activity."""
    if not linked:
        return ("", "needs_activity_evidence", NO_EVIDENCE_CONFIDENCE,
                ["no cited activity signal from an enabled source is linked; nothing to draft from"], [])
    flagged, hits = flagged_activities(linked)
    if flagged:
        why = hold_reason(hits, "linked activity text flagged as embedded_instruction")
        return ("", "needs_review_embedded_instruction", NO_EVIDENCE_CONFIDENCE,
                [f"{why} ({', '.join(flagged)}); "
                 "treated as data and withheld - no narrative drafted from it (client-billing-guidelines.md #11.1, #11.2)"],
                [])
    ordered = sorted(linked, key=lambda a: 0 if class_in(a.get("activity_class"), ("client_meeting",)) else 1)
    parts, reasons = [], []
    for activity in ordered:
        text, why = clause(entry, activity)
        parts.append(text if not parts else text[0].lower() + text[1:])
        reasons.extend(why)
    narrative = "; ".join(parts[:-1]) + ("; and " if len(parts) > 1 else "") + parts[-1] + "."
    if len(parts) == 1:
        narrative = parts[0] + "."
    if len(linked) > 1:
        reasons.append(multi_link_reason(len(linked)))
    status = "engine_generated_from_activity"
    if len(draft_words(narrative)) < DRAFT_MIN_WORDS:
        status = "needs_review_insufficient_detail"
        reasons.append(f"{len(draft_words(narrative))} words from cited metadata; left short rather than padded "
                       "(client-billing-guidelines.md #1.1)")
    elif reasons:
        status = "needs_review"
    confidence = round(min([a.get("confidence", 0.8) for a in linked] + [0.9]), 2)
    return narrative, status, confidence, reasons, [a.get("activity_id") for a in ordered]


def build_narrative(entry, linked):
    """Return (narrative, status, confidence, review_reasons, suggested_rewrites, covered_ids)."""
    existing = (entry.get("narrative") or "").strip()
    if not existing:
        narrative, status, confidence, reasons, covered = grounded_narrative(entry, linked)
        return narrative, status, confidence, reasons, [], covered

    reasons = []
    hits = screen(entry_texts(entry, linked))
    existing_flagged = entry.get("embedded_instruction") is True or bool(hits)
    if existing_flagged:
        reasons.append(hold_reason(hits, "existing narrative flagged as embedded_instruction")
                       + "; withheld from the "
                       "draft and left in the source entry only as evidence for guideline-check, never obeyed "
                       "(client-billing-guidelines.md #11.1, #11.2)")
    suggestions = []
    for activity in linked:
        narrative, status, confidence, why, covered = grounded_narrative(entry, [activity])
        if status == "needs_review_embedded_instruction":
            reasons.extend(why)
            continue
        if not narrative or embedded_instruction(narrative):
            continue
        if len(linked) > 1:
            why = why + [rewrite_scope_reason(
                activity.get("activity_id"), [a.get("activity_id") for a in linked if a is not activity])]
            if status == "engine_generated_from_activity":
                status = "needs_review"
        suggestions.append({
            "narrative": narrative,
            "status": status,
            "review_reasons": why,
            "linked_activity_ids": [activity.get("activity_id")],
            "confidence": confidence,
            "source": DRAFT_ENGINE,
            "citations": sorted(set(safe_citations(activity.get("citations", []))[0])),
        })
    covered = [a for s_ in suggestions for a in s_["linked_activity_ids"]]
    if existing_flagged:
        return "", "needs_review_embedded_instruction", NO_EVIDENCE_CONFIDENCE, reasons, suggestions, covered
    return existing, "existing_timesheet_narrative", EXISTING_NARRATIVE_CONFIDENCE, reasons, suggestions, covered


def draft_hold(packet):
    """packet_held() over the packet as narrative-draft saw it (the sections written after drafting left out)."""
    if not isinstance(packet, dict):
        return False
    return packet_held({k: v for k, v in packet.items() if k not in DRAFT_ONLY_SECTIONS})


def derive_draft(entry, by_id, packet, packet_hold):
    """The draft narrative-draft builds for one entry from the entry, its linked signals and the packet (#13.5).
    by_id maps activity IDs to the packet's signals; packet_hold is draft_hold(packet)."""
    linked = [by_id[a] for a in entry.get("activity_ids", []) if a in by_id]
    narrative, status, confidence, reasons, suggestions, covered = build_narrative(entry, linked)
    # The entry's own text, citations included, is screened like signal text (#11.1): when it trips, the
    # draft is withheld and no flagged entry citation is copied (#11.2).
    entry_hits = screen(entry_texts(entry))
    entry_flagged = entry.get("embedded_instruction") is True or bool(entry_hits)
    entry_citations, entry_citations_dropped = safe_citations(entry.get("citations", []), entry_flagged)
    if (entry_flagged or entry_citations_dropped) and status != "needs_review_embedded_instruction":
        narrative, status, confidence = "", "needs_review_embedded_instruction", NO_EVIDENCE_CONFIDENCE
        reasons.append(hold_reason(entry_hits, "time entry text or citation flagged as embedded_instruction")
                       + "; draft withheld and the flagged text never copied or obeyed "
                       "(client-billing-guidelines.md #11.1, #11.2)")
    excluded_links = entry.get("excluded_activity_ids") or []
    if excluded_links:
        reasons.append(excluded_links_reason(excluded_links, packet))
    cross = entry.get("cross_person_activity_ids") or []
    if cross:
        reasons.append(cross_person_reason(len(cross)))
    uncovered = [a.get("activity_id") for a in linked if a.get("activity_id") not in covered]
    if uncovered and status != "needs_review_embedded_instruction":
        reasons.append(uncovered_reason(uncovered))
    if packet_hold:
        reasons.append(PACKET_HOLD_REASON + f" ({METADATA_CITATION})")
    # Reasons found after the draft was built still gate it: a draft with any reason is never left as a clean
    # engine draft (B6).
    if status == "engine_generated_from_activity" and reasons:
        status = "needs_review"
    if any(INJECTION_CITATION in r for r in reasons):
        citations_extra = [INJECTION_CITATION, WITHHOLD_CITATION]
    else:
        citations_extra = []
    if packet_hold:
        citations_extra.append(METADATA_CITATION)
    citations = []
    for item in linked:
        # Citations are signal text too: flagged citation text is never copied into the draft (#11.2).
        item_flagged = item.get("embedded_instruction") is True or embedded_instruction(signal_texts(item))
        kept, dropped = safe_citations(item.get("citations", []), item_flagged)
        citations.extend(kept)
        if dropped:
            citations_extra = sorted(set(citations_extra + [INJECTION_CITATION, WITHHOLD_CITATION]))
    if excluded_links:
        citations.append(POLICY_CITATION)
    citations.extend(citations_extra)
    draft = {
        "narrative": narrative,
        "status": status,
        "needs_review": bool(reasons) or status not in ("engine_generated_from_activity", "existing_timesheet_narrative"),
        "review_reasons": reasons,
        "word_count": len(draft_words(narrative)),
        "sufficiency": "determined_by_guideline_check (client-billing-guidelines.md #1.3)",
        "linked_activity_ids": list(entry.get("activity_ids", [])),
        "covered_activity_ids": covered,
        "excluded_activity_ids": list(excluded_links),
        "confidence": confidence,
        "source": DRAFT_ENGINE,
        "citations": sorted(set(citations)) or entry_citations,
    }
    if suggestions:
        draft["suggested_rewrites"] = suggestions
    return draft


def derive_drafts(packet, only=None):
    """Draft (or re-draft) every entry in place, or only the entries at the positions in `only`."""
    by_id = {a["activity_id"]: a for a in packet.get("activity_signals", [])}
    hold = draft_hold(packet)
    for n, entry in enumerate(packet.get("time_entries", [])):
        if only is None or n in only:
            entry["draft"] = derive_draft(entry, by_id, packet, hold)


def check_drafts(packet):
    """Every carried draft equals its re-derivation from the packet (#13.5); used on drafted and coded packets.
    A difference in any field is refused with no output, so no edited narrative, status, confidence, reason, link or
    rewrite reaches a rule. Messages name the entry position and the differing field names only."""
    by_id = {a["activity_id"]: a for a in packet.get("activity_signals", [])}
    hold = draft_hold(packet)
    for i, entry in enumerate(packet.get("time_entries") or []):
        want, got = derive_draft(entry, by_id, packet, hold), entry["draft"]
        if got != want:
            # Only the engine's own field names are named; a supplied extra member is counted, never echoed.
            fields = [k for k in want if got.get(k) != want.get(k)]
            extra = len(set(got) - set(want))
            fields += [f"{extra} unexpected field(s)"] if extra else []
            raise SchemaError(f"invalid input: time_entries[{i}].draft does not match its re-derivation from the entry "
                              f"and its linked activity (differing: {', '.join(fields)}) ({DERIVED_CITATION})")


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
    refuse_supplied_markers(packet, exact_ok=True)
    check_unique_ids(packet)
    check_scope_state(packet)
    check_withheld_bindings(packet)
    if level >= 3:
        for key in ("missing_time_report", "exception_list", "prebill_summary"):
            if key not in packet:
                raise SchemaError(f"invalid input: '{key}' missing; {STAGE_HINT['compliance']}")
        check_list(packet["missing_time_report"], "missing_time_report", MISSING_SPEC)
        check_list(packet["exception_list"], "exception_list", EXCEPTION_SPEC)
    check_exclusions(packet, level)
    check_link_state(packet, level)
    check_signal_annotations(packet)
    if level in (1, 2):
        check_drafts(packet)
    if level >= 3:
        summary = check_fields(packet["prebill_summary"], "prebill_summary", SUMMARY_SPEC)
        for verdict, count in summary["verdict_counts"].items():
            check_enum(verdict, VERDICTS, "prebill_summary.verdict_counts key")
            check_number(count, f"prebill_summary.verdict_counts.{verdict}", low=0, integer=True)
    return packet
