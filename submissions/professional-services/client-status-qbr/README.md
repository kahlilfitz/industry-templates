# Client Status & QBR Assembly

For the engagement manager, project manager or programme lead who has a steering committee
coming up and too many sources to reconcile by hand: the plan, the financial tracker, last
week's status, open risks, decisions and actions.

This template pulls the delivery evidence together, calculates schedule, budget and scope
variance, ages open risks and decisions, separates client actions from internal actions, and
hands back a drafted status pack or QBR narrative in the engagement's reporting style.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `plan-retrieve` | Reads the engagement plan, milestones and prior status packs |
| 2 | `burn-pull` | Normalizes billed, unbilled WIP, forecast and budget records |
| 3 | `variance-calc` | Computes schedule, budget and scope variance with deterministic RAG |
| 4 | `risk-summarize` | Ages risks, decisions and actions; separates pending client actions |
| 5 | `status-draft` | Drafts the client status pack and QBR narrative with citations |

Numbers, RAG status, ageing buckets and threshold verdicts come from deterministic Python
engines (`variance_calc`, `item_age`). The model extracts, orchestrates and writes the cited
prose. It never sets a status, variance or ageing call itself.

## The case that shows why it exists

The second demo looks reassuring if you follow the obvious path:

- The current status says green because a milestone was quietly re-baselined last period; the
  engine compares the forecast to the original baseline and flags the schedule variance.
- Billed burn looks slightly under plan, but unbilled WIP has not landed yet; the engine includes
  WIP and turns the budget RAG red.
- A risk has sat in "open, monitoring" for more than 90 days without a re-rate, and an action
  logged as internal is actually blocked pending a client decision.

A naive reviewer drafts a green status pack. The engines produce a red/amber pack with the
rebaseline, WIP accrual, aged risk and client decision dependency called out before prose is
written.

## What you bring

The current engagement plan or milestone export, the prior status pack, time and billing or
budget-burn extracts, the risk register, decision log, action register and the client reporting
template. Raw formats are fine: email, CSV, markdown extracts and status-pack text are included
in the demo data to exercise the Connect path.

## Boundaries

Draft-first. It never sends the status pack, posts to a client portal, re-baselines the plan,
changes a forecast, closes a risk, commits a date or updates the system of record. It prepares a
reviewed draft and makes every variance, ageing call and action split traceable.

Grounded in the reporting rules in `references/`; replace them with your own engagement
reporting policy and controlled templates.
