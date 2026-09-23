---
name: asset-identify
description: Scores candidate reusable assets and builds the final deliverable index with completeness gaps using the deterministic asset_identify engine. Use after artifact-assemble when the user asks "what can we reuse from this?", "find reusable assets", "shortlist closeout assets", or "is the final deliverable package complete?".
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Closeout & Knowledge Management
---
# Asset Identify
## Purpose
Apply `references/reuse-asset-rubric.md` deterministically: final deliverable index, closeout completeness gaps, reuse score and reuse recommendation for each candidate asset.
## When to use
After `artifact-assemble` in every closeout harvest and whenever a delivery lead asks "what can we reuse from this?" or "is the closeout package complete?".
## Inputs
The contract entry payload (`ps.engagement-closeout-knowledge-harvest.v1`) containing artifacts and candidate_assets.
## Steps
1. Run `scripts/asset_identify.py --input engagement.json --out asset_shortlist.json`.
2. Quote the engine's deliverable gaps and reuse scores verbatim.
3. Pass all confidentiality markers and aggregation tokens forward unchanged to `lesson-cluster` and `sanitize-check`.
4. Make clear that a high reuse score is not a clearance decision.
## Output
`asset_shortlist.json` with `deliverable_index[]`, `reusable_asset_shortlist[]`, `escalations[]` and provenance.
## Grounding requirements
Every score cites `reuse-asset-rubric.md`; every completeness gap cites the source deliverable register row.
## Constraints
- The model never changes a score, recommendation band or completeness gap.
- Reuse value is separate from release permission.
- Do not draft the knowledge record yet; the Govern step must run first.
## Escalation / uncertainty
Scoring confidence below 0.70 prevents `shortlist` and routes the asset to internal retention or archive pending review.
