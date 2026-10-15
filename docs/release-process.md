# Release process

This process follows the *Industry Templates Plugin Testing and Validation Strategy*
(`sharepoint\Industry-Templates-Plugin-Testing-Strategy.docx`):

1. Build the plugin.
2. Package it.
3. Run Cowork's built-in plugin evaluation.
4. Fix what the evaluation recommends, then repeat from step 2.
5. Human spot check.
6. Publish and file the evidence.

| Step | Who | Command |
|---|---|---|
| 1. Build the plugin | Contributor or agent | Follow [CONTRIBUTING.md](../CONTRIBUTING.md); `npm run check:submissions` |
| 2. Package | Operator | `npm run evaluation:prepare -- --slug <slug>` |
| 3. Evaluate in Cowork | Operator, in Cowork | New task, attach the ZIP, paste the prompt |
| 4. Archive and fix | Watcher, then fix agent | `npm run evaluation:watch -- --slug <slug>` |
| 5. Human spot check | Two testers | Tracker workbook in SharePoint |
| 6. Publish | Owner | Promote the evaluated ZIP byte for byte |

Cowork evaluates the plugin by itself: it writes its own test cases from the skill descriptions.
The plugin's own `tests\` and `demo-data\` folders stay in the repository and are never sent to
Cowork. The only repository tests are the script unit tests (`npm run test:evaluation`), and CI runs
them.

Test policy (owner, 2026-10-15):

- **Plugin suites** keep their existing checks. New checks are added only in response to a Cowork
  finding, never from internal review.
- **Packaging rules** in `scripts\mos3-package.ts` (`check:submissions`) stay.
- **Regression protection** stays: the script unit tests, the packaging rules and the plugin suites.

## One-time setup

1. Install Node.js 22 and run `npm install`. Install Python 3 if you run plugin engines locally.
2. Sync the Industry Templates SharePoint library with OneDrive, then link it:
   `npm run sharepoint:link`. Then run `npm run sharepoint:doctor`, which must end with
   "SharePoint sync: ready.". See [SharePoint sync](sharepoint-sync.md).
3. Keep Cowork's task folder synced at `<OneDrive>\Documents\Cowork\Tasks`. If it is somewhere
   else, pass `--tasks-root`.
4. Install the GitHub Copilot CLI (`copilot`) and sign in. The fix step runs it.

## Where things live

