# Scenario A - Happy path

Alex Rivera has three clean engagement activities (one client meeting, one document analysis, one deliverable draft) and three matching time entries with no narrative yet. The engines build the activity packet from the raw exports, draft grounded narratives, map codes and pass guideline compliance with no missing time.

What to notice:

- Every narrative word comes from cited metadata: the calendar title and attendees, the document file name, and the purpose and deliverable in `raw/engagement-workplan.csv`. Nothing is padded to reach the 12-word minimum.
- TE-A-001 says "Attended", not "Led": the calendar export shows the Orion product lead organized the session.
- Mailbox sources are off in `config/signal-sources.json` (each skill's copy); `raw/mailbox-summary.txt` is never opened.

Run order (from this folder; `S` = the plugin's `skills` folder; `--generated-at` pins the timestamp so the files below reproduce exactly - omit it in real use to record the real UTC time):

1. `python3 $S/activity-pull/scripts/activity_pull.py --raw-dir raw --requester "Alex Rivera" --period-start 2026-09-14 --period-end 2026-09-18 --scenario scenario-a-happy --out activity.json --generated-at 2026-09-23T00:00:00Z`
2. `python3 $S/narrative-draft/scripts/narrative_draft.py --activity activity.json --out expected/drafted.json --generated-at 2026-09-23T00:00:00Z`
3. `python3 $S/code-map/scripts/code_map.py --activity activity.json --drafted expected/drafted.json --out expected/coded.json --generated-at 2026-09-23T00:00:00Z`
4. `python3 $S/guideline-check/scripts/guideline_check.py --activity activity.json --coded expected/coded.json --out expected/governed.json --generated-at 2026-09-23T00:00:00Z`
5. `python3 $S/exception-report/scripts/exception_report.py --activity activity.json --governed expected/governed.json --out expected/exception-report.md --generated-at 2026-09-23T00:00:00Z`

`python3 tests/run_tests.py` (from this test-data version folder; add `--plugin-root <dir>` to test a built package) re-runs this chain and checks every file byte for byte.
