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

Data minimisation (client-billing-guidelines.md #12.1): only the requesting timekeeper's rows
are returned. Colleagues' rows (--person <other> or --all-timekeepers) are released only in the
engagement-manager team view: the --requester must be the engagement_manager recorded in
raw/engagement-letter-extract.md AND --team-view-confirmation must be exactly
"engagement-manager:<engagement_id>". Otherwise colleague rows are withheld (fail closed); a
malformed confirmation is an input error. The role is never inferred from free text.

Free text is data (#11.1): a signal or entry whose text trips the shared embedded-instruction
tripwire is marked embedded_instruction / needs_review so no later step drafts from it.
A requested period with no rows for the requester produces a period_check warning.
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
ENGINE_VERSION = "activity_pull/1.0.4"
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
    except (OSError, UnicodeError, csv.Error) as exc:
        raise InputError(f"cannot read {os.path.basename(path)}: {exc}") from exc
    if rows:
        missing = [c for c in required if c not in rows[0]]
        if missing:
            raise InputError(f"{os.path.basename(path)} is missing column(s): {', '.join(missing)}")
    for idx, row in enumerate(rows, start=2):
        # csv.DictReader stores surplus cells under None and fills short rows with None: never guess.
        if None in row or any(row.get(c) is None for c in required):
            raise InputError(f"{os.path.basename(path)} row {idx} does not have one cell per header column")
    return rows


DECIMAL_RE = re.compile(r"\d+(?:\.\d+)?")
TIME_RE = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")


def cli_date(value, flag):
    if value is None:
        return None
    try:
        signal_policy.check_date(value, flag)
    except signal_policy.SchemaError as exc:
        raise InputError(str(exc)) from exc
    return value


def cell_date(row, key, cite):
    value = row[key].strip()
    try:
        signal_policy.check_date(value, f"{cite} {key}")
    except signal_policy.SchemaError as exc:
        raise InputError(str(exc)) from exc
    return value


def cell_hours(row, key, cite):
    """A plain non-negative decimal; 'nan', 'inf', '1e3', '-1' and '' are rejected, never coerced."""
    value = row[key].strip()
    if not DECIMAL_RE.fullmatch(value):
        raise InputError(f"{cite} {key} must be a non-negative decimal number of hours")
    return float(value)


def cell_id(row, key, cite):
    value = row[key].strip()
    if not value:
        raise InputError(f"{cite} {key} must not be empty")
    return value


def read_engagement(path):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeError) as exc:
        raise InputError(f"cannot read engagement-letter-extract.md: {exc}") from exc
    fields = dict(re.findall(r"^- (engagement_id|client_name|matter_name|billing_guidelines_id|engagement_manager): (.+)$",
                             text, re.M))
    fields = {k: v.strip() for k, v in fields.items()}
    missing = [k for k in ("engagement_id", "client_name", "matter_name") if k not in fields]
    if missing:
        raise InputError(f"engagement-letter-extract.md is missing: {', '.join(missing)}")
    return fields


def hours_between(start, end, cite="calendar row"):
    start, end = start.strip(), end.strip()
    if not (TIME_RE.fullmatch(start) and TIME_RE.fullmatch(end)):
        raise InputError(f"{cite} start and end must be HH:MM (24-hour)")
    fmt = "%H:%M"
    delta = datetime.datetime.strptime(end, fmt) - datetime.datetime.strptime(start, fmt)
    if delta.total_seconds() < 0:
        raise InputError(f"{cite} ends before it starts")
    return round(delta.total_seconds() / 3600.0, 1)


def subject_from_file(name):
    stem = os.path.splitext(name)[0]
    return re.sub(r"[-_]+", " ", stem).strip()


def in_period(date, period):
    return (not period["start"] or date >= period["start"]) and (not period["end"] or date <= period["end"])


def resolve_scope(args, engagement):
    """Return (allowed person keys or None for everyone, timekeeper_scope record). Fails closed."""
    requester = " ".join((args.requester or "").split())
    if not requester:
        raise InputError("--requester must name the requesting timekeeper")
    eng_id = engagement["engagement_id"]
    requested = [" ".join(p.split()) for p in (args.person or []) if p and p.strip()]
    others = sorted({p for p in requested if not signal_policy.same_person(p, requester)})
    wants_team = bool(args.all_timekeepers or others)
    token = None
    if args.team_view_confirmation is not None:
        token = args.team_view_confirmation  # compared exactly: no trimming, no case folding
        if not signal_policy.TEAM_VIEW_TOKEN_RE.fullmatch(token):
            raise InputError("--team-view-confirmation must be exactly 'engagement-manager:<engagement_id>' "
                             "(no spaces or other characters)")
        if token != signal_policy.team_view_token(eng_id):
            raise InputError(f"--team-view-confirmation is for another engagement; expected "
                             f"'{signal_policy.team_view_token(eng_id)}'")
    scope = {"mode": "self", "requester": requester, "people": [requester], "team_view": None, "withheld": None,
             "citations": [signal_policy.SCOPE_CITATION]}
    if not wants_team:
        return {signal_policy.person_key(requester)}, scope
    manager = engagement.get("engagement_manager")
    if token and manager and signal_policy.same_person(requester, manager):
        people = None if args.all_timekeepers else sorted({requester, *others})
        scope.update({"mode": "team", "people": people, "team_view": {
            "confirmed": True,
            "role": "engagement_manager",
            "confirmation": token,
            "verified_against": "raw/engagement-letter-extract.md #engagement (engagement_manager)",
            "citations": [signal_policy.SCOPE_CITATION],
        }})
        return (None if people is None else {signal_policy.person_key(p) for p in people}), scope
    if not token:
        reason = "no engagement-manager team-view confirmation was supplied"
    elif not manager:
        reason = "raw/engagement-letter-extract.md records no engagement_manager, so no team view can be granted"
    else:
        reason = "the requester is not the engagement manager recorded in raw/engagement-letter-extract.md"
    scope["withheld"] = {
        "requested": "all timekeepers" if args.all_timekeepers else others,
        "reason": f"colleagues' rows withheld: {reason}; only the requester's rows are returned",
        "citations": [signal_policy.SCOPE_CITATION],
    }
    return {signal_policy.person_key(requester)}, scope


def period_check(period, dates_available, dates_in_period):
    if not (period["start"] or period["end"]):
        return {"status": "no_period_requested", "warning": None}
    available = [min(dates_available), max(dates_available)] if dates_available else None
    in_period = [min(dates_in_period), max(dates_in_period)] if dates_in_period else None
    check = {"requested": dict(period), "data_dates_in_period": in_period, "data_dates_available": available}
    if in_period:
        check.update({"status": "data_found", "warning": None})
    else:
        where = (f"activity and time entries in scope are dated {available[0]} to {available[1]}" if available
                 else "no activity or time entries in scope were found for any date")
        check.update({"status": "no_data_in_period", "warning": (
            f"No activity or time entries were found for {period['start'] or 'the start'} to "
            f"{period['end'] or 'the end'}; {where}. An empty packet is not evidence that no work was done - "
            "confirm the period or re-run for the dates that hold data.")})
    return check


def main():
    ap = argparse.ArgumentParser(description="Build a cited activity packet from engagement-scoped raw exports.")
    ap.add_argument("--raw-dir", required=True, help="Folder holding the raw exports")
    ap.add_argument("--out", required=True, help="Output activity packet JSON")
    ap.add_argument("--signal-config", help="Additional signal policy JSON; it can only narrow the plugin's config/signal-sources.json, which is always applied (most restrictive wins)")
    ap.add_argument("--requester", required=True, help="The requesting timekeeper; only their rows are returned by default")
    who = ap.add_mutually_exclusive_group()
    who.add_argument("--person", action="append", help="Named colleague for the engagement-manager team view (repeatable)")
    who.add_argument("--all-timekeepers", action="store_true", help="Engagement-manager team view: every timekeeper")
    ap.add_argument("--team-view-confirmation", help="Exactly 'engagement-manager:<engagement_id>', supplied only after the "
                    "user explicitly confirms the engagement-manager team view; the requester must be the engagement "
                    "manager recorded in the engagement letter")
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
        people, timekeeper_scope = resolve_scope(args, engagement)
        cli_date(args.period_start, "--period-start")
        cli_date(args.period_end, "--period-end")
        if args.period_start and args.period_end and args.period_start > args.period_end:
            raise InputError("--period-start is after --period-end")
    except (InputError, signal_policy.PolicyError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        sys.exit(f"activity_pull: {exc}")

    eng_id = engagement["engagement_id"]
    period = {"start": args.period_start, "end": args.period_end}
    dates_available, dates_in_period = set(), set()

    def allowed(person):
        return people is None or signal_policy.person_key(person) in people
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
            if not allowed(row["person"]):
                continue  # #12.1: other timekeepers' rows are never read into the packet
            try:
                cell_id(row, "activity_id", cite)
                cell_id(row, "person", cite)
                row["date"] = cell_date(row, "date", cite)
            except InputError as exc:
                sys.exit(f"activity_pull: {exc}")
            if row["engagement_id"] != eng_id:
                out_of_scope.append({"activity_id": row["activity_id"], "reason": "outside engagement scope", "citations": [cite]})
                continue
            dates_available.add(row["date"])
            if not in_period(row["date"], period):
                continue
            dates_in_period.add(row["date"])
            if key == "calendar":
                match = workplan.get(("calendar_event", row["event_id"]))
                activity_class = (match[1]["activity_class"] if match else "") or "unclassified_meeting"
                subject = row["subject"].strip()
                try:
                    duration = hours_between(row["start"], row["end"], cite)
                except InputError as exc:
                    sys.exit(f"activity_pull: {exc}")
                meeting_id = row["event_id"]
                extra = {"organizer": row["organizer"].strip() or None,
                         "attendees": [a.strip() for a in row["attendees"].split(";") if a.strip()]}
            else:
                match = workplan.get(("document", row["file_name"]))
                activity_class = DOCUMENT_CLASS.get(row["activity_type"].strip().lower(), "unclassified_document_activity")
                subject = subject_from_file(row["file_name"])
                try:
                    duration = round(cell_hours(row, "duration_hours", cite), 2)
                except InputError as exc:
                    sys.exit(f"activity_pull: {exc}")
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
            reasons = []
            if not purpose:
                reasons.append("no controlled source states a purpose; purpose left null (never invented)")
            if signal_policy.embedded_instruction(signal_policy.signal_texts(signal)):
                signal["embedded_instruction"] = True
                signal["citations"].append(signal_policy.INJECTION_CITATION)
                reasons.append("text flagged as embedded_instruction; treated as data, never "
                               "drafted from or displayed (client-billing-guidelines.md #11.2)")
            if reasons:
                signal["needs_review"] = True
                signal["review_reason"] = "; ".join(reasons)
            signals.append(signal)

    kept_ids = {s["activity_id"] for s in signals}
    entries, excluded = [], []
    for idx, row in enumerate(timesheet_rows, start=2):
        if not allowed(row["person"]):
            continue
        cite = f"raw/timesheet.csv row {idx}"
        try:
            cell_id(row, "entry_id", cite)
            cell_id(row, "person", cite)
            row["date"] = cell_date(row, "date", cite)
            hours = cell_hours(row, "hours", cite)
        except InputError as exc:
            sys.exit(f"activity_pull: {exc}")
        dates_available.add(row["date"])
        if not in_period(row["date"], period):
            continue
        dates_in_period.add(row["date"])
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
        linked_signals = [s for s in signals if s["activity_id"] in kept_links]
        if signal_policy.embedded_instruction(signal_policy.entry_texts({"narrative": row["narrative"]}, linked_signals)):
            entry["embedded_instruction"] = True
        entries.append(entry)

    packet = {
        "contract_version": CONTRACT,
        "engagement": {
            "engagement_id": eng_id,
            "client_name": engagement["client_name"],
            "matter_name": engagement["matter_name"],
            "billing_guidelines_id": engagement.get("billing_guidelines_id"),
            "engagement_manager": engagement.get("engagement_manager"),
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
            "timekeeper_scope": timekeeper_scope,
            "period_check": period_check(period, dates_available, dates_in_period),
        },
    }
    if not args.scenario:
        packet["provenance"].pop("demo_scenario")
    signal_policy.filter_packet(packet, config_path=args.signal_config, script_dir=script_dir, engine=ENGINE)
    try:
        signal_policy.validate_packet(packet, "activity")  # never emit a packet the next engine would reject
    except signal_policy.SchemaError as exc:
        sys.exit(f"activity_pull: {exc}")
    try:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(packet, fh, indent=2)
            fh.write("\n")
    except OSError as exc:
        sys.exit(f"activity_pull: cannot write output: {exc}")
    print(f"activity_pull: {len(signals)} signal(s), {len(entries)} time entr(ies), "
          f"{len(packet['provenance']['excluded_signals'])} excluded link(s) -> {os.path.basename(args.out)}")
    if timekeeper_scope["withheld"]:
        print(f"activity_pull: WARNING {timekeeper_scope['withheld']['reason']} ({signal_policy.SCOPE_CITATION})")
    if packet["provenance"]["period_check"].get("warning"):
        print(f"activity_pull: WARNING {packet['provenance']['period_check']['warning']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
