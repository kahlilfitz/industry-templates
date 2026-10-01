# Submissions

This folder is the **only** place a contributor edits. Every archive under `public/bundles/` is
generated from here by [`scripts/import-submissions.ts`](../scripts/import-submissions.ts).

Start by copying [`_template/`](_template) to `submissions/<industry>/<your-slug>/`. The industry folder must match `metadata.json`'s `industry` — the importer checks.

## Anatomy of a submission

```
submissions/<industry>/<slug>/
├── metadata.json                  # package metadata — NEVER bundled
├── README.md                      # human-facing package documentation — NEVER bundled
├── tests/                         # test report, sample prompts — NEVER bundled
├── PACKAGE-NOTES.md               # engineering shorthand, optional — NEVER bundled
│
├── .claude-plugin/plugin.json     # ── everything below here IS bundled ──
├── contracts/<domain>.<name>.v1.json
├── references/                    # rules, thresholds, standards excerpts
├── demo-data/
│   ├── scenario-a-happy/
│   │   ├── <inputs>.json
│   │   ├── raw/                   # the messy originals: email, PDF excerpt, CSV export
│   │   ├── expected/              # committed engine outputs — your regression baseline
│   │   └── README.md
│   └── scenario-b-drama/          # same shape; the case where the obvious answer is wrong
└── skills/
    └── <skill-name>/
        ├── SKILL.md               # frontmatter (name + agent description) + instructions
        ├── scripts/               # deterministic engines
        ├── references/            # the rules this skill's engine mirrors
        ├── contracts/             # the contract slice this skill reads/writes
        └── templates/             # output document templates
```

The `<slug>` is the folder name: lowercase and hyphenated. It also becomes the bundle filename
(`quality-inspection` → `public/bundles/quality-inspection.zip`).

## What gets bundled

The download `.zip` is built from the submission folder with a single root directory named after
the slug, **excluding** `metadata.json`, `README.md`, `PACKAGE-NOTES.md` and `tests/`. Those four
are for people, and shipping them to the agent would only waste its context.

Everything else goes in verbatim — the bundle *is* the package the agent loads.

Bundles are **not** committed to the repository (`public/bundles/` is gitignored): zip entry
metadata is platform-specific, so a Windows-built archive never matches a Linux-built one
byte-for-byte. CI rebuilds them from every submission and uploads the directory as a workflow
artifact.

## `metadata.json`

```json
{
  "name": "Quality Inspection & Nonconformance",
  "description": "One human-friendly sentence describing the package.",
  "industry": "Manufacturing",
  "platforms": ["Cowork"],
  "tags": ["quality", "inspection", "ncr"],
  "author": "Your Name",
  "authorUrl": "https://github.com/your-handle",
  "version": "1.0.0",
  "createdAt": "2026-09-01",
  "updatedAt": "2026-09-04"
}
```

`name`, `description`, `industry`, `platforms`, `tags` and `author` are required. `authorGithub`
is derived from an `authorUrl` pointing at a GitHub profile when it is not supplied explicitly.

`industry` must be one of the values in `INDUSTRIES` in
[`scripts/import-submissions.ts`](../scripts/import-submissions.ts).

## `README.md`

Use the README to explain who the package is for, how the chain works, the concrete case that
shows why it exists, what the user brings, and where the boundaries are. It is for reviewers and
contributors and is not included in the bundle.

## Validate before you open the PR

```bash
npm run check:submissions   # metadata only, writes nothing
npm run build               # recreate public/bundles/
```
