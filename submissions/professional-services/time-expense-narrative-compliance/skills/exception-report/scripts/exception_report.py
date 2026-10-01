#!/usr/bin/env python3
"""exception_report - deterministic DRAFT pre-bill exception packet (step 5 of 5).

Reads governed.json from guideline_check and writes a Markdown review packet for the
engagement manager and billing coordinator. It only writes a local draft file: it has no
e-mail, chat or network code and never sends, submits, approves or alters WIP balances.
Engine flags are quoted verbatim; nothing is dropped or softened.
"""
import argparse
import datetime
import json
import os
import sys
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import signal_policy  # noqa: E402  (shared copy shipped next to each engine)

ENGINE = "engine:exception_report"
ENGINE_VERSION = "exception_report/1.0.2"
CONTRACT = "ps.time-expense-narrative-compliance.v1"


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


def load_governed(path):
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"cannot read {os.path.basename(path)}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("contract_version") != CONTRACT:
        raise InputError(f"expected a {CONTRACT} object")
    for key in ("time_entries", "exception_list", "missing_time_report", "prebill_summary"):
        if key not in payload:
            raise InputError(f"'{key}' missing - run guideline_check.py first")
    return payload


def cell(text):
    return str(text if text is not None else "").replace("|", "\\|").replace("\n", " ")


def flag_lines(flags):
    return "<br>".join(f"`{f['flag']}` ({f['severity']}): {cell(f['detail'])} [{', '.join(f.get('citations', []))}]"
                       for f in flags)


def main():
    ap = argparse.ArgumentParser(description="Write a DRAFT pre-bill exception packet (Markdown). Sends nothing.")
    ap.add_argument("--governed", required=True, help="governed.json from guideline_check")
    ap.add_argument("--out", required=True, help="Output Markdown draft")
    ap.add_argument("--requested-start", help="Period the user asked about (YYYY-MM-DD)")
    ap.add_argument("--requested-end", help="Period the user asked about (YYYY-MM-DD)")
    ap.add_argument("--signal-config", help="Signal policy JSON (default: the plugin's config/signal-sources.json)")
    ap.add_argument("--generated-at", help="Fixed ISO-8601 UTC timestamp for reproducible golden files")
    args = ap.parse_args()

    try:
        stamp = generated_at(args.generated_at)
        data = deepcopy(load_governed(args.governed))
        signal_policy.filter_packet(data, config_path=args.signal_config,
                                    script_dir=os.path.dirname(os.path.abspath(__file__)), engine=ENGINE)
    except (InputError, signal_policy.PolicyError) as exc:
        sys.exit(f"exception_report: {exc}")

    eng = data.get("engagement", {})
    period = data.get("period") or {}
    summary = data["prebill_summary"]
    by_verdict = {}
    by_flag_severity = {}
    for entry in data["time_entries"]:
        compliance = entry.get("compliance", {})
        by_verdict.setdefault(compliance.get("verdict", "unknown"), []).append(entry)
        for flag in compliance.get("flags", []):
            by_flag_severity.setdefault(flag.get("severity", "needs_review"), []).append((entry, flag))

    lines = [
        "# DRAFT - not sent, not approved",
        "",
        f"**Pre-bill exception packet** - {eng.get('client_name')} / {eng.get('matter_name')} ({eng.get('engagement_id')})",
        "",
        f"- Prepared for: engagement manager and billing coordinator (review only)",
        f"- Period covered by the governed data: {period.get('start')} to {period.get('end')}",
    ]
    if args.requested_start or args.requested_end:
        req = (args.requested_start or period.get("start"), args.requested_end or period.get("end"))
        if req != (period.get("start"), period.get("end")):
            lines.append(f"- **Period caveat:** you asked about {req[0]} to {req[1]}, but the governed data covers "
                         f"{period.get('start')} to {period.get('end')}. Re-run the chain for the requested period before relying on this packet.")
        else:
            lines.append("- Requested period matches the governed data.")
    lines += [
        f"- Generated: {stamp} by {ENGINE_VERSION} from guideline_check output (flags quoted verbatim)",
        "",
        "## Summary",
        "",
        f"- Entries: {summary.get('total_entries')} ({summary.get('total_hours')} h)",
        "- Verdicts: " + ", ".join(f"{k} {v}" for k, v in sorted(summary.get("verdict_counts", {}).items())),
        f"- Missing time: {summary.get('missing_time_hours')} h across {len(data['missing_time_report'])} activity signal(s)",
        f"- Excluded by signal policy: {', '.join(summary.get('excluded_signal_ids') or []) or 'none'}",
        "",
    ]
    sections = (("hold_for_review", "Held for review"),
                ("needs_review", "Needs review"))
    reject_rows = by_verdict.get("reject", [])
    lines += ["## Rejects - rewrite or remove before pre-bill", ""]
    if not reject_rows:
        lines += ["None.", ""]
    else:
        lines += ["| Entry | Person | Date | Hours | Engine flags (verbatim) |", "|---|---|---|---|---|"]
        for e in reject_rows:
            lines.append(f"| {e['entry_id']} | {cell(e.get('person'))} | {e.get('date')} | {e.get('duration_hours')} | "
                         f"{flag_lines(e['compliance']['flags'])} |")
        lines.append("")
    for severity, title in sections:
        rows = by_flag_severity.get(severity, [])
        lines += [f"## {title}", ""]
        if not rows:
            lines += ["None.", ""]
            continue
        lines += ["| Entry | Person | Date | Hours | Flag (verbatim) |", "|---|---|---|---|---|"]
        for e, flag in rows:
            lines.append(f"| {e['entry_id']} | {cell(e.get('person'))} | {e.get('date')} | {e.get('duration_hours')} | "
                         f"{flag_lines([flag])} |")
        lines.append("")
    lines += ["## Missing time", ""]
    if data["missing_time_report"]:
        lines += ["| Activity | Person | Date | Hours | Subject | Citations |", "|---|---|---|---|---|---|"]
        for m in data["missing_time_report"]:
            lines.append(f"| {m['activity_id']} | {cell(m.get('person'))} | {m.get('date')} | {m.get('duration_hours')} | "
                         f"{cell(m.get('subject'))} | {', '.join(m.get('citations', []))} |")
    else:
        lines.append("None.")
    lines += ["", "## Privacy exclusions", ""]
    excluded = data.get("provenance", {}).get("excluded_signals", [])
    if excluded:
        for x in excluded:
            lines.append(f"- {x.get('activity_id')}: {cell(x.get('reason'))} [{', '.join(x.get('citations', []))}]")
    else:
        lines.append("- None. Only enabled sources were used.")
    compliant = by_verdict.get("compliant", [])
    lines += ["", "## Compliant drafts", ""]
    lines += [f"- {e['entry_id']} ({cell(e.get('person'))}, {e.get('date')}, {e.get('duration_hours')} h): "
              f"{cell(e.get('draft', {}).get('narrative'))}" for e in compliant] or ["None."]
    lines += [
        "",
        "## Next steps (human decisions)",
        "",
        "- The billing coordinator or engagement manager decides every reject, hold and missing-time item (client-billing-guidelines.md #9.2).",
        "- Nothing has been sent, submitted, approved, recoded or used to alter WIP balances. To share this packet, the assistant prepares a draft message, "
        "shows the recipients and content, and waits for your explicit confirmation. It is never sent to the client.",
        "",
    ]
    try:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines))
    except OSError as exc:
        sys.exit(f"exception_report: cannot write output: {exc}")
    print(f"exception_report: DRAFT written (not sent) -> {os.path.basename(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
