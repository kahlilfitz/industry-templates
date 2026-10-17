---
name: sow-draft
description: Drafts the review-ready SOW, thin-input report and QRM deviation summary after `deviation-flag` using only selected approved clauses and engine output. Use when the user says "draft the SOW", "write the statement of work", "create the SOW package", "show the thin-input report", or after `deviation-flag`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: writing
---
# SOW Draft
## Purpose
Produce the terminal draft artifact: a structured SOW, thin-input report and QRM deviation summary using `templates/sow-template.md`.
## When to use
After `deviation-flag` completes, or when the user requests the draft SOW package.
## Inputs
`deviation-summary.json` under contract `ps.sow-drafting-scoping-notes.v1`.
## Steps
1. Validate that `selected_clauses[]`, `scope.thin_input_report[]`, `assumptions[]`, `exclusions[]` and `deviations[]` are present.
2. Fill `templates/sow-template.md`: engagement summary, scope, deliverables, milestones, acceptance, assumptions, exclusions, selected clauses, thin-input report and QRM deviation summary.
3. Draft only from approved clauses with `draft_allowed=true`.
4. For `thin_input_blocked` clauses, include a visible placeholder and the thin-input item; do not write commitment prose.
5. Mark the SOW DRAFT - pending partner, QRM and legal review where applicable.
## Output
`SOW-<pursuit_id>-draft.md` plus a deviation summary and thin-input report embedded in the draft package.
## Grounding requirements
Every clause quotes the approved library ID/version. Every commitment cites discovery evidence. Every deviation cites QRM rules. Every blocked commitment cites the thin-input rule.
## Constraints
- Draft-first: no issuance, no signature workflow, no CRM or contract-repository write-back.
- The model never approves a deviation, prices the engagement or commits a delivery date.
- Nothing appears in the SOW that is not present in the contract payload or selected approved library clause.
## Escalation / uncertainty
If any critical deviation or thin-input block exists, lead the draft with an "Open before issuance" section and present the SOW as review-ready only, not client-ready.
