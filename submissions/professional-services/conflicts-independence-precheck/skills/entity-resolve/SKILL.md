---
name: entity-resolve
description: Resolves prospective client names, aliases, trading brands and corporate-family structure for a conflicts check. Use after party-intake when the user says "resolve this client", "who is the parent?", "check affiliates", "any independence issues with this client?", before register-search.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Entity Resolve
## Purpose
Apply deterministic entity matching and corporate-family expansion before any register search. This is how a brand, subsidiary or transliterated name is tied to the legal entity and ultimate parent.
## When to use
After `party-intake` in every pre-check.
## Inputs
`intake.json` plus a corporate-structure extract in JSON form.
## Steps
1. Validate input against the contract.
2. Run `scripts/entity_resolve.py --intake intake.json --corporate-structure corporate-structure.json --out resolved.json`.
3. Quote the engine's match status, score, variants and family scope verbatim.
4. Treat `human_review` as a hold. The model may explain why the candidate is similar, but it must not resolve the entity.
## Output
`resolved.json` containing `resolved_entities[]`, `search_scope.entity_variants_by_party` and corporate-family IDs.
## Grounding requirements
Every resolved entity includes match score, source, citation and rule reference. Corporate-family expansion cites the source extract and ownership/control evidence.
## Constraints
- The engine computes identity and match status.
- A score below the automatic threshold is never promoted by the model.
- Corporate-family members at or above the ownership/control threshold must be included in search scope.
## Escalation / uncertainty
Scores in the forced-review band, missing ownership evidence or inconsistent corporate-structure records create a human-review escalation.
