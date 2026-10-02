#!/usr/bin/env python3
"""exception_report - deterministic DRAFT pre-bill exception packet (step 5 of 5).

Reads governed.json from guideline_check and writes a Markdown review packet for the
engagement manager and billing coordinator. It only writes a local draft file: it has no
e-mail, chat or network code and never sends, submits, approves or alters WIP balances.
Engine flags are quoted verbatim; nothing is dropped or softened.

v1.0.4: governed data that holds rows outside the recorded timekeeper scope is refused
(client-billing-guidelines.md #12.1). Every data-derived cell (person, subject, narrative,
flag detail, exclusion reason, engagement names) passes the shared embedded-instruction
tripwire; flagged text is replaced by a withheld marker and never printed (#11.2). The engagement
header fields are screened together as one record, so an instruction split across them is withheld.

Governed data is never taken on trust (client-billing-guidelines.md #13.2): before rendering, the
engine re-runs the shared guideline rules (billing_rules.py) on a copy. An entry whose recorded verdict
or flags are less severe than the rules', missing-time items that differ from the rules', or summary
totals, verdict counts or missing-time hours that contradict the line items are refused: no packet
is written, and the user is told to re-run guideline_check.py. A reject never renders as compliant.
Summary figures are derived from the line items, excluded signal IDs from provenance.excluded_signals, and
every printed flag detail and citation from the re-run (a supplied detail is never printed). An exclusion
reason is printed only when it is the signal policy's own wording for that record.

Engagement identity (#13.3): the governed header must equal provenance.engagement_identity, which
activity_pull recorded from the engagement letter, or the data is refused. Signals and time entries scoped
to another engagement are counted, never named or quoted.
"""
import argparse
import datetime
import os
import sys
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import billing_rules  # noqa: E402  (shared rules, identical copies next to code_map.py and guideline_check.py)
import signal_policy  # noqa: E402  (shared copy shipped next to each engine)

ENGINE = "engine:exception_report"
ENGINE_VERSION = "exception_report/1.0.4"
CONTRACT = "ps.time-expense-narrative-compliance.v1"
HEADER_KEYS = ("client_name", "matter_name", "engagement_id")


class InputError(ValueError):
    pass


