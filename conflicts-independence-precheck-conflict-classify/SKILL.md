---
name: conflict-classify
description: Applies deterministic conflicts and independence rules after register-search - the explicit Govern step. Use when the user asks "can we take this work?", "any conflicts?", "any independence issues with this client?", "is an ethical wall enough?", after register-search and before clearance-memo.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Conflict Classify (Govern)
## Purpose
Classify every register hit by conflict type, waiver posture, ethical-wall eligibility and required action. This is a deterministic Govern step.
## When to use
After `register-search` in every conflicts and independence pre-check.
## Inputs
`resolved.json` and `registers.json`.
## Steps
1. Validate inputs against the contract.
2. Run `scripts/conflict_classify.py --resolved resolved.json --registers registers.json --out classified.json`.
3. Quote `conflict_hits[]`, `precheck_position` and `escalations[]` verbatim.
4. Read `search_scope.registers_not_searched`. If it is non-empty the search is incomplete and the result must never be presented as clean, whatever the hit count.
5. A non-waivable category, prohibited-service category, forced-review identity band or confidence below floor remains a hold. The model never downgrades it.
## Output
`classified.json` containing `conflict_hits[]`, `precheck_position`, `prior_clearance_context[]`, required consent or ethical-wall recommendations, and an explicit search scope that states both the registers searched and any supplied register the engine did not cover.
## Grounding requirements
Every hit carries the register, match score, relationship, governing rule, source, citation and confidence. The scope attestation is derived from the registers the engine actually read, never from the input's own claim.
## Constraints
- The engine classifies; the model only explains.
- Never phrase the outcome as cleared, approved, no conflict or OK to proceed.
- A clean result is only "no hits found in the registers searched, subject to review" with scope stated, and is only available when every supplied register was covered.
- `prior_clearance_context[]` is context for the reviewer. It never downgrades, suppresses or resolves a hit.
## Escalation / uncertainty
Any hit, unresolved party, below-threshold confidence, unavailable register or uncovered supplied register routes to human QRM review.
