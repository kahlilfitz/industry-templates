# Product Content & Catalog Enrichment

For merchandisers and PIM stewards turning supplier spreadsheets, spec sheets and manuals into
channel-ready records that satisfy a taxonomy, a brand voice and a regulated-claim boundary.

It ingests supplier sources, normalises attributes against the taxonomy with GTIN validation,
scores completeness per channel, validates claims and regulated terms against the approved
claim library, and drafts the descriptions and review packet.

This is the one template both sides of the trading relationship use, from opposite ends of the
same feed.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `source-ingest` | Reads supplier sheets, specs and portal exports |
| 2 | `attribute-normalize` | Normalises to the taxonomy, validates GTIN check digits (deterministic) |
| 3 | `gap-score` | Scores completeness per channel and names the missing fields per SKU |
| 4 | `claim-check` | Validates claims against the approved library — the Govern step |
| 5 | `content-draft` | Drafts descriptions, comparison copy and the review packet |

## The case that shows why it exists

*"Use the copy as written, launch Friday, their legal reviewed it."*

- One GTIN **fails the GS1 check digit** — the record is blocked before anything else runs.
- *"Kills 99.9%"*, *"antibacterial"* and *"biodegradable"* are regulated terms with **no
  substantiation in the claim library** for these products. The supplier's own legal review is
  not your substantiation.
- The draft ships with approved attributes only. Blocked claims never appear in the output.

## What you bring

PIM and GDSN records, supplier spreadsheets and portals, product manuals and specifications,
your approved claim library, brand and taxonomy guidelines, channel templates, and
regulated-term lists.

## Boundaries

Ends at an approval-ready draft record. It does not publish to channel, approve a regulated
claim or change the taxonomy.

## Skills in this package

- **attribute-normalize** — Normalises supplier fields to the taxonomy and validates GTIN check digits with the deterministic attribute_normalize engine. Use after source-ingest, or on "map these to our taxonomy", "are these GTINs valid".
- **claim-check** — Validates marketing claims and regulated terms against the approved claim library - the explicit Govern step - with the deterministic claim_check engine. Use on "is this copy safe", "can we say antibacterial", "check the claims", after gap-score.
- **content-draft** — Drafts channel descriptions, comparison copy and the review/approval packet from the governed payload. Use to close every enrichment batch: "draft the product copy", "build the review packet".
- **gap-score** — Scores per-SKU completeness against the channel's required fields with the deterministic completeness_score engine. Use on "how complete are these", "what's missing per SKU", after attribute-normalize.
- **source-ingest** — Ingests supplier spreadsheets, spec sheets and copy into the rtl.product-content-enrichment.v1 contract. Use when the user says "enrich these SKUs", "supplier sent the item sheet", "get these products channel-ready", or an enrichment batch begins.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/product-content-catalog-enrichment/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/product-content-catalog-enrichment/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
