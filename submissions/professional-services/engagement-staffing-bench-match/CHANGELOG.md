# Changelog

Versions before 1.1.5 are recorded in the git history of
`submissions/professional-services/engagement-staffing-bench-match/` (1.1.4 was the automated
`Ready` candidate).

## 1.1.5 - 2026-10-12

Packaging and metadata release; engine behaviour, output contracts and schemas are unchanged
(only the engine version strings in `provenance.engines` move to 1.1.5).

- **MOS3 package.** The plugin is now a Microsoft 365 app package (manifest 1.28): new root
  `manifest.json` (stable app `id` `2daf60c8-e275-4f95-901b-b01b54defd72`, accent `#3949AB`, five
  `agentSkills` folders), `color.png` and `outline.png`; `metadata.json` sets
  `"packageFormat": "mos3"`. The `.claude-plugin/` folder is removed. The built ZIP holds only
  `manifest.json`, the two icons and `skills/` at its root.
- **Test data moved out of the plugin.** `demo-data/` and `tests/` moved to
  `test-data/professional-services/engagement-staffing-bench-match/1.1.5/` with a README.
  `tests/test_engines.py` now follows the runner contract: `--plugin-root <dir>` or `PLUGIN_ROOT`,
  defaulting to this submission folder; `skills/...` resolves against the plugin root and
  `demo-data/...` against the version folder; it prints both roots and stops if the plugin root has
  no `skills/`. It runs unchanged against an extracted ZIP.
- **Streaming runner.** `tests/test_engines.py` prints an ASCII-safe, flushed `PASS <group>: <test>`
  or `FAIL <group>: <test>` line as each test finishes, supports `--list-groups` and a repeatable
  `--group <name>` (`constraint-check`, `fit-score`, `slate-validate`, `shared-copies`,
  `package-layout`, `golden-scenarios`), ends with `N/M checks passed` and exits 1 on any failure.
  Every existing test still runs in the full suite.
- **Tests added (55 → 58).** `GoldenScenarioTests` runs the four engines from the plugin root on
  both scenarios in a fresh working directory and requires `expected/*.json` to match byte for byte
  apart from platform line endings;
  `PackageLayoutTests` checks every skill is self-contained (no demo data, tests, `../../` or
  `.claude-plugin` references). No existing test or assertion was removed or weakened.
- **Root dev folders removed.** Root `contracts/` and `references/` duplicated the copies every
  skill already carries, and nothing else used them; the empty `scripts/` folder was dropped.
  `skills/fit-score/` is now the canonical copy of the contract, both references and
  `scripts/safety_text.py`, and `SharedCopyTests` requires all five skills to carry byte-identical
  copies.
- **SKILL.md frontmatter.** Every skill adds `compatibility` (runtime and data needs) and
  `metadata.icon` (Fluent ID), and `metadata.version` is `1.1.5`.
- **Description rewrites.** Each description is now two sentences, five quoted user triggers and
  one `Do NOT use for ... (use <skill>)` line, under 800 characters. Routing meaning, sibling
  exclusions, adjacent-skill deferrals (`tool-scripts`, `create`, `d365-sales-*`) and the safety
  boundaries (draft only, never sends, assigns, approves or clears a conflict) are kept. New
  triggers: role-intake "extract the roles from this SOW"; fit-score "compare candidate fit for
  this role" and "show the provisional ranking"; constraint-check "is this candidate independent
  of the client?".
- **Output structures.** Each SKILL.md `Output format` section now shows the exact JSON shape or
  markdown skeleton it produces (taken from the contract and the existing goldens).
- **Runtime paths.** No skill referenced a root folder, demo data or `CLAUDE_PLUGIN_ROOT`; engines
  already resolve imports from their own `scripts/` folder, so no runtime path changed.
- **Engine versions.** The `ENGINE_VERSION` constants in `fit_score`, `slate_rank`,
  `constraint_check` and `slate_validate` are now `1.1.5`, and the eight goldens were regenerated;
  the only change in them is the `provenance.engines` strings. Engine logic is unchanged, and every
  other field Mobilization consumes is identical to 1.1.4.
- **Listing draft.** New `listing-metadata.md` (not packaged) drafts the store listing fields.
