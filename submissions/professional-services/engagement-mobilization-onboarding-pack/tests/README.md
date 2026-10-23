# Tests and demo data: engagement-mobilization-onboarding-pack

Demo data and the regression suite for the **engagement-mobilization-onboarding-pack** plugin. They
live in the submission folder (`submissions/professional-services/engagement-mobilization-onboarding-pack/`)
beside `skills/`, but none of this ships in the MOS3 package; the package holds only `manifest.json`,
the two icons and `skills/`.

```text
engagement-mobilization-onboarding-pack/
├── demo-data/
│   ├── scenario-a-happy/   raw/, upstream/, expected/
│   └── scenario-b-drama/   raw/, upstream/, expected/
└── tests/
    ├── README.md                this file
    ├── run_tests.py             the runner (streams PASS/FAIL per check, grouped)
    └── sample-test-prompts.csv  human spot-check prompts with expected routing and results
```

## What belongs in the suite

The suite holds only checks that were added to fix a finding from a Cowork evaluation (archived
under the plugin's `Evaluation\<version>\` folder in the SharePoint library). New checks are added
only in response to Cowork findings; internal QA rounds, class sweeps, shared-detector corpus checks
and package-layout checks are not kept here.

| Group | Added by | Cowork finding it covers |
| --- | --- | --- |
| `v101_checks` (34 checks) | 1.0.1 (`6d6e383`) | Cowork 1.0.0 blockers: novel and paraphrased steering lines (wall/conflict status, approvals, permission grants, send-to-address, suppression, homoglyphs) are caught, withheld everywhere and hold the pack, with no false positives on benign domain lines; wall-register briefing topics that name other clients or matters are screened; a pending wall review holds the pack; wrong JSON types stop with `InputError` and unknown enums fail closed; skill descriptions, routing (wall-status claims to `wall-check`, cold start to `engagement-retrieve`) and failure handling; every emitted citation resolves to a reference section; the contract declares the new statuses and fields |
| `v102_checks` (12 checks) | 1.0.2 (`25e6cbd`) | Cowork 1.0.1 No-ship complete-chain finding: Closeout `drafting_guidance` is never rendered as a lesson (`LC-A-001` is excluded as unwritten), and a first-week item that points at knowledge pending practice review (`AST-A-001`) is restated as a title-and-citation note, never an instruction to read it |
| `v106_checks` (3 checks) | 1.0.6 | Cowork 1.0.5 blocker R-01 (security scan): no shipped file under `skills/` contains the quoted instruction-override phrase, matched whole, case-insensitively and with whitespace normalised (a line-split copy is caught), nor with its words separated only by comment markers, quotes or punctuation; every `steering_guard.py` copy still detects the phrase without containing it, and the shared guard, safety helper and ethical-wall reference are byte-identical in all five skills. The earlier checks drive the engines with attack text but never read the shipped files' own text, so the phrase could move unnoticed. The scan covers whole files, code included, and matches the exact quoted words rather than the detector's pattern: the detector's regexes spell the phrase with `\s`, optional groups and alternations, so they never hold the words in a row |

| `v107_checks` (2 checks) | 1.0.7 | Cowork evaluation matrix 2026-10-22-1252 top blocker 3 (open spec conflicts, owner decision 2026-10-23) in `pack-draft/SKILL.md`. D1: Steps, Failure handling and Escalation all state that an `on_hold_internal_only` pack is drafted for internal use with the holds first, never drafting past a hold's content, and "do not draft past them" is gone. L2: step 5 keeps the engine's `Proposed, not assigned: <name> for <role>` line exactly, and the engine still renders it (Scenario B's Jules Park line, fresh and golden) |

Later rewrites of these checks (for example a label noting a stricter behaviour from a QA round)
are the same checks and stay in their group.

## Running the suite

Run from the submission folder. The runner prints the plugin root and data root it resolved first. It
then runs Scenario A and Scenario B through `scope_digest` → `knowledge_match` → `wall_check` →
`access_checklist` (shared setup that the checks read), and prints `PASS <label>` or
`FAIL <label> (detail)` as each check runs, under a `== group <name>` header. It repeats any
failures under `== failures` and ends with `N/M checks passed` (exit 1 on any failure).

Against the source submission (the default when neither `--plugin-root` nor `PLUGIN_ROOT` is set):

```powershell
python tests\run_tests.py
```

Against a built package, extract `public\bundles\engagement-mobilization-onboarding-pack.zip` to a
folder and pass it as the plugin root (or set the `PLUGIN_ROOT` environment variable):

```powershell
Expand-Archive public\bundles\engagement-mobilization-onboarding-pack.zip $env:TEMP\emop-zip
python tests\run_tests.py --plugin-root $env:TEMP\emop-zip
```

`skills/...` paths resolve against the plugin root and `demo-data/...` and `tests/...` paths
against the submission folder (the parent of `tests\`), so the working directory does not matter.
The runner stops with exit 2 and a clear error if the plugin root has no `skills\` folder.

- `--list-groups` prints the check group names, one per line.
- `--group NAME` (repeatable) runs only those groups, in suite order, after the shared scenario
  chain setup; for example `python tests\run_tests.py --group v102_checks`.
- An unknown group or argument exits 2.

## Scenarios

- **`scenario-a-happy`** (Orchard Ridge Clinics, `MOB-ORC-1042`): Taylor Reed joins as delivery
  analyst on a confirmed roster with a clear wall. One released Closeout asset (`AST-A-001`, pending practice review)
  is matched, the Closeout lesson `LC-A-001` is excluded because it has no written text, four
  least-privilege access requests are drafted, and the pack is `draft_internal_only`.
- **`scenario-b-drama`** (Nimbus Retail Bank, `MOB-NRB-3100`): Riley Chen is restricted by the
  ethical-wall register, so no prior knowledge is released (`denied_by_wall`), two workspaces are
  denied, one is held pending wall review and one is not requested because it exceeds the role.
  Jules Park is only proposed by Scenario 02, Dana Cho is excluded from the roster as ineligible,
  a source field carrying an embedded instruction is held, and the pack is `on_hold_internal_only`.

Each scenario has `raw/` (the SOW, engagement-letter and pursuit-record extracts, confirmed roster,
wall register and workspace inventory), `upstream/` (the Scenario 01 Closeout governed record and
the Scenario 02 validated staffing output) and `expected/` (the five goldens).
`upstream/closeout-governed.json` keeps Closeout's own engine stamps. `sample-test-prompts.csv`
lists chat prompts against these scenarios with the expected routing and result; it is for human
spot checks, and one `v101_checks` check reads it to confirm the "PM note says wall cleared" prompt
routes to `wall-check`.
