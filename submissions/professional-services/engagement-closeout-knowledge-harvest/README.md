# Engagement Closeout & Knowledge Harvest

For delivery leads, engagement managers and knowledge managers who know the reusable value is highest at closeout - exactly when the team is rolling onto the next pursuit.

This template assembles the final deliverable package, extracts lessons from the decision log and retrospective inputs, identifies genuinely reusable assets, runs a confidentiality and sanitisation gate, and drafts a knowledge record for practice review. It makes the closeout step compound: this engagement gets archived cleanly, and the next engagement starts cheaper.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `artifact-assemble` | Retrieves the engagement artifact set, deliverable register, decision log, retrospective inputs and confidentiality terms into `ps.engagement-closeout-knowledge-harvest.v1` |
| 2 | `asset-identify` | Scores candidate reusable assets with the deterministic `asset_identify` engine and builds the final deliverable index with completeness gaps |
| 3 | `lesson-cluster` | Clusters decisions and retrospective inputs into lesson themes with the deterministic `lesson_cluster` engine |
| 4 | `sanitize-check` | Performs the explicit Govern step with the deterministic `sanitize_check` engine: direct identifiers, personal data, commercial figures, licensed material, aggregation risk and confidence floor |
| 5 | `knowledge-record` | Drafts the knowledge record, lessons-learned narrative and sanitisation report from the governed payload |

Numbers and verdicts come from deterministic Python engines (`asset_identify`, `lesson_cluster`, `sanitize_check`). The model writes the lesson prose and the knowledge-record narrative, but it never decides that something is safe to release.

## The case that shows why it exists

Scenario B is the confidentiality incident a naive closeout creates. Each item looks safe one at a time: an anonymised architecture diagram, a "European utility client" descriptor, a 6,200-headcount figure, a go-live date and a named third-party product. Together, those facts identify the synthetic client to anyone in the sector.

The Govern engine catches the aggregation risk and HOLDS the package. It also catches a valuable reusable deck with an embedded client logo/name in a page-three diagram caption, and a retrospective quote that names an individual and attributes blame. The output does not quietly drop those items: it names what was removed or held, cites the rule, and gives rewrite guidance.

## Downstream handoff

This is the upstream dependency for **Credential & Case Study Assembly** (`credential-case-study-assembly`). The terminal `knowledge_record` object in the contract has a stable shape for that downstream template: reusable assets carry `clearance_state`, held assets carry rule citations, lessons carry sanitisation notes, and `downstream_handoff.consumer_template` is set to `credential-case-study-assembly`.

The handoff is intentionally conservative. Credential assembly may read the record, but it does not inherit permission to publish, quote a client, use a logo, disclose figures or waive terms.

## What you bring

An engagement workspace or SharePoint folder, the deliverable register, decision and risk logs, status history, retrospective notes, confidentiality terms, the firm's knowledge taxonomy and prior knowledge records. The demo scenarios include raw transcript, CSV and terms excerpts alongside structured JSON so the Connect path is real.

## Boundaries

Draft-first: the template assembles and drafts. It does not publish to the knowledge base, clear a confidentiality restriction, approve external use, waive a client term, create a credential, send client-facing material or write back to a system of record. Below-threshold confidence and any aggregation risk default to HOLD for human review.
