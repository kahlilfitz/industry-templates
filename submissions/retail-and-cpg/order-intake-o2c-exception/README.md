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
