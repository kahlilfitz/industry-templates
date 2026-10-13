# Deliverable Review & Quality Gate

For reviewing partners and QRM teams who need to know whether a deliverable is mechanically ready for judgement before scarce partner time is spent on the substance.

The package does **not** review the deliverable. It checks the mechanical layer so the human review starts at the judgement layer. The reviewing partner's expertise is the scarce resource; spending it on "is the disclaimer present" or "does the headline saving cite a real source" is the waste.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `deliverable-ingest` | Retrieves the draft deliverable and support pack from the engagement workspace and normalizes assertions, locations and evidence into the contract |
| 2 | `criteria-retrieve` | Retrieves the quality framework, gate criteria, required language, brand rules and prior findings |
| 3 | `assertion-map` | Maps each extracted assertion to support and classifies support using deterministic `assertion_map` logic |
| 4 | `gate-check` | Determines gate compliance and release-readiness severity using deterministic `gate_check` and `severity_rank` logic |
| 5 | `review-packet` | Drafts the partner review packet ordered by severity, using only contract data and citations |

Engines compute; the model drafts. Evidence-support verdicts, gate pass/fail, severity ranking and review status come from Python. The model extracts candidate assertions from prose, orchestrates the steps and writes the cited packet narrative. It never signs off a gate, downgrades a blocker or decides that an unsupported claim is acceptable.

Version 1.0.2 closes the v1.0.1 automated-evaluation blockers: review packets no longer append raw contract payloads or accept unconfirmed external routing, assertion mapping selects best evidence by relevance and cites every linked evidence item, definitive unsupported conclusions become release blockers, scope alignment and missing registers hold deterministically, and gate locations come from the deliverable payload instead of hard-coded defaults.

Version 1.0.3 closes the v1.0.2 automated-evaluation blockers. Null or absent registers and any client-data value other than `ok` now hold and escalate. The G8 tripwire folds Cyrillic/Greek look-alikes, catches reviewer- and assistant-addressed paraphrases, scans evidence citations, ignores ordinary "pre-approved" business prose and cannot be suppressed by upstream findings that reuse engine IDs. severity_rank returns a clean error for non-numeric page labels. The review packet is headed `DRAFT - HUMAN REVIEW REQUIRED`.

Version 1.0.4 follows 1.0.3, which was frozen and submitted for evaluation. It carries every 1.0.3 fix, and the G8 tripwire now runs on `steering_guard`, a shared detector vendored byte-for-byte into `skills/gate-check/scripts/`. It groups rules into intent families rather than phrase lists. It catches:

- text that addresses the tool directly (assistant, AI, Copilot, Claude, GPT, bot, agent, reviewer), whatever the verb;
- verdict steering such as "mark/report/classify this as supported" or "treat this as release ready";
- negative instructions aimed at this review, a finding or an item, and overrides of the disclaimer, reliance clause, QRM or G1-G8 rules;
- authority claims such as "System note: quality gate passed", and forwarding to an e-mail address or URL;
- look-alike letters from any non-Latin script mixed into a Latin word;
- steering hidden in IDs or file names;
- steering split across the fields of one record (an assertion, the deliverable, a brand check, licensed content, an evidence entry, a prior finding, the criteria or a carried finding) or across adjacent list entries.

A field too long to screen is held for review, never passed.

1.0.4 also closes the Cowork 1.0.3 findings. Every value in the demo `review-input.json` files now traces to the scenario's raw pack, including a new `raw/release-registers.md` with the client-data, brand-check and licensed-content registers, and a helper re-derives each input from its raw pack.

Version 1.0.5 changes packaging only. The plugin is now a Microsoft 365 (MOS3) app package: `manifest.json`, `color.png`, `outline.png` and `skills/`. Each skill carries its own contract and references, and gate, severity and output behaviour are unchanged. Demo data and tests no longer ship in the plugin.

### Bundled engine copies

Each skill runs only scripts inside its own folder, so a skill installed on its own still works. `gate-check` bundles the `assertion_map` engine it runs to recover a missing `assertion-mapped.json`, and `review-packet` bundles the `severity_rank` engine and the modules it imports for `--verify`. `deliverable-ingest` runs no script; it hands `review-input.json` to `assertion-map`. Change the canonical copy, then copy it byte-for-byte to the others; `tests/check_shared_copies.py` and the runner's `mos3_skill_isolation_tests` group fail on any drift, missing copy or stale copy.

| File | Canonical copy | Byte-identical copies |
|------|----------------|-----------------------|
| `contracts/deliverable-review-quality-gate.contract.json` | `skills/gate-check/` | the other four skills |
| `references/quality-gate-criteria.md`, `references/partner-review-packet-format.md` | `skills/gate-check/` | the other four skills |
| `scripts/assertion_map.py` | `skills/assertion-map/` | `gate-check` |
| `scripts/assertion_rules.py` | `skills/assertion-map/` | `gate-check`, `review-packet` |
| `scripts/gate_check.py`, `scripts/severity_rank.py` | `skills/gate-check/` | `review-packet` |
| `scripts/steering_guard.py` | `shared/steering-guard/` (repository) | `assertion-map`, `gate-check`, `review-packet` |

## Tests and demo data

Demo scenarios, goldens and tests live in [`test-data/professional-services/deliverable-review-quality-gate/1.0.6/`](../../../test-data/professional-services/deliverable-review-quality-gate/1.0.6/README.md). From that folder:

```bash
python tests/run_tests.py                              # against this source folder
python tests/run_tests.py --plugin-root <extracted ZIP> # against a built package
python tests/check_shared_copies.py
```

## The case that shows why it exists

In the second demo scenario, the deliverable looks excellent. It is polished, branded, client-confidential, and has a disclaimer. A skim review would likely move it forward.

The trap is that the polish hides release risk:

- The headline "£4.2m annual saving" traces only to a stakeholder's verbal workshop estimate, not to a model or analysis.
- A recommendation is written as a definitive conclusion even though the sample is too small to support an estate-wide conclusion.
- The disclaimer present is the wrong one: the deliverable names a third-party lender recipient, so reliance-restriction language is mandatory.
- A licensed analyst-style chart is reproduced without attribution.
- A prior review finding is marked closed in the tracker, but the fix never landed in the document.

A naive reviewer sees a professional report with a disclaimer. The engine starts the partner at the unsupported headline claim and wrong-disclaimer release blockers.

## What you bring

A draft deliverable, its supporting evidence set, the applicable QRM gate criteria and required language, brand/formatting standards, and prior review findings. The demo scenarios include raw markdown drafts (with page markers and a distribution list), evidence indexes, QRM extracts, prior-review notes and release-control registers alongside structured inputs, so the Connect path is visible rather than assumed. Every structured value traces to the raw pack, and `python tests/derive_review_input.py`, run from `test-data/professional-services/deliverable-review-quality-gate/1.0.6/`, checks that it does.

## Boundaries

Draft-first and judgement-preserving. This package checks and surfaces issues; it does not sign off a deliverable, clear a gate, approve release to the client, authorize reliance, contact a client, write back to a system of record, or substitute for reviewing-partner or QRM judgement.

The references are synthetic operational summaries for demonstration. Replace them with controlled firm policies before using on real work.
