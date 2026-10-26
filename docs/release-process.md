# Release process

This process follows the *Industry Templates Plugin Testing and Validation Strategy*
(`sharepoint\Industry-Templates-Plugin-Testing-Strategy.docx`), except that human testing is not
part of it (owner, 2026-10-23: "remove human testing from the process"; "Publish after Ready"):

1. Build the plugin.
2. Package it.
3. Run Cowork's built-in plugin evaluation.
4. Fix what the evaluation recommends, then repeat from step 2.
5. Owner Publish decision, after a Ready verdict.
6. Publish and file the evidence.

| Step | Who | Command |
|---|---|---|
| 1. Build the plugin | Contributor or agent | Follow [CONTRIBUTING.md](../CONTRIBUTING.md); `npm run check:submissions` |
| 2. Package | Operator, or the fix step after clean fixes | `npm run evaluation:prepare -- --slug <slug>` |
| 3. Evaluate in Cowork | Cowork (queue), or operator | Automatic from the queue folder; otherwise a new task with the ZIP and the prompt |
| 4. Archive, request the matrix (Ready) and fix | Watcher, then fix agent | `npm run evaluation:watch -- --slug <slug>` |
| 5. Publish decision | Owner | Record `Publish` in the plugin's deployment doc in SharePoint |
| 6. Publish | Owner | Promote the evaluated ZIP byte for byte |

Cowork evaluates the plugin by itself: it writes its own test cases from the skill descriptions.
The plugin's own `tests\` and `demo-data\` folders stay in the repository and are never sent to
Cowork. The only repository tests are the script unit tests (`npm run test:evaluation`), and CI runs
them.

Test policy (owner, 2026-10-15):

- **Plugin suites** hold only checks that came from a Cowork finding; checks from internal review
  (QA rounds, class sweeps, hardening, detector corpora, MOS3 layout) were deleted on 2026-10-15.
  A plugin with no Cowork-driven checks has no suite.
