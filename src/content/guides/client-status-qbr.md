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

Every skill also ships `scripts/validate_payload.py`, a standard-library-only validator that
checks the shared `ps.client-status-qbr.v1` payload against the contract at each hop. Nothing
needs installing: the skills call it as
`python "$SKILL_DIR/scripts/validate_payload.py" --input "$RUN_DIR/<file>.json" --hop <skill>`,
and a non-zero exit stops the chain rather than letting a gap propagate into the draft. Each call
starts with `scripts/step0.sh`, a POSIX `sh` guard that confirms `SKILL_DIR` is the right skill
folder at the right version and that the working folder `RUN_DIR` exists.

## Setting it up for your engagement

You never edit the plugin. `plan-retrieve` checks your files, converts dates that can only be
read one way, and asks one question per missing required field. To use different RAG or ageing
thresholds for a run, say so in conversation. Values are bounded, and every non-default value is
disclosed at the top of the pack (`references/status-reporting-rules.md` §8).

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

Grounded in the reporting rules in `references/`. The engines hold the published thresholds as
built-in defaults; per-run changes go through conversation (§8), not by editing the rules file.

## Skills in this package

- **burn-pull** — Pulls and normalizes time, budget, billed burn, unbilled WIP, accrual and forecast records for Client Status & QBR Assembly. Step 2 of 5; runs after plan-retrieve. Use when the user says "where are we on budget?", "why did burn change?", "get the burn numbers into the payload" or "pull the finance export". Keeps billed and unbilled WIP strictly separate, cites the export row or tracker line behind every figure it writes, and escalates when WIP movement cannot be traced to a source rather than inferring a baseline. Do NOT start a status run or assemble the pack — use plan-retrieve. Do NOT compute variance or RAG — use variance-calc. Do NOT age risks or decisions — use risk-summarize. Do NOT write the client narrative — use status-draft.
- **plan-retrieve** — Retrieves and structures the engagement plan, milestone schedule, RAID register, prior status packs and client reporting template for Client Status & QBR Assembly. Entry step for a status or QBR run — step 1 of 5. Use when the user says "build the status pack", "prepare the weekly status", "start the status run", "start the QBR run" or "draft the QBR from the source files". Extracts milestones with baseline and forecast dates, prior-period RAG, open risks, decisions, actions and change requests, citing every field to its source line; flags rebaselined milestones and items absent from the prior pack instead of dropping them. Do NOT pull current-period budget, burn or WIP figures — use burn-pull. Do NOT compute variance or RAG — use variance-calc. Do NOT age risks or decisions — use risk-summarize. Do NOT write the client narrative — use status-draft.
- **risk-summarize** — Ages risks, decisions and actions and separates pending client actions for Client Status & QBR Assembly. Step 4 of 5; runs after variance-calc. Use when the user says "show open risks", "what decisions are pending?", "what is waiting on the client?" or "summarize actions with ageing". Delegates ageing to scripts/item_age.py and quotes it verbatim; buckets every open item by its own opened or due date rather than the label on the register, so a risk marked "monitoring" still surfaces as stale or critical, and reclassifies an action blocked by a client decision as a pending client action. Do NOT start a status run — use plan-retrieve. Do NOT pull budget or burn — use burn-pull. Do NOT compute variance or RAG — use variance-calc. Do NOT write the client narrative — use status-draft.
- **status-draft** — Drafts the client status pack and QBR narrative from computed variance and aged-item outputs for Client Status & QBR Assembly. Final step — step 5 of 5; runs after risk-summarize. Use when the user says "draft the client update", "write the steering committee pack", "prepare the client-ready narrative" or "draft the QBR narrative". Always emits a labelled DRAFT for human review and never sends it, places escalations above the narrative and quotes engine figures exactly — retaining both even when the user asks for something client-ready. Do NOT start a status run or assemble sources — use plan-retrieve. Do NOT pull budget or burn — use burn-pull. Do NOT compute variance or RAG — use variance-calc. Do NOT age risks or decisions — use risk-summarize.
- **variance-calc** — Computes period-over-period schedule, budget and scope variance with deterministic RAG for Client Status & QBR Assembly. Step 3 of 5; runs after plan-retrieve and burn-pull. Use when the user says "calculate the variance", "why is the status red?", "what changed since last week?" or "give me schedule, budget and scope RAG". Delegates every threshold and calculation to scripts/variance_calc.py and quotes the engine output verbatim rather than restating it; surfaces masked slippage where a rebaseline hides variance against the original baseline. Do NOT start a status run — use plan-retrieve. Do NOT pull finance or burn data — use burn-pull. Do NOT age risks or decisions — use risk-summarize. Do NOT write the client narrative — use status-draft.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/client-status-qbr/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/client-status-qbr/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
