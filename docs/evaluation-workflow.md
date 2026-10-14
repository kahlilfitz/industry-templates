# Cowork evaluation workflow

This runbook describes how to freeze a plugin release candidate, evaluate the exact artifact in
Cowork, and archive the required evidence. Repository scripts automate artifact integrity and file
placement. Cowork performs the automated evaluation. Human reviewers retain publication authority.
For the end-to-end workstream around it, see the [operator runbook](operator-runbook.md).

## Evidence contract

Each evaluation archive contains exactly the evaluated ZIP and three Cowork reports:

```text
<SharePointRoot>/<Industry>/<plugin-slug>/Evaluation/<artifact-version>/
├── <plugin-slug>.zip
├── plugin-health.html
├── behavioral-test-report.html
└── recommendations.html
```

`plugin-health.html` and `behavioral-test-report.html` are the two reports the testing strategy
defines. `recommendations.html` states the identity check and the automated verdict, decided only
from those two reports, and lists suggested fixes.

A MOS3 candidate (see [MOS3 package format and test data](#mos3-package-format-and-test-data)) also
archives its test-data ZIP next to the plugin ZIP, as the record of the tests and fixtures that
version was verified against: `<plugin-slug>-test-data-<artifact-version>.zip`. It is not sent to
Cowork, is not part of the candidate, and is never distributed.

Keep successful and failed evaluations. Never rebuild or replace an evaluated ZIP after the Cowork
run. A changed artifact requires a new package version and a new evaluation folder.

## Responsibilities

| Activity | Repository scripts | Cowork | Human |
|---|:---:|:---:|:---:|
| Validate, build, and freeze the ZIP | Yes | | |
| Run automated evaluation | | Yes | |
| Generate the three HTML reports | | Yes | |
| Validate and archive evidence | Yes | | |
| Perform independent human reviews | | | Yes |
| Approve publication | | | Yes |

An automated `Ready for human review` verdict is not a publication decision. Both reviewers run every prompt in the
tracker; the critical-path prompts are the mandatory minimum the tracker must contain.

## Prerequisites

1. Install Node.js 22 and run `npm install`.
2. Ensure the plugin's `metadata.json` and `.claude-plugin/plugin.json` use the same version. For a
   MOS3 submission, `metadata.json` and the root `manifest.json` must use the same version, and the
   version's test data must exist under `test-data\`.
3. Complete plugin-specific regression tests.
4. Link the synchronized Industry Templates SharePoint library into the repository once with
   `npm run sharepoint:link`, and confirm `npm run sharepoint:doctor` reports ready. See
   [SharePoint sync](sharepoint-sync.md).

Evidence is archived through the repository's `sharepoint` link, so it syncs to SharePoint. The
archive root is resolved in this order: `--sharepoint-root`, then `INDUSTRY_TEMPLATES_SHAREPOINT_ROOT`,
then the `sharepoint` link. A plain, unsynced `sharepoint` folder is refused. To archive into a
different synchronized folder, set:

```powershell
$env:INDUSTRY_TEMPLATES_SHAREPOINT_ROOT = "C:\path\to\synced\Industry Templates"
```

Alternatively, pass `--sharepoint-root` to the archive command.

## Step 1: prepare and freeze the candidate

From the repository root, run:

```powershell
npm run evaluation:prepare -- --slug <plugin-slug>
```

The command:

1. Validates every submission, and that every vendored copy of a `shared/` module matches its
   source (`npm run check:shared`).
2. Rebuilds all reproducible bundles.
3. Confirms the submission and plugin-manifest versions agree (`.claude-plugin/plugin.json`, or the
   root `manifest.json` for a MOS3 submission).
4. Refuses a MOS3 version whose test data ships no regression runner (`tests/run_tests.py` or
   `tests/test_engines.py`). Preparation runs no test suite: the one full suite run happens before
   committing, from the test-data version folder against the source
   ([operator runbook](operator-runbook.md#the-lifecycle-loop), step 2). The bundler copies files byte
   for byte, so the frozen ZIP holds the code that run tested.
5. Copies the generated bundle into an immutable local run folder.
6. Records the SHA-256, Git commit, dirty-worktree state, artifact version, and Cowork task name.
7. Generates a ready-to-paste Cowork prompt.
8. Refuses to replace an existing candidate for the same plugin version.

Preparation always validates and rebuilds every submission; it has no `--only`. While several
plugins are changing in parallel, check or build one submission with
`npx tsx scripts/import-submissions.ts --check --only <plugin-slug>` (or without `--check` to build
only that bundle and leave the others in place), and prepare once every submission passes.

The generated Cowork prompt asks Cowork to run the plugin evaluation defined in the testing
strategy and nothing else. It does not run the shipped test suite; that runs once, before
committing (see step 4 above).

The result is:

```text
evaluation-inbox/<plugin-slug>/<artifact-version>/
├── <plugin-slug>.zip
├── evaluation-run.json
└── cowork-prompt.txt
```

`evaluation-inbox/` is ignored by Git. Preserve this folder until the reports have been archived.

If preparation records `"gitDirty": true`, the exact ZIP remains hash-protected, but the run is not
fully traceable to the recorded commit alone. Prefer preparing from a clean worktree for formal
release evidence.

### MOS3 candidates

For a submission with `"packageFormat": "mos3"`, preparation also:

1. Runs `npm run check:test-data` after the build.
2. Builds `<plugin-slug>-test-data-<version>.zip` from `test-data\<industry>\<plugin-slug>\<version>\`.
3. Does not run the runners, and Cowork does not run them either. Each runner must still read only
   `--plugin-root` and its own version folder (runbook
   [runner contract](operator-runbook.md#mos3-test-data)), so the archived test-data ZIP reproduces
   the run against the archived plugin ZIP.
4. Validates the plugin ZIP with the Microsoft 365 Agents Toolkit CLI:

   ```powershell
   npx --yes @microsoft/m365agentstoolkit-cli validate --package-file <plugin ZIP> --interactive false
   ```

   A non-zero exit fails preparation. Package validation needs no Microsoft 365 sign-in, and
   `--interactive false` keeps the toolkit from opening a sign-in window; it is stopped after 15
   minutes. `--skip-atk` skips it for local iteration only: the command
   prints `LocalChecksOnly: not a deployable acceptance result` and records `"atkValidated": false`
   in the receipt. Do not send a `--skip-atk` candidate for formal evaluation.
5. Copies both ZIPs into the inbox (the test-data ZIP only for the archive) and records
   `packageFormat`, `testDataFile`, `testDataSha256` and `atkValidated` in `evaluation-run.json`.
6. Renders the prompt from `docs\evaluation\cowork-evaluation-prompt-mos3.txt`.
7. Writes `FROZEN.sha256` into the test-data version folder. Commit it: from then on
   `check:test-data` fails if that folder changes.

```text
evaluation-inbox/<plugin-slug>/<artifact-version>/
├── <plugin-slug>.zip
├── <plugin-slug>-test-data-<artifact-version>.zip
├── evaluation-run.json
└── cowork-prompt.txt
```

## Step 2: run the Cowork task

This step is manual because Cowork does not support changing its task output directory from the
repository scripts.

1. Open Cowork.
2. Create a task using the exact `coworkTaskName` from `evaluation-run.json`.
3. Attach only `<plugin-slug>.zip` from the frozen `evaluation-inbox` folder. For a MOS3 candidate,
   do not attach the test-data ZIP.
4. Do not attach the mutable copies under `public/bundles/` or `public/test-data/`.
5. Attach or reference `Industry-Templates-Plugin-Testing-Strategy.docx`.
6. Paste the complete contents of `cowork-prompt.txt`.
7. Confirm the prompt requests exactly:
   - `plugin-health.html`
   - `behavioral-test-report.html`
   - `recommendations.html`
8. Start the task and wait for it to finish. Runs typically take 1–3 hours.
9. Do not rename or edit the generated reports.

Always create a new Cowork task for each artifact version. Reusing a task from an earlier version
can save the new attachment as `<plugin-slug> (1).zip`, which the watcher never matches; can mix old
and new reports, because the filenames are fixed and only `recommendations.html` is hash-checked; and
leaves the earlier verdict in the conversation, where it can bias the evaluator.

Resuming a stalled run of the same version in the same task is fine: type
`continue and produce the 3 reports`.

The Cowork task list can show a task as failed while the task page shows it still working. Trust
the task page and whether the task's output folder is still changing.

`recommendations.html` must visibly state the plugin slug, artifact version, Cowork task/run label,
artifact SHA-256 with an explicit `SHA-256 check: MATCH` or `MISMATCH` (`Plugin SHA-256 check` for
MOS3), one automated verdict (`Ready for human review`, `Blocked`, or `No-ship`) decided only from
`plugin-health.html` and `behavioral-test-report.html`, and the findings that decide it. It then
lists the suggested fixes (ID, skill or file, evidence, severity, suggested change) and ends with a
"Pending human-review evidence" section.

## Step 3: locate Cowork output

If the Cowork task directory is synchronized locally, use its `output` folder directly:

```text
<OneDrive>\Documents\Cowork\Tasks\<task-name>\output\
```

If it is not synchronized, manually download the three HTML files to one local folder. Do not create
or download another ZIP; the frozen inbox ZIP is the authoritative evaluated artifact.

### Optional: watch and archive automatically

If Cowork Tasks is synchronized under the standard OneDrive path, start a watcher after launching
the task:

```powershell
npm run evaluation:watch -- --slug <plugin-slug>
```

The watcher reads the frozen run receipt, finds every Cowork task carrying the input ZIP's SHA-256
rather than relying on its display name, and searches those task folders for a stable report set
that explicitly affirms the evaluated ZIP matches the frozen digest. Stale, incomplete and
artifact-mismatch output is ignored. The matching set is passed to `evaluation:archive`, which also
copies the frozen test-data ZIP for a MOS3 candidate. Useful options are:

```powershell
npm run evaluation:watch -- `
  --slug <plugin-slug> `
  --version <artifact-version> `
  --tasks-root "C:\path\to\OneDrive\Documents\Cowork\Tasks" `
  --timeout-minutes 180
```

Multiple watchers and Cowork evaluations may run in parallel when they use different frozen
slug/version candidates. Each watcher matches only its recorded ZIP hash. Do not run
`evaluation:prepare` concurrently in the same worktree because preparation rebuilds the shared
`public/bundles/` directory. Prepare candidates serially, then evaluate and archive them in
parallel.

The watcher polls every 30 seconds and stops after 180 minutes by default. A timeout is not a
failure: run the same command again. Restarting is safe, because the watcher only reads until it
archives, and it refuses a receipt that is already archived. Stop watchers before restarting your
terminal or agent session and start them again afterwards, but never stop one after it reports
`All three reports are present and stable.` while it is archiving. If the submission version has
advanced since preparation, pass the frozen `--version`.

## Step 4: validate and archive the evidence

Run:

```powershell
npm run evaluation:archive -- `
  --slug <plugin-slug> `
  --source "<Cowork task output folder>"
```

If the submission version has advanced since the candidate was prepared, identify the frozen
version explicitly:

```powershell
npm run evaluation:archive -- `
  --slug <plugin-slug> `
  --version <artifact-version> `
  --source "<Cowork task output folder>"
```

To override the destination for one run:

```powershell
npm run evaluation:archive -- `
  --slug <plugin-slug> `
  --source "<Cowork task output folder>" `
  --sharepoint-root "C:\path\to\synced\Industry Templates"
```

The archive command:

1. Requires all three report filenames and rejects empty files.
2. Confirms `recommendations.html` identifies the frozen slug and version.
3. Confirms `recommendations.html` affirms the frozen ZIP's SHA-256. Any stated
   `SHA-256 check: MISMATCH` fails the archive.
4. Extracts the automated verdict from `recommendations.html`.
5. Copies only the three reports and frozen ZIP, plus the frozen test-data ZIP when the receipt
   records one (its SHA-256 is checked before and after the copy).
6. Recomputes the copied ZIP's SHA-256.
7. Refuses to overwrite an existing version folder.
8. Updates the ignored local run receipt with the verdict and archive location.

Matching and identity checks are keyed to the plugin ZIP's SHA-256.

Archive `Blocked` and `No-ship` runs as evidence. Do not publish them.

### Interpreting the verdict

The verdict is decided only from `plugin-health.html` and `behavioral-test-report.html`.

| Verdict | Meaning |
|---|---|
| `Ready for human review` | Every bar in the two Cowork reports is met. The only open items are evidence that the two-reviewer human review supplies (installed-runtime critical-path runs, human grader-calibration labels, human spot checks), listed under "Pending human-review evidence", not as blockers. |
| `Blocked` | Evidence is missing that human review cannot supply (for example a stage that did not run, or an ambiguous artifact identity). |
| `No-ship` | An observed defect, a below-floor score, or a safety or security blocker. |

`Ready for human review` is never a publish signal. The archive and watch commands still read a
bare legacy `Ready` in older reports as `Ready for human review`; any other `Ready for …` phrase
fails to parse. Under the current prompts, missing human-review evidence alone should not produce
`Blocked`; if it does, check the report's "Pending human-review evidence" section and raise it with
the owner. Behavioral item 2 requires a pass rate of 95% or more, and `WEAK` cases count as not
passing, so remediation must fix every `WEAK` case as well as every `FAIL`. See
[Reading a verdict](operator-runbook.md#reading-a-verdict) in the operator runbook for where to find
each finding in the reports.

## Step 5: complete the human gate

For a `Ready for human review` evaluation:

1. Two independent reviewers each run every prompt in the tracker. The critical-path prompts are
   the mandatory minimum the tracker must contain.
2. Each reviewer records results in the plugin's human-test tracker.
3. Reviewers investigate failures or discrepancies.
4. The accountable owner records the publication decision in the tracker: `Publish`,
   `Fix and re-evaluate` or `Do not publish`.

Only when the tracker's publish gate reads `PASS` and the owner decision is `Publish` should the
archived ZIP be copied to the plugin folder as the current versioned distributable. That copy must
remain byte-identical to the ZIP under `Evaluation/`. For a MOS3 candidate only the plugin ZIP is
promoted; the test-data ZIP stays in `Evaluation/` as evidence. See the
[Ready path](operator-runbook.md#ready-path-human-gate-and-promotion) for the other decisions.

## Failure and retry rules

- Missing or malformed reports: correct the Cowork output; do not bypass archive validation.
- `Blocked` or `No-ship`: fix the plugin, increment its artifact version, and prepare a new run.
- Hash mismatch: stop. Determine which ZIP Cowork evaluated; never substitute a rebuilt ZIP.
- Existing destination folder: do not overwrite it. Use the existing evidence or create a new
  artifact version.
- Formal Cowork rerun: the archive convention permits one run per artifact version. Preserve the
  earlier run, increment the artifact version, prepare a new frozen ZIP, and archive the rerun under
  that new version. Never silently replace the earlier reports.

## Workflow tests

Run the evaluation automation tests with:

```powershell
npm run test:evaluation
```

These tests cover argument parsing, HTML normalization, verdict extraction (including the legacy
`Ready` mapping and phrase ordering), both prompt templates and the report set, formatted SHA-256
matching, file hashing, and the check that a MOS3 version ships a regression runner. They also cover
MOS3 validation and packaging
(`scripts\mos3-package.test.ts`) and the test-data checks, freezing and ZIP
(`scripts\test-data.test.ts`).

## MOS3 package format and test data

A submission opts into the MOS3 Microsoft 365 app package (manifest schema 1.28) with
`"packageFormat": "mos3"` in `metadata.json`; without the field it builds the Claude plugin layout as
before. The importer (`npm run build`, or `npm run check:submissions` to validate without writing)
then requires a root `manifest.json`, `color.png` (192×192) and `outline.png` (32×32, white on
transparent), and one `skills\<name>\SKILL.md` per `agentSkills` entry. It fails if `.claude-plugin\`
remains or `bundleTests` is set. `public\bundles\<plugin-slug>.zip` holds `manifest.json`,
`color.png`, `outline.png` and `skills/**` at the ZIP root, with no wrapper folder. Everything else
in the submission folder (`metadata.json`, `README.md`, `CHANGELOG.md`, `listing-metadata.md` and
any root `contracts\`, `references\`, `config\` or `scripts\`) stays out of the ZIP, so each skill
must be self-contained. The importer also validates the 1.28 manifest (schema, GUID `id`,
"Microsoft Corporation" developer, field lengths, the four closing links in `description.full`,
`accentColor`, `agentSkills`), every skill's frontmatter (`metadata.icon` and `metadata.version`
required, description at most 1,024 characters), companion-file limits, symlinks and `../`
references that leave a skill folder. It warns when a description exceeds 800 characters or a body
exceeds 2,000 words. Quoted triggers and the "Do NOT use for" line are checked by hand: see
[hardening checklist H](plugin-hardening-checklist.md#h-mos3-and-partner-guide).

Test data for a MOS3 plugin lives outside the plugin, one folder per version:

```text
test-data/<industry-folder>/<plugin-slug>/<version>/
├── README.md
├── demo-data/
├── tests/          run_tests.py or test_engines.py, optional check_shared_copies.py and helpers
└── FROZEN.sha256   written by evaluation:prepare; commit it
```

`<industry-folder>` is the folder name used under `submissions\`. Runners take the plugin root as
`python tests/<runner> --plugin-root <dir>` or the `PLUGIN_ROOT` environment variable. The plugin
root is an extracted MOS3 ZIP or the submission folder; with neither set it defaults to
`<repo>\submissions\<industry-folder>\<plugin-slug>`. The data root is the runner's parent version
folder. Runners keep `--group` and `--list-groups` where they have them.

`npm run check:test-data` requires the current version folder for every MOS3 submission, with a
runner in `tests\`, `demo-data\` and `README.md`. Any version folder with `FROZEN.sha256` must match
it exactly, including no extra or missing files. Other unfrozen versions warn, and test data for a
slug with no submission fails. `FROZEN.sha256` lists `<sha256>  <relative/path>` sorted by path,
for every file except itself and build litter such as `__pycache__`.
