# Deliverable Review & Quality Gate - test data 1.0.6

**Paired plugin:** `deliverable-review-quality-gate` version `1.0.6`

Source: `submissions/professional-services/deliverable-review-quality-gate/`. The MOS3 package (`manifest.json`, icons and
`skills/`) ships no demo data or tests, so they live here.

## Run the tests

Run from this folder. The working directory is not used: the data root is the parent of `tests/`, and every `skills/...`
path resolves against the plugin root (`--plugin-root DIR`, else the `PLUGIN_ROOT` environment variable, else
`<repo>/submissions/professional-services/deliverable-review-quality-gate`).

Against the source:

```bash
python tests/run_tests.py
python tests/check_shared_copies.py
```

Against a built package, expand `public/bundles/deliverable-review-quality-gate.zip` into an empty folder, then:

```bash
python tests/run_tests.py --plugin-root <extracted folder>
python tests/check_shared_copies.py --plugin-root <extracted folder>
```

`python tests/run_tests.py --list-groups` lists the test groups; `--group NAME` (repeatable) runs only those groups.
Each runner prints the resolved plugin root and data root first and exits 2 if the plugin root has no `skills/` folder.

## Scenarios

| Scenario | Covers | Golden status |
|---|---|---|
| `demo-data/scenario-a-happy` | A well-prepared benefits-review draft: quantified claims trace to signed client data and an approved model, the right disclaimer is present and the registers are clean. Only advisories remain (an appendix footer brand failure). | `partner_review_required_advisories_only` |
| `demo-data/scenario-b-drama` | A polished draft that hides release risk: a headline saving backed only by a verbal estimate, a definitive recommendation on a small sample, a third-party lender recipient with the wrong disclaimer, an unattributed licensed chart and prior findings closed in the tracker but not in the document. | `not_ready_for_release` |

Each scenario holds a raw pack (`raw/`), the structured `review-input.json` that `deliverable-ingest` and
`criteria-retrieve` produce from it, and the engine goldens in `expected/` (`assertion-mapped.json`,
`gate-checked.json`, `severity-ranked.json` and `engine-run.log`, generated with `--generated-at 2026-10-01T00:00:00Z`).

## Helpers in `tests/`

- `run_tests.py`: the regression runner (engines, contract, skill documents, goldens, injection tripwire benign and
  attack sets, versions and package layout). Its `mos3_skill_isolation_tests` group copies each script-running skill
  alone into a temporary folder and runs its documented commands against the goldens.
- `check_shared_copies.py`: every vendored file is byte-identical to its canonical copy (20 copies). The contract and
  shared references are canonical in `skills/gate-check/` and copied to every other skill. `assertion_map.py` and
  `assertion_rules.py` are canonical in `skills/assertion-map/` (copied to `gate-check`, and `assertion_rules.py` to
  `review-packet`). `gate_check.py` and `severity_rank.py` are canonical in `skills/gate-check/` (copied to
  `review-packet`). The vendored `steering_guard.py` copies in `assertion-map`, `gate-check` and `review-packet` match
  `shared/steering-guard/`.
- `derive_review_input.py`: re-derives each scenario's `review-input.json` from its raw pack and lists any value with no
  raw source or documented ingest rule.
- `check_messages.py`: scans the engine and helper scripts so no message formats review-input text.
- `steering-corpus.json`: the shared steering-guard corpus (a byte-identical copy of `shared/steering-guard/`).
- `sample-test-prompts.csv`: prompts for manual and Cowork testing with their expected behaviour.

## Frozen once evaluated

This folder is frozen when plugin version 1.0.6 is evaluated (`FROZEN.sha256` is added at freeze time). Do not edit it
afterwards; a new plugin version copies this folder forward to a new version folder and changes it there.
