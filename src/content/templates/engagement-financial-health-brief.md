---
name: Engagement Financial Health Brief
description: "Compute engagement economics on fixed practice definitions, explain the largest financial drivers, and draft a review-ready health brief before unbilled exposure becomes invisible."
agentDescription: "Professional Services Cowork plugin for delivery commercial control. Retrieves engagement financials, WIP, time, expense, plan, budget, rate-card and benchmark records; deterministically computes fixed-definition health indicators with health_calc; deterministically decomposes the largest variances with driver_attribute; refuses misleading benchmark comparisons when metric definition sets differ; and drafts a cited financial health brief for engagement or practice review. Draft-first; no WIP adjustment, write-off, rate change, reforecast or system write-back."
industry: Professional Services
platforms: [Cowork]
type: plugin
tags: [delivery, commercial-control, engagement-economics, realisation, utilisation, wip]
author: Kahlil Fitzgerald
authorUrl: "https://github.com/kahlilfitz"
authorGithub: kahlilfitz
version: 1.0.0
createdAt: 2026-09-23
updatedAt: 2026-09-23
bundle: bundles/engagement-financial-health-brief.zip
skills:
  - name: benchmark-compare
  - name: brief-draft
  - name: driver-attribute
  - name: financials-pull
  - name: health-calc
---
Compute engagement economics on fixed practice definitions, explain the largest financial drivers, and draft a review-ready health brief before unbilled exposure becomes invisible.

> **Professional Services template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

## Skills in this package

- **benchmark-compare** — Runs after health-calc and driver-attribute to compare health indicators against practice benchmarks only when the metric definition sets match. Use when the user asks "how does this compare to the practice?", "is this engagement above benchmark?", "show benchmark context", or after health-calc produces benchmark eligibility or refusal.
- **brief-draft** — Drafts the engagement financial health brief after health-calc, driver-attribute and benchmark-compare. Use when the user says "draft the brief", "write the engagement review", "prepare the practice review note", "summarize why margin is down", or "are we going to make our number?
- **driver-attribute** — Runs after health-calc to decompose the largest variance and rank the drivers with driver_attribute. Use when the user says "why is margin down?", "what is driving the variance?", "explain the WIP problem", "what changed versus plan?", or after health-calc flags amber or red indicators.
- **financials-pull** — Pulls engagement financials, WIP ageing, billing, time, expense, plan, budget, rate-card and practice benchmark records into the ps.engagement-financial-health-brief.v1 contract. Use when the user says "how is this engagement doing?", "pull the engagement financials", "are we going to make our number?", "prep the practice review", or when an engagement financial health run begins.
- **health-calc** — Runs after financials-pull to compute fixed-definition health indicators, RAG status, WIP ageing, unbilled exposure, burn, realisation, utilisation, ETC/EAC and early-warning flags with health_calc. Use when the user asks "what is the health?", "why does the dashboard say green?", "are we going to make our number?", "what is our WIP exposure?", or after the engagement records are pulled.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/professional-services/engagement-financial-health-brief/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/professional-services/engagement-financial-health-brief/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
