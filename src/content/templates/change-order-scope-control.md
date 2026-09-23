---
name: Change Order & Scope Control
description: "Compare client requests and delivered work against the SOW, cite the governing clause, quantify the effort delta, and draft a defensible change order before margin drift becomes unrecoverable."
agentDescription: "Professional Services Cowork plugin for delivery and commercial control. Retrieves the SOW, MSA and prior change orders; normalizes request logs, mail threads and delivered artifacts; deterministically matches requests to scope clauses, classifies each item as in-scope, out-of-scope or ambiguous, calculates the effort/cost delta and cumulative drift, and drafts a change order for human review. Draft-first; SOW-grounded; no acceptance, repricing, client issuance or system write-back."
industry: Professional Services
platforms: [Cowork]
type: plugin
tags: [delivery, commercial-control, scope, change-order, sow, margin]
author: Kahlil Fitzgerald
authorUrl: "https://github.com/kahlilfitz"
authorGithub: kahlilfitz
version: 1.0.0
createdAt: 2026-09-23
updatedAt: 2026-09-23
bundle: bundles/change-order-scope-control.zip
skills:
  - name: change-order-draft
  - name: request-intake
  - name: scope-classify
  - name: scope-match
  - name: sow-retrieve
---
Compare client requests and delivered work against the SOW, cite the governing clause, quantify the effort delta, and draft a defensible change order before margin drift becomes unrecoverable.

> **Professional Services template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

## Skills in this package

- **change-order-draft** — Runs deterministic `delta_calc.py` after `scope-classify` to calculate effort delta, cost delta and cumulative scope drift, then drafts the change order and drift summary. Use when the user says "draft the change order", "what is the cost impact?", "show cumulative drift", "where has scope drifted?", "should this be a change order?", or after `scope-classify` completes.
- **request-intake** — Extracts inbound client requests, mail-thread pressure, delivered artifacts and effort estimates into the contract after `sow-retrieve`. Use when the user says "review these requests", "is this in scope?", "should this be a change order?", "pull the request log", "what scope has drifted?", or "turn these emails into scope items".
- **scope-classify** — Runs deterministic `scope_classify.py` after `scope-match` to determine IN_SCOPE, OUT_OF_SCOPE or AMBIGUOUS with the SOW clause quoted. Use when the user says "is this in scope?", "is this out of scope?", "should this be a change order?", "what is ambiguous?", or "where has scope drifted?" before `change-order-draft`.
- **scope-match** — Runs deterministic `scope_match.py` after `request-intake` to match each request to SOW scope, deliverables, assumptions and exclusions. Use when the user asks "which SOW clause applies?", "map this to the SOW", "is this in scope?", "should this be a change order?", or "where has scope drifted?" before `scope-classify`.
- **sow-retrieve** — Retrieves the SOW, MSA, assumptions, exclusions and prior change orders that control scope. Use when the user says "is this in scope?", "should this be a change order?", "check the SOW", "what does the SOW allow?", "where has scope drifted?", or when a Change Order & Scope Control run begins before `request-intake`.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/professional-services/change-order-scope-control/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/professional-services/change-order-scope-control/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
