---
name: plan-retrieve
description: Retrieves and structures the engagement plan, milestone schedule, prior status packs and client reporting template for Client Status & QBR Assembly. Entry step for a status or QBR run — step 1 of 5, followed by burn-pull, variance-calc, risk-summarize and status-draft. Use when the user says "build the status pack", "prepare the weekly status", "start the status run" or "start the QBR run". Extracts milestones with baseline and forecast dates, prior-period RAG and open change requests, citing every field to its source line; flags rebaselined milestones and items absent from the prior pack instead of dropping them. Do NOT pull current-period budget, burn or WIP figures — use burn-pull; this skill carries only the prior pack's closing figures as historical context. Do NOT compute variance or RAG — use variance-calc. Do NOT age risks or decisions — use risk-summarize. Do NOT write the client narrative — use status-draft.
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
Start every Client Status & QBR Assembly run here. This is step 1 of 5: `plan-retrieve` →
`burn-pull` → `variance-calc` → `risk-summarize` → `status-draft`. A run-start phrase begins
this step only; tell the user the four remaining steps still have to run.

## When NOT to Use
- Current-period budget, burn, unbilled WIP or forecast-to-complete figures — use `burn-pull`.
  This skill carries only the prior pack's closing figures, as historical context.
- Variance percentages, RAG, or "why is the status red?" — use `variance-calc`.
- Risk, decision or action ageing, or "what is waiting on the client?" — use `risk-summarize`.
- The written client narrative, status pack prose or QBR wording — use `status-draft`.
- No engagement plan, milestone export or prior status pack has been supplied. Ask for the
  source document; never reconstruct a plan from memory or from the client's expectations.

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
`./status-run/status-input.json` — the `ps.client-status-qbr.v1` contract payload with
`engagement`, `reporting_period`, `sources`, `plan` and `prior_status` populated.

Write every artifact to a writable working directory such as `./status-run/`, created in the
user's workspace. The skill folder is read-only; never write outputs beside the scripts.

## Grounding requirements
Every milestone, prior forecast and scope-change field must carry confidence, source and
citation. Rebaseline flags must cite the exact plan/status line that shows the date movement.

## Guardrails
- **Draft-first (status-reporting-rules.md #7.1).** This skill reads and structures only. It
  never updates a plan, re-baselines a milestone, approves a scope change, commits a date or
  writes to a delivery system. If asked to do any of those, refuse the execution step and hand
  back the structured payload with a recommendation.
- **No fabrication.** Every milestone, date, RAG and scope item must come from a supplied
  document. If a field is absent, leave it absent and add an `escalations[]` entry. Never infer
  an original baseline from a current baseline when both are present.
- **Cite every figure.** Each extracted field carries `source`, `confidence` and `citation`
  pointing at the plan extract, prior status line or template row it came from. An uncited
  figure must not enter the payload.
- No variance math, RAG correction or status setting here; that is `variance-calc`.
- Never hide a quiet rebaseline because the current status pack says green.
- Synthetic demo data only; do not introduce real customer or person names.

## Escalation / uncertainty
If baseline dates conflict, confidence is below 0.75, or the prior status pack is missing, carry
the ambiguity in `escalations[]` and let `variance-calc` force the mechanical review path.