- **Cowork evaluation matrices are Cowork findings** (owner, 2026-10-22). The collected workbook
  and notes pair in `Evaluation Matrices\` counts like `recommendations.html`:
  - Matrix blockers (the notes' "Top blockers" and "Rows marked blocked") that a plugin change
    resolves are handled like required fixes, with a regression check named for the matrix and item.
  - Harness or environment blockers are reported to the owner, not fixed in the plugin.
  - Other matrix items are advisory and go to `BACKLOG.md`. See [AGENTS.md](../AGENTS.md).
- **Honest-empty outputs pass** (owner, 2026-10-22, confirming the decision every matrix's notes
  ask for). A row passes when its criterion calls for less output and the plugin produces it:
  withheld markers, declared gaps, verbatim script input errors with nothing written, refusals and
  holds. Two cases still fail: over-refusal on a happy-path row with complete inputs, and an empty
  output that declares no gap and quotes no error.
- **Packaging rules** in `scripts\mos3-package.ts` (`check:submissions`) stay.
- **Regression protection** stays: the script unit tests, the packaging rules and the plugin suites.
  The fix agent runs the plugin's suite before and after applying Cowork fixes (owner: "run the
  suites with the fix agent"); CI and `evaluation:prepare` do not run plugin suites.
  Each blocker or required fix adds at least one regression check named for its fix ID (owner,
  2026-10-15: "regression checks should be added for each blocker or required fix").

## One-time setup

1. Install Node.js 22 and run `npm install`. Install Python 3 if you run plugin engines locally.
2. Sync the Industry Templates SharePoint library with OneDrive, then link it:
   `npm run sharepoint:link`. Then run `npm run sharepoint:doctor`, which must end with
   "SharePoint sync: ready.". See [SharePoint sync](sharepoint-sync.md).
3. Keep Cowork's task folder synced at `<OneDrive>\Documents\Cowork\Tasks`. If it is somewhere
   else, pass `--tasks-root`. For automatic evaluation, keep Cowork's queue folder synced at
   `<OneDrive>\Cowork Plugin Evals\` (its `eval-ledger.md` describes the queue); otherwise pass
   `--queue-root`. OneDrive must be running for either folder to sync.
4. Install the GitHub Copilot CLI (`copilot`) and sign in. The fix step runs it.

## Where things live

| Location | Contents | In git? |
|---|---|---|
| `submissions\<industry>\<slug>\` | Plugin source, `metadata.json`, `README.md`, `CHANGELOG.md` and `BACKLOG.md` (advisory items) | Yes |
| `submissions\<industry>\<slug>\tests\`, `demo-data\` | The plugin's own tests and demo data, never bundled | Yes |
| `evaluation-inbox\<slug>\<version>\` | The plugin ZIP, the `evaluation-run.json` receipt, `cowork-prompt.txt` and `fix-brief.md` | No (local) |
| `<OneDrive>\Documents\Cowork\Tasks\<task>\` | Cowork's `input\` and `output\` | No |
| `<OneDrive>\Cowork Plugin Evals\` | Cowork's evaluation queue: `1 - To evaluate`, `2 - In progress`, `3 - Evaluated\<slug>\v<version> - <timestamp>\`, `4 - Needs attention` and `eval-ledger.md` | No |
| `<OneDrive>\Cowork Plugin Evals\4 - Matrices\` | Matrix requests in `1 - Queue\` (dropped by the archive step after a Ready verdict), requests Cowork has taken in `3 - Processed\` and completed workbook/notes pairs in `2 - Built\` | No |
| `sharepoint\<Industry>\<slug>\Evaluation\<version>\` | The archived ZIP and the three reports | No (SharePoint) |
| `<SharePoint plugin folder>\Evaluation Matrices\` | Collected matrix workbooks and build notes, with their original versioned/timestamped names | No (SharePoint) |
| `sharepoint\<Industry>\<slug>\` | The deployment doc (with the owner's Publish decision), the demo-data ZIP and promoted ZIPs | No (SharePoint) |

Professional Services Waves 1 and 2 use the Retail library layout instead: the plugin folder is
`sharepoint\Professional Services\Wave <n>\<Title Case Slug>\`, archives go to `Evaluation\v<version>\`,
and the promoted ZIP is `<slug>-cowork.zip`. `SHAREPOINT_WAVES` in `scripts\evaluation-workflow.ts`
lists the plugins that use it; the archive script follows it automatically. The plugin folder also
holds a loose `sample-test-prompts.csv` copied from the demo-data ZIP (Step 5). After promotion, its
`MOS Package\` folder holds the derived manifest-1.28 package (Step 6). Human test tracker workbooks
already in SharePoint are kept as history and are no longer updated.

## Collect evaluation matrices

For passing evaluations, Cowork has a separate watcher that consumes matrix requests from
`<OneDrive>\Cowork Plugin Evals\4 - Matrices\1 - Queue\`, moves each request to `3 - Processed\`
and writes completed outputs to `4 - Matrices\2 - Built\`.

**Requesting a matrix.** When `evaluation:archive` (and so `evaluation:watch`) archives a
**Ready** verdict, it copies the frozen, hash-verified evaluated ZIP to
`4 - Matrices\1 - Queue\<slug>-v<version>.zip`. Other verdicts request nothing. The request:

- never overwrites: it stops, with nothing written, if `1 - Queue\` or `3 - Processed\` already
  holds a different ZIP of that name;
- is skipped when the same ZIP is already queued or processed, or `2 - Built\<slug>\v<version> - *`
  already exists;
- is staged in `4 - Matrices\` and hard-linked into `1 - Queue\` (which fails rather than
  replaces), so Cowork never sees a partial ZIP;
- is recorded as `matrixRequest` (or `matrixRequestError`, including an unavailable queue folder)
  in the run's `evaluation-run.json`;
- never undoes or fails the archive. If it fails, or the queue folder is unavailable, the
  archive step prints the command to request it later.

`--no-matrix` on `evaluation:archive` or `evaluation:watch` turns the request off. To request one
by hand for an archived Ready run:

```powershell
npm run evaluation:request-matrix -- --slug <slug> --version <version>            # add --dry-run to preview
```

The collector below watches **Built**, not Queue; it does not build matrices and does not change
evaluation or publish decisions.

```powershell
npm run evaluation:watch-matrices
npm run evaluation:watch-matrices -- --once --dry-run
npm run evaluation:watch-matrices -- --once
```

Each completed build is a matching pair in the same folder (nested folders under Built are also
scanned):

| File | Name |
|---|---|
| Workbook | `<slug>-v<version>-eval-matrix-YYYY-MM-DD-HHMM.xlsx` |
| Notes | `<slug>-v<version>-matrix-notes-YYYY-MM-DD-HHMM.md` |

Example: `time-expense-narrative-compliance-v1.0.13-eval-matrix-2026-10-22-1015.xlsx` and
`time-expense-narrative-compliance-v1.0.13-matrix-notes-2026-10-22-1015.md`.

The collector:

- requires both files with the same slug, version and timestamp, non-empty and unchanged across
  observations for at least 15 seconds; polls every 30 seconds by default;
- resolves the slug from repository submission metadata and reuses `sharepointPluginDir` routing
  (including Professional Services Waves 1 and 2); the existing plugin folder must be present;
- copies both files, preserving their names, into `<SharePoint plugin folder>\Evaluation Matrices\`
  and verifies SHA-256; Built originals and the evaluation archives remain untouched;
- skips byte-identical destination files, including after a restart; preflights both destinations
  and refuses differing files instead of replacing them;
- records each collected pair (source path, SHA-256 and destination) in the gitignored
  `evaluation-inbox\matrix-collected.json` and skips recorded pairs whose SharePoint copies still
  exist without comparing them again, because SharePoint rewrites uploaded `.xlsx` files with its
  own metadata. A deleted SharePoint copy is copied again; a changed Built original is a new source
  and still meets the no-overwrite check;
- ignores hidden, Office lock and partial-download files; reports unrecognized filenames, unknown
  plugins, missing plugin folders and copy conflicts explicitly and retries on subsequent polls.
  Other valid pairs still get collected. Incomplete pairs remain pending; `--once` exits nonzero
  if anything is still pending or failed.

Leave the command running to collect future builds; `Ctrl+C` stops it. OneDrive must stay running
for changes to sync. Options:

| Option | Purpose |
|---|---|
| `--once` | Scan current outputs, wait once for stability if needed, then exit |
| `--dry-run` | Report destinations without writing files or folders |
| `--queue-root <path>` | Override `OneDriveCommercial` / `OneDrive` + `Cowork Plugin Evals` |
| `--built-root <path>` | Watch another Built folder directly; cannot combine with `--queue-root` |
| `--sharepoint-root <path>` | Override the usual environment-variable / `sharepoint\` link resolution |
| `--poll-seconds <n>` | Positive polling interval; default 30 |
| `--stable-seconds <n>` | Positive unchanged-content interval; default 15 |
| `--ledger <path>` | Collected-pair record; default `evaluation-inbox\matrix-collected.json` |

A timestamped new build uses new filenames; resolve a differing-file conflict with the owner
rather than deleting or overwriting shared evidence.

## Step 1: build the plugin

Build or change the plugin as [CONTRIBUTING.md](../CONTRIBUTING.md) describes, then run
`npm run check:submissions`. Bump the version in `metadata.json` and in the plugin manifest for
every change you send to Cowork, and only then: a re-run of an unchanged plugin keeps its version
(Step 2, `--requeue`). Engine version labels (the `ENGINE_VERSION`-style constants the
scripts stamp into their outputs, not the shared steering detector's `__version__`) match the plugin
version in every release; regenerate the `demo-data` expected outputs that record them.

## Step 2: package

```powershell
npm run evaluation:prepare -- --slug <slug>
```

This command:

1. validates every submission and builds the bundles;
2. copies `public\bundles\<slug>.zip` to `evaluation-inbox\<slug>\<version>\`;
3. records its SHA-256 in `evaluation-run.json`;
4. writes `cowork-prompt.txt`, built from `docs\evaluation\cowork-evaluation-prompt[-mos3].txt`;
5. if the queue folder `<OneDrive>\Cowork Plugin Evals\1 - To evaluate` exists, drops the pair
   `<slug>-v<version>.zip` and `<slug>-v<version>-prompt.md` there and records it as
   `queueSubmission` in `evaluation-run.json`. The prompt is `cowork-prompt.txt` with a header that
   names the queued ZIP. Pass `--no-queue` to skip the queue and evaluate manually (Step 3), or
   `--queue-root` to use another folder; the two cannot be combined.

It runs no plugin tests and no external package validator; Cowork's evaluation is the package check. A version can be prepared only once. The version is bumped only after fixes (Step 4); to re-send an unchanged version whose queue run did not complete, use `--requeue`:

```powershell
npm run evaluation:prepare -- --slug <slug> --requeue
```

`--requeue` builds nothing and follows Cowork's requeue convention: it moves this version's ZIP and
prompt from `4 - Needs attention` back into `1 - To evaluate`, unchanged. A file that is not in
`4 - Needs attention` is re-created from the inbox: the ZIP after its SHA-256 is checked against the
receipt, and the prompt from `cowork-prompt.txt`, which gives the same prompt as the first drop.
It refuses if the ZIP in `4 - Needs attention` has a different SHA-256. Cowork's note and any other
entries for this version move to `evaluation-inbox\<slug>\<version>\needs-attention\<timestamp>\`,
so the watcher does not stop on the earlier failure, and the earlier submission is recorded in
`queueHistory`. It refuses if the pair is still queued or in progress, if Cowork has already
evaluated it (run the watcher instead), or if the version is already archived. `--requeue` is for
the queue only; on the manual path, re-send an unchanged version by starting a new Cowork task with
the same inbox ZIP and `cowork-prompt.txt` (Step 3).

## Step 3: evaluate in Cowork

**Queued (default when the queue folder exists).** Cowork picks up the pair from `1 - To evaluate`,
moves it to `2 - In progress`, and files the pair and its reports in
`3 - Evaluated\<slug>\v<version> - <timestamp>\`. If it cannot complete the run (missing pair,
SHA-256 mismatch or a failed run), it moves the pair to `4 - Needs attention` with a note. Read
the note: if the plugin needs no change, re-send it with `--requeue` (Step 2); only a plugin fix
means a new version.
`eval-ledger.md` records every submission; a ZIP whose SHA-256 is already there is skipped.
Nothing else to do; run the watcher (Step 4).

**Manual (no queue, or `--no-queue`):**

1. Create a new Cowork task named exactly as `coworkTaskName` in `evaluation-run.json`
   (`evaluate-<slug>-v<version>-<date>`).
2. Attach only the plugin ZIP from `evaluation-inbox\`, never the one in `public\bundles\`.
3. Paste `cowork-prompt.txt` unchanged.

Cowork computes the ZIP's SHA-256, runs its built-in evaluation and saves three reports:

- `plugin-health.html`
- `behavioral-test-report.html`
- `recommendations.html`, which holds the verdict and a table of suggested fixes
  (`ID | Severity | Skill or file | Evidence | Suggested change`)

Rules:

- **One new task per run.** A reused task can save the ZIP as `<slug> (1).zip` and mix old
  and new reports. If a run fails and the plugin needs no change, start a new task with the same
  inbox ZIP and prompt; the version stays the same.
- **Runs take 1–3 hours; leave them alone.** If a run stalls, type
  `continue and produce the 3 reports` in the same task. The task list can show "failed" while the
  run is still working; check the task page and the output folder.
- **Do not ask Cowork to fix the plugin, and do not edit the reports.**

## Step 4: archive and fix

```powershell
npm run evaluation:watch -- --slug <slug>       # --no-fix: only archive; --no-prepare: fix but do not prepare; --no-matrix: do not request a matrix; --model <id>: agent model
```

The watcher:

1. finds the Cowork run whose ZIP has the recorded SHA-256: a task's `input\<slug>.zip`, or a
   queue folder `3 - Evaluated\<slug>\v<version> - *\<slug>-v<version>.zip`. It stops with the
   paths if Cowork moved the pair to `4 - Needs attention`. Timestamped report names are accepted;
2. waits until the three reports are present and stable;
3. **archives** them with the ZIP to `sharepoint\<Industry>\<slug>\Evaluation\<version>\` (Retail
   layout: `<Industry>\Wave <n>\<Title Case Slug>\Evaluation\v<version>\`)
   (`evaluation:archive`). `recommendations.html` must state the slug, the version,
   `SHA-256 check: MATCH` and the verdict, or nothing is archived;
4. on a **Ready** verdict, **requests the evaluation matrix** by copying the evaluated ZIP into
   Cowork's matrix queue ([Requesting a matrix](#collect-evaluation-matrices));
5. runs the **fix step** (`evaluation:fix`).

The fix step:

1. reads the suggested-fixes table in the archived `recommendations.html`;
2. appends **advisory** items to `submissions\<industry>\<slug>\BACKLOG.md`;
3. writes **blocker** and **required** items to `evaluation-inbox\<slug>\<version>\fix-brief.md`;
4. starts a non-interactive Copilot CLI agent on the brief. The agent may not push. It:
   - applies the fixes in the strategy's fix order;
   - bumps the patch version (including `listing-metadata.md`) and adds a CHANGELOG entry;
   - sets the engine version labels to the new version and regenerates the `demo-data` expected
     outputs that record them (labels only); if an existing check asserts the old label, it leaves
     the labels and reports the conflict;
   - runs the plugin's regression suite, if it has one (the commands in its `tests\README.md`),
     before and after the fixes: every check that passed before must still pass, and no existing
     check may be relaxed, except for the exact changes authorized in the one-time owner
     exceptions below; any other conflicting fix is reverted, skipped and reported;
   - runs `check:submissions` and `test:evaluation`;
   - adds at least one regression check per blocker or required fix, named for the fix ID, that
     fails before the fix and passes after (added only; existing checks are never changed except
     for the exact changes authorized in the one-time owner exceptions below);
   - otherwise leaves `tests\` and `demo-data\` alone unless a fix requires an edit, and lists any
     such edit;
   - commits locally, writes `evaluation-inbox\<slug>\<version>\fix-result.json` (each fix
     applied or skipped, conflicts, checks that already failed, the commit) and stops;
5. checks the agent's work. If every blocker and required fix was applied, with no conflicts and
   no pre-existing failing checks, the plugin is at the next version, and the commit titled
   `<slug> <next version>: …` changed only plugin files and left none uncommitted, it **prepares
   the next version** (Step 2) the same way as this one: queued if this run was queued, otherwise
   manual. Otherwise it stops with the reasons (`fixStatus: needs-attention`) and prepares nothing.
   `--no-prepare` (on the watcher or the fix step) turns the automatic prepare off.

If there are no blocker or required items, the fix step does nothing and the plugin goes to step 5.

**You then:**

1. Review the agent's commit: `git --no-pager log -1 --stat`, then `git --no-pager show`. Amend or
   revert it as needed. A queued next version is already with Cowork; if you change the commit,
   tell the owner before re-sending, because the evaluated ZIP no longer matches.
2. If the fix step stopped for attention, resolve the reasons, then go back to step 2 for the new
   version. Otherwise run the watcher for the new version (a manual next version also needs its
   Cowork task, Step 3). Each fix-and-re-run cycle is a new version: a new queue pair, or a new
   Cowork task when you are not using the queue.

**Running the steps by hand:**

- `npm run evaluation:archive -- --slug <slug> --source "<folder>"` archives a run. `<folder>` is
  the queue run folder (`3 - Evaluated\<slug>\v<version> - <timestamp>`) or a task's `output\`.
  Timestamped report names are accepted. A Ready verdict also requests the matrix (`--no-matrix`
  turns this off; `--queue-root` points at another Cowork queue folder).
- `npm run evaluation:request-matrix -- --slug <slug> --version <version>` requests the matrix for
  an archived Ready run whose automatic request was skipped or failed.
- `npm run evaluation:fix -- --slug <slug>` runs the fix step on an archived run. Add `--dry-run`
  to write the brief and the backlog without starting the agent.

**Verdicts in `recommendations.html`:**

| Verdict | Meaning | Next |
|---|---|---|
| Ready | Every bar in the strategy is met | The matrix is requested automatically; then step 5. This is not a publish signal |
| No-ship | There is at least one blocker or required fix | The fix step runs; then step 2 for the new version |
| Blocked | The evaluation could not complete, or the ZIP identity is unclear | Find out why. If the plugin must change, fix it and re-run as a new version. If not, the version stays; re-running an already archived version is not supported, so tell the owner |

The strategy's bar, which the prompt states:

- every skill at or above its launch floor;
- a behavioral pass rate of at least 95%, with no guardrail failures;
- output quality of at least 3.5/5;
- trigger consistency of 3/3;
- negative cases stay out;
- the security scan passes with no medium or high findings;
- the trust and safety gate passes.

A guardrail or safety failure is always a stop.

The prompt follows Cowork's queue template (`submission-prompt-template.md`, 2026-10-23), except
that it keeps the three fixed report filenames. From that template it takes:

- **The prompt wins.** Where the strategy document and the prompt disagree, the prompt wins: the
  human spot check and the SharePoint evidence location are not part of this release process.
- **Regression step.** When Cowork's intake supplies a regression baseline (an earlier evaluated
  version), each report adds a "Regression vs baseline" section, and `recommendations.html` names
  the baseline or says "No regression baseline". A bar measure that met the bar in the baseline
  and misses it now is a required fix.

The intake may still add a start-time stamp to the report names; the archive accepts either form.

Reports archived between 2026-10-12 and 2026-10-23 state `Ready for human review`. The archive
script reads that label as `Ready`, and the wave logs keep it as recorded.

### One-time owner exception for T&E R-03

**Owner approval: 2026-10-16.** This, the [1.0.13 R-02 exception](#one-time-owner-exception-for-te-1013-r-02)
and the [human-testing removal exception](#one-time-owner-exception-removing-human-testing) are the
only exceptions to the existing-check restrictions in this process and `AGENTS.md`:

- **Plugin and release:** `time-expense-narrative-compliance`, implementation release **1.0.12**.
- **Finding:** required **R-03 (ND-01)** from the archived **1.0.10** Cowork
  `recommendations.html`, not the unrelated R-03 from an earlier evaluation.
- **Exact scope:** replace the expectation inside `tests\run_tests.py`, `te110_tests`, in
  `1.0.10 R-01 ND-01: noun purposes use regarding, never an ungrammatical to clause` that requires
  `" regarding internal staffing check-in"` and rejects `" to internal staffing check-in"`.
  Replace that literal-bound check with rule-based grammar and grounding assertions. Do not
  delete its regression protection or change any other existing check or expectation.
- **Coverage:** retain rejection of ungrammatical `to` plus a noun-phrase purpose and recognition
  of evidence-grounded purposes. Permit a grammatical article in a retained `regarding` clause,
  or omission of a purpose clause only when it repeats the subject or title. Existing verb-purpose,
  invented-purpose, calendar-title casing and required-element checks must pass unchanged.
- **R-03 evidence:** add fix-ID-labelled regressions for repeated verb/noun wording, redundant
  purpose clauses, missing articles and duplicate participant prepositions. Show that the new
  checks fail on the unfixed 1.0.11 engine and pass on the fixed engine; run the entire plugin suite
  before and after, and report the one replaced check separately from unchanged checks.

The exception permits this test replacement only as part of the R-03 fix. It does not permit
unrelated test changes, weaker billing or safety rules, lower launch bars, packaging or publishing
without their existing gates. Version labels, copied-engine consistency, repository checks and
the next Cowork evaluation remain required. Approval alone does not implement the replacement or
engine fix; their implementation and evaluation status are recorded in the Wave 1 log.

### One-time owner exception for T&E 1.0.13 R-02

**Owner approval: 2026-10-16.**

- **Plugin and release:** `time-expense-narrative-compliance`, implementation release **1.0.13**.
- **Finding:** required **R-02** from the archived **1.0.12** Cowork `recommendations.html`: a
  deliverable clause that repeats the subject (and the same repeat between subject and purpose).
- **Exact scope:** regenerate `demo-data\scenario-b-drama\expected\drafted.json`, `coded.json` and
  `governed.json`. The only permitted non-label difference is in the TE-B-001 suggested rewrite for
  B-DOC-001. It drops " for the Integration Design" (11 words). Its status becomes
  `needs_review_insufficient_detail`, with the engine's 12-word (#1.1) review reason, and these values
  carry through to the downstream outputs.
- **Check change:** in `tests\run_tests.py`, the check `per-activity rewrites on a multi-link entry
  are needs_review and name what they leave out` changes its status condition from
  `r["status"] == "needs_review"` to `r["status"].startswith("needs_review")`. Its "only" reason
  and `covered_activity_ids` conditions stay unchanged. Report this check separately from the
  unchanged checks. Every other golden, check and expectation stays unchanged.
- **Evidence:** add R-02 regressions named for the fix ID that fail on the unfixed 1.0.12 engine
  and pass after. Run the entire plugin suite before and after. Report the golden diff and show that
  it contains nothing outside the scope above.

This exception permits only these golden updates and this check change, as part of the R-02 fix. It does not permit
padding a draft to reach 12 words, unrelated test changes, weaker billing or safety rules, or
packaging or publishing without their existing gates.

### One-time owner exception: removing human testing

**Owner approval: 2026-10-23** ("remove human testing from the process"; "Publish after Ready").

- **Scope:** the script unit tests in `scripts\evaluation-workflow.test.ts` only. The passing
  verdict is renamed from `Ready for human review` to `Ready`, so these expectations change:
  - `extractVerdict normalizes supported Cowork verdicts` and `extractVerdict reads the new phrase
    whole and never as a bare Ready`: the expected value `"Ready for human review"` becomes
    `"Ready"`, and the expected error lists `Ready, Blocked, or No-ship`. Every input stays,
    including the archived `Ready for human review` phrasings, and `Ready for publication` must
    still throw.
  - `verdictGuidance never treats Ready as a publish signal` (formerly `... Ready for human
    review ...`): the expected Ready guidance names the owner's Publish decision instead of two
    testers and the tracker, and the Blocked guidance no longer mentions human-review evidence
    but must still tell the operator to raise it with the owner before remediating.
  - The Cowork prompt check expects `exactly one of: Ready, Blocked, or No-ship`; it still requires
    `not a publish signal`.
- **Not permitted:** any change to plugin suites, goldens or any other check, weaker guardrails, or
  publishing without the owner's recorded Publish decision. Ready is still never a publish signal.

## Step 5: owner Publish decision

Do this after a `Ready` verdict. Human testing is not part of the process (owner, 2026-10-23), so
no testers or tracker are involved. Publication still needs the owner's explicit decision; never
infer it from the verdict.

1. Create `PLUGIN-DETAILS-AND-DEPLOYMENT.md` in the plugin folder (`sharepoint\<Industry>\<slug>\`,
   or the Retail-layout folder above) from the
   [deployment-doc template](templates/plugin-details-and-deployment.md), or refresh the existing
   one for this version. Record the evaluated SHA-256 in it.
2. Put the demo data next to it, zipped. The plugin ZIP holds no demo data or tests, so people
   trying the plugin get them from `<slug>-demo-data-v<version>.zip` in the plugin folder: `demo-data\`,
   `tests\sample-test-prompts.csv` and a short `README.md` naming the evaluated ZIP's SHA-256.
   Build it from the commit the evaluated ZIP came from (or a later commit where both folders are
   unchanged), never from a working tree. The one exception is a correction to
   `tests\sample-test-prompts.csv` alone, which is never packaged or read by a check: commit it,
   rebuild from that commit and say what changed in the README. Any other change to `demo-data\`
   or `tests\` waits for the next version.

   ```powershell
   git -c core.autocrlf=false archive --format=zip -o <slug>-demo-data-v<version>.zip `
     --add-file=<README.md> HEAD:submissions/<industry>/<slug> demo-data tests/sample-test-prompts.csv
   ```

   `core.autocrlf=false` keeps the files byte-identical to the repository (LF); Git for Windows
   sets it to `true` system-wide, which makes `git archive` write CRLF.

   These files are attached in people's own Cowork chats; they are never sent to the Cowork
   evaluation.

   In the Retail layout, also copy that ZIP's `tests/sample-test-prompts.csv` loose into the plugin
   folder as `sample-test-prompts.csv`, byte for byte, as Retail does. Write it from the ZIP, not
   the working tree, so it matches the published version's demo data. Keep its columns as they are:
   some plugin suites read them.
