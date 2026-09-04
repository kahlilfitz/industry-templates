# Supplier Qualification

For the sourcing lead deciding whether a new supplier gets on the approved vendor list — on the
evidence, not on the pitch.

It gathers the supplier dossier of certificates, financials, audits and PPAP elements, scores
risk across quality, financial and geographic dimensions, compares the supplier against the
approved vendor list and the category requirements, and drafts the qualification memo with its
conditions.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `dossier-ingest` | Gathers certs, financials, audit results and PPAP elements into the contract |
| 2 | `risk-score` | Scores risk across quality, financial and geographic dimensions (deterministic) |
| 3 | `avl-compare` | Compares against the approved vendor list and category requirements (deterministic) |
| 4 | `qualification-memo` | Drafts the qualification memo with named conditions |

## The case that shows why it exists

"22% cheaper, big logos, sign it this week." The dossier says otherwise:

- The IATF certificate **expired** three months ago — quality risk high.
- The quick ratio is 0.72 **and declining** — financial risk high.
- The supplier sits in the same region that already carries 68% of the category — concentration
  risk.
- The control plan is missing from the PPAP submission.

The result is an overall high-risk **do-not-qualify** with named, closeable conditions: a
re-issued certificate, PPAP completion, a dual-source plan, and a council override if the
business still wants to proceed.

A naive memo approves on brand and price. This one lists what would have to be true first.

## What you bring

The supplier dossier — certificates, financial statements, audit reports, PPAP elements — plus
your approved vendor list and category requirements.

## Boundaries

Draft-first: the memo is a recommendation for the sourcing council. Nothing is added to the AVL
by the template.

Grounded in PPAP/APQP and the qualification rules in `references/` — replace them with your own.

## Skills in this package

- **avl-compare** — Compares the candidate against the approved vendor list and category requirements and produces the banded recommendation, using the deterministic avl_match engine. Use when the user says "how do they compare to our current vendors", "check the AVL", "should we qualify them", or after risk-score in a run.
- **dossier-ingest** — Gathers the supplier's qualification documents - certificates, financials, audit reports, PPAP elements - into the mfg.supplier-qualification.v1 contract. Use when the user says "qualify this supplier", "review the supplier package", "new vendor for <category>", or when a qualification run begins.
- **qualification-memo** — Drafts the supplier qualification memo for approval from the contract payload - outcome, conditions, risk detail, AVL position. Use when the user says "draft the qualification memo", "write it up for approval", or after avl-compare in a run.
- **risk-score** — Scores supplier risk across quality, financial and geographic dimensions with the deterministic risk_score engine. Use when the user says "score this supplier", "how risky are they", "run the risk assessment", or after dossier-ingest in a qualification run.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/supplier-qualification/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/supplier-qualification/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
