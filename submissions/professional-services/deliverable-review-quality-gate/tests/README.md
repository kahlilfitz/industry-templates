# Deliverable Review & Quality Gate - tests and demo data

The MOS3 package (`manifest.json`, icons and `skills/`) ships no demo data or tests, so they live beside it in this
submission folder (`demo-data/` and `tests/`) and are never bundled.

## What the suite holds

Every check in `run_tests.py` answers a finding from a Cowork evaluation. Checks are added only in response to a Cowork
finding; internal QA rounds, class sweeps and hardening checklists do not add checks here. The label prefix names the
finding the check answers.

| Group | Checks | Cowork evaluation and finding |
|---|---|---|
| `negative_tests` | L1-L5, duplicate sample-limitation finding | 1.0.1: `scope_aligned=false` is a G3 blocker (L1); definitive unsupported conclusions are blockers (L2); relevance-first best evidence, all linked evidence cited (L3); G2 and G8 findings use the source location (L4); missing registers fail closed (L5) |
| `register_tests` | R1, R2, R10 | 1.0.2: a null register is not loaded, never empty; only `client_data_handling: ok` is clean; missing registers and recipients escalate without a placeholder page |
| `page_label_tests` | W3 | 1.0.2: a non-numeric page label or malformed location is a clean input error, never a traceback |
| `g8_tests` | W4-W9 | 1.0.2: look-alike letters, paraphrased steering, citation fields, engine-ID spoofing, benign approvals, a G8 note counted once at its real location |
| `tripwire_tests` | W5 | 1.0.2: the tripwire catches the reviewer/assistant-addressed paraphrase and look-alike set |
| `packet_template_tests` | T&S, D9, D11, D12, Advisory 3 | 1.0.1: no raw contract payload, external recipients held, findings before gate summary; 1.0.2: exact DRAFT label, #2.2 routing citation, no invented page; 1.0.3: no duplicated `Rule:` line, exact empty-section wording |
| `skill_doc_tests` | Non-blocking, Advisory 1, 2, 5 | 1.0.1 non-blocking skill guidance; 1.0.3 advisories (criteria seeding and paragraph numbering, QRM supplies the reliance clause, grounding in a cited source) |
| `skill_trigger_tests` | D13 | 1.0.2: "can this go to the client?" triggers `gate-check` only |
| `demo_derivation_tests` | G4b | 1.0.3 B1: every demo `review-input.json` value derives from its raw pack (with `derive_review_input.py`) |
| `version_tests` | version, CHANGELOG | Added with the 1.0.2 fixes; 1.0.3 B2: the shipped tests pass from the extracted ZIP (source-only `metadata.json` and `CHANGELOG.md` read only when present) |

The runner also turns a crashing group into a FAIL line instead of aborting (1.0.3 B2).

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
Exit code 0 = all passed, 1 = a check failed, 2 = unknown argument or group.

## Scenarios

| Scenario | Covers | Golden status |
|---|---|---|
| `demo-data/scenario-a-happy` | A well-prepared benefits-review draft: quantified claims trace to signed client data and an approved model, the right disclaimer is present and the registers are clean. Only advisories remain (an appendix footer brand failure). | `partner_review_required_advisories_only` |
| `demo-data/scenario-b-drama` | A polished draft that hides release risk: a headline saving backed only by a verbal estimate, a definitive recommendation on a small sample, a third-party lender recipient with the wrong disclaimer, an unattributed licensed chart and prior findings closed in the tracker but not in the document. | `not_ready_for_release` |

Each scenario holds a raw pack (`raw/`), the structured `review-input.json` that `deliverable-ingest` and
`criteria-retrieve` produce from it, and the engine goldens in `expected/` (`assertion-mapped.json`,
`gate-checked.json`, `severity-ranked.json` and `engine-run.log`, generated with `--generated-at 2026-10-01T00:00:00Z`).

## Files in `tests/`

- `run_tests.py`: the regression runner (the groups above).
- `derive_review_input.py`: re-derives each scenario's `review-input.json` from its raw pack and lists any value with no
  raw source or documented ingest rule (`python tests/derive_review_input.py`; `demo_derivation_tests` loads it).
- `sample-test-prompts.csv`: prompts for manual spot checks with their expected behaviour (not a check;
  `demo_derivation_tests` confirms prompts 1 and 2 state the golden statuses).
