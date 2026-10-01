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
└── full-report.html
```

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

An automated `Ready` verdict is not a publication decision. Both reviewers run every prompt in the
tracker; the critical-path prompts are the mandatory minimum the tracker must contain.

## Prerequisites

1. Install Node.js 22 and run `npm install`.
2. Ensure the plugin's `metadata.json` and `.claude-plugin/plugin.json` use the same version.
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

1. Validates every submission.
2. Rebuilds all reproducible bundles.
3. Confirms the submission and plugin-manifest versions agree.
4. Copies the generated bundle into an immutable local run folder.
5. Records the SHA-256, Git commit, dirty-worktree state, artifact version, and Cowork task name.
6. Generates a ready-to-paste Cowork prompt.
7. Refuses to replace an existing candidate for the same plugin version.

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

## Step 2: run the Cowork task

This step is manual because Cowork does not support changing its task output directory from the
repository scripts.

1. Open Cowork.
2. Create a task using the exact `coworkTaskName` from `evaluation-run.json`.
3. Attach `<plugin-slug>.zip` from the frozen `evaluation-inbox` folder.
4. Do not attach the mutable copy under `public/bundles/`.
5. Attach or reference `Industry-Templates-Plugin-Testing-Strategy.docx`.
6. Paste the complete contents of `cowork-prompt.txt`.
7. Confirm the prompt requests exactly:
   - `plugin-health.html`
   - `behavioral-test-report.html`
   - `full-report.html`
8. Start the task and wait for it to finish. Runs typically take 1–3 hours.
9. Do not rename or edit the generated reports.

Always create a new Cowork task for each artifact version. Reusing a task from an earlier version
can save the new attachment as `<plugin-slug> (1).zip`, which the watcher never matches; can mix old
and new reports, because the filenames are fixed and only `full-report.html` is hash-checked; and
leaves the earlier verdict in the conversation, where it can bias the evaluator.

Resuming a stalled run of the same version in the same task is fine: type
`continue and produce the 3 reports`.

The Cowork task list can show a task as failed while the task page shows it still working. Trust
the task page and whether the task's output folder is still changing.

The full report must visibly state the plugin slug, artifact version, Cowork task/run label,
artifact SHA-256, per-skill scores and launch floors, behavioral and safety totals, security result,
unresolved-conflict count, blockers, and one automated verdict: `Ready`, `Blocked`, or `No-ship`.

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
artifact-mismatch output is ignored. The matching set is passed to `evaluation:archive`. Useful
options are:

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
2. Confirms `full-report.html` identifies the frozen slug and version.
3. Confirms the full report contains the frozen ZIP's SHA-256.
4. Extracts the automated verdict.
5. Copies only the three reports and frozen ZIP.
6. Recomputes the copied ZIP's SHA-256.
7. Refuses to overwrite an existing version folder.
8. Updates the ignored local run receipt with the verdict and archive location.

Archive `Blocked` and `No-ship` runs as evidence. Do not publish them.

### Interpreting the verdict

`Ready` means internal bar items 1–7 of the testing strategy are met and the human spot check
(item 8) is pending. `Blocked` means one or more items were missed without a guardrail, safety or
security breach; `No-ship` means such a breach was found. Behavioral item 2 requires a pass rate of
95% or more, and `WEAK` cases count as not passing, so remediation must fix every `WEAK` case as
well as every `FAIL`. See [Reading a verdict](operator-runbook.md#reading-a-verdict) in the operator
runbook for the full bar and where to find each finding in `full-report.html`.

## Step 5: complete the human gate

For a `Ready` evaluation:

1. Two independent reviewers each run every prompt in the tracker. The critical-path prompts are
   the mandatory minimum the tracker must contain.
2. Each reviewer records results in the plugin's human-test tracker.
3. Reviewers investigate failures or discrepancies.
4. The accountable owner records the publication decision in the tracker: `Publish`,
   `Fix and re-evaluate` or `Do not publish`.

Only when the tracker's publish gate reads `PASS` and the owner decision is `Publish` should the
archived ZIP be copied to the plugin folder as the current versioned distributable. That copy must
remain byte-identical to the ZIP under `Evaluation/`. See the
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

These tests cover argument parsing, HTML normalization, verdict extraction, formatted SHA-256
matching, and file hashing.
