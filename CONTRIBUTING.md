# Contributing a template

Thanks for helping grow the **Industry Templates** repository. A *template* is a reusable package
that teaches an AI agent to do a specific job in a specific industry — targeting one or more of
**Cowork**, **Copilot Studio** and **Scout**.

You contribute by adding **one submission under [`submissions/<industry>/`](submissions/)** and
opening a pull request. You never edit `public/bundles/` directly — CI validates the metadata
and generates the download packages.

## The submission shape

Every submission is a `submissions/<industry>/<slug>/` folder: a `metadata.json` sidecar, an optional
`README.md`, optional `tests/`, and the **unpacked package** itself. Unless it opts into the
[MOS3 app package](#mos3-app-package-opt-in), the package uses the Claude plugin layout:

```
submissions/<industry>/<slug>/
├── metadata.json            # catalog details (sidecar — never bundled)
├── README.md                # optional — becomes the page's main content (never bundled)
├── tests/                   # optional — test report, sample prompts (never bundled)
└── the unpacked package:
    ├── .claude-plugin/plugin.json
    ├── skills/<name>/SKILL.md      # one folder per skill, in run order by name
    │   ├── scripts/                # deterministic engines
    │   ├── references/             # rules the engine cites
    │   ├── contracts/              # the contract this skill reads/writes
    │   └── templates/              # output document templates
    ├── contracts/*.json            # the package-level versioned contract
    ├── references/                 # shared rules, thresholds, standards excerpts
    └── demo-data/                  # two scenarios: a clean one, and one where
                                    # the obvious answer is wrong
```

Copy [`submissions/_template/`](submissions/_template) to get started. The `<slug>` is the
leaf folder name — lowercase and hyphenated, e.g. `quality-inspection` → `/templates/quality-inspection`. The industry folder above it must match `metadata.json`'s `industry` (`Retail & CPG` → `retail-and-cpg`); the importer fails the build if they disagree.

### MOS3 app package (opt-in)

A submission can instead build as a **MOS3 Microsoft 365 app package** (manifest schema
devPreview with a `packageName`, as Cowork's package validation requires), the
format in the "Building a Cowork Plugin — Partner Team Guide". Opt in with
`"packageFormat": "mos3"` in `metadata.json`; without it the layout above applies. The five
Professional Services Wave 1 plugins use it; every other submission is unchanged.

```
submissions/<industry>/<slug>/
├── metadata.json            # sidecar, never bundled ("packageFormat": "mos3", no bundleTests)
├── README.md, CHANGELOG.md  # never bundled
├── BACKLOG.md               # advisory items from Cowork evaluations, never bundled
├── listing-metadata.md      # store listing draft for the shared metadata template, never bundled
├── demo-data/               # synthetic demo data, never bundled
├── tests/                   # the plugin's own tests, never bundled
└── the package (the only files in the ZIP, at its root, no wrapper folder):
    ├── manifest.json        # devPreview manifest: packageName com.microsoft.cowork.<slug>,
    │                        # GUID id, "Microsoft Corporation" developer,
    │                        # description.full ending with the four required links
    ├── color.png            # 192×192
    ├── outline.png          # 32×32, white on transparent
    └── skills/<name>/       # SKILL.md with metadata.icon; self-contained scripts/, references/…
```

`.claude-plugin/` must be removed and `bundleTests` must not be set. Each skill must stand alone:
nothing outside `skills/<name>/` reaches the package, so a skill may not refer to root
`contracts/`, `references/`, demo data or tests. Skill descriptions stay within 1,024 characters
(target 800) with at least five quoted triggers and one "Do NOT use for" line, and bodies stay
under 2,000 words. Demo data and tests stay in the submission folder, outside the package.

> **A submission holds two kinds of file.** Everything **agent-facing** is bundled into the
> download verbatim — the bundle *is* the package the agent loads. The **human-facing** files
> (`metadata.json`, `README.md`, `tests/`, `PACKAGE-NOTES.md`, `BACKLOG.md`) are never bundled, so they cost
> the agent nothing. Don't leave other notes next to the payload; put them in the pull request
> description.

## `metadata.json`

| Field         | Required | Notes |
|---------------|----------|-------|
| `name`        | yes      | Human-readable package name. |
| `description` | yes      | One human-friendly sentence describing the package. |
| `industry`    | yes      | One of `Manufacturing`, `Retail & CPG`, `Financial Services`, `Healthcare`, `Energy`, `Public Sector`, `Professional Services`, `Cross-industry`. |
| `platforms`   | yes      | One or more of `Cowork`, `Copilot Studio`, `Scout`. |
| `tags`        | yes      | Lowercase tags for search and filtering. Don't repeat the industry here — it has its own filter. |
| `author`      | yes      | Person or team who wrote the template. |

Optional: `authorUrl`, `authorGithub`, `version`, `createdAt`, `updatedAt`, `coverColor`,
`featured`, `agentDescription`, `bundleTests` and `packageFormat`. `authorGithub` is derived from an
`authorUrl` that points at a GitHub profile when it is not supplied explicitly. `bundleTests: true`
ships `tests/` in a Claude-layout bundle; it is not allowed with `packageFormat: "mos3"`, which
requires `version`.

**Adding a new industry?** Add it to `INDUSTRIES` in
[`scripts/import-submissions.ts`](scripts/import-submissions.ts).

## Human documentation

Two files explain the package to reviewers:

- `metadata.json` provides the package name, description, industry, platforms, tags and author.
- `README.md` explains who the package is for, how the skill chain works, one concrete case,
  required inputs and boundaries.

## What makes a good template

- **Engines compute, the model drafts.** Anything that produces a number, a severity, a priority
  or a verdict belongs in a deterministic script, not in a prompt. The model extracts,
  orchestrates and writes the cited prose.
- **Rules live in `references/` as data**, and engine constants mirror them section by section,
  so a reader can check the engine against the rule.
- **Every hop carries provenance.** The contract should pass data *plus* confidence, provenance
  and citations, so an escalation is mechanical rather than a judgement call.
- **Two demo scenarios.** A happy path, and one where the obvious answer is wrong — the second
  is what shows a reviewer why the template is worth installing.
- **Draft-first.** No write-back to a system of record, nothing auto-sent, nothing auto-filed.
- **Synthetic demo data only.** No customer data, no real supplier names, no real people.

## Your skills also land in the catalog feed

Each `skills/<name>/` folder in your package is a canonical Agent Skill, so the publish workflow
also copies it — unpacked, one folder per skill — onto the generated `catalog`
branch, which any agent platform that adds skills from a public GitHub folder can
read from a single URL. Two consequences worth knowing:

- **Folders on that branch are named `<template-slug>-<skill-name>`**, so your
  skill names only have to be unique inside your own package. Reusing a name
  another template already uses is fine; reusing one twice in your own is not,
  and fails the build.
- **Each skill should stand on its own.** Keep the `references/`, `scripts/` and
  `contracts/` a skill needs inside that skill's folder, not only at the package
  root, or it will arrive in the feed missing its resources.

## Validate locally

```bash
npm install
npm run check:submissions   # validate metadata only, writes nothing
npm run test:evaluation     # repository script unit tests
npm run build               # recreate public/bundles/
```

While several submissions are changing at once, check or build just yours (other bundles are left
in place):

```bash
npx tsx scripts/import-submissions.ts --check --only <slug>
npx tsx scripts/import-submissions.ts --only <slug>
```

## What CI does

On a pull request, [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

1. Validates every submission and fails with an itemised message if metadata or package layout
   is invalid, then runs the repository script tests (`test:evaluation`).
2. Recreates `public/bundles/<slug>.zip` for every submission.
3. Exercises the flattened catalog export and uploads the bundles as a workflow artifact.

Merges to `main` also refresh the generated `catalog` branch.

## SharePoint library

Planning documents, scenario references, evaluation evidence and human-test trackers live in the
Industry Templates SharePoint library, not in git. Sync it with OneDrive and link it into the
repository as `sharepoint\` with `npm run sharepoint:link` — see
[SharePoint sync](docs/sharepoint-sync.md). Never commit anything from it.

## Evaluate a release candidate

Before treating a plugin as publishable, follow the [release process](docs/release-process.md):

1. package the exact ZIP with `npm run evaluation:prepare`;
2. run Cowork's built-in evaluation on it, which produces the two strategy reports plus
   `recommendations.html`;
3. let the watcher archive the reports and start the fix agent on blocker and required fixes;
4. repeat with the next version until the verdict is `Ready for human review`;
5. run the two-tester human spot check.

`Ready for human review` is never a publish signal.

By contributing you agree your template is shared under the repository's [MIT license](LICENSE).
