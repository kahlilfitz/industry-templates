---
name: burn-pull
description: Pulls and normalizes time, budget, billed burn, unbilled WIP, accrual and forecast records for Client Status & QBR Assembly. Step 2 of 5; runs after plan-retrieve. Use when the user says "where are we on budget?", "why did burn change?", "get the burn numbers into the payload" or "pull the finance export". Keeps billed and unbilled WIP strictly separate, cites the export row or tracker line behind every figure it writes, and escalates when WIP movement cannot be traced to a source rather than inferring a baseline. Do NOT start a status run or assemble the pack — use plan-retrieve. Do NOT compute variance or RAG — use variance-calc. Do NOT age risks or decisions — use risk-summarize. Do NOT write the client narrative — use status-draft.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Burn Pull
## Purpose
Normalize finance and delivery burn inputs into the budget hop of
`ps.client-status-qbr.v1`, preserving billed and unbilled values separately so the engine can
compute the authoritative burn view.

## When to use
After `plan-retrieve` and before `variance-calc` for any weekly status, fortnightly status or
QBR run that includes financial/burn reporting. This is step 2 of 5.

## When NOT to Use
- Starting a run, or reading the plan, milestones or prior status pack — use `plan-retrieve`.
- Turning these figures into percentages, thresholds or a budget RAG — use `variance-calc`.
  This skill writes raw values only; it never decides whether they are good or bad.
- Risk, decision or action ageing — use `risk-summarize`.
- Explaining the budget position to the client in prose — use `status-draft`.
- No finance export, budget tracker or forecast record has been supplied. Ask for it; never
  estimate burn from headcount, rate cards or elapsed schedule.

## Inputs
- Time and billing export.
- Budget tracker or engagement financials.
- Forecast-to-complete record.
- Prior status pack or prior forecast extract.
- Contract schema in `contracts/ps.client-status-qbr.v1.json`.

## Steps
1. Extract currency, baseline budget, planned burn to date, actual billed to date, unbilled
   WIP/accrual, current forecast-to-complete and prior forecast-to-complete.
2. Preserve billed and unbilled WIP as separate fields. WIP is not optional when present:
   `variance-calc` includes it under status-reporting-rules.md #3.3.
3. Capture source, confidence and citation for every value. Prefer the finance extract for
   computed fields and carry status-pack conflicts into `escalations[]`.
4. If unbilled WIP or the forecast-to-complete moved since the prior pack and the movement
   cannot be traced to an export row or tracker line, write an `escalations[]` entry naming the
   untraceable figure. Never infer a WIP baseline to make the movement reconcile.
5. Write or update the `budget` object in the contract payload using
   `source=skill:burn-pull`.

## Output
`./status-run/status-input.json` — the contract payload with `budget` populated and ready for
`variance-calc`.

Write every artifact to a writable working directory such as `./status-run/`, created in the
user's workspace. The skill folder is read-only; never write outputs beside the scripts.

## Grounding requirements
Every financial value must cite the export row, tracker line or prior status line it came from.
Do not collapse billed burn and WIP into a single unexplained number.

## Guardrails
- **Draft-first (status-reporting-rules.md #7.1).** This skill reads finance data only. It never
  updates the financial system, the budget tracker, a forecast, a rate or an invoice, and never
  raises a change request. If asked, refuse the execution step and return the figures with a
  recommendation.
- **No fabrication.** Never estimate, interpolate or balance a financial figure. A missing
  currency, WIP field or forecast stays missing and goes to `escalations[]`. Never invent a
  balancing adjustment to make burn reconcile to plan.
- **Cite every figure.** Every value written to `budget` carries `source`, `confidence` and a
  `citation` naming the export row, tracker line or prior status line behind it. An uncited
  financial figure must not enter the payload.
- No budget RAG, threshold verdict or variance percentage here; all math belongs to
  `variance-calc`.
- Never use billed-only burn as the final actual if unbilled WIP or accrual is present
  (status-reporting-rules.md #3.3).
- Synthetic demo data only; do not introduce real customer, person or account names.

## Escalation / uncertainty
Currency mismatch, missing WIP field, conflicting forecast values or confidence below 0.75 must
be written to `escalations[]`; do not invent a balancing adjustment.
