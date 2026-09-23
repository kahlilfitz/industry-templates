---
name: artifact-assemble
description: Retrieves and normalizes the engagement artifact set, deliverable register, decision log, status history, retrospective notes and confidentiality terms for closeout. Use when the user says "close out the engagement", "assemble the final deliverables", "harvest lessons learned", "what can we reuse from this?", or when an engagement closeout begins before asset-identify.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Closeout & Knowledge Management
---
# Artifact Assemble
## Purpose
Turn messy closeout inputs into the `ps.engagement-closeout-knowledge-harvest.v1` contract: engagement context, deliverable register, candidate reusable assets, decision log, retrospective inputs and confidentiality terms.
## When to use
At the start of every closeout harvest, before `asset-identify`. Use it for requests like "close out the engagement", "assemble the final package", "load the decision log", "bring in the retrospective" or "what can we reuse from this?".
## Inputs
- Engagement workspace or SharePoint artifact set.
- Deliverable register, status history and acceptance notes.
- Decision and risk logs.
- Retrospective transcript or survey notes.
- Client confidentiality terms extract.
- Firm knowledge taxonomy and prior knowledge records.
## Steps
1. Confirm the engagement identifier, closeout date and source workspace.
2. Extract each required deliverable with status, owner, confidence, source and citation.
3. Extract candidate assets with reuse signals: generalisability, effort to recreate, shelf life and client-specific dependency.
4. Preserve confidentiality markers and aggregation tokens; do not decide clearance here.
5. Structure decision log and retrospective inputs with citations and any named-person markers.
6. Write the contract entry payload for `asset-identify`.
## Output
A populated `ps.engagement-closeout-knowledge-harvest.v1` JSON payload ready for `asset-identify`.
## Grounding requirements
Every artifact, decision, retrospective entry and confidentiality term carries `confidence`, `source` matching `^(engine|skill|connector):`, and a citation to the originating file, row, transcript line or clause.
## Constraints
- Do not score reuse value; `asset-identify` does that.
- Do not cluster lessons; `lesson-cluster` does that.
- Do not decide whether content may leave the engagement boundary; `sanitize-check` does that.
- Synthetic demos only; never introduce real client or personal data into a package.
## Escalation / uncertainty
If required deliverables are missing, source identity is ambiguous or confidentiality terms are unavailable, preserve the gap in the payload and escalate rather than filling it from memory.
