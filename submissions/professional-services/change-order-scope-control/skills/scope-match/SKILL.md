---
name: scope-match
description: Runs deterministic `scope_match.py` after `request-intake` to match each request to SOW scope, deliverables, assumptions and exclusions. Use when the user asks "which SOW clause applies?", "map this to the SOW", "is this in scope?", "should this be a change order?", or "where has scope drifted?" before `scope-classify`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Scope Match
## Purpose
Match each normalized request to candidate SOW clauses without making the commercial determination.
## When to use
After `request-intake` in every Change Order & Scope Control run.
## Inputs
`sow.json`, `requests.json`, `prior-change-orders.json` and `delivered-artifacts.json` under contract `ps.change-order-scope-control.v1`.
## Steps
1. Validate that each request has tags, source, citation, confidence and estimate basis.
2. Run `scripts/scope_match.py --sow sow.json --requests requests.json --prior-change-orders prior-change-orders.json --delivered-artifacts delivered-artifacts.json --out matched.json`.
3. Quote matched clause ids, clause types, quotes, citations and confidence verbatim.
4. Do not say whether the item is in scope; hand `matched.json` to `scope-classify`.
## Output
`matched.json` with `matches[]`: candidate clauses per request, including quote, citation, match reason, confidence and source.
## Grounding requirements
Every matched clause cites the SOW/MSA clause. Matching cites `scope-classification-rules.md` where it uses tags and confidence floors.
## Constraints
- All matching happens in `scope_match.py`; the model never adds an uncited clause.
- A match is not a verdict.
- No network calls, no model calls and no write-back.
## Escalation / uncertainty
If no clause matches or confidence is below the floor, preserve the low-confidence match state so `scope-classify` can return AMBIGUOUS.
