---
name: Deliverable Review & Quality Gate
description: "Check a client-ready deliverable against quality-gate criteria, map assertions to supporting evidence, flag release blockers, and draft a partner review packet with every issue cited."
agentDescription: "Professional Services Cowork plugin: review a draft deliverable before client release. Retrieves the deliverable, support pack and QRM gate criteria; maps assertions to evidence with deterministic assertion_map; determines gate compliance with deterministic gate_check; ranks release blockers, must-fix items and advisories with deterministic severity_rank; drafts a partner review packet. Govern is explicit because release readiness is a firm-risk determination. Draft-first; no sign-off, gate clearance, release approval or substitution for reviewing-partner judgement."
industry: Professional Services
platforms: [Cowork]
type: plugin
tags: [delivery, quality-assurance, qrm, review, substantiation, release-readiness]
author: Kahlil Fitzgerald
authorUrl: "https://github.com/kahlilfitz"
authorGithub: kahlilfitz
version: 1.0.0
createdAt: 2026-09-23
updatedAt: 2026-09-23
bundle: bundles/deliverable-review-quality-gate.zip
skills:
  - name: assertion-map
  - name: criteria-retrieve
  - name: deliverable-ingest
  - name: gate-check
  - name: review-packet
---
Check a client-ready deliverable against quality-gate criteria, map assertions to supporting evidence, flag release blockers, and draft a partner review packet with every issue cited.

> **Professional Services template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

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

A test report and sample prompt set are kept with the source, in [`submissions/professional-services/deliverable-review-quality-gate/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/professional-services/deliverable-review-quality-gate/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
