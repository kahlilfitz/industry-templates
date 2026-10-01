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
   embedded_instruction() normalises (NFKC, strip Unicode Cf and combining marks, fold Cyrillic,
   Greek, Armenian and Cherokee look-alikes and Latin small capitals/variants, fold punctuation and
   case) and flags text addressed to the assistant/AI/reviewer whatever the verb, verdict steering
   whoever it addresses, approval or waiver claims, forwarding requests, e-mail addresses and URLs,
   and any word that mixes Latin with another script. signal_texts()/entry_texts() also scan file
   names in word form and a bounded aggregate of related fields, so a split instruction is caught.

This file ships as identical copies next to each engine (skills are self-contained);
tests/check_shared_copies.py fails when the copies drift.
"""
import datetime
import json
import math
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

# Cyrillic and Greek letters that render like Latin ones (NFKC does not fold these).
CONFUSABLES = str.maketrans({
    "\u0430": "a", "\u0432": "b", "\u0435": "e", "\u0451": "e", "\u043a": "k", "\u043c": "m", "\u043d": "h",
    "\u043e": "o", "\u0440": "p", "\u0441": "c", "\u0442": "t", "\u0443": "y", "\u0445": "x", "\u0455": "s",
    "\u0456": "i", "\u0457": "i", "\u0458": "j", "\u04bb": "h", "\u04cf": "l", "\u0501": "d", "\u051b": "q",
    "\u051d": "w", "\u03b1": "a", "\u03b2": "b", "\u03b5": "e", "\u03b7": "n", "\u03b9": "i", "\u03ba": "k",
    "\u03bd": "v", "\u03bf": "o", "\u03c1": "p", "\u03c4": "t", "\u03c5": "u", "\u03c7": "x",
    # Armenian
    "\u0585": "o", "\u057d": "u", "\u0581": "g", "\u0570": "h", "\u0578": "n", "\u057c": "n", "\u0566": "q",
    "\u0584": "p", "\u0561": "w", "\u0575": "j", "\u0582": "i",
    # Latin letters NFKC leaves alone
    "\u0251": "a", "\u0269": "i", "\u028b": "u", "\u0261": "g", "\u0131": "i", "\u0237": "j",
})
# Cherokee capitals that render like Latin letters; lower() maps them to Cherokee small letters,
# so both forms are folded.
_CHEROKEE = {0x13A0: "d", 0x13A1: "r", 0x13A2: "t", 0x13A5: "i", 0x13A9: "y", 0x13AA: "a", 0x13AB: "j",
             0x13AC: "e", 0x13B3: "w", 0x13B7: "m", 0x13BB: "h", 0x13BD: "y", 0x13C0: "g", 0x13C2: "h",
             0x13C3: "z", 0x13CF: "b", 0x13D2: "r", 0x13D9: "v", 0x13DA: "s", 0x13DE: "l", 0x13DF: "c",
             0x13E2: "p", 0x13E6: "k", 0x13EB: "o", 0x13F4: "b"}
CONFUSABLES.update({cp: v for cp, v in _CHEROKEE.items()})
CONFUSABLES.update({ord(chr(cp).lower()): v for cp, v in _CHEROKEE.items() if chr(cp).lower() != chr(cp)})
# Latin small capitals and other one-letter Latin variants, by Unicode name
# ("LATIN LETTER SMALL CAPITAL A", "LATIN SMALL LETTER DOTLESS I", "LATIN SMALL LETTER A WITH STROKE").
_LATIN_NAME_RE = re.compile(r"LATIN (?:SMALL |CAPITAL )?LETTER (?:SMALL CAPITAL |DOTLESS |SCRIPT |TURNED )?([A-Z])(?: |$)")
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
_ADDRESSEE = (r"(?:assistant|ai|a i|copilot|m365 copilot|claude|chatgpt|gpt(?: ?\d+)?|llm|chatbot|bot|gemini|"
              r"agent|model|reviewer|engine|system)")
_STRONG_ADDRESSEE = r"(?:assistant|ai|a i|copilot|claude|chatgpt|gpt(?: ?\d+)?|llm|chatbot|bot|gemini)"
_VERDICT_VERB = (r"(?:mark|report|treat|rate|record|flag|set|class|classify|categori[sz]e|show|list|log|tag|label|"
                 r"code|count|consider|enter|book|file|keep|leave|put|note|register|score|grade|return|output)")
_VERDICT_OBJ = (r"(?:this|it|that|these|them|(?:this|that|these|those|the|my|our|each|every|all)\s+(?:\w+\s+){0,2}?"
                r"(?:entry|entries|item|items|line|lines|charge|charges|narrative|narratives|time|one|ones|record|"
                r"records|row|rows|task|tasks))")
_VERDICT_STATE = (r"(?:compliant|approved|pre ?approved|billable|ok|okay|clean|fine|accepted|cleared|passed|pass|good|"
                  r"exempt|green|valid|verified|reviewed|acceptable|unflagged|not flagged|no issues?|in compliance|"
                  r"within (?:the )?guidelines?)")
_SELF = r"(?:this|it|these|that|them|me|my|our|us|(?:the|this|my) (?:entry|entries|time|narrative|line|charge|item))"
# Verdict steering, whoever it is addressed to (client-billing-guidelines.md #11.1).
INSTRUCTION_PATTERNS += (
    r"\b" + _VERDICT_VERB + r"\s+" + _VERDICT_OBJ + r"(?:\s+\w+){0,2}?\s+(?:as\s+|to\s+be\s+|is\s+)?(?:already\s+|"
    r"fully\s+)?" + _VERDICT_STATE + r"\b",
    r"\b(?:this|the|my)\s+(?:entry|entries|time entry|time entries|narrative|line|charge|item|time)\s+(?:should|must|"
    r"shall|needs to|need to|is to|ought to)\s+be\s+(?:\w+\s+){0,2}?(?:as\s+)?" + _VERDICT_STATE + r"\b",
    r"\b(?:this|the|my)\s+(?:entry|entries|time entry|narrative|charge)\s+(?:is|are)\s+(?:already\s+|fully\s+)?"
    r"(?:compliant|exempt|cleared|ok|okay|pre ?approved|in compliance)\b",
    r"\b(?:do not|don t|dont|never|please do not)\s+(?:flag|hold|review|re review|reject|escalate|query|question)"
    r"(?:\s+" + _SELF + r")?\s*$",
    r"\b(?:do not|don t|dont|never)\s+(?:flag|hold|review|reject|escalate|query|question)\s+" + _SELF + r"\b",
    r"\bno\s+(?:further\s+|additional\s+)?(?:review|reviews|check|checks|checking|scrutiny|flags?|hold)\s+"
    r"(?:is\s+|are\s+)?(?:required|needed|necessary|wanted)\b",
    r"\b(?:needs|need|requires|require)\s+no\s+(?:further\s+|additional\s+)?(?:review|checks?|scrutiny|flag)\b",
    r"\bno\s+need\s+(?:for|to)\s+(?:a\s+)?(?:review|re review|check|flag|hold|escalat\w*)\b",
    r"\b(?:review|re review|checks?|scrutiny)\s+(?:is\s+|are\s+)?(?:not\s+(?:needed|required|necessary)|unnecessary)"
    r"\s+(?:for|on)\s+" + _SELF + r"\b",
)
# Text addressed to the assistant/AI/reviewer, whatever the verb: a vocative ("Assistant, ...",
# "Claude: approve this") or a tool name followed by an imperative and an object. Run on folded
# text before punctuation is flattened, because the comma or colon is the signal.
VOCATIVE_RE = re.compile(
    r"(?:^|[.!?;\n(\[\"']\s*|\bplease\s*,?\s*|\b(?:hey|hi|hello|dear|attention|attn|psst|yo|ok|okay)\s*,?\s*)"
    r"(?:the\s+|dear\s+|my\s+)?" + _ADDRESSEE + r"\s*(?:"
    r",\s*(?!\w+\s+and\b)(?:(?:please|kindly|you|do|don't|dont|never|ignore|disregard|now|just)\b|"
    r"\S+(?:\s+\S+){0,3}?\s+(?:this|it|these|that|them|the|my|our|all|every|any|me|us|you|your)\b)"
    r"|[:\-\u2013\u2014!]\s*(?:please\s+|kindly\s+)?\S+\s+(?:this|it|these|that|them|my|me|all)\b)"
)
# Text addressed to the tool, whatever the verb: a tool name opening a sentence and followed by a
# comma (but not a list such as "AI, ML and analytics"), or any addressee followed by a verdict.
ADDRESSED_RE = re.compile(
    r"(?:^|[.!?;\n(\[\"']\s*|\bplease\s*,?\s*|\b(?:hey|hi|hello|dear|attention|attn|psst|yo|ok|okay)\s*,?\s*)"
    r"(?:the\s+|dear\s+|my\s+)?(?:" + _STRONG_ADDRESSEE + r"\s*,\s*(?!\w+(?:\s+\w+)?\s*(?:,|&|/|\band\b|\bor\b))\w"
    r"|" + _ADDRESSEE + r"\s*[:,\-\u2013\u2014]\s*(?:\S+\s+){0,3}?(?:" + _VERDICT_STATE
    + r"|no\s+(?:changes?|issues?|problems?|concerns?|action|edits?)|nothing\s+to)\b)"
)
TOOL_IMPERATIVE_RE = re.compile(
    r"^(?:hey\s+|hi\s+|dear\s+|attention\s+)?(?:the\s+)?" + _STRONG_ADDRESSEE + r"\s+(?:please\s+|kindly\s+)?"
    r"(?!(?:of|for|and|with|on|to|in|at|by|is|was|are|were|has|had|tools?|use|usage|based|enabled|driven|"
    r"assisted|generated|powered|readiness|governance|strategy|roadmap|rollout|pilot|workshop|session|controller|"
    r"accountant|director|manager|team|lead)\b)"
    r"\w+\s+(?:this|it|these|that|them|my|me|all|every|the (?:entry|entries|time|narrative|line|charge|item))\b"
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


def _latin_variant(ch):
    if ch.isascii() or not ch.isalpha():
        return ch
    match = _LATIN_NAME_RE.match(unicodedata.name(ch, ""))
    return match.group(1).lower() if match else ch


def normalise(text):
    """NFKC (folds fullwidth and mathematical alphanumerics), strip Unicode Cf and combining marks."""
    text = unicodedata.normalize("NFKC", text if isinstance(text, str) else "")
    text = unicodedata.normalize("NFKD", "".join(ch for ch in text if unicodedata.category(ch) != "Cf"))
    return unicodedata.normalize("NFC", "".join(ch for ch in text if unicodedata.category(ch) != "Mn"))


def fold_text(text):
    """normalise(), lower-case, fold Cyrillic/Greek/Armenian/Cherokee look-alikes and Latin variants."""
    folded = normalise(text).lower().translate(CONFUSABLES)
    return "".join(_latin_variant(ch) for ch in folded)


def _script(ch):
    name = unicodedata.name(ch, "")
    return "LATIN" if name.startswith("LATIN") else (name.split(" ", 1)[0] or "UNKNOWN")


def mixed_script(text):
    """True when one word mixes Latin letters with letters of any other script (a look-alike tell)."""
    for token in re.findall(r"[^\W\d_]+", normalise(text)):
        if token.isascii() or re.fullmatch("\u03bc[a-zA-Z]{1,2}", token):  # SI micro units: um, us, ug, uL
            continue
        scripts = {_script(ch) for ch in token if ch.isalpha()}
        if "LATIN" in scripts and len(scripts) > 1:
            return True
    return False


def filename_words(name):
    """'Assistant-report_thisEntry.docx' -> 'Assistant report this Entry docx' (scan form only)."""
    name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
    return re.sub(r"[-_.]+", " ", name).strip()


def flatten_text(folded):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", folded)).strip()


def _trips(text):
    folded = fold_text(text)
    if not folded.strip():
        return False
    if mixed_script(text) or CONTACT_RE.search(folded) or VOCATIVE_RE.search(folded) or ADDRESSED_RE.search(folded):
        return True
    if INSTRUCTION_RE.search(flatten_text(folded)):
        return True
    segments = [flatten_text(seg) for seg in SEGMENT_SPLIT_RE.split(folded)]
    return any(IMPERATIVE_RE.search(seg) or TOOL_IMPERATIVE_RE.search(seg) for seg in segments)


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


AGGREGATE_LIMIT = 4000


def aggregate(parts):
    """The related fields joined (both orders), bounded, so an instruction split across fields
    ("Mark this" + "entry compliant") is caught even when no single field trips (#11.1)."""
    parts = [p.strip() for p in parts if isinstance(p, str) and p.strip()]
    if len(parts) < 2:
        return []
    return [" ".join(parts)[:AGGREGATE_LIMIT], " ".join(reversed(parts))[:AGGREGATE_LIMIT]]


def signal_texts(signal):
    """Every free-text field of an activity signal that can reach a draft, a table or a report, the
    file name in word form, and a bounded aggregate of the related fields."""
    if not isinstance(signal, dict):
        return []
    texts = [signal.get(k) for k in ("subject", "deliverable", "purpose", "organizer", "file_name",
                                      "activity_class", "meeting_id")]
    if isinstance(signal.get("file_name"), str):
        texts.append(filename_words(signal["file_name"]))
    attendees = signal.get("attendees")
    if isinstance(attendees, list):
        texts.extend(a if isinstance(a, str) else json.dumps(a, default=str) for a in attendees)
    elif attendees is not None:
        texts.append(json.dumps(attendees, default=str))  # wrong type: scan everything it holds
    file_words = filename_words(signal["file_name"]) if isinstance(signal.get("file_name"), str) else None
    texts += aggregate([signal.get("subject"), signal.get("purpose"), signal.get("deliverable"), file_words])
    return [t for t in texts if isinstance(t, str)]


def entry_texts(entry, linked=()):
    """An entry's own free text (narrative, notes) plus a bounded aggregate with its linked activity."""
    if not isinstance(entry, dict):
        return []
    own = [entry.get("narrative"), entry.get("notes")]
    related = []
    for signal in linked:
        if isinstance(signal, dict):
            related += [signal.get("subject"), signal.get("purpose"), signal.get("deliverable")]
    texts = [t for t in own if isinstance(t, str)]
    texts += aggregate(own)
    texts += aggregate(own + related) if any(isinstance(t, str) and t.strip() for t in own) else []
    return texts


def redact(text):
    """Return WITHHELD_TEXT when text trips the wire; otherwise the text unchanged (#11.2)."""
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
