---
name: permission-check
description: Determines whether the client can be named, whether logo/testimonial use is allowed, which figures are cleared, and whether an anonymised descriptor re-identifies the client. Use after `credential-draft` when the user asks "can we name this client?", "is this case study cleared?", "can we use this quote?", "can this go on the website?", or before any credential/case-study copy is published.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Permission Check
## Purpose
This is the explicit Govern step. Run deterministic `permission_check` so naming, logo, testimonial, figure clearance and anonymisation safety are decided by rules, not by the model.
## When to use
After `credential-draft` and before `anonymize-variant` or `credential-record`.
## Inputs
- `draft.json` from `credential-draft`.
- `engagement-terms.json`.
- `reference-register.json`.
- `bd-request.json`.
## Steps
1. Run `scripts/permission_check.py --draft draft.json --terms engagement-terms.json --register reference-register.json --request bd-request.json --out governed.json`.
2. Quote `permission_verdict` verbatim: naming status, clause, logo status, testimonial status, cleared figures, uncleared figures and anonymisation descriptor status.
3. Lead with refusal when permission is absent, expired, wrong-scope or expressly prohibited. Silence is not consent (reference-naming-permission-rules.md #1.3).
4. Keep cleared and uncleared figures structurally separated. Uncleared figures never appear in publishable copy (reference-naming-permission-rules.md #6.4).
5. If the proposed anonymised descriptor is re-identifying, use only the engine's `safe_descriptor`.
## Output
`governed.json`, the clearance and Govern hop.
## Grounding requirements
Every verdict cites the engagement clause, reference-register row or numbered rule section. Every outcome figure carries source, clearance state and governing clause.
## Constraints
- Default is REFUSE-TO-NAME unless express written permission covers the declared use.
- Partner recollection, conference participation and verbal assurances never override engagement terms.
- The model never upgrades a refused name, refused quote, refused logo, unsafe descriptor or uncleared figure.
## Escalation / uncertainty
Conflicts between terms, register and requester statements are escalations. The draft can continue only as a refused/anonymised record pending legal or reference-owner review.
