---
name: Customer Service & Order Support
description: "A grounded first response, and a clean escalation packet when it cannot resolve: classify intent against the taxonomy, assemble customer, order, loyalty and delivery context while detecting contradictions, retrieve the approved answer, and draft the resolution in channel and tone."
agentDescription: "Retail Wave 1 Cowork plugin: a grounded first response, and a clean escalation packet when it cannot resolve. Classifies intent against the taxonomy (intent_classify); assembles customer, order, loyalty and delivery context and detects contradictions (context_assemble); retrieves the approved answer; drafts the resolution in channel and tone or builds the structured handoff packet. Reliability beats reach: it does not issue goodwill credit, change payment details or grant unsupported policy exceptions."
industry: Retail & CPG
platforms: [Cowork]
type: plugin
tags: [retailer, customer-service, contact-centre, wismo, intent, escalation]
author: Industry Templates
authorUrl: "https://github.com/SravaniSeethi"
authorGithub: SravaniSeethi
version: 1.0.1
createdAt: 2026-09-05
updatedAt: 2026-09-08
bundle: bundles/customer-service-order-support.zip
skills:
  - name: context-assemble
  - name: handoff-packet
  - name: inquiry-intake
  - name: knowledge-retrieve
  - name: resolution-draft
---
A grounded first response, and a clean escalation packet when it cannot resolve: classify intent against the taxonomy, assemble customer, order, loyalty and delivery context while detecting contradictions, retrieve the approved answer, and draft the resolution in channel and tone.

> **Retail & CPG template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

## Skills in this package

- **context-assemble** — Assembles customer, order, loyalty and carrier context, detects record-vs-account contradictions, and selects the resolution path deterministically with the context_assemble engine. Use after inquiry-intake, or on "pull up everything on this order".
- **handoff-packet** — Builds the structured escalation packet when the run cannot resolve - intent, context, contradictions, what was checked, recommended next step. Use on any low-confidence, contradicted, or out-of-scope run: "escalate this", "hand off to tier 2".
- **inquiry-intake** — Takes the customer inquiry from any channel and classifies intent against the taxonomy with the deterministic intent_classify engine. Use when a service inquiry arrives - "where is my order", "it says delivered but I never got it", "can I return this", "is it in stock", "how do I set this up".
- **knowledge-retrieve** — Retrieves the approved knowledge article, policy text or product doc that grounds the answer for the classified intent. Use after context-assemble, or on "what's the approved answer for this".
- **resolution-draft** — Drafts the customer-facing resolution in the right channel and tone from the assembled context and approved sources. Use to close resolvable runs - "draft the reply", "answer the customer".

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/retail-and-cpg/customer-service-order-support/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/retail-and-cpg/customer-service-order-support/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
