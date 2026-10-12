# Changelog

Earlier versions (1.0.0 to 1.0.2) are recorded in the git history of this folder.

## 1.0.3 - 2026-10-12

Packaging and description release. No scoring, clustering or sanitisation logic, output contract or
schema changed: the `ps.engagement-closeout-knowledge-harvest.v1` contract and the governed
`knowledge_record` shape read by Credential & Case Study Assembly and by the Engagement Mobilization &
Onboarding Pack Scenario 01 adapter are unchanged. The only golden differences are the engine version
strings in provenance.

- **MOS3 package.** The plugin is now a Microsoft 365 app package (manifest 1.28) instead of the
  Claude plugin layout. Added `manifest.json` (new stable GUID `id`, `accentColor` `#0B6A7A`,
  `agentSkills` listing the five skill folders), `color.png` and `outline.png`; removed
  `.claude-plugin/`. `metadata.json` sets `"packageFormat": "mos3"`. The ZIP now holds only
  `manifest.json`, the two icons and `skills/`.
- **Test data moved out of the plugin.** `demo-data/` and `tests/` moved to
  `test-data/professional-services/engagement-closeout-knowledge-harvest/1.0.3/` with a README.
  `tests/test_engines.py` follows the runner contract: `--plugin-root <dir>` or `PLUGIN_ROOT`
  (default: this submission folder), `skills/...` resolved against the plugin root and
  `demo-data/...` against the version folder, both roots printed at start, a clear failure when the
  plugin root has no `skills/`, an ASCII-safe `PASS <name>`/`FAIL <name>` line streamed and flushed
  per test, `--list-groups` and a repeatable `--group` (contract, lessons, sanitisation, goldens,
  packaging), a final `N/M checks passed` line and exit 1 on any failure. No test was removed or
  weakened. Added a package-boundary test and a golden test that reruns both scenarios and compares
  every `expected/` JSON and stdout file byte for byte, which the 1.0.2 runner never did (12 to 14
  tests).
- **Root dev copies removed.** The root `contracts/` and `references/` folders duplicated the copies
  every skill already carries and nothing outside the old test read them. The shared-copy test now
  checks that all five skills hold byte-identical copies of the contract and the three references.
- **Skill descriptions rewritten** to the Partner Team Guide shape: two sentences on what the skill
  does and when, six quoted trigger phrases (none shared between skills) and one `Do NOT use for ...
  (use <sibling>)` line that keeps every sibling exclusion and the safety exclusions (no publishing,
  sending, clearing a HOLD or releasing on a claimed approval). All are under 800 characters.
- **SKILL.md frontmatter.** Added `compatibility` (runtime and data each skill needs) and
  `metadata.icon` (Fluent icon ID); `metadata.version` is 1.0.3. Each skill body now shows the exact
  output structure (JSON shape for the engine outputs and assembled payload, table or Markdown
  skeleton for what the user sees).
- **Runtime paths.** No skill file referenced anything outside its own folder; engines read and
  write only `--input` and `--out`. No path changes were needed.
- **Engine version constants** bumped to `asset_identify/1.0.3`, `lesson_cluster/1.0.3` and
  `sanitize_check/1.0.3`. The six JSON goldens were regenerated; their only diff is these version
  strings, and the stdout goldens are unchanged. Downstream fixtures that record `/1.0.2` (for
  example Mobilization's `upstream/closeout-governed.json`) are historical inputs, and no downstream
  skill validates this version string.
- **LF output.** The three engines now write `--out` with `newline="\n"`. They previously wrote CRLF
  on Windows, so their output did not match the LF goldens byte for byte.
- Added `listing-metadata.md` (store listing draft; not packaged).
