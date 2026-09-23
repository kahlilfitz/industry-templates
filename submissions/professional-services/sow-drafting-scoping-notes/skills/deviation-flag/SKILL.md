---
name: deviation-flag
description: Runs deterministic `deviation_flag.py` after `clause-select` to compare selected approved clauses with requested or inherited prior-SOW terms and produce the QRM deviation summary. Use when the user says "check deviations", "can we copy this prior SOW?", "what needs QRM?", "is this clause approved?", or after `clause-select`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Pursuit Contracting
---
# Deviation Flag
## Purpose
Determine deviation severity and review route for inherited or requested non-standard clause language.
## When to use
After `clause-select`, especially when a prior similar SOW or requested client edits are present.
## Inputs
`selected-clauses.json` under contract `ps.sow-drafting-scoping-notes.v1`, including `selected_clauses[]`, `prior_sow_terms[]` and `scope.thin_input_report[]`.
## Steps
1. Validate that each selected clause carries library ID, version, deviation state, source, citation and confidence.
2. Run `scripts/deviation_flag.py --clauses selected-clauses.json --out deviation-summary.json`.
3. Quote each deviation exactly: family, severity, route, inherited clause summary, approved library clause and rule citation.
4. Preserve thin-input blocks as drafting blocks; do not convert them into approved deviations.
5. Hand `deviation-summary.json` to `sow-draft`.
## Output
`deviation-summary.json` with `deviations[]`, updated `selected_clauses[]`, `deviation_summary` and escalations.
## Grounding requirements
Every deviation cites the approved library ID/version and the QRM rule section. One-off prior approvals must be marked non-portable unless re-approved.
## Constraints
- Deviation severity is rules-engine-only.
- The model never approves, downgrades or suppresses a deviation.
- A client-favourable prior SOW is evidence of risk, not reusable approved language.
## Escalation / uncertainty
Critical deviations require QRM, legal and engagement partner review. Major deviations require partner and QRM review. Thin-input blocks require pursuit follow-up before the SOW can contain that commitment.
