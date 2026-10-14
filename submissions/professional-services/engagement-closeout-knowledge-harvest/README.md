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

This is the upstream dependency for **Credential & Case Study Assembly** (`credential-case-study-assembly`). The terminal `knowledge_record` object in the contract has a stable shape for that downstream template: reusable assets carry `clearance_state`, held assets carry rule citations, and lessons contain only governed category, evidence-ID, citation and drafting-guidance fields. Raw `client_descriptor`, retrospective text and `summary_seed` values are excluded. `downstream_handoff.consumer_template` is set to `credential-case-study-assembly`.

The handoff is intentionally conservative. Credential assembly may read the record, but it does not inherit permission to publish, quote a client, use a logo, disclose figures or waive terms.

**Engagement Mobilization & Onboarding Pack** (`engagement-mobilization-onboarding-pack`) also reads this record through its Scenario 01 adapter: only `knowledge_record`, `released_assets` and provenance/citations, never `held_assets` or raw `candidate_assets`. The `ps.engagement-closeout-knowledge-harvest.v1` contract is unchanged in 1.0.3.

## What you bring

An engagement workspace or SharePoint folder, the deliverable register, decision and risk logs, status history, retrospective notes, confidentiality terms, the firm's knowledge taxonomy and prior knowledge records.

### Size and runtime

Screening is linear in the number of records, so a large closeout is processed whole. Each input array (deliverable register, candidate assets, decision log, retrospective inputs, confidentiality terms) and the upstream `escalations` list holds at most 1000 records, the input arrays and `escalations` together at most 2500, and each text or name list inside a record (`named_people`, `third_party_products`) at most 200 items. A larger input is refused before anything is screened (`input error: ... above the screening ceiling (#8.1)`); nothing is dropped silently. Harvest one workstream or phase per run instead, each with its own knowledge record. Each engine stage takes about 9 seconds per 100 candidate assets (about 35 seconds for 400, about 90 for 1000), and up to about 2.5 minutes at the 2500-record ceiling.

## Package

From 1.0.3 the plugin ships as a MOS3 Microsoft 365 app package (manifest 1.28). The ZIP holds only `manifest.json`, `color.png`, `outline.png` and `skills/`. Each skill is self-contained: it carries its own copy of the contract (`contracts/`), the three rule references (`references/`) and, for the engine skills, its Python engine (`scripts/`). The engines use the Python 3 standard library only and read and write only the paths given by `--input` and `--out`.

## Tests and demo data

Demo data and the regression suite are not in the package. They live in this folder's `demo-data/` and `tests/` (see [`tests/README.md`](tests/README.md)). The two scenarios there include raw transcript, CSV and terms excerpts alongside structured JSON so the Connect path is real.

```powershell
cd submissions\professional-services\engagement-closeout-knowledge-harvest
python tests\test_engines.py                                 # against this submission folder
python tests\test_engines.py --plugin-root <extracted ZIP>   # against a built package
```

## Boundaries

Draft-first: the template assembles and drafts. It does not publish to the knowledge base, clear a confidentiality restriction, approve external use, waive a client term, create a credential, send client-facing material or write back to a system of record. Below-threshold confidence and any aggregation risk default to HOLD for human review.
