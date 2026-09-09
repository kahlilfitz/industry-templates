# Retail Execution & Perfect Store

For the field sales rep or territory manager covering dozens of outlets a week, who today
assembles each call from a mobile app, a planogram PDF, a promotion calendar and memory.

It assembles the pre-call plan — outlet profile, last visit's open actions, promotion status,
recent scan data — then after the visit scores the perfect-store gap deterministically against
the channel and cluster standard, ranks gaps by revenue impact rather than count, and drafts
the visit report, action register and a suggested order for the rep to confirm.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `visit-prep` | Assembles the pre-call plan for this specific outlet |
| 2 | `standard-retrieve` | Retrieves the perfect-store standard for its channel and cluster |
| 3 | `gap-score` | Scores the gap deterministically against that standard |
| 4 | `action-register` | Ranks gaps by revenue impact and tracks the agreed actions |
| 5 | `visit-report` | Drafts the report with evidence attached |

## The case that shows why it exists

Two stores score the same 4-out-of-6 — *"basically the same, quick one"*. The value maths says
otherwise:

- One failure is the **hero SKU out of stock**: roughly $523 a week at stake, **and it is on
  active promotion**, which doubles its weight.
- The other is the **promotional display down during the promotion week** — same doubled
  class.

Identical compliance percentage, completely different urgency. Ranking by count would have
buried both. The report tells the rep to go back today, and suggests the replenishment order
for them to confirm.

## What you bring

Perfect-store standards, planograms and space guidelines, the promotion calendar, an outlet
master with channel and cluster, visit history and audit forms, and syndicated scan extracts.

## Boundaries

Prepares and reports. It does not place the order, change the planogram or issue trade credit
— and it does not score shelf photos by computer vision. Photos attach as evidence, never as
the basis of a score.

## Skills in this package

- **action-register** — Ranks gaps by revenue at stake with the gap_rank engine and builds the action register and suggested order for the rep to confirm. Use on "what do I fix first", "rank the gaps", "build my order", after gap-score.
- **gap-score** — Scores perfect-store compliance deterministically from the visit audit answers with the visit_score engine - photos attach as evidence, never scored by vision. Use after the visit: "score the visit", "how compliant is the store".
- **standard-retrieve** — Retrieves the perfect-store / picture-of-success standard, planogram and promo calendar for the outlet's channel and cluster. Use on "what's the standard for this outlet", "what should this store look like", after visit-prep.
- **visit-prep** — Assembles the pre-call plan for a specific outlet - profile, last visit's open actions, promotion status, recent scan performance - into the rtl.retail-execution-perfect-store.v1 contract. Use when the rep says "prep me for <outlet>", "what's the plan for today's calls", "pre-call for store <id>".
- **visit-report** — Drafts the evidenced visit report and action register from the contract payload. Use to close every visit: "write the visit report", "log the visit".

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/retail-execution-perfect-store/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/retail-execution-perfect-store/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
