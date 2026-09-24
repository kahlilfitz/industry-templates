---
name: change-order-draft
description: Runs deterministic `delta_calc.py` after `scope-classify` to calculate effort delta, cost delta and cumulative scope drift, then drafts the change order and drift summary. Use when the user says "draft the change order", "what is the cost impact?", "show cumulative drift", "where has scope drifted?", "should this be a change order?", or after `scope-classify` completes.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: writing
---
# Change Order Draft
## Purpose
Quantify the commercial impact, produce the cumulative drift view, and draft the review-ready change order from the contract payload.
## When to use
After `scope-classify`, once every request is IN_SCOPE, OUT_OF_SCOPE or AMBIGUOUS.
## Inputs
`classified.json` and `rate-card.json` under contract `ps.change-order-scope-control.v1`.
## Steps
1. Validate classifications and rate-card coverage.
2. Run `scripts/delta_calc.py --classified classified.json --rate-card rate-card.json --out change-order.json`.
3. Quote all totals, line-item calculations and cumulative drift values verbatim from the engine.
4. Draft the change order from `change_order_draft`: scope summary, line items, governing clause citations, assumptions, exclusions, commercial total and review status.
5. Lead with `ambiguity_list[]` and `escalations[]`; unresolved ambiguous items are not included in the charge total.
## Output
`change-order.json` plus a human-readable draft change order and cumulative drift report.
## Grounding requirements
Every dollar amount traces to `engine:delta_calc`, rate-card citation and rule section. Every line item carries the scope classification citation from `scope_classify.py`.
## Constraints
- Draft-first: do not accept a change, commit effort, reprice the engagement, issue the change order to the client, update CRM/PSA or send email.
- IN_SCOPE items have zero change-order amount.
- AMBIGUOUS items show quantified exposure but are excluded from the draft total until human review.
## Escalation / uncertainty
If cumulative drift exceeds the threshold, show the escalation prominently. If rate-card coverage or estimate basis is incomplete, block the affected line item.
