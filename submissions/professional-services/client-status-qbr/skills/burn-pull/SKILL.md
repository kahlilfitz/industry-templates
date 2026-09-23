---
name: burn-pull
description: Pulls and normalizes time, budget, billed burn, unbilled WIP, accrual and forecast records for Client Status & QBR Assembly. Use after `plan-retrieve` when the user says "build the status pack", "where are we on budget?", "why did burn change?", "what changed since last week?", or before `variance-calc`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Client reporting
---
# Burn Pull
## Purpose
Normalize finance and delivery burn inputs into the budget hop of
`ps.client-status-qbr.v1`, preserving billed and unbilled values separately so the engine can
compute the authoritative burn view.

## When to use
After `plan-retrieve` and before `variance-calc` for any weekly status, fortnightly status or
QBR run that includes financial/burn reporting.

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
4. Write or update the `budget` object in the contract payload using
   `source=skill:burn-pull`.

## Output
The current contract payload with `budget` populated and ready for `variance-calc`.

## Grounding requirements
Every financial value must cite the export row, tracker line or prior status line it came from.
Do not collapse billed burn and WIP into a single unexplained number.

## Constraints
- No budget RAG, threshold verdict or variance percentage here; all math belongs to
  `variance-calc`.
- Never use billed-only burn as the final actual if unbilled WIP or accrual is present.
- Never update the financial system, forecast or budget tracker.

## Escalation / uncertainty
Currency mismatch, missing WIP field, conflicting forecast values or confidence below 0.75 must
be written to `escalations[]`; do not invent a balancing adjustment.
