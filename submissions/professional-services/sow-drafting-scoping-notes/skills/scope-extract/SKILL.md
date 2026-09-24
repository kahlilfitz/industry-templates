---
name: scope-extract
description: Runs deterministic `scope_extract.py` after `notes-ingest` to extract scope, deliverables, milestones, assumptions, exclusions and the thin-input report. Use when the user says "what did we scope?", "what did we not pin down?", "turn these notes into a statement of work", "draft the SOW", or after `notes-ingest` finishes.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Scope Extract
## Purpose
Apply deterministic thin-input rules to the normalized pursuit evidence and produce the SOW structure: scope, deliverables, milestones, acceptance criteria, assumptions, exclusions and blocked commitments.
## When to use
After `notes-ingest` in every run, before any clause selection or SOW drafting.
## Inputs
`ingested.json` under contract `ps.sow-drafting-scoping-notes.v1`.
## Steps
1. Validate that each evidence item carries source, citation and confidence.
2. Run `scripts/scope_extract.py --input ingested.json --out scope.json`.
3. Quote the engine output exactly for thin-input calls. The model may organize prose but never turns a blocked item into a commitment.
4. Carry `thin_input_report[]`, `assumptions[]` and `exclusions[]` forward to `clause-select`.
5. Treat verbal dates without plan evidence as planning targets only.
## Output
`scope.json` with `scope.deliverables[]`, `scope.milestones[]`, `scope.acceptance_criteria[]`, `scope.assumptions[]`, `scope.exclusions[]`, `scope.thin_input_report[]` and escalations.
## Grounding requirements
Every extracted item cites the discovery notes, CRM pursuit record or prior document that supports it. Every thin-input item cites the QRM rule that blocked drafting.
## Constraints
- Thin-input determination is rules-engine-only.
- Assumptions and exclusions are derived from what the notes did not establish; do not add generic boilerplate.
- Unsupported milestone dates stay non-committal planning targets.
## Escalation / uncertainty
Any blocked commitment tied to acceptance, test data, client obligations or milestones must be surfaced before drafting and routed to the pursuit lead.
