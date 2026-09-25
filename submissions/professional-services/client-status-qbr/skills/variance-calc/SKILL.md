---
name: variance-calc
description: Computes period-over-period schedule, budget and scope variance with deterministic RAG for Client Status & QBR Assembly. Step 3 of 5; runs after plan-retrieve and burn-pull. Use when the user says "calculate the variance", "why is the status red?", "what changed since last week?" or "give me schedule, budget and scope RAG". Delegates every threshold and calculation to scripts/variance_calc.py and quotes the engine output verbatim rather than restating it; surfaces masked slippage where a rebaseline hides variance against the original baseline. Do NOT start a status run — use plan-retrieve. Do NOT pull finance or burn data — use burn-pull. Do NOT age risks or decisions — use risk-summarize. Do NOT write the client narrative — use status-draft.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Variance Calc
## Purpose
Apply `references/status-reporting-rules.md` deterministically to compute schedule, budget,
scope and overall RAG, plus the period-over-period variance facts the draft must quote.

## When to use
After `plan-retrieve` and `burn-pull`, before `risk-summarize` and always before
`status-draft`. This is step 3 of 5.

## When NOT to Use
- Starting a run, or reading the plan and prior status pack — use `plan-retrieve`.
- Extracting or correcting the underlying finance figures — use `burn-pull`. This skill reads
  the `budget` object; it never sources or edits it.
- Ageing risks, decisions or actions, or identifying pending client actions — use
  `risk-summarize`. Item ageing thresholds (#5.1–#5.5) belong to that engine, not this one.
- Writing the client-facing explanation of the RAG — use `status-draft`.
- The payload has no `plan`, `prior_status` or `budget` populated. Run the earlier steps first
  rather than computing variance against partial data.

## Inputs
Contract payload `ps.client-status-qbr.v1` with plan, prior status and budget populated.

## Steps
1. Validate that the payload uses `contract_version=ps.client-status-qbr.v1`.
2. Run, from a writable working directory:
   `python scripts/variance_calc.py --input ./status-run/status-input.json --out ./status-run/variance.json`
3. Quote the engine output verbatim: RAG values, variance days, budget percentages, WIP
   inclusion, scope status and escalations.
4. If a displayed green status is contradicted by original-baseline variance, lead with the
   rebaseline escalation. If billed-only burn differs from WIP-inclusive burn, lead with the
   WIP escalation.

## Output
`./status-run/variance.json` — the contract payload with `variance_summary` populated and
`escalations[]` updated.

Write every artifact to a writable working directory such as `./status-run/`, created in the
user's workspace. The skill folder is read-only; never write outputs beside the scripts.

## Grounding requirements
Every computed fact must carry `source=engine:variance_calc`, confidence and a citation to
`status-reporting-rules.md` plus the source field from the input record.

## Guardrails
- **Draft-first (status-reporting-rules.md #7.1).** This skill computes and reports only. It
  never re-baselines a plan, updates a forecast, approves a scope item or commits a date. If
  asked to "fix" a red status, refuse the execution step and return the variance with a
  recommendation.
- **No fabrication.** Every number comes from `scripts/variance_calc.py`. The model never
  computes, estimates, rounds or adjusts a variance, percentage or RAG itself, and never
  changes green/amber/red in prose. Where the engine reports a figure as unmeasurable, say so
  rather than substituting a value.
- **Cite every figure.** Each quoted value carries the engine source, its confidence and the
  `status-reporting-rules.md` rule number it was derived under.
- The engine compares schedule to the original baseline, not only to the latest rebaseline.
- Schedule thresholds (#2.1/#2.2) are strict "more than"; budget thresholds (#3.1/#3.2) are
  inclusive "at least". Do not describe them as the same test.
- Budget variance is measured in either direction, so a material underspend can drive
  amber or red. Report the direction, never just the colour.

## Escalation / uncertainty
Low confidence, source conflicts, rebaseline masking or scope ambiguity must remain visible in
`escalations[]` and the eventual status draft.
