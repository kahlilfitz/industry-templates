---
name: SOW Drafting from Scoping Notes
description: "Turn discovery notes and a pursuit record into a review-ready SOW draft using the firm's approved clause library, with thin inputs and clause deviations surfaced before they become commitments."
agentDescription: "Professional Services Cowork plugin for pursuit contracting. Retrieves discovery notes, the CRM pursuit record, prior similar SOWs, the approved clause library and the SOW template; extracts scope and thin-input risks with deterministic scope_extract logic; selects approved clauses with deterministic clause_select logic; flags inherited or requested deviations with deterministic deviation_flag rules; and drafts a review-ready SOW plus QRM deviation summary. Draft-first; clause-library grounded; no deviation approval, pricing, delivery-date commitment, issuance or system write-back."
industry: Professional Services
platforms: [Cowork]
type: plugin
tags: [pursuit, contracting, sow, clause-library, qrm, scoping]
author: Kahlil Fitzgerald
authorUrl: "https://github.com/kahlilfitz"
authorGithub: kahlilfitz
version: 1.0.0
createdAt: 2026-09-23
updatedAt: 2026-09-23
bundle: bundles/sow-drafting-scoping-notes.zip
skills:
  - name: clause-select
  - name: deviation-flag
  - name: notes-ingest
  - name: scope-extract
  - name: sow-draft
---
Turn discovery notes and a pursuit record into a review-ready SOW draft using the firm's approved clause library, with thin inputs and clause deviations surfaced before they become commitments.

> **Professional Services template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

## Skills in this package

- **clause-select** — Runs deterministic `clause_select.py` after `scope-extract` to select approved clause-library language for the SOW and stop if the approved library is absent or unversioned. Use when the user says "use approved clauses", "which clauses belong in this SOW?", "draft the SOW from our clause library", or after `scope-extract` produces `scope.json`.
- **deviation-flag** — Runs deterministic `deviation_flag.py` after `clause-select` to compare selected approved clauses with requested or inherited prior-SOW terms and produce the QRM deviation summary. Use when the user says "check deviations", "can we copy this prior SOW?", "what needs QRM?", "is this clause approved?", or after `clause-select`.
- **notes-ingest** — Retrieves and normalizes discovery notes, scoping notes, CRM pursuit records, prior similar SOWs, approved clause library extracts and SOW templates before `scope-extract`. Use when the user says "draft the SOW", "turn these notes into a statement of work", "start from this discovery call", "use this pursuit record", or "copy this prior SOW but check it".
- **scope-extract** — Runs deterministic `scope_extract.py` after `notes-ingest` to extract scope, deliverables, milestones, assumptions, exclusions and the thin-input report. Use when the user says "what did we scope?", "what did we not pin down?", "turn these notes into a statement of work", "draft the SOW", or after `notes-ingest` finishes.
- **sow-draft** — Drafts the review-ready SOW, thin-input report and QRM deviation summary after `deviation-flag` using only selected approved clauses and engine output. Use when the user says "draft the SOW", "write the statement of work", "create the SOW package", "show the thin-input report", or after `deviation-flag`.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/professional-services/sow-drafting-scoping-notes/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/professional-services/sow-drafting-scoping-notes/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
