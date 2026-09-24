---
name: scope-classify
description: Runs deterministic `scope_classify.py` after `scope-match` to determine IN_SCOPE, OUT_OF_SCOPE or AMBIGUOUS with the SOW clause quoted. Use when the user says "is this in scope?", "is this out of scope?", "should this be a change order?", "what is ambiguous?", or "where has scope drifted?" before `change-order-draft`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Scope Classify
## Purpose
Apply the SOW precedence rules deterministically and produce the contractual determination for each request.
## When to use
After `scope-match` in every Change Order & Scope Control run.
## Inputs
`matched.json` under contract `ps.change-order-scope-control.v1`.
## Steps
1. Validate that every matched request carries candidate clauses, source, confidence and citations.
2. Run `scripts/scope_classify.py --matched matched.json --out classified.json`.
3. Quote the engine output exactly: classification, rationale, rule, governing clause quote, citation and confidence.
4. Route AMBIGUOUS items to the engagement partner or contract manager. Do not force a binary decision.
5. Hand `classified.json` to `change-order-draft`.
## Output
`classified.json` with `classifications[]`, `ambiguity_list[]` and escalations.
## Grounding requirements
Every classification carries the quoted SOW clause and citation. AMBIGUOUS items cite the conflicting or missing evidence.
## Constraints
- Classification is rules-engine-only; the model never overrides IN_SCOPE, OUT_OF_SCOPE or AMBIGUOUS.
- Explicit exclusion beats implied inclusion unless the SOW directly contradicts itself.
- Confidence below 0.75 forces AMBIGUOUS.
## Escalation / uncertainty
AMBIGUOUS is a first-class outcome. Present it as a refusal to decide without human commercial review, not as a weak out-of-scope call.
