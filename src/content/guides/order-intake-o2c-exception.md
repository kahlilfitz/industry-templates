# Order Intake & O2C Exception

For order-management and customer-service teams in grocery, CPG and wholesale, where a large
share of orders still arrive as unstructured email, PDF and portal submissions and get rekeyed
into ERP by hand.

It extracts and normalises the order lines, validates them against customer, pricing, product
and credit master data, queues exceptions with reason codes and a recommended correction for
each, and drafts the customer response.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `order-ingest` | Extracts lines from email, PDF and portal submissions |
| 2 | `line-normalize` | Normalises products, units of measure and quantities |
| 3 | `order-validate` | Validates against customer, price, product and credit rules (deterministic) |
| 4 | `exception-route` | Queues exceptions with reason codes and a recommended correction |
| 5 | `response-draft` | Drafts the customer or internal response |

## The case that shows why it exists

*"Just key it, truck at 2."* Four traps in a single line:

- The product alias resolves to **two different products** — vegan and standard — so the SKU
  is ambiguous.
- **500 eaches** from a customer who always orders cases, with a typical quantity of 40: both
  a unit-of-measure and a quantity anomaly.
- **12% below list** with no promotion reference — a price deviation.
- The exposure would **pass the credit limit**, so it queues for credit review rather than
  bouncing the customer.

Four exceptions routed with corrections, one clarification drafted, and the order held. A
naive clerk rekeys it as-is and ships 500 eaches of the wrong product below cost.

## What you bring

Customer and pricing master, product master and unit-of-measure rules, trading terms, credit
rules, order history, and carrier and delivery rules.

## Boundaries

Ships at action level L0–L2: order creation and release stay human-approved until you promote
the action level in `config/`. Autonomous order entry is a deliberate later step, once
validation accuracy is agreed.

## Skills in this package

- **exception-route** — Queues validation exceptions with reason codes and a recommended correction per exception, deterministically. Use on "route the exceptions", "what needs fixing before entry", after order-validate.
- **line-normalize** — Normalises extracted order lines - whitespace, casing, UOM tokens, qty formats - without changing meaning, preparing them for validation. Use after order-ingest.
- **order-ingest** — Ingests orders arriving as email, PDF or portal export into the rtl.order-intake-o2c.v1 contract. Use when the user says "order came in by email", "key in this PO", "process the attached order", or an order document arrives.
- **order-validate** — Validates the order against customer, pricing, product and credit masters deterministically with the order_validate engine. Use on "is this order clean", "validate before entry", after line-normalize.
- **response-draft** — Drafts the customer confirmation or clarification message and the internal entry note from the routed payload. Use to close every order run - "draft the reply to the customer", "write up the order status".

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/order-intake-o2c-exception/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/order-intake-o2c-exception/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
