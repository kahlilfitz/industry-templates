---
name: assertion-map
description: Maps deliverable assertions to the support pack and computes whether each assertion is supported, limited or unsupported with deterministic `assertion_map`. Use when the user says "what's not substantiated?", "check the claims", "trace the £4.2m saving", "which assertions lack evidence?", or after `criteria-retrieve` before `gate-check`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Quality assurance
---
# Assertion Map
## Purpose
Determine evidence support for each located assertion. Assertion classes matter: factual, quantified, forward-looking/opinion and recommendation claims have different evidence requirements.
## When to use
After `deliverable-ingest` and `criteria-retrieve`, before `gate-check`; also for direct questions like "what's not substantiated?" or "does this saving claim trace to evidence?".
## Inputs
Contract payload containing deliverable metadata, extracted assertions and evidence set.
## Steps
1. Validate the payload shape and contract version.
2. Run `scripts/assertion_map.py --input review-input.json --out assertion-mapped.json`.
3. Quote `support_status`, `support_score`, evidence IDs and rule citations verbatim.
4. Pass unsupported and limited assertion findings to `gate-check`.
## Output
`assertion-mapped.json` with `assertion_mappings[]`, evidence-support findings and escalations.
## Grounding requirements
Every mapping must cite the assertion location, evidence citation, criteria section and engine source.
## Constraints
- Evidence-support verdicts are engine-only; the model never rounds verbal support into substantiation.
- Quantified claims require traceable analytical evidence, not a stakeholder estimate.
- Recommendations based on small samples must remain limited or unsupported unless the limitation is stated.
## Escalation / uncertainty
Missing evidence, low confidence or ambiguous assertion class is escalated for human confirmation and carried into the review packet.