| Location | Contents | In git? |
|---|---|---|
| `submissions\<industry>\<slug>\` | Plugin source, `metadata.json`, `README.md`, `CHANGELOG.md` and `BACKLOG.md` (advisory items) | Yes |
| `submissions\<industry>\<slug>\tests\`, `demo-data\` | The plugin's own tests and demo data, never bundled | Yes |
| `evaluation-inbox\<slug>\<version>\` | The plugin ZIP, the `evaluation-run.json` receipt, `cowork-prompt.txt` and `fix-brief.md` | No (local) |
| `<OneDrive>\Documents\Cowork\Tasks\<task>\` | Cowork's `input\` and `output\` | No |
| `sharepoint\<Industry>\<slug>\Evaluation\<version>\` | The archived ZIP and the three reports | No (SharePoint) |
| `sharepoint\<Industry>\<slug>\` | The deployment doc, the tracker workbook and promoted ZIPs | No (SharePoint) |

## Step 1: build the plugin

Build or change the plugin as [CONTRIBUTING.md](../CONTRIBUTING.md) describes, then run
`npm run check:submissions`. Bump the version in `metadata.json` and in the plugin manifest for
every change you send to Cowork.

## Step 2: package

```powershell
npm run evaluation:prepare -- --slug <slug>
```

This command:

1. validates every submission and builds the bundles;
2. copies `public\bundles\<slug>.zip` to `evaluation-inbox\<slug>\<version>\`;
3. records its SHA-256 in `evaluation-run.json`;
4. writes `cowork-prompt.txt`, built from `docs\evaluation\cowork-evaluation-prompt[-mos3].txt`.

It runs no plugin tests and no external package validator; Cowork's evaluation is the package check. A version can be prepared only once; for a new run, bump the version.

## Step 3: evaluate in Cowork

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

- **One new task per version.** A reused task can save the ZIP as `<slug> (1).zip` and mix old
  and new reports.
- **Runs take 1–3 hours; leave them alone.** If a run stalls, type
  `continue and produce the 3 reports` in the same task. The task list can show "failed" while the
  run is still working; check the task page and the output folder.
- **Do not ask Cowork to fix the plugin, and do not edit the reports.**

## Step 4: archive and fix

```powershell
npm run evaluation:watch -- --slug <slug>       # add --no-fix to only archive, --model <id> for the agent
```

The watcher:

1. finds the Cowork task whose `input\<slug>.zip` has the recorded SHA-256;
2. waits until the three reports are present and stable;
3. **archives** them with the ZIP to `sharepoint\<Industry>\<slug>\Evaluation\<version>\`
   (`evaluation:archive`). `recommendations.html` must state the slug, the version,
   `SHA-256 check: MATCH` and the verdict, or nothing is archived;
4. runs the **fix step** (`evaluation:fix`).

The fix step:

1. reads the suggested-fixes table in the archived `recommendations.html`;
2. appends **advisory** items to `submissions\<industry>\<slug>\BACKLOG.md`;
3. writes **blocker** and **required** items to `evaluation-inbox\<slug>\<version>\fix-brief.md`;
4. starts a non-interactive Copilot CLI agent on the brief. The agent may not push. It:
   - applies the fixes in the strategy's fix order;
   - bumps the patch version (including `listing-metadata.md`) and adds a CHANGELOG entry;
   - runs `check:submissions` and `test:evaluation`, but not the plugin's own test suites;
   - leaves `tests\` and `demo-data\` alone unless a fix requires an edit, and lists any such edit;
   - commits locally and stops.

If there are no blocker or required items, the fix step does nothing and the plugin goes to step 5.

**You then:**

1. Review the agent's commit: `git --no-pager log -1 --stat`, then `git --no-pager show`. Amend or
   revert it as needed.
2. Go back to step 2 for the new version. Each fix-and-re-run cycle is a new version and a new
   Cowork task.

**Running the steps by hand:**

- `npm run evaluation:archive -- --slug <slug> --source "<task>\output"` archives a run.
- `npm run evaluation:fix -- --slug <slug>` runs the fix step on an archived run. Add `--dry-run`
  to write the brief and the backlog without starting the agent.

**Verdicts in `recommendations.html`:**

| Verdict | Meaning | Next |
|---|---|---|
| Ready for human review | Every bar in the strategy is met | Step 5. This is not a publish signal |
| No-ship | There is at least one blocker or required fix | The fix step runs; then step 2 for the new version |
| Blocked | The evaluation could not complete, or the ZIP identity is unclear | Find out why, then re-run as a new version |

The strategy's bar, which the prompt states:

- every skill at or above its launch floor;
- a behavioral pass rate of at least 95%, with no guardrail failures;
- output quality of at least 3.5/5;
- trigger consistency of 3/3;
- negative cases stay out;
- the security scan passes with no medium or high findings;
- the trust and safety gate passes.

A guardrail or safety failure is always a stop.

## Step 5: human spot check

Do this after a `Ready for human review` verdict.

1. Create `sharepoint\<Industry>\<slug>\PLUGIN-DETAILS-AND-DEPLOYMENT.md` from the
   [deployment-doc template](templates/plugin-details-and-deployment.md). Record the evaluated
   SHA-256 in it.
2. Add a tab for this version to `sharepoint\<Industry>\<slug>\<slug>-human-test-tracker.xlsx`,
   following the [tracker spec](templates/human-test-tracker.md). There is one workbook per
   plugin and one tab per version.
3. Two independent testers install the archived ZIP and run the critical-path prompts. They record
   the results in the tracker.
4. Promote only when the tab's **Publish gate** reads `PASS` and its **Owner decision** reads
   `Publish`.

Tracker workbooks carry an encrypting sensitivity label. Open and edit them in Excel desktop, or
through Excel COM.

## Step 6: publish and file the evidence

Promote the evaluated ZIP byte for byte. Never rebuild it.

```powershell
$dir = "sharepoint\<Industry>\<slug>"
Copy-Item "$dir\Evaluation\<version>\<slug>.zip" "$dir\<slug>-plugin-v<version>.zip"
Get-FileHash "$dir\Evaluation\<version>\<slug>.zip", "$dir\<slug>-plugin-v<version>.zip" -Algorithm SHA256
```

Both hashes must equal `artifactSha256` in the receipt. Then update the status in
`sharepoint\<Industry>\README.md` and in the wave log (for example
`docs\professional-services\wave-1.md`). Keep failed runs: every archived version stays in
`Evaluation\`.

## What is public and what stays in SharePoint

This repository is public; the SharePoint library is not.

| Public (repository) | SharePoint only |
|---|---|
| Plugin source, versions, commits and ZIP SHA-256s | The Cowork HTML reports |
| Automated verdicts and headline figures | The testing-strategy document; scenario and CRM evidence |
| Summaries, in your own words, of findings about the plugin's own synthetic behaviour | Reviewer identities, tracker results and owner decision records |
| Cowork task names | Deployment docs and library URLs |

Never copy report text or internal URLs into the repository, a commit message or a bundle.

**SharePoint write rules**

- Write only evaluation archives (through the scripts) and documents the owner asks for.
- Never delete, rename or overwrite other people's files.
- Never delete recursively through the link.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `no SharePoint root configured`, `plain local folder` or `broken link` | `npm run sharepoint:doctor`, then `npm run sharepoint:link` |
| `an evaluation candidate already exists` | Bump the version; never delete the inbox folder to retry |
| `version mismatch: metadata …, manifest …` | Make `metadata.json` and the manifest agree |
| The watcher never logs `Matched Cowork task` | Check `<task>\input\`: the wrong ZIP was attached, or the task has not synced. Start a new task with the inbox ZIP |
| `do not affirm the matching version/hash` | Stale reports, or the report lacks `SHA-256 check: MATCH`. Ask Cowork, in the same task, to add the missing lines |
| `SHA-256 check: MISMATCH` | Stop. Cowork evaluated a different file |
| The watcher times out | Restart it. It never archives twice |
| `no suggested-fixes table` | `recommendations.html` lacks the fixes table. Ask Cowork, in the same task, to add it, then run `npm run evaluation:fix -- --slug <slug> --report "<task>\output\recommendations.html"` |
| The fix agent failed | Read `fix-brief.md`, fix by hand or rerun `npm run evaluation:fix -- --slug <slug>` |
| A `.<version>-<pid>.tmp` folder is left under `Evaluation\` | An archive was interrupted before its rename. Make sure no watcher or archive is running, delete only that one folder, then archive again |
| `evaluation archive already exists` but the receipt says `prepared` | The rename finished but the receipt was not updated. Check that the folder holds the ZIP (with the matching hash) and the three reports, then tell the owner |
