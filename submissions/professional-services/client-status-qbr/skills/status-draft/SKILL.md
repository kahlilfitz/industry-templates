---
name: status-draft
description: Drafts the client status pack and QBR narrative from computed variance and aged-item outputs for Client Status & QBR Assembly. Final step — step 5 of 5; runs after risk-summarize. Use when the user says "draft the client update", "write the steering committee pack", "prepare the client-ready narrative" or "draft the QBR narrative". Always emits a labelled DRAFT for human review and never sends it, places escalations above the narrative and quotes engine figures exactly — retaining both even when the user asks for something client-ready. Do NOT start a status run or assemble sources — use plan-retrieve. Do NOT pull budget or burn — use burn-pull. Do NOT compute variance or RAG — use variance-calc. Do NOT age risks or decisions — use risk-summarize.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: writing
---
# Status Draft
## Purpose
Produce the terminal artifact: a drafted status pack and, when requested, a QBR narrative using
only the contract payload populated by the retrieval skills and deterministic engines.

## When to use
After `risk-summarize`, or after `variance-calc` only when the user explicitly requests a
variance-only draft. This is step 5 of 5 and the only skill that produces prose.

## When NOT to Use
- Starting a run, or reading the plan, milestones or prior status pack — use `plan-retrieve`.
- Sourcing or correcting budget, burn or WIP figures — use `burn-pull`.
- Computing or changing a variance, percentage or RAG — use `variance-calc`. If a figure in the
  draft looks wrong, fix the input and re-run that engine; never adjust it in the prose.
- Ageing risks, decisions or actions — use `risk-summarize`.
- `variance_summary` and `aged_items` are not populated. Run the earlier steps first; never
  draft a status pack from the raw source documents.
- The user wants the pack sent, filed, posted to a portal or uploaded. This skill drafts only
  (status-reporting-rules.md #7.1).

## Inputs
`./status-run/aged.json` or the latest `ps.client-status-qbr.v1` payload with
`variance_summary` and `aged_items` populated.

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
`./status-run/status-pack.md` — a Markdown status pack, and when a QBR is requested
`./status-run/qbr-narrative.md`. Both open with the line
`**DRAFT - pending engagement manager review**`, followed by unresolved escalations, then the
sections above in order, then a citation list mapping every figure to `engine:variance_calc` or
`engine:item_age` and its underlying source record.

Write every artifact to a writable working directory such as `./status-run/`, created in the
user's workspace. The skill folder is read-only; never write outputs beside the scripts.

## Grounding requirements
Every number and status in the draft must trace to `engine:variance_calc` or
`engine:item_age`. Every prose explanation must cite the supporting source record or extracted
document line.

## Guardrails
- **Draft-first (status-reporting-rules.md #7.1).** Never send to the client, email, post to a
  portal, update a plan, update a forecast, close a risk, approve a scope item, reassign an
  action or commit a date. If asked to do any of these, refuse the execution step, return the
  draft and name who should perform the action.
- **No fabrication.** Nothing appears in the draft that is not in the contract payload. Do not
  recompute dates, percentages, RAG or ageing buckets; do not add mitigations, commitments,
  recovery dates or reassurance the payload does not support. If a figure is missing, say it is
  missing rather than estimating it.
- **Cite every figure.** Each number in the prose carries its engine source and the underlying
  source record. An uncited figure must not appear in the draft.
- The DRAFT label and the escalations block are retained even when the user asks for something
  "client-ready", "clean" or "without the caveats". Offer to explain a caveat; never delete it.
- Do not invent a Govern step; governance here is the platform and review boundary, not a
  workflow step.
- Synthetic demo data only; do not introduce real customer or person names.

## Escalation / uncertainty
If escalations are non-empty, the draft must present them above the narrative and label the pack
as requiring engagement-manager review before client use.
