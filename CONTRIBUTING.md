# Contributing a template

Thanks for helping grow the **Industry Templates** gallery. A *template* is a reusable package
that teaches an AI agent to do a specific job in a specific industry — targeting one or more of
**Cowork**, **Copilot Studio** and **Scout**.

You contribute by adding **one submission under [`submissions/<industry>/`](submissions/)** and
opening a pull request. You never edit `src/content/` or `public/bundles/` directly — CI
validates your metadata and generates the published page and the download package for you.

## The submission shape

Every submission is a `submissions/<industry>/<slug>/` folder: a `metadata.json` sidecar, an optional
`README.md`, optional `tests/`, and the **unpacked package** itself.

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

> **A submission holds two kinds of file.** Everything **agent-facing** is bundled into the
> download verbatim — the bundle *is* the package the agent loads. The **human-facing** files
> (`metadata.json`, `README.md`, `tests/`, `PACKAGE-NOTES.md`) are never bundled, so they cost
> the agent nothing. Don't leave other notes next to the payload; put them in the pull request
> description.

## `metadata.json`

| Field         | Required | Notes |
|---------------|----------|-------|
| `name`        | yes      | Display name shown in the gallery. |
| `description` | yes      | The catalog summary on the card and at the top of the page. One human-friendly sentence. |
| `industry`    | yes      | One of `Manufacturing`, `Retail & CPG`, `Financial Services`, `Healthcare`, `Energy`, `Public Sector`, `Cross-industry`. This is the gallery's primary facet. |
| `platforms`   | yes      | One or more of `Cowork`, `Copilot Studio`, `Scout`. |
| `tags`        | yes      | Lowercase tags for search and filtering. Don't repeat the industry here — it has its own filter. |
| `author`      | yes      | Person or team who wrote the template. |

Optional: `authorUrl`, `authorGithub`, `version`, `createdAt`, `updatedAt`, `coverColor`,
`featured`, `agentDescription`. Most are inferred: `version` and `agentDescription` fall back to
the package manifest, and `authorGithub` is derived from an `authorUrl` that points at a GitHub
profile.

**Adding a new industry?** Add it to `INDUSTRIES` and `INDUSTRY_COLORS` in
[`src/lib/templates.ts`](src/lib/templates.ts). The filter row renders only industries that have
at least one template, so it grows as the gallery does.

## What visitors see

Two things you write for them:

- The **catalog description** (`metadata.json`'s `description`) — the one-liner on your card.
- Your **`README.md`** — this becomes the main content on the detail page, in your own voice.
  The "Skills in this package" list and the install steps are appended automatically from the
  real payload, so don't hand-write those; they can never drift that way.

A good README covers: who it's for, how the skill chain works, one concrete case that shows why
the template earns its place, what the user has to bring, and where the boundaries are.

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

Each `skills/<name>/` folder in your package is a canonical Agent Skill, so CI
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
npm run import:submissions  # generate the page(s) + bundle(s)
npm run dev                 # preview at http://localhost:4321/industry-templates
npm run build               # runs the same content validation as CI
```

## What CI does

On a pull request, [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

1. Imports your submission, failing with an itemised message if any required metadata is
   missing or invalid.
2. Generates `src/content/templates/<slug>.md`, `src/content/guides/<slug>.md` and
   `public/bundles/<slug>.zip`.
3. Builds the site.

Merges to `main` deploy to GitHub Pages.

By contributing you agree your template is shared under the repository's [MIT license](LICENSE).
