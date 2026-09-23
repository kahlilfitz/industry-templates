---
name: knowledge-record
description: Drafts the knowledge record, lessons-learned narrative and sanitisation report after sanitize-check, using only governed release candidates. Use after sanitize-check when the user says "draft the knowledge record", "prepare for practice review", "write the closeout summary", "package this for reuse", or asks about the downstream credential-case-study-assembly handoff.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Closeout & Knowledge Management
---
# Knowledge Record
## Purpose
Produce the terminal draft: a practice-review-ready knowledge record with reusable assets, lessons learned, sanitisation report and downstream handoff fields populated from the governed contract payload.
## When to use
After `sanitize-check` completes. Use this for "draft the knowledge record", "prepare the closeout for practice review", "what can BD reuse?" or "send this to Credential & Case Study Assembly".
## Inputs
`governed.json` from `sanitize-check`, including `released_assets[]`, `held_assets[]`, `lesson_clusters[]`, `lessons_for_draft[]`, `sanitisation_report` and `knowledge_record` seed.
## Steps
1. Validate that `sanitize-check` has run. If `sanitisation_report` is missing, stop and run Govern first.
2. Draft the knowledge record from the `knowledge_record` seed: context, reusable assets, lesson themes, sanitisation summary and open holds.
3. Use only assets in `released_assets[]` for reusable body content; held assets may be listed in the sanitisation appendix with reasons.
4. Rewrite flagged lessons at role/process level, preserving the engine's rewrite guidance and citations.
5. Include the downstream handoff block for `credential-case-study-assembly`, with the fields that template may read and the warning that it inherits no publication permission.
6. Mark the result DRAFT - pending practice, legal or engagement-owner review.
## Output
A draft knowledge record and sanitisation report ready for practice review. The stable handoff object remains in `knowledge_record.downstream_handoff` for `credential-case-study-assembly`.
## Grounding requirements
Every asset and lesson paragraph cites governed payload ids and source citations. Every exclusion cites the sanitisation rule that held it.
## Constraints
- Draft-first: do not publish, clear a confidentiality restriction, approve external use, waive a client term or create a credential.
- Do not use held content in the reusable record body.
- Do not remove the sanitisation report; downstream users need to know what was excluded and why.
## Escalation / uncertainty
If all high-value assets are held, draft a record that says so and route to practice/legal review rather than inventing a sanitized case study. If Credential & Case Study Assembly requests a held asset, refuse and cite the hold.
