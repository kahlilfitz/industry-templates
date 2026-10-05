# Agent guide

Follow [CONTRIBUTING.md](CONTRIBUTING.md) for submission conventions and
[docs/evaluation-workflow.md](docs/evaluation-workflow.md) for release candidates.

Before any workstream task (building or remediating a plugin, freezing or evaluating a candidate,
archiving evidence, writing deployment docs or trackers, promoting a distributable or updating
status), read [docs/operator-runbook.md](docs/operator-runbook.md) and apply
[docs/plugin-hardening-checklist.md](docs/plugin-hardening-checklist.md) before every freeze.

## Skills in sub-agents

QA review, fix and test sub-agents in this repository do not invoke skills unless their prompt
names one; they work from the prompt and the repository. A Cowork plugin-engineering skill (such as
`cowork-plugin-engineer`) applies only to Cowork packaging, manifest, OAuth and ZIP-validation
work, never to engine correctness reviews or fixes.

## Shared modules (`shared\`)

`shared\<module>\` is the source of truth for code vendored into several plugins, such as the
instruction detector `shared\steering-guard\steering_guard.py`. Never edit a vendored copy inside
`submissions\`: change `shared\`, bump its version, copy it byte-for-byte into every plugin listed
by `npm run check:shared`, and rerun each plugin's tests. Plugin-specific vocabulary goes through
the detector's hooks. The operator scores detectors against a private held-out set that agents are
never given; do not look for it or ask for its contents.

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
