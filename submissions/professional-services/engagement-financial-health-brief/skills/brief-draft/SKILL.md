---
name: brief-draft
description: Drafts the engagement financial health brief after health-calc, driver-attribute and benchmark-compare. Use when the user says "draft the brief", "write the engagement review", "prepare the practice review note", "summarize why margin is down", or "are we going to make our number?"
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Delivery Commercial Control
---
# Brief Draft
## Purpose
Produce the terminal artifact: a cited, review-ready financial health brief for the engagement or practice review.

## When to use
After `health-calc`, `driver-attribute` and `benchmark-compare`.

## Inputs
`drivers.json` containing the health indicators, benchmark comparison/refusal, driver attribution, escalations and provenance.

## Steps
1. Validate that indicators and drivers come from engine output.
2. Draft a brief with: executive status, indicators against plan, WIP/unbilled exposure, benchmark comparison or refusal, largest driver decomposition, early-warning flags, recommended human review questions and appendix citations.
3. Mark the output DRAFT and preserve the boundary: reporting and explanation only.
4. If benchmark comparison is refused, include the refusal as an explicit finding rather than omitting benchmark context silently.

## Output
`ENGAGEMENT-FINANCIAL-HEALTH-BRIEF-<engagement-id>.md` or the requested document format.

## Grounding requirements
Every numeric claim traces to `engine:health_calc` or `engine:driver_attribute`. Every definition claim cites `engagement-financial-metric-definitions.md`.

## Constraints
- The model drafts prose only; it does not calculate, rank, change status or rewrite drivers.
- No WIP adjustment, write-off, rate change, reforecast, invoice action, budget transfer or system write-back.
- Do not include real customers, real people or Microsoft-internal information in demo outputs.

## Escalation / uncertainty
If engine escalations are present, put them near the top of the brief and label the draft as requiring engagement manager or finance partner review.
