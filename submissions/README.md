# Submissions

This folder is the **only** place a contributor edits. Everything the site publishes —
`src/content/templates/`, `src/content/guides/` and `public/bundles/` — is generated from here
by [`scripts/import-submissions.ts`](../scripts/import-submissions.ts).

Start by copying [`_template/`](_template) to `submissions/<your-slug>/`.

## Anatomy of a submission

```
submissions/<slug>/
├── metadata.json                  # catalog details — NEVER bundled
├── README.md                      # the detail page's main content — NEVER bundled
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

The `<slug>` is the folder name: lowercase, hyphenated, and it becomes the page URL
(`quality-inspection` → `/templates/quality-inspection`).

## What gets bundled

The download `.zip` is built from the submission folder with a single root directory named after
the slug, **excluding** `metadata.json`, `README.md`, `PACKAGE-NOTES.md` and `tests/`. Those four
are for people, and shipping them to the agent would only waste its context.

Everything else goes in verbatim — the bundle *is* the package the agent loads.

Bundles are **not** committed to the repository (`public/bundles/` is gitignored): zip entry
metadata is platform-specific, so a Windows-built archive never matches a Linux-built one
byte-for-byte. CI rebuilds them from your submission before every deploy. The generated pages
under `src/content/` *are* committed, so a reviewer can see exactly what your submission will
publish.

## `metadata.json`

```json
{
  "name": "Quality Inspection & Nonconformance",
  "description": "One human-friendly sentence — the card summary and the top of the page.",
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

`name`, `description`, `industry`, `platforms`, `tags` and `author` are required. Everything else
is optional or inferred:

- `version` and `agentDescription` fall back to `.claude-plugin/plugin.json`.
- `authorGithub` is derived from an `authorUrl` pointing at a GitHub profile.
- `skills` is read from your `skills/*/SKILL.md` folders — never hand-write it.
- `bundle` is set automatically.
- `featured: true` pins the template to the top of the default sort. Use sparingly.

`industry` must be one of the values in `INDUSTRIES` in
[`src/lib/templates.ts`](../src/lib/templates.ts). Adding a new industry means adding it there
plus a colour in `INDUSTRY_COLORS`; the gallery's filter row renders only industries that have at
least one template.

Don't put the industry in `tags` — it already has its own filter.

## `README.md`

Your README becomes the detail page's main content, in your own voice. The
**"Skills in this package"** list, the **Demo data** note, the **Install** steps and the **Test
evidence** link are appended automatically from the real payload, so don't write those yourself —
generated boilerplate can't drift from the files that actually ship.

Write the part only you can write: who it's for, how the chain works, the one concrete case that
shows why the template earns its place, what the user brings, and where the boundaries are.

If you omit the README entirely, the page falls back to your catalog description plus that same
generated boilerplate.

## Validate before you open the PR

```bash
npm run check:submissions   # metadata only, writes nothing
npm run import:submissions  # regenerate pages + bundles
npm run dev                 # look at it
```
