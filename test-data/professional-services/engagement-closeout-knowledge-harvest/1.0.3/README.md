# Test data: engagement-closeout-knowledge-harvest 1.0.3

Demo data and the engine regression suite for **Engagement Closeout & Knowledge Harvest**
(`engagement-closeout-knowledge-harvest`) **version 1.0.3**. The plugin source is
`submissions/professional-services/engagement-closeout-knowledge-harvest/`; its MOS3 package ships
only `manifest.json`, the two icons and `skills/`, so nothing in this folder is installed with the
plugin.

## Layout

| Path | Contents |
|---|---|
| `demo-data/scenario-a-happy/` | Raw closeout pack (`raw/`), structured input `engagement.json`, engine goldens (`expected/`) |
| `demo-data/scenario-b-drama/` | Same layout; the aggregation-risk confidentiality case |
| `tests/test_engines.py` | Engine regression suite (Python 3 standard library `unittest`) |
| `tests/sample-test-prompts.csv` | Human spot-check prompts for the tracker |

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

With neither `--plugin-root` nor `PLUGIN_ROOT`, the plugin root defaults to
`<repo>\submissions\professional-services\engagement-closeout-knowledge-harvest`. The runner prints
both resolved roots, fails with exit code 2 if the plugin root has no `skills\`, streams one line per
test and ends with `N/M checks passed` (exit 1 on any failure). Extra arguments, such as a test name,
are passed to `unittest`.

## What the scenarios cover

- **Scenario A, happy path** (`scenario-a-happy`): a regional distribution engagement with a mostly
  complete package. `asset_identify` scores three assets and finds one deliverable gap (the draft
  training handover); `lesson_cluster` builds cited governance and adoption clusters;
  `sanitize_check` produces review-required release candidates with no aggregation hold.
- **Scenario B, drama path** (`scenario-b-drama`): individually harmless facts (anonymised
  architecture, "European utility" descriptor, 6,200 headcount, go-live date, named third-party
  product) combine to identify the synthetic client. `sanitize_check` sets `HOLD_AGGREGATION_RISK`
  (#5.1, #5.2), holds the steering deck for an embedded client logo/name, and flags a named-person
  blame quote for role/process rewrite (#2.1, #2.2).

The suite also covers wrong-contract and missing-array failures in every engine, unclassified lesson
evidence, named-person and commercial-figure holds, client names in asset text, exclusion of raw seeds
from the governed knowledge record, byte-identical contract and reference copies across all five
skills, and the package boundary (no demo data, tests or `.claude-plugin` in the plugin root, no
paths that escape a skill folder).

## Freezing

This folder is frozen once version 1.0.3 is evaluated: `FROZEN.sha256` is written at freeze time
and `npm run check:test-data` then fails on any change. A new plugin version copies this folder
forward to a new version folder and changes the copy.
