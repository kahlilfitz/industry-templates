#!/usr/bin/env python3
"""activity_pull - deterministic raw-export -> activity packet converter (step 1 of 5).

Reads the engagement-scoped exports in a raw/ folder and writes a
ps.time-expense-narrative-compliance.v1 activity packet:

  raw/engagement-letter-extract.md   engagement identity (## Engagement key: value lines)
  raw/calendar-export.csv            calendar metadata (source key: calendar)
  raw/document-activity-log.csv      engagement-workspace document activity (document_activity)
  raw/engagement-workplan.csv        controlled workplan: activity class, deliverable, purpose
  raw/timesheet.csv                  existing time entries

Privacy (client-billing-guidelines.md #10.1): config/signal-sources.json is read FIRST. A source
that is disabled is never opened; timesheet links into a disabled or unknown source are removed
from evidence and recorded under provenance.excluded_signals with the policy citation.
Purpose is copied only from the controlled workplan; when none exists it stays null and the
signal is marked needs_review - it is never invented.
"""
import argparse
import csv
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import signal_policy  # noqa: E402  (shared copy shipped next to each engine)

ENGINE = "engine:activity_pull"
ENGINE_VERSION = "activity_pull/1.0.3"
CONTRACT = "ps.time-expense-narrative-compliance.v1"
POLICY_CITATION = signal_policy.POLICY_CITATION
MATCHED_CONFIDENCE = {"calendar": 0.96, "document_activity": 0.94}
UNMATCHED_CONFIDENCE = 0.70  # below client-billing-guidelines.md #9.1 floor -> held for review
TIMESHEET_CONFIDENCE = 0.97
NON_BILLABLE_CLASSES = ("internal_admin", "billing_hygiene")  # client-billing-guidelines.md #5.1
DOCUMENT_CLASS = {"analyze": "document_analysis", "research": "research", "draft": "deliverable_drafting"}
# Activity-ID namespaces used by connectors: lets a disabled source's links be recognised
# without opening the disabled export.
ID_NAMESPACE = (("-CAL-", "calendar"), ("-DOC-", "document_activity"), ("-MAIL-", "mailbox_metadata"))
SOURCE_FILES = (
    ("calendar", "calendar-export.csv", "connector:m365-calendar"),
    ("document_activity", "document-activity-log.csv", "connector:engagement-document-activity"),
    ("mailbox_metadata", "mailbox-summary.txt", "connector:mailbox-metadata"),
    ("mailbox_content", "mailbox-summary.txt", "connector:mailbox-content"),
)
PARSERS_AVAILABLE = ("calendar", "document_activity")


class InputError(ValueError):
    pass


