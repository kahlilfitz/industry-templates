# Deliverable Review & Quality Gate

For reviewing partners and QRM teams who need to know whether a deliverable is mechanically ready for judgement before scarce partner time is spent on the substance.

The package does **not** review the deliverable. It clears the mechanical layer so the human review starts at the judgement layer. The reviewing partner's expertise is the scarce resource; spending it on "is the disclaimer present" or "does the headline saving cite a real source" is the waste.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `deliverable-ingest` | Retrieves the draft deliverable and support pack from the engagement workspace and normalizes assertions, locations and evidence into the contract |
| 2 | `criteria-retrieve` | Retrieves the quality framework, gate criteria, required language, brand rules and prior findings |
| 3 | `assertion-map` | Maps each extracted assertion to support and classifies support using deterministic `assertion_map` logic |
| 4 | `gate-check` | Determines gate compliance and release-readiness severity using deterministic `gate_check` and `severity_rank` logic |
| 5 | `review-packet` | Drafts the partner review packet ordered by severity, using only contract data and citations |

Engines compute; the model drafts. Evidence-support verdicts, gate pass/fail, severity ranking and release-readiness status come from Python. The model extracts candidate assertions from prose, orchestrates the steps and writes the cited packet narrative. It never clears a gate, downgrades a blocker or decides that an unsupported claim is acceptable.

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

A draft deliverable, its supporting evidence set, the applicable QRM gate criteria and required language, brand/formatting standards, and prior review findings. The demo scenarios include raw markdown drafts, evidence indexes, QRM extracts and prior-review notes alongside structured inputs so the Connect path is visible rather than assumed.

## Boundaries

Draft-first and judgement-preserving. This package checks and surfaces issues; it does not sign off a deliverable, clear a gate, approve release to the client, authorize reliance, contact a client, write back to a system of record, or substitute for reviewing-partner or QRM judgement.

The references are synthetic operational summaries for demonstration. Replace them with controlled firm policies before using on real work.

## Skills in this package

- **assertion-map** — Maps deliverable assertions to the support pack and computes whether each assertion is supported, limited or unsupported with deterministic `assertion_map`. Use when the user says "what's not substantiated?", "check the claims", "trace the £4.2m saving", "which assertions lack evidence?", or after `criteria-retrieve` before `gate-check`.
- **criteria-retrieve** — Retrieves the QRM quality framework, gate criteria, required disclaimer/reliance language, brand rules and prior-review findings. Use when the user says "which checklist applies?", "retrieve the gate criteria", "what disclaimer is required?", "check QRM requirements", or after `deliverable-ingest` before `assertion-map`.
- **deliverable-ingest** — Retrieves and structures the draft deliverable and supporting evidence set for a quality-gate run. Use when the user says "review this deliverable", "is this ready to go to the client?", "run the quality gate", "check the support pack", or at the start of a Deliverable Review & Quality Gate flow before `criteria-retrieve` and `assertion-map`.
- **gate-check** — Runs the explicit Govern step after `assertion-map`: determines gate compliance with deterministic `gate_check`, then orders release blockers, must-fix items and advisories with deterministic `severity_rank`. Use when the user says "is this ready to go to the client?", "run the quality gate", "what blocks release?", "can we clear the gate?", or after `assertion-map`.
- **review-packet** — Drafts the partner review packet from deterministic `gate-check` and `severity_rank` output. Use when the user says "draft the review packet", "summarize what the partner needs to review", "make the issue list", "what needs fixing before client release?", or after `gate-check` completes.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/deliverable-review-quality-gate/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/deliverable-review-quality-gate/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
