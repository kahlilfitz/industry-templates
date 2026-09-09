# Returns & Refund Case

For the service desk or contact-centre agent making a return decision that is genuinely a
compliance determination — and needs to be the same decision whoever is on shift.

It retrieves the order, receipt, SKU attributes and warranty, classifies the return reason
against the taxonomy, validates eligibility deterministically with the policy clause cited,
surfaces fraud signals from a rule set without adjudicating them, and drafts the
recommendation and case packet.

Governance is an explicit step here, not a platform guardrail: the refusal has to be
defensible.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `return-intake` | Reads the order, receipt, SKU attributes and warranty |
| 2 | `policy-retrieve` | Retrieves the applicable return and warranty policy |
| 3 | `reason-classify` | Classifies the return reason against the taxonomy |
| 4 | `eligibility-check` | Validates eligibility with the clause cited — the Govern step |
| 5 | `case-packet` | Drafts the recommendation and the case packet |

## The case that shows why it exists

Loud, sympathetic, urgent — and every record says hold:

- **32 days against a 15-day electronics window** — ineligible, with the clause cited.
- The **serial on the unit does not match the serial sold** on that order — surfaced as a
  signal, not adjudicated.
- It is the **fourth receiptless return in 90 days**, above the value threshold.

The determination is ineligible, the recommendation is hold-for-review, the packet routes to
asset protection, and the manager exception is *drafted as a request* — the template never
grants it. A naive agent processes the goodwill refund to end the scene.

## What you bring

Return and warranty policy, receipts and order records, SKU attributes and serial data, your
reason-code taxonomy, carrier and RMA rules, and your fraud rule set.

## Boundaries

Draft-first. It never authorises a refund, releases funds, adjudicates fraud, disposes
inventory or books a carrier.

## Skills in this package

- **case-packet** — Drafts the return case packet - determination, recommendation, evidence list, fraud signals, customer response draft - from the contract payload. Use to close every return case: "build the case packet", "write up the return".
- **eligibility-check** — Determines return eligibility against the configured policy and surfaces fraud signals deterministically - the explicit Govern step of this plugin. Use on "is this returnable", "do they get a refund", "any red flags", after reason-classify.
- **policy-retrieve** — Retrieves the applicable return, warranty and price-match policy text and the customer's configured windows for the case. Use after return-intake, or on "what does the return policy say for <category>".
- **reason-classify** — Classifies the stated return reason against the customer's reason-code taxonomy with the deterministic reason_classify engine. Use after return-intake in every case, or on "what reason code is this".
- **return-intake** — Structures a return request - item, order/receipt, reason as stated, condition, serials, customer history - into the rtl.returns-refund-case.v1 contract. Use when the user says "customer wants to return", "process this return", "can they get a refund", or a return case begins.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/returns-refund-case/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/returns-refund-case/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
