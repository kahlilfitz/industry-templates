# Store Task & Promotion Execution

For the store manager or field operations lead who receives an HQ campaign pack built for
hundreds of stores and has to make it true for *this* one — before launch day, not after the
mispriced shelf is photographed.

It ingests the pack, price file, planogram and task list, maps the requirements to the store's
format and cluster, tests completeness, flags pricing and signage conflicts deterministically,
ranks exceptions by revenue impact, and drafts the readiness checklist, shift brief and
exception list.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `pack-ingest` | Reads the campaign pack, price file, planogram and task list |
| 2 | `store-map` | Maps requirements to this store's format and cluster |
| 3 | `readiness-check` | Tests completeness; flags pricing and signage conflicts (deterministic) |
| 4 | `exception-raise` | Ranks what the store cannot fix, by revenue at stake |
| 5 | `brief-draft` | Drafts the readiness checklist and shift brief in store language |

## The case that shows why it exists

*"Everything shipped, reporting READY Monday."* The check finds what the confidence hides:

- An end-cap requirement calls for a fixture **the small format does not carry** — a conflict
  the store cannot fix locally, so it escalates to HQ.
- A **price conflict on the hero SKU**: the promotional price is *higher* than the current
  shelf price, so executing the change would raise the price during the promotion. Blocked,
  and ranked first at roughly 340 units a week at stake.
- Two signage kits were never received while their tasks sit open.

Ranking by revenue rather than by count is what puts the pricing trap at the top.

## What you bring

Promotion briefs and campaign packs, price and price-change files, planograms and signage
lists, launch calendars, store task lists, and the store master with cluster definitions.

## Boundaries

It does not change POS prices, planograms, labour schedules or campaign funding. It produces
the readiness pack and the exception list; the store and HQ act on them.

## Skills in this package

- **brief-draft** — Drafts the store readiness checklist, the shift brief in store language, and the exception escalation from the contract payload. Use to close every execution run - "draft the shift brief", "write up the readiness pack".
- **exception-raise** — Ranks readiness exceptions by revenue at stake with the exception_rank engine and raises the exception list. Use when the user asks "what do we fix first", "rank the gaps", or after readiness-check.
- **pack-ingest** — Ingests the HQ campaign pack, price file, planogram and task list into the rtl.store-task-promotion-execution.v1 contract. Use when the user says "new campaign pack landed", "prep the store for the launch", "are we ready for Monday's promo", or when a store assignment arrives.
- **readiness-check** — Tests store readiness against the campaign pack deterministically - applicability, completeness, fixture conflicts and price integrity - with the readiness_check engine. Use when the user asks "are we ready", "any gaps for launch", "check the pack against my store".
- **store-map** — Retrieves the store profile - format, cluster, fixtures, received assets, completed tasks, prior execution history - for the readiness test. Use after pack-ingest, or when the user asks "what does this store actually have".

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/store-task-promotion-execution/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/store-task-promotion-execution/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
