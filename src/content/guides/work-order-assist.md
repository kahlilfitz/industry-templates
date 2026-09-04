# Work Order Assistant

Everything a technician or planner needs for one work order, gathered in one place instead of
across four systems and a filing cabinet.

It pulls the work order and asset context, retrieves the SOPs, OEM manuals and prior fix notes
that actually apply, ranks the most similar past jobs, checks parts readiness against the
storeroom and the supersession table, and drafts clean technician notes or a planner summary
with the next best action.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `wo-intake` | Reads the work order and asset context into the contract |
| 2 | `knowledge-retrieve` | Retrieves relevant SOPs, OEM manual sections and prior fix notes |
| 3 | `similar-work-rank` | Ranks the most similar past work orders (deterministic) |
| 4 | `parts-readiness` | Checks parts against the storeroom and supersession table (deterministic) |
| 5 | `work-order-writeup` | Drafts the technician notes or planner summary, cited |

## The case that shows why it exists

Instrument air compressor C-500 — class A, no redundancy — threw the same intake-valve fault
again. The technician is about to do exactly what the SOP says: pull another VK-100 intake
valve and fit it.

Two facts change the answer:

- **History:** the last *three* VK-100 swaps on C-500 all came back. The fault recurred every
  time.
- **A recommended change:** a fix note flags VK-100 as prone to this failure and recommends the
  superseding VK-200.

The SOP is not wrong, it is just out of date. Following it books a fourth repeat visit.

## What you bring

The work order, the asset register, work-order history, a parts catalogue and usage data, plus
whatever SOPs and OEM manual excerpts you have. The demo scenarios ship all of it, including
the raw work-order text and PDF excerpts.

## Boundaries

Draft-first and document-grounded. No auto-scheduling and no CMMS write-back — a planner still
owns the schedule.

Grounded in CMMS standards, SOPs and OEM manuals — see `references/`.

## Skills in this package

- **knowledge-retrieve** — Retrieves the SOPs, OEM manuals, prior fixes and parts history relevant to a work order and attaches them to the mfg.work-order-assist.v1 contract. Use when the user says "find the SOP and manual", "pull prior fixes for <asset>", "get the parts history", "what did we do last time", or after wo-intake completes.
- **parts-readiness** — Checks whether a work order's parts are ready — storeroom stock, shortages, and part supersession — and computes a READY/PARTIAL/BLOCKED status, deterministically. Use when the user says "are the parts in stock", "check parts readiness", "can we schedule this", "is that part still current", or after similar-work-rank completes.
- **similar-work-rank** — Ranks the most similar past work orders for the current job and surfaces recurring failures and superseding fixes, deterministically. Use when the user says "find similar past work", "have we done this before", "what's the closest prior fix", "is this a repeat failure", or after knowledge-retrieve completes.
- **wo-intake** — Pulls the current work order and its asset context into the mfg.work-order-assist.v1 contract inputs. Use when the user says "assemble the work order packet", "pull up WO <id>", "get me everything for this work order", "work order for <asset>", or when a Work Order Assistant run begins.
- **work-order-writeup** — Drafts the technician notes or planner summary for a work order from the assembled contract payload, with every determination cited to the SOP, manual, history and parts data. Use when the user says "draft the technician notes", "write up the work order", "give me the planner summary", "what's the next best action", or after parts-readiness completes.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/work-order-assist/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/work-order-assist/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
