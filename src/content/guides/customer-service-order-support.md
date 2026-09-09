# Customer Service & Order Support

For contact-centre and digital-care agents handling the small, repeatable set of intents that
carry most retail service traffic — where is my order, can I return this, is it in stock, what
does the policy say.

It classifies intent against the taxonomy, assembles customer, order, loyalty and delivery
context while detecting contradictions between sources, retrieves the approved answer, and
either drafts the resolution in channel and tone or builds a structured handoff packet.

The design bet is reliability over reach: a confident wrong answer costs more than an
escalation.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `inquiry-intake` | Classifies intent against the taxonomy (deterministic) |
| 2 | `context-assemble` | Consolidates customer, order, loyalty and delivery context; flags contradictions |
| 3 | `knowledge-retrieve` | Retrieves the approved answer with its citation |
| 4 | `resolution-draft` | Drafts the resolution in the customer's channel and tone |
| 5 | `handoff-packet` | Builds the structured escalation when confidence is below threshold |

## The case that shows why it exists

Delivered-not-received, with refund-now pressure and a chargeback threat.

- The intent resolves to **delivered-not-received**, which outranks a routine order-status
  read.
- The **carrier scan contradicts the customer's account** — the contradiction is recorded with
  its citation, and the interim reply never disputes the customer directly.
- The instant-resolution gate is **not met** on tier or value, so it routes to investigation
  with the clock attached, and goodwill is recorded as a **proposal for a human**.

A naive agent promises the instant refund.

## What you bring

Knowledge articles, CRM case history, OMS order status, loyalty records, delivery and carrier
status, product documentation, approved scripts and service policy.

## Boundaries

Resolution drafts and escalation packets. It does not issue goodwill credit, change payment
details or grant an unsupported policy exception.

## Skills in this package

- **context-assemble** — Assembles customer, order, loyalty and carrier context, detects record-vs-account contradictions, and selects the resolution path deterministically with the context_assemble engine. Use after inquiry-intake, or on "pull up everything on this order".
- **handoff-packet** — Builds the structured escalation packet when the run cannot resolve - intent, context, contradictions, what was checked, recommended next step. Use on any low-confidence, contradicted, or out-of-scope run: "escalate this", "hand off to tier 2".
- **inquiry-intake** — Takes the customer inquiry from any channel and classifies intent against the taxonomy with the deterministic intent_classify engine. Use when a service inquiry arrives - "where is my order", "it says delivered but I never got it", "can I return this", "is it in stock", "how do I set this up".
- **knowledge-retrieve** — Retrieves the approved knowledge article, policy text or product doc that grounds the answer for the classified intent. Use after context-assemble, or on "what's the approved answer for this".
- **resolution-draft** — Drafts the customer-facing resolution in the right channel and tone from the assembled context and approved sources. Use to close resolvable runs - "draft the reply", "answer the customer".

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/customer-service-order-support/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/customer-service-order-support/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
