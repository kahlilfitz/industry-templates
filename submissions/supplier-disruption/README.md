# Supplier Disruption Assist

For the buyer or supply-chain planner who has just been told a shipment is late, and needs to
know what that actually costs before deciding how hard to push.

It takes the late PO, shipment delay, shortage or supplier notice, maps the shortage through
BOM where-used to the affected products, production lines, open orders and at-risk dates and
quantities, recommends a mitigation, computes an escalation tier, and drafts both the supplier
follow-up and the internal escalation brief.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `disruption-intake` | Reads the supplier notice, PO record and shipment data into the contract |
| 2 | `supply-knowledge-retrieve` | Pulls supplier master, on-time history and sourcing standards |
| 3 | `shortage-impact-map` | Maps the shortage through BOM where-used to products, lines, orders and dates (deterministic) |
| 4 | `mitigation-recommend` | Recommends expedite / substitute / reschedule and computes the escalation tier (deterministic) |
| 5 | `disruption-writeup` | Drafts the supplier follow-up and internal escalation brief |

## The case that shows why it exists

A supplier emails the buyer a reassuring note about 30 precision servo drives: *a small
scheduling adjustment… think about a week or so… nothing major.* Taken at face value, this is a
routine wave-it-through delay.

Two things change the answer:

- **The supplier portal** carries the system-confirmed revised date — a **14-day** slip, not
  "about a week". The portal date governs the email.
- **Context:** the part is single-source critical with almost no buffer (on-hand 2, safety stock
  4, lead time 42 days), it feeds a high-runner product, and a customer sales order sits in the
  blast radius.

The email and the data tell different stories. The template reads both and believes the data.

## What you bring

The supplier notice or email, the PO record, open orders, inventory status, BOM where-used, the
supplier master and on-time history. CSV exports from ERP/MRP are fine.

## Boundaries

Draft-first: nothing is auto-sent, and no PO or ERP record is written. It starts from PO and
email data; connecting live portal and ERP alerts is the graduation step.

Grounded in ERP/MRP data (D365 SCM, SAP), PO and shipment records, supplier master and
BOM where-used — see `references/`.
