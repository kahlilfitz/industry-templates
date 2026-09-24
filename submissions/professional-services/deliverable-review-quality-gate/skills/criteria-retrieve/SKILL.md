---
name: criteria-retrieve
description: Retrieves the QRM quality framework, gate criteria, required disclaimer/reliance language, brand rules and prior-review findings. Use when the user says "which checklist applies?", "retrieve the gate criteria", "what disclaimer is required?", "check QRM requirements", or after `deliverable-ingest` before `assertion-map`.
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: analysis
---
# Criteria Retrieve
## Purpose
Load the quality framework and criteria that the deterministic engines will apply: substantiation, required language, scope alignment, confidentiality, brand, licensed-content attribution and prior-findings closure.
## When to use
After `deliverable-ingest` in every run, and whenever a reviewer asks "which checklist applies?", "what language is required?", or "what did QRM ask us to fix last time?".
## Inputs
- Quality and risk framework excerpts.
- Gate criteria and required disclaimer/reliance language.
- Brand and formatting standards.
- Prior review findings and closure tracker.
## Steps
1. Retrieve the criteria set that applies to the deliverable type, audience and intended recipients.
2. Identify whether third-party reliance language is required.
3. Normalize prior findings, closure status and required fixes.
4. Cite the numbered criteria sections the engines must use.
5. Pass the complete criteria payload to `assertion-map` and `gate-check`.
## Output
Contract payload with `criteria`, `prior_findings`, required language and citations to `quality-gate-criteria.md` and `severity-rules.md`.
## Grounding requirements
Every criterion used by an engine must cite a numbered section in the copied references.
## Constraints
- Retrieve criteria only; do not clear gates or make severity decisions.
- Reference excerpts are illustrative summaries, not copied standards or firm policies.
- Do not replace a missing criterion with a model assumption.
## Escalation / uncertainty
If the applicable framework is ambiguous, record an escalation to QRM and block gate determination until an owner selects the criteria set.
