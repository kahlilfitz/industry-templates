---
name: Client Status & QBR Assembly
description: "Assemble client-ready status packs and QBR narratives from plan, burn, risk, decision and action records, with variances and ageing computed before the draft is written."
agentDescription: "Professional Services Cowork plugin: assemble recurring client status packs and QBR narrative drafts. Retrieves plans, prior status, budget burn, risks, decisions and actions; computes schedule/budget/scope variance (deterministic variance_calc) and item ageing/client-action separation (deterministic item_age); drafts a client-ready pack with every variance and escalation cited. Draft-first; no write-back, no send, no re-baseline."
industry: Professional Services
platforms: [Cowork]
type: plugin
tags: [delivery, client-reporting, status-pack, qbr, variance, engagement-management]
author: Kahlil Fitzgerald
authorUrl: "https://github.com/kahlilfitz"
authorGithub: kahlilfitz
version: 1.0.0
createdAt: 2026-09-23
updatedAt: 2026-09-23
bundle: bundles/client-status-qbr.zip
skills:
  - name: burn-pull
  - name: plan-retrieve
  - name: risk-summarize
  - name: status-draft
  - name: variance-calc
---
Assemble client-ready status packs and QBR narratives from plan, burn, risk, decision and action records, with variances and ageing computed before the draft is written.

> **Professional Services template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

## Skills in this package

- **burn-pull** — Pulls and normalizes time, budget, billed burn, unbilled WIP, accrual and forecast records for Client Status & QBR Assembly. Runs after plan-retrieve. Use when the user says "where are we on budget?", "why did burn change?", "get the burn numbers into the payload" or "pull the finance export". Keeps billed and unbilled WIP strictly separate, carries a per-field citation for every figure, and escalates when WIP movement cannot be sourced from the prior pack rather than inferring a baseline. Do NOT start a status run or assemble the pack — use plan-retrieve. Do NOT compute variance or RAG — use variance-calc. Do NOT age risks or decisions — use risk-summarize. Do NOT write the client narrative — use status-draft.
- **plan-retrieve** — Retrieves and structures the engagement plan, milestone schedule, prior status packs and client reporting template for Client Status & QBR Assembly. Entry step for a status or QBR run. Use when the user says "build the status pack", "prepare the weekly status", "start the status run" or "draft the QBR". Extracts milestones with baseline and forecast dates, prior-period RAG and open change requests, citing every field to its source line; flags rebaselined milestones and items absent from the prior pack instead of dropping them. Do NOT use for budget or burn figures — use burn-pull. Do NOT compute variance or RAG — use variance-calc. Do NOT age risks or decisions — use risk-summarize. Do NOT write the client narrative — use status-draft.
- **risk-summarize** — Ages risks, decisions and actions and separates pending client actions for Client Status & QBR Assembly. Runs after variance-calc. Use when the user says "show open risks", "what decisions are pending?", "what is waiting on the client?" or "summarize actions with ageing". Delegates ageing to scripts/item_age.py and quotes it verbatim; reclassifies an action blocked by a client decision as a pending client action, and flags items whose stated status contradicts their age instead of accepting the label. Do NOT start a status run — use plan-retrieve. Do NOT pull budget or burn — use burn-pull. Do NOT compute variance or RAG — use variance-calc. Do NOT write the client narrative — use status-draft.
- **status-draft** — Drafts the client status pack and QBR narrative from computed variance and aged-item outputs for Client Status & QBR Assembly. Final step; runs after risk-summarize. Use when the user says "draft the client update", "write the steering committee pack", "prepare the client-ready narrative" or "draft the QBR narrative". Always emits a labelled DRAFT for human review and never sends it, places escalations above the narrative and quotes engine figures exactly — retaining both even when the user asks for something client-ready. Do NOT start a status run or assemble sources — use plan-retrieve. Do NOT pull budget or burn — use burn-pull. Do NOT compute variance or RAG — use variance-calc. Do NOT age risks or decisions — use risk-summarize.
- **variance-calc** — Computes period-over-period schedule, budget and scope variance with deterministic RAG for Client Status & QBR Assembly. Runs after plan-retrieve and burn-pull. Use when the user says "calculate the variance", "why is the status red?", "what changed since last week?" or "give me schedule, budget and scope RAG". Delegates every threshold and calculation to scripts/variance_calc.py and quotes the engine output verbatim rather than restating it; surfaces masked slippage where a rebaseline hides variance against the original baseline. Do NOT start a status run — use plan-retrieve. Do NOT pull finance or burn data — use burn-pull. Do NOT age risks or decisions — use risk-summarize. Do NOT write the client narrative — use status-draft.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/professional-services/client-status-qbr/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/professional-services/client-status-qbr/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
