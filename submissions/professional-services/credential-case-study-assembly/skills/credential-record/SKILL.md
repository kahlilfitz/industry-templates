---
name: credential-record
description: Drafts the final credential entry and short, medium and long case-study copy after `permission-check` and optional `anonymize-variant`. Use when the user says "write the credential record", "draft the case study", "make the short and long versions", "prepare this for the credentials library", or "do we have a case study for this?".
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Business Development
---
# Credential Record
## Purpose
Produce the terminal draft artifact: credential entry, short/medium/long case-study copy, anonymised variant when required, cleared/uncleared figure list and permission record.
## When to use
After `permission-check`; after `anonymize-variant` when naming is refused.
## Inputs
`governed.json` under contract `ps.credential-case-study-assembly.v1`.
## Steps
1. Validate that `permission_verdict` exists. If it is missing, stop; no copy may be drafted without the Govern step.
2. Fill `templates/credential-record-template.md`.
3. If `naming_status=permit_to_name`, the named draft may use the client name but only cleared figures.
4. If `naming_status=refuse_to_name`, draft only the anonymised variant and use `safe_descriptor`.
5. Always attach the permission record, governing clause, cleared figures and uncleared figures. Uncleared figures belong in the "not for publishable copy" section only.
6. Mark the artifact DRAFT and pending legal/reference-owner approval.
## Output
`CREDENTIAL-<engagement_id>.md` or equivalent document containing the credential entry, case-study variants and clearance appendix.
## Grounding requirements
Every copy point is traceable to `governed.json`; every permission and figure decision cites the engine output and rules.
## Constraints
- Draft-first only: no publication, system-of-record write-back, approval or external send.
- Do not include refused client names, logos, testimonials, unsafe descriptors or uncleared figures in publishable copy.
- The model drafts prose; deterministic engines provide verdicts and cleared fact boundaries.
## Escalation / uncertainty
If the desired copy requires refused material, state exactly what is blocked and the clause/rule that blocks it. Route to reference operations for new written permission.