3. The owner records the decision in the deployment doc's **Owner decision** field: `Publish`
   with the date and the evaluated SHA-256, or `Hold` with the reason. Only the owner writes it.
4. Promote (Step 6) only when that field reads `Publish` for this exact version and SHA-256.

## Step 6: publish and file the evidence

Promote the evaluated ZIP byte for byte. Never rebuild it.

```powershell
$dir = "sharepoint\<Industry>\<slug>"
Copy-Item "$dir\Evaluation\<version>\<slug>.zip" "$dir\<slug>-plugin-v<version>.zip"
Get-FileHash "$dir\Evaluation\<version>\<slug>.zip", "$dir\<slug>-plugin-v<version>.zip" -Algorithm SHA256
```

For a plugin in the Retail layout (Professional Services Waves 1 and 2), the target is the latest
distributable `<slug>-cowork.zip`:

```powershell
$dir = "sharepoint\Professional Services\Wave <n>\<Title Case Slug>"
Copy-Item "$dir\Evaluation\v<version>\<slug>.zip" "$dir\<slug>-cowork.zip"
Get-FileHash "$dir\Evaluation\v<version>\<slug>.zip", "$dir\<slug>-cowork.zip" -Algorithm SHA256
```

Both hashes must equal `artifactSha256` in the receipt. For a MOS3 plugin in the Retail layout, then
build the manifest-1.28 MOS package from the same evaluated ZIP:

