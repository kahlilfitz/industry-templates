---
name: notes-ingest
description: Retrieves and normalizes discovery notes, scoping notes, CRM pursuit records, prior similar SOWs, approved clause library extracts and SOW templates before `scope-extract`. Use when the user says "draft the SOW", "turn these notes into a statement of work", "start from this discovery call", "use this pursuit record", or "copy this prior SOW but check it".
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Pursuit Contracting
---
# Notes Ingest
## Purpose
Collect the messy pursuit inputs and normalize them into the `ps.sow-drafting-scoping-notes.v1` contract without making scope, clause or QRM determinations.
## When to use
Start every SOW Drafting from Scoping Notes run here, especially when the user provides discovery-call notes, CRM pursuit records, prior executed SOWs, an approved clause library or the firm's SOW template.
## Inputs
- Discovery-call transcript, scoping notes, workshop notes or pursuit lead email.
- CRM pursuit record: client, project, lifecycle stage, commercial context and key dates.
- Prior similar SOWs and MSA/SOW template excerpts.
- Approved clause library extract and QRM deviation rules.
- Rate card or pricing context for citation only; pricing is out of scope.
## Steps
1. Retrieve and cite each input document; preserve document IDs, versions and dates.
2. Extract candidate facts into `evidence[]` with `key`, `value`, `source`, `citation` and `confidence`.
3. Extract prior SOW terms into `prior_sow_terms[]`; mark one-off or client-specific approvals when the prior document says so.
4. Preserve the clause library payload exactly as retrieved. Do not paraphrase approved clauses into new language.
5. Hand the normalized contract input to `scope-extract`.
## Output
`ingested.json` under contract `ps.sow-drafting-scoping-notes.v1`.
## Grounding requirements
Every fact must cite the raw source line, transcript turn, CRM field or prior SOW clause. Prior SOW terms are evidence for deviation checks, not drafting source language.
## Constraints
- No clause selection, deviation grading or commitment drafting in this skill.
- Never treat a prior SOW as approved language.
- Never infer missing acceptance criteria, client obligations, test-data ownership or delivery dates from enthusiasm in notes.
## Escalation / uncertainty
If source documents conflict or the clause library cannot be identified as approved and versioned, keep the evidence but flag the run for degraded extraction-only handling in `clause-select`.
