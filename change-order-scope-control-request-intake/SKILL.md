---
name: request-intake
description: Extracts inbound client requests, mail-thread pressure, delivered artifacts and effort estimates into the contract after `sow-retrieve`. Use when the user says "review these requests", "is this in scope?", "should this be a change order?", "pull the request log", "what scope has drifted?", or "turn these emails into scope items".
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Request Intake
## Purpose
Normalize messy request evidence into cited request records that deterministic engines can match, classify and price.
## When to use
After `sow-retrieve`, before `scope-match`, whenever mail threads, task logs, chat excerpts or delivered-artifact inventories need to become scope items.
## Inputs
- Request log, task-system export or issue list.
- Mail threads and meeting notes containing client asks.
- Delivered-artifact inventory.
- Rate card and role-based estimates supplied by the delivery lead.
## Steps
1. Extract one request per discrete ask. Keep the client's wording in `request_text` and summarize without deciding scope.
2. Assign evidence tags only when grounded in the SOW or request text; tags are inputs to `scope_match.py`, not verdicts.
3. Capture estimate hours by role and the estimate basis. If estimate basis is missing, mark it for escalation rather than inventing hours.
4. Preserve provenance: each request needs `source`, `citation`, `confidence` and any delivered-artifact link.
5. Hand the structured request payload to `scope-match`.
## Output
`requests.json`, delivered-artifact inventory and rate-card inputs under contract `ps.change-order-scope-control.v1`.
## Grounding requirements
Every request cites the mail, task, meeting note or artifact inventory row it came from. Every estimate cites the delivery lead estimate or work log basis.
## Constraints
- The model extracts and structures only; it never decides in-scope versus out-of-scope.
- Do not collapse multiple asks into one line if they have different SOW clauses or estimates.
- Do not compute totals; `delta_calc.py` owns all math.
## Escalation / uncertainty
If a request lacks enough evidence to cite, flag it as intake-incomplete so `scope-classify` can return AMBIGUOUS rather than guessing.
