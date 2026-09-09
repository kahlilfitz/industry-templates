---
name: Product Content & Catalog Enrichment
description: "Turn incomplete supplier data into channel-ready, claim-safe product records: normalise attributes against the taxonomy with GTIN validation, score completeness per channel, validate claims and regulated terms against the approved claim library, and draft the descriptions and review packet."
agentDescription: "Retail Wave 1 Cowork plugin (retailer-side, CPG-enabled): turn incomplete supplier data into channel-ready, claim-safe product records. Ingests supplier sheets and specs; normalises attributes against the taxonomy with GTIN validation (attribute_normalize); scores completeness per channel (completeness_score); validates claims and regulated terms against the approved claim library - the explicit Govern step (claim_check); drafts descriptions and the review packet. Ends at an approval-ready draft record: it does not publish to channel, approve a regulated claim or change the taxonomy."
industry: Retail & CPG
platforms: [Cowork]
type: plugin
tags: [retailer, merchandising, pim, gdsn, gtin, catalog]
author: Industry Templates
authorUrl: "https://github.com/SravaniSeethi"
authorGithub: SravaniSeethi
version: 1.0.0
createdAt: 2026-09-05
updatedAt: 2026-09-08
bundle: bundles/product-content-catalog-enrichment.zip
skills:
  - name: attribute-normalize
  - name: claim-check
  - name: content-draft
  - name: gap-score
  - name: source-ingest
---
Turn incomplete supplier data into channel-ready, claim-safe product records: normalise attributes against the taxonomy with GTIN validation, score completeness per channel, validate claims and regulated terms against the approved claim library, and draft the descriptions and review packet.

> **Retail & CPG template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

## Skills in this package

- **attribute-normalize** — Normalises supplier fields to the taxonomy and validates GTIN check digits with the deterministic attribute_normalize engine. Use after source-ingest, or on "map these to our taxonomy", "are these GTINs valid".
- **claim-check** — Validates marketing claims and regulated terms against the approved claim library - the explicit Govern step - with the deterministic claim_check engine. Use on "is this copy safe", "can we say antibacterial", "check the claims", after gap-score.
- **content-draft** — Drafts channel descriptions, comparison copy and the review/approval packet from the governed payload. Use to close every enrichment batch: "draft the product copy", "build the review packet".
- **gap-score** — Scores per-SKU completeness against the channel's required fields with the deterministic completeness_score engine. Use on "how complete are these", "what's missing per SKU", after attribute-normalize.
- **source-ingest** — Ingests supplier spreadsheets, spec sheets and copy into the rtl.product-content-enrichment.v1 contract. Use when the user says "enrich these SKUs", "supplier sent the item sheet", "get these products channel-ready", or an enrichment batch begins.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/retail-and-cpg/product-content-catalog-enrichment/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/retail-and-cpg/product-content-catalog-enrichment/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
