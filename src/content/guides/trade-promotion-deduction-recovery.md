# Trade Promotion & Deduction Recovery

For deduction analysts and trade managers on the brand side, where retailers deduct against
invoices and the backup arrives as PDFs and portal exports that someone matches by hand
against trade terms and the promotion calendar.

Valid deductions get paid. Invalid ones get written off because chasing them costs more than
they are worth — which is the loss this template is built to stop.

It extracts the deduction records and claim backup, matches each claim to the governing
promotion, allowance or trade term, classifies validity deterministically and quantifies the
disputable amount with the calculation shown, and drafts the dispute packet and post-event
brief.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `claim-ingest` | Extracts and normalises the deduction records and claim backup |
| 2 | `term-retrieve` | Retrieves the governing promotion, allowance or trade term |
| 3 | `claim-match` | Matches each claim to its governing term |
| 4 | `validity-classify` | Classifies validity and quantifies the disputable amount — the Govern step |
| 5 | `dispute-packet` | Drafts the dispute packet and post-event brief |

## The case that shows why it exists

*"$25.9k, write it off, the account manager wants no friction."* The arithmetic disagrees:

- One claim bills **12% of volume against a signed term of 8%** — partially valid, with
  $7,300 disputable and the calculation shown.
- A **$4,000 compliance penalty arrives with no backup document at all** — unsupported, and
  fully disputable pending that backup.
- Total disputable: **$11,300**. The write-off decision now happens with the number in front
  of a human, which is the entire point.

## What you bring

ERP deduction and AR records, customer claim backup and portal exports, trade terms and
customer agreements, the promotion calendar, and TPM system records.

## Boundaries

It determines and drafts. It does not post credits, write off deductions, approve trade spend,
change a term or authorise a payment.

**One scoping note.** Promotion-lift analysis needs account-level financial truth and
standardised definitions. Where that foundation is absent, scope the deployment to deduction
validity only and leave lift out — `config/` carries that switch, and the demo shows lift
correctly skipped with validity unaffected.

## Skills in this package

- **claim-ingest** — Extracts deduction records and claim backup (PDFs, portal exports) into the rtl.trade-deduction-recovery.v1 contract. Use when the user says "retailer deducted from the invoice", "work this deduction", "claim backup arrived", or a deduction case begins.
- **claim-match** — Matches each claim to its governing promotion or trade term deterministically with the claim_match engine. Use on "does this deduction match anything we signed", after term-retrieve.
- **dispute-packet** — Drafts the dispute packet and the post-event promotion brief from the governed payload. Use to close every deduction case: "draft the dispute", "build the packet for the retailer".
- **term-retrieve** — Retrieves the governing trade terms, promotion calendar entries and agreements for the customer and period. Use on "what did we actually sign", "what's the agreed rate", after claim-ingest.
- **validity-classify** — Classifies deduction validity and quantifies the disputable amount with the calculation shown - the explicit Govern step - and runs promotion lift only where the RGM scoping allows. Use on "is this deduction valid", "how much can we dispute", "should we write it off", after claim-match.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/trade-promotion-deduction-recovery/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/trade-promotion-deduction-recovery/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
