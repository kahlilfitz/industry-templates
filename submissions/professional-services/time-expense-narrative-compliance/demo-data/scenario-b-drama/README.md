# Scenario B - Drama path

This scenario is built to fool a skim reviewer. The longest entry (TE-B-001, Morgan Lee, 7.5 hours) reads like professional English, but it is rejectable: it links three activity classes (client meeting, document analysis, research), uses prohibited wording and uncured vague phrases, has no work verb or purpose clause, and links activity from a different date. The deterministic engines also surface a duplicate same-meeting narrative, a plausible but wrong task code, a non-billable internal entry and three hours of unrecorded document work.

What to notice:

| Finding | Entry / signal | Engine | Guideline |
|---|---|---|---|
| Mailbox link excluded, not used as evidence | TE-B-001 -> B-MAIL-001 | activity_pull, then every engine | #10.1 |
| Block billing (3 classes in 7.5 h) | TE-B-001 | guideline_check | #2.1 |
| Prohibited terms, uncured vague phrases, missing actor + purpose | TE-B-001 | guideline_check | #3.1, #3.2, #1.2 |
| Conflicting classes -> UNMAPPED at 0.40, held | TE-B-001 | code_map | task-phase-codes #5.3 |
| Linked activity on another date; evidence overrun | TE-B-001 | guideline_check | #6.2 |
| Duplicate meeting narrative | TE-B-003 (vs TE-B-002) | guideline_check | #7.1 |
| Wrong task code AN220, should be DL300 | TE-B-003 | code_map | #4.1, #4.2 |
| Non-billable internal staffing; under 12 words | TE-B-004 | guideline_check | #5.1, #1.1 |
| Missing time: B-DOC-003 (2.0 h) + B-DOC-004 (1.0 h) | no entry | guideline_check | #8.1 |

The mailbox item: `raw/timesheet.csv` row 2 still links `B-MAIL-001`, a mailbox item. Mailbox content and metadata are disabled in `config/signal-sources.json`, so `activity_pull` never opens a mailbox export; it removes the link from evidence and records it under `provenance.excluded_signals` with the #10.1 citation. Every later engine re-applies the same policy (`signal_policy.py`), and `guideline_check` raises a `disabled_source_signal` hold on TE-B-001.

Run order (from this folder; `S` = the plugin's `skills` folder; `--generated-at` pins the timestamp so the files below reproduce exactly):

1. `python3 $S/activity-pull/scripts/activity_pull.py --raw-dir raw --all-timekeepers --period-start 2026-09-14 --period-end 2026-09-18 --scenario scenario-b-drama --out activity.json --generated-at 2026-09-23T00:00:00Z`
2. `python3 $S/narrative-draft/scripts/narrative_draft.py --activity activity.json --out expected/drafted.json --generated-at 2026-09-23T00:00:00Z`
3. `python3 $S/code-map/scripts/code_map.py --drafted expected/drafted.json --out expected/coded.json --generated-at 2026-09-23T00:00:00Z`
4. `python3 $S/guideline-check/scripts/guideline_check.py --coded expected/coded.json --out expected/governed.json --generated-at 2026-09-23T00:00:00Z`
5. `python3 $S/exception-report/scripts/exception_report.py --governed expected/governed.json --out expected/exception-report.md --generated-at 2026-09-23T00:00:00Z`

`--all-timekeepers` is the engagement-manager view. A single timekeeper uses `--person "Morgan Lee"` instead.
