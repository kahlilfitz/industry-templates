---
name: sow-retrieve
description: Retrieves the SOW, MSA, assumptions, exclusions and prior change orders that control scope. Use when the user says "is this in scope?", "should this be a change order?", "check the SOW", "what does the SOW allow?", "where has scope drifted?", or when a Change Order & Scope Control run begins before `request-intake`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# SOW Retrieve
## Purpose
Collect the controlling commercial documents and preserve numbered clauses exactly enough for downstream deterministic engines to cite them.
## When to use
Start every Change Order & Scope Control run here, before `request-intake`.
## Inputs
- SOW or SOW excerpt with numbered scope, deliverable, assumption and exclusion clauses.
- MSA or change-control excerpt.
- Prior change orders and no-charge accommodation notes.
- Contract repository or SharePoint document identifiers.
## Steps
1. Retrieve the SOW as the controlling document and record document id, revision, effective date and clause citations.
2. Extract clauses into the shared contract `ps.change-order-scope-control.v1`: `id`, `title`, `type`, `quote`, `tags`, `citation`, `source`, `confidence`.
3. Retrieve the MSA only for change-control mechanics. Do not let it override the SOW scope boundary.
4. Retrieve prior change orders and mark no-charge accommodations with internal cost when available for cumulative drift.
5. Hand the structured SOW packet to `request-intake`.
## Output
Structured SOW/MSA/prior-change-order payload under contract `ps.change-order-scope-control.v1`.
## Grounding requirements
Every clause carries a numbered citation and a short quote. Use `source=connector:<repository>` for retrieved documents and `source=skill:sow-retrieve` for extracted fields.
## Constraints
- The SOW is the source of authority for scope.
- Do not classify requests here; classification belongs to `scope-classify`.
- Do not create or issue a change order.
## Escalation / uncertainty
If the SOW revision is unclear, clauses are unnumbered, or the MSA conflicts with the SOW on scope, stop the chain and route to the engagement partner or contract manager.
