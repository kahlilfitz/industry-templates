---
name: deliverable-ingest
description: Retrieves and structures the draft deliverable and supporting evidence set for a quality-gate run. Use when the user says "review this deliverable", "is this ready to go to the client?", "run the quality gate", "check the support pack", or at the start of a Deliverable Review & Quality Gate flow before `criteria-retrieve` and `assertion-map`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Deliverable Ingest
## Purpose
Normalize the draft deliverable and support pack into the `ps.deliverable-review-quality-gate.v1` contract: deliverable metadata, located assertions, evidence items, citations and provenance.
## When to use
Start every deliverable quality-gate run here, especially on requests such as "review this deliverable", "is this ready to go to the client?", "what's not substantiated?", or "check the evidence pack".
## Inputs
- Draft deliverable from the engagement workspace or SharePoint.
- Supporting evidence index: models, extracts, minutes, signed client data, workshop notes, prior analysis and third-party content records.
- Prior review notes if supplied.
## Steps
1. Retrieve the deliverable and evidence set without changing source files.
2. Extract candidate assertions with location: section, page, paragraph and label.
3. Classify assertions as factual, quantified, forward-looking/opinion or recommendation; do not decide support.
4. Preserve every citation and source as `connector:` or `skill:` provenance in the contract.
5. Pass the structured payload to `criteria-retrieve`, then `assertion-map`.
## Output
A populated contract input payload with `deliverable`, `assertions`, `evidence_set`, `prior_findings`, confidence, provenance and citations.
## Grounding requirements
Every assertion must carry a deliverable location and citation. Every evidence item must carry source identity, type, confidence and citation.
## Constraints
- Do not judge support, severity or gate clearance in this skill.
- Do not summarize away inconvenient evidence such as verbal estimates or small samples.
- Synthetic demos only; do not introduce real client or firm data.
## Escalation / uncertainty
If the draft, support pack or evidence source cannot be located, record the missing source and stop before analysis rather than inventing support.