def generated_at(override):
    if override:
        try:
            datetime.datetime.fromisoformat(override.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InputError(f"--generated-at must be an ISO-8601 timestamp, got a string of {len(override)} character(s)") from exc
        return override
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_governed(path):
    payload = signal_policy.read_json(path, InputError)
    if not isinstance(payload, dict) or payload.get("contract_version") != CONTRACT:
        raise InputError(f"expected a {CONTRACT} object")
    signal_policy.validate_packet(payload, "governed")
    return payload


def cell(text):
    text = str(text if text is not None else "")
    return signal_policy.redact(text).replace("|", "\\|").replace("\n", " ")


def cells(values):
    """Join a list of data-derived values, each passed through cell(); a non-list is treated as one value."""
    if values is None:
        return ""
    return ", ".join(cell(v) for v in (values if isinstance(values, list) else [values]))


def flag_lines(flags):
    return "<br>".join(f"`{cell(f.get('flag'))}` ({cell(f.get('severity'))}): {cell(f.get('detail'))} [{cells(f.get('citations', []))}]"
                       for f in flags if isinstance(f, dict))


def main():
    ap = argparse.ArgumentParser(description="Write a DRAFT pre-bill exception packet (Markdown). Sends nothing.")
    ap.add_argument("--governed", required=True, help="governed.json from guideline_check")
    ap.add_argument("--out", required=True, help="Output Markdown draft")
    ap.add_argument("--requested-start", help="Period the user asked about (YYYY-MM-DD)")
    ap.add_argument("--requested-end", help="Period the user asked about (YYYY-MM-DD)")
    ap.add_argument("--signal-config", help="Additional signal policy JSON; it can only narrow the plugin's config/signal-sources.json, which is always applied (most restrictive wins)")
    ap.add_argument("--generated-at", help="Fixed ISO-8601 UTC timestamp for reproducible golden files")
    args = ap.parse_args()

    try:
        stamp = generated_at(args.generated_at)
        signal_policy.check_date(args.requested_start, "--requested-start", null=True)
        signal_policy.check_date(args.requested_end, "--requested-end", null=True)
        if args.requested_start and args.requested_end and args.requested_start > args.requested_end:
            raise InputError("--requested-start is after --requested-end")
        data = deepcopy(load_governed(args.governed))
        signal_policy.enforce_timekeeper_scope(data, engine=ENGINE, strict=True)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        problems, rerun = billing_rules.reconcile_governed(data, script_dir=script_dir, engine=ENGINE)
        if problems:
            raise InputError(
                f"governed data does not match a re-run of the guideline-check rules ({billing_rules.RECONCILE_CITATION}): "
                + "; ".join(problems[:6]) + (f"; and {len(problems) - 6} more" if len(problems) > 6 else "")
                + ". No packet was written; re-run guideline_check.py on the coded data")
        signal_policy.filter_packet(data, config_path=args.signal_config,
                                    script_dir=script_dir, engine=ENGINE)
    except (InputError, signal_policy.PolicyError) as exc:
        sys.exit(f"exception_report: {exc}")

    # Only re-derived flag detail and citations are printed; supplied detail text never is (#13.2).
    for entry, want in zip(data["time_entries"], rerun["time_entries"]):
        entry["compliance"]["flags"] = billing_rules.rendered_flags(entry["compliance"].get("flags"),
                                                                    want["compliance"]["flags"])
    eng = data.get("engagement", {})
    # The header fields are one record: an instruction split across client and matter name is withheld.
    header = {k: eng.get(k) for k in HEADER_KEYS if isinstance(eng.get(k), str)}
    header_hits = signal_policy.screen_record(header, pair_keys=HEADER_KEYS)
    header_withheld = bool(header_hits) or signal_policy.WITHHELD_TEXT in header.values()
    if header_withheld:
        eng = {k: signal_policy.WITHHELD_TEXT for k in HEADER_KEYS}
    packet_hold = signal_policy.packet_held(data)
    period = data.get("period") or {}
    figures = billing_rules.summary_figures(data["time_entries"], data["missing_time_report"])
    other_ids = signal_policy.other_engagement_ids(data)
    other_entries = len(data.get("provenance", {}).get("excluded_entries", []))
    other_note = (f"{len(other_ids)} activity signal(s) and {other_entries} time entr(ies) scoped to another engagement "
                  f"were excluded and are not shown ({signal_policy.ENGAGEMENT_CITATION})"
                  if other_ids or other_entries else "")
    data_dates = sorted({d for d in [e.get("date") for e in data["time_entries"]]
                         + [s.get("date") for s in data.get("activity_signals", [])] if isinstance(d, str) and d})
    actual = (data_dates[0], data_dates[-1]) if data_dates else (None, None)
    by_verdict = {}
    by_flag_severity = {}
    for entry in data["time_entries"]:
        compliance = entry.get("compliance", {})
        verdict = compliance.get("verdict")
        if verdict not in signal_policy.VERDICTS:
            verdict = "hold_for_review"  # unrecognised verdicts fail closed (validate_packet rejects them first)
        if verdict == "compliant" and (compliance.get("flags")
                                       or signal_policy.embedded_instruction(entry.get("draft", {}).get("narrative"))):
            verdict = "needs_review"  # a flagged entry is never listed as a compliant draft
        if packet_hold and signal_policy.SEVERITY_RANK[verdict] < signal_policy.SEVERITY_RANK["hold_for_review"]:
            verdict = "hold_for_review"  # a metadata hold governs every entry (#11.3); reconcile refuses it first
        by_verdict.setdefault(verdict, []).append(entry)
        for flag in compliance.get("flags", []):
            severity = flag.get("severity") if flag.get("severity") in signal_policy.SEVERITIES else "hold_for_review"
            by_flag_severity.setdefault(severity, []).append((entry, flag))

    lines = [
        "# DRAFT - not sent, not approved",
        "",
        f"**Pre-bill exception packet** - {cell(eng.get('client_name'))} / {cell(eng.get('matter_name'))} "
        f"({cell(eng.get('engagement_id'))})",
        "",
        f"- Prepared for: engagement manager and billing coordinator (review only)",
    ]
    if header_withheld:
        lines.append("- **Engagement names withheld:** " + signal_policy.hold_reason(
            header_hits, "the client, matter and engagement fields read together as an instruction")
            + "; check the engagement record (client-billing-guidelines.md #11.1, #11.2)")
    if packet_hold:
        lines.append(f"- **Metadata withheld:** {signal_policy.PACKET_HOLD_REASON}; every entry is held for review "
                     f"({signal_policy.METADATA_CITATION})")
    lines += [
        f"- Period covered by the governed data: {cell(period.get('start'))} to {cell(period.get('end'))} "
        f"(entries and activity actually dated {cell(actual[0])} to {cell(actual[1])})",
    ]
    if args.requested_start or args.requested_end:
        req = (args.requested_start or period.get("start") or actual[0], args.requested_end or period.get("end") or actual[1])
        declared = (period.get("start"), period.get("end"))
        beyond_declared = bool(declared[0] and declared[1]) and (req[0] < declared[0] or req[1] > declared[1])
        beyond_data = not data_dates or req[0] < actual[0] or req[1] > actual[1]
        narrower = bool(data_dates) and (actual[0] < req[0] or actual[1] > req[1])
        if beyond_declared or beyond_data:
            lines.append(f"- **Period caveat:** you asked about {req[0]} to {req[1]}, but the governed data contains entries "
                         f"and activity dated only {actual[0]} to {actual[1]}. Time outside those dates has not been "
                         "checked; re-run the chain for the requested period, or confirm no other time exists, before relying on this packet.")
        elif narrower:
            lines.append(f"- **Period caveat:** you asked about {req[0]} to {req[1]}, but this packet also covers entries and "
                         f"activity dated {actual[0]} to {actual[1]}. Re-run the chain for the requested period for a packet limited to it.")
        else:
            lines.append("- Requested period matches the governed data.")
    lines += [
        f"- Generated: {stamp} by {ENGINE_VERSION} from guideline_check output (flags quoted verbatim)",
        "",
        "## Summary",
        "",
        f"- Entries: {figures['total_entries']} ({figures['total_hours']} h)",
        "- Verdicts: " + ", ".join(f"{cell(k)} {cell(v)}" for k, v in sorted(figures["verdict_counts"].items())),
        f"- Missing time: {figures['missing_time_hours']} h across {len(data['missing_time_report'])} activity signal(s)",
        f"- Excluded by signal policy: {cells([x for x in billing_rules.excluded_ids(data) if x not in other_ids]) or 'none'}",
    ]
    if other_note:
        lines.append(f"- Other engagements: {other_note}")
    lines += [
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
            lines.append(f"| {cell(e.get('entry_id'))} | {cell(e.get('person'))} | {cell(e.get('date'))} | {cell(e.get('duration_hours'))} | "
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
            lines.append(f"| {cell(e.get('entry_id'))} | {cell(e.get('person'))} | {cell(e.get('date'))} | {cell(e.get('duration_hours'))} | "
                         f"{flag_lines([flag])} |")
        lines.append("")
    lines += ["## Missing time", ""]
    if data["missing_time_report"]:
        lines += ["| Activity | Person | Date | Hours | Subject | Citations |", "|---|---|---|---|---|---|"]
        for m in data["missing_time_report"]:
            lines.append(f"| {cell(m.get('activity_id'))} | {cell(m.get('person'))} | {cell(m.get('date'))} | {cell(m.get('duration_hours'))} | "
                         f"{cell(m.get('subject'))} | {cells(m.get('citations', []))} |")
    else:
        lines.append("None.")
    lines += ["", "## Privacy exclusions", ""]
    excluded = [x for x in data.get("provenance", {}).get("excluded_signals", [])
                if x.get("activity_id") not in other_ids]
    # reconcile_governed has already matched every reason and citation to the engines' own wording (#13.2).
    for x in excluded:
        lines.append(f"- {cell(x.get('activity_id'))}: {cell(x.get('reason'))} [{cells(x.get('citations', []))}]")
    if other_note:
        lines.append(f"- {other_note}.")
    if not excluded and not other_note:
        lines.append("- None. Only enabled sources were used.")
    compliant = by_verdict.get("compliant", [])
    lines += ["", "## Compliant drafts", ""]
    lines += [f"- {cell(e.get('entry_id'))} ({cell(e.get('person'))}, {cell(e.get('date'))}, {cell(e.get('duration_hours'))} h): "
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
    text = "\n".join(lines)
    try:
        signal_policy.write_output(args.out, text)  # encodes first, then temp file + os.replace
    except (OSError, UnicodeError) as exc:
        sys.exit(f"exception_report: cannot write output: {exc}")
    print(f"exception_report: DRAFT written (not sent) -> {os.path.basename(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
