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

## Skills in this package

- **artifact-assemble** — Retrieves and normalizes the engagement artifact set, deliverable register, decision log, status history, retrospective notes and confidentiality terms for closeout. Use when the user says "close out the engagement", "assemble the final deliverables", "harvest lessons learned", "what can we reuse from this?", or when an engagement closeout begins before asset-identify.
- **asset-identify** — Scores candidate reusable assets and builds the final deliverable index with completeness gaps using the deterministic asset_identify engine. Use after artifact-assemble when the user asks "what can we reuse from this?", "find reusable assets", "shortlist closeout assets", or "is the final deliverable package complete?".
- **knowledge-record** — Drafts the knowledge record, lessons-learned narrative and sanitisation report after sanitize-check, using only governed release candidates. Use after sanitize-check when the user says "draft the knowledge record", "prepare for practice review", "write the closeout summary", "package this for reuse", or asks about the downstream credential-case-study-assembly handoff.
- **lesson-cluster** — Clusters decisions and retrospective inputs into lesson themes with the deterministic lesson_cluster engine. Use after asset-identify when the user says "lessons learned", "cluster the retrospective", "what did we learn?", or "write the closeout lessons".
- **sanitize-check** — Determines what may leave the engagement boundary using the deterministic sanitize_check Govern engine. Use after lesson-cluster when the user asks "can we share this externally?", "is this safe to reuse?", "sanitise the closeout record", "remove client-confidential material", or before knowledge-record.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/engagement-closeout-knowledge-harvest/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/engagement-closeout-knowledge-harvest/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
