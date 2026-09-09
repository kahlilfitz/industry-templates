---
name: Consumer & Market Insight Synthesis
description: "Prior research reused instead of re-commissioned: retrieve and rank prior research and panel extracts, compare trends across markets and periods, flag contradictory evidence rather than smoothing it, check usage rights and claim provenance, and draft a cited insight brief with a provenance record."
agentDescription: "CPG Wave 2 Cowork plugin: prior research reused instead of re-commissioned. Retrieves and ranks prior research and panel extracts; compares trends across markets and periods (trend_compare); flags contradictory evidence rather than smoothing it; checks usage rights, geography and claim provenance - the explicit Govern step (provenance_check); drafts a cited insight brief with a provenance record. Scoped to retrieval, comparison and citation - it does not forecast demand, approve claims or assert causal attribution, and it does not analyse large tabular files."
industry: Retail & CPG
platforms: [Cowork]
type: plugin
tags: [cpg, insights, consumer-research, category, panel, provenance]
author: Industry Templates
authorUrl: "https://github.com/SravaniSeethi"
authorGithub: SravaniSeethi
version: 1.0.0
createdAt: 2026-09-07
updatedAt: 2026-09-08
bundle: bundles/consumer-market-insight-synthesis.zip
skills:
  - name: contradiction-flag
  - name: insight-brief
  - name: provenance-check
  - name: research-retrieve
  - name: trend-compare
---
Prior research reused instead of re-commissioned: retrieve and rank prior research and panel extracts, compare trends across markets and periods, flag contradictory evidence rather than smoothing it, check usage rights and claim provenance, and draft a cited insight brief with a provenance record.

> **Retail & CPG template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

## Skills in this package

- **contradiction-flag** — Surfaces contradictory evidence - studies moving the same metric in opposite directions - rather than a smoothed answer. Use on "do the studies agree", "any conflicting evidence", after trend-compare.
- **insight-brief** — Drafts the cited insight brief with the provenance and usage-rights record attached. Use to close every insight run: "draft the brief", "write it up for the category review".
- **provenance-check** — Checks usage rights, geography and expiry for every retrieved study against the declared use - the explicit Govern step - with the deterministic provenance_check engine. Use on "can we use this externally", "is this stat cleared for the board deck", after trend-compare.
- **research-retrieve** — Retrieves and ranks prior research, panel extracts and campaign results relevant to the question. Use when the user says "what do we already know about <topic>", "find prior research on", "have we studied this before", or an insight request begins.
- **trend-compare** — Compares trends across markets and periods like-for-like with the deterministic trend_compare engine. Use on "how has this trended", "compare markets", "what changed since the last study", after research-retrieve.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/consumer-market-insight-synthesis/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/consumer-market-insight-synthesis/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
