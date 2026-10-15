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
| `tests/run_tests.py` | Engine regression suite (Python 3 standard library), 4 groups, 169 checks |
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
