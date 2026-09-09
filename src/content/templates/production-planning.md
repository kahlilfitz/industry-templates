---
name: Production Planning
description: "Turn demand into a publishable shift plan: pull the forecast and open orders, check capacity, constraints and material availability, sequence the week to minimise changeovers with a deterministic campaign heuristic, and draft the shift plan for the planner to publish."
agentDescription: "Manufacturing Wave 2 Cowork plugin - the heaviest build in the set. Pulls the demand forecast and open orders; checks capacity, constraints and material availability (capacity_check engine); optimizes the weekly sequence for changeovers with a deterministic campaign heuristic (sequence_optimize engine); drafts the shift plan for the planner to publish. Draft-first, document-grounded; a live solver/APS is the graduation, not v1."
industry: Manufacturing
platforms: [Cowork]
type: plugin
tags: [operations, scheduling, production-planning, changeover, capacity]
author: Industry Templates
authorUrl: "https://github.com/SravaniSeethi"
authorGithub: SravaniSeethi
version: 1.0.0
createdAt: 2026-09-01
updatedAt: 2026-09-04
bundle: bundles/production-planning.zip
skills:
  - name: capacity-check
  - name: demand-pull
  - name: schedule-optimize
  - name: shift-plan-draft
---
Turn demand into a publishable shift plan: pull the forecast and open orders, check capacity, constraints and material availability, sequence the week to minimise changeovers with a deterministic campaign heuristic, and draft the shift plan for the planner to publish.

> **Manufacturing template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

## Skills in this package

- **capacity-check** — Checks capacity, constraints and material availability for the plan week with the deterministic capacity_check engine. Use when the user says "do we have capacity", "does the week fit", "check materials", or after demand-pull in a planning run.
- **demand-pull** — Pulls the demand forecast and open orders for the plan week into the mfg.production-planning.v1 contract. Use when the user says "plan next week", "build the schedule", "pull the orders for line <x>", or when a planning run begins.
- **schedule-optimize** — Optimizes the weekly sequence for changeovers with the deterministic campaign heuristic - naive vs optimized compared side by side - using the sequence_optimize engine. Use when the user says "optimize the schedule", "sequence the week", "minimize changeovers", or after capacity-check in a planning run.
- **shift-plan-draft** — Drafts the shift plan from the optimized schedule for the planner to review and publish. Use when the user says "draft the shift plan", "write up the week", "publish the plan" (which produces the draft), or after schedule-optimize in a planning run.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/manufacturing/production-planning/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/manufacturing/production-planning/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
