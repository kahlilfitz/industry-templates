---
name: role-intake
description: Reads a signed engagement, SOW extract, mobilisation note or staffing request into the staffing contract. Use when the user says "new engagement signed", "staff this SOW", "who can we staff on this?", "mobilise this project", or "start a staffing slate".
license: Proprietary
metadata:
  version: "1.0"
  author: Microsoft Professional Services Skills
  category: Mobilisation
---
# Role Intake
## Purpose
Normalise the signed engagement request and SOW role extract into the `ps.engagement-staffing-bench-match.v1` contract: engagement identity, client, practice, role requirements, start dates, allocations, location, language, rate band and citations.
## When to use
At the start of every Engagement Staffing & Bench Match run.
## Inputs
- Staffing request email or mobilisation note.
- SOW role extract with open roles, start dates, expected duration and required skills.
- Rate-card or commercial guardrail excerpt if supplied.
## Steps
1. Extract `engagement{}` with `source`, `confidence` and `citation`.
2. Extract each role into `roles[]`: required and preferred skills, required certifications, seniority, start date, allocation, location, language, duration and rate band.
3. Preserve uncertainty. If a role requirement is ambiguous, carry it as an escalation rather than guessing.
4. Hand off the contract payload to `bench-query`.
## Output
`roles.json` or an equivalent contract payload containing `engagement{}` and `roles[]`.
## Grounding requirements
Every role field cites the SOW clause, staffing email line or rate-card excerpt it came from.
## Constraints
- Do not score fit, rank candidates, infer availability or clear conflicts.
- Do not create a staffing assignment or update any system of record.
## Escalation / uncertainty
Missing start date, allocation, required skill, client identity, or rate band should be flagged before scoring. Low-confidence extraction below 0.75 is held for human review under `independence-eligibility-rules.md #8.1`.
