---
name: Time & Expense Narrative Compliance
description: "Draft compliant time-entry narratives from engagement activity, map them to billing codes, and catch rejectable entries before pre-bill review."
agentDescription: "Professional Services Cowork plugin: draft time-entry narratives from engagement-scoped activity, map task and phase codes deterministically, govern narrative compliance against client billing guidelines, surface missing time and pre-bill exceptions, and stop before submission or billing. Draft-first; privacy-narrow signal defaults; every compliance verdict and flag is rules-engine cited."
industry: Professional Services
platforms: [Cowork]
type: plugin
tags: [delivery, billing, time-entry, narrative-compliance, wip, pre-bill]
author: Kahlil Fitzgerald
authorUrl: "https://github.com/kahlilfitz"
authorGithub: kahlilfitz
version: 1.0.0
createdAt: 2026-09-23
updatedAt: 2026-09-23
bundle: bundles/time-expense-narrative-compliance.zip
skills:
  - name: activity-pull
  - name: code-map
  - name: exception-report
  - name: guideline-check
  - name: narrative-draft
---
Draft compliant time-entry narratives from engagement activity, map them to billing codes, and catch rejectable entries before pre-bill review.

> **Professional Services template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

## Skills in this package

- **activity-pull** — Retrieves engagement-scoped calendar, document activity, existing timesheet entries, billing guidelines and codes before narrative drafting. Use first when a user says "write up my time", "find my missing time", "what am I missing this week?", "prepare pre-bill hygiene", or asks to draft time from activity. This runs before `narrative-draft`.
- **code-map** — Maps drafted time narratives to the client's phase and task code structure after `narrative-draft`. Use when the user asks "what code should this use?", "map my time to billing codes", "is this task code wrong?", or before checking whether a narrative will be rejected. Run before `guideline-check`.
- **exception-report** — Creates the engagement-manager pre-bill exception list after `guideline-check`. Use when the user says "show me the pre-bill exceptions", "what needs fixing before billing?", "summarize rejected narratives", "missing time report", or "send my billing coordinator the cleanup list".
- **guideline-check** — Governs drafted and coded time narratives against client billing guidelines after `code-map`. Use when the user asks "will this narrative get rejected?", "check billing guideline compliance", "catch block billing", "find prohibited terms", "what will pre-bill reject?", or "is this time compliant?" Run before `exception-report`.
- **narrative-draft** — Drafts or normalizes time-entry narrative prose from cited activity signals after `activity-pull`. Use when the user says "write up my time", "draft my time entries", "turn my calendar into narratives", or "make these entries client-ready". Run before `code-map`; the model may improve prose, but deterministic output and provenance stay fixed.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/professional-services/time-expense-narrative-compliance/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/professional-services/time-expense-narrative-compliance/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
