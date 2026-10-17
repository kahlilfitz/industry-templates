---
name: closeout-retrieve
description: Retrieves the sanitised closeout knowledge record, deliverables, outcome evidence, engagement terms and reference register before Credential & Case Study Assembly begins. Use when the user says "write up this credential", "do we have a case study for this?", "pull the closeout record", "turn this closeout into a credential", or when a credential/case-study request begins. This runs before `credential-draft`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Closeout Retrieve
## Purpose
Retrieve and normalise the upstream closeout package inputs into `ps.credential-case-study-assembly.v1`: the closeout knowledge record, deliverables, outcome evidence, engagement terms, reference register and BD request.
## When to use
Start every Credential & Case Study Assembly run here, especially on "write up this credential", "can we use this client as a reference", "do we have a case study for this", or "turn the closeout into proposal copy".
## Inputs
- Sanitised closeout knowledge record from **Engagement Closeout & Knowledge Harvest** (`engagement-closeout-knowledge-harvest`), preferably the `ps.engagement-closeout-knowledge-harvest.v1` terminal `knowledge_record` where `downstream_handoff.consumer_template=credential-case-study-assembly`.
- Engagement workspace deliverable summaries and outcome evidence.
- Engagement terms/reference clauses and reference-register extract.
- Credential taxonomy and prior published credentials.
- BD or marketing request, including requested use (`pitch_only`, `public_marketing`, or `press`) and requested date.
## Steps
1. Confirm the upstream closeout record is sanitised and carries citations, confidence and provenance. Map `ps.engagement-closeout-knowledge-harvest.v1.engagement`, `knowledge_record.reusable_assets`, `knowledge_record.sanitisation_summary`, `knowledge_record.downstream_handoff.contract_fields` and related governed citations into this package's `engagement`, `client`, `deliverables`, `outcomes` and evidence fields without changing the permission rules.
2. Preserve every source citation from the closeout record. Never copy raw client-confidential content that the closeout package did not mark as safe for reuse.
3. Retrieve engagement terms and reference-register rows by the clause IDs in the closeout record. Missing rows are not neutral; they force the Govern step toward refusal (reference-naming-permission-rules.md #1.3, #8.1).
4. Capture the declared use before drafting starts. Permission scope depends on it (reference-naming-permission-rules.md #2).
5. Write the entry hop as `closeout-record.json` under contract `ps.credential-case-study-assembly.v1`.
## Output
`closeout-record.json` with engagement, client, deliverables, outcomes, request shell, confidence, provenance and citations.
## Grounding requirements
Every extracted field carries a source beginning with `connector:` or `skill:`, confidence, and citations back to the upstream closeout record, terms, register or BD request.
## Constraints
- Do not draft copy here.
- Do not infer permission from relationship history, events or partner statements.
- Do not proceed without a closeout knowledge record; this template has nothing reliable to read without the upstream handoff.
## Escalation / uncertainty
If closeout evidence, terms or reference-register rows are missing, continue only to produce a refusal/uncertainty record. Escalate missing upstream handoff to the closeout owner and reference operations.
