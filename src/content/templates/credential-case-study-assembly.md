---
name: Credential & Case Study Assembly
description: "Draft case-study credentials from fresh closeout records while deterministically refusing uncleared client names, testimonials and outcome figures."
agentDescription: "Professional Services Cowork plugin: consumes the sanitised closeout knowledge record from Engagement Closeout & Knowledge Harvest, matches it to a credential taxonomy, checks client naming/reference permissions with deterministic permission_check governance, and drafts credential and case-study variants. Draft-first; it does not publish, approve external use, clear a client name or assert unverified figures."
industry: Professional Services
platforms: [Cowork]
type: plugin
tags: [closeout, business-development, credentials, case-study, reference-permissions, anonymisation]
author: Kahlil Fitzgerald
authorUrl: "https://github.com/kahlilfitz"
authorGithub: kahlilfitz
version: 1.0.0
createdAt: 2026-09-23
updatedAt: 2026-09-23
bundle: bundles/credential-case-study-assembly.zip
skills:
  - name: anonymize-variant
  - name: closeout-retrieve
  - name: credential-draft
  - name: credential-record
  - name: permission-check
---
Draft case-study credentials from fresh closeout records while deterministically refusing uncleared client names, testimonials and outcome figures.

> **Professional Services template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

## Skills in this package

- **anonymize-variant** — Produces the anonymised credential and case-study variant after `permission-check` refuses naming or flags a descriptor as re-identifying. Use when the user says "make it anonymous", "we cannot name the client", "sanitize this credential", "can we describe them as a top-five insurer?", or after `permission-check` sets `anonymised_variant_required=true`.
- **closeout-retrieve** — Retrieves the sanitised closeout knowledge record, deliverables, outcome evidence, engagement terms and reference register before Credential & Case Study Assembly begins. Use when the user says "write up this credential", "do we have a case study for this?", "pull the closeout record", "turn this closeout into a credential", or when a credential/case-study request begins. This runs before `credential-draft`.
- **credential-draft** — Matches a closeout record to the credential taxonomy and prepares the structured draft plan before permissions are checked. Use after `closeout-retrieve` when the user says "write up this credential", "draft the case study", "make this proposal credential", or "classify this engagement for credentials"; run before `permission-check`.
- **credential-record** — Drafts the final credential entry and short, medium and long case-study copy after `permission-check` and optional `anonymize-variant`. Use when the user says "write the credential record", "draft the case study", "make the short and long versions", "prepare this for the credentials library", or "do we have a case study for this?".
- **permission-check** — Determines whether the client can be named, whether logo/testimonial use is allowed, which figures are cleared, and whether an anonymised descriptor re-identifies the client. Use after `credential-draft` when the user asks "can we name this client?", "is this case study cleared?", "can we use this quote?", "can this go on the website?", or before any credential/case-study copy is published.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/professional-services/credential-case-study-assembly/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/professional-services/credential-case-study-assembly/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
