---
name: Maintenance Triage
description: "Move a fault forward: read the fault note, alarm codes and asset history, rank the likely failure modes against OEM manuals and past work orders, prioritise by asset criticality and downtime cost, and draft the work-order update with a recommended action."
agentDescription: "Manufacturing Wave 1 Cowork plugin: move a fault forward. Reads fault notes, alarm codes and asset history; identifies the likely failure mode from OEM manuals and past work orders (deterministic fault_rank); prioritizes by asset criticality and downtime cost (deterministic criticality_score); and drafts the work-order update with the recommended action. Draft-first; document-grounded, historian optional. NOT predictive maintenance (that is Wave 3)."
industry: Manufacturing
platforms: [Cowork]
type: plugin
tags: [maintenance, triage, cmms, reliability, failure-mode, work-order]
author: Industry Templates
authorUrl: "https://github.com/SravaniSeethi"
authorGithub: SravaniSeethi
version: 1.0.0
createdAt: 2026-08-01
updatedAt: 2026-09-04
bundle: bundles/maintenance-triage.zip
skills:
  - name: criticality-rank
  - name: failure-mode-rank
  - name: fault-intake
  - name: history-retrieve
  - name: work-order-update
featured: true
---
Move a fault forward: read the fault note, alarm codes and asset history, rank the likely failure modes against OEM manuals and past work orders, prioritise by asset criticality and downtime cost, and draft the work-order update with a recommended action.

> **Manufacturing template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

## Skills in this package

- **criticality-rank** — Prioritizes the fault by asset criticality and downtime cost into a P1-P4 maintenance priority with a response target and cost estimate, deterministically. Use when the user says "how urgent is this", "what's the priority", "rank by criticality", "what will downtime cost", or after failure-mode-rank completes.
- **failure-mode-rank** — Ranks the likely failure modes for a fault against the failure-mode library, symptoms, alarm codes and repeat-failure history, deterministically. Use when the user says "what's the likely cause", "rank the failure modes", "diagnose this fault", "is this the real root cause?", or after history-retrieve completes.
- **fault-intake** — Reads maintenance fault notes, operator reports, alarm/event logs, asset IDs and location into the mfg.maintenance-triage.v1 contract inputs. Use when the user says "triage this fault", "work this breakdown", "read the fault note for <asset>", "what's wrong with pump <id>", or when a maintenance triage run begins.
- **history-retrieve** — Retrieves the asset's maintenance history — prior work orders, similar failures, PM records — and the relevant OEM manual and troubleshooting sections, and attaches them to the mfg.maintenance-triage.v1 contract. Use when the user says "pull the history for <asset>", "has this failed before?", "find the manual section", "any prior work orders?", or after fault-intake completes.
- **work-order-update** — Drafts the work-order update and recommended action from the triaged contract payload, with every determination cited to the manual, history and rules. Use when the user says "draft the work order", "write up the WO update", "what should we do", "recommend the fix", or after criticality-rank completes.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/maintenance-triage/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/maintenance-triage/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
