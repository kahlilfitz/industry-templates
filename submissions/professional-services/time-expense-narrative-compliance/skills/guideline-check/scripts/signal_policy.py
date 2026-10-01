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
3. Embedded-instruction tripwire (client-billing-guidelines.md #11.1). Free text is data.
   embedded_instruction() normalises (NFKC, strip Unicode Cf, fold Cyrillic/Greek look-alikes,
   fold punctuation and case) and flags text that steers the reviewer, claims an approval or
   waiver, asks for forwarding, or carries an e-mail address or URL.

This file ships as identical copies next to each engine (skills are self-contained);
tests/check_shared_copies.py fails when the copies drift.
"""
import json
import os
import re
import unicodedata

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
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError(f"cannot read signal policy {os.path.basename(path)}: {exc}") from exc
    sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(sources, dict):
        raise PolicyError(f"signal policy {os.path.basename(path)} has no 'sources' object")
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

# Cyrillic and Greek letters that render like Latin ones (NFKC does not fold these).
CONFUSABLES = str.maketrans({
    "\u0430": "a", "\u0432": "b", "\u0435": "e", "\u0451": "e", "\u043a": "k", "\u043c": "m", "\u043d": "h",
    "\u043e": "o", "\u0440": "p", "\u0441": "c", "\u0442": "t", "\u0443": "y", "\u0445": "x", "\u0455": "s",
    "\u0456": "i", "\u0457": "i", "\u0458": "j", "\u04bb": "h", "\u04cf": "l", "\u0501": "d", "\u051b": "q",
    "\u051d": "w", "\u03b1": "a", "\u03b2": "b", "\u03b5": "e", "\u03b7": "n", "\u03b9": "i", "\u03ba": "k",
    "\u03bd": "v", "\u03bf": "o", "\u03c1": "p", "\u03c4": "t", "\u03c5": "u", "\u03c7": "x",
})
_OBJ = (r"(?:this|it|these|that|them|my (?:entry|entries|time|narrative)|"
        r"the (?:entry|entries|time entry|time entries|narrative|narratives|line|charge|item))")
_ENTRY_OBJ = r"(?:(?:this|these|the|my) (?:entry|entries|time entry|time entries|narrative|line|charge|item|one))"
_SUBJ = r"(?:this|it|these|entry|entries|narrative|time|line|charge)"
INSTRUCTION_PATTERNS = (
    # ignore / override the rules
    r"\b(?:ignore|disregard|forget|override|overrule|bypass)\s+(?:(?:all|any|the|your|previous|prior|above|earlier|"
    r"these|those|billing|review|client|engine|system)\s+)*(?:rules?|instructions?|guidelines?|polic(?:y|ies)|flags?|"
    r"checks?|engine|review|reviewer|prompts?|verdicts?)\b",
    # mark / treat it as compliant
    r"\b(?:mark|set|classify|record|log)\s+" + _OBJ + r"(?:\s+\w+){0,2}?\s+(?:as\s+)?(?:compliant|approved|passed|"
    r"clean|cleared|reviewed|billable)\b",
    r"\b(?:treat|consider|regard|handle)\s+" + _OBJ + r"(?:\s+\w+){0,2}?\s+as\s+(?:already\s+)?(?:compliant|approved|"
    r"billable|passed|reviewed|clean|cleared|fine|ok|okay|good|settled|final|verified|accepted|done|closed|resolved)\b",
    # do not check / no need to look at this
    r"\b(?:do not|don t|dont|never|no need to|not necessary to|unnecessary to|needn t|need not|nobody needs to|"
    r"no one needs to|nobody should|no one should|nobody has to|no one has to)\s+(?:double check|flag|reject|review|"
    r"re review|check|hold|question|change|edit|touch|modify|alter|query|escalate|examine|inspect|verify|look at|"
    r"look into|scrutini[sz]e|audit|challenge)\s+" + _OBJ,
    r"\b(?:don t|do not|dont|no need to|needn t)\s+bother\s+(?:checking|reviewing|looking|verifying|flagging|with)\b",
    r"\b" + _SUBJ + r"\s+(?:must|should|need|needs|is|are|shall)\s+not\s+(?:to\s+)?be\s+(?:flagged|reviewed|rejected|"
    r"held|checked|questioned|changed|edited|touched|queried|escalated|examined)\b",
    # approval / sign-off / authority claims about this entry
    r"\bplease\s+approve\s+(?:this|these|the|my|all)\s+(?:\w+\s+){0,2}?(?:entry|entries|pre ?bill|prebill|"
    r"narratives?|timesheets?)\b",
    r"\b" + _SUBJ + r"(?:\s+s|\s+(?:(?:has|have|had)\s+)?(?:already\s+|previously\s+)?(?:been|was|were|is|are))\s+"
    r"(?:been\s+)?(?:already\s+|previously\s+)?(?:pre ?approved|okayed|ok d|signed off|blessed|rubber stamped|"
    r"green ?lit|whitelisted)\b",
    r"\b" + _SUBJ + r"(?:\s+s)?\s+(?:(?:has|have|had)\s+)?(?:(?:already|previously)\s+(?:(?:been|was|were|is|are)\s+)?|"
    r"(?:been|was|were|is|are)\s+(?:already|previously)\s+)(?:approved|cleared|reviewed|checked|verified|vetted|"
    r"accepted)\b",
    r"\balready\s+(?:cleared|signed off|okayed|vetted|blessed)\s+by\s+(?:the\s+)?(?:\w+\s+){0,2}?(?:billing|partner|"
    r"client|manager|director|reviewer|finance|lead|principal|team)\b",
    r"\bno\s+(?:further\s+)?(?:review|reviews|checks?|scrutiny|verification)\s+(?:is\s+|are\s+)?(?:required|needed|"
    r"necessary)\b",
    r"\b(?:per|according to)\s+(?:the\s+)?(?:\w+\s+)?(?:partner|client|reviewer|billing|manager|director|principal)\b"
    r".{0,40}\b(?:this|the)\s+(?:entry|entries|time|narrative|charge|line)\b.{0,30}\b(?:approved|cleared|fine|ok|"
    r"okay|pass|accepted|exempt)\b",
    r"\b(?:signed off|okayed|ok d|blessed|rubber stamped|green ?lit|green lighted)\s+(?:on\s+)?" + _ENTRY_OBJ,
    r"\b(?:this|it|entry|entries|these|narrative|time)(?:\s+s)?\s+(?:has|have|already has|already have|got|carries|"
    r"comes with)\s+(?:the\s+)?(?:\w+\s+){0,2}?(?:blessing|sign off|signoff|okay|go ahead|green light|"
    r"stamp of approval)\b",
    # leave it alone / let it through
    r"\bleave\s+" + _OBJ + r"(?:\s+(?:one|entry|entries|line|narrative))?\s+(?:alone|as is|as it is|exactly as "
    r"(?:it is|written|entered)|unchanged|untouched|as written|as entered)\b",
    r"\b(?:let|allow|wave|pass)\s+(?:this|it|these|the entry|the entries)(?:\s+one)?\s+(?:go\s+|to\s+go\s+|"
    r"to\s+pass\s+|pass\s+)?(?:through|by)\b",
    r"\b(?:this|it|the entry|the narrative|this entry|this one)(?:\s+s)?\s+(?:is\s+)?(?:fine|good|ok|okay|correct|"
    r"acceptable|final|clean|compliant)\s+as\s+(?:is|written|it stands|submitted|entered)\b",
    r"\b(?:bill|submit|post|release|include)\s+(?:this|it|these|the entry|the entries)\s+as\s+(?:is|written|entered)\b",
    r"\baccept\s+(?:this|these|it|the entry|the entries)(?:\s+\w+){0,2}?\s+(?:as is|as written|without)\b",
    r"\b(?:keep|leave|omit|exclude|drop|remove)\s+(?:this|it|these|the entry|the entries|me|my entry|my entries)\s+"
    r"(?:off|out of|from)\s+(?:the\s+)?(?:exception|exceptions|review|pre ?bill|hold|cleanup|flag)",
    r"\b(?:skip|disable|turn off|switch off|suppress)\s+(?:the\s+|all\s+|any\s+|your\s+)?(?:compliance\s+|billing\s+|"
    r"guideline\s+)?(?:checks?|reviews?|rules?|guidelines?|flags?|tripwire)\s+(?:for|on)\s+(?:this|these|it|me|my)\b",
    r"\b(?:skip|bypass)\s+" + _ENTRY_OBJ,
    # addressed to the reviewer / assistant
    r"\b(?:assistant|ai|model|reviewer|system|engine|copilot|bot|llm|chatbot|claude|gpt)\s+(?:please\s+)?(?:ignore|"
    r"mark|approve|skip|send|forward|treat|accept|clear|leave|disregard)\b",
    r"\b(?:note|notes|message|instruction|instructions|reminder)\s+(?:to|for)\s+(?:the\s+)?(?:ai|assistant|reviewer|"
    r"copilot|bot|llm|chatbot|claude|gpt|model|engine)\b",
    r"\b(?:hey|hi|hello|dear|attention|attn)\s+(?:the\s+)?(?:ai|assistant|copilot|bot|llm|chatbot|claude|gpt|"
    r"reviewer|model)\b",
    r"\b(?:ai|copilot|llm|chatbot|claude|gpt|assistant|bot|model|reviewer)\s+(?:should|must|needs to|need to|can|will|"
    r"please|is to|has to)\s+(?:treat|mark|approve|ignore|skip|accept|pass|leave|consider|forward|send|clear|let|keep)"
    r"\s+" + _OBJ,
    r"\b(?:ai|copilot|llm|chatbot|claude|gpt|assistant|bot|model|reviewer)\s+(?:should|must|needs to|need to|will|"
    r"is to)\s+not\s+(?:flag|review|check|question|reject|hold)\b",
    # waiver / suspension of the rules
    r"\b(?:waive|waived|waives|waiving|exempted|exempts|suspended|suspends|lifted)\s+(?:the\s+|all\s+|its\s+|"
    r"their\s+|our\s+|any\s+)?(?:billing\s+|review\s+|outside counsel\s+)?(?:guidelines?|rules?|reviews?|"
    r"review requirements?|billing requirements?|polic(?:y|ies)|checks?|caps?)\b",
    r"\b(?:exempt|exempted|excused)\s+from\s+(?:the\s+|all\s+|any\s+)?(?:billing\s+)?(?:guidelines?|rules?|reviews?|"
    r"checks?|scrutiny|compliance)\b",
    r"\b(?:billing\s+|review\s+)?(?:guidelines?|rules?|checks?|reviews?|requirements?)\s+(?:are|is|were|was|"
    r"have been|has been)\s+(?:waived|suspended|lifted|relaxed|not applicable|off)\s+(?:for|on)\s+"
    r"(?:this|these|me|my|our|it)\b",
    r"\b(?:guidelines?|rules?|requirements?|polic(?:y|ies)|checks?)\s+(?:do not|does not|don t|doesn t)\s+apply\s+"
    r"(?:to|for)\s+(?:this|these|me|my|our|it)\b",
    # forward / send / export the data
    r"\b(?:forward|send|e ?mail|upload|export|transmit|share|copy|cc|bcc)\s+(?:this|these|all|a copy of\s+"
    r"(?:this|these|the))\s+(?:\w+\s+){0,2}?(?:packet|entries|entry|report|list|narratives?|records?|exceptions?|"
    r"prebill|pre bill|wip|timesheets?)\b",
    r"\b(?:forward|send|e ?mail|share|cc|bcc|copy)\s+(?:the\s+)?(?:time entries|entries|packet|pre ?bill|"
    r"exception list|exceptions|cleanup list|wip|timesheets?|narratives)\s+to\b",
)
# Anchored at the start of a sentence: imperatives that a time narrative never contains.
IMPERATIVE_PATTERNS = (
    r"^(?:please\s+|kindly\s+|just\s+)?(?:approve|submit|release|finali[sz]e|post|accept|clear)\s+(?:this|these|the|"
    r"my|all|it)\b(?:\s+\w+){0,3}?\s+(?:entry|entries|pre ?bill|prebill|narratives?|timesheets?|time)\b",
    r"^(?:please\s+|kindly\s+|just\s+)?(?:approve|submit|accept|clear)\s+(?:it|this|these)(?:\s+(?:one|now|as is))?$",
    r"^(?:please\s+|kindly\s+)?(?:do not|don t|dont|never)\s+(?:flag|reject|review|check|hold|question|change|edit|"
    r"escalate)\b",
    r"^(?:please\s+|kindly\s+)?(?:forward|send|e ?mail|share|export|upload|cc)\s+(?:this|these|it|all|the|a copy)\b",
    r"^(?:please\s+|kindly\s+)?(?:ignore|disregard|bypass|override)\b",
)
INSTRUCTION_RE = re.compile("|".join(INSTRUCTION_PATTERNS))
IMPERATIVE_RE = re.compile("|".join(IMPERATIVE_PATTERNS))
SEGMENT_SPLIT_RE = re.compile(r"[.!?;:\n\u2013\u2014]+|\s-\s|,\s+")
# Any e-mail address or URL inside narrative or signal text is out of place in a time narrative.
CONTACT_RE = re.compile(
    r"[a-z0-9._%+-]+\s*(?:@|\(at\)|\[at\])\s*[a-z0-9-]+(?:\s*(?:\.|\(dot\)|\[dot\])\s*[a-z0-9-]+)+"
    r"|\b(?:https?|ftp)://\S+|\bwww\.\S+"
    r"|\b[a-z0-9-]+\.(?:com|net|org|io|co|ai|biz|info|xyz|me|app|dev)(?:/\S*)?\b",
    re.IGNORECASE,
)


def fold_text(text):
    """NFKC, strip Unicode format (Cf) characters, lower-case, fold Cyrillic/Greek look-alikes."""
    text = unicodedata.normalize("NFKC", text if isinstance(text, str) else "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    return text.lower().translate(CONFUSABLES)


def flatten_text(folded):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", folded)).strip()


def _trips(text):
    folded = fold_text(text)
    if not folded.strip():
        return False
    if CONTACT_RE.search(folded) or INSTRUCTION_RE.search(flatten_text(folded)):
        return True
    return any(IMPERATIVE_RE.search(flatten_text(seg)) for seg in SEGMENT_SPLIT_RE.split(folded))


def embedded_instruction(*texts):
    """True when any text steers the reviewer/assistant, claims an approval or waiver, asks for
    forwarding, or carries an e-mail address or URL (client-billing-guidelines.md #11.1)."""
    for text in texts:
        if isinstance(text, (list, tuple)):
            if embedded_instruction(*text):
                return True
        elif isinstance(text, str) and _trips(text):
            return True
    return False


def signal_texts(signal):
    """Every free-text field of an activity signal that can reach a draft, a table or a report."""
    if not isinstance(signal, dict):
        return []
    texts = [signal.get(k) for k in ("subject", "deliverable", "purpose", "organizer", "file_name",
                                      "activity_class", "meeting_id")]
    attendees = signal.get("attendees")
    if isinstance(attendees, list):
        texts.extend(a if isinstance(a, str) else json.dumps(a, default=str) for a in attendees)
    elif attendees is not None:
        texts.append(json.dumps(attendees, default=str))  # wrong type: scan everything it holds
    return [t for t in texts if isinstance(t, str)]


def redact(text):
    """Return WITHHELD_TEXT when text trips the wire; otherwise the text unchanged (#11.2)."""
    return WITHHELD_TEXT if embedded_instruction(text) else text
