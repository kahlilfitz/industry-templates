# Test data: engagement-closeout-knowledge-harvest 1.0.3

Demo data and the engine regression suite for **Engagement Closeout & Knowledge Harvest**
(`engagement-closeout-knowledge-harvest`) **version 1.0.3**. The plugin source is
`submissions/professional-services/engagement-closeout-knowledge-harvest/`; its MOS3 package ships
only `manifest.json`, the two icons and `skills/`, so nothing in this folder is installed with the
plugin.

## Layout

| Path | Contents |
|---|---|
| `demo-data/scenario-a-happy/` | Raw closeout pack (`raw/`), structured input `engagement.json` (derivable from `raw/` by `skills/artifact-assemble/references/closeout-ingest-rules.md`), engine goldens and stdout (`expected/`), the knowledge-record skeleton and an accepted reviewer-filled example draft |
| `demo-data/scenario-b-drama/` | Same layout; the aggregation-risk confidentiality case |
| `tests/test_engines.py` | Engine regression suite (Python 3 standard library `unittest`) |
| `tests/check_shared_copies.py` | Stand-alone check that the contract, references, `closeout_core.py` and `steering_guard.py` copies are byte-identical across skills, with `steering_guard.py` pinned to the `shared/steering-guard` release hash |
| `tests/steering-corpus.json` | Byte-identical copy of `shared/steering-guard/corpus.json` (attack, benign and field-pair lines) |
| `tests/closeout-steering-sets.json` | Closeout sets: 25 attack, 14 paraphrase, 26 benign closeout and lessons lines, 7 attack pairs, 5 benign pairs, the 19 former detector-gap lines that shared detector 1.1.2 missed and 1.1.3 began catching (`detector_gaps_closed_in_1_1_3`; 1.1.5 still catches them; kept as render-policy evidence), the line the closeout hook vocabulary closed first, and 2 probes only the hook vocabulary catches |
| `tests/closeout-render-corpus.json` | QA round 6 render corpus: 238 realistic titles, IDs and citations (19 reported false-withhold regressions, 13 control words) that must render with no hold (#8.6) |
| `tests/sample-test-prompts.csv` | Human spot-check prompts for the tracker (one per 1.0.3 fix) |

## Running the tests

Run from this folder. The runner resolves `demo-data/...` against this folder (the parent of
`tests/`, not the current directory) and `skills/...` against the plugin root.

```powershell
# Against the submission source (the default plugin root)
python tests\test_engines.py

# Against a built package: expand public\bundles\engagement-closeout-knowledge-harvest.zip first
python tests\test_engines.py --plugin-root <extracted ZIP folder>

# Equivalent, via the environment
$env:PLUGIN_ROOT = '<extracted ZIP folder>'; python tests\test_engines.py
```

```powershell
# Shared-copy check on its own (also run by the release group)
python tests\check_shared_copies.py --plugin-root <extracted ZIP folder>

# List the groups, then run only some of them (--group is repeatable)
python tests\test_engines.py --list-groups
python tests\test_engines.py --group goldens --group sanitisation
```

With neither `--plugin-root` nor `PLUGIN_ROOT`, the plugin root defaults to
`<repo>\submissions\professional-services\engagement-closeout-knowledge-harvest`. The runner prints
both resolved roots and fails with exit code 2 if the plugin root has no `skills\` or a group name is
unknown. It streams an ASCII-safe `PASS <Class.test>` or `FAIL <Class.test>` line per test as the test
finishes (a failing subtest fails its test), prints failure details after the results, and ends with
`N/M checks passed`. The exit code is 1 on any failure.

| Group | Tests | Covers |
|---|---|---|
| `contract` | 5 | Contract version, required arrays, output schema and the Mobilization Scenario 01 adapter |
| `validation` | 21 | Strict input validation: types, enums, duplicates, depth, reserved labels, no echo |
| `lessons` | 1 | Lesson clustering, ranking and taxonomy citations |
| `sanitisation` | 7 | Govern holds, citations, raw-seed exclusion and engine versions (`/1.0.3`) |
| `policy` | 9 | Ties, empty terms, release versus hold, precedence and provenance labels |
| `integrity` | 9 | Every stage re-derives the previous stage's whole document and refuses edits |
| `screening` | 36 | Embedded-instruction screen: families, locations, joins, oversize, rendered holds, split partners (the clean half of an instruction split around a value that trips on its own, a directive ending in an item reference, a split around a supplied marker of any bracket shape, and splits over three or more records, entries or rendered lines, with IDs and citations between the parts); single-pass scanning, the screening ceilings (1000 per array or escalations list, 2500 across the arrays and escalations, 200 per list), a timed 100-asset chain and linear scaling from 100 to 400 assets |
| `steering-corpus` | 5 | Vendored shared detector and corpus scored at the real call site |
| `steering-sets` | 10 | Closeout attack, paraphrase and benign sets; every former detector-gap line caught by shared detector 1.1.5 (default call and closeout hook path) and withheld in every rendered field, ID and draft slot; hook-only probes |
| `render-policy` | 59 | Titles, citations and IDs render only in an allow-shape (#8.6), including upper-case, CamelCase, fused, zero-width, combining-mark and look-alike-digit forms, short fused lead verbs and clauses split between a title and its citation (source, file name or any anchor or sheet name), a citation's source and anchor, or adjacent citation parts or neighbour records in input and rendering order, read by the token-anchored boundary recogniser; case-evidenced fused phrases; short fused lead verbs with trailing complements; digit shorthand in verdict phrases (`safe2reuse`) while `B2B`-style identifiers render; case-evidenced phrases ending at token ends (`SafeToolkit` renders); dotted shorthand (`DOC-7#safe.2.reuse`) while dotted versions and extensions render; clause material running on after a case-evidenced phrase (`SafeToreuse`, `SafeToarchive`) unless the run-on part is an allowlisted ordinary word (`SafeToolkit`) not followed by clause material (`TheyAreasClear` is withheld); verdict phrases and shorthand split by an extension or anchor (`raw/safe2.md#reuse`, `raw/safe.md#to-reuse`, `raw/safe.markdown#to-reuse`) while noun to-do anchors render (`docs/status-okay.md#to-dos`) and `to.do` does not count as one; clause material anywhere after an allowlisted run-on (`SafeTools2Reuse`, `SafeTools-this-record`), read through every later part of the same token (`SafeTools2ReleaseRoadmapNow`, `SafeToolsPlan2Reuse`) while names with digits render (`SafeTools2ReleaseNotes`, `SafeToolsTeams2Go`); a later 2 or 4 before any verb but go or use (`SafeToolsPlan2Release`, `NoNeedleRoadmap4Share`) while ordinals render (`SafeToolsPhase2Review`) and product compounds are no later material (`SafeToolsReviewServiceNowMigration` renders); one extension rule at every extension site (`Project Good` with `raw/to.go` is withheld); benign fused locators, the realistic render corpus and its 9,810 title and citation pairs still render; withheld flags and skeleton markers |
| `drafting` | 7 | Knowledge-record skeleton and `record_check.py` refusal codes, including short-phrase copies |
| `derivation` | 1 | Demo inputs re-derive from each scenario's raw pack (G4b) |
| `goldens` | 1 | Both scenarios reproduce every `expected/` file byte for byte, LF only |
| `packaging` | 3 | Byte-identical skill copies, the MOS3 package boundary and LF-only packaged text (G3) |
| `release` | 8 | Guardrails, citations, routing, versions, stand-alone skills and the runner |
| `harness` | 2 | A crashing test is reported as FAIL |

The full suite (184 tests) takes about three minutes.

## What the scenarios cover

- **Scenario A, happy path** (`scenario-a-happy`): a regional distribution engagement with a mostly
  complete package. `asset_identify` scores three assets and finds one deliverable gap (the draft
  training handover); `lesson_cluster` builds cited governance and adoption clusters and keeps the
  tied DEC-014 decision `unclassified` for review; `sanitize_check` produces review-required release
  candidates with no aggregation hold and holds the client-specific AST-003 configuration (#1.3).
- **Scenario B, drama path** (`scenario-b-drama`): individually harmless facts (anonymised
  architecture, "European utility" descriptor, 6,200 headcount, go-live date, named third-party
  product) combine to identify the synthetic client. `sanitize_check` sets `HOLD_AGGREGATION_RISK`
  (#5.1, #5.2), holds the steering deck for an embedded client logo/name, and flags a named-person
  blame quote for role/process rewrite (#2.1, #2.2). Every member asset's own finding carries the
  group hold.

The suite also builds hostile and malformed variants of these scenarios in memory: injected,
obfuscated, split and rendered-only instructions; prose and former detector-gap lines in titles, citations
and IDs; malformed, duplicated and over-deep input; forged
or edited intermediates; unknown markers and empty terms; and filled drafts that leak held or client
material. It also checks byte-identical copies, the package boundary, the guardrail block, citations,
routing and version declarations.

## Freezing

This folder is frozen once version 1.0.3 is evaluated: `FROZEN.sha256` is written at freeze time
and `npm run check:test-data` then fails on any change. A new plugin version copies this folder
forward to a new version folder and changes the copy.
