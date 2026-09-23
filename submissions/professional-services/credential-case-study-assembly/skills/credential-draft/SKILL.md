---
name: credential-draft
description: Matches a closeout record to the credential taxonomy and prepares the structured draft plan before permissions are checked. Use after `closeout-retrieve` when the user says "write up this credential", "draft the case study", "make this proposal credential", or "classify this engagement for credentials"; run before `permission-check`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Business Development
---
# Credential Draft
## Purpose
Run the deterministic `credential_draft` engine to classify the closeout record against the credential taxonomy and prepare a draft plan for credential and case-study copy.
## When to use
After `closeout-retrieve`, before any permission-dependent copy is drafted.
## Inputs
`closeout-record.json` under contract `ps.credential-case-study-assembly.v1`.
## Steps
1. Validate that the payload carries engagement, client, deliverables, outcomes, confidence, provenance and citations.
2. Run `scripts/credential_draft.py --closeout closeout-record.json --out draft.json`.
3. Quote taxonomy values and confidence exactly from the engine: sector, service line, capability, engagement size band and outcome type.
4. Do not write final marketing prose yet. The next skill decides which names and figures are cleared.
## Output
`draft.json` with `taxonomy_match` and `draft_assets` populated.
## Grounding requirements
Every taxonomy value cites `credential-taxonomy.md`; low-confidence or ambiguous matches remain visible in `taxonomy_match.escalations`.
## Constraints
- The model never computes or overrides a taxonomy match.
- Do not blend outcome figures into prose before clearance.
- Draft plan only; naming and figure clearance belong to `permission-check`.
## Escalation / uncertainty
If taxonomy confidence is below 0.72 or values tie within the ambiguity band, keep the engine's best match but flag review by the credential taxonomy owner.
