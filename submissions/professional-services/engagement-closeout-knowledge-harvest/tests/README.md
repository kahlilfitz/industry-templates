# Engagement Closeout & Knowledge Harvest - tests and demo data

Demo data and the Cowork regression suite for **Engagement Closeout & Knowledge Harvest**
(`engagement-closeout-knowledge-harvest`). They live in the submission folder beside `skills/`
(`demo-data/` and `tests/`); the MOS3 package ships only `manifest.json`, the two icons and
`skills/`, so neither folder is installed with the plugin.

The suite holds only checks that came from a Cowork evaluation finding. Internal QA, hardening,
steering-corpus, render-policy, golden, packaging and release checks were removed on 2026-10-15 by
owner decision. A new check is added only in response to a Cowork finding.

## Layout

| Path | Contents |
|---|---|
| `demo-data/scenario-a-happy/` | Raw closeout pack (`raw/`), structured input `engagement.json` (derivable from `raw/` by `skills/artifact-assemble/references/closeout-ingest-rules.md`), engine goldens and stdout (`expected/`), the knowledge-record skeleton and an accepted reviewer-filled example draft |
| `demo-data/scenario-b-drama/` | Same layout; the aggregation-risk confidentiality case |
| `tests/test_engines.py` | Cowork regression suite (Python 3 standard library `unittest`) |
| `tests/sample-test-prompts.csv` | Human spot-check prompts for the tracker (not an automated check) |

## Running the tests

Run from `submissions\professional-services\engagement-closeout-knowledge-harvest\`. The runner
resolves `demo-data/...` against the submission folder (the parent of `tests/`, not the current
directory) and `skills/...` against the plugin root.

```powershell
# Against the submission source (the default plugin root)
python tests\test_engines.py

# Against a built package: expand public\bundles\engagement-closeout-knowledge-harvest.zip first
python tests\test_engines.py --plugin-root <extracted ZIP folder>

# Equivalent, via the environment
$env:PLUGIN_ROOT = '<extracted ZIP folder>'; python tests\test_engines.py
```

```powershell
# List the groups, then run only some of them (--group is repeatable)
python tests\test_engines.py --list-groups
python tests\test_engines.py --group sanitisation
```

With neither `--plugin-root` nor `PLUGIN_ROOT`, the plugin root defaults to the submission folder.
The runner prints both resolved roots and fails with exit code 2 if the plugin root has no `skills\` or a group name is
unknown. It streams an ASCII-safe `PASS <Class.test>` or `FAIL <Class.test>` line per test as the test
finishes (a failing subtest fails its test), prints failure details after the results, and ends with
`N/M checks passed`. The exit code is 1 on any failure. The suite has 10 tests and takes a few seconds.

## Checks and the Cowork findings they cover

The tests were added in 1.0.2 (commit `68902f7`) as regression fixtures for the findings of the
Cowork 1.0.0 report (required fixes) and the 1.0.1 report (No-ship engine-layer probes, which the
report asked to be added as regression fixtures). Rule numbers refer to
`confidentiality-sanitisation-rules.md` and `lesson-taxonomy.md`.

| Group | Test | Cowork finding |
|---|---|---|
| `contract` | `test_wrong_contract_fails_explicitly_in_every_engine` | 1.0.0: replace the assert-based contract checks with an explicit failure; 1.0.1 probe P5 (wrong `contract_version`) |
| `contract` | `test_asset_identify_rejects_missing_candidate_assets` | 1.0.1 probe P6: `asset_identify` exited 0 with `candidate_assets` missing and the chain ended in a release-candidate disposition (fail-open) |
| `lessons` | `test_lesson_clusters_are_ranked_and_cited` | 1.0.0: clusters cite their own taxonomy section (not `#1.1` on every cluster), are ranked by priority, and unmatched evidence stays `unclassified` (`#1.5`) instead of defaulting to delivery-governance |
| `sanitisation` | `test_every_finding_cites_confidentiality_rules` | 1.0.0: every sanitize-check finding cites `confidentiality-sanitisation-rules.md` |
| `sanitisation` | `test_governed_knowledge_record_excludes_raw_seeds` | 1.0.0 confidentiality logic defect: `client_descriptor` and unflagged lesson `summary_seed` values reached the knowledge record and handoff |
| `sanitisation` | `test_named_person_markers_hold_assets` | 1.0.1 probes P1 and P1b: assets with `named_individual` or `named_person_blame` markers were released (#2.1, #2.2, #6.2) |
| `sanitisation` | `test_commercial_markers_hold_until_sanitization_is_verified` | 1.0.1 probe P2: unbanded `contract_value`, `pricing` and `margin` assets were released (#3.1, #6.2) |
| `sanitisation` | `test_client_name_in_asset_text_holds` | 1.0.1 probe P3: an asset title containing the client name was released (#1.1) |
| `sanitisation` | `test_held_asset_title_does_not_repeat_client_name` | 1.0.4 R-01: a held asset's `held_assets[].title` repeated the client name word for word, although its finding says the name is not repeated (#1.1) |
| `sanitisation` | `test_untagged_named_person_blame_requires_rewrite` | 1.0.1 probe P9: named-person blame in retrospective text with an empty `named_people` list produced no finding (#2.1, #2.2) |

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