```powershell
npm run mos:build -- --slug <slug> --version <version>
```

It writes `<plugin folder>\MOS Package\<slug>-mos3-v<version>.zip`, a `README.md` that proves only
`manifest.json` changed (`$schema`, `manifestVersion` 1.28, `packageName` removed) and that the
manifest passes the v1.28 schema, and an extracted `skills\`. It refuses unless `<slug>-cowork.zip`
is byte-identical to the evaluated ZIP, and it never deletes or overwrites a different file. Use
`--out-dir <folder>` for a dry run outside SharePoint. Cowork evaluates the devPreview package only
([owner decision](professional-services/wave-1.md#owner-decision-derived-manifest-128-mos-package-2026-10-16)).

Then update the status in
`sharepoint\<Industry>\README.md` and in the wave log (for example
`docs\professional-services\wave-1.md`). Keep failed runs: every archived version stays in
`Evaluation\`.

## What is public and what stays in SharePoint

This repository is public; the SharePoint library is not.

| Public (repository) | SharePoint only |
|---|---|
| Plugin source, versions, commits and ZIP SHA-256s | The Cowork HTML reports |
| Automated verdicts and headline figures | The testing-strategy document; scenario and CRM evidence |
| Summaries, in your own words, of findings about the plugin's own synthetic behaviour | Owner decision records (and historical tracker results) |
| Cowork task names | Deployment docs and library URLs |

Never copy report text or internal URLs into the repository, a commit message or a bundle.

**SharePoint write rules**

- Write only evaluation archives and MOS packages (through the scripts) and documents the owner asks for.
- Never delete, rename or overwrite other people's files.
- Never delete recursively through the link.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `no SharePoint root configured`, `plain local folder` or `broken link` | `npm run sharepoint:doctor`, then `npm run sharepoint:link` |
| `an evaluation candidate already exists` | If the plugin changed (fixes), bump the version. If not, re-send it with `--requeue`. Never delete the inbox folder to retry |
| `version mismatch: metadata …, manifest …` | Make `metadata.json` and the manifest agree |
| The watcher never logs `Matched Cowork task` | Check `<task>\input\`: the wrong ZIP was attached, or the task has not synced. Start a new task with the inbox ZIP |
| Queued pair stays in `1 - To evaluate` | Check that OneDrive is running and Cowork's queue watcher is on; read `eval-ledger.md`. A ZIP with an already-logged SHA-256 is skipped as a duplicate |
| `Cowork moved … to "4 - Needs attention"` | Read the note next to the pair and `eval-ledger.md`. A SHA-256 mismatch means the handoff broke: stop and investigate. Sync gaps and failed runs: `npm run evaluation:prepare -- --slug <slug> --requeue`, same version. A plugin defect: fix it, bump the version and prepare again |
| `already queued for Cowork` | The pair is still in `1 - To evaluate` or `2 - In progress`. Wait for Cowork, or remove the stale pair after checking the ledger |
| `do not affirm the matching version/hash` | Stale reports, or the report lacks `SHA-256 check: MATCH`. Ask Cowork, in the same task, to add the missing lines |
| `SHA-256 check: MISMATCH` | Stop. Cowork evaluated a different file |
| The watcher times out | Restart it. It never archives twice |
| `no suggested-fixes table` | `recommendations.html` lacks the fixes table. Ask Cowork, in the same task, to add it, then run `npm run evaluation:fix -- --slug <slug> --report "<task>\output\recommendations.html"` |
| The fix agent failed | Read `fix-brief.md`, fix by hand or rerun `npm run evaluation:fix -- --slug <slug>` |
| `needs the owner's attention before it is prepared` | Read the listed reasons and `fix-result.json`. Resolve them (an existing-check conflict needs an owner decision), then `npm run evaluation:prepare -- --slug <slug>` |
| A `.<version>-<pid>.tmp` folder is left under `Evaluation\` | An archive was interrupted before its rename. Make sure no watcher or archive is running, delete only that one folder, then archive again |
| `evaluation archive already exists` but the receipt says `prepared` | The rename finished but the receipt was not updated. Check that the folder holds the ZIP (with the matching hash) and the three reports, then tell the owner |
