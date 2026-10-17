# Time & Expense Narrative Compliance - tests and demo data

Demo data and the engine regression suite for **Time & Expense Narrative Compliance**
(`time-expense-narrative-compliance`). They live in the submission folder beside `skills/`
(`demo-data/` and `tests/`); the MOS3 package ships only `manifest.json`, the two icons and
`skills/`, so neither folder is installed with the plugin. The plugin handles time entries only; expense reports and receipts are out of scope.

## Layout

| Path | Contents |
|---|---|
| `demo-data/scenario-a-happy/` | Raw engagement exports (`raw/`), the activity packet `activity.json`, engine goldens (`expected/`) and a README with the run order |
| `demo-data/scenario-b-drama/` | Same layout; the skim-proof rejection case |
| `tests/run_tests.py` | Engine regression suite (Python 3 standard library), 12 groups, 257 checks |
| `tests/sample-test-prompts.csv` | Human spot-check prompts for the tracker |

## Running the tests

Run from `submissions\professional-services\time-expense-narrative-compliance\`. The runner resolves
`demo-data/...` and `tests/...` against the submission folder (the parent of `tests/`, not the
current directory) and `skills/...` against the plugin root.

```powershell
# Against the submission source (the default plugin root)
python tests\run_tests.py

# Against a built package: expand public\bundles\time-expense-narrative-compliance.zip first
python tests\run_tests.py --plugin-root <extracted ZIP folder>

