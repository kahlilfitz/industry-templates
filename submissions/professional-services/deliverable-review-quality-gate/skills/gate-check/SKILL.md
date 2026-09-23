---
name: gate-check
description: Runs the explicit Govern step after `assertion-map`: determines gate compliance with deterministic `gate_check`, then orders release blockers, must-fix items and advisories with deterministic `severity_rank`. Use when the user says "is this ready to go to the client?", "run the quality gate", "what blocks release?", "can we clear the gate?", or after `assertion-map`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Quality assurance
---
# Gate Check
## Purpose
Apply QRM gate criteria deterministically and rank the resulting issues for partner review. Govern appears explicitly because release readiness is a firm-risk determination.
## When to use
After `assertion-map` in every run, and on any question about readiness, gate clearance, release blockers or client release.
## Inputs
`assertion-mapped.json` under contract `ps.deliverable-review-quality-gate.v1`.
## Steps
1. Run `scripts/gate_check.py --mapped assertion-mapped.json --out gate-checked.json`.
2. Run `scripts/severity_rank.py --gates gate-checked.json --out severity-ranked.json`.
3. Quote gate statuses, findings, severities, ranking and release-readiness status verbatim.
4. Pass ranked output to `review-packet`.
## Output
`gate-checked.json` and `severity-ranked.json` with `gate_results[]`, `findings[]`, `ranked_findings[]`, `release_readiness`, escalations and citations.
## Grounding requirements
Every finding must include gate ID, severity, deliverable location, criteria section, confidence, source and citation.
## Constraints
- The model never clears a gate, downgrades a blocker or substitutes a disclaimer for evidence.
- A release blocker can never be auto-downgraded.
- This step may refuse readiness; that refusal is the point of Govern.
## Escalation / uncertainty
Low-confidence mappings, unknown criteria or any release blocker are escalated to the reviewing partner and QRM owner.
