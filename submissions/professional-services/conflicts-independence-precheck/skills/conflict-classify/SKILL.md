---
name: conflict-classify
description: Applies deterministic conflicts and independence rules after register-search - the explicit Govern step. Use when the user asks "can we take this work?", "any conflicts?", "any independence issues with this client?", "is an ethical wall enough?", after register-search and before clearance-memo.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Risk and Compliance
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
4. A non-waivable category, prohibited-service category, forced-review identity band or confidence below floor remains a hold. The model never downgrades it.
## Output
`classified.json` containing `conflict_hits[]`, `precheck_position`, required consent or ethical-wall recommendations, and explicit search scope.
## Grounding requirements
Every hit carries the register, match score, relationship, governing rule, source, citation and confidence.
## Constraints
- The engine classifies; the model only explains.
- Never phrase the outcome as cleared, approved, no conflict or OK to proceed.
- A clean result is only "no hits found in the registers searched, subject to review" with scope stated.
## Escalation / uncertainty
Any hit, unresolved party, below-threshold confidence or unavailable register routes to human QRM review.
