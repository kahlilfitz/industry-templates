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
