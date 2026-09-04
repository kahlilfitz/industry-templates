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

## Skills in this package

- **disruption-intake** — Picks up a supply disruption from a PO record, shipment feed, supplier email or portal notice and pulls it into the mfg.supplier-disruption.v1 contract inputs. Use when the user says "a PO is late", "our supplier is delayed", "we're short on a part", "process this supplier notice", "shipment is going to slip", or when a Supplier Disruption Agent run begins.
- **disruption-writeup** — Drafts the supplier follow-up and the internal escalation brief from the assembled contract payload, with the impact and mitigation cited to the ERP/MRP, supplier master and rules. Use when the user says "draft the supplier email", "write the escalation brief", "draft the follow-up", "give me the escalation", "write it up", or after mitigation-recommend completes.
- **mitigation-recommend** — Chooses the mitigation (expedite, substitute or reschedule) for a mapped shortage and computes the escalation tier and owner-notification list, deterministically. Use when the user says "what do we do about it", "should we expedite or substitute", "recommend a mitigation", "who do we escalate to", "who do we notify", or after shortage-impact-map completes.
- **shortage-impact-map** — Maps a part shortage through BOM/where-used to the affected products, production lines and open orders, with the quantity and date at risk per order, deterministically. Use when the user says "what does this shortage affect", "which lines and orders are hit", "when does this bite", "map the impact", "what's at risk", or after supply-knowledge-retrieve completes.
- **supply-knowledge-retrieve** — Retrieves the ERP/MRP supply position, supplier master, BOM/where-used and open orders relevant to a disruption and attaches them plus the supplier's delivery history to the mfg.supplier-disruption.v1 contract. Use when the user says "what does this part go into", "where is this used", "what's our on-hand and lead time", "is this single-source", "has this supplier been late before", or after disruption-intake completes.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/supplier-disruption/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/supplier-disruption/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
