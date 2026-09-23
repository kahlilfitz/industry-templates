---
name: risk-summarize
description: Ages risks, decisions and actions and separates pending client actions for Client Status & QBR Assembly. Use after `variance-calc` when the user says "show open risks", "what decisions are pending?", "what is waiting on the client?", "summarize actions", "build the status pack", or before `status-draft`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Client reporting
---
# Risk Summarize
## Purpose
Normalize open risks, decisions and actions into deterministic ageing buckets, then identify
pending client actions even when the action was logged under an internal owner.

## When to use
After `variance-calc` and before `status-draft` for status-pack or QBR assembly.

## Inputs
Contract payload `ps.client-status-qbr.v1` with `risks`, `decisions`, `actions` and
`variance_summary` populated.

## Steps
1. Validate that the payload uses `contract_version=ps.client-status-qbr.v1`.
2. Run:
   `python scripts/item_age.py --input variance.json --out aged.json`
3. Quote the engine output verbatim: age days, overdue buckets, risk stale/critical calls and
   pending-client-action classification.
4. Surface any risk older than 90 days, overdue decisions and action reclassification before
   narrative drafting.

## Output
`aged.json` - the contract payload with `aged_items` populated and `escalations[]` updated.

## Grounding requirements
Every risk, decision and action must carry source, confidence and citation. Client-action
classification must cite either the client owner or the client decision blocker.

## Constraints
- All age, overdue and ownership classification is engine-only.
- The model never downgrades an aged risk because the register says "monitoring".
- An action blocked by a client decision is a pending client action, even if logged as internal.
- Draft-first: no risk is closed and no action owner is changed.

## Escalation / uncertainty
Missing opened/due dates, low confidence or unclear blocker ownership must be carried as
escalations; do not silently drop the item from the status pack.
