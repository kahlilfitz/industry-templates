# Test data: time-expense-narrative-compliance 1.0.6

Demo data and the engine regression suite for **Time & Expense Narrative Compliance**
(`time-expense-narrative-compliance`) **version 1.0.6**. The plugin source is
`submissions/professional-services/time-expense-narrative-compliance/`; its MOS3 package ships
only `manifest.json`, the two icons and `skills/`, so nothing in this folder is installed with the
plugin. The plugin handles time entries only; expense reports and receipts are out of scope.

## Layout

| Path | Contents |
|---|---|
| `demo-data/scenario-a-happy/` | Raw engagement exports (`raw/`), the activity packet `activity.json`, engine goldens (`expected/`) and a README with the run order |
| `demo-data/scenario-b-drama/` | Same layout; the skim-proof rejection case |
| `tests/run_tests.py` | Engine regression suite (Python 3 standard library), 39 groups |
| `tests/check_shared_copies.py` | Fails when a skill's copy of a shared file drifts from the canonical copy in `skills/activity-pull/` (`billing_rules.py`: `skills/guideline-check/`), or `steering_guard.py` from its pinned SHA-256 |
| `tests/steering-corpus.json` | Shared embedded-instruction corpus (byte-identical to `shared/steering-guard/`), attack and benign sets |
| `tests/sample-test-prompts.csv` | Human spot-check prompts for the tracker |

## Running the tests

Run from this folder. The runner resolves `demo-data/...` and `tests/...` against this folder (the
parent of `tests/`, not the current directory) and `skills/...` against the plugin root.

```powershell
# Against the submission source (the default plugin root)
python tests\run_tests.py

# Against a built package: expand public\bundles\time-expense-narrative-compliance.zip first
python tests\run_tests.py --plugin-root <extracted ZIP folder>

# Equivalent, via the environment
$env:PLUGIN_ROOT = '<extracted ZIP folder>'; python tests\run_tests.py

# Shared-copy check on its own (same plugin-root rules)
python tests\check_shared_copies.py --plugin-root <extracted ZIP folder>
```

With neither `--plugin-root` nor `PLUGIN_ROOT`, the plugin root defaults to
`<repo>\submissions\professional-services\time-expense-narrative-compliance`. The runner prints both
resolved roots, exits 2 if the plugin root has no `skills\`, streams one `PASS`/`FAIL` line per check
under `== group <name>` headers, repeats failures under `== failures` and ends with
`N/M checks passed` (exit 1 on any failure). `--list-groups` prints the group names; `--group NAME`
(repeatable) runs only those groups plus any group whose state they read. An unknown group or
argument exits 2.

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

The suite also covers timekeeper scope and the engagement-manager team view, embedded-instruction
screening with the shared corpus (attack lines must trip, benign lines must not), whole-chain
re-derivation and reconciliation, contract and input validation, privacy exclusions, period checks,
atomic writes and ASCII-safe output. MOS3-specific checks: every skill carries
`config/signal-sources.json` byte-identical to the canonical `skills/activity-pull/config/` copy;
each engine loads only the copy in its own skill folder and never a file above it (without its copy
a skill runs on the narrow default, mailbox sources off); and the package boundary (no demo data,
tests, `.claude-plugin` or root `config/`, `contracts/`, `references/` in the plugin root, and no
SKILL.md or script reference that leaves its skill folder).

## Freezing

This folder is frozen once version 1.0.6 is evaluated: `FROZEN.sha256` is written at freeze time
and `npm run check:test-data` then fails on any change. A new plugin version copies this folder
forward to a new version folder and changes the copy.
