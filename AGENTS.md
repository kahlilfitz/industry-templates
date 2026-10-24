# Agent guide

Follow [CONTRIBUTING.md](CONTRIBUTING.md) for submission conventions and
[docs/release-process.md](docs/release-process.md) for packaging, Cowork evaluation, fixes, the
owner's Publish decision and publishing.

## Change scope

Cowork's `recommendations.html` and Cowork's evaluation matrices decide what changes between
versions.

- Change only what the task names: blocker or required fixes from the latest archived
  `recommendations.html`, matrix blockers (below), owner decisions, or regressions your own change
  caused. Advisory items go to the submission's `BACKLOG.md`, not into the plugin. Report any other
  defect you find; do not fix it.
- Owner decision (2026-10-22): Cowork's evaluation matrix output is a Cowork finding. That covers
  the workbook and notes pair (`<slug>-v<version>-eval-matrix-YYYY-MM-DD-HHMM.xlsx` and
  `-matrix-notes-YYYY-MM-DD-HHMM.md`, collected into the plugin's SharePoint
  `Evaluation Matrices\` folder) for the plugin's current version.
  - **Matrix blockers**, meaning the notes' "Top blockers" and "Rows marked blocked", are handled
    like required fixes when a plugin change resolves them. Each one adds a regression check named
    for the matrix and item (for example `matrix 2026-10-22-1133 blocker 2`).
  - Blockers that sit in the eval harness or environment (tool spies, fault injection, multi-turn
    support, sibling plugins, runtime) are not fixed in the plugin. Report them to the owner.
  - Other matrix items (unresolved questions, guardrail gaps) are advisory: they go to
    `BACKLOG.md` unless the owner promotes them.
- Owner decision (2026-10-22), **honest-empty grading**: a row passes when its pass criterion calls
  for less output and the plugin produces it. That covers withheld markers and placeholders,
  declared gaps, script input errors quoted verbatim with nothing written, refusals and holds.
  Two cases still fail:
  - **Over-refusal:** a happy-path row with complete inputs that refuses, holds or returns nothing.
  - **Undeclared empty output:** an empty result that names no missing source or field and quotes
    no script error.

  Never weaken a guardrail, withholding rule or hold to make a completeness-graded row pass.
- Except for the one-time owner exceptions below, never relax, delete or change the expected result
  of an existing test or check. If a fix makes an existing test fail outside those exceptions, stop,
  do not commit, and report the conflict.
- Every change sent to Cowork is a new version: bump `metadata.json` and the manifest together and
  add a CHANGELOG entry. Bump only after fixes; an unchanged version whose queue run did not
  complete is re-sent with `npm run evaluation:prepare -- --slug <slug> --requeue`. Engine version labels (`ENGINE_VERSION`-style constants, not
  `steering_guard.py` `__version__`) match the plugin version in every release.
- Commit path-limited (`git commit -m ... -- <paths>`) and stop for owner review. Push only when
  the owner explicitly asks in the current session, only to the current branch's tracked remote,
  never force-push, and never push to `main`. The unattended `evaluation:fix` agent never pushes.
  Owner decision (2026-10-16): the fix step itself prepares the next version when its checks find
  nothing that needs the owner's attention; the agent still never runs `evaluation:prepare`.
- Owner decision (2026-10-24, "prepare plugin for cowork after fixes"): after an interactive agent
  applies fixes and commits the new version, it runs `npm run evaluation:prepare -- --slug <slug>`
  without waiting to be asked, then commits the evaluation records and stops. It prepares only
  when nothing needs the owner's attention: the plugin suite and `npm run check:submissions` pass,
  the version, engine labels and CHANGELOG are bumped, and no existing-check conflict or open owner
  decision remains. Otherwise it stops and reports.
- Never infer an owner sign-off or a publish decision.
- Owner decision (2026-10-23): human testing is not part of the release process ("remove human
  testing from the process"). After a `Ready` verdict, publication still needs the owner's
  `Publish` decision recorded in the plugin's SharePoint deployment doc ("Publish after Ready").
  Do not ask about or plan testers, trackers or a human spot check.

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

## One-time owner exception: T&E 1.0.13 R-02

Owner-approved on 2026-10-16, for `time-expense-narrative-compliance` **1.0.13 only**: while
applying required **R-02 from the 1.0.12 Cowork evaluation** (skip a deliverable clause that
repeats the subject), regenerate `demo-data\scenario-b-drama\expected\drafted.json`, `coded.json`
and `governed.json`. The only permitted non-label change is the TE-B-001 B-DOC-001 suggested
rewrite losing " for the Integration Design", and the status and review reason that follow from
the 12-word minimum (#1.1), as they flow through code-map and guideline-check. In
`tests\run_tests.py`, the check `per-activity rewrites on a multi-link entry are needs_review and
name what they leave out` changes its status condition from `r["status"] == "needs_review"` to
`r["status"].startswith("needs_review")`; its "only" reason and coverage conditions stay unchanged.
Every other golden, check and expectation stays unchanged. Follow the
[exception's evidence requirements](docs/release-process.md#one-time-owner-exception-for-te-1013-r-02).
This is not a general waiver, an evaluation verdict, or a publish decision.

## One-time owner exception: removing human testing

Owner-approved on 2026-10-23, with removing human testing from the release process: the passing
verdict is renamed from `Ready for human review` to `Ready`, so the verdict expectations in
`scripts\evaluation-workflow.test.ts` (extractVerdict values and error text, verdictGuidance text,
and the Cowork prompt verdict list) change to match. Every test input stays, archived
`Ready for human review` reports still parse as `Ready`, other `Ready for ...` phrases still throw,
and the prompts must still say Ready is `not a publish signal`. No plugin suite, golden or other
check changes. See the
[exception's scope](docs/release-process.md#one-time-owner-exception-removing-human-testing).
This is not a general waiver or a publish decision.

## Tests and demo data

- A MOS3 plugin's tests and demo data live in `submissions\<industry>\<slug>\tests\` and
  `demo-data\`. They are never bundled; the package holds only `manifest.json`, the icons and
  `skills\`.
- The repository's regression tests are the script unit tests (`npm run test:evaluation`), which
  CI runs. Plugin suites are not CI-gated; the evaluation fix agent runs its plugin's suite before
  and after applying fixes. Otherwise run one only when the task asks for it.
- Every blocker or required Cowork fix, including a matrix blocker fixed in the plugin, adds at least
  one regression check, named for its fix ID or matrix item, that fails before the fix and passes after.
- Plugin suites hold only checks that came from a Cowork finding, which includes Cowork's evaluation
  matrices (internal checks were deleted on 2026-10-15). Add a plugin check only in response to a
  Cowork finding; never add checks from internal review.
- Cowork's built-in evaluation is the plugin evaluation. Never send tests or demo data to Cowork.

## SharePoint library (`sharepoint\`)

`sharepoint\` is a gitignored link to the OneDrive-synced Industry Templates SharePoint library
([docs/sharepoint-sync.md](docs/sharepoint-sync.md)). It holds the planning context agents need:

- `sharepoint\<Industry>\*-scenarios*.md` and `*-references*.md` — scenario lists, scoring and evidence.
- `sharepoint\<Industry>\<plugin folder>\Evaluation\<version folder>\` — archived Cowork reports and
  evaluated ZIPs. Professional Services Waves 1 and 2 mirror Retail: `Wave <n>\<Title Case Slug>\` and
  `Evaluation\v<version>\` (`SHAREPOINT_WAVES` in `scripts\evaluation-workflow.ts`). Every other
  plugin uses `<slug>\` and `Evaluation\<version>\`.
- `PLUGIN-DETAILS-AND-DEPLOYMENT.md` in each plugin folder, which holds the owner's Publish
  decision. Human-test tracker workbooks there are history only (human testing was removed on
  2026-10-23).
- `sharepoint\Industry-Templates-Plugin-Testing-Strategy.docx` — release bar and testing strategy.

Rules:

- Because the folder is gitignored, file-search tools skip it unless you pass the `sharepoint\...`
  path explicitly.
- If `sharepoint\` is missing or a path does not resolve, run `npm run sharepoint:doctor` and report
  the result; do not recreate the folder by hand.
- Everything written there syncs to SharePoint for the whole team. Write only evaluation archives
  (through `npm run evaluation:archive`/`evaluation:watch`), MOS packages (through
  `npm run mos:build`, only after the owner promotes `<slug>-cowork.zip`), completed evaluation
  matrix/notes pairs (through `npm run evaluation:watch-matrices`, copied without overwriting into
  the plugin's `Evaluation Matrices\` folder) and documents the user asks for. Never
  delete, rename or overwrite other people's files, and never delete recursively through the link.
- Never commit, copy into `submissions/`, or bundle anything from `sharepoint\`.
