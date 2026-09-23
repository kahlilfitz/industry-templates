---
name: register-search
description: Searches client, matter, adverse-party and independence registers using resolved legal names, aliases and corporate-family scope. Use after entity-resolve when the user says "search the conflicts system", "check the matter register", "look for adverse parties", before conflict-classify.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Risk and Compliance
---
# Register Search
## Purpose
Connect to the relevant registers and return the scoped evidence that the Govern step will classify.
## When to use
After `entity-resolve` and before `conflict-classify`.
## Inputs
`resolved.json`, plus exported or connected client, matter, adverse-party, independence and prior-clearance records.
## Steps
1. Search using every `entity_variants_tried` value and every controlled corporate-family entity ID emitted by `entity-resolve`.
2. Record the actual registers searched, date range, export timestamp and filters in `search_scope`.
3. Carry raw hits forward with register name, record ID, matched entity, relationship text, match score, source and citation.
4. Do not classify or waive anything; that is `conflict-classify`.
## Output
`registers.json` plus updated `search_scope` for the classification engine.
## Grounding requirements
Every hit cites the source register row or matter record. The memo must be able to state exactly what was searched and what was not searched.
## Constraints
- A name-only zero-hit result is not a clearance.
- Do not suppress family hits because the submitted client name is different.
- Do not decide that a similar-name hit is "probably unrelated"; carry the score and let the engine hold if required.
## Escalation / uncertainty
Unavailable registers, stale extracts, missing date ranges or unresolved parties must be written to `escalations[]`.
