---
name: status-draft
description: Drafts the client status pack and QBR narrative from computed variance and aged-item outputs. Use after `risk-summarize` when the user says "build the status pack", "draft the client update", "write the steering committee pack", "draft the QBR", "what changed since last week?", or "prepare the client-ready narrative".
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Client reporting
---
# Status Draft
## Purpose
Produce the terminal artifact: a drafted status pack and, when requested, a QBR narrative using
only the contract payload populated by the retrieval skills and deterministic engines.

## When to use
After `risk-summarize`, or after `variance-calc` only when the user explicitly requests a
variance-only draft.

## Inputs
`aged.json` or the latest `ps.client-status-qbr.v1` payload with `variance_summary` and
`aged_items` populated.

## Steps
1. Validate the contract and lead with unresolved `escalations[]`.
2. Draft the status pack sections:
   - executive RAG and period-over-period movement;
   - schedule variance;
   - budget burn including WIP and forecast movement;
   - scope/change-control status;
   - open risks, decisions and actions with ageing;
   - pending client actions separated from internal actions;
   - QBR narrative assembled from the period's status facts.
3. Quote engine facts exactly. Do not recompute dates, percentages, RAG or ageing buckets.
4. Mark the output as **DRAFT - pending engagement manager review**.

## Output
A client-ready draft status pack and/or QBR narrative in the engagement's established format,
with citations to plan, financial, risk, decision and action sources plus rule citations.

## Grounding requirements
Every number and status in the draft must trace to `engine:variance_calc` or
`engine:item_age`. Every prose explanation must cite the supporting source record or extracted
document line.

## Constraints
- Draft-first: never send to the client, post to a portal, update a plan, update a forecast,
  close a risk, approve a scope item, reassign an action or commit a date.
- Nothing appears in the draft that is not in the contract payload.
- Do not invent a Govern step; governance here is the platform and review boundary, not a
  workflow step.

## Escalation / uncertainty
If escalations are non-empty, the draft must present them above the narrative and label the pack
as requiring engagement-manager review before client use.