# Equivalent, via the environment
$env:PLUGIN_ROOT = '<extracted ZIP folder>'; python tests\run_tests.py
```

With neither `--plugin-root` nor `PLUGIN_ROOT`, the plugin root defaults to the submission folder.
The runner prints both
resolved roots, exits 2 if the plugin root has no `skills\`, streams one `PASS`/`FAIL` line per check
under `== group <name>` headers, repeats failures under `== failures` and ends with
`N/M checks passed` (exit 1 on any failure). `--list-groups` prints the group names; `--group NAME`
(repeatable) runs only those groups. An unknown group or argument exits 2.

## What the suite checks

Every check answers a finding from a Cowork evaluation of this plugin. A check is added only in
response to a Cowork finding; internal QA rounds do not add checks to this suite.

| Group | Checks | Added in | Cowork finding it answers |
|---|---|---|---|
| `golden_tests` | 10 | 1.0.2 | 1.0.1 evaluation: re-running the whole chain on both scenarios with the fixed `--generated-at` reproduces `activity.json` and every `expected/` golden byte for byte |
| `fixture_tests` | 62 | 1.0.2, 1.0.3 | 1.0.1 evaluation: privacy floor (disabled-source signals, stand-alone policy tampering), grounded rewrites with originals preserved, truthful exception sections, embedded authority/instruction text (including zero-width evasion), short narratives left unpadded, citation hygiene and bad input; 1.0.3 fixes for the canonical 1.0.1 Blocked findings B1 (conflicting-class code mapping, NB900/BH910), B2 (`no_linked_evidence`), B3 (additive `--signal-config`), B4 (instruction paraphrases) and the period caveat |
| `hardening_tests` | 66 | 1.0.4 | Cowork 1.0.3 trust-and-safety blockers: external-recipient and timekeeper-scope guardrails in every `SKILL.md`, timekeeper scope (data minimisation) in every engine, embedded instructions in subjects, deliverables, missing-time rows and rewrites withheld everywhere, citation integrity, mixed-entry coverage, the empty-period warning, and the attack-paraphrase and benign domain-prose sets |
| `te107_tests` | 31 | 1.0.7 | Cowork 1.0.6 recommendations F02 (`partially_mapped_activity_classes`) and F03 (purpose verbs and inflected vague phrases) |
| `te108_tests` | 13 | 1.0.8 | Cowork 1.0.7 required fixes in guideline-check: F-01 (pasted-narrative intake: Step 0 asks for engagement, period, timekeeper, entry ID and every raw export, keeps the narrative in its timesheet row, builds activity → drafted → coded, names missing inputs and offers the earlier stage) and F-02 (missing time starts from raw exports through activity-pull, narrative-draft and code-map; both packets mandatory). The end-to-end checks run the stages in the order Step 0 names |
| `te109_tests` | 20 | 1.0.9 | Cowork 1.0.8 required fixes: F-01 (GC-03: every grounded draft on the same fixture passes #1.2 with walk-through, go-over and discuss purposes; bare verbs and look-alikes are not credited; all three rules copies agree), F-02 (GR-01: no refusal-routing exclusions, quoted approval/submission/write-off triggers and an action-only guardrail), F-03 (GR-05: explicit personal/contact/compensation/rate exclusions and letter-first manager check; AP-01: self-mode withheld colleagues are distinct and anonymous, preserved by every downstream engine with raw re-derivation, including colleagues found only in calendar, document activity or timesheets) |
| `te110_tests` | 15 | 1.0.10 | Cowork 1.0.9 required fixes: R-01 (ND-01: noun purposes use "regarding", calendar title initials are lower-case mid-sentence, every generated narrative passes #1.2 on the same fixture, all shared purpose verbs retain "to", unsupported purposes are not credited, and all five policy copies agree), R-02 (ER-01: an other-engagement exclusion built from raw exports cites #10.1 and #13.3 in the summary and privacy section, and the signal-policy summary line cites #10.1), R-03 (ER-01: each entry has full rows once, under its own verdict, and rejected entries are cross-referenced with their hold and needs-review flags) |
| `te111_r01_tests` | 3 | 1.0.11 | Cowork 1.0.10 R-01 / AP-01: an explicit "show me activity.json" request uses the presentation view; flagged signals and entries expose only ID, date, hours and a withheld notice; the unchanged internal contract still passes downstream raw re-derivation |
| `te111_r02_tests` | 3 | 1.0.11 | Cowork 1.0.10 R-02 / AP-02: named colleagues are passed without a confirmation to record the denied request, the reason cites the letter's lack of authorization, and every downstream engine preserves the denial and self-only rows when re-deriving from raw exports |
| `te111_r04_tests` | 2 | 1.0.11 | Cowork 1.0.10 R-04 / GC-01: the entries table includes a date and Notes has explicit slots for flagged-entry and withheld-row notices |
| `te112_r03_tests` | 15 | 1.0.12 | Cowork 1.0.10 R-03 / ND-01: raw-export reproductions for redundant research labels, repeated title/purpose clauses, noun-purpose articles and a single participant list; the grammar list covers every draft, the full chain still passes #1.2, invented and flagged purposes are not credited, and determiners, extra purpose meaning, non-participant "with" text, one-word subjects and research as an object or possessed noun are preserved |
| `te113_tests` | 17 | 1.0.13 | Cowork 1.0.12 R-01 / ND-01, ND-03, GR-02: title groups and attendees share one "with" clause without duplicated names or doubled prepositions; R-02 / ND-01, ND-03: case/article-insensitive repeated deliverables and purposes are omitted in both clause orders, distinct meaning stays visible, omitted purposes require exact grounded wording, and the 11-word scenario-B suggestion stays unpadded; R-03 / GR-02: each downstream skill independently excludes personal and rate data |

For 1.0.13, the original unchanged suite passed 240/240, with no pre-existing failures. On resuming
after the owner's extended R-02 exception, the retained R-01/R-03 changes passed 248/248 before
re-applying R-02. The new `te113_tests` group fails 15/17 checks on the unfixed 1.0.12 engines and
instructions (including checks for each fix ID); two preservation controls already pass there.
All 17 pass on 1.0.13, and the full suite passes 257/257.

The owner's exception in `AGENTS.md` and `docs/release-process.md` authorizes exactly one existing
assertion change: in `per-activity rewrites on a multi-link entry are needs_review and name what
they leave out`, the status condition becomes `r["status"].startswith("needs_review")`. Its "only"
reason and `covered_activity_ids` conditions are unchanged, and this check passes separately.
AST comparison of all 59 pre-existing test/helper functions confirms that no other existing
assertion changes. The other 239 existing checks pass unchanged.

Both demo chains were regenerated from their raw inputs at `2026-09-23T00:00:00Z`. The edited
files in each of `demo-data/scenario-a-happy/` and `demo-data/scenario-b-drama/` are `activity.json`,
`expected/drafted.json`, `expected/coded.json`, `expected/governed.json` and
`expected/exception-report.md`. Seven outputs differ only in engine version labels, verified byte
for byte. The three scenario-B JSON expected outputs additionally contain only the owner's
authorized TE-B-001/B-DOC-001 suggestion change: remove " for the Integration Design", set
`needs_review_insufficient_detail` and add the 11-word #1.1 review reason. A full parsed-output
comparison confirms every other value is unchanged. No raw export or other demo file is edited.

All copied engines agree byte for byte, `steering_guard.py` is unchanged, `check:submissions`
passes and all 54 `test:evaluation` checks pass. These are local ND-01/ND-03 engine reproductions
and GR-02 standalone-instruction checks, not new Cowork built-in runs or a publish decision.

For 1.0.12, the unchanged 1.0.11 suite passed 225/225 before editing. The owner's explicit exception
in `AGENTS.md` and `docs/release-process.md` authorizes replacing only the literal-bound condition of
`1.0.10 R-01 ND-01: noun purposes use regarding, never an ungrammatical to clause` in `te110_tests`.
The check keeps its name but now asserts grounded grammatical noun-purpose wording or omission of
a purpose already stated by the title, rejects `to` plus the noun phrase, and requires #1.2 purpose
recognition. All 224 other existing checks and their expectations are unchanged; an AST comparison
of the 57 pre-existing test functions confirms the single authorized condition is the only change.

The new `te112_r03_tests` group runs the entire raw-export chain, not hand-edited packets. Against
the original 1.0.11 engines, seven new checks and the authorized replacement fail; the eight
additional controls pass. All 15 new checks and the replaced check pass on 1.0.12, and the entire
suite passes 240/240. `check:submissions` and all 40 `test:evaluation` checks pass. This is a local
ND-01 reproduction, not a new Cowork built-in evaluation. Both demo chains were regenerated and
all ten outputs differ only in version labels; raw exports and behavioral goldens are unchanged.

For 1.0.11, all 217 baseline checks passed before the fixes. All eight added checks failed on
the unfixed engines/instructions and pass afterwards; the full suite passes 225/225. No existing
check or expected result changed, and there were no pre-existing failures.

In 1.0.11, R-03 was skipped: the protected `te110_tests` check named
`1.0.10 R-01 ND-01: noun purposes use regarding, never an ungrammatical to clause` requires the
exact substring ` regarding internal staffing check-in`. On its fixture the title is
`Staffing check-in`; either suppressing the repeated purpose or adding the required article
removes that substring. The 1.0.11 brief did not authorize changing that expectation. Narrative
behavior was left unchanged until the one-time exception used for 1.0.12 above, and no R-03 check
was added for the unapplied 1.0.11 fix. The legacy `withheld.requested` key also remains because existing hardening and
`te109_tests` checks assert it; R-02 fixes the denial reason and the instructions instead.

Both demo chains were regenerated with `--generated-at 2026-09-23T00:00:00Z`. In each of
`demo-data/scenario-a-happy/` and `demo-data/scenario-b-drama/`, only engine version labels changed
in `activity.json`, `expected/drafted.json`, `expected/coded.json`, `expected/governed.json` and
`expected/exception-report.md`. Raw exports and all other demo files are unchanged. AP-01,
AP-02 and GC-01 checks are local reproductions of the findings, not new Cowork built-in runs.

For 1.0.10, the new group reproduced R-01, R-02 and R-03 failures before the fixes.
The 202 pre-existing checks and their expectations are unchanged. Version-label regeneration was
checked separately: all ten demo outputs changed only their engine labels. R-02/R-03 were attempted,
but failed the two protected exception-report golden checks; they were reverted and skipped rather
than changing those expected results. Owner resolution is required and no commit was made.
Raw exports are unchanged. The ND-01 checks are local engine reproductions, not a new Cowork
built-in evaluation.

`fixture_tests` and `hardening_tests` run inside `defence_in_depth()`: their hand-edited packets
pass the activity re-derivation gate so the defences behind it stay under test.

## What the scenarios cover

- **Scenario A, happy path** (`scenario-a-happy`): Alex Rivera has three clean engagement
  activities and three matching time entries with no narrative. The chain drafts grounded
  narratives ("Attended", not "Led", where Alex did not organise the meeting), maps codes and passes
  guideline compliance; the exception packet has no exceptions.
- **Scenario B, drama path** (`scenario-b-drama`): a fluent 7.5-hour entry that is still
  rejectable (block billing across three activity classes, prohibited and vague wording, missing
  elements, `UNMAPPED` at 0.40, linked activity on another date, evidence overrun), a duplicate
  meeting narrative, a wrong submitted task code, a mailbox link excluded under the off-by-default
  signal policy (#10.1), and three hours of document activity with no time entry (missing time).
