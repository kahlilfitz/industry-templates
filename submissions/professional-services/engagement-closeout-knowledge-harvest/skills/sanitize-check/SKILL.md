---
name: sanitize-check
description: Determines what may leave the engagement boundary using the deterministic sanitize_check Govern engine. Use after lesson-cluster when the user asks "can we share this externally?", "is this safe to reuse?", "sanitise the closeout record", "remove client-confidential material", or before knowledge-record.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Closeout & Knowledge Management
---
# Sanitize Check (Govern)
## Purpose
The sanitisation determination is the work: direct identifiers, personal data, commercial figures, licensed material, aggregation risk and confidence floor decide whether an item is held or becomes a release candidate for human review.
## When to use
After `lesson-cluster` and before `knowledge-record` on every closeout harvest; also whenever a user asks "can we share this externally?" or "is this safe to reuse?".
## Inputs
`lessons_clustered.json` containing scored assets, lesson clusters, retrospective inputs and confidentiality terms.
## Steps
1. Run `scripts/sanitize_check.py --input lessons_clustered.json --out governed.json`.
2. Quote `sanitisation_report.findings[]` verbatim, especially HOLD decisions.
3. Lead with aggregation-risk holds; individually safe facts can combine into a client-identification incident.
4. Pass only `released_assets[]` and rewritten lesson guidance to `knowledge-record`; held content stays named in the report but out of the reusable record body.
## Output
`governed.json` with `sanitisation_report`, `released_assets`, `held_assets`, lesson rewrite guidance and a stable `knowledge_record` payload seed.
## Grounding requirements
Every finding cites `confidentiality-sanitisation-rules.md`; every released asset carries `clearance_state`, confidence, source and citation.
## Constraints
- Default disposition is HOLD.
- Below-threshold confidence holds for human review.
- The model never overrides the engine's clearance state and never launders restricted content by paraphrase.
- A release candidate is not publication approval; all candidate states require human practice review.
## Escalation / uncertainty
Aggregation risk, missing rights evidence, embedded client identifiers, named-person blame or confidence below 0.80 all escalate to human review.
