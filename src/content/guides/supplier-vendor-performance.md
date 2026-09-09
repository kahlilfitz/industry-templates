# Supplier & Vendor Performance Review

For the buyer or category manager who currently spends a week in spreadsheets before every
vendor review, assembling delivery performance, quality records, invoice disputes and the
contract terms that govern them.

It pulls the PO, receipt, invoice, return and quality records, rolls up the OTIF, defect and
dispute scorecard with trends, clusters recurring issues with evidence, retrieves the
governing trading term, and drafts the review agenda, corrective action request and commitment
tracker.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `record-pull` | Pulls PO, receipt, invoice, return and quality records |
| 2 | `scorecard-roll` | Rolls up OTIF, defect, return and dispute rates with trends (deterministic) |
| 3 | `issue-cluster` | Clusters recurring issues and attaches the evidence |
| 4 | `term-retrieve` | Retrieves and quotes the governing contract or trading term |
| 5 | `review-pack` | Drafts the agenda, corrective action request and commitment tracker |

## The case that shows why it exists

*"Great partner, keep it friendly, skip the scorecard."* The records disagree:

- OTIF has fallen across **three consecutive quarters** — a trend flag, not a bad quarter.
- The latest quarter breaches the threshold in the trading terms, which **triggers a
  corrective-action right and a rebate**. The clause is quoted; whether to invoke it stays the
  buyer's decision.
- The short-ship cluster concentrates in **one DC**, which meets the "mostly our own fault"
  line with specific record ids.

A naive prep writes the friendly deck the buyer asked for. Hospitality is not a metric.

## What you bring

ERP purchase orders, receipts and invoices, supplier portals and correspondence, quality and
return records, contracts and trading terms, and the vendor master.

## Boundaries

Read-only scorecarding and drafting. It does not change a PO, place a payment hold, amend a
contract or deselect a supplier.

## Skills in this package

- **issue-cluster** — Clusters recurring issues by type and lane with record evidence, and maps scorecard breaches to governing trading terms, deterministically. Use on "what keeps going wrong", "cluster the issues", after scorecard-roll.
- **record-pull** — Pulls PO, receipt, invoice, return, quality and dispute records for the vendor and review period into the rtl.supplier-vendor-performance.v1 contract. Use when the user says "prep the vendor review for <supplier>", "pull the supplier records", "quarterly business review coming up".
- **review-pack** — Drafts the vendor review agenda, corrective action request and commitment tracker from the contract payload. Use to close every review prep: "draft the review pack", "build the QBR agenda".
- **scorecard-roll** — Rolls up the OTIF / defect / dispute scorecard by quarter with trend flags, deterministically, with the scorecard_roll engine. Use on "how are they performing", "roll the scorecard", after record-pull.
- **term-retrieve** — Retrieves and quotes the governing contract or trading term for any performance question. Use on "what does the agreement say about OTIF", "do we have a rebate right", or after issue-cluster.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/supplier-vendor-performance/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/supplier-vendor-performance/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
