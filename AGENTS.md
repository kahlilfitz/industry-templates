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
- Never relax, delete or change the expected result of an existing test or check. If a fix makes
  an existing test fail, stop, do not commit, and report the conflict.
- Every change sent to Cowork is a new version: bump `metadata.json` and the manifest together and
  add a CHANGELOG entry. Engine version labels (`ENGINE_VERSION`-style constants, not
  `steering_guard.py` `__version__`) match the plugin version in every release.
- Commit path-limited (`git commit -m ... -- <paths>`), never push, and stop for owner review.
- Never infer an owner sign-off or a publish decision.

## Tests and demo data

- A MOS3 plugin's tests and demo data live in `submissions\<industry>\<slug>\tests\` and
  `demo-data\`. They are never bundled; the package holds only `manifest.json`, the icons and
  `skills\`.
- The repository's regression tests are the script unit tests (`npm run test:evaluation`), which
  CI runs. Plugin suites are not CI-gated; the evaluation fix agent runs its plugin's suite before
  and after applying fixes. Otherwise run one only when the task asks for it.
- Plugin suites hold only checks that came from a Cowork finding (internal checks were deleted on
  2026-10-15). Add a plugin check only in response to a Cowork finding; never add checks from
  internal review.
- Cowork's built-in evaluation is the plugin evaluation. Never send tests or demo data to Cowork.

## Skills in sub-agents

QA review, fix and test sub-agents in this repository do not invoke skills unless their prompt
names one; they work from the prompt and the repository. A Cowork plugin-engineering skill (such as
`cowork-plugin-engineer`) applies only to Cowork packaging, manifest, OAuth and ZIP-validation
work, never to engine correctness reviews or fixes.

## SharePoint library (`sharepoint\`)

`sharepoint\` is a gitignored link to the OneDrive-synced Industry Templates SharePoint library
([docs/sharepoint-sync.md](docs/sharepoint-sync.md)). It holds the planning context agents need:

- `sharepoint\<Industry>\*-scenarios*.md` and `*-references*.md` — scenario lists, scoring and evidence.
- `sharepoint\<Industry>\<slug>\Evaluation\<version>\` — archived Cowork reports and evaluated ZIPs.
- `sharepoint\<Industry>\<slug>\PLUGIN-DETAILS-AND-DEPLOYMENT.md` and `*-human-test-tracker.xlsx`.
- `sharepoint\Industry-Templates-Plugin-Testing-Strategy.docx` — release bar and testing strategy.

Rules:

- Because the folder is gitignored, file-search tools skip it unless you pass the `sharepoint\...`
  path explicitly.
- If `sharepoint\` is missing or a path does not resolve, run `npm run sharepoint:doctor` and report
  the result; do not recreate the folder by hand.
- Everything written there syncs to SharePoint for the whole team. Write only evaluation archives
  (through `npm run evaluation:archive`/`evaluation:watch`) and documents the user asks for. Never
  delete, rename or overwrite other people's files, and never delete recursively through the link.
- Never commit, copy into `submissions/`, or bundle anything from `sharepoint\`.
