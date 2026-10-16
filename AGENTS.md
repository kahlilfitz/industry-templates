# Agent guide

Follow [CONTRIBUTING.md](CONTRIBUTING.md) for submission conventions and
[docs/release-process.md](docs/release-process.md) for packaging, Cowork evaluation, fixes, human
review and publishing.

## Change scope

Cowork's `recommendations.html` decides what changes between versions.

- Change only what the task names: blocker or required fixes from the latest archived
  `recommendations.html`, owner decisions, or regressions your own change caused. Advisory items
  go to the submission's `BACKLOG.md`, not into the plugin. Report any other defect you find; do
  not fix it.
- Except for the one-time owner exception below, never relax, delete or change the expected result
  of an existing test or check. If a fix makes an existing test fail outside that exception, stop,
  do not commit, and report the conflict.
- Every change sent to Cowork is a new version: bump `metadata.json` and the manifest together and
  add a CHANGELOG entry. Engine version labels (`ENGINE_VERSION`-style constants, not
  `steering_guard.py` `__version__`) match the plugin version in every release.
- Commit path-limited (`git commit -m ... -- <paths>`) and stop for owner review. Push only when
  the owner explicitly asks in the current session, only to the current branch's tracked remote,
  never force-push, and never push to `main`. The unattended `evaluation:fix` agent never pushes.
- Never infer an owner sign-off or a publish decision.

## One-time owner exception: T&E R-03

Owner-approved on 2026-10-16, for `time-expense-narrative-compliance` **1.0.12 only**:
replace the exact-literal expectation in `tests\run_tests.py`, `te110_tests`, in the check named
`1.0.10 R-01 ND-01: noun purposes use regarding, never an ungrammatical to clause`. This permits
rule-based grammar and grounding checks instead of requiring
`" regarding internal staffing check-in"` while applying required **R-03 from the 1.0.10 Cowork
evaluation**.

Preserve the original grammar and grounding protections, add R-03 regressions that fail before
the engine fix and pass afterward, and leave every other existing check unchanged. Follow the
[exception's evidence requirements](docs/release-process.md#one-time-owner-exception-for-te-r-03).
This is not a general waiver, an evaluation verdict, or a publish decision.

## Tests and demo data

- A MOS3 plugin's tests and demo data live in `submissions\<industry>\<slug>\tests\` and
  `demo-data\`. They are never bundled; the package holds only `manifest.json`, the icons and
  `skills\`.
- The repository's regression tests are the script unit tests (`npm run test:evaluation`), which
  CI runs. Plugin suites are not CI-gated; the evaluation fix agent runs its plugin's suite before
  and after applying fixes. Otherwise run one only when the task asks for it.
- Every blocker or required Cowork fix adds at least one regression check, named for its fix ID,
  that fails before the fix and passes after.
- Plugin suites hold only checks that came from a Cowork finding (internal checks were deleted on
  2026-10-15). Add a plugin check only in response to a Cowork finding; never add checks from
  internal review.
- Cowork's built-in evaluation is the plugin evaluation. Never send tests or demo data to Cowork.

## SharePoint library (`sharepoint\`)

`sharepoint\` is a gitignored link to the OneDrive-synced Industry Templates SharePoint library
([docs/sharepoint-sync.md](docs/sharepoint-sync.md)). It holds the planning context agents need:

- `sharepoint\<Industry>\*-scenarios*.md` and `*-references*.md` — scenario lists, scoring and evidence.
- `sharepoint\<Industry>\<plugin folder>\Evaluation\<version folder>\` — archived Cowork reports and
  evaluated ZIPs. Professional Services Waves 1 and 2 mirror Retail: `Wave <n>\<Title Case Slug>\` and
  `Evaluation\v<version>\` (`SHAREPOINT_WAVES` in `scripts\evaluation-workflow.ts`). Every other
  plugin uses `<slug>\` and `Evaluation\<version>\`.
- `PLUGIN-DETAILS-AND-DEPLOYMENT.md` and the human-test tracker in each plugin folder
  (`<Title Case Slug> - Human Test Tracker.xlsx` in the Retail layout, otherwise
  `<slug>-human-test-tracker.xlsx`).
- `sharepoint\Industry-Templates-Plugin-Testing-Strategy.docx` — release bar and testing strategy.

Rules:

- Because the folder is gitignored, file-search tools skip it unless you pass the `sharepoint\...`
  path explicitly.
- If `sharepoint\` is missing or a path does not resolve, run `npm run sharepoint:doctor` and report
  the result; do not recreate the folder by hand.
- Everything written there syncs to SharePoint for the whole team. Write only evaluation archives
  (through `npm run evaluation:archive`/`evaluation:watch`), MOS packages (through
  `npm run mos:build`, only after the owner promotes `<slug>-cowork.zip`) and documents the user asks
  for. Never
  delete, rename or overwrite other people's files, and never delete recursively through the link.
- Never commit, copy into `submissions/`, or bundle anything from `sharepoint\`.
