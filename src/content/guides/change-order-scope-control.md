# Change Order & Scope Control

For engagement managers, delivery leads and commercial managers who need to answer the question that quietly erodes margin: is this client request inside the SOW, outside it, or too ambiguous to decide without a commercial conversation?

This template compares request logs, mail threads and delivered artifacts against the SOW as the controlling document. It cites the governing clause for every scope call, calculates the effort and cost delta, rolls the impact into a cumulative scope-drift view, and drafts a change order in a format a partner or contract manager can review.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `sow-retrieve` | Retrieves the SOW, MSA and prior change orders and preserves the numbered clauses that govern scope |
| 2 | `request-intake` | Extracts inbound requests, mail context and delivered-artifact evidence into the shared contract |
| 3 | `scope-match` | Runs `scope_match.py` to match each request to deliverables, assumptions and exclusions |
| 4 | `scope-classify` | Runs `scope_classify.py` to determine in-scope, out-of-scope or ambiguous under the SOW rules |
| 5 | `change-order-draft` | Runs `delta_calc.py` to quantify effort, cost and cumulative drift, then drafts the change order |

Verdicts and numbers come from deterministic Python engines (`scope_match`, `scope_classify`, `delta_calc`). The model extracts requests from messy inputs and writes the cited prose. It never decides scope, computes pricing, or changes an engine output.

## The case that shows why it exists

In the second demo scenario, each request sounds too small to fight: one more workshop, a quick data refresh, a short report, a couple of added interviews, and a harmless training office hour. A reasonable engagement manager might absorb each one to protect the relationship.

The documents tell a different story:

- The extra work is caused by a failed SOW assumption: the client did not provide the single clean export the plan depended on.
- Six individually small accommodations roll into a current change-order value of more than $15K.
- Prior no-charge accommodations push cumulative margin erosion above the escalation threshold.
- One request that sounds like a new executive report is actually covered by the SOW's readiness-report clause, so the engine protects the client relationship as well as the margin.
- One Legal workflow request hits a direct contradiction between the deliverable list and the exclusion list, so the engine refuses to decide and routes it to a human.

A naive reviewer treats the items as relationship maintenance. The engines cite the failed assumption, quantify the cumulative drift, protect the covered item, and mark the contradictory item AMBIGUOUS instead of forcing a false answer.

## What you bring

The SOW, MSA or change-control clause, prior change orders, request log, relevant mail threads, delivered-artifact inventory, rate card and effort estimates. The demo scenarios include raw SOW excerpts, mail threads, prior change-order notes, delivered-artifact inventories and rate cards, plus structured JSON inputs for engine-only regression runs.

## Boundaries

Draft-first: the package determines and drafts. It does not accept a change, commit delivery effort, reprice an engagement, issue a change order to the client, update the contract repository or write back to PSA/CRM systems. Ambiguous items stay ambiguous until an engagement partner or contract manager decides.

Grounded in the SOW/MSA excerpts and the rules in `references/` - replace them with your controlled firm documents before production use.

## Skills in this package

- **change-order-draft** — Runs deterministic `delta_calc.py` after `scope-classify` to calculate effort delta, cost delta and cumulative scope drift, then drafts the change order and drift summary. Use when the user says "draft the change order", "what is the cost impact?", "show cumulative drift", "where has scope drifted?", "should this be a change order?", or after `scope-classify` completes.
- **request-intake** — Extracts inbound client requests, mail-thread pressure, delivered artifacts and effort estimates into the contract after `sow-retrieve`. Use when the user says "review these requests", "is this in scope?", "should this be a change order?", "pull the request log", "what scope has drifted?", or "turn these emails into scope items".
- **scope-classify** — Runs deterministic `scope_classify.py` after `scope-match` to determine IN_SCOPE, OUT_OF_SCOPE or AMBIGUOUS with the SOW clause quoted. Use when the user says "is this in scope?", "is this out of scope?", "should this be a change order?", "what is ambiguous?", or "where has scope drifted?" before `change-order-draft`.
- **scope-match** — Runs deterministic `scope_match.py` after `request-intake` to match each request to SOW scope, deliverables, assumptions and exclusions. Use when the user asks "which SOW clause applies?", "map this to the SOW", "is this in scope?", "should this be a change order?", or "where has scope drifted?" before `scope-classify`.
- **sow-retrieve** — Retrieves the SOW, MSA, assumptions, exclusions and prior change orders that control scope. Use when the user says "is this in scope?", "should this be a change order?", "check the SOW", "what does the SOW allow?", "where has scope drifted?", or when a Change Order & Scope Control run begins before `request-intake`.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/change-order-scope-control/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/change-order-scope-control/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
