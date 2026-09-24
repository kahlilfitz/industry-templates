---
name: constraint-check
description: Applies independence, conflict, prior-role, ethical-wall and availability constraints after fit-score; explicitly refuses ineligible candidates. Use when the user says "is anyone conflicted?", "can we staff them?", "check independence", "why can't we use the top match?", after fit-score.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Constraint Check (Govern)
## Purpose
Apply `references/independence-eligibility-rules.md` deterministically. This is the explicit Govern step: each candidate-role pair receives an eligibility verdict, blocking rule, citations and refusal rationale where applicable.
## When to use
After `fit-score` in every run, and on any question about independence, conflicts, ethical walls, prior roles or availability clearance.
## Inputs
`ranked.json` + `constraints.json` using contract `ps.engagement-staffing-bench-match.v1`.
## Steps
1. Validate the ranked payload and conflicts/constraints extract.
2. Run `scripts/constraint_check.py --ranked ranked.json --constraints constraints.json --out governed.json`.
3. Quote eligibility verdicts, blocking rules, availability calculations and gap statements verbatim.
4. If the top provisional candidate is ineligible, lead with the refusal and cite the rule. It is not overrideable by prose, schedule pressure or partner preference.
5. Hand off `governed.json` to `slate-draft`.
## Output
`governed.json` with `governed_roles[]`, eligibility per candidate, final eligible ranks, refusals, escalations and gap statements.
## Grounding requirements
Every refusal cites the conflicts record or availability record and the rule section. The model must keep the clause with the candidate name.
## Constraints
- The engine decides; the model never clears a conflict, waives independence, assigns a person or changes `ineligible` to `eligible`.
- Ineligible candidates cannot appear in the recommended slate.
- Availability includes approved leave and soft-booked pursuits even when base allocation is 0%.
## Escalation / uncertainty
`needs_review` is not eligible. Route it to independence or resource management review and draft an exception request only if asked; never grant the exception.
