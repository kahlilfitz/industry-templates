#!/usr/bin/env python3
"""signal_policy - shared signal-source privacy filter (client-billing-guidelines.md #10.1).

Every engine in this plugin calls filter_packet() before it uses activity evidence, so a
signal from a disabled or unknown source can never reach a narrative, a code mapping or a
compliance verdict - even when a hand-built packet contains one.

Policy resolution is most-restrictive-wins: a source is usable only when it is enabled in
EVERY policy that is available. When the plugin-level policy is unavailable (for example,
when a skill runs stand-alone), the documented narrow default is the mandatory floor and a
packet policy may narrow it but can never enable mailbox access.

This file ships as identical copies next to each engine (skills are self-contained);
tests/check_shared_copies.py fails when the copies drift.
"""
import json
import os

POLICY_CITATION = "client-billing-guidelines.md #10.1"
SIGNAL_POLICY_VERSION = "signal_policy/1.0.3"

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
