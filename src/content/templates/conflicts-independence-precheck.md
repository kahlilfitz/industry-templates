---
name: Conflicts & Independence Pre-Check
description: "Assembles a cited first-pass conflicts and independence position for QRM review without clearing, waiving or approving the pursuit."
agentDescription: "Professional Services Cowork plugin: assemble a cited first-pass conflicts and independence pre-check. Resolves entity names and corporate families, searches client/matter/adverse-party/independence registers, classifies conflicts deterministically, and drafts a proposed memo or escalation packet for human QRM review. Draft-first; never clears, waives, accepts or approves a pursuit."
industry: Professional Services
platforms: [Cowork]
type: plugin
tags: [pursuit, risk, compliance, conflicts, independence, qrm, ethical-wall]
author: Kahlil Fitzgerald
authorUrl: "https://github.com/kahlilfitz"
authorGithub: kahlilfitz
version: 1.0.0
createdAt: 2026-09-23
updatedAt: 2026-09-23
bundle: bundles/conflicts-independence-precheck.zip
skills:
  - name: clearance-memo
  - name: conflict-classify
  - name: entity-resolve
  - name: party-intake
  - name: register-search
---
Assembles a cited first-pass conflicts and independence position for QRM review without clearing, waiving or approving the pursuit.

> **Professional Services template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

## Skills in this package

- **clearance-memo** — Drafts a proposed conflicts clearance memo or escalation packet after conflict-classify. Use when the user says "draft the clearance memo", "write the conflicts memo", "prepare the QRM escalation", "can we take this work?", only after classified.json exists.
- **conflict-classify** — Applies deterministic conflicts and independence rules after register-search - the explicit Govern step. Use when the user asks "can we take this work?", "any conflicts?", "any independence issues with this client?", "is an ethical wall enough?", after register-search and before clearance-memo.
- **entity-resolve** — Resolves prospective client names, aliases, trading brands and corporate-family structure for a conflicts check. Use after party-intake when the user says "resolve this client", "who is the parent?", "check affiliates", "any independence issues with this client?", before register-search.
- **party-intake** — Starts a conflicts and independence pre-check from a pursuit record, intake form or email. Use when the user says "run a conflicts check", "can we take this work?", "start independence pre-check", "new pursuit risk review", "check this client and party list", before entity-resolve.
- **register-search** — Searches client, matter, adverse-party and independence registers using resolved legal names, aliases and corporate-family scope. Use after entity-resolve when the user says "search the conflicts system", "check the matter register", "look for adverse parties", before conflict-classify.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/professional-services/conflicts-independence-precheck/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/professional-services/conflicts-independence-precheck/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
