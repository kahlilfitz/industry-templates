---
name: risk-summarize
description: Ages risks, decisions and actions and separates pending client actions for Client Status & QBR Assembly. Step 4 of 5; runs after variance-calc. Use when the user says "show open risks", "what decisions are pending?", "what is waiting on the client?" or "summarize actions with ageing". Delegates ageing to scripts/item_age.py and quotes it verbatim; buckets every open item by its own opened or due date rather than the label on the register, so a risk marked "monitoring" still surfaces as stale or critical, and reclassifies an action blocked by a client decision as a pending client action. Do NOT start a status run — use plan-retrieve. Do NOT pull budget or burn — use burn-pull. Do NOT compute variance or RAG — use variance-calc. Do NOT write the client narrative — use status-draft.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Risk Summarize
## Purpose
Normalize open risks, decisions and actions into deterministic ageing buckets, then identify
pending client actions even when the action was logged under an internal owner.

## When to use
After `variance-calc` and before `status-draft` for status-pack or QBR assembly. This is
step 4 of 5.

## When NOT to Use
- Starting a run, or reading the plan and prior status pack — use `plan-retrieve`.
- Budget, burn or WIP figures — use `burn-pull`.
- Schedule, budget or scope variance and the overall RAG — use `variance-calc`. Item ageing
  here is independent of the engagement RAG and never overrides it.
- Writing the client-facing risk narrative or mitigation commentary — use `status-draft`.
- The payload has no `risks`, `decisions` or `actions` populated, or `variance_summary` is
  missing. Run the earlier steps first rather than ageing a partial register.

## Inputs
Contract payload `ps.client-status-qbr.v1` with `risks`, `decisions`, `actions` and
`variance_summary` populated.

## Steps
1. Validate that the payload uses `contract_version=ps.client-status-qbr.v1`.
2. Run, from a writable working directory:
   `python scripts/item_age.py --input ./status-run/variance.json --out ./status-run/aged.json`
3. Quote the engine output verbatim: age days, overdue buckets, risk stale/critical calls and
   pending-client-action classification.
4. Surface any risk older than 90 days, overdue decisions and action reclassification before
   narrative drafting.

## Output
`./status-run/aged.json` — the contract payload with `aged_items` populated and
`escalations[]` updated. `aged_items.pending_client_actions` contains both client-owned
actions and unmade client decisions, each tagged with its `kind`.

Write every artifact to a writable working directory such as `./status-run/`, created in the
user's workspace. The skill folder is read-only; never write outputs beside the scripts.

## Grounding requirements
Every risk, decision and action must carry source, confidence and citation. Client-action
classification must cite either the client owner or the client decision blocker.

## Guardrails
- **Draft-first (status-reporting-rules.md #7.1).** This skill classifies only. It never closes
  a risk, approves a decision, reassigns an action owner, changes a due date or updates a
  register. If asked to close or reassign, refuse the execution step and return the
  classification with a recommendation.
- **No fabrication.** All age, overdue and ownership classification comes from
  `scripts/item_age.py`. A missing `opened_date` or `due_date` is never treated as zero days or
  as "not overdue" — the engine reports it as unknown and escalates. The model never fills in a
  plausible date.
- **Cite every figure.** Each aged item carries `source=engine:item_age`, its confidence and the
  `status-reporting-rules.md` rule number behind its bucket.
- The model never downgrades an aged risk because the register says "monitoring".
- An action blocked by a client decision is a pending client action, even if logged as internal
  (status-reporting-rules.md #5.5).
- Closed, cancelled and approved items are excluded from ageing and never generate escalations.

## Escalation / uncertainty
Missing opened/due dates, low confidence or unclear blocker ownership must be carried as
escalations; do not silently drop the item from the status pack.