def generated_at(override):
    if override:
        try:
            datetime.datetime.fromisoformat(override.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InputError(f"--generated-at is not an ISO-8601 timestamp: {override!r}") from exc
        return override
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv(path, required):
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
    except OSError as exc:
        raise InputError(f"cannot read {os.path.basename(path)}: {exc}") from exc
    if rows:
        missing = [c for c in required if c not in rows[0]]
        if missing:
            raise InputError(f"{os.path.basename(path)} is missing column(s): {', '.join(missing)}")
    return rows


def read_engagement(path):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise InputError(f"cannot read engagement-letter-extract.md: {exc}") from exc
    fields = dict(re.findall(r"^- (engagement_id|client_name|matter_name|billing_guidelines_id): (.+)$", text, re.M))
    missing = [k for k in ("engagement_id", "client_name", "matter_name") if k not in fields]
    if missing:
        raise InputError(f"engagement-letter-extract.md is missing: {', '.join(missing)}")
    return fields


def hours_between(start, end):
    fmt = "%H:%M"
    delta = datetime.datetime.strptime(end, fmt) - datetime.datetime.strptime(start, fmt)
    return round(delta.total_seconds() / 3600.0, 1)


def subject_from_file(name):
    stem = os.path.splitext(name)[0]
    return re.sub(r"[-_]+", " ", stem).strip()


def in_period(date, period):
    return (not period["start"] or date >= period["start"]) and (not period["end"] or date <= period["end"])


def main():
    ap = argparse.ArgumentParser(description="Build a cited activity packet from engagement-scoped raw exports.")
    ap.add_argument("--raw-dir", required=True, help="Folder holding the raw exports")
    ap.add_argument("--out", required=True, help="Output activity packet JSON")
    ap.add_argument("--signal-config", help="Additional signal policy JSON; it can only narrow the plugin's config/signal-sources.json, which is always applied (most restrictive wins)")
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument("--person", action="append", help="Requesting timekeeper (repeat for named colleagues)")
    who.add_argument("--all-timekeepers", action="store_true", help="Engagement-manager view: every timekeeper")
    ap.add_argument("--period-start", help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--period-end", help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--scenario", help="Demo scenario label recorded in provenance")
    ap.add_argument("--generated-at", help="Fixed ISO-8601 UTC timestamp for reproducible golden files")
    args = ap.parse_args()

    try:
        stamp = generated_at(args.generated_at)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        plugin_config_path = signal_policy.find_plugin_config(script_dir)
        if plugin_config_path:
            with open(plugin_config_path, encoding="utf-8") as fh:
                config = json.load(fh)
        else:
            config = {"sources": signal_policy.NARROW_DEFAULT,
                      "note": "plugin config/signal-sources.json not found; documented narrow default applied"}
        if not isinstance(config, dict) or not isinstance(config.get("sources"), dict):
            raise InputError("config/signal-sources.json has no 'sources' object")
        # The plugin config (or narrow default) is always applied; --signal-config may only narrow it.
        enabled, _ = signal_policy.effective_sources({}, config_path=args.signal_config, script_dir=script_dir)
        config = json.loads(json.dumps(config))
        for key, value in enabled.items():
            entry = config["sources"].get(key)
            if isinstance(entry, dict):
                entry["enabled"] = value
            else:
                config["sources"][key] = {"enabled": value}
        engagement = read_engagement(os.path.join(args.raw_dir, "engagement-letter-extract.md"))
        workplan_rows = read_csv(os.path.join(args.raw_dir, "engagement-workplan.csv"),
                                 ("workplan_id", "engagement_id", "item_type", "match_key", "activity_class", "deliverable", "purpose"))
        timesheet_rows = read_csv(os.path.join(args.raw_dir, "timesheet.csv"),
                                  ("entry_id", "date", "person", "hours", "narrative", "activity_ids", "phase_code", "task_code"))
    except (InputError, signal_policy.PolicyError, OSError, json.JSONDecodeError) as exc:
        sys.exit(f"activity_pull: {exc}")

    eng_id = engagement["engagement_id"]
    period = {"start": args.period_start, "end": args.period_end}
    people = None if args.all_timekeepers else set(args.person)
    workplan = {}
    for idx, row in enumerate(workplan_rows, start=2):
        if row["engagement_id"] == eng_id:
            workplan[(row["item_type"], row["match_key"])] = (idx, row)

    signals, skipped_sources, out_of_scope = [], [], []
    read_keys = set()
    for key, filename, source in SOURCE_FILES:
        path = os.path.join(args.raw_dir, filename)
        if not enabled.get(key):
            if os.path.exists(path) and key not in {s["policy_key"] for s in skipped_sources}:
                skipped_sources.append({"policy_key": key, "file": f"raw/{filename}", "reason": "source disabled; file not opened",
                                        "citations": [POLICY_CITATION]})
            continue
        if key not in PARSERS_AVAILABLE:
            skipped_sources.append({"policy_key": key, "file": f"raw/{filename}",
                                    "reason": "enabled but no approved parser in this version; not read", "citations": [POLICY_CITATION]})
            continue
        read_keys.add(key)
        try:
            if key == "calendar":
                rows = read_csv(path, ("activity_id", "event_id", "date", "start", "end", "person", "subject", "organizer", "attendees", "engagement_id"))
            else:
                rows = read_csv(path, ("activity_id", "date", "person", "file_name", "activity_type", "duration_hours", "engagement_id"))
        except InputError as exc:
            sys.exit(f"activity_pull: {exc}")
        for idx, row in enumerate(rows, start=2):
            cite = f"raw/{filename} row {idx}"
            if row["engagement_id"] != eng_id:
                out_of_scope.append({"activity_id": row["activity_id"], "reason": "outside engagement scope", "citations": [cite]})
                continue
            if people is not None and row["person"] not in people:
                continue
            if not in_period(row["date"], period):
                continue
            if key == "calendar":
                match = workplan.get(("calendar_event", row["event_id"]))
                activity_class = (match[1]["activity_class"] if match else "") or "unclassified_meeting"
                subject = row["subject"].strip()
                duration = hours_between(row["start"], row["end"])
                meeting_id = row["event_id"]
                extra = {"organizer": row["organizer"].strip() or None,
                         "attendees": [a.strip() for a in row["attendees"].split(";") if a.strip()]}
            else:
                match = workplan.get(("document", row["file_name"]))
                activity_class = DOCUMENT_CLASS.get(row["activity_type"].strip().lower(), "unclassified_document_activity")
                subject = subject_from_file(row["file_name"])
                try:
                    duration = round(float(row["duration_hours"]), 2)
                except ValueError:
                    sys.exit(f"activity_pull: {cite} has a non-numeric duration_hours")
                meeting_id = None
                extra = {"file_name": row["file_name"]}
            citations = [cite]
            purpose, deliverable = None, None
            if match:
                citations.append(f"raw/engagement-workplan.csv row {match[0]}")
                purpose = match[1]["purpose"].strip() or None
                deliverable = match[1]["deliverable"].strip() or None
            billable = activity_class not in NON_BILLABLE_CLASSES
            citations.append(POLICY_CITATION)
            if not billable:
                citations.append("client-billing-guidelines.md #5.1")
            signal = {
                "activity_id": row["activity_id"],
                "person": row["person"],
                "date": row["date"],
                "activity_class": activity_class,
                "duration_hours": duration,
                "subject": subject,
                "purpose": purpose,
                "deliverable": deliverable,
                "meeting_id": meeting_id,
                "billable_signal": billable,
            }
            signal.update(extra)
            signal.update({
                "source": source,
                "confidence": MATCHED_CONFIDENCE[key] if (match and purpose) else UNMATCHED_CONFIDENCE,
                "citations": citations,
            })
            if not purpose:
                signal["needs_review"] = True
                signal["review_reason"] = "no controlled source states a purpose; purpose left null (never invented)"
            signals.append(signal)

    kept_ids = {s["activity_id"] for s in signals}
    entries, excluded = [], []
    for idx, row in enumerate(timesheet_rows, start=2):
        if people is not None and row["person"] not in people:
            continue
        if not in_period(row["date"], period):
            continue
        cite = f"raw/timesheet.csv row {idx}"
        try:
            hours = float(row["hours"])
        except ValueError:
            sys.exit(f"activity_pull: {cite} has a non-numeric hours value")
        links = [a.strip() for a in (row["activity_ids"] or "").split(";") if a.strip()]
        kept_links, dropped = [], []
        for activity_id in links:
            if activity_id in kept_ids:
                kept_links.append(activity_id)
                continue
            dropped.append(activity_id)
            hint = next((k for ns, k in ID_NAMESPACE if ns in activity_id), None)
            if hint and not enabled.get(hint):
                reason = (f"linked from {row['entry_id']} ({cite}); the ID belongs to the '{hint}' source, which is disabled "
                          "in config/signal-sources.json, so that source was not read and the link is not evidence")
            else:
                reason = f"linked from {row['entry_id']} ({cite}) but not found in any enabled, engagement-scoped export"
            if activity_id not in {e["activity_id"] for e in excluded}:
                excluded.append({"activity_id": activity_id, "source": None, "policy_key": hint, "reason": reason,
                                 "excluded_by": ENGINE, "citations": [cite, POLICY_CITATION]})
        entry = {
            "entry_id": row["entry_id"],
            "person": row["person"],
            "date": row["date"],
            "duration_hours": hours,
            "narrative": row["narrative"],
            "activity_ids": kept_links,
            "submitted_phase_code": row["phase_code"] or None,
            "submitted_task_code": row["task_code"] or None,
            "source": "connector:timesheet",
            "confidence": TIMESHEET_CONFIDENCE,
            "citations": [cite],
        }
        if dropped:
            entry["excluded_activity_ids"] = dropped
        entries.append(entry)

    packet = {
        "contract_version": CONTRACT,
        "engagement": {
            "engagement_id": eng_id,
            "client_name": engagement["client_name"],
            "matter_name": engagement["matter_name"],
            "billing_guidelines_id": engagement.get("billing_guidelines_id"),
            "source": "connector:engagement-workspace",
            "confidence": 0.99,
            "citations": ["raw/engagement-letter-extract.md #engagement"],
        },
        "period": period,
        "signal_config": config,
        "guidelines": {
            "guidelines_id": engagement.get("billing_guidelines_id"),
            "summary": "Synthetic outside-counsel-style billing guideline excerpt for demos.",
            "source": "connector:sharepoint-guidelines",
            "confidence": 0.98,
            "citations": ["client-billing-guidelines.md #1.1", "client-billing-guidelines.md #2.1",
                          "client-billing-guidelines.md #3.1", "client-billing-guidelines.md #8.1"],
        },
        "code_structure": {
            "code_set_id": "SYNTH-PS-CODES-2026",
            "source": "connector:billing-code-repository",
            "confidence": 0.98,
            "citations": ["task-phase-codes.md #1.1", "task-phase-codes.md #2.1", "task-phase-codes.md #3.1", "task-phase-codes.md #4.1"],
        },
        "activity_signals": signals,
        "time_entries": entries,
        "provenance": {
            "demo_scenario": args.scenario,
            "generated_at": stamp,
            "engines": [ENGINE_VERSION],
            "sources_read": sorted(read_keys),
            "skipped_sources": skipped_sources,
            "out_of_scope_rows": out_of_scope,
            "excluded_signals": excluded,
            "timekeeper_scope": {"mode": "all_timekeepers" if people is None else "named",
                                 "people": None if people is None else sorted(people)},
        },
    }
    if not args.scenario:
        packet["provenance"].pop("demo_scenario")
    signal_policy.filter_packet(packet, config_path=args.signal_config, script_dir=script_dir, engine=ENGINE)
    try:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(packet, fh, indent=2)
            fh.write("\n")
    except OSError as exc:
        sys.exit(f"activity_pull: cannot write output: {exc}")
    print(f"activity_pull: {len(signals)} signal(s), {len(entries)} time entr(ies), "
          f"{len(packet['provenance']['excluded_signals'])} excluded link(s) -> {os.path.basename(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
