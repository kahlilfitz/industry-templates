# Deliverable Review & Quality Gate - tests and demo data

The MOS3 package (`manifest.json`, icons and `skills/`) ships no demo data or tests, so they live beside it in this
submission folder (`demo-data/` and `tests/`) and are never bundled.

## Run the tests

Run from `submissions/professional-services/deliverable-review-quality-gate/`. The working directory is not used: the
data root is the parent of `tests/`, and every `skills/...` path resolves against the plugin root (`--plugin-root DIR`,
else the `PLUGIN_ROOT` environment variable, else this submission folder).

Against the source:

```bash
python tests/run_tests.py
```

Against a built package, expand `public/bundles/deliverable-review-quality-gate.zip` into an empty folder, then:

```bash
python tests/run_tests.py --plugin-root <extracted folder>
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
  alone into a temporary folder and runs its documented commands against the goldens. It also checks that every
  vendored file is byte-identical to its canonical copy (19 copies): the contract and shared references are canonical
  in `skills/gate-check/` and copied to every other skill; `assertion_map.py`, `assertion_rules.py` and
  `steering_guard.py` are canonical in `skills/assertion-map/`; `gate_check.py` and `severity_rank.py` are canonical in
  `skills/gate-check/` (copied to `review-packet`).
- `derive_review_input.py`: re-derives each scenario's `review-input.json` from its raw pack and lists any value with no
  raw source or documented ingest rule.
- `check_messages.py`: scans the engine and helper scripts so no message formats review-input text.
- `steering-corpus.json`: the steering-guard corpus the vendored detector is scored against.
- `sample-test-prompts.csv`: prompts for manual and Cowork testing with their expected behaviour.