---
name: plan-retrieve
description: Retrieves and structures the engagement plan, milestone schedule, prior status packs and client reporting template for Client Status & QBR Assembly. Entry step for a status or QBR run. Use when the user says "build the status pack", "prepare the weekly status", "start the status run" or "draft the QBR". Extracts milestones with baseline and forecast dates, prior-period RAG and open change requests, citing every field to its source line; flags rebaselined milestones and items absent from the prior pack instead of dropping them. Do NOT use for budget or burn figures — use burn-pull. Do NOT compute variance or RAG — use variance-calc. Do NOT age risks or decisions — use risk-summarize. Do NOT write the client narrative — use status-draft.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Plan Retrieve
## Purpose
Turn the engagement plan, milestone schedule, prior period status and reporting template into
the `ps.client-status-qbr.v1` contract's plan and prior-status inputs.

## When to use
Start every Client Status & QBR Assembly run here. Use this before `burn-pull`, `variance-calc`,
`risk-summarize` or `status-draft`.

## Inputs
- Engagement plan or milestone export.
- Prior weekly/fortnightly status pack.
- QBR or client status template, if supplied.
- PM email or notes describing current reporting period context.
- Contract schema in `contracts/ps.client-status-qbr.v1.json`.

## Steps
1. Verify engagement ID, project code, client name and reporting period across all supplied
   files. Preserve conflicts instead of smoothing them over (status-reporting-rules.md #1.2).
2. Extract each milestone with `id`, `name`, `original_baseline_date`,
   `current_baseline_date`, `current_forecast_date`, `reported_rag`,
   `rebaselined_last_period`, `source`, `confidence` and `citation`.
3. Extract prior-status milestone forecasts and the prior reported RAG. Do not accept the
   prior pack's green status as a computed status; `variance-calc` recomputes it.
4. Extract open scope changes, especially unapproved items and any client-facing impact.
5. Write or update the contract payload. Use `source` values beginning `skill:plan-retrieve`
   and preserve citations to the plan extract, prior status pack and template.

## Output
`status-input.json` or the current contract payload with `engagement`, `reporting_period`,
`sources`, `plan` and `prior_status` populated.

## Grounding requirements
Every milestone, prior forecast and scope-change field must carry confidence, source and
citation. Rebaseline flags must cite the exact plan/status line that shows the date movement.

## Constraints
- No variance math, RAG correction or status setting here; that is `variance-calc`.
- Never infer an original baseline from a current baseline when both are present.
- Never hide a quiet rebaseline because the current status pack says green.
- Synthetic demo data only; do not introduce real customer or person names.

## Escalation / uncertainty
If baseline dates conflict, confidence is below 0.75, or the prior status pack is missing, carry
the ambiguity in `escalations[]` and let `variance-calc` force the mechanical review path.
