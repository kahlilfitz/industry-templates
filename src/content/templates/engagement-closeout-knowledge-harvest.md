---
name: Engagement Closeout & Knowledge Harvest
description: "Capture reusable value at closeout by assembling deliverables, clustering lessons, ranking reusable assets, and drafting a sanitised knowledge record with confidentiality holds visible."
agentDescription: "Professional Services Cowork plugin: close out an engagement before the team disperses. Retrieves the artifact set, deliverable register, decision log and retrospective inputs; assembles a final deliverable index; scores reusable assets with asset_identify; clusters lessons with lesson_cluster; performs an explicit confidentiality Govern gate with sanitize_check; drafts a sanitised knowledge record for practice review. Draft-first; never publishes to a knowledge base, clears a confidentiality restriction, approves external use or waives a client term. The knowledge record is shaped for downstream Credential & Case Study Assembly."
industry: Professional Services
platforms: [Cowork]
type: plugin
tags: [closeout, knowledge-management, lessons-learned, sanitisation, confidentiality, reuse]
author: Kahlil Fitzgerald
authorUrl: "https://github.com/kahlilfitz"
authorGithub: kahlilfitz
version: 1.0.0
createdAt: 2026-09-23
updatedAt: 2026-09-23
bundle: bundles/engagement-closeout-knowledge-harvest.zip
skills:
  - name: artifact-assemble
  - name: asset-identify
  - name: knowledge-record
  - name: lesson-cluster
  - name: sanitize-check
---
Capture reusable value at closeout by assembling deliverables, clustering lessons, ranking reusable assets, and drafting a sanitised knowledge record with confidentiality holds visible.

> **Professional Services template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

## Skills in this package

- **artifact-assemble** — Retrieves and normalizes the engagement artifact set, deliverable register, decision log, status history, retrospective notes and confidentiality terms for closeout. Use when the user says "close out the engagement", "assemble the final deliverables", "harvest lessons learned", "what can we reuse from this?", or when an engagement closeout begins before asset-identify.
- **asset-identify** — Scores candidate reusable assets and builds the final deliverable index with completeness gaps using the deterministic asset_identify engine. Use after artifact-assemble when the user asks "what can we reuse from this?", "find reusable assets", "shortlist closeout assets", or "is the final deliverable package complete?".
- **knowledge-record** — Drafts the knowledge record, lessons-learned narrative and sanitisation report after sanitize-check, using only governed release candidates. Use after sanitize-check when the user says "draft the knowledge record", "prepare for practice review", "write the closeout summary", "package this for reuse", or asks about the downstream credential-case-study-assembly handoff.
- **lesson-cluster** — Clusters decisions and retrospective inputs into lesson themes with the deterministic lesson_cluster engine. Use after asset-identify when the user says "lessons learned", "cluster the retrospective", "what did we learn?", or "write the closeout lessons".
- **sanitize-check** — Determines what may leave the engagement boundary using the deterministic sanitize_check Govern engine. Use after lesson-cluster when the user asks "can we share this externally?", "is this safe to reuse?", "sanitise the closeout record", "remove client-confidential material", or before knowledge-record.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/professional-services/engagement-closeout-knowledge-harvest/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/professional-services/engagement-closeout-knowledge-harvest/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
