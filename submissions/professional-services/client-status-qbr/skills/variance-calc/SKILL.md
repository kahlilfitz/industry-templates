---
name: variance-calc
description: Computes period-over-period schedule, budget and scope variance with deterministic RAG for Client Status & QBR Assembly. Use after `plan-retrieve` and `burn-pull` when the user says "what changed since last week?", "why is the status red?", "calculate the variance", "build the status pack", or before `risk-summarize` and `status-draft`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Client reporting
---
# Variance Calc
## Purpose
Apply `references/status-reporting-rules.md` deterministically to compute schedule, budget,
scope and overall RAG, plus the period-over-period variance facts the draft must quote.

## When to use
After `plan-retrieve` and `burn-pull`, before `risk-summarize` and always before
`status-draft`.

## Inputs
Contract payload `ps.client-status-qbr.v1` with plan, prior status and budget populated.

## Steps
1. Validate that the payload uses `contract_version=ps.client-status-qbr.v1`.
2. Run:
   `python scripts/variance_calc.py --input status-input.json --out variance.json`
3. Quote the engine output verbatim: RAG values, variance days, budget percentages, WIP
   inclusion, scope status and escalations.
4. If a displayed green status is contradicted by original-baseline variance, lead with the
   rebaseline escalation. If billed-only burn differs from WIP-inclusive burn, lead with the
   WIP escalation.

## Output
`variance.json` - the contract payload with `variance_summary` populated and `escalations[]`
updated.

## Grounding requirements
Every computed fact must carry `source=engine:variance_calc`, confidence and a citation to
`status-reporting-rules.md` plus the source field from the input record.

## Constraints
- All numbers, RAG and threshold verdicts come from `scripts/variance_calc.py`.
- The model never changes green/amber/red status in prose.
- The engine compares schedule to original baseline, not only to the latest rebaseline.
- Draft-first: no plan rebaseline, forecast update or scope approval is executed.

## Escalation / uncertainty
Low confidence, source conflicts, rebaseline masking or scope ambiguity must remain visible in
`escalations[]` and the eventual status draft.
