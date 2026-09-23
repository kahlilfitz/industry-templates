---
name: Engagement Staffing & Bench Match
description: "Build a defensible ranked staffing slate from engagement requirements, bench availability and independence constraints, with conflicts and gaps made visible before partner approval."
agentDescription: "Professional Services Cowork plugin: build a ranked staffing slate for a signed engagement. Reads the SOW role extract, staffing request, bench roster, availability calendar, rate bands and conflicts register; computes deterministic fit scores and provisional ranks (fit_score, slate_rank); applies independence and availability constraints deterministically (constraint_check) with Govern refusal when a candidate is conflicted or unavailable; drafts a partner-ready recommendation with citations and gap statements. Draft-first; no allocation, assignment, rate change or independence override."
industry: Professional Services
platforms: [Cowork]
type: plugin
tags: [mobilisation, resourcing, staffing, bench, independence, conflicts]
author: Kahlil Fitzgerald
authorUrl: "https://github.com/kahlilfitz"
authorGithub: kahlilfitz
version: 1.0.0
createdAt: 2026-09-23
updatedAt: 2026-09-23
bundle: bundles/engagement-staffing-bench-match.zip
skills:
  - name: bench-query
  - name: constraint-check
  - name: fit-score
  - name: role-intake
  - name: slate-draft
---
Build a defensible ranked staffing slate from engagement requirements, bench availability and independence constraints, with conflicts and gaps made visible before partner approval.

> **Professional Services template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

## Skills in this package

- **bench-query** — Normalizes the bench roster, skills taxonomy, availability, utilisation, location, language and rate data before fit-score. Use when the user says "check the bench", "who is available?", "pull the roster", "include rates", or after role-intake.
- **constraint-check** — Applies independence, conflict, prior-role, ethical-wall and availability constraints after fit-score; explicitly refuses ineligible candidates. Use when the user says "is anyone conflicted?", "can we staff them?", "check independence", "why can't we use the top match?", after fit-score.
- **fit-score** — Computes deterministic fit scores, utilisation context and provisional ranks using fit_score and slate_rank. Use when the user says "rank the bench", "build me a slate", "score the candidates", "who is the best fit?", after bench-query and before constraint-check.
- **role-intake** — Reads a signed engagement, SOW extract, mobilisation note or staffing request into the staffing contract. Use when the user says "new engagement signed", "staff this SOW", "who can we staff on this?", "mobilise this project", or "start a staffing slate".
- **slate-draft** — Drafts the partner-ready staffing recommendation after constraint-check, including ranked eligible slate, refused top matches, conflicts, utilisation context and gap statements. Use when the user says "draft the recommendation", "build me a slate", "send partner approval", or after constraint-check.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/professional-services/engagement-staffing-bench-match/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/professional-services/engagement-staffing-bench-match/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
